<!--
Pilot paper draft for AirInsight (VaniStream).
Conventions: every number is read from a saved file in the repository and the path sits in an HTML comment next to it.
TODO = not yet measured, decided or written. UNVERIFIED = inferred or from memory, not confirmed.
References are listed in paper/refs.md (11 entries; no others). In-text keys are (Author, Year).
Tables for the duplicate-pair evaluation, retrieval, ablations, word error rate and the scale benchmark are left empty on purpose.
-->

# AirInsight: a pilot study of streaming novelty filtering, genre labelling and two-tier retrieval over All India Radio news bulletins

TODO: final title, authors, affiliations.

## Abstract

[Abstract intentionally left empty. Numbers it should contain once everything is measured: number of bulletins and hours of audio in the sample; number of sentences before and after the novelty gate; size of the human-labelled gold sets (genre sentences, labelled pairs, judged queries, hand-corrected bulletins); genre macro-F1 of each system with its 95% interval; human-versus-LLM agreement on the from-scratch overlap; duplicate-pair precision, recall and F1 at the validation-selected threshold; retrieval recall, MRR and nDCG of each system; word error rate by Whisper size; transcription real-time factors; scale-benchmark latency. TODO: write the abstract from the final result files only.]

## 1. Introduction

All India Radio (AIR) publishes its news bulletins as audio in a public online archive. Bulletins follow one another through the day, and a working hypothesis of this project, UNVERIFIED and not tested in this paper, is that the same story is read, in similar words, in several bulletins of one day, so that a text store built from the bulletins holds a great deal of repeated material. In the 3-month listing we crawled, 1,896 of the 2,173 listed items are hourly bulletins, which is the setting that motivates the hypothesis. <!-- data/metadata_3month_english.csv: title column, Hourly News 1,896 of 2,173 rows -->

This paper describes a pipeline for such a stream and reports a pilot-scale evaluation of parts of it. The pipeline transcribes bulletin audio with Whisper, cuts the transcript into sentences, embeds each sentence, drops a sentence when it is too similar to one already kept (a streaming novelty gate), assigns one of ten genre labels, stores the result in a vector index and a relational table, and answers questions by filtering on date and genre before a vector search. <!-- nlp_pipeline.py, vector_store.py, rag_engine.py; ROADMAP.md section 0 --> The scope is deliberately small: a sample of 10 whole days, one human annotator, gold sets of a few hundred items, and two test days. We report what was measured, we report what was not, and we mark every inference as unverified.

The paper contains the following. Section 3 describes the archive, how it was crawled, the sample and the split by whole days, a check of files that share a broadcast slot, and the transcription. Section 4 describes the system. Section 5 describes the gold sets, the annotation procedure (which involved a language model and one human), the metrics, the baselines and the controls against leakage. Section 6 reports the genre evaluation on 175 human-labelled sentences, the agreement between the human labels and the language-model labels, the duplicate-slot finding, and transcription speed; the results of the duplicate-pair, retrieval and word-error-rate evaluations are not yet available and their tables are empty. Section 7 lists limitations plainly.

TODO: research questions fixed in advance of the remaining evaluations (duplicate-pair threshold, retrieval variants, word error rate by Whisper size).
TODO: contribution statement, to be written after all results exist; this draft makes no claim of novelty and no claim about which system is best.

## 2. Related Work

**Speech and text resources from Indian broadcast archives.** Shrutilipi (Bhogale et al., 2022) mines audio and text pairs from public data, including the All India Radio archives, where PDF transcripts are aligned to bulletin audio; it covers over 6,400 hours across 12 Indian languages and was built to train speech recognition systems. This project uses the same broadcaster's public archive but differs in purpose and scale: it looks at English hourly bulletins (209 of the 239 bulletins in our sample), it is a pilot of novelty filtering, genre labelling and retrieval over a transcribed stream, and it is not built as ASR training data. <!-- config/sample_config.json, option A summary: hourly_items 209, items 239 --> In our crawl, the audio cards of the archive page carried only a title and a date as their "transcript" blurb; the other archive pages that may hold text were not checked, so we do not know whether they correspond to the PDF transcripts that Shrutilipi aligns (UNVERIFIED), and we transcribed the audio ourselves. <!-- ROADMAP.md section 4: "The card's 'Transcript' is only an accessibility blurb"; /bulletins-detail-archive/ and /text-archive-search/ UNCHECKED -->

**Speech recognition.** We transcribe with Whisper models (Radford et al., 2022), which are trained with large-scale weak supervision, run through the faster-whisper implementation. We use the `small` size for the whole sample and the `tiny` and `base` sizes for five bulletins; their word error rates are not yet computed. <!-- ROADMAP.md sections 8a and 8e -->

**Sentence embeddings, retrieval and retrieval-augmented generation.** Sentence-BERT (Reimers and Gurevych, 2019) computes sentence embeddings with siamese BERT networks. The pipeline embeds each sentence with a model named all-MiniLM-L6-v2 (384 dimensions); the MiniLM reference we associate with it, (Wang et al., 2020), is UNVERIFIED and given from memory, and it is not established here that it describes this exact checkpoint. <!-- nlp_pipeline.py: EMBEDDING_MODEL --> Vectors are searched with a flat inner-product FAISS index; the reference we associate with FAISS, (Johnson et al., 2017), is likewise UNVERIFIED and from memory. Retrieval-augmented generation (Lewis et al., 2020) combines retrieval with generation for knowledge-intensive tasks, and our answer step follows that pattern: retrieved sentences are given to a language model that writes the answer. The generation step is not evaluated here beyond a planned small human check (TODO).

**Near-duplicate and novelty detection in news; zero-shot classification.** Rodier and Carter (2020) flag near-duplicate news articles online by finding the most likely original, adapting shingling. Lee (2015) addresses sentence-level novelty detection in streams of documents. Tumre et al. (2025) combine embeddings with community detection to find near-duplicates among short news snippets. Fu et al. (2015) use incremental TF-IDF with locality-sensitive hashing for novelty detection in text streams. Our gate works on single sentences with a fixed embedding-similarity threshold, which we describe in Section 4.3 and examine on labelled pairs in a later evaluation. For genre labelling, Yin et al. (2019) formulate zero-shot text classification as textual entailment, and the BART model (Lewis et al., 2019) is a denoising sequence-to-sequence pre-training approach; the checkpoint we use as one genre backend is facebook/bart-large-mnli, and we make no statement about how that checkpoint was fine-tuned. <!-- nlp_pipeline.py: DEFAULT_CLASSIFIER_MODEL "facebook/bart-large-mnli" --> In a limited, non-exhaustive search we did not find prior work that applies sentence-level novelty filtering, genre labelling and retrieval together to transcribed radio bulletins. [TODO authors: confirm that this sentence reflects the search that was actually done; do not read it as a claim of novelty.]

