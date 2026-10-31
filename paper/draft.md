<!--
SKELETON ONLY. Pilot paper draft for AirInsight (VaniStream).
Conventions used in this file:
- Every number in the text is read from a saved file; the file path is in an HTML comment next to it.
- TODO = not yet measured, decided or written. UNVERIFIED = inferred or stated from memory/a screenshot, not confirmed.
- No evaluation result appears anywhere. All Results tables are empty on purpose.
- No references have been invented; Related Work holds headings only.
-->

# AirInsight: a pilot study of streaming novelty filtering and two-tier retrieval over All India Radio news bulletins

TODO: final title, author names, affiliations.

## Abstract

<!-- Abstract intentionally left empty. -->

## 1. Introduction

<!-- Contribution statement taken from ROADMAP.md section 6 ("Thursday pilot paper"). -->
This paper reports a pilot-scale, human-reviewed evaluation of a pipeline that turns news bulletins from All India Radio (AIR) into a searchable store: speech recognition, sentence segmentation, a streaming novelty gate that drops near-duplicate sentences, genre labelling, and two-tier retrieval (a metadata prefilter followed by vector search) feeding an answer generator. The full dataset and large-scale evaluation are future work.

TODO: motivation paragraph. A working hypothesis, UNVERIFIED and not tested here, is that AIR repeats the same stories across bulletins within a day, which makes redundancy a practical problem for retrieval over such a stream. <!-- The archive listing is dominated by hourly bulletins: 1,896 of 2,173 listed items, data/metadata_3month_english.csv -->

TODO: research questions (to be fixed before any result is looked at). Candidate wording, not yet agreed:
1. TODO: how well do the gold genre labels agree with the project's genre backends and with simple baselines?
2. TODO: at which cosine threshold does the novelty gate separate duplicate from non-duplicate sentence pairs on labelled pairs, and how do simple baselines compare?
3. TODO: how do the retrieval variants (BM25, vector-only, date prefilter, full system) rank judged-relevant sentences?
4. TODO: how does Whisper size affect word error rate on hand-corrected bulletins?

TODO: contributions list (to be written after the results exist; no claim is made in this skeleton).
TODO: paper outline paragraph.

## 2. Related Work

TODO: citations to be added by the authors. Headings only.

### 2.1 Speech recognition for broadcast news
### 2.2 Near-duplicate detection and novelty filtering in text streams
### 2.3 Retrieval over spoken or transcribed news, and retrieval-augmented generation
### 2.4 News genre and topic classification
### 2.5 LLM-assisted annotation and its risks

## 3. Data

### 3.1 The AIR audio archive and how it was scraped

The AIR website exposes an archive of audio bulletins that is loaded through an AJAX call returning HTML fragments, 12 items per page. <!-- ROADMAP.md section 4, "S3 RESULT" (12 items per page, confirmed by the S3 test) --> Each item has a title, a date and a direct `.mp3` URL; the page does not give the time of day, so the broadcast hour is parsed from the file name (first standalone four-digit HHMM group; hour is HHMM divided by 100, or empty and flagged when the name has no valid time). <!-- ROADMAP.md section 4; rule in air_bulletins_scraper.py, function parse_hour_from_url -->

The date filter treats both bounds as exclusive, so each crawl window is queried from the day before its first day to the day after its last day. <!-- ROADMAP.md section 4, S3c result and "Window rule" (inferred from four probes, then consistent with the S1 and S3d crawls) -->

We crawled listing metadata only (no audio) for 2026-08-01 to 2026-10-31 in 14 weekly windows. <!-- ROADMAP.md section 4 "S3d RESULT"; data/metadata_3month_english.csv (window column: 14 distinct values) --> The listing holds 2,173 distinct audio URLs over 92 days. <!-- data/metadata_3month_english.csv: 2,173 rows, 92 distinct dates, 2026-08-01 to 2026-10-31 --> Titles: Hourly News 1,896; Midday News 92; Morning News 92; Evening News 87; News At Nine 2; four items titled in Hindi or Urdu. <!-- data/metadata_3month_english.csv, title column --> The broadcast hour could be parsed for 2,030 items; 143 were flagged (141 with no time in the file name, 2 with an invalid time). <!-- data/metadata_3month_english.csv, hour and hour_flag columns --> 31 October 2026 was still in progress when crawled and is treated as incomplete. <!-- ROADMAP.md section 4, S3d "Unusual days" -->

