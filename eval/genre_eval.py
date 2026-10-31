"""Genre eval (A8): macro-F1, per-class P/R/F1 with support, confusion matrix, bootstrap CIs, two baselines, kappa.

Gold: data/gold/genre_sheet_annotator1.csv (must be fully labelled, else exit 3 with a message).
Systems, each tagged with a category in the result JSON:
  * baselines (trained-on-silver): majority class and TF-IDF + logistic regression, trained ONLY on TRAIN-day silver labels
    in store_A after removing every sentence whose text equals a gold/val/test sentence (the S6 leakage rule)
  * project classifiers, zero-shot (no training): the fast NLI backend and the BART zero-shot backend
  * fine-tuned-on-silver: checkpoints from eval/finetune_genre.py (5 seeds; mean and std over seeds reported); scored only if
    they exist; training happens only with --train-finetune or the cluster job, never implicitly
  * the older models/air-genre-classifier checkpoint if present, marked UNVERIFIED (its training data is unknown)
All are evaluated ONLY on the gold sheet. Silver labels are never scored as gold.
A class with fewer than MIN_CLASS_SUPPORT gold examples gets no score ("insufficient support") and is left out of macro-F1.
Cohen's kappa is computed between annotator 1 and annotator 2 on the overlap file once annotator 2 has labelled it.
Feeds: results/genre_eval_*.json -> genre table (see eval/README.md).
"""
import json
import os
import sqlite3
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402

NAME = "genre_eval"
INSUFFICIENT = "insufficient support"


def default_paths() -> dict:
    return {"gold": cfg.GOLD_GENRE, "annotator2": cfg.GOLD_GENRE_ANNOTATOR2, "store_db": cfg.STORE_DB,
            "sample_config": cfg.SAMPLE_CONFIG}


def gold_status(paths=None, labels=None):
    p = paths or default_paths()
    return common.check_labelled_csv(p["gold"], "annotator_1_label", labels or cfg.genre_labels(), "genre gold (annotator 1)")


# ---------------------------------------------------------------- metrics
def confusion(y_true, y_pred, labels) -> list:
    idx = {l: i for i, l in enumerate(labels)}
    m = np.zeros((len(labels), len(labels)), dtype=int)
    for t, p in zip(y_true, y_pred):
        m[idx[t], idx[p]] += 1
    return m.tolist()


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def genre_metrics(y_true, y_pred, labels, min_support=cfg.MIN_CLASS_SUPPORT,
                  resamples=cfg.BOOTSTRAP_RESAMPLES, seed=cfg.SEED) -> dict:
    """Per-class P/R/F1 (+support), macro-F1 over classes with enough support, accuracy, confusion matrix, bootstrap CIs.

    Zero-division convention: precision/recall/F1 are 0.0 when their denominator is 0 (flagged as *_undefined).
    """
    y_true, y_pred = list(y_true), list(y_pred)
    n = len(y_true)
    sup = Counter(y_true)
    included = [l for l in labels if sup[l] >= min_support]
    T = np.array([[t == l for l in labels] for t in y_true], dtype=bool)
    P = np.array([[p == l for l in labels] for p in y_pred], dtype=bool)
    per_class = {}
    for j, l in enumerate(labels):
        pred_n = int(P[:, j].sum())
        if l not in included:
            per_class[l] = {"support": int(sup[l]), "predicted": pred_n, "status": INSUFFICIENT,
                            "note": f"fewer than {min_support} gold examples; no score reported"}
            continue
        tp = int((T[:, j] & P[:, j]).sum())
        fp = int((~T[:, j] & P[:, j]).sum())
        fn = int((T[:, j] & ~P[:, j]).sum())
        p, r, f = _prf(tp, fp, fn)
        per_class[l] = {"support": int(sup[l]), "predicted": pred_n, "precision": p, "recall": r, "f1": f,
                        "precision_undefined": tp + fp == 0, "recall_undefined": tp + fn == 0}
    out = {"n": n, "labels": list(labels), "min_class_support": min_support, "classes_scored": included,
           "classes_insufficient_support": [l for l in labels if l not in included],
           "per_class": per_class, "confusion_matrix": {"rows_true_cols_pred": list(labels), "counts": confusion(y_true, y_pred, labels)},
           "accuracy": float((T & P).any(axis=1).mean()) if n else None}
    if not included or n == 0:
        out["macro_f1"] = INSUFFICIENT
        out["bootstrap"] = {**common.bootstrap_meta(n, resamples, seed), "note": "no class has enough support"}
        return out
    out["macro_f1"] = float(np.mean([per_class[l]["f1"] for l in included]))

    idx = common.bootstrap_indices(n, resamples, seed)
    TP = (T & P)[idx].sum(axis=1).astype(float)          # (B, L)
    FP = (~T & P)[idx].sum(axis=1).astype(float)
    FN = (T & ~P)[idx].sum(axis=1).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        prec = np.where(TP + FP > 0, TP / (TP + FP), 0.0)
        rec = np.where(TP + FN > 0, TP / (TP + FN), 0.0)
        f1 = np.where(prec + rec > 0, 2 * prec * rec / (prec + rec), 0.0)
    cols = [labels.index(l) for l in included]
    out["bootstrap"] = {
        **common.bootstrap_meta(n, resamples, seed),
        "note": "classes fixed to those scored on the full gold set; a resample missing a class counts its F1 as 0",
        "macro_f1_ci95": common.percentile_ci(f1[:, cols].mean(axis=1)),
        "accuracy_ci95": common.percentile_ci((T & P)[idx].any(axis=2).mean(axis=1)),
        "per_class_f1_ci95": {l: common.percentile_ci(f1[:, labels.index(l)]) for l in included},
    }
    return out


