"""A1: filtered FAISS search must return exactly the top-k of the candidate set."""
import faiss
import numpy as np
import pytest

import vector_store

N, DIM = 1000, vector_store.EMBEDDING_DIM


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("store")
    index_path, db_path = str(tmp / "index.bin"), str(tmp / "store.db")
    rng = np.random.default_rng(0)
    vecs = rng.normal(size=(N, DIM)).astype(np.float32)
    faiss.normalize_L2(vecs)
    segs = [{"text": f"sentence {i}", "genre": "Other", "genre_confidence": 0.5, "embedding": vecs[i]} for i in range(N)]
    vector_store.add_segments(segs, "2026-01-01", 5, "text/x.txt", index_path, db_path)
    return index_path, db_path, vecs


@pytest.fixture(autouse=True)
def _no_output_dir(monkeypatch):
    # resolve_audio_path would read output/metadata.csv; keep the tests away from output/
    monkeypatch.setattr(vector_store, "resolve_audio_path", lambda *a, **k: ("", False))


def _query(seed):
    q = np.random.default_rng(seed).normal(size=DIM).astype(np.float32)
    return q / np.linalg.norm(q)


def _expected(vecs, q, cand, k):
    cand = np.array(sorted(set(cand)))
    scores = vecs[cand] @ q
    order = np.argsort(-scores)[:k]
    return [int(cand[i]) for i in order], [float(scores[i]) for i in order]


def _run(store, q, cand, k):
    index_path, db_path, _ = store
    return vector_store.semantic_search(q, faiss_ids=list(cand), top_k=k, index_path=index_path, db_path=db_path)


@pytest.mark.parametrize("seed", range(5))
def test_narrow_filter_returns_exact_topk_of_candidates(store, seed):
    vecs = store[2]
    rng = np.random.default_rng(100 + seed)
    cand = rng.choice(N, size=30, replace=False).tolist()
    q = _query(seed)
    got = _run(store, q, cand, 5)
    exp_ids, exp_scores = _expected(vecs, q, cand, 5)
    assert [r["faiss_id"] for r in got] == exp_ids
    assert np.allclose([r["score"] for r in got], exp_scores, atol=1e-5)
    assert all(r["faiss_id"] in set(cand) for r in got)


def test_filter_with_fewer_than_k_matches_returns_all_of_them(store):
    cand = [7, 400, 951]
    got = _run(store, _query(11), cand, 10)
    assert sorted(r["faiss_id"] for r in got) == sorted(cand)


def test_candidate_ids_not_in_index_are_ignored(store):
    cand = [3, 4, 5, 5000, 99999]
    got = _run(store, _query(12), cand, 10)
    assert sorted(r["faiss_id"] for r in got) == [3, 4, 5]


def test_empty_filter_returns_nothing(store):
    assert _run(store, _query(13), [], 5) == []


class _NoSelectorIndex:
    """Delegates to a real index but rejects any search that passes search parameters (selector)."""
    def __init__(self, inner):
        self._inner = inner

    def search(self, x, k, params=None):
        if params is not None:
            raise RuntimeError("selector search unavailable")
        return self._inner.search(x, k)

    def __getattr__(self, name):
        return getattr(self._inner, name)


@pytest.mark.parametrize("seed", range(3))
def test_fallback_when_selector_search_fails_is_still_exact(store, monkeypatch, seed):
    """If the selector-based search is unavailable, the answer must still be the exact top-k of the candidates."""
    real_load = vector_store._load_or_create_index
    monkeypatch.setattr(vector_store, "_load_or_create_index", lambda path=vector_store.FAISS_INDEX_PATH: _NoSelectorIndex(real_load(path)))
    vecs = store[2]
    cand = np.random.default_rng(200 + seed).choice(N, size=30, replace=False).tolist()
    q = _query(20 + seed)
    got = _run(store, q, cand, 5)
    exp_ids, _ = _expected(vecs, q, cand, 5)
    assert [r["faiss_id"] for r in got] == exp_ids
