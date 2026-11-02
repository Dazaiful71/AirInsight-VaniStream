# PHASE 4 - Results, limitations and future work (slide content)

Status of this file: slide CONTENT only (no layout). Written 2026-11-02 from saved files in the repository. Every number carries its source path in the slide's Sources line; where a number is derived by simple arithmetic from file values it is marked "(derived)". PENDING = no result file exists; nothing PENDING has been estimated. UNVERIFIED = inferred or not confirmed by a file. Where two intervals overlap the slides say "not distinguishable on this gold set"; that is a statement about the intervals, not a statistical test.

Deck map: Part A, recap of Phase 3 (slides 1-3). Part B, Phase 4 body (slides 4-27). Slides 28-29 are the glossary. Likely professor questions follow the slides. (The body is longer than the target of about 18 slides because the dedup, retrieval, ablation and WER slides, each a clear PENDING table, were requested separately.)

---

## PART A - Recap of Phase 3

### Slide 1 - Phase 3 in one slide: the evaluation design
**Content**
- Why gold: the store's genre labels come from a model (silver); scoring a model on model-made labels is circular, so held-out sentences are labelled by a person.
- Gold sets drawn only from the validation and test days of the 10-day sample: genre sheet 400 sentences, overlap subset 175, pair sheet 100 pairs, query template 50 rows, ASR references for 5 bulletins.
- Only the 175 overlap sentences are human-labelled (one person, from scratch). An LLM (Claude Sonnet 5.5, 2026-10-31) pre-labelled the 400 sentences and 100 pairs in separate files, used only to measure human-versus-LLM agreement.
- No second human annotator exists, so there is no inter-annotator kappa.
- Splits are whole days (6 train, 2 validation, 2 test); a hidden key keeps pair scores from annotators.

**Speaker notes**
Phase 3 fixed how we would evaluate before we looked at any result. Gold labels come from a person on held-out days, and the language-model labels are kept apart and used only for an agreement measure. We stated from the start that there is only one human, so we cannot report agreement between humans. Today's slides report what that design has produced so far.

**Suggested visual**
Three-lane flow: gold lane (175 sentences -> human from scratch -> scoring); comparison lane (same 175 -> LLM labels -> human-vs-LLM agreement); pending lane (225 sentences + 100 pairs -> LLM pre-label -> human review TODO).

**Sources**
paper/draft.md sections 5.1 and 5.2; ROADMAP.md sections 8b, 8f; results/genre_eval_20261101T180912Z.json (gold_sheet n 175).

---

### Slide 2 - Phase 3 in one slide: protocol
**Content**
- Metrics: genre macro-F1 over classes with at least 5 gold sentences, per-class P/R/F1, accuracy, confusion matrix; duplicate-pair precision/recall/F1 across cosine thresholds 0.60-0.95; retrieval recall@1/3/5/10, MRR, nDCG@5; ASR word error rate; human-versus-LLM agreement.
- Baselines: majority class, TF-IDF + logistic regression, the fast and BART zero-shot backends (genre); text-overlap and MinHash baselines (duplicates); BM25, vector-only, date prefilter, full system (retrieval).
- Uncertainty: 95% percentile bootstrap, 1000 resamples, seed 42; no statistical test.
- Leakage: training-day segments identical in text to any gold or validation/test sentence are removed (17 of 2,520 in the genre run).
- Threshold plan: choose the duplicate threshold on validation pairs, report on test pairs.

**Speaker notes**
The protocol chooses metrics and baselines before results exist. The bootstrap tells us how much a score moves if the evaluation items were drawn again. The leakage filter removed 17 training-day segments whose text matched a gold or validation/test sentence. The duplicate threshold plan is selection on validation and reporting on test, so test data does not shape the choice.

**Suggested visual**
Task x metric x baseline matrix (rows: genre, agreement, duplicates, retrieval, ASR; columns: metric, unit resampled, baselines, result file name pattern).

**Sources**
eval/eval_config.py; eval/README.md; results/genre_eval_20261101T180912Z.json (baseline_training_data: n_removed_identical_to_gold_or_valtest 17, n_train_day_segments 2520); paper/draft.md sections 5.3 to 5.6.

---

### Slide 3 - What was pending when Phase 4 began
**Content**
- Run and saved: genre evaluation on the 175 gold sentences (majority, TF-IDF + LR, fast, BART); human-versus-LLM agreement on the same 175; the same-slot file check; the store build reports.
- Not run: duplicate-pair evaluation (pair labels not human-reviewed), retrieval evaluation and ablations (queries not written or judged), word error rate (reference transcripts not written), fine-tuned classifiers (no checkpoint), scale benchmark, BART relabelling of the store, agreement on the 225 reviewed sentences.
- Unlocks: human review of 225 sentences and 100 pairs; queries written and judged; five hand-typed reference transcripts; cluster access for heavy jobs (header check against the real template is UNVERIFIED).
- The next slides show what exists and keep every missing result as an explicit PENDING table.

**Speaker notes**
Entering this phase, one evaluation had real numbers and the rest were waiting for human work or compute. We keep that division visible. The rule for the remaining slides is that a table is filled only if a result file exists.

**Suggested visual**
Two-column checklist: "result file exists" (4 items) versus "PENDING, with unlock" (8 items).

**Sources**
ls results/ and results/store_reports/ (genre_eval_20261101T180912Z.json, human_vs_llm_agreement_20261101T175909Z.json, duplicate_pairs_check.json, store_A_build_report.json, store_A_dedup_report.json, store_A_nodedup_build_report.json); ROADMAP.md sections 8, 8b to 8h; cluster/README.md.

---

## PART B - Phase 4 body: results, limitations, future work

### Slide 4 - Project status as of 2 November 2026
**Content**
- Data: 3-month listing crawled (2,173 items); 10-day sample downloaded and transcribed (239 bulletins, 1,441.3 minutes of audio).
- Pipeline: segmentation, embeddings, novelty gate, genre labelling, FAISS + SQLite, two-tier retrieval implemented and tested on synthetic data (118 test functions in 9 files).
- Stores built: with the gate (4,264 segments) and without it (9,519 segments).
- Evaluations with result files: genre (175 sentences), human-versus-LLM agreement (175 sentences), same-slot file check.
- Evaluations WITHOUT result files: duplicates, retrieval, ablations, WER, fine-tuning, scale benchmark.
- Writing: a paper draft exists with empty tables for the missing evaluations; this deck follows it.

**Speaker notes**
This slide is the honest balance sheet. The engineering and the data collection are done at pilot scale, and one evaluation has real numbers. The remaining evaluations are implemented but cannot run until human labels or reference text exist. We would rather show an empty table than guess.

**Suggested visual**
Status table, one row per evaluation. Data: genre_eval -> result file exists (results/genre_eval_20261101T180912Z.json); human_vs_llm_agreement -> exists (results/human_vs_llm_agreement_20261101T175909Z.json, overlap group only); duplicate_pairs_check (same-slot) -> exists (results/duplicate_pairs_check.json); store reports -> exist (results/store_reports/); dedup_eval, retrieval_eval, retrieval ablations, asr_eval, fine-tuning, scale_benchmark -> PENDING.

