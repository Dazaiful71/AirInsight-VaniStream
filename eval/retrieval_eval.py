"""Retrieval eval (A6): BM25, vector-only, SQL date prefilter + vector, full system, over store_A val/test segments.

Gold: data/gold/query_sheet.csv. Every written query needs relevant_segment_ids (semicolon separated ids from
data/gold/valtest_sentence_index.csv); unfinished sheets exit 3 with a message.
date_constraint format: empty, one day "YYYY-MM-DD", or a range "YYYY-MM-DD:YYYY-MM-DD" (both ends inclusive, val/test days only).

Step 1 - map gold-relevant raw sentences to store segments:
  * exact: a store segment (val/test split) whose text equals the sentence;
  * gate: the sentence was dropped by the novelty gate -> the kept segment that caused its rejection, recomputed as the
    first best-cosine match in the pool the gate had at that moment (all segments of earlier-processed files plus kept
    segments earlier in the same file) provided the cosine reaches the gate threshold;
  * unmapped: neither works; counted and reported, never silently dropped.
Step 2 - rank the store's val/test segments for each query with each system (top RETRIEVAL_DEPTH) and score recall@k,
MRR, nDCG@5 (binary gains) per query, with percentile-bootstrap CIs over queries.
Systems: bm25 (own Okapi BM25, k1=1.5, b=0.75); vector_only (MiniLM cosine over val/test segments, no filters);
date_prefilter_vector (+ the query's date_constraint through vector_store.metadata_prefilter); full_system (genre keyword
prefilter via rag_engine._extract_genre + date prefilter + vector search + rag_engine._filter_by_relevance; no LLM).
Feeds: results/retrieval_eval_*.json -> retrieval table (see eval/README.md).
"""
import math
import os
import re
import sqlite3
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402

NAME = "retrieval_eval"
SYSTEMS = ("bm25", "vector_only", "date_prefilter_vector", "full_system")
# Ablation switches (all on = the full system). They act on the full_system ranking only:
#   prefilter off          -> no genre/date SQL prefilter (search all val/test segments)
#   relevance_filter off   -> rag_engine._filter_by_relevance is skipped
#   dedup off              -> the store built WITHOUT the novelty gate (store_A_nodedup, build_store_A.py --no-gate) is used
DEFAULT_FLAGS = {"prefilter": True, "relevance_filter": True, "dedup": True}


def flags_tag(flags: dict) -> str:
    off = [k for k in ("prefilter", "relevance_filter", "dedup") if not flags.get(k, True)]
    return "" if not off else "_".join("no" + k.replace("_", "") for k in off)


def result_name(flags: dict) -> str:
    tag = flags_tag(flags)
    return NAME if not tag else f"{NAME}_ablation_{tag}"


def default_paths(flags: dict = None) -> dict:
    store = cfg.STORE_DIR if (flags or DEFAULT_FLAGS).get("dedup", True) else cfg.STORE_NODEDUP_DIR
    return {"gold": cfg.GOLD_QUERIES, "sentence_index": cfg.GOLD_SENTENCE_INDEX,
            "store_db": os.path.join(store, "news_store.db"), "store_index": os.path.join(store, "faiss_index.bin"),
            "sample_dir": cfg.SAMPLE_DIR, "sample_config": cfg.SAMPLE_CONFIG,
            "build_report": os.path.join(store, "build_report.json")}


def gold_status(paths=None):
    p = paths or default_paths()
    rel = common.rel(p["gold"])
    if not os.path.isfile(p["gold"]):
        return common.GoldStatus(False, f"query gold is missing: {rel}")
    rows = common.read_csv(p["gold"])
    written = [r for r in rows if (r.get("query_text") or "").strip()]
    if not written:
        return common.GoldStatus(False, f"no queries written yet in {rel} (0 of {len(rows)} rows have query_text)")
    unjudged = [r["id"] for r in written if not (r.get("relevant_segment_ids") or "").strip()]
    if unjudged:
        return common.GoldStatus(False, f"{len(unjudged)} written queries have no relevant_segment_ids yet "
                                        f"(e.g. {unjudged[:3]}) in {rel}")
    return common.GoldStatus(True, f"{len(written)} judged queries ({rel})", written)


# ---------------------------------------------------------------- pure metrics
def recall_at_k(ranked, relevant, k):
    return len(set(ranked[:k]) & set(relevant)) / len(set(relevant))


def reciprocal_rank(ranked, relevant):
    rel = set(relevant)
    for i, d in enumerate(ranked, 1):
        if d in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked, relevant, k):
    rel = set(relevant)
    dcg = sum(1.0 / math.log2(i + 1) for i, d in enumerate(ranked[:k], 1) if d in rel)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(rel), k) + 1))
    return dcg / idcg if idcg else 0.0