## 3. Data

### 3.1 The archive and the crawl

The AIR website exposes its audio bulletins through an archive page whose listing is loaded by an AJAX call that returns HTML fragments, 12 items per page. <!-- ROADMAP.md section 4, "S3 RESULT" --> Each item has a title, a date and a direct `.mp3` address. The page gives no time of day, so the broadcast hour is taken from the file name: the first standalone four-digit group is read as HHMM and the hour is HHMM divided by 100; a name without a valid time gives an empty hour and a flag. <!-- ROADMAP.md section 4; air_bulletins_scraper.py, parse_hour_from_url --> The date filter treats both bounds as exclusive, so each crawl window is queried from the day before its first day to the day after its last day; this was inferred from four probe requests and is consistent with the later crawls. <!-- ROADMAP.md section 4, S3c result and "Window rule" -->

We crawled the listing (metadata only, no audio) for 2026-08-01 to 2026-10-31 in 14 weekly windows and 184 result pages. <!-- data/metadata_3month_english.csv: window column has 14 distinct values; ROADMAP.md section 4 "S3d RESULT": 184 pages --> The listing holds 2,173 distinct audio addresses over 92 days. <!-- data/metadata_3month_english.csv: 2,173 rows, 92 distinct dates --> By title there are 1,896 Hourly News items, 92 Midday News, 92 Morning News, 87 Evening News, 2 News At Nine and 4 items with Hindi or Urdu titles. <!-- data/metadata_3month_english.csv, title column --> The broadcast hour could be parsed for 2,030 items, and 143 were flagged (141 with no time in the file name, 2 with an invalid time). <!-- data/metadata_3month_english.csv: hour and hour_flag columns --> 31 October 2026 was still in progress when crawled and is treated as incomplete. <!-- ROADMAP.md section 4, S3d "Unusual days" -->

Requests followed the site's robots.txt, which allowed all paths when checked on 31 October 2026, and used a random delay of 1 to 3 seconds; the crawler stops if a path is disallowed. <!-- ROADMAP.md section 2 item 16; air_bulletins_scraper.py lines 954-955 (--min-delay 1.0, --max-delay 3.0) --> The total size of the archive is UNVERIFIED (a screenshot showed 1,686 result pages; the full archive was not crawled), and the separate "Daily Broadcast" tab was not examined. <!-- ROADMAP.md section 4 -->

### 3.2 The option A sample

Audio was downloaded and transcribed only for a sample of whole days. The pool is the 91 complete days from 2026-08-01 to 2026-10-30, after removing 31 October and the four non-English items, which leaves 2,153 items. <!-- ROADMAP.md section 8a "Pool"; config/sample_config.json, pilot_plan_s4.exclusions --> Days were drawn with a fixed seed of 42, stratified by month and by weekday versus weekend, with the rule that no two chosen days are consecutive calendar days. <!-- config/sample_config.json, pilot_plan_s4.seed and .rule --> The sample used here, called option A, has 10 days: 2026-08-10, 08-16, 08-28, 09-03, 09-06, 09-30, 10-19, 10-21, 10-24 and 10-27. <!-- config/sample_config.json, pilot_plan_s4.option_A_about_10_days.days --> It holds 239 bulletins, of which 209 are hourly and 30 are Morning, Midday, Evening or News At Nine. <!-- config/sample_config.json: items 239, hourly_items 209, non_hourly_items 30; data/sample_A/metadata.csv: 239 rows --> The days are fixed by the rule and the seed and were not hand-picked; the choice of 10 days reflects the time available for annotation and transcription (TODO: the authors should confirm this reason).

### 3.3 Split by whole days

Training, validation and test sets consist of whole days, never of sentences or hours, because adjacent hourly bulletins overlap in content. <!-- ROADMAP.md section 8a "Fixed seeded rule" --> The split is 6 training days (144 bulletins), 2 validation days (48 bulletins; 2026-08-16 and 2026-10-24) and 2 test days (47 bulletins; 2026-08-28 and 2026-09-06). <!-- config/sample_config.json, option A split; data/sample_A/metadata.csv, split column: train 144, val 48, test 47 --> Gold annotation is drawn from the validation and test days only; the training days provide machine-labelled (silver) training data only. <!-- ROADMAP.md section 8b "Leakage rule" --> With two test days, results can reflect the stories of those two days.

### 3.4 Files that share a broadcast slot

In the archive, two different audio files sometimes carry the same date and the same HHMM in their names: 124 such date-and-time pairs occur in the 3-month listing. <!-- ROADMAP.md section 4, "Same-time duplicates (measured in S3d ...)" --> Inside option A there are 9 such pairs, on 8 of the 10 days. <!-- config/sample_config.json: duplicate_slot_pairs 9, days_with_a_duplicate_slot_pairs 8; results/duplicate_pairs_check.json: n_pairs 9 --> We compared the two files of each pair; the result is reported in Section 6.3.

### 3.5 Transcription

All 239 bulletins of option A were transcribed with faster-whisper, model `small`, on the GPU in float16, with voice-activity detection left at the library default (off). <!-- data/sample_A/metadata.csv: whisper_model small, device cuda, compute_type float16 on all 239 rows --> The audio totals 1,441.3 minutes (24.02 hours). <!-- data/sample_A/metadata.csv: sum of duration_s; ROADMAP.md section 8a "S5 results" --> Transcription took 81.9 minutes of compute and 82.2 minutes of wall time including one model load, a real-time factor of 0.0568, on a laptop with an NVIDIA RTX 2050 (4 GB). <!-- ROADMAP.md section 8a "S5 results"; hardware: ROADMAP.md section 5 --> The 239 transcripts yield 9,519 sentences after segmentation (Section 4.3). <!-- results/store_reports/store_A_build_report.json: sentences_before_gate all 9519 --> We have not yet measured the word error rate of these transcripts: reference transcripts typed by a human from the audio are planned for five bulletins (Section 5.2), and Whisper `tiny` and `base` hypotheses exist for the same five bulletins. <!-- ROADMAP.md section 8e --> Speeds are in Section 6.4.

## 4. System

### 4.1 Ingest

