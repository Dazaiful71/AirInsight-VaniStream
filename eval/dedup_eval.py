"""Dedup eval (A7): threshold sweep for the project's cosine gate plus five baselines, on the labelled pair sheet.

Gold: data/gold/duplicate_pairs_sheet.csv (labels same / paraphrase / follow-up / different; every row must be
labelled, else exit 3) joined by id to data/gold/duplicate_pairs_HIDDEN_KEY.csv (cosine, split).
Positive class (primary): same + paraphrase. Alternative: only "same". Both are reported and the choice is recorded.
Protocol: sweep thresholds, choose the best-F1 threshold on VAL-day pairs only (ties -> the higher threshold), report it
on TEST-day pairs. Methods: project cosine (all-MiniLM-L6-v2 score from the key), exact string match, normalised-text
match, TF-IDF cosine, word 5-gram Jaccard, MinHash estimate (word 3-gram shingles, 128 permutations, seed 42).
The pair sheet was sampled across cosine bands and includes random low-similarity negatives, so its class balance is NOT
the corpus's: precision/recall here describe this sample, not deployment.
Feeds: results/dedup_eval_*.json -> dedup table (see eval/README.md).
"""
import functools
import hashlib
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402

NAME = "dedup_eval"
DEFINITIONS = {
    "primary_same_plus_paraphrase_positive": {"positive": ["same", "paraphrase"], "negative": ["follow-up", "different"]},
    "alternative_only_same_positive": {"positive": ["same"], "negative": ["paraphrase", "follow-up", "different"]},
}


def default_paths() -> dict:
    return {"gold": cfg.GOLD_PAIRS, "key": cfg.GOLD_PAIRS_KEY, "sentence_index": cfg.GOLD_SENTENCE_INDEX}


def gold_status(paths=None):
    p = paths or default_paths()
    return common.check_labelled_csv(p["gold"], "label", cfg.PAIR_LABELS, "duplicate-pair gold")