def query_metrics(ranked, relevant) -> dict:
    m = {f"recall@{k}": recall_at_k(ranked, relevant, k) for k in cfg.RETRIEVAL_KS}
    m["mrr"] = reciprocal_rank(ranked, relevant)
    m[f"ndcg@{cfg.NDCG_K}"] = ndcg_at_k(ranked, relevant, cfg.NDCG_K)
    return m


def summarise(per_query: dict, resamples=cfg.BOOTSTRAP_RESAMPLES, seed=cfg.SEED) -> dict:
    """Mean of each metric over queries with a percentile-bootstrap CI over queries. per_query: qid -> metrics dict."""
    qids = sorted(per_query)
    names = list(per_query[qids[0]]) if qids else []
    idx = common.bootstrap_indices(len(qids), resamples, seed) if qids else None
    out = {"n_queries": len(qids), "bootstrap": common.bootstrap_meta(len(qids), resamples, seed)}
    for n in names:
        v = np.array([per_query[q][n] for q in qids])
        out[n] = {"mean": float(v.mean()), "ci95": common.percentile_ci(v[idx].mean(axis=1))}
    return out


class BM25:
    """Okapi BM25 over a fixed document list (ids parallel to docs). Documents with no query term score 0 and are not returned."""

    def __init__(self, ids, docs, k1=1.5, b=0.75):
        self.ids, self.k1, self.b = list(ids), k1, b
        self.tf = [Counter(self.tok(d)) for d in docs]
        self.len = np.array([sum(t.values()) for t in self.tf], dtype=float)
        self.avg = self.len.mean() if len(docs) else 0.0
        df = Counter(w for t in self.tf for w in t)
        n = len(docs)
        self.idf = {w: math.log((n - c + 0.5) / (c + 0.5) + 1.0) for w, c in df.items()}

    @staticmethod
    def tok(text):
        return re.findall(r"[a-z0-9]+", text.lower())

    def rank(self, query, depth):
        q = self.tok(query)
        scores = np.zeros(len(self.ids))
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in q:
                if w in tf:
                    f = tf[w]
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            scores[i] = s
        order = sorted((i for i in range(len(self.ids)) if scores[i] > 0), key=lambda i: (-scores[i], self.ids[i]))
        return [self.ids[i] for i in order[:depth]]


# ---------------------------------------------------------------- store + mapping
def load_store(paths):
    for k in ("store_db", "store_index"):
        if not os.path.isfile(paths[k]):
            raise common.PrerequisiteMissing(f"store file not found: {common.rel(paths[k])} (run the ingest stage first)")
    import vector_store
    con = sqlite3.connect(paths["store_db"])
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT faiss_id, text, genre, date, hour, split, source_file FROM segments ORDER BY faiss_id")]
    con.close()
    emb = vector_store.get_all_embeddings(paths["store_index"])
    if emb is None or len(emb) != len(rows):
        raise common.PrerequisiteMissing("store index and database do not have the same number of segments")
    emb = emb / np.where(np.linalg.norm(emb, axis=1, keepdims=True) == 0, 1, np.linalg.norm(emb, axis=1, keepdims=True))
    return rows, emb


def file_order_key(source_file: str, date: str):
    """Same processing order as ingest_pipeline with sort_rows=True: (date, hour unknown last, hour, file)."""
    import ingest_pipeline
    hour = ingest_pipeline._extract_hour(os.path.basename(source_file))
    return (date, hour is None, hour or 0, source_file)


