"""A4: the novelty gate keeps/drops exactly what the old version did, scales, and batch/live share dedup stats."""
import inspect
import json
import time

import numpy as np
import pytest

import ingest_pipeline
import live_stream_ingest
from nlp_pipeline import mmr_novelty_filter_detailed


def old_mmr_novelty_filter_detailed(sentences, embeddings, existing_embeddings=None, existing_texts=None, threshold=0.85):
    """Frozen copy of the pre-A4 implementation (repeated np.vstack), kept as the reference."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normed = embeddings / norms
    if existing_embeddings is not None and len(existing_embeddings) > 0:
        ex_norms = np.linalg.norm(existing_embeddings, axis=1, keepdims=True)
        ex_norms = np.where(ex_norms == 0, 1, ex_norms)
        pool = list(existing_embeddings / ex_norms)
        if existing_texts and len(existing_texts) == len(existing_embeddings):
            pool_texts = list(existing_texts)
        else:
            pool_texts = [f"Existing segment #{idx+1}" for idx in range(len(existing_embeddings))]
    else:
        pool = []
        pool_texts = []
    novel_indices, rejections = [], []
    for i in range(len(normed)):
        if pool:
            pool_matrix = np.vstack(pool)
            sims = pool_matrix @ normed[i]
            best_idx = int(np.argmax(sims))
            max_sim = float(sims[best_idx])
        else:
            max_sim, best_idx = -1.0, -1
        if max_sim >= threshold:
            matched_str = pool_texts[best_idx] if 0 <= best_idx < len(pool_texts) else ""
            rejections.append({"rejected_text": sentences[i], "matched_text": matched_str,
                               "cosine_score": round(max_sim, 4), "matched_source_idx": best_idx})
        else:
            novel_indices.append(i)
            pool.append(normed[i])
            pool_texts.append(sentences[i])
    return novel_indices, rejections


def _make(n_new, n_existing, dim=64, seed=0, dup_fraction=0.4):
    """Random unit-ish vectors with planted near-duplicates of existing and of earlier new sentences."""
    rng = np.random.default_rng(seed)
    existing = rng.normal(size=(n_existing, dim)).astype(np.float32) if n_existing else None
    new = rng.normal(size=(n_new, dim)).astype(np.float32)
    for i in range(n_new):
        if rng.random() < dup_fraction:
            if existing is not None and rng.random() < 0.5:
                src = existing[rng.integers(len(existing))]
            elif i > 0:
                src = new[rng.integers(i)]
            else:
                continue
            new[i] = src + rng.normal(scale=0.15, size=dim).astype(np.float32)
    sents = [f"new sentence {i}" for i in range(n_new)]
    texts = [f"existing sentence {i}" for i in range(n_existing)] if n_existing else None
    return sents, new, existing, texts


def _same(a, b):
    assert a[0] == b[0]
    assert len(a[1]) == len(b[1])
    for x, y in zip(a[1], b[1]):
        assert x["rejected_text"] == y["rejected_text"]
        assert x["matched_text"] == y["matched_text"]
        assert x["matched_source_idx"] == y["matched_source_idx"]
        assert x["cosine_score"] == pytest.approx(y["cosine_score"], abs=1e-4)


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("n_existing", [0, 25])
def test_gate_matches_old_version(seed, n_existing):
    sents, new, existing, texts = _make(60, n_existing, seed=seed)
    old = old_mmr_novelty_filter_detailed(sents, new, existing, texts, 0.85)
    got = mmr_novelty_filter_detailed(sents, new, existing, texts, 0.85)
    _same(got, old)
    assert 0 < len(got[1]) < len(sents), "fixture should contain both kept and dropped sentences"


def test_gate_matches_old_version_edge_cases():
    sents, new, existing, texts = _make(20, 10, seed=99)
    new[3] = 0.0                                  # zero vector
    existing[2] = existing[1]                     # exact tie in the existing pool: lowest index must win
    new[5] = existing[1]
    for ex_texts in (texts, None):                # without texts the placeholder names are used
        _same(mmr_novelty_filter_detailed(sents, new, existing, ex_texts, 0.85),
              old_mmr_novelty_filter_detailed(sents, new, existing, ex_texts, 0.85))
    got = mmr_novelty_filter_detailed(sents, new, existing, texts, 0.85)
    assert [r for r in got[1] if r["rejected_text"] == "new sentence 5"][0]["matched_source_idx"] == 1
    # empty input and empty existing arrays
    assert mmr_novelty_filter_detailed([], np.zeros((0, 64), dtype=np.float32)) == ([], [])
    _same(mmr_novelty_filter_detailed(sents, new, np.zeros((0, 64), dtype=np.float32), None),
          old_mmr_novelty_filter_detailed(sents, new, None, None))


def test_threshold_is_unchanged():
    import nlp_pipeline
    assert nlp_pipeline.DEFAULT_MMR_THRESHOLD == 0.85


def test_timing_10000_sentences():
    sents, new, _, _ = _make(10_000, 0, dim=384, seed=1, dup_fraction=0.3)
    t0 = time.perf_counter()
    got = mmr_novelty_filter_detailed(sents, new, None, None, 0.85)
    t_new = time.perf_counter() - t0
    # old version on the first 2,000 of the same input, for a like-for-like comparison at a size where it finishes quickly
    t0 = time.perf_counter()
    old_small = old_mmr_novelty_filter_detailed(sents[:2000], new[:2000], None, None, 0.85)
    t_old_2k = time.perf_counter() - t0
    t0 = time.perf_counter()
    new_small = mmr_novelty_filter_detailed(sents[:2000], new[:2000], None, None, 0.85)
    t_new_2k = time.perf_counter() - t0
    _same(new_small, old_small)
    print(f"\n10,000 sentences (new): {t_new:.2f}s | 2,000 sentences: old {t_old_2k:.2f}s, new {t_new_2k:.2f}s | kept {len(got[0])}")
    assert t_new < 60, "10,000 sentences should finish well inside a minute"
    assert t_new_2k < t_old_2k


def test_dedup_stats_schema_matches_legacy_batch_report():
    rej_a = [{"rejected_text": "x", "matched_text": "y", "cosine_score": 0.91, "matched_source_idx": 3}]
    rej_b = [{"rejected_text": "p", "matched_text": "q", "cosine_score": 0.99, "matched_source_idx": 1},
             {"rejected_text": "r", "matched_text": "s", "cosine_score": 0.86, "matched_source_idx": 2}]
    stats = ingest_pipeline.DedupStats()
    stats.add_file("text/a.txt", 10, 9, rej_a)
    stats.add_file("text/b.txt", 20, 18, rej_b)
    # the report layout the batch ingest wrote before A4
    legacy = {
        "totals": {"total_sentences": 30, "novel_sentences": 27, "rejected_sentences": 3, "reduction_pct": 10.0},
        "per_file": [
            {"source_file": "text/a.txt", "total_sentences": 10, "novel_sentences": 9, "rejected_sentences": 1},
            {"source_file": "text/b.txt", "total_sentences": 20, "novel_sentences": 18, "rejected_sentences": 2},
        ],
        "top_rejected_pairs": sorted(rej_a + rej_b, key=lambda x: x["cosine_score"], reverse=True),
    }
    assert stats.report() == legacy


def test_dedup_stats_top_list_is_bounded_and_written(tmp_path):
    stats = ingest_pipeline.DedupStats(top_n=5)
    for k in range(50):
        stats.add_file(f"f{k}", 3, 2, [{"rejected_text": "t", "matched_text": "m", "cosine_score": 0.85 + k / 1000, "matched_source_idx": 0}])
    assert len(stats.top_rejected) == 5 and stats.report()["totals"]["rejected_sentences"] == 50
    path = tmp_path / "r.json"
    stats.write(str(path))
    assert json.loads(path.read_text(encoding="utf-8"))["totals"]["total_sentences"] == 150


def test_live_path_records_dedup_stats():
    src = inspect.getsource(live_stream_ingest)
    assert "DedupStats()" in src and "detailed=True" in src and "dedup_stats.add_file(" in src and "dedup_stats.write(" in src
    assert live_stream_ingest.LIVE_DEDUP_REPORT == "dedup_report_live.json"