Transcripts are processed in order of date, then broadcast hour (bulletins without a parsed hour last), then file name. The hour is stored as 0 to 23, or as NULL with a flag when the file name has no valid time; it is never stored as 0 for "unknown". Every stored segment also carries its day-level split. <!-- ingest_pipeline.py (_extract_hour_and_flag, run with sort_rows); vector_store.py (hour_flag and split columns); ROADMAP.md section 8d -->

### 4.2 Segmentation and embedding

Transcripts are cut into sentences with the NLTK punkt tokenizer, and each sentence is embedded with all-MiniLM-L6-v2 (384 dimensions) <!-- nlp_pipeline.py: segment_sentences, EMBEDDING_MODEL --> (Reimers and Gurevych, 2019; MiniLM reference (Wang et al., 2020), UNVERIFIED). Chunks are single sentences; windows and paragraphs are not used.

### 4.3 Novelty gate

Sentences are processed as a stream. A sentence is dropped when its cosine similarity to any stored or already accepted sentence is at least 0.85; otherwise it is kept and added to the pool. <!-- nlp_pipeline.py: DEFAULT_MMR_THRESHOLD 0.85, mmr_novelty_filter_detailed --> The value 0.85 was fixed before any labelled data existed and is not tuned inside the pipeline; the labelled-pair evaluation (Section 5) is meant to examine other thresholds on validation pairs. <!-- ROADMAP.md section 2 item 4 --> The design is related to sentence-level novelty detection in streams (Lee, 2015; Fu et al., 2015) and to near-duplicate detection in news (Rodier and Carter, 2020; Tumre et al., 2025); we do not claim that it follows any one of them.

On option A the gate ran across all splits, in processing order. It read 9,519 sentences and kept 4,264; by split, 5,560 became 2,520 (training), 1,981 became 879 (validation) and 1,978 became 865 (test). <!-- results/store_reports/store_A_build_report.json: sentences_before_gate, sentences_after_gate (committed copy of store_A/build_report.json) --> The gate therefore dropped 5,255 sentences, 55.2% of those read. <!-- results/store_reports/store_A_dedup_report.json: totals (rejected_sentences 5255, reduction_pct 55.2) --> This is a count of what the gate did and is not a precision figure: whether each dropped sentence was really a repeat has not been measured (it is the subject of the labelled-pair evaluation). Because the gate runs across splits in date order, a validation or test sentence can be dropped because of an earlier training-day sentence, and sentences of the gold sets can be dropped. <!-- ROADMAP.md section 8c "Choices and caveats" --> For an ablation, a second store built with the gate off keeps all 9,519 sentences. <!-- results/store_reports/store_A_nodedup_build_report.json: segments_in_store 9519, threshold 1.01 -->

### 4.4 Genre classification

Each sentence receives one of ten labels: Politics, Economy, Science & Technology, Sports, International, Defence & Security, Health, Environment, Society & Culture and Other. <!-- nlp_pipeline.py: GENRE_LABELS --> The code offers three backends: zero-shot classification with facebook/bart-large-mnli, a faster zero-shot cross-encoder (cross-encoder/nli-MiniLM2-L6-H768), and a DistilBERT classifier fine-tuned on silver labels (Yin et al., 2019; Lewis et al., 2019). <!-- nlp_pipeline.py: DEFAULT_CLASSIFIER_MODEL, FAST_CLASSIFIER_MODEL; train_genre_classifier.py: DEFAULT_MODEL_NAME distilbert-base-uncased --> The genre column of the option A store was produced with the fast backend, chosen for speed on CPU: on 24 sentences BART took 1.65 s per sentence against 0.18 s for the fast backend. <!-- results/store_reports/store_A_build_report.json: classifier_backend "fast"; ROADMAP.md section 8c --> These labels are silver. Their quality on the gold set is reported in Section 6.1. No fine-tuned checkpoint exists yet, so no fine-tuned result is reported (TODO).

### 4.5 Two-tier retrieval and answer generation

A query first goes through regular-expression date parsing and keyword-based genre extraction. These select candidate segments in SQLite by date range and genre, and a vector search over the candidates (a flat inner-product index on unit vectors) returns the top results. A relevance filter then removes weak matches: it returns nothing when the best score is below 0.20, and otherwise keeps scores of at least the larger of 0.20 and 0.65 times the best score; generic news queries use a floor of 0.05. <!-- rag_engine.py: answer_query, _parse_date_range, _extract_genre, _filter_by_relevance --> A language model (Gemini) writes the answer from the retrieved sentences, with an extractive fallback, following the retrieval-augmented pattern (Lewis et al., 2020). <!-- rag_engine.py: _generate_with_gemini; ROADMAP.md section 1 item 10 --> The model name is hard-coded and may be retired (UNVERIFIED). <!-- ROADMAP.md section 2 item 10 --> The index is a FAISS flat index (Johnson et al., 2017, UNVERIFIED). Answer quality is to be checked only by a small human check of about 30 questions (TODO); no automatic answer-quality metric is used. <!-- ROADMAP.md section 6 -->

## 5. Evaluation Protocol

### 5.1 Gold sets

All gold material is drawn from the validation and test days. The genre sheet has 400 sentences, 100 from each of 2026-08-16, 2026-08-28, 2026-09-06 and 2026-10-24, drawn at random within each day with seed 42 from sentences of at least four words, using the project's own segmentation and not stratified by any model prediction. <!-- data/gold/genre_sheet_annotator1.csv: 400 rows, 100 per date; data/gold/build_gold_sheets.py (SEED = 42, MIN_WORDS = 4); ROADMAP.md section 8b --> The sampling pool had 3,903 sentences from 95 bulletins. <!-- ROADMAP.md section 8b; data/gold/valtest_sentence_index.csv: 3,903 rows --> A subset of 175 of the 400 sentences, listed in a different random order, forms the overlap sheet (47, 42, 38 and 48 sentences from the four days). <!-- data/gold/genre_sheet_annotator2_overlap.csv: 175 rows --> **The gold set used for the genre evaluation in this paper is these 175 sentences with the human labels typed from scratch (N = 175; 95 from the validation days and 80 from the test days).** <!-- results/genre_eval_20261101T180912Z.json: gold_sheet n 175, n_by_split {val 95, test 80} --> The other 225 sentences of the sheet are not used as gold because they have not been human-reviewed yet. TODO: human review of the 225 sentences.