Crawling followed the site's robots.txt (checked on 31 Oct 2026; it allowed all paths at that time, and the scraper stops if a path is disallowed) with a randomised delay of 1 to 3 seconds between requests. <!-- ROADMAP.md section 2 item 16 (robots.txt check); air_bulletins_scraper.py lines 954-955, --min-delay 1.0, --max-delay 3.0 -->

TODO: the total archive size is UNVERIFIED (a screenshot showed 1,686 pages; the full archive was not crawled). TODO: the "Daily Broadcast" tab and the site's text-archive pages were not examined.

### 3.2 The option A sample

Audio was downloaded and transcribed only for a sample of whole days. The pool is the 91 complete days from 2026-08-01 to 2026-10-30 after removing 31 October and the four non-English items, 2,153 items in all. <!-- ROADMAP.md section 8a "Pool"; config/sample_config.json, pilot_plan_s4.exclusions --> Days were drawn with a fixed seed of 42, stratified by month and by weekday versus weekend, with the rule that no two chosen days are consecutive calendar days. <!-- config/sample_config.json, pilot_plan_s4.seed and pilot_plan_s4.rule --> The sample used here, "option A", has 10 days: 2026-08-10, 08-16, 08-28, 09-03, 09-06, 09-30, 10-19, 10-21, 10-24 and 10-27. <!-- config/sample_config.json, pilot_plan_s4.option_A_about_10_days.days --> It holds 239 bulletins, 209 hourly and 30 Morning, Midday, Evening or News At Nine. <!-- config/sample_config.json, option_A summary: items 239, hourly_items 209, non_hourly_items 30; data/sample_A/metadata.csv, 239 rows --> TODO: the days are fixed by a rule and a seed, not by hand; the paper must say why 10 days were chosen (time budget for annotation and transcription) and that this is a pilot.

### 3.3 Split by whole days

Training, validation and test sets are made of whole days, never of sentences or hours, because adjacent hourly bulletins overlap in content. <!-- ROADMAP.md section 8a "Fixed seeded rule" --> The split is train 6 days (144 bulletins), validation 2 days (48 bulletins: 2026-08-16 and 2026-10-24), test 2 days (47 bulletins: 2026-08-28 and 2026-09-06). <!-- config/sample_config.json, option_A split; data/sample_A/metadata.csv split column: train 144, val 48, test 47 --> Gold annotation is drawn from the validation and test days only; the training days are used for silver (machine-labelled) training data only. <!-- ROADMAP.md section 8b "Leakage rule" --> Consequence stated plainly: the test set is two days, so results can reflect the stories of those two days.

### 3.4 Duplicate-slot files

Within the archive, two different audio files sometimes carry the same date and the same HHMM in their names (124 such date-and-time pairs in the 3-month listing). <!-- ROADMAP.md section 4, "Same-time duplicates (measured in S3d ...)" --> Inside option A there are 9 such pairs on 8 of the 10 days. <!-- config/sample_config.json, option_A summary: duplicate_slot_pairs 9, days_with_a_duplicate_slot_pairs 8; results/duplicate_pairs_check.json, n_pairs 9 -->

We compared the two files of every pair. In all 9 pairs the SHA-256 values differ (0 identical), the durations differ by 2.98 to 11.42 seconds, and the word 5-gram Jaccard similarity of the transcripts is between 0.0008 and 0.0388. <!-- results/duplicate_pairs_check.json: sha256_equal false for all 9 pairs; duration_diff_s min 2.98, max 11.42; jaccard_word_5grams min 0.0008, max 0.0388 --> With the thresholds we chose (a label of "different text" below a Jaccard of 0.3), all 9 pairs are labelled different. <!-- results/duplicate_pairs_check.json: thresholds_our_choice.different_if_jaccard_below 0.3; label_counts {"different text": 9} --> All 9 pairs are in the 01:05 and 03:05 night slots. <!-- results/duplicate_pairs_check.json, hhmm field of each pair --> So, in this sample, same-slot files are different recordings and not re-uploads; they are not treated as duplicates of each other. Whether this holds for other slots, other months or the rest of the archive is UNVERIFIED.

### 3.5 Speech recognition

