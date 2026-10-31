"""S7 part 1: build a NEW store from option A under store_A/ (never the project's default store files).

  .venv_gpu/Scripts/python.exe build_store_A.py [--classifier fast|zero-shot|finetuned] [--reindex]

Resumable: a rerun skips transcripts already listed in store_A/processed_files.txt (use --reindex to start over).
Writes store_A/news_store.db, store_A/faiss_index.bin, store_A/dedup_report.json, store_A/build_report.json.
Rows are processed in (date, hour, file) order; the gate is order dependent and runs across ALL splits.
Threshold is the project default 0.85 and is not a flag here on purpose.
"""
import argparse
import csv
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict

import ingest_pipeline

STORE = "store_A"
SAMPLE = os.path.join("data", "sample_A")
THRESHOLD = 0.85
GATE_OFF_THRESHOLD = 1.01   # cosine cannot reach this, so every sentence is kept (ablation only)


def build_report(store_dir: str, metadata_csv: str, seconds: float, classifier: str, threshold: float = THRESHOLD) -> dict:
    db = sqlite3.connect(os.path.join(store_dir, "news_store.db"))
    seg_by_split = dict(db.execute("SELECT COALESCE(split, 'NULL'), COUNT(*) FROM segments GROUP BY split").fetchall())
    null_by_split = dict(db.execute(
        "SELECT COALESCE(split, 'NULL'), COUNT(*) FROM segments WHERE hour IS NULL GROUP BY split").fetchall())
    flags = dict(db.execute("SELECT COALESCE(hour_flag, ''), COUNT(*) FROM segments WHERE hour IS NULL GROUP BY hour_flag").fetchall())
    hours = dict(db.execute("SELECT hour, COUNT(*) FROM segments WHERE hour IS NOT NULL GROUP BY hour ORDER BY hour").fetchall())
    bad_hours = db.execute("SELECT COUNT(*) FROM segments WHERE hour IS NOT NULL AND (hour < 0 OR hour > 23)").fetchone()[0]
    days_per_split = {k: sorted(v) for k, v in _group(db.execute("SELECT split, date FROM segments GROUP BY split, date").fetchall()).items()}
    genres = dict(db.execute("SELECT genre, COUNT(*) FROM segments GROUP BY genre ORDER BY 2 DESC").fetchall())
    total_segments = db.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
    db.close()

    split_of = {}
    with open(metadata_csv, newline="", encoding="utf-8") as h:
        for r in csv.DictReader(h):
            split_of[r["transcript_file"].replace("\\", "/")] = r.get("split") or "NULL"
    dd = json.load(open(os.path.join(store_dir, "dedup_report.json"), encoding="utf-8"))
    raw, novel = Counter(), Counter()
    for f in dd["per_file"]:
        sp = split_of.get(f["source_file"], "NULL")
        raw[sp] += f["total_sentences"]
        novel[sp] += f["novel_sentences"]
    return {
        "store_dir": store_dir,
        "threshold": threshold,
        "classifier_backend": classifier,
        "seconds": round(seconds, 1),
        "segments_in_store": total_segments,
        "sentences_before_gate": dict(raw) | {"all": sum(raw.values())},
        "sentences_after_gate": dict(novel) | {"all": sum(novel.values())},
        "segments_by_split_in_db": seg_by_split,
        "null_hour_segments_by_split": null_by_split,
        "null_hour_total": sum(null_by_split.values()),
        "null_hour_flags": flags,
        "segments_with_hour_outside_0_23": bad_hours,
        "segments_per_hour": hours,
        "days_per_split": days_per_split,
        "genre_counts_SILVER": genres,
        "dedup_totals": dd["totals"],
    }


def _group(pairs):
    out = defaultdict(list)
    for k, v in pairs:
        out[k].append(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classifier", choices=["zero-shot", "fast", "finetuned"], default="zero-shot")
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--no-gate", action="store_true",
                    help="ablation store: novelty gate OFF (threshold 1.01, nothing is rejected). Use with --store-dir store_A_nodedup")
    ap.add_argument("--store-dir", default=STORE)
    a = ap.parse_args()
    if os.path.basename(os.path.normpath(a.store_dir)) in ("", ".", "output"):
        raise SystemExit("store dir must be a new folder such as store_A")
    if a.no_gate and os.path.basename(os.path.normpath(a.store_dir)) == STORE:
        raise SystemExit("--no-gate must write to its own folder (--store-dir store_A_nodedup), never to store_A")
    os.makedirs(a.store_dir, exist_ok=True)
    meta = os.path.join(SAMPLE, "metadata.csv")
    t0 = time.perf_counter()
    summary = ingest_pipeline.run(
        reindex=a.reindex,
        mmr_threshold=GATE_OFF_THRESHOLD if a.no_gate else THRESHOLD,
        metadata_csv=meta,
        classifier=a.classifier,
        text_root=SAMPLE,
        index_path=os.path.join(a.store_dir, "faiss_index.bin"),
        db_path=os.path.join(a.store_dir, "news_store.db"),
        processed_file=os.path.join(a.store_dir, "processed_files.txt"),
        report_path=os.path.join(a.store_dir, "dedup_report.json"),
        sort_rows=True,
    )
    seconds = time.perf_counter() - t0
    print("ingest summary (this run):", summary)
    rep = build_report(a.store_dir, meta, seconds, a.classifier, GATE_OFF_THRESHOLD if a.no_gate else THRESHOLD)
    rep["note_seconds"] = "wall time of THIS invocation only; a resumed run counts only the remaining files"
    with open(os.path.join(a.store_dir, "build_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("segments_per_hour",)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
