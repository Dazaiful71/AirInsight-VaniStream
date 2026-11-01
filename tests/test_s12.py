"""S12: human-vs-LLM agreement (synthetic, hand-computed), the --two-humans kappa guard, committed store reports."""
import csv
import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "eval"))
sys.path.insert(0, ROOT)

import agreement_eval  # noqa: E402
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402
import genre_eval  # noqa: E402
from test_eval_metrics import _genre_fixture, load, write_csv  # noqa: E402

LABELS = ["A", "B", "C"]
HUMAN = ["A", "A", "A", "B", "B", "C"]
LLM = ["A", "A", "B", "B", "A", "C"]


# =============================================================== agreement metrics, hand computed
def test_agreement_hand_computed():
    m = agreement_eval.agreement_metrics(HUMAN, LLM, LABELS, min_support=1, resamples=200)
    assert m["n"] == 6 and m["agree_count"] == 4 and m["disagree_count"] == 2
    assert m["observed_agreement"] == pytest.approx(4 / 6)
    # po = 4/6; human counts (3,2,1), LLM counts (3,2,1) -> pe = (9 + 4 + 1) / 36 = 14/36; kappa = (24/36 - 14/36) / (22/36) = 5/11
    assert m["cohens_kappa_human_vs_llm"] == pytest.approx(5 / 11)
    assert m["confusion_matrix"]["counts"] == [[2, 1, 0], [1, 1, 0], [0, 0, 1]]
    a, b, c = (m["per_label"][k] for k in LABELS)
    assert (a["human_count"], a["llm_count"], a["agree_count"]) == (3, 3, 2)
    assert (b["human_count"], b["llm_count"], b["agree_count"]) == (2, 2, 1)
    assert (c["human_count"], c["llm_count"], c["agree_count"]) == (1, 1, 1)
    assert a["agreement_rate_given_human_label"] == pytest.approx(2 / 3) and b["agreement_rate_given_human_label"] == 0.5
    assert a["disagree_count_given_human_label"] == 1


def test_agreement_default_support_floor_hides_rates_but_keeps_counts():
    m = agreement_eval.agreement_metrics(HUMAN, LLM, LABELS, resamples=50)          # default floor 5
    assert all(v["agreement_rate_given_human_label"] == "insufficient support" for v in m["per_label"].values())
    assert m["per_label"]["A"]["agree_count"] == 2


def test_agreement_perfect_and_total_disagreement_edge_cases():
    perfect = agreement_eval.agreement_metrics(["A", "B", "A", "B"], ["A", "B", "A", "B"], LABELS, resamples=100)
    assert perfect["observed_agreement"] == 1.0 and perfect["cohens_kappa_human_vs_llm"] == pytest.approx(1.0)
    assert perfect["bootstrap"]["observed_agreement_ci95"] == [1.0, 1.0]
    flipped = agreement_eval.agreement_metrics(["A", "B"], ["B", "A"], LABELS, resamples=50)
    assert flipped["observed_agreement"] == 0.0 and flipped["cohens_kappa_human_vs_llm"] == pytest.approx(-1.0)
    constant = agreement_eval.agreement_metrics(["A", "A"], ["A", "A"], LABELS, resamples=50)
    assert constant["cohens_kappa_human_vs_llm"] is None                            # chance agreement 1: undefined
    with pytest.raises(ValueError):
        agreement_eval.agreement_metrics(["A"], ["A", "B"], LABELS)


