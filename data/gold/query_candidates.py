"""Show candidate sentences from the val/test days for judging one query. Does not decide relevance.

Candidates are the union of two rankers (embedding cosine with all-MiniLM-L6-v2, and TF-IDF word overlap), so the
judged pool is not only what the embedding model likes. Judge every candidate yourself, then write the relevant
segment ids (semicolon separated) into data/gold/query_sheet.csv, column relevant_segment_ids.

  .venv_gpu/Scripts/python.exe data/gold/query_candidates.py "your query" [--date 2026-08-16] [--k 15]
"""
import argparse
import csv
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
GOLD = os.path.join(ROOT, "data", "gold")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--date", default="", help="only sentences from this day (YYYY-MM-DD)")
    ap.add_argument("--k", type=int, default=15, help="top-k from EACH ranker")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(os.path.join(GOLD, "valtest_sentence_index.csv"), encoding="utf-8-sig")))
    emb = np.load(os.path.join(GOLD, "valtest_embeddings.npy"))
    keep = [i for i, r in enumerate(rows) if not a.date or r["date"] == a.date]
    if not keep:
        print("no sentences for that date; val/test days are:", sorted({r["date"] for r in rows}))
        return 1

    from nlp_pipeline import embed_sentences
    from sklearn.feature_extraction.text import TfidfVectorizer
    q = embed_sentences([a.query])[0]
    q = q / np.linalg.norm(q)
    emb_scores = emb[keep] @ q
    tf = TfidfVectorizer(lowercase=True, stop_words="english").fit([rows[i]["text"] for i in keep])
    tf_scores = (tf.transform([rows[i]["text"] for i in keep]) @ tf.transform([a.query]).T).toarray().ravel()

    top_e = list(np.argsort(-emb_scores)[:a.k])
    top_t = [j for j in np.argsort(-tf_scores)[:a.k] if tf_scores[j] > 0]
    order = list(dict.fromkeys(top_e + top_t))
    print(f"query: {a.query!r} | date: {a.date or 'all val/test days'} | {len(order)} candidates "
          f"(top {a.k} embedding + top {a.k} TF-IDF, merged)\n")
    for j in order:
        r = rows[keep[j]]
        print(f"{r['id']}  [{r['date']} h={r['hour'] or '-'}]\n    {r['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
