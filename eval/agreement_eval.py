"""Human-vs-LLM agreement on the genre sheets (S12). Every output here is named "human_vs_llm_agreement".

This is NOT inter-annotator agreement: one side is a language model's pre-label. Never report these numbers as a kappa
between annotators.

Two groups are measured separately, because they mean different things:
  * overlap_human_from_scratch: the 175-sentence overlap, human labels typed before the human saw the LLM labels. This is
    the only group that is independent of the LLM. Default human column: annotator_2_label in the overlap sheet
    (TODO: confirm that this is where the from-scratch labels go; change with --overlap-col).
  * rest_human_reviewed: the other 225 sentences, where the human REVIEWED and corrected LLM pre-labels. Agreement here is
    inflated by anchoring (the human started from the LLM label) and is not an independent measure.
Per group: observed agreement, Cohen's kappa, per-label agreement counts, a confusion matrix (rows human, columns LLM) and
95% percentile bootstrap CIs (1000 resamples, seed 42).

The human labels are checked FIRST. If no group has complete human labels the script exits with code 3 and does not open
the LLM label files. Feeds: results/human_vs_llm_agreement_*.json (see eval/README.md).
"""
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402
from genre_eval import cohen_kappa  # noqa: E402

NAME = "human_vs_llm_agreement"
GROUPS = ("overlap_human_from_scratch", "rest_human_reviewed")
CAVEAT = {
    "overlap_human_from_scratch": "human labels typed from scratch before seeing the LLM labels; independent of the LLM",
    "rest_human_reviewed": "human reviewed and corrected LLM pre-labels (anchoring): agreement is inflated and NOT independent",
}


def default_paths() -> dict:
    return {"overlap_sheet": cfg.GOLD_GENRE_ANNOTATOR2, "overlap_col": "annotator_2_label",
            "rest_sheet": cfg.GOLD_GENRE, "rest_col": "annotator_1_label",
            "llm_overlap": cfg.GOLD_LLM_OVERLAP, "llm_rest": cfg.GOLD_LLM_REST}


# ---------------------------------------------------------------- pure metrics
def agreement_metrics(human: list, llm: list, labels: list, min_support: int = cfg.MIN_CLASS_SUPPORT,
                      resamples: int = cfg.BOOTSTRAP_RESAMPLES, seed: int = cfg.SEED) -> dict:
    """Observed agreement, Cohen's kappa, per-label counts, confusion matrix and bootstrap CIs for two label lists."""
    n = len(human)
    if n == 0 or n != len(llm):
        raise ValueError("need two equally long, non-empty label lists")
    idx = {l: i for i, l in enumerate(labels)}
    conf = np.zeros((len(labels), len(labels)), dtype=int)
    for h, m in zip(human, llm):
        conf[idx[h], idx[m]] += 1
    agree = sum(h == m for h, m in zip(human, llm))
    per_label = {}
    for l in labels:
        i = idx[l]
        n_h, n_m, both = int(conf[i].sum()), int(conf[:, i].sum()), int(conf[i, i])
        entry = {"human_count": n_h, "llm_count": n_m, "agree_count": both, "disagree_count_given_human_label": n_h - both}
        if n_h >= min_support:
            entry["agreement_rate_given_human_label"] = both / n_h
        else:
            entry["agreement_rate_given_human_label"] = "insufficient support"
        per_label[l] = entry
    h_arr = np.array([idx[h] for h in human])
    m_arr = np.array([idx[m] for m in llm])
    boot = common.bootstrap_indices(n, resamples, seed)
    obs = (h_arr == m_arr)[boot].mean(axis=1)
    kappas = []
    for row in boot:
        k = cohen_kappa([human[i] for i in row], [llm[i] for i in row])
        kappas.append(np.nan if k is None else k)
    return {
        "n": n, "observed_agreement": agree / n, "cohens_kappa_human_vs_llm": cohen_kappa(human, llm),
        "agree_count": int(agree), "disagree_count": int(n - agree),
        "per_label": per_label, "min_support_for_rate": min_support,
        "confusion_matrix": {"rows_human_cols_llm": list(labels), "counts": conf.tolist()},
        "bootstrap": {**common.bootstrap_meta(n, resamples, seed), "observed_agreement_ci95": common.percentile_ci(obs),
                      "cohens_kappa_ci95": common.percentile_ci(kappas)},
    }