def map_relevant(sent_ids, sent_index, store_rows, store_emb, sample_dir, embed_fn, threshold):
    """Map gold raw-sentence ids to store segments. Returns {sentence_id: {"status", "faiss_id", ...}}."""
    from nlp_pipeline import segment_sentences
    by_text = {}
    for r in store_rows:
        if r["split"] in cfg.GOLD_SPLITS:
            by_text.setdefault(r["text"], r["faiss_id"])
    file_keys = {}
    for r in store_rows:
        file_keys[r["source_file"]] = file_order_key(r["source_file"], r["date"])
    out = {}
    for sid in sent_ids:
        row = sent_index.get(sid)
        if row is None:
            out[sid] = {"status": "unmapped", "reason": "id not in the gold sentence index"}
            continue
        if row["text"] in by_text:
            out[sid] = {"status": "exact", "faiss_id": by_text[row["text"]]}
            continue
        src = f"text/{row['date']}/{os.path.splitext(row['source_file'])[0]}.txt"
        tpath = os.path.join(sample_dir, src)
        if not os.path.isfile(tpath):
            out[sid] = {"status": "unmapped", "reason": f"transcript not found: {src}"}
            continue
        sents = segment_sentences(open(tpath, encoding="utf-8").read())
        if row["text"] not in sents:
            out[sid] = {"status": "unmapped", "reason": "sentence not found in its transcript"}
            continue
        j = sents.index(row["text"])
        my_key = file_order_key(src, row["date"])
        pool = []
        for r in store_rows:
            if r["source_file"] == src:
                if r["text"] in sents and sents.index(r["text"]) < j:
                    pool.append(r)
            elif file_keys[r["source_file"]] < my_key:
                pool.append(r)
        if not pool:
            out[sid] = {"status": "unmapped", "reason": "gate pool was empty at that point"}
            continue
        q = np.asarray(embed_fn([row["text"]]), dtype=np.float32)[0]
        q = q / (np.linalg.norm(q) or 1.0)
        pos = {r["faiss_id"]: i for i, r in enumerate(store_rows)}
        sims = np.array([store_emb[pos[r["faiss_id"]]] @ q for r in pool])
        best = int(np.argmax(sims))
        if sims[best] >= threshold - 1e-4:
            out[sid] = {"status": "gate", "faiss_id": pool[best]["faiss_id"], "cosine": float(sims[best])}
        else:
            out[sid] = {"status": "unmapped", "reason": f"best pool cosine {float(sims[best]):.3f} is below the gate threshold"}
    return out


# ---------------------------------------------------------------- systems
def parse_date_constraint(text: str):
    t = (text or "").strip()
    if not t:
        return None, None
    a, _, b = t.partition(":")
    return a.strip(), (b.strip() or a.strip())


class Systems:
    def __init__(self, paths, store_rows, store_emb, embed_fn, flags=None):
        import vector_store
        self.flags = {**DEFAULT_FLAGS, **(flags or {})}
        self.vs = vector_store
        self.vs.resolve_audio_path = lambda *a, **k: ("", False)   # never look at output/ during evaluation
        self.paths, self.rows, self.emb, self.embed_fn = paths, store_rows, store_emb, embed_fn
        self.pool_ids = [r["faiss_id"] for r in store_rows if r["split"] in cfg.GOLD_SPLITS]
        self.pool_set = set(self.pool_ids)
        pos = {r["faiss_id"]: i for i, r in enumerate(store_rows)}
        self.pool_idx = np.array([pos[i] for i in self.pool_ids])
        self.bm25 = BM25(self.pool_ids, [store_rows[i]["text"] for i in self.pool_idx])

    def _qvec(self, query):
        q = np.asarray(self.embed_fn([query]), dtype=np.float32)[0]
        return q / (np.linalg.norm(q) or 1.0)

    def _vector(self, query, ids):
        if not ids:
            return []
        pos = {r["faiss_id"]: i for i, r in enumerate(self.rows)}
        idx = np.array([pos[i] for i in ids])
        sims = self.emb[idx] @ self._qvec(query)
        order = sorted(range(len(ids)), key=lambda i: (-sims[i], ids[i]))
        return [ids[i] for i in order[:cfg.RETRIEVAL_DEPTH]]

    def rank(self, system, query, date_from, date_to):
        if system == "bm25":
            return self.bm25.rank(query, cfg.RETRIEVAL_DEPTH)
        if system == "vector_only":
            return self._vector(query, self.pool_ids)
        if system == "date_prefilter_vector":
            ids = [i for i in self.vs.metadata_prefilter(date_from, date_to, None, self.paths["store_db"]) if i in self.pool_set]
            return self._vector(query, sorted(ids))
        if system == "full_system":
            import rag_engine
            if self.flags["prefilter"]:
                genre = rag_engine._extract_genre(query)
                ids = sorted(i for i in self.vs.metadata_prefilter(date_from, date_to, genre, self.paths["store_db"]) if i in self.pool_set)
            else:
                genre, ids = None, sorted(self.pool_ids)       # no SQL prefilter: every val/test segment is a candidate
            if not ids:
                return []
            raw = self.vs.semantic_search(self._qvec(query), ids, top_k=cfg.RETRIEVAL_DEPTH,
                                          index_path=self.paths["store_index"], db_path=self.paths["store_db"])
            kept = rag_engine._filter_by_relevance(raw, query, genre) if self.flags["relevance_filter"] else raw
            return [s["faiss_id"] for s in kept]
        raise ValueError(system)


