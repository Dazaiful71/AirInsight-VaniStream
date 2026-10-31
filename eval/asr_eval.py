"""ASR eval (A9): word error rate of Whisper tiny / base / small against hand-corrected reference transcripts.

References: data/gold/asr_refs/<audio file stem>.txt for every bulletin listed in config/sample_config.json
(pilot_plan_s4.asr_wer_candidates_from_option_A_test_days). They must be corrected by a person from the audio, never
copied from a Whisper output. Missing references -> exit 3 with a message.
Hypotheses: small = the option A transcripts (data/sample_A/text, produced with faster-whisper small, cuda, float16);
tiny and base = data/asr_hyp/<model>/<stem>.txt, transcribed on demand with the same settings and cached there.

Normalisation (applied identically to reference and hypothesis, documented in every result file):
  Unicode NFKC, lowercase; apostrophes deleted (india's -> indias); hyphens/dashes -> space; thousands commas inside
  numbers deleted (1,000 -> 1000); every other punctuation or symbol character -> space (so "5%" -> "5");
  decimals keep their point (3.5). NUMBERS ARE NOT CONVERTED between digits and words, so "three" vs "3" counts as an
  error; this is a known limitation and makes WER slightly pessimistic wherever the references and Whisper disagree on style.
WER = (S + D + I) / N_ref from a Levenshtein word alignment (own implementation, no jiwer needed; ties prefer
match/substitution, then deletion, then insertion, so S/D/I split may differ from other tools while WER is identical).
Overall WER pools the counts over files. Feeds: results/asr_eval_*.json -> ASR table (see eval/README.md).
"""
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402

NAME = "asr_eval"
NORMALISATION = ("NFKC + lowercase; apostrophes deleted; hyphens/dashes -> space; commas inside numbers deleted; other "
                 "punctuation/symbols -> space; decimal points kept; numbers NOT converted between digits and words")


def default_paths() -> dict:
    return {"refs_dir": cfg.GOLD_ASR_DIR, "hyp_dir": cfg.ASR_HYP_DIR, "sample_text_dir": cfg.SAMPLE_TEXT_DIR,
            "sample_dir": cfg.SAMPLE_DIR, "sample_config": cfg.SAMPLE_CONFIG}


def wer_candidates(sample_config: str) -> list:
    plan = json.load(open(sample_config, encoding="utf-8"))["pilot_plan_s4"]
    return [{"stem": os.path.splitext(c["file"])[0], "date": c["date"], "role": c["role"]}
            for c in plan["asr_wer_candidates_from_option_A_test_days"]]


def gold_status(paths=None):
    p = paths or default_paths()
    cands = wer_candidates(p["sample_config"])
    missing = []
    for c in cands:
        ref = os.path.join(p["refs_dir"], c["stem"] + ".txt")
        if not os.path.isfile(ref) or not open(ref, encoding="utf-8").read().strip():
            missing.append(c["stem"] + ".txt")
    if missing:
        return common.GoldStatus(False, f"{len(missing)} of {len(cands)} hand-corrected reference transcripts are missing "
                                        f"in {common.rel(p['refs_dir'])}: {missing}")
    return common.GoldStatus(True, f"{len(cands)} reference transcripts present", cands)


# ---------------------------------------------------------------- metric
def normalise(text: str) -> list:
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"(?<=\d),(?=\d)", "", t)
    t = t.replace("'", "").replace("’", "")
    t = re.sub(r"[-‐-―_]", " ", t)
    return re.findall(r"\d+\.\d+|\w+", t)