All 239 option A bulletins were transcribed with faster-whisper, model `small`, on GPU in float16, with voice-activity detection left at the library default (off). <!-- data/sample_A/metadata.csv: whisper_model small, device cuda, compute_type float16 for all 239 rows --> The audio totals 1,441.3 minutes (24.02 hours). <!-- data/sample_A/metadata.csv, sum of duration_s; ROADMAP.md section 8a "S5 results" --> Transcription took 81.9 minutes (82.2 minutes wall time including one model load), a real-time factor of 0.0568, on a laptop with an NVIDIA RTX 2050 (4 GB). <!-- ROADMAP.md section 8a "S5 results" (from data/sample_A/transcribe_log.txt, not committed); hardware: ROADMAP.md section 5 -->

TODO: transcription quality is not measured until the hand-corrected references exist (see Section 5.2). TODO: Whisper tiny and base hypotheses exist for five bulletins; their word error rates are not computed.

## 4. System

### 4.1 Ingest

Transcripts are processed in order of date, then broadcast hour (bulletins without a parsed hour last), then file name. The broadcast hour is stored as 0 to 23, or as NULL with a flag when the file name has no valid time; it is never stored as 0 for "unknown". Every stored segment also carries its day-level split. <!-- ingest_pipeline.py (_extract_hour_and_flag, run with sort_rows); vector_store.py (hour_flag and split columns); ROADMAP.md section 8d -->

### 4.2 Segmentation and embedding

Transcripts are cut into sentences with NLTK's punkt tokenizer and each sentence is embedded with all-MiniLM-L6-v2 (384 dimensions). <!-- nlp_pipeline.py: segment_sentences, EMBEDDING_MODEL "all-MiniLM-L6-v2" --> Chunks are single sentences; windows or paragraphs are not used.

### 4.3 Novelty gate

Sentences are processed in a stream. A sentence is dropped when its cosine similarity to any stored or already-accepted sentence is at least 0.85; otherwise it is kept and added to the pool. <!-- nlp_pipeline.py: DEFAULT_MMR_THRESHOLD 0.85, mmr_novelty_filter_detailed --> The 0.85 value was fixed before any labelled data existed and is not tuned in the pipeline; the dedup evaluation (Section 5) examines other thresholds on validation pairs. <!-- ROADMAP.md section 2 item 4 ("one fixed threshold (0.85), no justification") -->

On option A the gate was applied across all splits in processing order. It read 9,519 sentences (train 5,560; validation 1,981; test 1,978) and kept 4,264 (train 2,520; validation 879; test 865). <!-- results/store_reports/store_A_build_report.json: sentences_before_gate, sentences_after_gate (committed copy, identical by SHA-256 to store_A/build_report.json; ROADMAP.md section 8c) --> This is a count of what the gate did, not a measure of whether its decisions were right. Because the gate is order dependent and runs across splits, a validation or test sentence can be dropped because of an earlier training-day sentence. <!-- ROADMAP.md section 8c "Choices and caveats" --> For ablation, a store built with the gate off keeps all 9,519 sentences. <!-- results/store_reports/store_A_nodedup_build_report.json: segments_in_store 9519, threshold 1.01 (gate off) -->

### 4.4 Genre classification

Each sentence receives one of ten labels: Politics, Economy, Science & Technology, Sports, International, Defence & Security, Health, Environment, Society & Culture, Other. <!-- nlp_pipeline.py: GENRE_LABELS --> Three backends exist: zero-shot classification with facebook/bart-large-mnli, a faster zero-shot cross-encoder (cross-encoder/nli-MiniLM2-L6-H768), and a DistilBERT classifier fine-tuned on silver labels. <!-- nlp_pipeline.py: DEFAULT_CLASSIFIER_MODEL, FAST_CLASSIFIER_MODEL; train_genre_classifier.py: DEFAULT_MODEL_NAME distilbert-base-uncased --> The genre column of the option A store comes from the fast backend, chosen for speed on CPU; these labels are silver and their quality is UNVERIFIED. <!-- results/store_reports/store_A_build_report.json: classifier_backend "fast"; ROADMAP.md section 8c (BART measured at 1.65 s per sentence against 0.18 s for the fast backend on 24 sentences) --> TODO: no fine-tuned checkpoint exists yet, so no fine-tuned result can be reported.

### 4.5 Two-tier retrieval and answer generation