The pair sheet has 100 sentence pairs from different bulletins of the same day, drawn across cosine bands from 0.60 to 0.95 plus 20 random low-similarity pairs, 25 per day; each sentence is used in at most one pair and the similarity score is held in a separate key file that annotators did not see. <!-- data/gold/duplicate_pairs_sheet.csv: 100 rows; ROADMAP.md section 8b --> The pairs have not been human-reviewed yet, so no pair evaluation is reported (TODO). The query sheet has 50 empty rows for queries and relevance judgments (TODO: queries are written by a human and judged; final counts to be stated). <!-- data/gold/query_sheet.csv: 50 rows --> The reference transcripts for five bulletins are TODO (Section 5.2).

### 5.2 Annotation procedure

The sampling sheets (genre, pair and query templates) were built with code written by an LLM assistant. <!-- ROADMAP.md section 8b; the commit trailers name Claude Sonnet 5.5 from the first commit on, which is UNVERIFIED for work before that commit --> The genre sheet of 400 sentences and the pair sheet of 100 pairs were then pre-labelled by an LLM, Claude Sonnet 5.5, on 2026-10-31, in a single pass, using only the sentence text and the label descriptions in the project (no model predictions, silver labels, similarity scores, hidden key or human labels). <!-- data/gold/llm/PROVENANCE.md: model, date, files read, statement --> The 175 overlap sentences were labelled by the human from scratch, before the human saw the LLM labels, and these are the gold labels used in this paper. <!-- procedure as stated by the authors; no saved file records the order in which the human saw the labels (UNVERIFIED by the repository) --> There is one human annotator. TODO: the human review of the other 225 sentences and of the 100 pairs; the number of human corrections is to be reported as [N_GENRE_CORRECTIONS] of 225 and [N_PAIR_CORRECTIONS] of 100.

Agreement between the human labels and the LLM labels on the 175 overlap sentences is reported as human-versus-LLM agreement (Section 6.2). Because there is no second human annotator, no inter-annotator kappa is computed or reported. The pair labels are defined as follows: same, the same fact in nearly the same wording; paraphrase, the same fact in different wording; follow-up, the same story with new or updated information; different, a different fact. <!-- data/gold/llm/PROVENANCE.md (definitions given for the LLM pass) --> The LLM read "follow-up" at the level of the story, so the boundary between follow-up and different is the least certain part. <!-- ROADMAP.md section 8f --> TODO: state whether the human uses the same definitions.

The label `Other` holds sentences that fit none of the nine genres. The label set has no category for bulletin boilerplate (sign-offs, headline announcements, newsreader names) or for accident, collapse, fire and crime stories, and the LLM pre-labelling put these under `Other`; `Other` is therefore inflated by boilerplate and accident stories. <!-- data/gold/llm/PROVENANCE.md (rules applied); ROADMAP.md section 8f --> The human labels contain 29 `Other` sentences out of 175; whether the human used `Other` for the same reasons was not examined (TODO). <!-- results/genre_eval_20261101T180912Z.json: gold_sheet.support_by_class Other 29 --> The project code defines only the label names; the descriptions available to annotators are the keyword hints of the project's keyword map, and written definitions of the ten genres are TODO. <!-- data/gold/README.md -->

For the queries, the human writes and selects them; an LLM produced 80 draft queries (52 with a date constraint, 28 without) and left the relevant-segment column empty. <!-- ROADMAP.md section 8f --> TODO: relevance judging uses candidates from a helper script that merges embedding and TF-IDF rankings, which may favour retrievers similar to those two rankers (UNVERIFIED effect). The reference transcripts for five bulletins (English-0105-0110-9, English-1505, English-1905-1, morninng, Midday-News) are to be typed by a human from the audio and not copied from any Whisper output (TODO). <!-- config/sample_config.json, pilot_plan_s4.asr_wer_candidates_from_option_A_test_days -->

### 5.3 Metrics

For genre we report macro-F1 over the classes that have at least 5 gold examples, per-class precision, recall and F1 with support, accuracy and a confusion matrix; a class with fewer than 5 gold examples would be reported as "insufficient support". <!-- eval/eval_config.py: MIN_CLASS_SUPPORT 5; eval/genre_eval.py --> For duplicate detection we sweep the cosine threshold from 0.60 to 0.95 in steps of 0.01, treat same plus paraphrase as the positive class (with a variant that counts only same), choose the best-F1 threshold on validation pairs and report it on test pairs. <!-- eval/eval_config.py: DEDUP_THRESHOLDS; eval/dedup_eval.py --> For retrieval we report recall at 1, 3, 5 and 10, mean reciprocal rank and nDCG at 5 with binary relevance over each system's top 20, after mapping each relevant sentence to a stored segment (exactly by text, otherwise to the kept segment that caused its rejection, otherwise unmapped). <!-- eval/eval_config.py: RETRIEVAL_KS, NDCG_K 5, RETRIEVAL_DEPTH 20; eval/retrieval_eval.py --> For speech recognition we report word error rate with substitutions, deletions and insertions after lowercasing and removing punctuation and apostrophes; numbers are not converted between digits and words. <!-- eval/asr_eval.py (NORMALISATION) --> Human-versus-LLM agreement is reported as observed agreement and Cohen's kappa between the human labels and the LLM labels, with per-label counts and a confusion matrix. <!-- eval/agreement_eval.py --> Anything trainable is run with 5 seeds (42 to 46) and reported as mean and sample standard deviation. <!-- eval/eval_config.py: SEEDS_FOR_MULTI_RUN -->

### 5.4 Baselines and ablations

For genre the systems are a majority-class baseline and a TF-IDF plus logistic-regression baseline, both trained only on training-day silver labels; the project's two zero-shot backends (fast and BART); and fine-tuned classifiers trained on training-day silver labels (not yet trained). All are scored only on the gold sheet, and none of them sees gold labels. <!-- eval/genre_eval.py (docstring) --> For duplicates the baselines are exact string match, normalised-text match, TF-IDF cosine, word 5-gram Jaccard, and a MinHash estimate with word 3-gram shingles and 128 permutations (seed 42). <!-- eval/dedup_eval.py; eval/eval_config.py: MINHASH_SHINGLE_WORDS 3, MINHASH_PERMUTATIONS 128 --> For retrieval the systems are BM25, vector-only search, date prefilter plus vector search, and the full system, with switches that turn off the prefilter, the relevance filter and the novelty gate (the last uses the separate store built without the gate). <!-- eval/retrieval_eval.py (docstring and flags) --> For speech recognition the sizes are Whisper tiny, base and small. <!-- eval/eval_config.py: ASR_MODELS -->

### 5.5 Controls against leakage

