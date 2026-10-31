"""S5 part 4: compare the two files of every duplicate-slot pair in the downloaded sample.

A duplicate-slot pair = two different audio files with the same date and the same parsed HHMM
(first standalone 4-digit group in the filename). Analysis only: no network, no downloads.

Usage (from the project folder):
  .venv_gpu/Scripts/python.exe eval/duplicate_pairs_check.py
Output: results/duplicate_pairs_check.json
"""
import argparse
import csv
import itertools
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from air_bulletins_scraper import parse_hour_from_url  # noqa: E402

# Labels are descriptive, the thresholds are our own choices and are saved in the output.
NEAR_IDENTICAL_JACCARD = 0.8
DIFFERENT_JACCARD = 0.3
DURATION_TOLERANCE_S = 2.0


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def ngrams(ws: list[str], n: int = 5) -> set:
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def similarity(a: str, b: str) -> dict:
    wa, wb = words(a), words(b)
    ga, gb = ngrams(wa), ngrams(wb)
    inter = len(ga & gb)
    union = len(ga | gb)
    return {
        "words_a": len(wa),
        "words_b": len(wb),
        "jaccard_word_5grams": round(inter / union, 4) if union else None,
        "containment_in_shorter": round(inter / min(len(ga), len(gb)), 4) if ga and gb else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.path.join("data", "sample_A"))
    ap.add_argument("--out", default=os.path.join("results", "duplicate_pairs_check.json"))
    a = ap.parse_args()

    with open(os.path.join(a.base, "metadata.csv"), newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    slots: dict = {}
    for r in rows:
        hhmm, _hour, _flag = parse_hour_from_url(r["audio_url"])
        if hhmm is not None:
            slots.setdefault((r["date"], hhmm), []).append(r)

    pairs = []
    for (date, hhmm), items in sorted(slots.items()):
        if len(items) < 2:
            continue
        for x, y in itertools.combinations(items, 2):
            def transcript(r):
                path = os.path.join(a.base, r["transcript_file"]) if r["transcript_file"] else ""
                if path and os.path.isfile(path):
                    with open(path, encoding="utf-8") as h:
                        return h.read()
                return ""
            tx, ty = transcript(x), transcript(y)
            dx = float(x["duration_s"]) if x["duration_s"] else None
            dy = float(y["duration_s"]) if y["duration_s"] else None
            sim = similarity(tx, ty) if tx and ty else {}
            same_sha = x["sha256"] == y["sha256"]
            jac = sim.get("jaccard_word_5grams")
            dur_close = dx is not None and dy is not None and abs(dx - dy) <= DURATION_TOLERANCE_S
            if same_sha:
                label = "byte-identical"
            elif jac is None:
                label = "not classified (a transcript is missing)"
            elif jac >= NEAR_IDENTICAL_JACCARD and dur_close:
                label = "near-identical (same text, same length)"
            elif jac >= NEAR_IDENTICAL_JACCARD:
                label = "near-identical text, different length"
            elif jac < DIFFERENT_JACCARD:
                label = "different text"
            else:
                label = "intermediate (partly shared text)"
            pairs.append({
                "date": date,
                "hhmm": hhmm,
                "file_a": os.path.basename(x["audio_url"]),
                "file_b": os.path.basename(y["audio_url"]),
                "title_a": x["title"],
                "title_b": y["title"],
                "split": x.get("split", ""),
                "duration_s_a": dx,
                "duration_s_b": dy,
                "duration_diff_s": None if dx is None or dy is None else round(abs(dx - dy), 2),
                "bytes_a": os.path.getsize(os.path.join(a.base, x["audio_file"])),
                "bytes_b": os.path.getsize(os.path.join(a.base, y["audio_file"])),
                "sha256_equal": same_sha,
                "transcript_chars_a": len(tx),
                "transcript_chars_b": len(ty),
                **sim,
                "label": label,
                "start_a": tx[:140].replace("\n", " "),
                "start_b": ty[:140].replace("\n", " "),
            })

    summary = {}
    for p in pairs:
        summary[p["label"]] = summary.get(p["label"], 0) + 1
    out = {
        "definition": "two different audio files with the same date and the same parsed HHMM",
        "base": a.base,
        "n_pairs": len(pairs),
        "thresholds_our_choice": {
            "near_identical_if_jaccard_word_5grams_at_least": NEAR_IDENTICAL_JACCARD,
            "different_if_jaccard_below": DIFFERENT_JACCARD,
            "same_length_if_duration_difference_at_most_s": DURATION_TOLERANCE_S,
        },
        "label_counts": summary,
        "pairs": pairs,
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2, ensure_ascii=False)
    print(f"{len(pairs)} pairs -> {a.out}")
    print(json.dumps(summary, indent=1))
    for p in pairs:
        print(f"{p['date']} {p['hhmm']:04d} {p['file_a']} | {p['file_b']} | sha_equal={p['sha256_equal']} "
              f"dur {p['duration_s_a']}/{p['duration_s_b']} jaccard={p.get('jaccard_word_5grams')} -> {p['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