A query first passes through regular-expression date parsing and keyword genre extraction; these select candidate segments in SQLite (date range, genre). A vector search over the candidates (flat inner-product index on unit vectors) returns the top results, and a relevance filter then drops weak matches. <!-- rag_engine.py: answer_query, _parse_date_range, _extract_genre; vector_store.py: metadata_prefilter, semantic_search --> The relevance filter returns nothing when the best score is below 0.20 and otherwise keeps scores of at least the larger of 0.20 and 0.65 times the best score; generic news queries use a floor of 0.05. <!-- rag_engine.py: _filter_by_relevance --> A language model (Gemini) writes the answer from the retrieved sentences, with an extractive fallback. <!-- rag_engine.py: _generate_with_gemini; ROADMAP.md section 1 item 10 --> The model name is hard-coded and may be retired (UNVERIFIED). <!-- ROADMAP.md section 2 item 10 --> TODO: answer quality is evaluated only by a small human check (Section 5.1); no automatic answer-quality metric is used.

## 5. Evaluation Protocol

### 5.1 Gold sets (pilot scale)

All gold material is drawn from the validation and test days only.

- **Genre sheet.** 400 sentences, 100 from each of 2026-08-16, 2026-08-28, 2026-09-06 and 2026-10-24, drawn at random within each day (seed 42) from sentences of at least four words, using the project's own segmentation, and not stratified by any model prediction. <!-- data/gold/genre_sheet_annotator1.csv: 400 rows, 100 per date; ROADMAP.md section 8b; data/gold/build_gold_sheets.py (SEED = 42, MIN_WORDS = 4) --> The sampling pool had 3,903 sentences from 95 bulletins. <!-- ROADMAP.md section 8b; data/gold/valtest_sentence_index.csv: 3,903 rows -->
- **Overlap subset.** 175 of the 400 sentences, in a different random order. <!-- data/gold/genre_sheet_annotator2_overlap.csv: 175 rows; per day 47, 42, 38, 48 -->
- **Pair sheet.** 100 sentence pairs from different bulletins of the same day, drawn across cosine bands from 0.60 to 0.95 plus 20 random low-similarity pairs, 25 per day. <!-- data/gold/duplicate_pairs_sheet.csv: 100 rows; ROADMAP.md section 8b (bands, 16 per band, 20 negatives, 25 per day) --> Each sentence is used in at most one pair, and the similarity score is kept in a separate hidden key file. Pairs from the two files of a duplicate slot are not used.
- **Query sheet.** 50 rows for queries with relevance judgments. <!-- data/gold/query_sheet.csv: 50 rows --> TODO: queries not yet written; final count to be stated.
- **ASR references.** TODO: five bulletins listed in Section 5.2.

TODO: a human check of about 30 generated answers, reported as a small check and not as a benchmark. <!-- ROADMAP.md section 6 -->

### 5.2 Annotation procedure

**Who did what.** The sampling sheets (genre, pair, query templates) were built with code written by an LLM assistant. <!-- ROADMAP.md section 8b; model identity for this earlier work: the commit trailers name Claude Sonnet 5.5 from the first commit on; for work before that commit this is UNVERIFIED --> The genre sheet and the pair sheet were then pre-labelled by an LLM: Claude Sonnet 5.5, on 2026-10-31, in one pass, using only the sentence text and the label descriptions in `data/gold/README.md`, with no access to model predictions, silver labels, similarity scores, the hidden key file or human labels. <!-- data/gold/llm/PROVENANCE.md (model, date, files read, statement) --> A human then reviewed and corrected every LLM label. TODO: number of genre labels changed by the human: [N_GENRE_CORRECTIONS] of 400; number of pair labels changed: [N_PAIR_CORRECTIONS] of 100; per-class change table [TODO]. Only the human-reviewed labels are gold; the LLM labels are never scored as gold.

**From-scratch overlap.** The 175-sentence overlap was labelled by the human from scratch, before the human saw the LLM labels. TODO: confirm which column of which file holds these labels (`eval/agreement_eval.py` assumes `annotator_2_label` in the overlap sheet; change with `--overlap-col`). Agreement with the LLM is reported as human-versus-LLM agreement (`eval/agreement_eval.py`, output named `human_vs_llm_agreement`), and it is NOT inter-annotator kappa. The 225 sentences the human only reviewed are reported separately and flagged as inflated by anchoring, so only the from-scratch overlap is an independent comparison. `eval/genre_eval.py` computes `inter_annotator_kappa` only when run with `--two-humans`, which must be passed only if the two label columns come from two different people; TODO: whether a second human annotates anything (not planned in this draft).

