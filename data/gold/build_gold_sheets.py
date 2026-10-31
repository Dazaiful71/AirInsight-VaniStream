"""S6: build the annotation sheets (genre, duplicate pairs, query template) from option A transcripts.

Nothing here labels anything. Only VALIDATION and TEST days (config/sample_config.json, option A split) are read;
train days are never opened. No network, no downloads, no transcription.

Run from the project folder:
  .venv_gpu/Scripts/python.exe data/gold/build_gold_sheets.py
"""
import csv
import json
import os
import random
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from air_bulletins_scraper import parse_hour_from_url  # noqa: E402
from nlp_pipeline import GENRE_LABELS, embed_sentences, segment_sentences  # noqa: E402

SEED = 42
GOLD = os.path.join("data", "gold")
BASE = os.path.join("data", "sample_A")
MIN_WORDS = 4                 # fragments shorter than this are not offered for labelling
N_GENRE = 400
N_OVERLAP = 175
BANDS = [(0.60, 0.70), (0.70, 0.80), (0.80, 0.85), (0.85, 0.90), (0.90, 0.95)]
PER_BAND = 16
N_NEG = 20
NEG_MAX_SIM = 0.40
MAX_HOUR_GAP = 2              # candidate pairs: same day, different bulletin file, hours at most this far apart


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:   # BOM so Excel shows Hindi/UTF-8 correctly
        w = csv.DictWriter(handle, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    plan = json.load(open(os.path.join("config", "sample_config.json"), encoding="utf-8"))
    split = plan["pilot_plan_s4"]["option_A_about_10_days"]["split"]
    eval_days = {d: s for s in ("val", "test") for d in split[s]["days"]}
    train_days = set(split["train"]["days"])
    assert not (set(eval_days) & train_days)

    rows = [r for r in csv.DictReader(open(os.path.join(BASE, "metadata.csv"), encoding="utf-8"))]
    # leakage guard 1: the csv's own split column must agree with the config for every row we use
    for r in rows:
        if r["date"] in eval_days:
            assert r["split"] == eval_days[r["date"]], (r["date"], r["split"])
        elif r["date"] in train_days:
            assert r["split"] == "train"

    # ---- sentence pool (val/test days only), project segmentation
    pool = []
    for r in sorted((r for r in rows if r["date"] in eval_days), key=lambda r: (r["date"], r["audio_file"])):
        text = open(os.path.join(BASE, r["transcript_file"]), encoding="utf-8").read()
        hhmm, hour, _flag = parse_hour_from_url(r["audio_url"])
        fname = os.path.basename(r["audio_url"])
        stem = os.path.splitext(fname)[0]
        pos = 0
        for s in segment_sentences(text):
            if len(s.split()) < MIN_WORDS:
                continue
            pos += 1
            pool.append({"id": f"{r['date']}_{stem}_s{pos:03d}", "date": r["date"], "hour": "" if hour is None else hour,
                         "source_file": fname, "position": pos, "split": eval_days[r["date"]], "text": s})
    by_day = defaultdict(list)
    for p in pool:
        by_day[p["date"]].append(p)
    print("pool (val/test, >=%d words): %d sentences from %d bulletins" % (MIN_WORDS, len(pool), len({p['source_file'] + p['date'] for p in pool})))
    print("pool per day:", {d: len(v) for d, v in sorted(by_day.items())})

    # ---- 1. genre sheet: proportional per day (largest remainder), random within day
    days = sorted(by_day)
    raw = {d: N_GENRE * len(by_day[d]) / len(pool) for d in days}
    alloc = {d: int(raw[d]) for d in days}
    for d in sorted(days, key=lambda d: raw[d] - alloc[d], reverse=True)[:N_GENRE - sum(alloc.values())]:
        alloc[d] += 1
    rng = random.Random(SEED)
    chosen = []
    for d in days:
        chosen += rng.sample(by_day[d], alloc[d])
    chosen.sort(key=lambda p: (p["date"], p["source_file"], p["position"]))
    gfields = ["id", "date", "hour", "source_file", "sentence_text", "annotator_1_label"]
    write_csv(os.path.join(GOLD, "genre_sheet_annotator1.csv"), gfields,
              [{"id": p["id"], "date": p["date"], "hour": p["hour"], "source_file": p["source_file"],
                "sentence_text": p["text"], "annotator_1_label": ""} for p in chosen])
    ov = random.Random(SEED).sample(chosen, N_OVERLAP)
    random.Random(SEED + 1).shuffle(ov)
    write_csv(os.path.join(GOLD, "genre_sheet_annotator2_overlap.csv"),
              ["id", "date", "hour", "source_file", "sentence_text", "annotator_2_label"],
              [{"id": p["id"], "date": p["date"], "hour": p["hour"], "source_file": p["source_file"],
                "sentence_text": p["text"], "annotator_2_label": ""} for p in ov])
    print("genre sheet:", len(chosen), "per day", dict(Counter(p["date"] for p in chosen)))
    print("overlap sheet:", len(ov), "per day", dict(Counter(p["date"] for p in ov)))
    exact_dups = len(chosen) - len({" ".join(p["text"].lower().split()) for p in chosen})
    print("genre sheet sentences whose exact text appears more than once in the sheet:", exact_dups)

    # ---- sentence index + embeddings for the val/test pool (used by pair sheet and query tool)
    emb = embed_sentences([p["text"] for p in pool])
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    np.save(os.path.join(GOLD, "valtest_embeddings.npy"), emb.astype(np.float32))
    write_csv(os.path.join(GOLD, "valtest_sentence_index.csv"),
              ["id", "date", "hour", "source_file", "position", "split", "text"], pool)

    # ---- 2. duplicate-pair sheet
    idx_by_day = defaultdict(list)
    for i, p in enumerate(pool):
        idx_by_day[p["date"]].append(i)
    cands = []   # (sim, i, j)
    for d, idx in idx_by_day.items():
        sim = emb[idx] @ emb[idx].T
        for a in range(len(idx)):
            pa = pool[idx[a]]
            if pa["hour"] == "":
                continue
            for b in range(a + 1, len(idx)):
                pb = pool[idx[b]]
                if pb["hour"] == "" or pb["source_file"] == pa["source_file"] or abs(pa["hour"] - pb["hour"]) > MAX_HOUR_GAP:
                    continue
                cands.append((float(sim[a, b]), idx[a], idx[b]))
    print("candidate pairs (same day, different file, hour gap <= %d): %d" % (MAX_HOUR_GAP, len(cands)))
    prng = random.Random(SEED)
    used = set()
    selected = []   # (kind, sim, i, j)

    def take(group, kind, n):
        pools_by_day = defaultdict(list)
        for c in group:
            pools_by_day[pool[c[1]]["date"]].append(c)
        for v in pools_by_day.values():
            prng.shuffle(v)
        got, order = 0, sorted(pools_by_day)
        while got < n and any(pools_by_day.values()):
            for d in order:
                while pools_by_day[d]:
                    c = pools_by_day[d].pop()
                    if c[1] in used or c[2] in used:
                        continue
                    used.update((c[1], c[2]))
                    selected.append((kind, c[0], c[1], c[2]))
                    got += 1
                    break
                if got >= n:
                    break
        return got

    shortfalls = {}
    for lo, hi in BANDS:
        kind = f"{lo:.2f}-{hi:.2f}"
        got = take([c for c in cands if lo <= c[0] < hi], kind, PER_BAND)
        if got < PER_BAND:
            shortfalls[kind] = got
    got = take([c for c in cands if c[0] < NEG_MAX_SIM], f"random<{NEG_MAX_SIM:.2f}", N_NEG)
    if got < N_NEG:
        shortfalls["negatives"] = got
    prng.shuffle(selected)
    sheet, key = [], []
    for n, (kind, s, i, j) in enumerate(selected, 1):
        if prng.random() < 0.5:
            i, j = j, i
        pid = f"P{n:03d}"
        sheet.append({"id": pid, "sentence_a": pool[i]["text"], "sentence_b": pool[j]["text"], "label": ""})
        key.append({"id": pid, "cosine_all_MiniLM_L6_v2": round(s, 4), "band": kind, "date": pool[i]["date"],
                    "split": pool[i]["split"], "sentence_a_id": pool[i]["id"], "sentence_b_id": pool[j]["id"],
                    "hour_a": pool[i]["hour"], "hour_b": pool[j]["hour"]})
    write_csv(os.path.join(GOLD, "duplicate_pairs_sheet.csv"), ["id", "sentence_a", "sentence_b", "label"], sheet)
    write_csv(os.path.join(GOLD, "duplicate_pairs_HIDDEN_KEY.csv"),
              ["id", "cosine_all_MiniLM_L6_v2", "band", "date", "split", "sentence_a_id", "sentence_b_id", "hour_a", "hour_b"], key)
    print("pair sheet:", len(sheet), "| per band:", dict(Counter(k["band"] for k in key)), "| shortfalls:", shortfalls)
    print("pairs per day:", dict(Counter(k["date"] for k in key)))

    # ---- 3. query template (empty)
    write_csv(os.path.join(GOLD, "query_sheet.csv"),
              ["id", "query_text", "date_constraint", "relevant_segment_ids"],
              [{"id": f"Q{n:03d}", "query_text": "", "date_constraint": "", "relevant_segment_ids": ""} for n in range(1, 51)])

    # ---- leakage checks on everything just written
    train_dates = train_days
    problems = []
    for name, col in [("genre_sheet_annotator1.csv", "date"), ("genre_sheet_annotator2_overlap.csv", "date"),
                      ("duplicate_pairs_HIDDEN_KEY.csv", "date"), ("valtest_sentence_index.csv", "date")]:
        for r in csv.DictReader(open(os.path.join(GOLD, name), encoding="utf-8-sig")):
            if r[col] in train_dates or r[col] not in eval_days:
                problems.append((name, r[col]))
    sheet_ids = {r["id"] for r in csv.DictReader(open(os.path.join(GOLD, "genre_sheet_annotator1.csv"), encoding="utf-8-sig"))}
    ov_ids = {r["id"] for r in csv.DictReader(open(os.path.join(GOLD, "genre_sheet_annotator2_overlap.csv"), encoding="utf-8-sig"))}
    print("LEAKAGE CHECK: rows from a train day or a non-val/test day in any gold file:", len(problems))
    print("overlap subset of sheet 1:", ov_ids <= sheet_ids, "| overlap size", len(ov_ids))
    print("genre labels from nlp_pipeline.GENRE_LABELS:", GENRE_LABELS)
    assert not problems


if __name__ == "__main__":
    main()