def cohen_kappa(a, b):
    """Cohen's kappa for two label lists; None when chance agreement is 1 (kappa undefined)."""
    a, b = list(a), list(b)
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("need two equally long, non-empty label lists")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def kappa_block(ids_to_a1, rows2, labels, resamples=cfg.BOOTSTRAP_RESAMPLES, seed=cfg.SEED) -> dict:
    """Kappa between annotator 1 and 2 on the overlap rows (matched by id)."""
    pairs = [(ids_to_a1[r["id"]], r["annotator_2_label"].strip()) for r in rows2
             if r["id"] in ids_to_a1 and r.get("annotator_2_label", "").strip()]
    if not rows2 or len(pairs) < len(rows2):
        return {"status": "not computed: annotator 2 has not labelled the whole overlap file",
                "labelled": len(pairs), "overlap_rows": len(rows2)}
    bad = sorted({b for _, b in pairs} - set(labels))
    if bad:
        return {"status": f"not computed: annotator 2 labels outside the label set: {bad[:5]}"}
    a1, a2 = [p[0] for p in pairs], [p[1] for p in pairs]
    idx = common.bootstrap_indices(len(pairs), resamples, seed)
    ks = []
    for row in idx:
        k = cohen_kappa([a1[i] for i in row], [a2[i] for i in row])
        ks.append(np.nan if k is None else k)
    return {"n_overlap": len(pairs), "kappa": cohen_kappa(a1, a2), "observed_agreement": float(np.mean([x == y for x, y in pairs])),
            "bootstrap": {**common.bootstrap_meta(len(pairs), resamples, seed), "kappa_ci95": common.percentile_ci(ks)},
            "per_class_counts_annotator1": dict(Counter(a1)), "per_class_counts_annotator2": dict(Counter(a2))}


# ---------------------------------------------------------------- baselines and trained systems
import finetune_genre as ft  # noqa: E402

ALL_SYSTEMS = ("baselines", "fast", "zero-shot", "finetuned")
CAT_ZERO_SHOT = "zero-shot (no training on this corpus)"
CAT_FINETUNED = "fine-tuned-on-silver (train-day silver labels only, leakage-filtered)"
CAT_BASELINE = "trained-on-silver baseline (train-day silver labels only, leakage-filtered)"
CAT_PROJECT_CKPT = "fine-tuned-on-silver (older project checkpoint; its training data is NOT verified leakage-free: UNVERIFIED)"


def tfidf_lr_predict(train_texts, train_labels, test_texts, seed=cfg.SEED):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    vec = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True, min_df=2)
    X = vec.fit_transform(train_texts)
    clf = LogisticRegression(max_iter=1000, C=1.0, random_state=seed)
    clf.fit(X, train_labels)
    return list(clf.predict(vec.transform(test_texts)))


def split_of_dates(sample_config: str) -> dict:
    plan = json.load(open(sample_config, encoding="utf-8"))["pilot_plan_s4"]["option_A_about_10_days"]["split"]
    return {d: s for s in plan for d in plan[s]["days"]}


def mean_std(values):
    v = np.asarray(values, dtype=float)
    return {"mean": float(v.mean()), "std": float(v.std(ddof=1)) if len(v) > 1 else None, "n": int(len(v))}