# ---------------------------------------------------------------- inputs
def human_labels(sheet: str, col: str, labels: list, exclude_ids=None, only_ids=None):
    """(dict id -> label, message). dict is None when the sheet is missing, a label is empty or outside the label set."""
    rel = common.rel(sheet)
    if not os.path.isfile(sheet):
        return None, f"sheet missing: {rel}"
    rows = common.read_csv(sheet)
    if exclude_ids is not None:
        rows = [r for r in rows if r["id"] not in exclude_ids]
    if only_ids is not None:
        rows = [r for r in rows if r["id"] in only_ids]
    if not rows:
        return None, f"no rows to compare in {rel}"
    empty = [r["id"] for r in rows if not (r.get(col) or "").strip()]
    if empty:
        return None, f"human labels not complete in {rel}: {len(rows) - len(empty)} of {len(rows)} rows have '{col}' filled"
    got = {r["id"]: r[col].strip() for r in rows}
    bad = sorted(set(got.values()) - set(labels))
    if bad:
        return None, f"labels outside the project label set in {rel}: {bad[:5]}"
    return got, f"{len(got)} human labels in {rel}"


def llm_labels(path: str, labels: list) -> dict:
    if not os.path.isfile(path):
        raise common.PrerequisiteMissing(f"LLM label file missing: {common.rel(path)}")
    out = {r["id"]: r["llm_label"].strip() for r in common.read_csv(path)}
    bad = sorted(set(out.values()) - set(labels))
    if bad:
        raise common.PrerequisiteMissing(f"LLM labels outside the label set in {common.rel(path)}: {bad[:5]}")
    return out


def collect_human(paths: dict, labels: list) -> dict:
    """Human labels per group, without touching any LLM file. group -> (dict or None, message)."""
    overlap_ids = {r["id"] for r in common.read_csv(paths["overlap_sheet"])} if os.path.isfile(paths["overlap_sheet"]) else set()
    return {
        "overlap_human_from_scratch": human_labels(paths["overlap_sheet"], paths["overlap_col"], labels),
        "rest_human_reviewed": human_labels(paths["rest_sheet"], paths["rest_col"], labels, exclude_ids=overlap_ids),
    }


def gold_status(paths=None, labels=None):
    p = paths or default_paths()
    h = collect_human(p, labels or cfg.genre_labels())
    ok = any(v[0] is not None for v in h.values())
    msg = "; ".join(f"{g}: {m}" for g, (d, m) in h.items())
    if not ok:
        return common.GoldStatus(False, "no group has complete human labels, so nothing was compared and the LLM files were not "
                                        "opened. " + msg)
    return common.GoldStatus(True, msg, h)


def compute(paths, labels, human=None, resamples=cfg.BOOTSTRAP_RESAMPLES):
    human = human or collect_human(paths, labels)
    results = {"output_name": NAME,
               "what_this_is": "agreement between human labels and LLM pre-labels; NOT inter-annotator agreement",
               "llm_label_files": {"overlap": common.rel(paths["llm_overlap"]), "rest": common.rel(paths["llm_rest"])},
               "label_set": "nlp_pipeline.GENRE_LABELS", "groups": {}}
    llm_path = {"overlap_human_from_scratch": paths["llm_overlap"], "rest_human_reviewed": paths["llm_rest"]}
    for g in GROUPS:
        got, msg = human[g]
        if got is None:
            results["groups"][g] = {"status": f"not computed: {msg}", "caveat": CAVEAT[g]}
            continue
        llm = llm_labels(llm_path[g], labels)
        missing = sorted(set(got) - set(llm))
        extra = sorted(set(llm) - set(got))
        if missing or extra:
            raise common.PrerequisiteMissing(f"{g}: ids differ between the human sheet and {common.rel(llm_path[g])} "
                                             f"({len(missing)} without an LLM label, {len(extra)} LLM labels without a human row)")
        ids = sorted(got)
        results["groups"][g] = {"caveat": CAVEAT[g], **agreement_metrics([got[i] for i in ids], [llm[i] for i in ids],
                                                                          labels, resamples=resamples)}
    return results, {"human_vs_llm_agreement": True}


def run(paths=None, results_dir=None, resamples=cfg.BOOTSTRAP_RESAMPLES):
    p = paths or default_paths()
    labels = cfg.genre_labels()
    st = gold_status(p, labels)
    inputs = [p["overlap_sheet"], p["rest_sheet"]] + ([p["llm_overlap"], p["llm_rest"]] if st.ok else [])
    return common.save_or_report(NAME, st, lambda: compute(p, labels, st.rows, resamples), inputs, results_dir)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    d = default_paths()
    ap.add_argument("--overlap-sheet", default=d["overlap_sheet"])
    ap.add_argument("--overlap-col", default=d["overlap_col"], help="column with the human labels typed from scratch")
    ap.add_argument("--rest-sheet", default=d["rest_sheet"])
    ap.add_argument("--rest-col", default=d["rest_col"], help="column with the reviewed human labels")
    a = ap.parse_args()
    p = {**d, "overlap_sheet": a.overlap_sheet, "overlap_col": a.overlap_col, "rest_sheet": a.rest_sheet, "rest_col": a.rest_col}
    return run(p)[0]


if __name__ == "__main__":
    raise SystemExit(main())