**Pair labels.** same: the same fact in nearly the same wording; paraphrase: the same fact in different wording; follow-up: the same story with new or updated information; different: a different fact. <!-- data/gold/llm/PROVENANCE.md (definitions given for the LLM pass) --> The LLM read "follow-up" at the level of the story, so the boundary between follow-up and different is the least certain part. <!-- ROADMAP.md section 8f; data/gold/llm/PROVENANCE.md --> TODO: state whether the human used the same definitions.

**The "Other" label.** The LLM pre-labels use `Other` for bulletin boilerplate (sign-offs, headline announcements, newsreader names, fragments with no usable context) and for accident, collapse, fire and crime stories, which have no genre of their own in the label set; `Other` is therefore inflated by boilerplate and accident stories. <!-- data/gold/llm/PROVENANCE.md (rules applied); ROADMAP.md section 8f --> TODO: report the share of `Other` in the final human-reviewed gold labels.

**Genre label descriptions.** The project code defines only the label names; the descriptions given to annotators are the keyword hints of the project's keyword map. <!-- data/gold/README.md --> TODO: written definitions for the ten genres.

**Queries.** TODO: the queries are written by a human. An LLM produced 80 draft queries for the human to select and edit; the draft file contains no relevance judgments. <!-- data/gold/llm/query_candidates_draft.csv: 80 rows --> TODO: relevance judging uses candidates from a helper script that merges embedding and TF-IDF rankings; this pooling can favour retrievers similar to those two rankers (UNVERIFIED effect).

**ASR references.** The reference transcripts for five bulletins (English-0105-0110-9, English-1505, English-1905-1, morninng, Midday-News) are typed by a human from the audio, not copied from any Whisper output. <!-- config/sample_config.json, pilot_plan_s4.asr_wer_candidates_from_option_A_test_days --> TODO: not yet written; annotator identity and time spent to be recorded.

### 5.3 Metrics

- **Genre.** Macro-F1 over classes with at least 5 gold examples, per-class precision, recall and F1 with support, accuracy and the confusion matrix; classes with fewer than 5 gold examples are reported as "insufficient support". <!-- eval/eval_config.py: MIN_CLASS_SUPPORT = 5; eval/genre_eval.py -->
- **Duplicate detection.** Precision, recall and F1 at each cosine threshold from 0.60 to 0.95 in steps of 0.01. The positive class is same plus paraphrase (primary); the alternative counts only same as positive and is also reported. The threshold is chosen on validation-day pairs (best F1, ties to the higher threshold) and reported on test-day pairs. <!-- eval/eval_config.py: DEDUP_THRESHOLDS; eval/dedup_eval.py -->
- **Retrieval.** Recall@1, 3, 5 and 10, mean reciprocal rank and nDCG@5 with binary relevance, over the top 20 results of each system. <!-- eval/eval_config.py: RETRIEVAL_KS (1, 3, 5, 10), NDCG_K 5, RETRIEVAL_DEPTH 20 --> Relevant sentences are judged on raw sentences and mapped to segments of the store: exactly by text, otherwise to the kept segment that caused the sentence's rejection, otherwise reported as unmapped. <!-- eval/retrieval_eval.py (docstring) -->
- **ASR.** Word error rate with substitutions, deletions and insertions, per file and overall, after lowercasing, removing punctuation and apostrophes; numbers are not converted between digits and words, which makes the rate pessimistic where references and Whisper differ in style. <!-- eval/asr_eval.py (docstring, NORMALISATION) -->
- **Agreement.** Human-versus-LLM agreement: observed agreement, Cohen's kappa, per-label counts and confusion matrix with 95% bootstrap intervals, for the from-scratch overlap and, flagged, for the reviewed remainder (Section 5.2). <!-- eval/agreement_eval.py; eval/eval_config.py: BOOTSTRAP_RESAMPLES 1000, SEED 42 -->
- **Multiple seeds.** Anything trainable is run with 5 seeds (42 to 46) and reported as mean and sample standard deviation. <!-- eval/eval_config.py: SEEDS_FOR_MULTI_RUN -->

### 5.4 Baselines and ablations