Splits are by whole days. Gold sentences come only from validation and test days, and the training days feed silver training only. <!-- ROADMAP.md section 8b --> Before any training or baseline fitting, training-day segments whose normalised text is identical to a gold sentence or to any validation or test sentence of the sampling pool are removed; in the genre run reported here 17 of the 2,520 training-day segments were removed (4 of them match the gold sheet alone), leaving 2,503. <!-- results/genre_eval_20261101T180912Z.json: baseline_training_data n_train_day_segments 2520, n_removed_identical_to_gold_or_valtest 17, n_removed_identical_to_gold_sheet_only 4, n_training_examples 2503 --> Thresholds and models are to be chosen on validation data and reported on test data, gold labels are never used for training, and pair similarity scores were kept out of annotators' sight. Known gaps: the novelty gate ran across splits; gold sentences were sampled from raw sentences and not from the post-gate store; and the labels the zero-shot systems and baselines are compared against were typed by the same person who is the only annotator.

### 5.6 Confidence intervals

Intervals are 95% percentile bootstrap intervals, 1000 resamples, seed 42, resampling sentences. <!-- eval/eval_config.py: BOOTSTRAP_RESAMPLES 1000, SEED 42; results/genre_eval_20261101T180912Z.json: bootstrap --> No statistical test is run. When two intervals overlap we say that the two systems are not distinguishable on this gold set; this is a statement about the intervals, not a test.

## 6. Results

### 6.1 Genre classification on the gold set

The gold set is the 175 sentences with human labels typed from scratch (Section 5.1). <!-- results/genre_eval_20261101T180912Z.json: gold_sheet path data\gold\genre_sheet_annotator2_overlap.csv, label_column annotator_2_label, n 175 --> The two baselines were trained on 2,503 training-day segments with silver labels, for which the majority class is `Other`. <!-- results/genre_eval_20261101T180912Z.json: baseline_training_data majority_class Other, n_training_examples 2503 --> All ten classes had at least 5 gold sentences in the full gold set, so no class was marked "insufficient support" there; in the validation-only and test-only blocks of the result file some classes were (Science & Technology and Health on validation days; Politics, Science & Technology, Sports and Health on test days). <!-- results/genre_eval_20261101T180912Z.json: systems.*.all_gold.classes_insufficient_support (empty), val_days_only and test_days_only classes_insufficient_support --> The result file was produced with seed 42 and 1000 bootstrap resamples; no `--two-humans` option was used. <!-- results/genre_eval_20261101T180912Z.json: extra.two_humans_flag false -->

**Table 1. Genre classification on the gold set (N = 175).** Source: `results/genre_eval_20261101T180912Z.json` (all_gold blocks). Intervals are 95% bootstrap intervals.

| System | Category | Macro-F1 | Macro-F1 95% interval | Accuracy | Accuracy 95% interval |
|---|---|---|---|---|---|
| Majority class (`Other`) | trained on silver labels (baseline) | 0.0284 | [0.0205, 0.0364] | 0.1657 | [0.1143, 0.2229] |
| TF-IDF + logistic regression | trained on silver labels (baseline) | 0.1109 | [0.0654, 0.1536] | 0.2000 | [0.1429, 0.2629] |
| Fast zero-shot (cross-encoder/nli-MiniLM2-L6-H768) | zero-shot | 0.4333 | [0.3450, 0.5119] | 0.4229 | [0.3543, 0.4971] |
| BART zero-shot (facebook/bart-large-mnli) | zero-shot | 0.4334 | [0.3478, 0.4987] | 0.4514 | [0.3714, 0.5257] |

<!-- Numbers in Table 1: results/genre_eval_20261101T180912Z.json, systems.majority_class_train_silver, tfidf_logreg_train_silver, project_fast_nli_minilm, project_zero_shot_bart; all_gold.macro_f1, accuracy and bootstrap.macro_f1_ci95, accuracy_ci95 -->

The macro-F1 intervals of the two zero-shot systems overlap, as do their accuracy intervals, so the two are not distinguishable on this gold set. The accuracy intervals of the two baselines also overlap; their macro-F1 intervals do not. The intervals of both baselines do not overlap with those of the zero-shot systems on either measure. The accuracy of the majority-class baseline equals the share of `Other` among the gold sentences, 29 of 175. <!-- results/genre_eval_20261101T180912Z.json: gold_sheet.support_by_class Other 29; majority accuracy 0.1657 -->

**Table 2. Per-class F1 on the gold set.** Source: `results/genre_eval_20261101T180912Z.json` (all_gold.per_class); the file also holds precision, recall and per-class intervals.

| Class | Support | Majority | TF-IDF + LR | Fast zero-shot | BART zero-shot |
|---|---|---|---|---|---|
| Politics | 14 | 0.000 | 0.000 | 0.125 | 0.417 |
| Economy | 16 | 0.000 | 0.000 | 0.500 | 0.400 |
| Science & Technology | 7 | 0.000 | 0.000 | 0.571 | 0.462 |
| Sports | 20 | 0.000 | 0.333 | 0.571 | 0.824 |
| International | 31 | 0.000 | 0.167 | 0.508 | 0.485 |
| Defence & Security | 16 | 0.000 | 0.118 | 0.353 | 0.118 |
| Health | 6 | 0.000 | 0.000 | 0.615 | 0.571 |
| Environment | 19 | 0.000 | 0.000 | 0.333 | 0.688 |
| Society & Culture | 17 | 0.000 | 0.222 | 0.390 | 0.000 |
| Other | 29 | 0.284 | 0.269 | 0.366 | 0.370 |

**Table 3. Per-class precision and recall of the two zero-shot systems on the gold set.** Source: `results/genre_eval_20261101T180912Z.json` (all_gold.per_class). P = precision, R = recall.

| Class | Support | Fast P | Fast R | BART P | BART R |
|---|---|---|---|---|---|
| Politics | 14 | 0.500 | 0.071 | 0.500 | 0.357 |
| Economy | 16 | 0.750 | 0.375 | 0.556 | 0.312 |
| Science & Technology | 7 | 0.571 | 0.571 | 0.500 | 0.429 |
| Sports | 20 | 1.000 | 0.400 | 1.000 | 0.700 |
| International | 31 | 0.500 | 0.516 | 0.457 | 0.516 |
| Defence & Security | 16 | 0.333 | 0.375 | 1.000 | 0.062 |
| Health | 6 | 0.571 | 0.667 | 0.500 | 0.667 |
| Environment | 19 | 0.800 | 0.211 | 0.846 | 0.579 |
| Society & Culture | 17 | 0.333 | 0.471 | 0.000 | 0.000 |
| Other | 29 | 0.266 | 0.586 | 0.253 | 0.690 |