def test_agreement_bootstrap_states_seed_and_resamples_and_is_reproducible():
    a = agreement_eval.agreement_metrics(HUMAN, LLM, LABELS, resamples=300, seed=7)
    b = agreement_eval.agreement_metrics(HUMAN, LLM, LABELS, resamples=300, seed=7)
    assert a["bootstrap"]["seed"] == 7 and a["bootstrap"]["resamples"] == 300
    assert a["bootstrap"]["observed_agreement_ci95"] == b["bootstrap"]["observed_agreement_ci95"]
    lo, hi = a["bootstrap"]["observed_agreement_ci95"]
    assert 0 <= lo <= 4 / 6 + 1e-9 and 4 / 6 - 1e-9 <= hi <= 1
    default = agreement_eval.agreement_metrics(HUMAN, LLM, LABELS)
    assert default["bootstrap"]["seed"] == 42 and default["bootstrap"]["resamples"] == 1000


# =============================================================== end to end on synthetic sheets
def _fixture(tmp_path, overlap_labelled=True, rest_labelled=True):
    """Overlap sheet (4 rows, human col annotator_2_label), annotator-1 sheet (4 overlap ids + 6 rest ids), LLM files."""
    gl = ["Sports", "Economy", "Sports", "Politics"]
    rest_h = ["Sports", "Sports", "Economy", "Economy", "Health", "Other"]
    ov_rows = [{"id": f"o{i}", "date": "2026-08-16", "hour": "", "source_file": "x", "sentence_text": f"t{i}",
                "annotator_2_label": gl[i] if overlap_labelled else ""} for i in range(4)]
    a1_rows = [{"id": f"o{i}", "date": "2026-08-16", "hour": "", "source_file": "x", "sentence_text": f"t{i}", "annotator_1_label": "Other"}
               for i in range(4)]
    a1_rows += [{"id": f"r{i}", "date": "2026-08-28", "hour": "", "source_file": "x", "sentence_text": f"u{i}",
                 "annotator_1_label": rest_h[i] if rest_labelled else ""} for i in range(6)]
    write_csv(tmp_path / "overlap.csv", ov_rows, list(ov_rows[0]))
    write_csv(tmp_path / "a1.csv", a1_rows, list(a1_rows[0]))
    llm_ov = ["Sports", "Economy", "Politics", "Politics"]            # agrees with the human on 3 of 4
    llm_rest = ["Sports", "Economy", "Economy", "Economy", "Health", "Other"]   # agrees on 5 of 6
    write_csv(tmp_path / "llm_ov.csv", [{"id": f"o{i}", "llm_label": llm_ov[i]} for i in range(4)], ["id", "llm_label"])
    write_csv(tmp_path / "llm_rest.csv", [{"id": f"r{i}", "llm_label": llm_rest[i]} for i in range(6)], ["id", "llm_label"])
    return {"overlap_sheet": str(tmp_path / "overlap.csv"), "overlap_col": "annotator_2_label",
            "rest_sheet": str(tmp_path / "a1.csv"), "rest_col": "annotator_1_label",
            "llm_overlap": str(tmp_path / "llm_ov.csv"), "llm_rest": str(tmp_path / "llm_rest.csv")}


def test_agreement_end_to_end_two_groups_named_human_vs_llm(tmp_path):
    paths = _fixture(tmp_path)
    code, out = agreement_eval.run(paths, str(tmp_path / "res"), resamples=100)
    assert code == 0 and os.path.basename(out).startswith("human_vs_llm_agreement_")
    d = load(out)
    assert d["name"] == "human_vs_llm_agreement" and d["seed"] == cfg.SEED
    r = d["results"]
    assert r["output_name"] == "human_vs_llm_agreement" and "human_vs_llm_agreement" in r["what_this_is"]
    g1, g2 = r["groups"]["overlap_human_from_scratch"], r["groups"]["rest_human_reviewed"]
    assert g1["n"] == 4 and g1["agree_count"] == 3 and g1["observed_agreement"] == 0.75
    assert g2["n"] == 6 and g2["agree_count"] == 5 and g2["observed_agreement"] == pytest.approx(5 / 6)
    assert "inflated" in g2["caveat"] and "independent of the LLM" in g1["caveat"]
    assert g1["confusion_matrix"]["counts"][cfg.genre_labels().index("Politics")][cfg.genre_labels().index("Politics")] == 1
    assert len(d["inputs"]) == 4 and all(i["sha256"] for i in d["inputs"])


