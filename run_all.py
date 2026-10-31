"""run_all.py - resumable pipeline skeleton: ingest -> genre eval -> dedup eval -> retrieval eval -> ASR eval.

  .venv_gpu/Scripts/python.exe run_all.py --list
  .venv_gpu/Scripts/python.exe run_all.py --stage ingest
  .venv_gpu/Scripts/python.exe run_all.py --stage all [--force] [--classifier fast]

State is kept in results/run_all_state.json. A stage is skipped when it is marked done AND its input files still have
the same SHA-256 AND its output marker still exists (use --force to rerun). An eval stage whose gold labels are missing
stops the whole run with a clear message (exit code 3); later stages are not attempted. The eval stages are stubs
today: they only become 'done' when the eval script itself exits 0.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "eval"))
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402

STATE_PATH = os.path.join(cfg.RESULTS_DIR, "run_all_state.json")
STAGES = ["ingest", "genre", "dedup", "retrieval", "asr"]


def stage_defs(args):
    import asr_eval
    import dedup_eval
    import genre_eval
    import retrieval_eval
    return {
        "ingest": {
            "command": [sys.executable, os.path.join(ROOT, "build_store_A.py"), "--classifier", args.classifier],
            "inputs": [cfg.SAMPLE_METADATA, cfg.SAMPLE_CONFIG],
            "done_marker": cfg.STORE_BUILD_REPORT,
            "gold": None,
        },
        "genre": {"command": [sys.executable, os.path.join(ROOT, "eval", "genre_eval.py")],
                  "inputs": [cfg.GOLD_GENRE, cfg.STORE_DB], "done_marker": None, "gold": genre_eval.gold_status},
        "dedup": {"command": [sys.executable, os.path.join(ROOT, "eval", "dedup_eval.py")],
                  "inputs": [cfg.GOLD_PAIRS, cfg.GOLD_PAIRS_KEY], "done_marker": None, "gold": dedup_eval.gold_status},
        "retrieval": {"command": [sys.executable, os.path.join(ROOT, "eval", "retrieval_eval.py")],
                      "inputs": [cfg.GOLD_QUERIES, cfg.STORE_DB, cfg.STORE_INDEX], "done_marker": None,
                      "gold": retrieval_eval.gold_status},
        "asr": {"command": [sys.executable, os.path.join(ROOT, "eval", "asr_eval.py")],
                "inputs": [cfg.SAMPLE_METADATA], "done_marker": None, "gold": asr_eval.gold_status},
    }


def load_state(path=STATE_PATH):
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state, path=STATE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def input_hashes(paths):
    return {common.rel(p): common.file_sha256(p) for p in paths}


def is_done(name, spec, state):
    rec = state.get(name)
    if not rec or rec.get("status") != "done":
        return False
    if spec.get("done_marker") and not os.path.isfile(spec["done_marker"]):
        return False
    return rec.get("inputs") == input_hashes(spec["inputs"])


def run_stage(name, spec, state, force, state_path=STATE_PATH):
    """Returns 0 ok/skipped, 3 gold missing, otherwise the failing exit code."""
    if not force and is_done(name, spec, state):
        print(f"[{name}] already done (inputs unchanged) - skipping")
        return 0
    if spec["gold"] is not None:
        status = spec["gold"]()
        if not status.ok:
            print(f"[{name}] STOP: gold labels are missing, so this stage and every later one were not run.\n"
                  f"         {status.message}")
            state[name] = {"status": "blocked_no_gold", "message": status.message}
            save_state(state, state_path)
            return common.EXIT_NO_GOLD
    print(f"[{name}] running: {' '.join(os.path.basename(c) if i else c for i, c in enumerate(spec['command']))}")
    code = subprocess.run(spec["command"], cwd=ROOT).returncode
    if code == 0:
        state[name] = {"status": "done", "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                       "inputs": input_hashes(spec["inputs"])}
    else:
        state[name] = {"status": f"failed_exit_{code}"}
        note = " (stub: gold is labelled but the metric code is not written yet)" if code == common.EXIT_NOT_IMPLEMENTED else ""
        print(f"[{name}] STOP: exit code {code}{note}")
    save_state(state, state_path)
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=STAGES + ["all"], help="stage to run, or 'all' in order")
    ap.add_argument("--force", action="store_true", help="rerun even if marked done")
    ap.add_argument("--classifier", choices=["fast", "zero-shot", "finetuned"], default="fast",
                    help="genre backend for the ingest stage (default fast: zero-shot BART is about 10x slower on CPU)")
    ap.add_argument("--list", action="store_true", help="show stage status and exit")
    args = ap.parse_args()

    specs = stage_defs(args)
    state = load_state()
    if args.list or not args.stage:
        for n in STAGES:
            gold = specs[n]["gold"]
            g = "" if gold is None else ("gold ok" if gold().ok else "gold MISSING")
            print(f"{n:10s} {'done' if is_done(n, specs[n], state) else state.get(n, {}).get('status', 'not run'):22s} {g}")
        return 0
    todo = STAGES if args.stage == "all" else [args.stage]
    for n in todo:
        code = run_stage(n, specs[n], state, args.force)
        if code != 0:
            return code
    print("requested stages finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
