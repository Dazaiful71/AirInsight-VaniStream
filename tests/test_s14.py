"""genre_eval: --gold-sheet / --gold-col options and the val/test sentence index in the default paths. Synthetic data only."""
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "eval"))
sys.path.insert(0, ROOT)

import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402
import genre_eval  # noqa: E402
from test_eval_metrics import _genre_fixture, load, write_csv  # noqa: E402

FIELDS = ["id", "date", "hour", "source_file", "sentence_text"]


def _rename_label_column(paths, tmp_path, new_col, keep_old_empty=True):
    """Copy of the fixture gold sheet whose labels sit in `new_col` (the old annotator_1_label column left empty)."""
    rows = common.read_csv(paths["gold"])
    out = []
    for r in rows:
        d = {k: r[k] for k in FIELDS}
        d[new_col] = r["annotator_1_label"]
        if keep_old_empty:
            d["annotator_1_label"] = ""
        out.append(d)
    path = tmp_path / "other_sheet.csv"
    write_csv(path, out, list(out[0]))
    return {**paths, "gold": str(path), "gold_col": new_col}


# ------------------------------------------------------------------ defaults are unchanged
def test_default_paths_keep_the_old_sheet_and_column_and_add_the_sentence_index():
    p = genre_eval.default_paths()
    assert p["gold"] == cfg.GOLD_GENRE and p["gold_col"] == "annotator_1_label"
    assert p["sentence_index"] == cfg.GOLD_SENTENCE_INDEX
    assert p["annotator2"] == cfg.GOLD_GENRE_ANNOTATOR2 and p["store_db"] == cfg.STORE_DB


def test_old_style_paths_without_gold_col_behave_as_before(tmp_path):
    paths = _genre_fixture(tmp_path)                                  # no gold_col, no sentence_index: the previous call shape
    assert "gold_col" not in paths
    code, out = genre_eval.run(paths, str(tmp_path / "res"), systems=("baselines",))
    assert code == 0
    g = load(out)["results"]["gold_sheet"]
    assert g["label_column"] == "annotator_1_label" and g["n"] == 20 and g["support_by_class"] == {"Sports": 10, "Economy": 10}


def test_default_gold_sheet_still_exits_3_while_it_is_unlabelled(tmp_path):
    paths = _genre_fixture(tmp_path)
    rows = common.read_csv(paths["gold"])
    for r in rows:
        r["annotator_1_label"] = ""
    write_csv(paths["gold"], rows, list(rows[0]))
    assert genre_eval.run(paths, str(tmp_path / "res"), systems=("baselines",)) == (3, None)
    assert not os.path.exists(tmp_path / "res")


# ------------------------------------------------------------------ --gold-sheet / --gold-col
def test_gold_col_selects_the_label_column(tmp_path):
    base = _genre_fixture(tmp_path)
    paths = _rename_label_column(base, tmp_path, "annotator_2_label")
    # with the old column the sheet counts as unlabelled ...
    assert genre_eval.run({**paths, "gold_col": "annotator_1_label"}, str(tmp_path / "r0"), systems=("baselines",)) == (3, None)
    # ... with the chosen column it is scored, with the same numbers as the original sheet
    code, out = genre_eval.run(paths, str(tmp_path / "r1"), systems=("baselines",))
    assert code == 0
    r = load(out)["results"]
    assert r["gold_sheet"]["label_column"] == "annotator_2_label" and r["gold_sheet"]["path"].endswith("other_sheet.csv")
    assert r["gold_sheet"]["n"] == 20
    assert r["systems"]["tfidf_logreg_train_silver"]["all_gold"]["macro_f1"] == pytest.approx(1.0)
    maj = r["systems"]["majority_class_train_silver"]["all_gold"]
    assert maj["macro_f1"] == pytest.approx((2 / 3 + 0) / 2)
    assert "kappa_skipped" in r and "inter_annotator_kappa" not in r                      # no flag, no kappa


def test_two_humans_is_refused_when_the_gold_column_is_the_second_annotator_column(tmp_path):
    paths = _rename_label_column(_genre_fixture(tmp_path), tmp_path, "annotator_2_label")
    code, out = genre_eval.run(paths, str(tmp_path / "res"), systems=("baselines",), two_humans=True)
    assert code == 0
    assert load(out)["results"]["inter_annotator_kappa"]["status"].startswith("not computed: the gold column is the second-annotator")