- **Genre:** majority class and TF-IDF with logistic regression (both trained only on training-day silver labels and scored only on gold); the project's fast and BART zero-shot backends; fine-tuned classifiers trained on training-day silver labels (5 seeds). <!-- eval/genre_eval.py (docstring) -->
- **Duplicates:** exact string match, normalised-text match, TF-IDF cosine, word 5-gram Jaccard, and a MinHash estimate (word 3-gram shingles, 128 permutations, seed 42). <!-- eval/dedup_eval.py; eval/eval_config.py: MINHASH_SHINGLE_WORDS 3, MINHASH_PERMUTATIONS 128 -->
- **Retrieval:** BM25, vector-only, date prefilter plus vector, and the full system; ablation switches turn off the prefilter, the relevance filter and the novelty gate (the last uses a separate store built with the gate off). <!-- eval/retrieval_eval.py (docstring and flags) -->
- **ASR:** Whisper tiny, base and small; larger sizes are prepared for the cluster and not run. <!-- eval/eval_config.py: ASR_MODELS; cluster/03_asr_sizes.sbatch -->

### 5.5 Leakage controls

- Split by whole days; gold only from validation and test days; training days feed silver training only. <!-- ROADMAP.md section 8b -->
- Silver training sentences identical (after normalisation) to any gold, validation or test sentence are removed before training. <!-- eval/finetune_genre.py (leakage_filter) -->
- Thresholds and models are chosen on validation data and reported on test data; gold labels are never used for training.
- The pair similarity scores live in a separate hidden key file that annotators did not see. <!-- ROADMAP.md section 8b -->
- Known gaps: the novelty gate ran across splits; gold sentences were sampled from raw sentences and not from the post-gate store; an older fine-tuned checkpoint, if one is ever found, has unknown training data (UNVERIFIED). <!-- ROADMAP.md sections 8c and 8d -->

### 5.6 Confidence intervals

Intervals are 95% percentile bootstrap intervals with 1000 resamples and seed 42, resampling sentences, pairs or queries. <!-- eval/eval_config.py: BOOTSTRAP_RESAMPLES 1000, SEED 42 --> No statistical test is run, so no claim of a statistical difference between systems is made. With about 50 pairs per split or about 50 queries the intervals will be wide.

## 6. Results

All tables below are EMPTY. Each is filled from one saved result file by the command in Section 9. TODO: fill them only from those files; write no number by hand.

### Table 1. Genre classification on the gold sheet
Source: `results/genre_eval_*.json`

| System | Category | n (gold) | Macro-F1 | Macro-F1 95% CI | Accuracy | Accuracy 95% CI | Classes scored | Classes with insufficient support |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

### Table 2. Genre classification, per class
Source: `results/genre_eval_*.json`

| System | Class | Support | Precision | Recall | F1 | F1 95% CI |
|---|---|---|---|---|---|---|
| | | | | | | |

### Table 3. Genre classification, trainable systems over 5 seeds
Source: `results/genre_eval_*.json`

| System | Seeds | Macro-F1 mean | Macro-F1 std | Accuracy mean | Accuracy std | Training examples |
|---|---|---|---|---|---|---|
| | | | | | | |

### Table 4. Agreement between the human labels and the LLM pre-labels (not inter-annotator kappa)
Source: `results/human_vs_llm_agreement_*.json` (reported separately for the from-scratch overlap and for the reviewed remainder)

| Group | Items compared | Observed agreement | Observed agreement 95% CI | Cohen's kappa (human vs LLM) | Kappa 95% CI | Human corrections of LLM labels |
|---|---|---|---|---|---|---|
| overlap, human from scratch | | | | | | |
| remainder, human reviewed (inflated by anchoring) | | | | | | |

### Table 5. Duplicate-pair detection
Source: `results/dedup_eval_*.json`

| Method | Positive class definition | Threshold chosen on validation | Validation F1 | Test precision | Test recall | Test F1 | Test F1 95% CI | Validation pairs | Test pairs |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

### Table 6. Mapping of gold-relevant sentences to store segments
Source: `results/retrieval_eval_*.json`

| Distinct relevant sentences | Mapped by exact text | Mapped via gate rejection | Unmapped | Queries evaluated | Queries skipped |
|---|---|---|---|---|---|
| | | | | | |

### Table 7. Retrieval
Source: `results/retrieval_eval_*.json`

| System | Queries | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | nDCG@5 |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

(each cell to include its 95% CI)

### Table 8. Retrieval ablations of the full system
Source: `results/retrieval_eval_ablation_*.json`