def align_counts(ref: list, hyp: list) -> dict:
    """Word-level Levenshtein alignment -> substitutions, deletions, insertions, correct words and WER."""
    n, m = len(ref), len(hyp)
    dist = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dist[i][0] = i
    for j in range(1, m + 1):
        dist[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dist[i][j] = min(dist[i - 1][j - 1] + cost, dist[i - 1][j] + 1, dist[i][j - 1] + 1)
    i, j, s, d, ins, c = n, m, 0, 0, 0, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dist[i][j] == dist[i - 1][j - 1] + (0 if ref[i - 1] == hyp[j - 1] else 1):
            if ref[i - 1] == hyp[j - 1]:
                c += 1
            else:
                s += 1
            i, j = i - 1, j - 1
        elif i > 0 and dist[i][j] == dist[i - 1][j] + 1:
            d += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    return {"ref_words": n, "hyp_words": m, "substitutions": s, "deletions": d, "insertions": ins, "correct": c,
            "wer": (s + d + ins) / n if n else None}


def pool(counts: list) -> dict:
    n = sum(c["ref_words"] for c in counts)
    s, d, i = (sum(c[k] for c in counts) for k in ("substitutions", "deletions", "insertions"))
    return {"ref_words": n, "substitutions": s, "deletions": d, "insertions": i, "wer": (s + d + i) / n if n else None}


# ---------------------------------------------------------------- hypotheses
def default_hyp_loader(paths, model, cand):
    """Hypothesis text for one bulletin and model; transcribes (and caches) tiny/base on demand."""
    if model == "small":
        f = os.path.join(paths["sample_text_dir"], cand["date"], cand["stem"] + ".txt")
        if not os.path.isfile(f):
            raise common.PrerequisiteMissing(f"option A transcript missing: {common.rel(f)}")
        return open(f, encoding="utf-8").read()
    f = os.path.join(paths["hyp_dir"], model, cand["stem"] + ".txt")
    if os.path.isfile(f) and os.path.getsize(f) > 0:
        return open(f, encoding="utf-8").read()
    audio = os.path.join(paths["sample_dir"], "audio", cand["date"], cand["stem"] + ".mp3")
    if not os.path.isfile(audio):
        raise common.PrerequisiteMissing(f"audio missing for {model} transcription: {common.rel(audio)}")
    return transcribe_cached(audio, model, f)


def transcribe_cached(audio_path: str, model: str, cache_file: str, device: str = "auto") -> str:
    """Whisper hypothesis for one audio file, cached in cache_file (non-empty cache = no transcription, no model load).

    Same engine and settings as the option A run (faster-whisper, VAD default off); device auto = cuda + float16 when usable.
    """
    if os.path.isfile(cache_file) and os.path.getsize(cache_file) > 0:
        return open(cache_file, encoding="utf-8").read()
    sys.path.insert(0, cfg.ROOT)
    import air_bulletins_scraper as scraper
    dev, compute = scraper.resolve_device("faster-whisper", device, None)
    text = scraper.transcribe_with_stats(audio_path, "faster-whisper", model, dev, compute)["text"]
    os.makedirs(os.path.dirname(cache_file) or ".", exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as h:
        h.write(text)
    return text


def compute(paths, hyp_loader=None, models=cfg.ASR_MODELS):
    hyp_loader = hyp_loader or default_hyp_loader
    cands = gold_status(paths).rows
    results = {"normalisation": NORMALISATION,
               "wer_definition": "(substitutions + deletions + insertions) / reference words; overall pools counts over files",
               "reference_dir": common.rel(paths["refs_dir"]), "models": {}, "bulletins": cands}
    for model in models:
        per_file = {}
        for c in cands:
            ref = normalise(open(os.path.join(paths["refs_dir"], c["stem"] + ".txt"), encoding="utf-8").read())
            hyp = normalise(hyp_loader(paths, model, c))
            per_file[c["stem"]] = {**align_counts(ref, hyp), "date": c["date"], "role": c["role"]}
        results["models"][model] = {"per_file": per_file, "overall": pool(list(per_file.values()))}
    return results, None


def run(paths=None, results_dir=None, hyp_loader=None):
    p = paths or default_paths()
    inputs = [os.path.join(p["refs_dir"], c["stem"] + ".txt") for c in wer_candidates(p["sample_config"])]
    return common.save_or_report(NAME, gold_status(p), lambda: compute(p, hyp_loader), inputs, results_dir)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(cfg.ASR_MODELS), help="comma list of Whisper sizes to score")
    a = ap.parse_args()
    st = gold_status()
    models = tuple(m.strip() for m in a.models.split(",") if m.strip())
    p = default_paths()
    inputs = [os.path.join(p["refs_dir"], c["stem"] + ".txt") for c in wer_candidates(p["sample_config"])]
    return common.save_or_report(NAME, st, lambda: compute(p, None, models), inputs)[0]


if __name__ == "__main__":
    raise SystemExit(main())