# ---------------------------------------------------------------- driver
def compute(paths, embed_fn=None, flags=None):
    import json
    flags = {**DEFAULT_FLAGS, **(flags or {})}
    if embed_fn is None:
        from nlp_pipeline import embed_sentences as embed_fn
    queries = gold_status(paths).rows
    sent_index = {r["id"]: r for r in common.read_csv(paths["sentence_index"])}
    rows, emb = load_store(paths)
    threshold = 0.85
    if os.path.isfile(paths.get("build_report", "")):
        threshold = json.load(open(paths["build_report"], encoding="utf-8")).get("threshold", threshold)
    split_of = {}
    plan = json.load(open(paths["sample_config"], encoding="utf-8"))["pilot_plan_s4"]["option_A_about_10_days"]["split"]
    for s in plan:
        for d in plan[s]["days"]:
            split_of[d] = s

    parsed = {}
    for q in queries:
        ids = [x.strip() for x in re.split(r"[;,]", q["relevant_segment_ids"]) if x.strip()]
        parsed[q["id"]] = ids
    all_ids = sorted({i for ids in parsed.values() for i in ids})
    mapping = map_relevant(all_ids, sent_index, rows, emb, paths["sample_dir"], embed_fn, threshold)
    counts = Counter(m["status"] for m in mapping.values())

    systems = Systems(paths, rows, emb, embed_fn, flags)
    per_query, skipped = {s: {} for s in SYSTEMS}, []
    detail = {}
    for q in queries:
        qid = q["id"]
        d_from, d_to = parse_date_constraint(q.get("date_constraint", ""))
        bad_day = [d for d in (d_from, d_to) if d and split_of.get(d) not in cfg.GOLD_SPLITS]
        if bad_day:
            skipped.append({"id": qid, "reason": f"date_constraint outside val/test days: {bad_day}"})
            continue
        unknown = [i for i in parsed[qid] if i not in sent_index]
        rel = sorted({mapping[i]["faiss_id"] for i in parsed[qid] if "faiss_id" in mapping.get(i, {})})
        if not rel:
            skipped.append({"id": qid, "reason": "no relevant sentence could be mapped to a store segment",
                            "unknown_ids": unknown})
            continue
        detail[qid] = {"query_text": q["query_text"], "date_constraint": q.get("date_constraint", ""),
                       "n_relevant_ids_given": len(parsed[qid]), "n_relevant_store_segments": len(rel),
                       "mapping": {i: mapping[i]["status"] for i in parsed[qid]}, "systems": {}}
        for s in SYSTEMS:
            ranked = systems.rank(s, q["query_text"], d_from, d_to)
            m = query_metrics(ranked, rel)
            per_query[s][qid] = m
            detail[qid]["systems"][s] = {"metrics": m, "returned": len(ranked), "top5_faiss_ids": ranked[:5]}
    results = {
        "mapping_of_gold_relevant_sentences": {"distinct_sentences": len(all_ids), "exact_text_match": counts["exact"],
                                               "mapped_via_gate_rejection": counts["gate"], "unmapped": counts["unmapped"],
                                               "gate_threshold_used": threshold,
                                               "unmapped_reasons": {i: m["reason"] for i, m in mapping.items() if m["status"] == "unmapped"}},
        "queries": {"written": len(queries), "evaluated": len(detail), "skipped": skipped},
        "ablation_flags": {**flags, "meaning": "flags act on full_system only; dedup=false uses the store built without the novelty gate",
                           "store_used": common.rel(os.path.dirname(paths["store_db"]))},
        "settings": {"depth": cfg.RETRIEVAL_DEPTH, "ks": list(cfg.RETRIEVAL_KS), "ndcg_k": cfg.NDCG_K,
                     "segment_pool": "store_A segments with split val or test", "systems": list(SYSTEMS)},
        "per_system": {s: summarise(per_query[s]) for s in SYSTEMS} if detail else "no evaluable queries",
        "per_query": detail,
    }
    return results, None


def run(paths=None, results_dir=None, embed_fn=None, flags=None):
    flags = {**DEFAULT_FLAGS, **(flags or {})}
    p = paths or default_paths(flags)
    return common.save_or_report(result_name(flags), gold_status(p), lambda: compute(p, embed_fn, flags),
                                 [p["gold"], p["sentence_index"], p["store_db"], p["store_index"]], results_dir)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Retrieval eval; the --no-* switches are ablations of the full system.")
    ap.add_argument("--no-prefilter", action="store_true", help="skip the genre/date SQL prefilter")
    ap.add_argument("--no-relevance-filter", action="store_true", help="skip rag_engine._filter_by_relevance")
    ap.add_argument("--no-dedup", action="store_true", help="use the store built without the novelty gate (store_A_nodedup)")
    a = ap.parse_args()
    flags = {"prefilter": not a.no_prefilter, "relevance_filter": not a.no_relevance_filter, "dedup": not a.no_dedup}
    return run(flags=flags)[0]


if __name__ == "__main__":
    raise SystemExit(main())
