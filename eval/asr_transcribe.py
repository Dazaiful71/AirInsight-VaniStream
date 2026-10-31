"""Transcribe the WER bulletins with several Whisper sizes and cache the hypotheses (no references needed). Resumable.

  .venv_gpu/Scripts/python.exe eval/asr_transcribe.py --models tiny base          # the real run (laptop or cluster)
  .venv_gpu/Scripts/python.exe eval/asr_transcribe.py --smoke                     # ONE bulletin, first model only

Hypotheses go to data/asr_hyp/<model>/<stem>.txt; a file that already has a non-empty hypothesis is skipped.
Every transcription that actually runs is logged (audio duration, wall seconds, real-time factor, device, GPU memory peak
sampled with nvidia-smi every 0.5 s) to data/asr_hyp/transcribe_log.json, merged across runs. The first file of each model
includes model load / GPU warm-up in its time. The `small` hypotheses are the option A transcripts and are not recreated
here unless --include-small is given. asr_eval.py reads these files; this script never computes WER.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asr_eval  # noqa: E402
import eval_config as cfg  # noqa: E402

LOG_PATH = os.path.join(cfg.ASR_HYP_DIR, "transcribe_log.json")


def gpu_used_mib():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10)
        return int(out.stdout.strip().splitlines()[0]) if out.returncode == 0 else None
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


class VramSampler:
    """Background sampler of GPU memory used (MiB); .peak is the maximum seen, .baseline the value before starting."""

    def __init__(self, interval=0.5):
        self.interval, self.peak, self.baseline = interval, None, gpu_used_mib()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            v = gpu_used_mib()
            if v is not None and (self.peak is None or v > self.peak):
                self.peak = v
            self._stop.wait(self.interval)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        self._t.join(timeout=5)


def load_log():
    return json.load(open(LOG_PATH, encoding="utf-8")) if os.path.isfile(LOG_PATH) else {"runs": []}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["tiny", "base"])
    ap.add_argument("--smoke", action="store_true", help="one bulletin, first model only (5-minute job)")
    ap.add_argument("--include-small", action="store_true")
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()
    models = list(a.models) + (["small"] if a.include_small and "small" not in a.models else [])
    cands = asr_eval.wer_candidates(cfg.SAMPLE_CONFIG)
    if a.smoke:
        models, cands = models[:1], cands[:1]
    log = load_log()
    t0 = time.time()
    for m in models:
        with VramSampler() as vram:
            entries = []
            for i, c in enumerate(cands):
                audio = os.path.join(cfg.SAMPLE_DIR, "audio", c["date"], c["stem"] + ".mp3")
                cache = os.path.join(cfg.ASR_HYP_DIR, m, c["stem"] + ".txt")
                if not os.path.isfile(audio):
                    print(f"[asr_transcribe] audio missing, skipped: {audio}")
                    continue
                st = {}
                asr_eval.transcribe_cached(audio, m, cache, a.device, stats=st)
                if st:
                    entries.append({"model": m, "stem": c["stem"], "role": c["role"], "first_file_of_model_run": not entries, **st})
                    print(f"[asr_transcribe] {m} {c['stem']}: audio {st['duration_s']} s, {st['seconds']} s, RTF {st['rtf']}, {st['device']}/{st['compute_type']}")
                else:
                    print(f"[asr_transcribe] {m} {c['stem']}: cached, skipped")
        if entries:
            log["runs"].append({"model": m, "files": entries, "gpu_memory_used_mib": {"baseline_before": vram.baseline, "peak_during_run": vram.peak},
                                "note": "peak is total GPU memory in use (nvidia-smi, 0.5 s sampling), not process-only; the first file includes model load"})
            os.makedirs(cfg.ASR_HYP_DIR, exist_ok=True)
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(log, f, indent=2)
    print(f"[asr_transcribe] finished in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