def test_gold_col_validates_labels_in_the_chosen_column(tmp_path):
    paths = _rename_label_column(_genre_fixture(tmp_path), tmp_path, "annotator_2_label")
    rows = common.read_csv(paths["gold"])
    rows[0]["annotator_2_label"] = "Gossip"
    write_csv(paths["gold"], rows, list(rows[0]))
    st = genre_eval.gold_status(paths)
    assert not st.ok and "Gossip" in st.message and "annotator_2_label" in st.message


def test_command_line_options_map_into_the_paths(monkeypatch):
    seen = {}

    def fake_run(paths=None, **kw):
        seen["paths"], seen["kw"] = paths, kw
        return 0, None
    monkeypatch.setattr(genre_eval, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["genre_eval.py", "--gold-sheet", "some/sheet.csv", "--gold-col", "annotator_2_label",
                                      "--systems", "baselines,fast,zero-shot"])
    assert genre_eval.main() == 0
    assert seen["paths"]["gold"] == "some/sheet.csv" and seen["paths"]["gold_col"] == "annotator_2_label"
    assert seen["paths"]["sentence_index"] == cfg.GOLD_SENTENCE_INDEX and seen["kw"]["systems"] == ("baselines", "fast", "zero-shot")
    assert seen["kw"]["two_humans"] is False and seen["kw"]["finetune"] is None          # no --two-humans, no training
    monkeypatch.setattr(sys, "argv", ["genre_eval.py"])
    genre_eval.main()
    assert seen["paths"]["gold"] == cfg.GOLD_GENRE and seen["paths"]["gold_col"] == "annotator_1_label"


# ------------------------------------------------------------------ leakage filter covers the val/test sentence index
def _add_train_row(db, text, genre="Sports"):
    con = sqlite3.connect(db)
    con.execute("INSERT INTO segments (text, genre, split) VALUES (?, ?, 'train')", (text, genre))
    con.commit()
    con.close()


def test_leakage_filter_uses_the_sentence_index_from_the_paths(tmp_path):
    paths = _genre_fixture(tmp_path)
    # a val/test sentence that is NOT in the gold sheet, and a train-day segment with the same text apart from case/punctuation
    write_csv(tmp_path / "index.csv", [{"id": "v1", "date": "2026-08-16", "hour": "", "source_file": "x", "position": "1", "split": "val",
                                        "text": "Cricket final tomorrow in Delhi."}],
              ["id", "date", "hour", "source_file", "position", "split", "text"])
    _add_train_row(paths["store_db"], "cricket FINAL tomorrow in delhi")
    with_index = {**paths, "sentence_index": str(tmp_path / "index.csv")}
    code, out = genre_eval.run(with_index, str(tmp_path / "r1"), systems=("baselines",))
    t = load(out)["results"]["baseline_training_data"]
    assert t["n_removed_identical_to_gold_or_valtest"] == 1 and t["n_removed_identical_to_gold_sheet_only"] == 0
    assert t["n_train_day_segments"] == 9 and t["n_training_examples"] == 8
    # without the index (the old call shape) only gold-sheet texts are used, so the row stays
    code, out2 = genre_eval.run(paths, str(tmp_path / "r2"), systems=("baselines",))
    t2 = load(out2)["results"]["baseline_training_data"]
    assert t2["n_removed_identical_to_gold_or_valtest"] == 0 and t2["n_training_examples"] == 9


def test_genre_eval_and_finetune_use_the_same_leakage_inputs():
    import finetune_genre as ft
    import inspect
    assert genre_eval.default_paths()["sentence_index"] == cfg.GOLD_SENTENCE_INDEX
    assert "cfg.GOLD_SENTENCE_INDEX" in inspect.getsource(ft.main)                        # finetune_genre.py passes the same index


def test_sentence_index_is_part_of_the_result_input_hashes(tmp_path):
    paths = _genre_fixture(tmp_path)
    write_csv(tmp_path / "index.csv", [{"id": "v1", "date": "d", "hour": "", "source_file": "x", "position": "1", "split": "val",
                                        "text": "some other text"}], ["id", "date", "hour", "source_file", "position", "split", "text"])
    _, out = genre_eval.run({**paths, "sentence_index": str(tmp_path / "index.csv")}, str(tmp_path / "res"), systems=("baselines",))
    names = [os.path.basename(i["path"]) for i in load(out)["inputs"]]
    assert "index.csv" in names