| Prefilter | Relevance filter | Novelty gate | Queries | Recall@1 | Recall@5 | Recall@10 | MRR | nDCG@5 |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

### Table 9. Word error rate by Whisper size
Source: `results/asr_eval_*.json`

| Model | Bulletin | Reference words | Substitutions | Deletions | Insertions | WER |
|---|---|---|---|---|---|---|
| | | | | | | |
| | overall | | | | | |

### Table 10. Transcription speed by Whisper size
Source: `data/asr_hyp/transcribe_log.json` (not committed; one run per model, first file includes model load)

| Model | Device and precision | Audio (s) | Transcription time (s) | Real-time factor | GPU memory peak (MiB) |
|---|---|---|---|---|---|
| | | | | | |

### Table 11. Scale benchmark (synthetic vectors; measures speed, not quality)
Source: `results/scale_benchmark_n10000_*.json`

| Segments | Index build (s) | Unfiltered query latency p50 / p95 (ms) | Prefiltered query latency p50 / p95 (ms) | Novelty gate time (s) | Peak memory (MB) | Host |
|---|---|---|---|---|---|---|
| | | | | | | |

## 7. Limitations

<!-- Collected from ROADMAP.md sections 2, 3, 4, 6, 7, 8a to 8f and 10. -->
<!-- Numbers repeated in this section (10 days, 239 bulletins, 2 test days, about 400 / 175 / 100 / about 50 / 5 gold items, four Hindi or Urdu items) are sourced where they first appear in Sections 3 and 5: config/sample_config.json, data/sample_A/metadata.csv, data/gold/*.csv, data/metadata_3month_english.csv. -->

Scale and design
- The corpus is small: a 10-day sample of 239 bulletins from one 3-month window, and only 2 test days; results can reflect the stories of those days.
- The gold sets are pilot scale (about 400 genre sentences, 175 overlap sentences, 100 pairs, about 50 queries, 5 ASR bulletins) and must be called pilot wherever they appear.
- Chunks are single sentences; context windows were not tried.
- English only. Hindi and multilingual support are out of scope; segmentation, embeddings, genre keywords, prompts and labels are English-only, and four Hindi or Urdu items were removed from the English pool.
- One genre per sentence; no multi-label genres or story clustering.
- Date parsing is by regular expressions and genre extraction by keyword lists (ties return nothing); forms such as "this week", "last year" or "in March" are missing, and a year left out silently uses the anchor year.
- No cross-encoder reranker, no open-weights generator baseline, no user study and no learned query understanding.
- Answer quality is checked only by a small human check, not by a benchmark; the generator can produce statements the retrieved sentences do not support (hallucination risk), and it is a closed model whose name is hard-coded and may be retired (UNVERIFIED).

Speech recognition
- ASR errors propagate into every later stage. Transcription quality is not yet measured (no references yet); word error rate normalisation does not convert numbers between digits and words.
- Whisper timings come from one run on one laptop GPU (RTX 2050, 4 GB); speeds on other hardware, on longer bulletins or on the cluster are unmeasured; medium and larger sizes are not tested.
- Sentence timestamps for archive bulletins are empty (live ingestion aligns sentences heuristically).

Novelty gate and labels
- The gate uses one fixed threshold (0.85) that was not tuned before the evaluation; it catches near-identical sentences, not paraphrases or follow-ups; it is order dependent and ran across all splits.
- The store's genre labels are silver (fast zero-shot backend) and of unverified quality; the fine-tuned classifier has only silver training labels, and no checkpoint exists yet.
- The broadcast hour is missing for 710 segments (Morning, Midday, Evening and News At Nine bulletins and some others without a time in the file name). <!-- results/store_reports/store_A_build_report.json: null_hour_total 710 -->
- The duplicate-slot finding covers option A only.
- The pair sheet is sampled across similarity bands, so precision and recall on it describe that sample, not deployment.

Annotation
- The genre and pair labels began as one LLM pass by a single model that also built the sampling sheets; they are gold only after human review, and the review may be influenced by the LLM labels (anchoring).
- Agreement with the LLM is not inter-annotator agreement; TODO: whether a second human annotated anything (inter-annotator kappa is computed only with `--two-humans`).
- `Other` is inflated by boilerplate and accident stories; Science & Technology and Health have few sentences, so several per-class scores will be reported as insufficient support.
- The follow-up versus different boundary for pairs is subjective.
- Relevance judging uses pooled candidates from two rankers, which may favour similar retrievers; gold-relevant sentences that the gate dropped are mapped to the sentence that caused the drop.

Data source and legal
- The archive's total size is unverified; the Daily Broadcast tab and the text-archive pages were not examined.
- Licensing and redistribution rights for AIR audio and transcripts are unresolved (TODO); government-content licensing must be settled before releasing data.

Engineering
- Live-stream ingestion is limited to one stream at a time, with in-memory chat sessions, no authentication, a new SQLite connection per call and a full rewrite of the vector index on each add; it was not run end to end after the latest changes (UNVERIFIED), and its compute type is still hard-coded.
- The scale benchmark uses synthetic vectors at 10,000 segments only; 100,000 and 1,000,000 segments were not run.
- The cluster scripts were never submitted and were not compared with the cluster's own template; internet access, ffmpeg and CUDA libraries on the cluster nodes are unknown.
- Tests are a local pytest suite; there is no continuous integration.

## 8. Ethics and licensing

- **Source.** Public radio news from the official AIR website. Requests respected robots.txt and used a 1 to 3 second randomised delay (Section 3.1). Audio files are not stored in the project repository. <!-- .gitignore excludes audio and data/sample_A -->
- **Redistribution.** TODO: confirm with AIR / Prasar Bharati whether audio or transcripts may be shared. The annotation sheets contain sentences of transcripts, so the same question applies to them; do not publish them before it is answered.
- **People.** Bulletins name public officials, newsreaders and, in some stories, private individuals; TODO: privacy review before any data release.
- **Annotators and LLM use.** The annotators are members of the project group. An LLM pre-labelled the annotation sheets, and its use is disclosed in Section 5.2.
- **Compute terms.** Cluster use is limited to the approved task; TODO: written confirmation. <!-- ROADMAP.md section 10 -->
- **Dual use and harm.** TODO: statement on misuse of searchable broadcast transcripts and on the risk of generated answers presenting unsupported claims as fact.

## 9. Reproducibility

- **One command** (resumable; stops with a message at any stage whose gold labels are missing): `.venv_gpu/Scripts/python.exe run_all.py --stage all`; `run_all.py --list` shows the state of each stage. Stages: ingest, genre, dedup, retrieval, asr. <!-- run_all.py (docstring) --> The ingest stage uses the fast genre backend by default.
- **Individual scripts:** `build_store_A.py` (store; `--no-gate --store-dir store_A_nodedup` for the ablation store), `eval/genre_eval.py`, `eval/dedup_eval.py`, `eval/retrieval_eval.py`, `eval/asr_transcribe.py` and `eval/asr_eval.py`, `eval/finetune_genre.py`, `eval/scale_benchmark.py`, and cluster jobs in `cluster/`. Each evaluation writes `results/<name>_<timestamp>.json` with the seed and the SHA-256 of every input file. <!-- eval/eval_common.py: write_result -->
- **Seeds:** 42 for day selection, gold sampling, bootstrap and MinHash; 42 to 46 for multi-seed runs. <!-- config/sample_config.json (seed 42); eval/eval_config.py: SEED, SEEDS_FOR_MULTI_RUN -->
- **Environment:** Python 3.11.9 in `.venv_gpu`; faster-whisper 1.2.1 and ctranslate2 4.8.4 for transcription; faiss-cpu 1.15.0; the PyTorch in `.venv_gpu` is a CPU build (2.14.0), so genre classification and embeddings ran on CPU. <!-- ROADMAP.md section 5 (versions); requirements.txt (faiss-cpu==1.15.0); ROADMAP.md section 8c (CPU torch) --> TODO: full `pip freeze` to be saved next to the paper.
- **Hardware:** laptop NVIDIA GeForce RTX 2050 (4 GB) for scraping, transcription and development. <!-- ROADMAP.md section 5 -->
- **Code and data availability:** the project is a git repository; TODO: record the commit hash at submission. Audio, the sampled audio folder and the built stores are not committed; the listing `data/metadata_3month_english.csv`, the option A configuration `config/sample_config.json`, the gold sheets and the LLM files under `data/gold/llm/` are. <!-- .gitignore; data/metadata_3month_english.csv -->
- **Tests:** TODO: number of passing tests at submission (run `pytest tests`).
