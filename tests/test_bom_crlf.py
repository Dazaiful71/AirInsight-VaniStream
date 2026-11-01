"""Excel-style CSV (UTF-8 with BOM, CRLF line endings) must be read correctly by the eval code. Synthetic files only."""
import csv
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "eval"))
sys.path.insert(0, ROOT)

import agreement_eval  # noqa: E402
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402
import genre_eval  # noqa: E402
from test_eval_metrics import _genre_fixture, load  # noqa: E402

BOM = b"\xef\xbb\xbf"


def write_excel_style(path, rows, fields):
    """Raw bytes exactly as Excel's 'CSV UTF-8' save: BOM, CRLF after every line including the last, no other tricks."""
    lines = [",".join(fields)] + [",".join(_cell(r[f]) for f in fields) for r in rows]
    with open(path, "wb") as f:
        f.write(BOM + ("\r\n".join(lines) + "\r\n").encode("utf-8"))


def _cell(v):
    v = str(v)
    return '"' + v.replace('"', '""') + '"' if any(c in v for c in ',"\n') else v


def test_synthetic_file_really_is_bom_plus_crlf(tmp_path):
    p = tmp_path / "x.csv"
    write_excel_style(p, [{"id": "a", "v": "Sports"}], ["id", "v"])
    raw = p.read_bytes()
    assert raw.startswith(BOM) and raw.count(b"\r\n") == 2 and raw.count(b"\n") == 2


def test_plain_utf8_would_misread_the_first_column_but_utf8_sig_does_not(tmp_path):
    p = tmp_path / "x.csv"
    write_excel_style(p, [{"id": "a", "v": "Sports"}], ["id", "v"])
    with open(p, newline="", encoding="utf-8") as f:
        assert csv.DictReader(f).fieldnames[0] == "﻿id"                       # the bug the BOM would cause
    rows = common.read_csv(str(p))
    assert list(rows[0]) == ["id", "v"] and rows[0]["id"] == "a"
    assert rows[0]["v"] == "Sports"                                                # no stray carriage return in the last column


def test_shared_reader_uses_utf8_sig_and_newline_empty():
    import inspect
    src = inspect.getsource(common.read_csv)
    assert 'encoding="utf-8-sig"' in src and 'newline=""' in src


def test_check_labelled_csv_accepts_a_bom_crlf_file(tmp_path):
    p = tmp_path / "g.csv"
    write_excel_style(p, [{"id": "1", "label": "same"}, {"id": "2", "label": "different"}], ["id", "label"])
    st = common.check_labelled_csv(str(p), "label", cfg.PAIR_LABELS)
    assert st.ok and [r["id"] for r in st.rows] == ["1", "2"]


def _overlap_bom_crlf(tmp_path):
    """The overlap sheet in the exact shape of the real one, with human labels typed in, saved Excel-style."""
    fields = ["id", "date", "hour", "source_file", "sentence_text", "annotator_2_label"]
    labels = ["Sports", "Economy", "Sports", "Politics"]
    rows = [{"id": f"o{i}", "date": "2026-08-16", "hour": "5", "source_file": "x.mp3",
             "sentence_text": f'sentence, with a comma and "quotes" {i}', "annotator_2_label": labels[i]} for i in range(4)]
    path = tmp_path / "overlap.csv"
    write_excel_style(path, rows, fields)
    return path


def test_agreement_eval_reads_a_bom_crlf_overlap_sheet(tmp_path):
    overlap = _overlap_bom_crlf(tmp_path)
    a1_fields = ["id", "date", "hour", "source_file", "sentence_text", "annotator_1_label"]
    a1_rows = [{"id": f"o{i}", "date": "2026-08-16", "hour": "", "source_file": "x", "sentence_text": "t", "annotator_1_label": "Other"}
               for i in range(4)]
    a1_rows += [{"id": f"r{i}", "date": "2026-08-28", "hour": "", "source_file": "x", "sentence_text": "u", "annotator_1_label": ""}
                for i in range(3)]                                                   # rest group left unlabelled
    write_excel_style(tmp_path / "a1.csv", a1_rows, a1_fields)
    write_excel_style(tmp_path / "llm_ov.csv", [{"id": f"o{i}", "llm_label": l} for i, l in
                                                enumerate(["Sports", "Economy", "Politics", "Politics"])], ["id", "llm_label"])
    write_excel_style(tmp_path / "llm_rest.csv", [{"id": "r0", "llm_label": "Sports"}], ["id", "llm_label"])
    paths = {"overlap_sheet": str(overlap), "overlap_col": "annotator_2_label", "rest_sheet": str(tmp_path / "a1.csv"),
             "rest_col": "annotator_1_label", "llm_overlap": str(tmp_path / "llm_ov.csv"), "llm_rest": str(tmp_path / "llm_rest.csv")}
    st = agreement_eval.gold_status(paths)
    assert st.ok and st.rows["overlap_human_from_scratch"][0] == {"o0": "Sports", "o1": "Economy", "o2": "Sports", "o3": "Politics"}
    assert st.rows["rest_human_reviewed"][0] is None                                # incomplete rest group is reported, not guessed
    code, out = agreement_eval.run(paths, str(tmp_path / "res"), resamples=50)
    assert code == 0
    g = load(out)["results"]["groups"]["overlap_human_from_scratch"]
    assert g["n"] == 4 and g["agree_count"] == 3 and g["observed_agreement"] == 0.75


def test_genre_eval_kappa_reads_a_bom_crlf_overlap_sheet(tmp_path):
    paths = _genre_fixture(tmp_path)
    rows = common.read_csv(paths["annotator2"])
    write_excel_style(paths["annotator2"], rows, ["id", "date", "hour", "source_file", "sentence_text", "annotator_2_label"])
    assert open(paths["annotator2"], "rb").read().startswith(BOM)
    code, out = genre_eval.run(paths, str(tmp_path / "res"), systems=("baselines",), two_humans=True)
    assert code == 0
    k = load(out)["results"]["inter_annotator_kappa"]
    assert k["n_overlap"] == 10 and k["kappa"] == pytest.approx(0.0)                 # same synthetic answer as with a plain file


def test_real_overlap_sheet_header_reads_as_id_without_touching_label_values():
    """Only the header row of the real file is read here; no label value is looked at."""
    path = cfg.GOLD_GENRE_ANNOTATOR2
    with open(path, newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    assert header[0] == "id" and "annotator_2_label" in header and "﻿" not in "".join(header)