def test_no_key_or_title_in_the_output_says_inter_annotator(tmp_path):
    paths = _fixture(tmp_path)
    _, out = agreement_eval.run(paths, str(tmp_path / "res"), resamples=50)
    d = load(out)
    keys = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                keys.append(k)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    assert not any("inter_annotator" in k or "inter-annotator" in k for k in keys)
    assert "human_vs_llm_agreement" in os.path.basename(out) and d["name"] == "human_vs_llm_agreement"


def test_exit_3_when_human_labels_empty_and_llm_files_are_not_opened(tmp_path, monkeypatch):
    paths = _fixture(tmp_path, overlap_labelled=False, rest_labelled=False)
    opened = []
    real_read = common.read_csv
    monkeypatch.setattr(common, "read_csv", lambda p: (opened.append(os.path.basename(p)), real_read(p))[1])
    code, out = agreement_eval.run(paths, str(tmp_path / "res"))
    assert code == 3 and out is None and not os.path.exists(tmp_path / "res")
    assert "llm_ov.csv" not in opened and "llm_rest.csv" not in opened            # LLM labels untouched without human labels


def test_one_group_can_run_when_only_the_overlap_is_labelled(tmp_path):
    paths = _fixture(tmp_path, overlap_labelled=True, rest_labelled=False)
    code, out = agreement_eval.run(paths, str(tmp_path / "res"), resamples=50)
    assert code == 0
    g = load(out)["results"]["groups"]
    assert g["overlap_human_from_scratch"]["n"] == 4
    assert g["rest_human_reviewed"]["status"].startswith("not computed: human labels not complete")


def test_label_outside_the_set_and_id_mismatch_are_refused(tmp_path):
    paths = _fixture(tmp_path)
    rows = common.read_csv(paths["overlap_sheet"])
    rows[0]["annotator_2_label"] = "Gossip"
    write_csv(paths["overlap_sheet"], rows, list(rows[0]))
    st = agreement_eval.gold_status(paths)
    assert st.rows["overlap_human_from_scratch"][0] is None and "outside the project label set" in st.rows["overlap_human_from_scratch"][1]
    paths2 = _fixture(tmp_path)
    write_csv(tmp_path / "llm_rest.csv", [{"id": "zz", "llm_label": "Sports"}], ["id", "llm_label"])
    assert agreement_eval.run(paths2, str(tmp_path / "res2"), resamples=20) == (2, None)


def test_the_real_agreement_run_is_never_started_by_the_test_suite():
    """The real evaluation opens the LLM label files; a person must start it, never pytest (no subprocess on the script)."""
    import glob
    needle = '"agreement_eval' + '.py"'                       # built in two pieces so this file does not match itself
    offenders = [os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "tests", "*.py"))
                 if needle in open(p, encoding="utf-8").read()]
    assert offenders == []


# =============================================================== --two-humans guard
def test_kappa_skipped_without_flag_and_labelled_inter_annotator_with_it(tmp_path, capsys):
    paths = _genre_fixture(tmp_path)
    code, out = genre_eval.run(paths, str(tmp_path / "r1"), systems=("baselines",))
    assert code == 0
    r = load(out)["results"]
    assert "inter_annotator_kappa" not in r and "kappa_annotator1_vs_annotator2" not in r
    assert "different person" in r["kappa_skipped"] and "--two-humans" in r["kappa_skipped"]
    assert "kappa skipped" in capsys.readouterr().out
    code, out2 = genre_eval.run(paths, str(tmp_path / "r2"), systems=("baselines",), two_humans=True)
    r2 = load(out2)["results"]
    k = r2["inter_annotator_kappa"]
    assert k["n_overlap"] == 10 and k["kappa"] == pytest.approx(0.0) and "different people" in k["assumption"]
    assert "kappa_skipped" not in r2
    assert load(out2)["extra"]["two_humans_flag"] is True and load(out)["extra"]["two_humans_flag"] is False