**Sources**
results/ directory listing; ROADMAP.md sections 8 to 8h; tests/*.py (118 "def test_" lines, derived); paper/draft.md.

---

### Slide 5 - Genre results: all systems on the 175 gold sentences
**Content**
- Gold: 175 sentences with human labels typed from scratch (95 from validation days, 80 from test days); ten classes, each with at least 5 sentences, so none was marked "insufficient support" overall.
- Majority class (`Other`, trained on silver): macro-F1 0.0284 [0.0205, 0.0364]; accuracy 0.1657 [0.1143, 0.2229].
- TF-IDF + logistic regression (trained on silver): macro-F1 0.1109 [0.0654, 0.1536]; accuracy 0.2000 [0.1429, 0.2629].
- Fast zero-shot (cross-encoder/nli-MiniLM2-L6-H768): macro-F1 0.4333 [0.3450, 0.5119]; accuracy 0.4229 [0.3543, 0.4971].
- BART zero-shot (facebook/bart-large-mnli): macro-F1 0.4334 [0.3478, 0.4987]; accuracy 0.4514 [0.3714, 0.5257].
- The two zero-shot systems are not distinguishable on this gold set (macro-F1 and accuracy intervals overlap). The two baselines are not distinguishable on accuracy (intervals overlap) but their macro-F1 intervals do not overlap. Neither baseline's interval overlaps a zero-shot system's, on either measure.
- Baselines were trained on 2,503 training-day silver segments after removing 17 matching sentences.

**Speaker notes**
On 175 human-labelled sentences, both zero-shot backends land around 0.43 macro-F1, and their intervals overlap, so we cannot separate them. The majority-class and bag-of-words baselines score far lower, and their intervals do not overlap with the zero-shot ones. We do not read this as the models being good; there is no external reference score and no human ceiling for this label set. The majority baseline's accuracy equals the share of `Other` (29 of 175).

**Suggested visual**
Horizontal interval plot (dot = estimate, bar = 95% interval), two panels (macro-F1, accuracy). Data table: majority 0.0284 [0.0205, 0.0364] / 0.1657 [0.1143, 0.2229]; TF-IDF+LR 0.1109 [0.0654, 0.1536] / 0.2000 [0.1429, 0.2629]; fast 0.4333 [0.3450, 0.5119] / 0.4229 [0.3543, 0.4971]; BART 0.4334 [0.3478, 0.4987] / 0.4514 [0.3714, 0.5257].

**Sources**
results/genre_eval_20261101T180912Z.json (systems.*.all_gold: macro_f1, accuracy, bootstrap.macro_f1_ci95, bootstrap.accuracy_ci95; baseline_training_data; gold_sheet).

---

### Slide 6 - Genre results: per-class F1 and support
**Content**
- Support per class (human labels): International 31, Other 29, Sports 20, Environment 19, Society & Culture 17, Economy 16, Defence & Security 16, Politics 14, Science & Technology 7, Health 6.
- BART F1 by class: Sports 0.824, Environment 0.688, Health 0.571, Science & Technology 0.462, International 0.485, Politics 0.417, Economy 0.400, Other 0.370, Defence & Security 0.118, Society & Culture 0.000.
- Fast F1 by class: Health 0.615, Sports 0.571, Science & Technology 0.571, International 0.508, Economy 0.500, Society & Culture 0.390, Other 0.366, Defence & Security 0.353, Environment 0.333, Politics 0.125.
- TF-IDF + LR: non-zero F1 only for Sports 0.333, Other 0.269, Society & Culture 0.222, International 0.167, Defence & Security 0.118. Majority: Other 0.284, all else 0.
- Per-class intervals are wide. Example: Sports BART [0.6486, 0.9474] versus fast [0.3077, 0.7742]; Environment BART [0.4615, 0.8387] versus fast [0.0870, 0.5455]; in both cases the zero-shot systems are not distinguishable on this gold set.
- Health (6) and Science & Technology (7) rest on very few sentences.

**Speaker notes**
Per-class scores show where each system puts its weight, but with 6 to 31 sentences per class they are noisy. The intervals for the same class from the two zero-shot systems overlap, so we do not rank the systems by class. Two things are descriptive facts rather than conclusions: BART assigned no sentence to Society & Culture, and the baselines mostly predicted `Other`. We report them and do not explain them.

**Suggested visual**
Grouped bar chart of F1 by class for the four systems, with support printed under each class. Data table (class / support / majority / TF-IDF+LR / fast / BART): Politics 14 / 0.000 / 0.000 / 0.125 / 0.417; Economy 16 / 0.000 / 0.000 / 0.500 / 0.400; Science & Technology 7 / 0.000 / 0.000 / 0.571 / 0.462; Sports 20 / 0.000 / 0.333 / 0.571 / 0.824; International 31 / 0.000 / 0.167 / 0.508 / 0.485; Defence & Security 16 / 0.000 / 0.118 / 0.353 / 0.118; Health 6 / 0.000 / 0.000 / 0.615 / 0.571; Environment 19 / 0.000 / 0.000 / 0.333 / 0.688; Society & Culture 17 / 0.000 / 0.222 / 0.390 / 0.000; Other 29 / 0.284 / 0.269 / 0.366 / 0.370.

**Sources**
results/genre_eval_20261101T180912Z.json (systems.*.all_gold.per_class: support, precision, recall, f1; bootstrap.per_class_f1_ci95).

---

### Slide 7 - Genre results: what the confusion matrices show
**Content**
- Majority: all 175 sentences predicted `Other`. TF-IDF + LR: 142 of 175 predicted `Other`.
- Fast zero-shot: Politics 14 -> 1 correct, 8 predicted `Other`; Sports 20 -> 8 correct, 7 predicted International; Environment 19 -> 4 correct, 6 predicted Defence & Security, 6 `Other`, 3 International; International 31 -> 16 correct, 10 predicted `Other`; `Other` 29 -> 17 correct, 8 predicted Society & Culture.
- BART zero-shot: Society & Culture 17 -> 0 correct, 14 predicted `Other`; Defence & Security 16 -> 1 correct, 11 predicted `Other`; Sports 20 -> 14 correct, 5 predicted International; Environment 19 -> 11 correct, 6 `Other`; `Other` 29 -> 20 correct, 7 predicted International.
- Precision and recall (fast / BART): Sports precision 1.000 / 1.000, recall 0.400 / 0.700; Defence & Security precision 0.333 / 1.000, recall 0.375 / 0.062 (BART predicted 1 sentence); Environment precision 0.800 / 0.846, recall 0.211 / 0.579; Society & Culture precision 0.333 / 0.000, recall 0.471 / 0.000.
- These are counts of what each system did on these 175 sentences; causes were not investigated.

**Speaker notes**
The matrices show that both zero-shot systems send many sentences to `Other`, and that they confuse nearby topics such as Sports and International. The BART backend predicted almost no Defence & Security and no Society & Culture sentences. We do not know why; one possibility is the wording of the label names, but that is not tested here (UNVERIFIED). Full matrices are in the result file.

**Suggested visual**
Two 10x10 heat maps (fast, BART), rows = human label, columns = predicted label, cell = count; highlight the `Other` column. Data: the matrices stored under systems.project_fast_nli_minilm.all_gold.confusion_matrix.counts and systems.project_zero_shot_bart.all_gold.confusion_matrix.counts (column order Politics, Economy, Science & Technology, Sports, International, Defence & Security, Health, Environment, Society & Culture, Other).

**Sources**
results/genre_eval_20261101T180912Z.json (confusion_matrix.counts and per_class.predicted for each system).

---

### Slide 8 - Genre results: validation-only and test-only blocks
**Content**
- The same systems scored separately on the 95 validation-day sentences and the 80 test-day sentences.
- Classes below 5 gold sentences are dropped in each block: validation drops Science & Technology and Health (8 classes scored); test drops Politics, Science & Technology, Sports and Health (6 classes scored).
- Validation macro-F1 (8 classes): majority 0.0360 [0.0216, 0.0487]; TF-IDF+LR 0.1444 [0.0717, 0.2127]; fast 0.3859 [0.2827, 0.4672]; BART 0.3426 [0.2672, 0.4031].
- Test macro-F1 (6 classes): majority 0.0466 [0.0268, 0.0667]; TF-IDF+LR 0.1190 [0.0588, 0.1869]; fast 0.3641 [0.2677, 0.4506]; BART 0.4032 [0.2815, 0.5037].
- Within each block the fast and BART intervals overlap: not distinguishable on this gold set.
- Blocks average over different class sets, so their macro-F1 values are not comparable with each other or with the all-gold values.

**Speaker notes**
We report the two held-out groups separately so that a reader can see whether the picture depends on the days. Because the support rule drops different classes in each block, the averages are over different sets of classes, and they should not be compared across blocks. Within a block, the two zero-shot systems cannot be separated. The ordering between blocks is a reminder that two test days can reflect their own stories.

**Suggested visual**
Small-multiple interval plots: panel for validation (n = 95), panel for test (n = 80); four systems each. Data as in the bullets; accuracy values for the table: validation majority 0.1684, TF-IDF 0.2000, fast 0.4421, BART 0.4421; test majority 0.1625, TF-IDF 0.2000, fast 0.4000, BART 0.4625 (intervals in the result file).

**Sources**
results/genre_eval_20261101T180912Z.json (systems.*.val_days_only and test_days_only: n, macro_f1, accuracy, bootstrap, classes_insufficient_support).

---

### Slide 9 - Human-versus-LLM agreement: headline
**Content**
- Compared: the 175 from-scratch human labels versus the LLM's labels (Claude Sonnet 5.5, 2026-10-31) for the same sentences.
- The LLM label equals the human label for 119 sentences and differs for 56.
- Observed agreement 0.68, 95% bootstrap interval [0.6114, 0.7486].
- Cohen's kappa (human versus LLM) 0.6351, interval [0.5559, 0.7085]; 1000 resamples, seed 42.
- Every output is named human_vs_llm_agreement. This is NOT inter-annotator agreement: one side is a model, and there is no second human.
- The 225 other sentences (human-reviewed, not yet) and the 100 pairs are not part of this measure; the reviewed group would be inflated by anchoring and is reported separately when it exists.
- The LLM also built the sampling sheets; an earlier run of the agreement script was started by mistake by an old test, its output never read and deleted; this run is the intended one.

**Speaker notes**
This is the only agreement figure we have. It says how often a model and the human gave the same label on the same 175 sentences. It does not tell us the human is right, and it does not tell us how two humans would agree. Kappa corrects for chance agreement given the label frequencies, and here it is 0.6351. We call it human-versus-LLM agreement everywhere so that nobody reads it as annotator reliability.

**Suggested visual**
Single-number panel with intervals (observed agreement, kappa) and a one-line caption "human vs LLM, not inter-annotator". Data: observed 0.68 [0.6114, 0.7486]; kappa 0.6351 [0.5559, 0.7085]; agree 119 of 175.

**Sources**
results/human_vs_llm_agreement_20261101T175909Z.json (groups.overlap_human_from_scratch: n, agree_count, disagree_count, observed_agreement, cohens_kappa_human_vs_llm, bootstrap); ROADMAP.md section 8h.

---

### Slide 10 - Human-versus-LLM agreement: per label and largest disagreements
**Content**
- Counts per label (human assigned / LLM assigned / both agree): Politics 14 / 8 / 6; Economy 16 / 17 / 10; Science & Technology 7 / 8 / 4; Sports 20 / 17 / 17; International 31 / 39 / 24; Defence & Security 16 / 11 / 6; Health 6 / 5 / 3; Environment 19 / 16 / 15; Society & Culture 17 / 25 / 12; Other 29 / 29 / 22.
- Largest disagreement cells (human label then LLM label, raw counts): Defence & Security -> International 6; Politics -> Society & Culture 5; Other -> Society & Culture 4; Environment -> International 4; International -> Economy 3; Economy -> Science & Technology 3; Defence & Security -> Other 3.
- The 56 disagreements spread over 30 distinct label pairs; no label pair accounts for more than 6.
- How to read: rows are the human label, columns are the LLM label; the diagonal is agreement.
- These counts do not say which label is correct; no label was changed.

**Speaker notes**
The LLM assigned more sentences to International and to Society & Culture than the human did, and fewer to Politics and Defence & Security. The largest single disagreement is the human saying Defence & Security where the LLM said International, six times. We list the counts without interpretation, and we do not use them to change any label. They do suggest where written genre definitions would help the next round of labelling (UNVERIFIED as a cause).

**Suggested visual**
Heat map of the 10x10 agreement confusion matrix (rows human, columns LLM) and a bar chart of the top disagreement cells. Data: matrix in groups.overlap_human_from_scratch.confusion_matrix.counts; top cells as listed above.

**Sources**
results/human_vs_llm_agreement_20261101T175909Z.json (per_label, confusion_matrix); the count of 30 distinct disagreeing pairs and the "no pair above 6" statement are derived from the off-diagonal cells (derived).

---

### Slide 11 - Transcription speed by Whisper size
**Content**
- Whole sample, `small`, GPU float16: 239 bulletins, 1,441.3 min of audio, 81.9 min of transcription, RTF 0.0568 (hourly 0.0576; other 0.0551).
- Five bulletins (tiny / base RTF): English-0105-0110-9 (287.45 s) 0.0224 / 0.0250; English-1505 (283.56 s) 0.0201 / 0.0274; English-1905-1 (283.34 s) 0.0193 / 0.0286; morninng (883.87 s) 0.0197 / 0.0288; Midday-News (870.70 s) 0.0198 / 0.0304.
- Times (tiny / base): 6.45 / 7.18 s; 5.69 / 7.76 s; 5.47 / 8.09 s; 17.39 / 25.43 s; 17.20 / 26.49 s.
- GPU memory in use (total, nvidia-smi): tiny run peak 241 MiB (from 0); base run peak 473 MiB (from 209, because tiny stayed loaded).
- Each figure is one run on one laptop GPU; the opening file of each model run includes model load or warm-up.
- Speed says nothing about accuracy: WER is PENDING.

**Speaker notes**
All three sizes run far faster than real time on the laptop GPU. Even the slowest figure here, base on the Midday bulletin at 0.0304, transcribes a 14.5-minute bulletin in about 26 seconds. These are single runs, so we do not claim a precise ranking. Which size is accurate enough is the open question the WER evaluation is meant to answer.

**Suggested visual**
Grouped bar chart of RTF per bulletin for tiny and base (five bulletin groups), plus a horizontal reference line at small's whole-sample RTF 0.0568 (a different data set; label it). Data table: as in the bullets.

**Sources**
ROADMAP.md section 8e (source log data/asr_hyp/transcribe_log.json, not committed) and section 8a ("S5 results"); data/sample_A/metadata.csv.

---

### Slide 12 - GPU versus CPU
**Content**
- Two-bulletin test (two hourly bulletins, 9.50 min of audio, one run per setting, opening file includes warm-up).
- GPU float16: base RTF 0.042 (23.9 s, peak 369 MiB); small RTF 0.067 (38.2 s, peak 881 MiB).
- GPU int8_float16: base RTF 0.043 (24.6 s, 273 MiB); small RTF 0.072 (41.0 s, 593 MiB).
- CPU int8: base RTF 0.100 (56.8 s); small RTF 0.264 (150.6 s); CPU memory not measured.
- Stated ratios: GPU about 2.4 times faster than CPU for base and 3.9 times for small.
- Transcript lengths on GPU and CPU agree within about 0.5% in characters; text was not compared word by word.
- Medium was not measured (fit in 4 GB is UNVERIFIED); cluster (A6000) speeds are unmeasured.
- The genre classifiers and embeddings ran on CPU: the PyTorch in the project environment is a CPU build.

**Speaker notes**
The GPU matters most for the larger model: small is 3.9 times faster on the GPU, base 2.4 times. The int8 option saves memory without a speed gain on this card. The sample is only two bulletins and one run, so these are indications and not benchmarks. The genre and embedding steps ran on CPU because the environment's PyTorch has no CUDA support.

**Suggested visual**
Grouped bar chart of RTF by setting (base and small x GPU float16, GPU int8_float16, CPU int8). Data table (model / setting / RTF / time s / peak GPU MiB): base GPU float16 0.042 / 23.9 / 369; base GPU int8_float16 0.043 / 24.6 / 273; small GPU float16 0.067 / 38.2 / 881; small GPU int8_float16 0.072 / 41.0 / 593; base CPU int8 0.100 / 56.8 / n.a.; small CPU int8 0.264 / 150.6 / n.a.

**Sources**
ROADMAP.md section 5 (RTX 2050 table and text); results/store_reports/store_A_build_report.json (classifier run on CPU) and ROADMAP.md section 8c; paper/draft.md section 9.

---

### Slide 13 - The store and the novelty gate: what the numbers are
**Content**
- Option A, gate threshold 0.85, all splits, date order: 9,519 sentences read, 4,264 kept; dropped 5,255 (55.2%).
- By split (read -> kept): train 5,560 -> 2,520; validation 1,981 -> 879; test 1,978 -> 865. Drop shares (derived): train 54.7%, validation 55.6%, test 56.3%.
- The 20 highest-scoring rejected pairs listed in the dedup report all have cosine 1.0 (identical vectors).
- THE DROP RATE IS NOT A PRECISION FIGURE: whether each dropped sentence was a true repeat has not been measured; that is the purpose of the labelled-pair evaluation (PENDING).
- Because the gate runs across splits in date order, a validation or test sentence can be dropped because of an earlier training-day sentence, including gold sentences.
- 710 stored segments have no hour (train 479, validation 80, test 151), all flagged no_time_in_filename.
- Genre column (fast backend, silver): Other 1,601; International 705; Society & Culture 479; Defence & Security 378; Sports 306; Politics 226; Economy 192; Environment 141; Science & Technology 126; Health 110.
- Gate-off store for ablation: 9,519 segments, 1,547 without hour.

**Speaker notes**
More than half the sentences are dropped by the gate at 0.85, but that number describes what the gate did, not whether it was right. A sentence can be dropped for being a true repeat or for being merely similar, and we have not measured the split between the two. The highest-scoring rejected pairs are exact copies, which is reassuring but is only 20 examples. The store's genre column comes from the fast backend, which scored 0.4333 macro-F1 on the gold sentences, so the stored genres are of limited quality.

**Suggested visual**
Sankey or stacked bar per split: sentences read versus kept. Data: train 5,560 / 2,520; validation 1,981 / 879; test 1,978 / 865. Second chart: bar of the silver genre counts above. Table: NULL hours by split (train 479, validation 80, test 151).

**Sources**
results/store_reports/store_A_build_report.json (sentences_before_gate, sentences_after_gate, null_hour_segments_by_split, genre_counts_SILVER, classifier_backend, threshold, dedup_totals); results/store_reports/store_A_dedup_report.json (totals, top_rejected_pairs); results/store_reports/store_A_nodedup_build_report.json.

---

### Slide 14 - Files that share a broadcast slot
**Content**
- Archive finding: 124 date-and-time pairs in the 3-month listing have two different audio files (250 items involved).
- Inside option A: 9 such pairs on 8 of the 10 days, all in the 01:05 and 03:05 night slots.
- All 9 pairs have different SHA-256 values (0 identical files).
- Durations differ by 2.98 to 11.42 seconds.
- Word 5-gram Jaccard similarity of the two transcripts: 0.0008 to 0.0388 (all 9 below the preset 0.3 cut-off, labelled "different text").
- Reading: in this sample, same-slot files are different recordings and not re-uploads, so they are not treated as duplicates of each other.
- Scope: option A only; other slots, months or the rest of the archive are UNVERIFIED.

**Speaker notes**
We were worried that same-slot files were copies, which would have inflated the duplicate rate and complicated the evaluation. We compared every pair inside the sample on file hash, duration and transcript overlap. All nine are clearly different recordings. This is a bounded statement: it covers our ten days, and we make no claim about the rest of the archive.

**Suggested visual**
Table of the 9 pairs (date / slot / duration difference s / Jaccard / SHA equal?) taken from the pairs list; plus a scatter of duration difference (x) versus Jaccard (y) with the 0.3 cut-off line.

**Sources**
results/duplicate_pairs_check.json (n_pairs, pairs[].duration_diff_s, jaccard_word_5grams, sha256_equal, hhmm, label_counts, thresholds_our_choice); ROADMAP.md section 4 ("Same-time duplicates"); config/sample_config.json (duplicate_slot_pairs 9, days_with_a_duplicate_slot_pairs 8).

---

### Slide 15 - Duplicate-pair detection: PENDING
**Content**
- STATUS: PENDING. No file results/dedup_eval_*.json exists; dedup_eval.py has not been run on real labels.
- Needs: human review of the 100 pair labels (same / paraphrase / follow-up / different) and an agreed written definition of the four labels.
- Will report: for each method, precision, recall and F1 across thresholds, the threshold chosen on validation pairs, and test results with 95% intervals; baselines exact match, normalised match, TF-IDF cosine, word 5-gram Jaccard, MinHash (3-gram shingles, 128 permutations).
- The sheet is sampled across cosine bands, so results describe the sample and not deployment.
- Nothing about the gate's precision can be said until this runs.

**Speaker notes**
This is the evaluation that would tell us whether 0.85 is a sensible threshold. It cannot run yet because the pair labels have not been reviewed by a person. When it runs, the threshold is chosen on validation pairs only. Until then the drop rate on slide 13 stays a count, not a quality measure.

**Suggested visual**
Empty PENDING table. Columns: Method / positive-class definition / threshold chosen on validation / validation F1 / test precision / test recall / test F1 / test-F1 interval / n validation pairs / n test pairs. Rows: project cosine (MiniLM), exact match, normalised match, TF-IDF cosine, word 5-gram Jaccard, MinHash; all cells "PENDING".

**Sources**
eval/dedup_eval.py (docstring); eval/eval_config.py; ROADMAP.md rows A7 and section 8b; ls results/ (no dedup_eval_*.json).

---

### Slide 16 - Retrieval: PENDING
**Content**
- STATUS: PENDING. No file results/retrieval_eval_*.json exists.
- Needs: the human writes and judges about 50 queries (an LLM supplied 80 draft queries, 52 with a date constraint and 28 without, with relevant segments left empty).
- Will report: mapping counts (exact / via gate rejection / unmapped), then recall@1/3/5/10, MRR and nDCG@5 with intervals for BM25, vector-only, date prefilter + vector and the full system, over store_A segments of validation and test days, top 20.
- Judging uses candidates from a helper that merges embedding and TF-IDF rankings; this pooling can favour similar retrievers (UNVERIFIED effect).
- The answer-generation step gets only a planned human check of about 30 questions (also PENDING).

**Speaker notes**
Retrieval is the heart of the system and the least evaluated part. It needs queries and judgments from a person, and there are none yet. The draft queries are a convenience, not data. When the evaluation runs, we will report how many relevant sentences could be mapped into the store at all, since the gate removed some.

**Suggested visual**
Two empty PENDING tables: (a) mapping counts: distinct relevant sentences / mapped by exact text / mapped via gate rejection / unmapped / queries evaluated / queries skipped; (b) metrics: system / queries / recall@1 / @3 / @5 / @10 / MRR / nDCG@5 (each with interval).

**Sources**
eval/retrieval_eval.py (docstring); ROADMAP.md section 8f (draft queries 80: 52 dated, 28 undated); data/gold/query_sheet.csv (50 rows); ls results/ (no retrieval_eval_*.json).

---

### Slide 17 - Ablations: PENDING
**Content**
- STATUS: PENDING. No file results/retrieval_eval_ablation_*.json exists.
- Prepared: switches --no-prefilter, --no-relevance-filter, --no-dedup (the last uses the gate-off store).
- Gate-off store exists: 9,519 segments (train 5,560; validation 1,981; test 1,978), built in 1,856.2 s on CPU, with the fast backend's silver genres.
- With-gate store: 4,264 segments, built in 978.2 s.
- Runs once judged queries exist; each ablation writes its own result file.
- No ablation result is claimed or estimated.

**Speaker notes**
The ablation switches test whether each stage earns its place: the prefilter, the relevance filter and the gate itself. The gate-off store is ready, so removing the gate is possible. All three ablations wait for the judged queries.

**Suggested visual**
Empty PENDING table: Prefilter / relevance filter / novelty gate / queries / recall@1 / recall@5 / recall@10 / MRR / nDCG@5, rows "all on", "prefilter off", "relevance filter off", "gate off". Side box with the two store sizes.

**Sources**
results/store_reports/store_A_nodedup_build_report.json; results/store_reports/store_A_build_report.json; eval/retrieval_eval.py (flags); ls results/.

---

### Slide 18 - Word error rate: PENDING
**Content**
- STATUS: PENDING. No file results/asr_eval_*.json exists; data/gold/asr_refs/ is empty.
- Needs: a human types reference transcripts from the audio for five bulletins: English-0105-0110-9, English-1505, English-1905-1, morninng, Midday-News (never copied from a Whisper output).
- Hypotheses ready: `small` (option A transcripts) and `tiny`, `base` (cached for the same five bulletins).
- Will report: WER with substitutions, deletions and insertions per file and overall for each size.
- Normalisation fixed in advance (lowercase, punctuation and apostrophes removed, hyphens to space, thousands commas removed, numbers not converted between digits and words).
- Our WER code equals the jiwer library on 306 synthetic cases; the error-type split can differ on ties.

**Speaker notes**
We can say how fast each size runs but not how accurate it is. Accuracy needs the five reference transcripts, and writing them is slow human work. The comparison between sizes will use identical normalisation and identical bulletins. Larger Whisper sizes are prepared for the cluster and have not run.

**Suggested visual**
Empty PENDING table: Model / bulletin / reference words / substitutions / deletions / insertions / WER, with tiny, base, small x five bulletins plus overall rows.

**Sources**
config/sample_config.json (asr_wer_candidates_from_option_A_test_days); eval/asr_eval.py; ROADMAP.md section 8e; tests/test_s9.py (jiwer cross-check); ls data/gold/asr_refs/ (empty).

---

### Slide 19 - Other PENDING items
**Content**
- Fine-tuned classifier: no checkpoint exists (models/ is absent); code for 5-seed training on leakage-filtered silver labels exists and has run only with a tiny fake model in tests. PENDING.
- Scale benchmark (10,000 synthetic segments): script and cluster job exist; no result file. PENDING.
- BART relabelling of the whole store: script and cluster job exist; the store's genre column still comes from the fast backend. PENDING.
- Agreement for the 225 human-reviewed sentences and for pairs: waits for human review. PENDING.
- Cluster: four job scripts written, never submitted, headers not compared with the cluster's real template, nodes' internet/ffmpeg/CUDA access unknown. UNVERIFIED.
- Genre labels for the other 225 sentences as gold: PENDING human review.

**Speaker notes**
These are not failures but items that were scoped in and not yet run. Each has code and a plan. Heavy jobs need the cluster, which we have not tested. We list them so the audience can see exactly what the current results do not cover.

**Suggested visual**
Checklist table: item / what exists (code, data) / what is missing / result file expected (genre_eval fine-tuned block, scale_benchmark_n10000_*.json, silver_bart labels, agreement reviewed group).

**Sources**
ROADMAP.md sections 8d, 8e, 8h; cluster/README.md; eval/finetune_genre.py; eval/scale_benchmark.py; cluster/bart_label_store.py; ls results/.

---

### Slide 20 - Discussion: what the results do and do not show
**Content**
- Show: on 175 human-labelled sentences, the two zero-shot backends reach macro-F1 around 0.43, are not distinguishable from each other on this gold set, and lie clearly above the majority and TF-IDF + LR baselines on both measures.
- Show: per-class behaviour differs widely and unevenly (for example no BART predictions for Society & Culture), with wide per-class intervals.
- Show: a human and an LLM gave the same genre for 119 of 175 sentences (observed 0.68, kappa 0.6351).
- Show: at 0.85 the gate dropped 55.2% of sentences; same-slot files in option A are different recordings; transcription runs far faster than real time on the laptop GPU.
- Do NOT show: that either backend is good in absolute terms (no external reference, no human ceiling); that the gate's decisions are correct; any retrieval, answer-quality or WER result; that results hold beyond two test days, one broadcaster and one annotator.
- Do NOT show: anything about fine-tuning or about the ablations.

**Speaker notes**
It is as important to say what a result does not show. Our genre numbers are measurements on 175 sentences labelled by one person; they support comparing the four systems on that set and nothing more. The agreement figure compares a person with a model. The gate and speed figures are descriptive. We deliberately make no claim about overall system quality until the missing evaluations exist.

**Suggested visual**
Two-column "supported / not supported" table, each row linked to a slide number.

**Sources**
results/genre_eval_20261101T180912Z.json; results/human_vs_llm_agreement_20261101T175909Z.json; results/store_reports/; results/duplicate_pairs_check.json; ROADMAP.md section 8a.

---

### Slide 21 - Limitations
**Content**
- Scale: 10 days (239 bulletins) from one 3-month window; two test days; gold N = 175 with 6 to 31 per class; all gold is pilot scale.
- Annotation: one human, no inter-annotator kappa; sampling sheets built by an LLM; LLM pre-labels for 225 sentences and 100 pairs not human-reviewed; `Other` inflated by boilerplate and accident stories; genre descriptions are only keyword hints; the follow-up/different boundary is subjective.
- Models: the store's genre column comes from the fast backend (macro-F1 0.4333 on 175 sentences, interval [0.3450, 0.5119]); no fine-tuned classifier; the project's keyword date and genre parsing, single-sentence chunks, English only, one genre per sentence.
- Gate: one fixed threshold (0.85) not tuned; order dependent; ran across splits; drop rate is not precision; 710 segments lack an hour.
- Speech: ASR quality unmeasured; numbers not converted in normalisation; timings are single runs on one 4 GB GPU; timestamps empty for archive bulletins.
- Retrieval/answers: unevaluated; closed generator model hard-coded and possibly retired (UNVERIFIED); hallucination risk; relevance judging pooled from two rankers.
- Data/legal: archive size UNVERIFIED; AIR redistribution rights unresolved.
- Engineering: live stream not rerun after changes (UNVERIFIED); one stream at a time, no authentication; synthetic scale test only; cluster scripts unsubmitted; no continuous integration.

**Speaker notes**
This list is deliberately plain. The biggest limits are the small gold set, the single annotator and the two test days. The second group is what is missing: no retrieval, WER, or fine-tuning results. The third is what could break outside this pilot: licensing, a hard-coded generator, and a pipeline that is English only. We state them so that no one reads more into the results than they carry.

**Suggested visual**
Grouped list with four boxes (Data and scale / Annotation / Models and pipeline / Operations and legal); no chart.

**Sources**
paper/draft.md section 7; ROADMAP.md sections 2, 3, 4, 6, 8a to 8h, 10; results/genre_eval_20261101T180912Z.json; results/store_reports/store_A_build_report.json.

---

### Slide 22 - Threats to validity
**Content**
- Internal: one annotator whose labels are both the gold and the benchmark; LLM-built sheets; possible anchoring for any labels reviewed from LLM pre-labels (which is why only the from-scratch overlap is gold).
- Construct: ten coarse genres with `Other` as a catch-all; the label set has no category for boilerplate or accidents; pair labels need a story-level judgment.
- Statistical: small N and wide intervals; many per-class comparisons with no correction; no statistical test; per-split blocks average over different classes.
- External: two test days, one broadcaster, English only, one 3-month window; the sample is stratified by month and weekday, not by topic.
- Leakage: the gate ran across splits; gold was sampled from raw sentences, not from the post-gate store; training-day silver labels came from a model whose behaviour on the gold is itself being measured.
- Conclusion: the baselines were trained on silver labels from the fast backend, which also appears as an evaluated system (the fast zero-shot backend labelled the training data for the baselines).

**Speaker notes**
Threats to validity are the ways our conclusions could be wrong even if the code is right. The last one deserves attention: the baselines learn from silver labels that came from the fast backend, so their behaviour is tied to that backend's behaviour. We therefore treat the baselines as a floor, not as an independent competitor. None of these threats has been quantified yet.

**Suggested visual**
Matrix: threat type (internal, construct, statistical, external, leakage, conclusion) x "what we did about it" x "what remains". No numbers needed.

**Sources**
paper/draft.md sections 4.3, 5.2, 5.5, 7; ROADMAP.md sections 8c, 8f; results/store_reports/store_A_build_report.json (classifier_backend fast); results/genre_eval_20261101T180912Z.json (baseline_training_data.label_origin).

---

### Slide 23 - Ethics and AIR content licensing
**Content**
- Source: public radio news from the official AIR website; requests followed robots.txt (all paths allowed on 31 Oct 2026) with a 1 to 3 second random delay.
- Audio is not stored in the project repository; the repository holds the listing, configuration, gold sheets, LLM-label files and result files.
- Redistribution rights for AIR audio and transcripts are UNRESOLVED (TODO: ask AIR / Prasar Bharati). The annotation sheets contain sentences of transcripts, so they should not be published before the answer.
- People: bulletins name officials, newsreaders and, in some stories, private individuals; a privacy review is TODO before any release.
- LLM use is disclosed: it built the sampling sheets and produced separate pre-labels; the gold labels are the human's.
- Cluster terms: GPUs only for the approved task; written confirmation is TODO.
- Misuse of searchable broadcast transcripts and of unsupported generated answers: statement TODO.

**Speaker notes**
We took public content politely, but taking it and republishing it are different matters. We have not secured the right to share audio or transcripts, so no data release is planned until that is answered. We disclose the language-model involvement in building and pre-labelling. Several ethics items are written as TODO because we have not completed them.

**Suggested visual**
Simple checklist with status icons: robots.txt respected (done), delays (done), redistribution rights (TODO), privacy review (TODO), compute-terms confirmation (TODO), misuse statement (TODO).

**Sources**
paper/draft.md section 8; ROADMAP.md sections 2 (item 16), 4, 9, 10; .gitignore (audio and data/sample_A excluded).

---

### Slide 24 - Related work (abstract-level only)
**Content**
- Indian broadcast archives: Shrutilipi (Bhogale et al., 2022) mines audio-text pairs from public data including the AIR archives (PDF transcripts aligned to bulletin audio); over 6,400 hours across 12 Indian languages; built for ASR training. Our work differs in purpose and scale: English bulletins, a pilot of filtering, labelling and retrieval, not ASR training data.
- Speech recognition: Whisper (Radford et al., 2022), robust speech recognition via large-scale weak supervision; used through faster-whisper.
- Embeddings and retrieval: Sentence-BERT (Reimers and Gurevych, 2019); retrieval-augmented generation (Lewis et al., 2020); FAISS (Johnson et al., 2017, UNVERIFIED, from memory) and MiniLM (Wang et al., 2020, UNVERIFIED, from memory).
- Near-duplicate and novelty detection in news: online near-duplicate flagging by finding the most likely original (Rodier and Carter, 2020); sentence-level novelty detection in document streams (Lee, 2015); embeddings plus community detection for short news snippets (Tumre et al., 2025); incremental TF-IDF with locality-sensitive hashing (Fu et al., 2015).
- Zero-shot classification as textual entailment (Yin et al., 2019); BART denoising sequence-to-sequence pre-training (Lewis et al., 2019).
- All entries except Shrutilipi are abstract-level only, not read in full. We did not find work combining these steps for transcribed radio bulletins in a limited, non-exhaustive search [authors to confirm the search done]; this is not a claim of novelty.

**Speaker notes**
We only cite what is on our reference list, and we describe each paper only at the level of its title and abstract. Shrutilipi is closest in data source, but its goal is speech recognition training data in many languages, while ours is a small English evaluation of a text pipeline. The near-duplicate and novelty papers relate to our gate; we do not claim that our gate follows any of them. Two references, for FAISS and MiniLM, are from memory and must be checked.

**Suggested visual**
Table: reference / one-line description / where it is used in our work / reading status (read in full vs abstract only vs UNVERIFIED). Rows from paper/refs.md.

**Sources**
paper/refs.md (all 11 entries and statuses); paper/draft.md section 2.

---

### Slide 25 - Future work and the thesis plan
**Content**
- Complete the pilot evaluations: human review of 225 sentences and 100 pairs; written genre definitions; queries written and judged; five hand-typed reference transcripts; then run duplicates, retrieval, ablations and WER.
- Second annotator (a different person) on an overlap subset, so inter-annotator kappa can be reported; thesis target kappa at least 0.7 (a goal, not a result).
- Fine-tuned classifier with 5 seeds (mean and standard deviation) on leakage-filtered silver labels; BART relabelling of the store.
- Larger gold sets as thesis targets: 1,500+ genre sentences, 500+ pairs, 200+ queries, reference transcripts for about 100 bulletin minutes.
- Data: 3 months English plus 1 month Hindi (Hindi/Urdu were out of scope for the pilot).
- Retrieval: hybrid retrieval and a cross-encoder reranker only if baselines show gaps and ablations support them; context-window chunks; open-weights generator baseline.
- Scale tests at 10k, 100k and 1M segments (10k synthetic benchmark is prepared); user or case study.

**Speaker notes**
The pilot is a base for the thesis. The opening step is to finish what is already designed, because most of it is waiting for human labels. The second is to add a second annotator so agreement between people can be reported. After that come larger gold sets, a second language, and the system extensions that were left out of the pilot. The thesis numbers listed here are targets taken from the plan, not results.

**Suggested visual**
Roadmap diagram in three lanes: "finish pilot" (immediate), "strengthen evaluation" (second annotator, larger gold, seeds), "extend system" (Hindi, hybrid, reranker, scale, user study).

**Sources**
ROADMAP.md section 3 (P0/P1/P2 lists), section 6 (OUT OF SCOPE table and thesis targets), section 12 (milestones and targets); paper/draft.md section 7.

---

### Slide 26 - Conclusion
**Content**
- Built: a pilot pipeline from archive crawl to searchable store, with 2,173 listed items, 239 transcribed bulletins and two stores.
- Designed: gold sets, metrics, baselines, leakage controls and a reproducible run order, with every result file carrying its seed and input hashes.
- Measured so far: genre on 175 human-labelled sentences (four systems, with intervals); human-versus-LLM agreement (0.68 observed, kappa 0.6351); transcription speed; the gate's drop counts; the same-slot finding.
- Not measured: duplicate-detection quality, retrieval, ablations, WER, fine-tuning, scale.
- Honest status: one annotator, two test days, pilot scale; the results support the comparisons shown and no broader claim.

**Speaker notes**
The deliverable at this stage is a working, tested pipeline and an evaluation design that is ready to run, plus an initial set of real, carefully caveated numbers. The missing results are listed rather than hidden. The next work is mostly human labelling, after which the remaining tables can be filled from files.

**Suggested visual**
One-slide summary strip: Built / Designed / Measured / Pending, each with 3 to 4 short items.

**Sources**
All sources of slides 4 to 25; paper/draft.md.

---

### Slide 27 - Final project timeline
**Content**
- Pilot paper schedule (ROADMAP): Sun 1 Nov finish transcription, evaluation code, annotation start (done as code; annotation partly done); Mon 2 Nov cluster day (pipeline stages, fine-tuning, genre/dedup/retrieval evals); Tue 3 Nov cluster day (WER across sizes, ablations, 10k benchmark; ALL tables final by Tuesday night); Wed 4 Nov buffer only, no new experiments; Thu 5 Nov verify every number against results/ and submit.
- Status against that plan on 2 Nov: cluster not used; ablations, WER, dedup, retrieval not run; the genre and agreement results were produced locally.
- Open Member B items from the plan: written answers from the cluster admins; the professor's confirmation of scope and format; a second annotator.
- Thesis plan (relative weeks, calendar dates not in the files, UNVERIFIED): phase 0 week 1 fix blockers; phase 1 weeks 2-6 collect data; phase 2 weeks 4-8 annotate; phase 3 weeks 7-10 evaluation code; phase 4 weeks 9-12 baselines and ablations; phase 5 weeks 11-13 scale; phase 6 weeks 12-14 system extensions (hybrid retrieval, reranker, window chunks, only if baselines show gaps); phase 7 weeks 14-16 write and release.
- Priority if time runs short: fixes at the top, then retrieval/dedup/genre evaluations, then gold labels, then run_all.py; shrink the gold set before relaxing rigor.

**Speaker notes**
Today is Monday 2 November. The plan reserves Tuesday night as the last time any cluster job can run and Wednesday as a buffer with no new experiments, so the remaining evaluations need human inputs very soon. The thesis plan is expressed in weeks, and the files do not give start dates for it, so we do not show calendar dates. If annotation slips, the plan is to label fewer items and say so.

**Suggested visual**
Gantt chart: the pilot days 1-5 Nov (rows: transcription/eval code, annotation, cluster runs, writing, submission) with a marker for "today" at 2 Nov; below it, a week 1-16 bar for the thesis phases.

**Sources**
ROADMAP.md sections 8 (day-by-day schedule), 9 (Member B tasks), 12 (milestones and targets); date from the project environment (2026-11-02).

---

### Slide 28 - Glossary (1 of 2)
**Content**
- WER: (substitutions + deletions + insertions) divided by reference words.
- RTF: transcription time divided by audio duration (0.0568 means about 3.4 s per audio minute, derived).
- Macro-F1: the mean of per-class F1, every class counting equally; here only classes with at least 5 gold sentences.
- Cohen's kappa: agreement corrected for chance; here human versus LLM, not between two people.
- Novelty gate: drops a sentence whose cosine similarity to a kept sentence is at least 0.85.

**Speaker notes**
Keep this slide ready for questions. The terms people mix up most are kappa, which here compares a person with a model, and the gate's drop rate, which is a count and not an accuracy. Macro-F1 gives rare classes the same weight as common ones. The real-time factor is smaller for faster transcription.

**Suggested visual**
Two-column glossary table; no chart.

**Sources**
eval/asr_eval.py, eval/genre_eval.py, eval/agreement_eval.py, nlp_pipeline.py.

---

### Slide 29 - Glossary (2 of 2)
**Content**
- nDCG@5, MRR and recall@k: rank-based retrieval metrics (PENDING in this deck).
- Zero-shot: used without training on this corpus. Silver versus gold: machine-made versus human-made labels.
- Bootstrap interval: the range of a score over resampled evaluation items. "Not distinguishable on this gold set": the intervals overlap.
- Leakage: evaluation information reaching training or model selection. Whole-day split: train, validation and test by calendar day.
- Anchoring: a reviewer's labels drifting toward the labels they were shown.

**Speaker notes**
These terms support the discussion and threats slides. The retrieval metrics are defined here because their tables are still PENDING. Anchoring is the reason the reviewed labels are kept apart from the from-scratch labels. Leakage and the whole-day split explain why the sample was cut by days.

**Suggested visual**
Two-column glossary table; no chart.

**Sources**
eval/retrieval_eval.py, eval/eval_config.py, paper/draft.md sections 5.2, 5.5, 5.6.

---

# Likely questions from a strict professor, with honest answers

1. **Is 0.43 macro-F1 good?**
   We cannot say in absolute terms: there is no external reference score and no human ceiling (one annotator, no inter-annotator kappa). What the files show is that the two zero-shot backends score 0.4333 and 0.4334 on 175 sentences, their intervals overlap, and both lie above the majority (0.0284) and TF-IDF + LR (0.1109) baselines. Source: results/genre_eval_20261101T180912Z.json.

2. **Is BART better than the fast model?**
   Not distinguishable on this gold set: macro-F1 0.4334 [0.3478, 0.4987] versus 0.4333 [0.3450, 0.5119], and the accuracy intervals overlap too. Per-class differences (for example Sports, Environment) also come with overlapping intervals.

3. **Why does BART never predict Society & Culture?**
   It assigned 0 of 175 sentences to that label and sent 14 of the 17 human-labelled Society & Culture sentences to `Other`. We have not investigated the cause; a link to label wording is an untested guess (UNVERIFIED).

4. **What does kappa 0.6351 mean?**
   Agreement between the human labels and the LLM labels on the same 175 sentences, corrected for chance, with interval [0.5559, 0.7085]. It is not annotator reliability, because one rater is a model and there is no second human.

5. **Why not treat the LLM labels as gold?**
   The LLM also built the sampling sheets and its labels carry its own biases; using them as gold would measure a model against a model. Gold is the human's from-scratch labels only.

6. **Does the 55.2% drop rate mean 55% of sentences are duplicates?**
   No. It counts what the gate dropped at 0.85 (5,255 of 9,519). Whether the dropped sentences are true repeats is unmeasured until the labelled-pair evaluation runs (PENDING).

7. **Why are dedup, retrieval, ablations and WER missing?**
   They need human inputs that do not exist yet: reviewed pair labels, written and judged queries, hand-typed reference transcripts. The code is written and tested on synthetic data only, and the tables are marked PENDING rather than estimated.

8. **Are tiny or base worse than small?**
   Unknown; only speed was measured (tiny RTF 0.0193 to 0.0224, base 0.0250 to 0.0304 on five bulletins, one run). Accuracy needs the WER evaluation.

9. **Is the store's genre column reliable?**
   Its source, the fast backend, scored 0.4333 macro-F1 on 175 gold sentences. That is the only measure we have, and it is not a measure on the 4,264 stored segments (UNVERIFIED that it carries over).

10. **Can the results generalise?**
    Not from this evidence: two test days, one broadcaster, English only, one annotator, one 3-month window. We state this in the limitations.

11. **Why no statistical test?**
    The gold sets are small and the comparisons are many; we report 95% bootstrap intervals and say "not distinguishable on this gold set" when they overlap. No claim goes beyond what the intervals show.

12. **What about leakage, given the gate ran across splits?**
    The split is by whole day and training-day segments identical to gold or validation/test text were removed (17 of 2,520). But the gate itself saw all splits, so gold sentences can be dropped from the store; the retrieval evaluation maps them explicitly. Source: results/genre_eval_20261101T180912Z.json; ROADMAP.md section 8c.

13. **Why do the two speed measurements for small differ (0.067 and 0.0568)?**
    The 0.067 comes from a two-file test with warm-up included; 0.0568 is the whole 239-bulletin sample. We use the whole-sample figure for throughput. Source: ROADMAP.md sections 5 and 8a.

14. **Could same-slot files be duplicates?**
    In option A they are not: 9 of 9 pairs differ in hash, duration (2.98 to 11.42 s) and transcript (Jaccard 0.0008 to 0.0388). The rest of the archive is unverified. Source: results/duplicate_pairs_check.json.

15. **Can you release the data?**
    Not yet. Redistribution rights for AIR audio and transcripts are unresolved, and a privacy review is outstanding. The repository does not contain audio.

16. **What would you do with one more week?**
    Human review of the 225 sentences and 100 pairs, write and judge the queries, type the five reference transcripts, then run the duplicate, retrieval, ablation and WER evaluations and fill the tables from the result files. A second annotator would come next.

17. **Was any evaluation run by accident?**
    Once: an old test started the real agreement script after the human labels existed. The output was never read and was deleted, the test was replaced by one that forbids that, and the real run came afterwards with the same seed. Source: ROADMAP.md section 8h.
