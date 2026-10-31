"""Transcribe the WER bulletins with several Whisper sizes and cache the hypotheses (no references needed). Resumable.

  .venv_gpu/Scripts/python.exe eval/asr_transcribe.py --models tiny base          # the real run (laptop or cluster)
  .venv_gpu/Scripts/python.exe eval/asr_transcribe.py --smoke                     # ONE bulletin, first model only

Hypotheses go to data/asr_hyp/<model>/<stem>.txt; a file that already has a non-empty hypothesis is skipped.
The `small` hypotheses are the option A transcripts and are not recreated here unless --include-small is given.
asr_eval.py reads these files; this script never computes WER.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asr_eval  # noqa: E402
import eval_config as cfg  # noqa: E402


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
    t0 = time.time()
    for m in models:
        for c in cands:
            audio = os.path.join(cfg.SAMPLE_DIR, "audio", c["date"], c["stem"] + ".mp3")
            cache = os.path.join(cfg.ASR_HYP_DIR, m, c["stem"] + ".txt")
            if not os.path.isfile(audio):
                print(f"[asr_transcribe] audio missing, skipped: {audio}")
                continue
            done = os.path.isfile(cache) and os.path.getsize(cache) > 0
            asr_eval.transcribe_cached(audio, m, cache, a.device)
            print(f"[asr_transcribe] {m} {c['stem']}: {'cached, skipped' if done else 'transcribed'}")
    print(f"[asr_transcribe] finished in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
