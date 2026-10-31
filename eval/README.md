# eval/ - evaluation skeleton (A5)

The metric code for all four evals is written and tested on small synthetic inputs (`tests/test_eval_metrics.py`, hand-computed expected values). **No real evaluation has been run and no real number exists**: every eval stops with a clear message (exit code 3) until its gold file is labelled, and writes a result only when it is.

## Files

| File | Role |
|---|---|
| `eval_config.py` | Paths, seed (42), split names, gold file locations, label sets. Change settings here only. |
| `eval_common.py` | `write_result()` (writes `results/<name>_<UTC timestamp>.json` with the seed, git commit if any, SHA-256 of every input file), gold checkers, exit codes. |
| `genre_eval.py` (A8) | Macro-F1 over classes with >= 5 gold examples (others reported as "insufficient support"), per-class P/R/F1 + support, confusion matrix, 95% percentile bootstrap CIs (1000 resamples, seed 42), baselines majority-class and TF-IDF + logistic regression (trained only on store_A train-day SILVER labels, scored only on gold), Cohen's kappa annotator 1 vs 2 on the overlap file. Also scores the project's fast NLI and BART zero-shot backends (category zero-shot) and fine-tuned checkpoints (category fine-tuned-on-silver; 5 seeds, mean and sample std; training set minus any sentence identical to a gold/val/test sentence; training only via `finetune_genre.py` or `--train-finetune`). A model that cannot load is recorded as "not run". |
| `dedup_eval.py` (A7) | Joins the labelled pair sheet to the hidden key by id. Positive = same + paraphrase (alternative: only same; both reported). Threshold sweep 0.60-0.95 step 0.01 with bootstrap CIs; best-F1 threshold chosen on VAL pairs only, reported on TEST pairs (0.85 shown for reference only). Baselines: exact match, normalised match, TF-IDF cosine, word 5-gram Jaccard and a MinHash estimate (word 3-gram shingles, 128 permutations, seed 42). The pair sample is stratified by cosine band, so numbers describe the sample, not deployment. |
| `retrieval_eval.py` (A6) | Maps gold-relevant sentences to store_A segments (exact text, else the kept segment that caused the gate rejection, else unmapped; counts reported), then recall@1/3/5/10, MRR, nDCG@5 per query with bootstrap CIs for BM25, vector-only, date-prefilter + vector, full system (genre + date prefilter + vector + relevance filter, no LLM). Pool = store_A val/test segments; depth 20. Ablation switches for the full system: `--no-prefilter`, `--no-relevance-filter`, `--no-dedup` (needs `store_A_nodedup`, built with `build_store_A.py --no-gate --store-dir store_A_nodedup`; NOT built yet); ablated runs write `retrieval_eval_ablation_*`. |
| `asr_eval.py` (A9) | WER (own Levenshtein; S/D/I per file and overall) for Whisper tiny/base/small against `data/gold/asr_refs/<stem>.txt`. Normalisation: NFKC, lowercase, apostrophes deleted, hyphens to space, commas inside numbers deleted, other punctuation removed; numbers are NOT converted between digits and words. small = the option A transcripts; tiny/base are transcribed on demand (`transcribe_cached`, or `asr_transcribe.py`) into `data/asr_hyp/<model>/`. Our WER equals jiwer's on 306 synthetic cases; the S/D/I split can differ from jiwer when alignments tie in cost. |
| `duplicate_pairs_check.py` | S5 analysis of duplicate-slot file pairs (already ran; output `results/duplicate_pairs_check.json`). |

Exit codes: 0 = result written, 2 = a non-gold prerequisite is missing (store, transcripts, audio), 3 = gold missing or not labelled (nothing evaluated).
The project is not a git repository, so `git_commit` is `null` in result files; the input hashes carry the reproducibility.

## Which result file feeds which paper table

Table numbers are PROPOSED (the paper outline is not fixed); adjust when the paper structure is decided.

| Result file | Gold input | Proposed paper table | Status |
|---|---|---|---|
| `results/duplicate_pairs_check.json` | none (option A transcripts) | Corpus note: same-slot files are different recordings | exists |
| `results/asr_eval_*.json` | `data/gold/asr_refs/*.txt` (hand-corrected, TODO) | ASR: WER per Whisper size | code done, waiting for references |
| `results/genre_eval_*.json` | `data/gold/genre_sheet_annotator1.csv` (+ annotator 2 overlap for kappa), `store_A` train silver | Genre: per-class F1, macro-F1, baselines, kappa | code done, waiting for labels |
| `results/dedup_eval_*.json` | `data/gold/duplicate_pairs_sheet.csv` (+ hidden key) | Dedup: threshold sweep, P/R/F1 vs baselines | code done, waiting for labels |
| `results/retrieval_eval_*.json` | `data/gold/query_sheet.csv`, `store_A` | Retrieval: recall@k, MRR, nDCG per method | code done, waiting for queries |
| ablations, scale benchmark | none yet | Ablations / scale | TODO: no script yet |

## Rules

- Every number in a slide or in the paper comes from a file in `results/`.
- Evaluate only on gold (val/test days). Silver labels (the store's genre column) are never scored as gold.
- Choose thresholds and models on `val`, report on `test`.
- GPU smoke test (real Whisper tiny, opt-in): `AIRINSIGHT_GPU_SMOKE=1 .venv_gpu/Scripts/python.exe -m pytest tests/test_s9.py -k gpu_smoke -s`; skipped in the normal suite.
- `python run_all.py --list` shows stage status; `python run_all.py --stage all` runs what is ready and stops at the first stage whose gold is missing.

## Formats and limits to know

- `query_sheet.csv`: `date_constraint` is empty, one day `YYYY-MM-DD`, or a range `YYYY-MM-DD:YYYY-MM-DD` (val/test days only; a constraint on a train day makes the query skipped and listed in the result). `relevant_segment_ids` are ids from `data/gold/valtest_sentence_index.csv`, separated by `;`.
- Bootstrap CIs: percentile, 95%, 1000 resamples, seed 42, resampling items / pairs / queries. With about 50 pairs per split or about 50 queries they will be wide; say so in the paper.
- Gold is evaluated on val and test days only. For the dedup threshold, val selects and test reports.
- Helper scripts: `finetune_genre.py` (5-seed fine-tuning, resumable), `asr_transcribe.py` (cache hypotheses), `scale_benchmark.py` (10,000 SYNTHETIC segments, speed only). Cluster jobs for these are in `cluster/` (never submitted; compare with the real `gpu_single` template first: UNVERIFIED).
- Not covered yet (TODO): running the ablations, the fine-tuning, BART relabelling and the scale benchmark on real inputs; no fine-tuned checkpoint exists.
- Everything above is tested only on synthetic data. Behaviour on the real labelled sheets is UNVERIFIED.