def aggregate_seeds(per_seed: dict) -> dict:
    """Mean and sample standard deviation (ddof=1) over seeds of macro-F1, accuracy and per-class F1.

    per_seed: seed -> genre_metrics() dict (all-gold). A class enters the per-class table only if it was scored in every seed.
    """
    seeds = sorted(per_seed)
    out = {"n_seeds": len(seeds), "seeds": seeds, "std_definition": "sample standard deviation over seeds (ddof=1)",
           "per_seed_macro_f1": {s: per_seed[s]["macro_f1"] for s in seeds}}
    ok = [s for s in seeds if isinstance(per_seed[s]["macro_f1"], float)]
    out["macro_f1"] = mean_std([per_seed[s]["macro_f1"] for s in ok]) if len(ok) == len(seeds) and ok else INSUFFICIENT
    accs = [per_seed[s]["accuracy"] for s in seeds if per_seed[s]["accuracy"] is not None]
    out["accuracy"] = mean_std(accs) if accs else None
    common_classes = set.intersection(*[set(per_seed[s]["classes_scored"]) for s in seeds]) if seeds else set()
    out["per_class_f1"] = {c: mean_std([per_seed[s]["per_class"][c]["f1"] for s in seeds]) for c in sorted(common_classes)}
    return out


def score_block(y, pred, splits, labels) -> dict:
    block = {"all_gold": genre_metrics(y, pred, labels)}
    for sp in cfg.GOLD_SPLITS:
        sel = [i for i, s in enumerate(splits) if s == sp]
        block[f"{sp}_days_only"] = genre_metrics([y[i] for i in sel], [pred[i] for i in sel], labels)
    return block


def default_classifiers() -> dict:
    """The project's own zero-shot backends, loaded lazily. Each predict() returns one label per sentence."""
    def make(fast):
        def predict(texts):
            import nlp_pipeline
            return [g for g, _ in nlp_pipeline.classify_genres_batch(list(texts), fast=fast)]
        return predict
    return {"project_fast_nli_minilm": {"key": "fast", "category": CAT_ZERO_SHOT, "predict": make(True),
                                        "model": "cross-encoder/nli-MiniLM2-L6-H768"},
            "project_zero_shot_bart": {"key": "zero-shot", "category": CAT_ZERO_SHOT, "predict": make(False),
                                       "model": "facebook/bart-large-mnli"}}


def default_finetune() -> dict:
    return {"dir": cfg.FINETUNE_DIR, "seeds": list(cfg.SEEDS_FOR_MULTI_RUN), "predictor": ft.hf_predictor,
            "trainer": ft.default_trainer, "train": False, "project_checkpoint": cfg.PROJECT_CHECKPOINT,
            "epochs": 5, "batch_size": 16}


def finetuned_block(y, texts, splits, labels, ft_cfg, train_texts, train_labels, train_info) -> dict:
    """Score finished leakage-safe checkpoints (one per seed) and aggregate. Trains missing seeds ONLY if ft_cfg['train']."""
    per_seed, blocks, notes = {}, {}, []
    for seed in ft_cfg["seeds"]:
        d = ft.seed_dir(ft_cfg["dir"], seed)
        if ft_cfg.get("train") and not ft.is_done(d):
            r = ft.train_seed(train_texts, train_labels, seed, ft_cfg["dir"], train_info, trainer=ft_cfg["trainer"],
                              epochs=ft_cfg.get("epochs", 5), batch_size=ft_cfg.get("batch_size", 16))
            notes.append(r["status"])
        if not ft.is_done(d):
            continue
        marker = json.load(open(os.path.join(d, "DONE"), encoding="utf-8"))
        pred = ft_cfg["predictor"](d, texts)
        blocks[seed] = {"training": {"seed": marker["seed"], "n_training_examples": marker["n_training_examples"]},
                        **score_block(y, pred, splits, labels)}
        per_seed[seed] = blocks[seed]["all_gold"]
    if not per_seed:
        return {"category": CAT_FINETUNED, "status": "not run: no finished checkpoint in "
                f"{common.rel(ft_cfg['dir'])} (train with eval/finetune_genre.py or genre_eval.py --train-finetune)",
                "seeds_requested": list(ft_cfg["seeds"])}
    return {"category": CAT_FINETUNED, "training_set": train_info, "seeds_requested": list(ft_cfg["seeds"]),
            "seeds_scored": sorted(per_seed), "train_notes": notes, "per_seed": blocks, "mean_std_over_seeds": aggregate_seeds(per_seed)}


