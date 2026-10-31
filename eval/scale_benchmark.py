"""Scale benchmark on SYNTHETIC data: N segments (default 10,000), retrieval latency and novelty-gate time. Resumable.

Random unit vectors and random metadata are used on purpose: latency and memory of a flat FAISS index plus an SQLite
prefilter do not depend on the text, and the real store has fewer than 10,000 segments. The numbers say nothing about
retrieval quality.
  python eval/scale_benchmark.py [--n 10000] [--queries 200] [--smoke] [--force]
Writes results/scale_benchmark_n<N>_*.json via the shared writer; skips if that result already exists (use --force).
This job needs no GPU.
"""
import argparse
import glob
import os
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402


def peak_rss_mb():
    try:
        import resource
        if sys.platform != "win32":
            return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)   # Linux reports KiB
    except ImportError:
        pass
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e6, 1)
    except ImportError:
        return None


def run_benchmark(n: int, n_queries: int, seed: int = cfg.SEED, workdir: str = None) -> dict:
    import vector_store
    from nlp_pipeline import mmr_novelty_filter_detailed
    rng = np.random.default_rng(seed)
    dim = vector_store.EMBEDDING_DIM
    vecs = rng.normal(size=(n, dim)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    genres = ["Politics", "Economy", "Sports", "International", "Other"]
    workdir = workdir or tempfile.mkdtemp(prefix="scale_bench_")
    os.makedirs(workdir, exist_ok=True)
    ip, dp = os.path.join(workdir, "i.bin"), os.path.join(workdir, "s.db")
    vector_store.resolve_audio_path = lambda *a, **k: ("", False)
    t0 = time.perf_counter()
    for start in range(0, n, 500):                         # batches, like ingest adds per transcript
        seg = [{"text": f"synthetic {i}", "genre": genres[i % 5], "genre_confidence": 0.5, "embedding": vecs[i]}
               for i in range(start, min(n, start + 500))]
        day = f"2026-08-{1 + (start // 500) % 28:02d}"
        vector_store.add_segments(seg, day, (start // 500) % 24, "text/synthetic.txt", ip, dp)
    build_s = time.perf_counter() - t0
    qs = rng.normal(size=(n_queries, dim)).astype(np.float32)
    lat = {"unfiltered": [], "date_genre_prefilter": []}
    for q in qs:
        t = time.perf_counter()
        vector_store.semantic_search(q, None, top_k=20, index_path=ip, db_path=dp)
        lat["unfiltered"].append(time.perf_counter() - t)
        t = time.perf_counter()
        ids = vector_store.metadata_prefilter("2026-08-05", "2026-08-12", "Sports", dp)
        vector_store.semantic_search(q, ids, top_k=20, index_path=ip, db_path=dp)
        lat["date_genre_prefilter"].append(time.perf_counter() - t)
    t = time.perf_counter()
    mmr_novelty_filter_detailed([f"s{i}" for i in range(n)], vecs, threshold=0.85)
    gate_s = time.perf_counter() - t

    def pct(v, p):
        return float(np.percentile(np.asarray(v) * 1000, p))   # milliseconds

    return {"n_segments": n, "n_queries": n_queries, "data": "SYNTHETIC random unit vectors (not real text)",
            "index_build_seconds": build_s, "novelty_gate_seconds_for_n_sentences": gate_s,
            "query_latency_ms": {k: {"p50": pct(v, 50), "p95": pct(v, 95), "max": float(np.max(v) * 1000)} for k, v in lat.items()},
            "peak_rss_mb": peak_rss_mb(),
            "machine_note": "timings depend on the machine this ran on; the host is recorded with the result"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10_000)
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--smoke", action="store_true", help="1,000 segments, 20 queries, result name scale_benchmark_smoke")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--results-dir", default=cfg.RESULTS_DIR)
    a = ap.parse_args()
    n, nq = (1000, 20) if a.smoke else (a.n, a.queries)
    name = "scale_benchmark_smoke" if a.smoke else f"scale_benchmark_n{n}"
    if not a.force and glob.glob(os.path.join(a.results_dir, name + "_*.json")):
        print(f"[scale_benchmark] result for {name} already exists - skipping (use --force)")
        return 0
    res = run_benchmark(n, nq)
    import platform
    common.write_result(name, res, [], results_dir=a.results_dir, extra={"host": platform.node(), "platform": platform.platform()})
    print(f"[scale_benchmark] done: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
