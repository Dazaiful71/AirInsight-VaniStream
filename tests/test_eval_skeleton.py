"""A5 / run_all skeleton: stubs stop cleanly without gold, results carry provenance, run_all is resumable."""
import csv
import glob
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "eval"))
sys.path.insert(0, ROOT)

import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402
import run_all  # noqa: E402

STUBS = ["genre_eval", "dedup_eval", "retrieval_eval", "asr_eval"]


def _results_snapshot():
    return sorted(glob.glob(os.path.join(cfg.RESULTS_DIR, "*")))


@pytest.mark.parametrize("stub", STUBS)
def test_stub_exits_with_no_gold_code_and_message(stub):
    before = _results_snapshot()
    p = subprocess.run([sys.executable, os.path.join(ROOT, "eval", stub + ".py")], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == common.EXIT_NO_GOLD
    assert "NO GOLD" in p.stdout and "Traceback" not in p.stderr
    assert _results_snapshot() == before, "a stub must not write a result file"


def _write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_check_labelled_csv(tmp_path):
    p = str(tmp_path / "g.csv")
    assert not common.check_labelled_csv(str(tmp_path / "missing.csv"), "label").ok
    _write_csv(p, [{"id": "1", "label": ""}, {"id": "2", "label": "same"}], ["id", "label"])
    st = common.check_labelled_csv(p, "label", cfg.PAIR_LABELS)
    assert not st.ok and "1 of 2" in st.message
    _write_csv(p, [{"id": "1", "label": "same"}, {"id": "2", "label": "bogus"}], ["id", "label"])
    assert not common.check_labelled_csv(p, "label", cfg.PAIR_LABELS).ok
    _write_csv(p, [{"id": "1", "label": "same"}, {"id": "2", "label": "different"}], ["id", "label"])
    assert common.check_labelled_csv(p, "label", cfg.PAIR_LABELS).ok


def test_labelled_gold_reaches_the_stub_not_implemented_code(tmp_path, monkeypatch):
    p = str(tmp_path / "g.csv")
    _write_csv(p, [{"id": "1", "label": "same"}], ["id", "label"])
    st = common.check_labelled_csv(p, "label", cfg.PAIR_LABELS)
    assert common.run_stub("dedup_eval", st) == common.EXIT_NOT_IMPLEMENTED


def test_write_result_records_seed_timestamp_and_input_hash(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("x", encoding="utf-8")
    path = common.write_result("unit_example", {"note": "text only"}, [str(inp), str(tmp_path / "absent")], seed=7,
                               results_dir=str(tmp_path / "res"))
    d = json.load(open(path, encoding="utf-8"))
    assert os.path.basename(path).startswith("unit_example_") and path.endswith("Z.json")
    assert d["seed"] == 7 and d["timestamp_utc"].endswith("+00:00") and "git_commit" in d
    assert d["inputs"][0]["sha256"] == common.file_sha256(str(inp)) and len(d["inputs"][0]["sha256"]) == 64
    assert d["inputs"][1]["sha256"] is None
    assert d["results"] == {"note": "text only"}


def test_config_points_to_the_gold_files_and_split_names():
    assert cfg.SEED == 42 and cfg.SPLITS == ("train", "val", "test") and cfg.GOLD_SPLITS == ("val", "test")
    for p in (cfg.GOLD_GENRE, cfg.GOLD_PAIRS, cfg.GOLD_QUERIES):
        assert os.path.isfile(p), p
    assert "news_store.db" in cfg.STORE_DB and os.path.basename(os.path.dirname(cfg.STORE_DB)) == "store_A"


# ---------------------------------------------------------------- run_all
def _spec(tmp_path, code=0, gold=None, inputs=None, marker=None):
    return {"command": [sys.executable, "-c", f"raise SystemExit({code})"], "inputs": inputs or [],
            "done_marker": marker, "gold": gold}


def test_run_all_skips_done_stage_and_reruns_when_input_changes(tmp_path):
    sp = str(tmp_path / "state.json")
    inp = tmp_path / "in.txt"
    inp.write_text("a", encoding="utf-8")
    spec = _spec(tmp_path, inputs=[str(inp)])
    state = {}
    assert run_all.run_stage("s", spec, state, False, sp) == 0 and state["s"]["status"] == "done"
    assert run_all.is_done("s", spec, state)
    assert run_all.run_stage("s", spec, state, False, sp) == 0          # skipped (no subprocess needed)
    inp.write_text("b", encoding="utf-8")
    assert not run_all.is_done("s", spec, state)                        # input changed -> not done any more
    marker = tmp_path / "marker"
    spec2 = _spec(tmp_path, marker=str(marker))
    state2 = {}
    run_all.run_stage("m", spec2, state2, False, sp)
    assert not run_all.is_done("m", spec2, state2)                      # done marker file missing
    marker.write_text("x")
    assert run_all.is_done("m", spec2, state2)


def test_run_all_stops_at_missing_gold_and_does_not_run_the_command(tmp_path, capsys):
    sp = str(tmp_path / "state.json")
    ran = tmp_path / "ran"
    spec = {"command": [sys.executable, "-c", f"open(r'{ran}', 'w').write('x')"], "inputs": [], "done_marker": None,
            "gold": lambda: common.GoldStatus(False, "labels missing for test")}
    state = {}
    assert run_all.run_stage("g", spec, state, False, sp) == common.EXIT_NO_GOLD
    assert not ran.exists() and state["g"]["status"] == "blocked_no_gold"
    out = capsys.readouterr().out
    assert "STOP" in out and "labels missing for test" in out


def test_run_all_failed_stage_is_not_marked_done(tmp_path):
    sp = str(tmp_path / "state.json")
    state = {}
    code = run_all.run_stage("f", _spec(tmp_path, code=4), state, False, sp)
    assert code == 4 and state["f"]["status"] == "failed_exit_4" and not run_all.is_done("f", _spec(tmp_path), state)


def test_run_all_cli_stops_at_first_missing_gold_with_stage_genre():
    """Real stage list: with no labelled gold, --stage genre stops with code 3 and a message; state file not required."""
    state_before = os.path.isfile(run_all.STATE_PATH)
    p = subprocess.run([sys.executable, os.path.join(ROOT, "run_all.py"), "--stage", "genre"], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == common.EXIT_NO_GOLD and "STOP" in p.stdout
    lst = subprocess.run([sys.executable, os.path.join(ROOT, "run_all.py"), "--list"], cwd=ROOT, capture_output=True, text=True)
    assert lst.returncode == 0 and all(s in lst.stdout for s in run_all.STAGES)
    if not state_before and os.path.isfile(run_all.STATE_PATH):
        os.remove(run_all.STATE_PATH)   # keep results/ clean when this test created the state file
