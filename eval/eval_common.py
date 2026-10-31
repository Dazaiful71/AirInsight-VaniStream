"""Helpers shared by the eval scripts: result writer, gold loaders, exit codes."""
import csv
import datetime
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_config as cfg  # noqa: E402

EXIT_OK = 0
EXIT_NO_GOLD = 3            # gold file missing or not labelled yet: nothing was evaluated
EXIT_NOT_IMPLEMENTED = 4    # gold is labelled but the metric code has not been written yet (stub)


def rel(path: str) -> str:
    """Path relative to the project root; the absolute path if it is on another drive."""
    try:
        return os.path.relpath(path, cfg.ROOT)
    except ValueError:
        return path


# ---------------------------------------------------------------- result writer
def file_sha256(path: str):
    """SHA-256 of a file, or None if it does not exist."""
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_commit():
    """HEAD commit if the project is a git repository, else None (it is not one today)."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cfg.ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def write_result(name: str, results: dict, inputs: list, seed: int = cfg.SEED, results_dir: str = None,
                 extra: dict = None) -> str:
    """Write results/<name>_<UTC timestamp>.json with the results, the seed, and the hash of every input file.

    inputs: file paths that fed the result (gold file, store DB, ...). A missing input is recorded with sha256 null.
    Returns the path written.
    """
    results_dir = results_dir or cfg.RESULTS_DIR
    os.makedirs(results_dir, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "name": name,
        "timestamp_utc": now.isoformat(timespec="seconds"),
        "seed": seed,
        "git_commit": git_commit(),
        "inputs": [{"path": rel(p), "sha256": file_sha256(p)} for p in inputs],
        "results": results,
    }
    if extra:
        payload["extra"] = extra
    path = os.path.join(results_dir, f"{name}_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------- statistics
def bootstrap_indices(n: int, resamples: int = cfg.BOOTSTRAP_RESAMPLES, seed: int = cfg.SEED):
    """(resamples, n) integer matrix of item indices drawn with replacement; same seed -> same matrix."""
    import numpy as np
    return np.random.default_rng(seed).integers(0, n, size=(resamples, n))


def percentile_ci(values, level: float = 0.95):
    """Percentile interval of a 1-D sample of bootstrap statistics; NaNs are ignored. None if nothing is defined."""
    import numpy as np
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if v.size == 0:
        return None
    lo, hi = np.percentile(v, [100 * (1 - level) / 2, 100 * (1 + level) / 2])
    return [float(lo), float(hi)]


def bootstrap_meta(n_items: int, resamples: int = cfg.BOOTSTRAP_RESAMPLES, seed: int = cfg.SEED) -> dict:
    return {"method": "percentile bootstrap over items, 95% CI", "resamples": resamples, "seed": seed, "n_items": n_items}


def save_or_report(name, status_or_error, compute, inputs, results_dir=None):
    """Shared driver: (exit code, result path). Exit 3 without gold; 2 when a non-gold prerequisite is missing."""
    if not status_or_error.ok:
        print(f"[{name}] NO GOLD - nothing evaluated. {status_or_error.message}")
        return EXIT_NO_GOLD, None
    try:
        results, extra = compute()
    except PrerequisiteMissing as e:
        print(f"[{name}] CANNOT RUN: {e}")
        return 2, None
    path = write_result(name, results, inputs, results_dir=results_dir, extra=extra)
    print(f"[{name}] wrote {path}")
    return EXIT_OK, path


class PrerequisiteMissing(Exception):
    """A non-gold input (store, transcripts, audio) is missing; the message says which."""


# ---------------------------------------------------------------- gold loaders
def read_csv(path: str) -> list:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class GoldStatus:
    """Result of checking a gold file: ok flag plus a one-paragraph human message."""

    def __init__(self, ok: bool, message: str, rows=None):
        self.ok, self.message, self.rows = ok, message, rows

    def __iter__(self):
        return iter((self.ok, self.message))


def check_labelled_csv(path: str, label_col: str, allowed=None, what: str = "gold file") -> GoldStatus:
    """The file must exist and EVERY row must carry an allowed label."""
    rel_path = rel(path)
    if not os.path.isfile(path):
        return GoldStatus(False, f"{what} is missing: {rel_path}")
    rows = read_csv(path)
    if not rows:
        return GoldStatus(False, f"{what} has no rows: {rel_path}")
    labelled = [r for r in rows if (r.get(label_col) or "").strip()]
    if len(labelled) < len(rows):
        return GoldStatus(False, f"{what} is not fully labelled yet: {len(labelled)} of {len(rows)} rows have "
                                 f"'{label_col}' filled in ({rel_path}). Label every row first.")
    if allowed is not None:
        bad = sorted({r[label_col].strip() for r in rows} - set(allowed))
        if bad:
            return GoldStatus(False, f"{what} has labels outside the allowed set {sorted(allowed)}: {bad[:5]} ({rel_path})")
    return GoldStatus(True, f"{what}: {len(rows)} labelled rows ({rel_path})", rows)


def run_stub(name: str, status: GoldStatus) -> int:
    """Shared behaviour of the stubs: stop clearly without gold; with gold, say the metric code is still TODO."""
    if not status.ok:
        print(f"[{name}] NO GOLD - nothing evaluated. {status.message}")
        return EXIT_NO_GOLD
    print(f"[{name}] gold found ({status.message}), but the {name} metrics are not implemented yet (stub). "
          f"No result file written.")
    return EXIT_NOT_IMPLEMENTED