# ---------------------------------------------------------------- driver
def compute(paths, labels, systems=ALL_SYSTEMS, classifiers=None, finetune=None):
    gold = common.read_csv(paths["gold"])
    texts = [r["sentence_text"] for r in gold]
    y = [r["annotator_1_label"].strip() for r in gold]
    split_of = split_of_dates(paths["sample_config"])
    splits = [split_of.get(r["date"], "unknown") for r in gold]
    bad_days = sorted({r["date"] for r, s in zip(gold, splits) if s not in cfg.GOLD_SPLITS})
    if bad_days:
        raise common.PrerequisiteMissing(f"gold sheet has sentences from non-val/test days: {bad_days}")
    tr_texts, tr_labels, tr_info = ft.build_training_set(paths["store_db"], paths["gold"], paths.get("sentence_index", ""))
    majority = Counter(tr_labels).most_common(1)[0][0]
    results = {
        "label_set": "nlp_pipeline.GENRE_LABELS",
        "gold_sheet": {"n": len(gold), "n_by_split": dict(Counter(splits)), "support_by_class": dict(Counter(y))},
        "baseline_training_data": {**tr_info, "n_segments": tr_info["n_training_examples"], "majority_class": majority,
                                   "tfidf": "TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, min_df=2)",
                                   "logreg": "LogisticRegression(C=1.0, max_iter=1000)", "seed": cfg.SEED},
        "systems_requested": list(systems), "systems": {},
    }
    if "baselines" in systems:
        results["systems"]["majority_class_train_silver"] = {
            "category": CAT_BASELINE, **score_block(y, [majority] * len(gold), splits, labels)}
        per_seed = {s: genre_metrics(y, tfidf_lr_predict(tr_texts, tr_labels, texts, seed=s), labels) for s in cfg.SEEDS_FOR_MULTI_RUN}
        results["systems"]["tfidf_logreg_train_silver"] = {
            "category": CAT_BASELINE,
            **score_block(y, tfidf_lr_predict(tr_texts, tr_labels, texts, seed=cfg.SEED), splits, labels),
            "multi_seed": {"mean_std_over_seeds": aggregate_seeds(per_seed),
                           "note": "LogisticRegression (lbfgs) is deterministic, so the seeds are expected to give identical "
                                   "predictions and a standard deviation of 0; reported for completeness"}}
    available = classifiers if classifiers is not None else default_classifiers()
    for name, spec in available.items():
        if spec["key"] not in systems:
            continue
        try:
            pred = list(spec["predict"](texts))
            if len(pred) != len(texts):
                raise RuntimeError(f"classifier returned {len(pred)} labels for {len(texts)} sentences")
            bad = sorted(set(pred) - set(labels))
            if bad:
                raise RuntimeError(f"classifier returned labels outside the label set: {bad[:5]}")
            results["systems"][name] = {"category": spec["category"], "model": spec.get("model"),
                                        **score_block(y, pred, splits, labels)}
        except Exception as e:  # a missing model or no network must not hide the other systems
            results["systems"][name] = {"category": spec["category"], "status": f"not run: {type(e).__name__}: {e}"}
    if "finetuned" in systems:
        ft_cfg = {**default_finetune(), **(finetune or {})}
        results["systems"]["finetuned_on_silver_multi_seed"] = finetuned_block(y, texts, splits, labels, ft_cfg, tr_texts, tr_labels, tr_info)
        ckpt = ft_cfg.get("project_checkpoint")
        if ckpt and os.path.isdir(ckpt):
            try:
                results["systems"]["project_checkpoint_air_genre_classifier"] = {
                    "category": CAT_PROJECT_CKPT, **score_block(y, list(ft_cfg["predictor"](ckpt, texts)), splits, labels)}
            except Exception as e:
                results["systems"]["project_checkpoint_air_genre_classifier"] = {"category": CAT_PROJECT_CKPT,
                                                                                 "status": f"not run: {type(e).__name__}: {e}"}
        else:
            results["systems"]["project_checkpoint_air_genre_classifier"] = {
                "category": CAT_PROJECT_CKPT, "status": f"not run: no checkpoint at {common.rel(ckpt or '')}"}
    a2 = paths.get("annotator2")
    if a2 and os.path.isfile(a2):
        results["kappa_annotator1_vs_annotator2"] = kappa_block({r["id"]: r["annotator_1_label"].strip() for r in gold},
                                                                  common.read_csv(a2), labels)
    else:
        results["kappa_annotator1_vs_annotator2"] = {"status": "not computed: overlap file missing"}
    return results, {"seeds_for_multi_run": list(cfg.SEEDS_FOR_MULTI_RUN)}


def run(paths=None, results_dir=None, systems=ALL_SYSTEMS, classifiers=None, finetune=None):
    p = paths or default_paths()
    labels = cfg.genre_labels()
    st = gold_status(p, labels)
    inputs = [p["gold"], p["annotator2"], p["store_db"]]
    return common.save_or_report(NAME, st, lambda: compute(p, labels, systems, classifiers, finetune), inputs, results_dir)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--systems", default=",".join(ALL_SYSTEMS), help="comma list of: " + ", ".join(ALL_SYSTEMS))
    ap.add_argument("--train-finetune", action="store_true", help="train missing fine-tune seeds first (slow; off by default)")
    a = ap.parse_args()
    systems = tuple(s.strip() for s in a.systems.split(",") if s.strip())
    bad = sorted(set(systems) - set(ALL_SYSTEMS))
    if bad:
        ap.error(f"unknown systems: {bad}")
    ft_cfg = {"train": True} if a.train_finetune else None
    return run(systems=systems, finetune=ft_cfg)[0]


if __name__ == "__main__":
    raise SystemExit(main())