With 175 sentences and between 6 and 31 per class, the per-class intervals in the result file are wide (for example, the per-class F1 interval of BART for Science & Technology is [0.0, 0.8000] and of the fast system for Politics [0.0, 0.3636]), so differences between classes or between the two zero-shot systems in Tables 2 and 3 should not be read as established. <!-- results/genre_eval_20261101T180912Z.json: systems.project_zero_shot_bart.all_gold.bootstrap.per_class_f1_ci95 Science & Technology; systems.project_fast_nli_minilm ... Politics --> The BART system assigned no sentence to Society & Culture, and the fast system assigned 2 sentences to Politics. <!-- results/genre_eval_20261101T180912Z.json: per_class.predicted, BART Society & Culture 0, fast Politics 2 --> The full confusion matrices (rows human label, columns predicted label) are in the result file. The genre column of the option A store came from the fast system, so Table 1 gives its macro-F1 of 0.4333 (interval [0.3450, 0.5119]) as the only measure we have of the quality of that column, and it is a measure on 175 sentences, not on the 2,520 training-day segments or on the post-gate store (UNVERIFIED that it carries over). <!-- results/store_reports/store_A_build_report.json: classifier_backend fast; results/genre_eval_20261101T180912Z.json: project_fast_nli_minilm macro_f1 -->

### 6.2 Agreement between the human labels and the LLM labels

On the 175 from-scratch overlap sentences, the LLM label equals the human label for 119 sentences and differs for 56. <!-- results/human_vs_llm_agreement_20261101T175909Z.json: groups.overlap_human_from_scratch agree_count 119, disagree_count 56, n 175 --> Observed agreement is 0.68 with a 95% bootstrap interval of [0.6114, 0.7486], and Cohen's kappa between the human labels and the LLM labels is 0.6351, interval [0.5559, 0.7085] (seed 42, 1000 resamples). <!-- results/human_vs_llm_agreement_20261101T175909Z.json: observed_agreement 0.68, cohens_kappa_human_vs_llm 0.6351451973194342, bootstrap.observed_agreement_ci95, cohens_kappa_ci95 --> This is human-versus-LLM agreement. It is not inter-annotator agreement, and there is no second human annotator. The 225 sentences that a human has not yet reviewed and the 100 pairs are not part of this measure.

**Table 4. Human-versus-LLM agreement on the 175 overlap sentences, per label.** Source: `results/human_vs_llm_agreement_20261101T175909Z.json` (groups.overlap_human_from_scratch.per_label). "Human" and "LLM" are the number of sentences each assigned to the label; "Agree" is the number given that label by both.

| Label | Human | LLM | Agree |
|---|---|---|---|
| Politics | 14 | 8 | 6 |
| Economy | 16 | 17 | 10 |
| Science & Technology | 7 | 8 | 4 |
| Sports | 20 | 17 | 17 |
| International | 31 | 39 | 24 |
| Defence & Security | 16 | 11 | 6 |
| Health | 6 | 5 | 3 |
| Environment | 19 | 16 | 15 |
| Society & Culture | 17 | 25 | 12 |
| Other | 29 | 29 | 22 |

The label pairs with the most disagreements, as counts of sentences (human label, then LLM label), are Defence & Security then International (6), Politics then Society & Culture (5), Other then Society & Culture (4) and Environment then International (4); the full confusion matrix is in the result file. <!-- results/human_vs_llm_agreement_20261101T175909Z.json: confusion_matrix.counts --> The LLM that produced these labels also wrote the code that built the sampling sheets (Section 5.2). A first agreement run was started by mistake by an old test; its output was never read and was deleted, and the numbers above come from the run made afterwards with the same seed. <!-- ROADMAP.md section 8h -->

### 6.3 Files that share a broadcast slot

Table 5 compares the two files of each of the 9 same-slot pairs inside option A. In all 9 pairs the two files have different SHA-256 values, the durations differ by between 2.98 and 11.42 seconds, and the word 5-gram Jaccard similarity of the two transcripts lies between 0.0008 and 0.0388. With the threshold we chose in advance (a Jaccard below 0.3 is labelled "different text"), all 9 pairs are labelled different. All 9 pairs are in the 01:05 and 03:05 night slots. In this sample, therefore, files that share a slot are different recordings and not re-uploads of one recording, and they are not treated as duplicates of each other. Whether this holds in other slots, other months or the rest of the archive is UNVERIFIED.

**Table 5. Same-slot file pairs inside option A.** Source: `results/duplicate_pairs_check.json`.

| Pairs | Pairs with identical SHA-256 | Duration difference (s), min to max | Word 5-gram Jaccard, min to max | Pairs labelled "different text" | Slots |
|---|---|---|---|---|---|
| 9 | 0 | 2.98 to 11.42 | 0.0008 to 0.0388 | 9 | 01:05 and 03:05 |

<!-- Numbers in Table 5 and the paragraph above: results/duplicate_pairs_check.json: n_pairs 9; pairs[].sha256_equal all false; pairs[].duration_diff_s min 2.98 max 11.42; pairs[].jaccard_word_5grams min 0.0008 max 0.0388; label_counts {"different text": 9}; thresholds_our_choice.different_if_jaccard_below 0.3; pairs[].hhmm 0105 and 0305 -->

### 6.4 Transcription speed

Table 6 gives the real-time factor (transcription time divided by audio time) of Whisper `small` over the whole sample, and Table 7 gives `tiny` and `base` on the five bulletins chosen for the word-error-rate evaluation. Each figure comes from a single run on one laptop GPU. The first file of each model run includes model load or warm-up. GPU memory is the total in use as reported by `nvidia-smi` and not the memory of the process alone. <!-- ROADMAP.md section 8e (source file data/asr_hyp/transcribe_log.json, not committed) -->

**Table 6. Whisper `small`, float16, GPU, option A (239 bulletins).** Source: `ROADMAP.md` section 8a ("S5 results"; from `data/sample_A/metadata.csv` and the transcription log, which is not committed).

| Files | Audio (min) | Transcription time (min) | Real-time factor |
|---|---|---|---|
| 209 hourly bulletins | 998.7 | 57.5 | 0.0576 |
| 30 Morning, Midday, Evening and News At Nine bulletins | 442.6 | 24.4 | 0.0551 |
| All 239 | 1,441.3 | 81.9 | 0.0568 |

**Table 7. Whisper `tiny` and `base`, float16, GPU, five bulletins.** Source: `ROADMAP.md` section 8e and `data/asr_hyp/transcribe_log.json` (not committed). RTF = real-time factor.