def test_two_humans_flag_exists_on_the_command_line():
    p = subprocess.run([sys.executable, os.path.join(ROOT, "eval", "genre_eval.py"), "--help"], cwd=ROOT, capture_output=True, text=True)
    assert "--two-humans" in p.stdout and "different people" in " ".join(p.stdout.split())


# =============================================================== committed store reports
COPIES = {"store_A_build_report.json": "store_A/build_report.json",
          "store_A_dedup_report.json": "store_A/dedup_report.json",
          "store_A_nodedup_build_report.json": "store_A_nodedup/build_report.json"}


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_store_report_copies_exist_and_parse():
    for name in COPIES:
        path = os.path.join(ROOT, "results", "store_reports", name)
        assert os.path.isfile(path), name
        json.load(open(path, encoding="utf-8"))


def test_store_report_copies_are_identical_to_the_originals_when_they_exist():
    checked = 0
    for name, original in COPIES.items():
        orig = os.path.join(ROOT, original)
        if os.path.isfile(orig):                                                    # originals are untracked and may be absent
            assert _sha(orig) == _sha(os.path.join(ROOT, "results", "store_reports", name)), name
            checked += 1
    assert checked in (0, 3)


def test_paper_comments_cite_the_copies_not_the_untracked_originals():
    text = open(os.path.join(ROOT, "paper", "draft.md"), encoding="utf-8").read()
    assert "results/store_reports/store_A_build_report.json" in text
    assert "results/store_reports/store_A_nodedup_build_report.json" in text
    assert "<!-- store_A/build_report.json" not in text and "<!-- store_A_nodedup/build_report.json" not in text


# =============================================================== S13: --only-overlap and wording
def test_only_overlap_skips_the_reviewed_group_and_never_opens_its_files(tmp_path, monkeypatch):
    paths = _fixture(tmp_path)
    opened = []
    real_read = common.read_csv
    monkeypatch.setattr(common, "read_csv", lambda p: (opened.append(os.path.basename(p)), real_read(p))[1])
    code, out = agreement_eval.run(paths, str(tmp_path / "res"), resamples=50, groups=("overlap_human_from_scratch",))
    assert code == 0
    d = load(out)
    assert list(d["results"]["groups"]) == ["overlap_human_from_scratch"]            # the other group is not reported
    assert "rest_human_reviewed" in d["results"]["groups_skipped"] and "not reported" in d["results"]["groups_skipped"]["rest_human_reviewed"]
    assert "llm_rest.csv" not in opened and "a1.csv" not in opened                   # neither its LLM file nor its human sheet is read
    assert [os.path.basename(i["path"]) for i in d["inputs"]] == ["overlap.csv", "llm_ov.csv"]


def test_only_overlap_does_not_need_the_reviewed_labels_to_exist(tmp_path):
    paths = _fixture(tmp_path, overlap_labelled=True, rest_labelled=False)
    code, out = agreement_eval.run(paths, str(tmp_path / "res"), resamples=50, groups=("overlap_human_from_scratch",))
    assert code == 0 and load(out)["results"]["groups"]["overlap_human_from_scratch"]["n"] == 4


def test_no_key_title_or_value_in_the_output_says_inter_annotator(tmp_path):
    paths = _fixture(tmp_path)
    for groups in (agreement_eval.GROUPS, ("overlap_human_from_scratch",)):
        _, out = agreement_eval.run(paths, str(tmp_path / ("res" + str(len(groups)))), resamples=50, groups=groups)
        text = json.dumps(load(out)).lower()
        assert "inter-annotator" not in text and "inter_annotator" not in text and "interannotator" not in text
        assert load(out)["name"] == "human_vs_llm_agreement"