# ---------------------------------------------------------------- text scores
def normalise(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def word_ngrams(text: str, n: int = 5) -> set:
    w = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def jaccard5(a: str, b: str) -> float:
    ga, gb = word_ngrams(a), word_ngrams(b)
    union = len(ga | gb)
    return len(ga & gb) / union if union else 0.0


_MH_PRIME = (1 << 61) - 1


def shingles(text: str, n: int = cfg.MINHASH_SHINGLE_WORDS) -> set:
    """Word n-gram shingles; a sentence shorter than n words is one shingle; no words -> empty set."""
    w = re.findall(r"[a-z0-9']+", text.lower())
    if not w:
        return set()
    if len(w) < n:
        return {tuple(w)}
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


@functools.lru_cache(maxsize=None)
def _mh_params(perms: int, seed: int):
    rng = np.random.default_rng(seed)
    a = [int(x) for x in rng.integers(1, _MH_PRIME, perms, dtype=np.int64)]
    b = [int(x) for x in rng.integers(0, _MH_PRIME, perms, dtype=np.int64)]
    return tuple(a), tuple(b)


def minhash_signature(shingle_set: set, perms: int = cfg.MINHASH_PERMUTATIONS, seed: int = cfg.SEED):
    """MinHash signature: for each of `perms` random affine permutations of a 61-bit hash, the minimum over the shingles."""
    if not shingle_set:
        return None
    hs = [int.from_bytes(hashlib.blake2b(" ".join(sh).encode("utf-8"), digest_size=8).digest(), "big") % _MH_PRIME
          for sh in shingle_set]
    a, b = _mh_params(perms, seed)
    return tuple(min((a[i] * h + b[i]) % _MH_PRIME for h in hs) for i in range(perms))


def minhash_jaccard(text_a: str, text_b: str, n: int = cfg.MINHASH_SHINGLE_WORDS, perms: int = cfg.MINHASH_PERMUTATIONS,
                    seed: int = cfg.SEED) -> float:
    """Estimated Jaccard similarity of the two sentences' word-shingle sets (fraction of equal signature slots)."""
    sa, sb = minhash_signature(shingles(text_a, n), perms, seed), minhash_signature(shingles(text_b, n), perms, seed)
    if sa is None or sb is None:
        return 0.0
    return sum(x == y for x, y in zip(sa, sb)) / perms


def tfidf_cosines(sents_a, sents_b, corpus_texts):
    """TF-IDF fitted on corpus_texts (unlabelled sentences), cosine of each (a, b) pair."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(lowercase=True).fit(corpus_texts)
    A, B = vec.transform(sents_a), vec.transform(sents_b)
    return np.asarray(A.multiply(B).sum(axis=1)).ravel()


# ---------------------------------------------------------------- metrics
def confusion_counts(score, y, threshold):
    pred = score >= threshold
    return int((pred & y).sum()), int((pred & ~y).sum()), int((~pred & y).sum()), int((~pred & ~y).sum())


def prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f = 0.0 if (p is None or r is None or p + r == 0) else 2 * p * r / (p + r)
    return p, r, f


def sweep(score, y, thresholds, resamples=cfg.BOOTSTRAP_RESAMPLES, seed=cfg.SEED) -> list:
    """Precision / recall / F1 at each threshold with bootstrap CIs. Precision is None when nothing is predicted positive."""
    score, y = np.asarray(score, dtype=float), np.asarray(y, dtype=bool)
    idx = common.bootstrap_indices(len(y), resamples, seed)
    out = []
    for t in thresholds:
        pred = score >= t
        tp, fp, fn, tn = confusion_counts(score, y, t)
        p, r, f = prf(tp, fp, fn)
        TP = (pred & y)[idx].sum(axis=1).astype(float)
        FP = (pred & ~y)[idx].sum(axis=1).astype(float)
        FN = (~pred & y)[idx].sum(axis=1).astype(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            bp = np.where(TP + FP > 0, TP / (TP + FP), np.nan)
            br = np.where(TP + FN > 0, TP / (TP + FN), np.nan)
            bf = np.where(TP + FP + FN > 0, 2 * TP / (2 * TP + FP + FN), np.nan)
        out.append({"threshold": t, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": p, "recall": r, "f1": f,
                    "precision_ci95": common.percentile_ci(bp), "recall_ci95": common.percentile_ci(br),
                    "f1_ci95": common.percentile_ci(bf)})
    return out


def select_threshold(rows):
    """Best F1 on the given sweep rows; ties go to the higher threshold. None if no positive pair exists (F1 all 0)."""
    best = None
    for r in rows:
        if best is None or r["f1"] >= best["f1"]:
            best = r
    if best is None or best["f1"] == 0.0:
        return None
    return best["threshold"]


def evaluate_method(score, y, split, thresholds, resamples=cfg.BOOTSTRAP_RESAMPLES, seed=cfg.SEED) -> dict:
    """Sweep on val, select on val, report on test (plus the 0.85 gate threshold on test for reference)."""
    score, y, split = np.asarray(score, float), np.asarray(y, bool), np.asarray(split)
    val, test = split == "val", split == "test"
    out = {"n_val": int(val.sum()), "n_test": int(test.sum()),
           "positives_val": int(y[val].sum()), "positives_test": int(y[test].sum())}
    if val.sum() == 0 or test.sum() == 0:
        out["status"] = "not computed: need pairs from both val and test days"
        return out
    val_rows = sweep(score[val], y[val], thresholds, resamples, seed)
    test_rows = sweep(score[test], y[test], thresholds, resamples, seed)
    chosen = select_threshold(val_rows)
    out["sweep_val"], out["sweep_test_for_plotting_only"] = val_rows, test_rows
    if chosen is None:
        out["selected_threshold_on_val"] = None
        out["status"] = "no threshold selected: val pairs contain no positive pair the method can find"
    else:
        out["selected_threshold_on_val"] = chosen
        out["test_at_selected_threshold"] = next(r for r in test_rows if r["threshold"] == chosen)
        out["val_at_selected_threshold"] = next(r for r in val_rows if r["threshold"] == chosen)
    ref = [r for r in test_rows if r["threshold"] == 0.85]
    if ref:
        out["test_at_project_default_0.85_reference_only"] = ref[0]
    return out


def evaluate_binary_method(pred, y, split, resamples=cfg.BOOTSTRAP_RESAMPLES, seed=cfg.SEED) -> dict:
    """Parameter-free matcher (exact / normalised): one operating point, reported on val and on test."""
    pred, y, split = np.asarray(pred, float), np.asarray(y, bool), np.asarray(split)
    out = {}
    for sp in cfg.GOLD_SPLITS:
        m = split == sp
        out[f"{sp}_pairs"] = (sweep(pred[m], y[m], [1.0], resamples, seed)[0] if m.sum() else "no pairs")
    return out


# ---------------------------------------------------------------- driver
def load_pairs(paths) -> list:
    if not os.path.isfile(paths["key"]):
        raise common.PrerequisiteMissing(f"hidden key file missing: {common.rel(paths['key'])}")
    sheet = common.read_csv(paths["gold"])
    key = {r["id"]: r for r in common.read_csv(paths["key"])}
    missing = [r["id"] for r in sheet if r["id"] not in key]
    if missing:
        raise common.PrerequisiteMissing(f"pairs without an entry in the hidden key file: {missing[:5]}")
    rows = []
    for r in sheet:
        k = key[r["id"]]
        rows.append({"id": r["id"], "a": r["sentence_a"], "b": r["sentence_b"], "label": r["label"].strip(),
                     "cosine": float(k["cosine_all_MiniLM_L6_v2"]), "split": k["split"], "date": k["date"]})
    return rows


def compute(paths, resamples=cfg.BOOTSTRAP_RESAMPLES):
    rows = load_pairs(paths)
    bad = sorted({r["split"] for r in rows} - set(cfg.GOLD_SPLITS))
    if bad:
        raise common.PrerequisiteMissing(f"pair key contains non-val/test splits: {bad}")
    a, b = [r["a"] for r in rows], [r["b"] for r in rows]
    corpus = a + b
    if paths.get("sentence_index") and os.path.isfile(paths["sentence_index"]):
        corpus = [r["text"] for r in common.read_csv(paths["sentence_index"])]
    scores = {
        "project_cosine_minilm": np.array([r["cosine"] for r in rows]),
        "tfidf_cosine": tfidf_cosines(a, b, corpus),
        "word_5gram_jaccard": np.array([jaccard5(x, y) for x, y in zip(a, b)]),
        "minhash_jaccard_estimate": np.array([minhash_jaccard(x, y) for x, y in zip(a, b)]),
    }
    binary = {
        "exact_string_match": np.array([float(x == y) for x, y in zip(a, b)]),
        "normalised_text_match": np.array([float(normalise(x) == normalise(y)) for x, y in zip(a, b)]),
    }
    split = [r["split"] for r in rows]
    labels = [r["label"] for r in rows]
    results = {
        "label_definitions_for_positive_class": DEFINITIONS,
        "minhash": {"shingle": f"word {cfg.MINHASH_SHINGLE_WORDS}-grams", "permutations": cfg.MINHASH_PERMUTATIONS,
                    "hash": "blake2b 64-bit mod 2^61-1, affine permutations", "seed": cfg.SEED,
                    "meaning": "estimates the Jaccard similarity of the word-shingle sets; swept like TF-IDF and Jaccard"},
        "choice_recorded": "primary = same + paraphrase positive; alternative = only 'same' positive; both reported",
        "protocol": "threshold chosen on VAL-day pairs (max F1, ties -> higher threshold), reported on TEST-day pairs",
        "thresholds_swept": {"project_cosine_minilm": [cfg.DEDUP_THRESHOLDS[0], cfg.DEDUP_THRESHOLDS[-1], 0.01],
                             "baselines_tfidf_jaccard": [cfg.DEDUP_BASELINE_THRESHOLDS[0], cfg.DEDUP_BASELINE_THRESHOLDS[-1], 0.01]},
        "bootstrap": common.bootstrap_meta(len(rows), resamples),
        "sampling_note": "pairs were sampled across cosine bands 0.60-0.95 (+ random pairs < 0.40), so class balance is "
                         "not the corpus's; numbers describe this sample only",
        "pairs": {"n": len(rows), "by_split": {s: split.count(s) for s in cfg.GOLD_SPLITS},
                  "label_counts": {l: labels.count(l) for l in cfg.PAIR_LABELS}},
        "definitions": {},
    }
    for dname, d in DEFINITIONS.items():
        y = np.array([l in d["positive"] for l in labels])
        block = {"positives": int(y.sum()), "negatives": int((~y).sum()), "methods": {}}
        for m, sc in scores.items():
            grid = cfg.DEDUP_THRESHOLDS if m == "project_cosine_minilm" else cfg.DEDUP_BASELINE_THRESHOLDS
            block["methods"][m] = evaluate_method(sc, y, split, grid, resamples)
        for m, pr in binary.items():
            block["methods"][m] = evaluate_binary_method(pr, y, split, resamples)
        results["definitions"][dname] = block
    return results, {"hidden_key_read": True}


def run(paths=None, results_dir=None):
    p = paths or default_paths()
    st = gold_status(p)
    return common.save_or_report(NAME, st, lambda: compute(p), [p["gold"], p["key"], p.get("sentence_index", "")], results_dir)


def main() -> int:
    return run()[0]


if __name__ == "__main__":
    raise SystemExit(main())