| Bulletin | Audio (s) | tiny time (s) | tiny RTF | base time (s) | base RTF |
|---|---|---|---|---|---|
| English-0105-0110-9 (hourly, night) | 287.45 | 6.45 | 0.0224 | 7.18 | 0.0250 |
| English-1505 (hourly, day) | 283.56 | 5.69 | 0.0201 | 7.76 | 0.0274 |
| English-1905-1 (hourly, evening) | 283.34 | 5.47 | 0.0193 | 8.09 | 0.0286 |
| morninng (Morning News) | 883.87 | 17.39 | 0.0197 | 25.43 | 0.0288 |
| Midday-News (Midday News) | 870.70 | 17.20 | 0.0198 | 26.49 | 0.0304 |

GPU memory in use peaked at 241 MiB during the `tiny` run (0 MiB before) and at 473 MiB during the `base` run, which started at 209 MiB because the `tiny` model was still loaded. <!-- ROADMAP.md section 8e; data/asr_hyp/transcribe_log.json: gpu_memory_used_mib -->

An earlier comparison used two hourly bulletins (4.76 and 4.74 minutes, 9.50 minutes of audio in total), one run per setting (Table 8); it also compared float16 with int8_float16 and the GPU with the CPU.

**Table 8. Two-bulletin speed comparison.** Source: `ROADMAP.md` section 5 (RTX 2050 table); the first file of each run includes warm-up.

| Model | Compute type | Device | Real-time factor | Transcription time (s) | Peak GPU memory (MiB) |
|---|---|---|---|---|---|
| base | float16 | GPU | 0.042 | 23.9 | 369 |
| base | int8_float16 | GPU | 0.043 | 24.6 | 273 |
| small | float16 | GPU | 0.067 | 38.2 | 881 |
| small | int8_float16 | GPU | 0.072 | 41.0 | 593 |
| base | int8 | CPU | 0.100 | 56.8 | not measured |
| small | int8 | CPU | 0.264 | 150.6 | not measured |

### 6.5 Evaluations not yet available

The tables below are empty. Each is to be filled from one saved result file by the command in Section 9 and from nothing else. TODO: fill them only from those files.

**Table 9. Duplicate-pair detection (needs human-reviewed pair labels).** Source: `results/dedup_eval_*.json`

| Method | Positive-class definition | Threshold chosen on validation pairs | Validation F1 | Test precision | Test recall | Test F1 | Test F1 95% interval | Validation pairs | Test pairs |
|---|---|---|---|---|---|---|---|---|---|
| TODO | | | | | | | | | |

**Table 10. Mapping of relevant sentences to stored segments (needs judged queries).** Source: `results/retrieval_eval_*.json`

| Distinct relevant sentences | Mapped by exact text | Mapped via gate rejection | Unmapped | Queries evaluated | Queries skipped |
|---|---|---|---|---|---|
| TODO | | | | | |

**Table 11. Retrieval (needs judged queries).** Source: `results/retrieval_eval_*.json` (each cell with its 95% interval)

| System | Queries | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | nDCG@5 |
|---|---|---|---|---|---|---|---|
| TODO | | | | | | | |

**Table 12. Retrieval ablations of the full system.** Source: `results/retrieval_eval_ablation_*.json`

| Prefilter | Relevance filter | Novelty gate | Queries | Recall@1 | Recall@5 | Recall@10 | MRR | nDCG@5 |
|---|---|---|---|---|---|---|---|---|
| TODO | | | | | | | | |

**Table 13. Word error rate by Whisper size (needs hand-corrected references).** Source: `results/asr_eval_*.json`

| Model | Bulletin | Reference words | Substitutions | Deletions | Insertions | WER |
|---|---|---|---|---|---|---|
| TODO | | | | | | |

**Table 14. Scale benchmark on synthetic vectors (speed only).** Source: `results/scale_benchmark_n10000_*.json`

| Segments | Index build (s) | Unfiltered query latency p50 / p95 (ms) | Prefiltered query latency p50 / p95 (ms) | Novelty gate time (s) | Peak memory (MB) | Host |
|---|---|---|---|---|---|---|
| TODO | | | | | | |

## 7. Limitations

<!-- Collected from ROADMAP.md sections 2, 3, 4, 6, 7, 8a to 8h and 10. Numbers repeated here are sourced where they first appear in Sections 3 to 6. -->

**Scale and design.** The corpus is small: a sample of 10 days (239 bulletins) from one 3-month window, with only 2 test days, so results can reflect the stories of those days. The gold set used for the genre evaluation has N = 175 sentences, with between 6 and 31 sentences per class, and the pair, query and speech-recognition gold sets do not yet exist in reviewed form; all gold sets are pilot scale and must be called so wherever they appear. Chunks are single sentences, and context windows were not tried. The pipeline is English only; Hindi and multilingual support are out of scope, segmentation, embeddings, genre keywords, prompts and labels are English-only, and four Hindi or Urdu items were removed from the English pool. A sentence has one genre; multi-label genres and story clustering are not implemented. Date parsing uses regular expressions and genre extraction uses keyword lists (ties return nothing); forms such as "this week", "last year" or "in March" are missing, and a year left out silently uses the anchor year. There is no cross-encoder reranker, no open-weights generator baseline, no user study and no learned query understanding. Answer quality is to be checked only by a small human check, not by a benchmark; the generator can state things that the retrieved sentences do not support, and it is a closed model whose name is hard-coded and may be retired (UNVERIFIED).

**Annotation.** There is one human annotator, so there is no inter-annotator kappa; the only agreement figure is human-versus-LLM agreement on the 175 overlap sentences. The sampling sheets were built with code written by an LLM, and the genre and pair labels began as one pass by a single LLM that also built those sheets; labels that a human only reviews may be influenced by the LLM label (anchoring), which is why only the from-scratch overlap is used as gold, and the human review of the other 225 sentences and of the 100 pairs has not been done. The label `Other` is inflated by bulletin boilerplate and by accident stories, for which the label set has no category, and the genre descriptions available to annotators are only keyword hints. Science & Technology (7 sentences) and Health (6) are thin in the gold set, and the validation-only and test-only blocks leave several classes without enough support. The follow-up versus different boundary for pairs is subjective. The pair sheet was sampled across similarity bands, so precision and recall on it will describe that sample and not deployment. Relevance judging will use pooled candidates from two rankers, which may favour similar retrievers, and relevant sentences that the gate dropped have to be mapped to the sentence that caused the drop.

