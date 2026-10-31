"""Label every segment of a store with the BART zero-shot backend (resumable). Never modifies the store.

  python cluster/bart_label_store.py [--smoke] [--store-dir store_A] [--out-dir data/silver_bart]

Reads <store-dir>/news_store.db read-only and appends rows (faiss_id, genre, confidence) to <out-dir>/labels.csv after every
batch; ids already in labels.csv are skipped on rerun. --smoke labels only the first 200 segments into <out-dir>_smoke.
The labels are SILVER (zero-shot model output), not gold. Uses the GPU when torch sees one (nlp_pipeline picks cuda:0).
"""
import argparse
import csv
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--store-dir", default="store_A")
    ap.add_argument("--out-dir", default=os.path.join("data", "silver_bart"))
    ap.add_argument("--batch", type=int, default=64)
    a = ap.parse_args()
    db = os.path.join(ROOT, a.store_dir, "news_store.db")
    if not os.path.isfile(db):
        print(f"[bart_label_store] store not found: {db}")
        return 2
    out_dir = os.path.join(ROOT, a.out_dir + ("_smoke" if a.smoke else ""))
    os.makedirs(out_dir, exist_ok=True)
    labels_csv = os.path.join(out_dir, "labels.csv")
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    rows = con.execute("SELECT faiss_id, text FROM segments ORDER BY faiss_id").fetchall()
    con.close()
    if a.smoke:
        rows = rows[:200]
    done = set()
    if os.path.isfile(labels_csv):
        with open(labels_csv, newline="", encoding="utf-8") as f:
            done = {int(r["faiss_id"]) for r in csv.DictReader(f)}
    todo = [r for r in rows if r[0] not in done]
    print(f"[bart_label_store] {len(rows)} segments, {len(done)} already labelled, {len(todo)} to do")
    import nlp_pipeline
    new_file = not os.path.isfile(labels_csv)
    t0 = time.time()
    with open(labels_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["faiss_id", "genre", "confidence"])
        for i in range(0, len(todo), a.batch):
            chunk = todo[i:i + a.batch]
            preds = nlp_pipeline.classify_genres_batch([t for _, t in chunk], fast=False)
            for (fid, _), (g, c) in zip(chunk, preds):
                w.writerow([fid, g, round(c, 6)])
            f.flush()
            print(f"[bart_label_store] {min(i + a.batch, len(todo))}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    with open(os.path.join(out_dir, "DONE.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": len(rows), "model": nlp_pipeline.DEFAULT_CLASSIFIER_MODEL, "label_origin": "SILVER",
                   "smoke": a.smoke}, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