**Genre labels and models.** The genre column of the store comes from the fast zero-shot backend, which scores a macro-F1 of 0.4333 (interval [0.3450, 0.5119]) on the 175 gold sentences, so the stored genres are of limited quality; this is a measure on 175 sentences only. The interval of the BART backend overlaps it, so the two are not distinguishable on this gold set. The fine-tuned classifier has only silver training labels, and no checkpoint exists yet; if an older checkpoint is found, its training data is unknown (UNVERIFIED). <!-- results/genre_eval_20261101T180912Z.json: project_fast_nli_minilm macro_f1 0.4333, interval; project_zero_shot_bart interval -->

**Novelty gate and store.** The gate uses one fixed threshold (0.85) that was not tuned before the evaluation, catches near-identical sentences and not paraphrases or follow-ups, is order dependent, and ran across all splits in date order, so sentences of the gold sets can be dropped because of earlier training-day sentences. The drop rate of 55.2% (5,255 of 9,519 sentences) is a count of what the gate did and not a precision figure. <!-- results/store_reports/store_A_dedup_report.json: totals --> The broadcast hour is missing for 710 segments (bulletins with no time in the file name, mostly Morning, Midday, Evening and News At Nine), so hour-based features exclude them. <!-- results/store_reports/store_A_build_report.json: null_hour_total 710 --> The same-slot finding covers option A only.

**Speech recognition and timing.** ASR errors propagate into every later stage, and the transcription quality is not yet measured because the human reference transcripts do not exist; the word-error-rate normalisation does not convert numbers between digits and words. All timings are single runs: the comparison of precision settings and of GPU against CPU used two hourly bulletins (9.50 minutes of audio) with one run per setting, the `tiny` and `base` timings come from one run over five bulletins, and the `small` timing is one run over the whole sample, all on one laptop GPU (RTX 2050, 4 GB); speeds on other hardware or on the cluster are unmeasured, and `medium` and larger sizes were not tested. <!-- ROADMAP.md sections 5, 8a and 8e --> Sentence timestamps are empty for archive bulletins (live ingestion aligns them heuristically).

**Data source and legal.** The total size of the archive is unverified, the Daily Broadcast tab and the pages that may hold transcript text were not examined, and the licensing and redistribution rights for AIR audio and transcripts are unresolved (TODO); this must be settled before any data release.

**Engineering.** Live-stream ingestion handles one stream at a time, keeps chat sessions in memory, has no authentication, opens a new SQLite connection per call and rewrites the whole vector index on every addition; it was not run end to end after the latest changes (UNVERIFIED) and its compute type is still hard-coded. The scale benchmark uses synthetic vectors at 10,000 segments only; 100,000 and 1,000,000 segments were not run. The cluster scripts were never submitted and were not compared with the cluster's template; internet access, ffmpeg and CUDA libraries on the cluster nodes are unknown. The tests are a local suite without continuous integration.

## 8. Ethics and licensing

- **Source.** Public radio news from the official AIR website. Requests respected robots.txt and used a 1 to 3 second random delay (Section 3.1). Audio files are not stored in the project repository. <!-- .gitignore excludes audio and data/sample_A -->
- **Redistribution.** TODO: confirm with AIR / Prasar Bharati whether audio or transcripts may be shared. The annotation sheets contain sentences of transcripts, so the same question applies to them; they should not be published before it is answered.
- **People.** Bulletins name public officials, newsreaders and, in some stories, private individuals. TODO: privacy review before any data release.
- **Annotators and LLM use.** The only annotator is a member of the project group. An LLM pre-labelled the annotation sheets and built the sampling sheets, and its use is disclosed in Section 5.2.
- **Compute terms.** Cluster use is limited to the approved task. TODO: written confirmation. <!-- ROADMAP.md section 10 -->
- **Misuse and harm.** TODO: a statement on misuse of searchable broadcast transcripts and on the risk of generated answers presenting unsupported claims as fact.

## 9. Reproducibility

- **One command** (resumable; it stops with a message at any stage whose gold labels are missing): `.venv_gpu/Scripts/python.exe run_all.py --stage all`; `run_all.py --list` shows the state of each stage. The stages are ingest, genre, dedup, retrieval and asr. <!-- run_all.py (docstring) --> The genre run in Section 6.1 used instead `eval/genre_eval.py --gold-sheet data/gold/genre_sheet_annotator2_overlap.csv --gold-col annotator_2_label --systems baselines,fast,zero-shot`, and the agreement run used `eval/agreement_eval.py --only-overlap`. <!-- ROADMAP.md section 8h -->
- **Scripts.** `build_store_A.py` builds the stores (`--no-gate --store-dir store_A_nodedup` for the ablation store); the evaluation scripts are `eval/genre_eval.py`, `eval/agreement_eval.py`, `eval/dedup_eval.py`, `eval/retrieval_eval.py`, `eval/asr_transcribe.py` and `eval/asr_eval.py`; helpers are `eval/finetune_genre.py` and `eval/scale_benchmark.py`; cluster jobs are in `cluster/`. Each evaluation writes `results/<name>_<timestamp>.json` with the seed and the SHA-256 of every input file. <!-- eval/eval_common.py: write_result -->
- **Seeds.** 42 for day selection, gold sampling, bootstrap and MinHash; 42 to 46 for multi-seed runs. <!-- config/sample_config.json (seed 42); eval/eval_config.py: SEED, SEEDS_FOR_MULTI_RUN -->
- **Environment.** Python 3.11.9 in `.venv_gpu`; faster-whisper 1.2.1 and ctranslate2 4.8.4 for transcription; faiss-cpu 1.15.0; the PyTorch in `.venv_gpu` is a CPU build (2.14.0), so genre classification and embeddings ran on the CPU. <!-- ROADMAP.md section 5 (versions); requirements.txt (faiss-cpu==1.15.0); ROADMAP.md section 8c --> TODO: save the full list of installed packages next to the paper.
- **Hardware.** Laptop with an NVIDIA GeForce RTX 2050 (4 GB) for crawling, transcription and development. <!-- ROADMAP.md section 5 -->
- **Code and data availability.** The project is a git repository; TODO: record the commit hash at submission. Audio, the sampled audio folder and the built stores are not committed; the listing `data/metadata_3month_english.csv`, the option A configuration `config/sample_config.json`, the gold sheets, the LLM files under `data/gold/llm/` and the result files in `results/` are. <!-- .gitignore; data/metadata_3month_english.csv -->
- **Tests.** TODO: record the number of passing tests at submission (`pytest tests`).
