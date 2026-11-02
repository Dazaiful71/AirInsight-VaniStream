# PHASE 3 - Evaluation design and gold data (slide content)

Status of this file: slide CONTENT only (no layout). Written 2026-11-02 from saved files in the repository. Every number carries its source path in the slide's Sources line. PENDING = no result file exists yet; nothing PENDING has been estimated. UNVERIFIED = inferred or not confirmed by a file.

Naming note: the repository does not define "Phase 1 / 2 / 3 / 4". The recap below groups the ROADMAP steps (S1 to S7, A1 to A9) into a Phase 1-2 story; that grouping is mine (UNVERIFIED as the course's phase definition).

Deck map: Part A, recap of Phases 1 and 2 (slides 1-6). Part B, Phase 3 body (slides 7-21). Then a glossary (slides 22-23) and likely professor questions (section at the end).

---

## PART A - Recap of Phases 1 and 2

### Slide 1 - The problem and why AIR bulletins
**Content**
- All India Radio (AIR) publishes news bulletins as audio in a public online archive.
- The 3-month listing is dominated by hourly bulletins: 1,896 of 2,173 items.
- Working hypothesis (UNVERIFIED, not tested in this work): the same story is read in similar words in several bulletins of a day, so a text store built from them holds much repeated material.
- Goal of the pipeline: transcribe bulletins, keep only sentences that add something, label genre, and answer date- and topic-filtered questions.
- Scope of this work: a pilot (10 whole days, one human annotator, gold sets of a few hundred items, two test days).
- Principle used throughout: label what was measured, mark what was inferred, show nothing that is not in a saved file.

**Speaker notes**
This project turns a public radio archive into a searchable text store. We chose AIR bulletins because they are public, dated and numerous: the 3-month listing has 2,173 items, and 1,896 of them are hourly bulletins. We suspect that stories repeat across bulletins, but we have not tested that, so it is a hypothesis and not a finding. The work is a pilot, and the rule we follow is simple: every number comes from a saved file, and anything not measured is marked PENDING or UNVERIFIED.

**Suggested visual**
Bar chart of listing items by title. Data: Hourly News 1,896; Midday News 92; Morning News 92; Evening News 87; News At Nine 2; Hindi/Urdu-titled 4 (total 2,173). Small inset: the existing diagram `AirInsight_Architecture.png` as a thumbnail of the pipeline.

**Sources**
data/metadata_3month_english.csv (title column); ROADMAP.md section 0 and section 6; paper/draft.md section 1.

---

### Slide 2 - The archive and the crawl: what we found
**Content**
- The archive listing is loaded by an AJAX call that returns HTML fragments, 12 items per page; every item has a direct .mp3 address, a title and a date, and no time of day.
- The old scraper got HTTP 403 ("Invalid request"): it posted to the www host without the WordPress nonce.
- Working request: POST to https://newsonair.gov.in/wp-admin/admin-ajax.php (no www) with a fresh nonce in field `security` read from the archive page's inline script, plus Origin, Referer and X-Requested-With headers. Which of the two missing pieces caused the 403 was not tested separately.
- Date bounds are EXCLUSIVE on both ends (inferred from 4 probe requests, then consistent with the later crawls); to fetch days D1..Dn, send date_from = D1 minus 1 day and date_to = Dn plus 1 day.
- Broadcast hour comes from the file name (earliest standalone 4-digit HHMM, hour = HHMM // 100); names with no valid time give an empty hour plus a flag, never 0.
- The "Transcript" on an audio card is only an accessibility blurb (title and date), so all text comes from our own transcription.
- robots.txt allowed all paths on 31 Oct 2026; the crawler stops if a path is disallowed; random delay of 1 to 3 seconds.

**Speaker notes**
Before any real crawl we had to find out how the site really works. The old scraper failed with a 403 because it lacked the nonce and used the wrong host. We rebuilt the request the way the page's own JavaScript sends it. A second discovery was that the date filter excludes both bounds, which would have silently skipped the opening and closing day of every window; four probe requests showed this, and the window rule fixes it. We respect robots.txt and wait one to three seconds between requests.

**Suggested visual**
Table of the four probes (page 1, newest at the top). Data: (2026-10-19, 2026-10-19) -> "No posts found", 0 pages; (10-18, 10-20) -> 12 items all on 19 Oct, 3 pages; (10-24, 10-26) -> 12 items all on 25 Oct, 2 pages; (10-30, 10-31) -> "No posts found", 0 pages. Next to it, a two-box diagram: "old request (www, no nonce) -> 403" versus "new request (no www, nonce, headers) -> 200".

**Sources**
ROADMAP.md section 4 (S3 RESULT, S3c table, "Window rule"), section 2 items 12a, 13, 16; air_bulletins_scraper.py (parse_hour_from_url; --min-delay 1.0, --max-delay 3.0).

---

### Slide 3 - The 3-month metadata crawl
**Content**
- Metadata only (no audio): 2026-08-01 to 2026-10-31, 14 weekly windows, 184 result pages.
- 2,173 distinct audio addresses over 92 days, 0 duplicates, 0 days with no items.
- Items per day: minimum 16 (31 Oct, still in progress when crawled), maximum 25, median 24, mean 23.6.
- Hour parsed for 2,030 items; 143 flagged (141 with no time in the name, 2 with an invalid time such as 9999.mp3).
- Flags fall mostly on non-hourly bulletins: Midday News 61 of 92, Evening News 36 of 87, Morning News 12 of 92, Hourly News 30 of 1,896.
- 124 date-and-time pairs have two different files at the same slot (250 items involved); content was checked later (slide 20).
- Total archive size is UNVERIFIED (a screenshot showed 1,686 pages; the full archive was not crawled).

**Speaker notes**
The crawl was cheap because it fetched metadata only. It covered every day of the three months and found about 24 items a day. The hour of day is missing mostly for Midday and Morning bulletins, whose file names carry no time. We also noticed that some date-and-time slots have two files; we did not assume they were copies and checked them later. The archive is larger than our window, but we have not measured its full size.

**Suggested visual**
Histogram of items per day. Data (days -> items per day): 59 days -> 24; 23 days -> 23; 5 days -> 25; 3 days -> 22; 1 day -> 21; 1 day -> 16. Second chart: stacked bar of flagged versus parsed hour by title (Midday 61 flagged / 31 parsed; Evening 36 / 51; Morning 12 / 80; Hourly 30 / 1,866).

**Sources**
ROADMAP.md section 4 (S3d RESULT); data/metadata_3month_english.csv (rows, dates, title, hour, hour_flag, window columns). The "parsed" counts in the second chart are derived: total items per title minus flagged.

---

### Slide 4 - The pilot sample and the split by whole days
**Content**
- Pool: 91 complete days (2026-08-01 to 10-30), after removing 31 Oct (incomplete) and 4 non-English items: 2,153 items.
- Rule (seed 42): strata = month x weekday/weekend; random draw within a stratum; no two chosen days on consecutive calendar days.
- Option A has 10 days: 08-10, 08-16, 08-28, 09-03, 09-06, 09-30, 10-19, 10-21, 10-24, 10-27 (3 weekend + 7 weekday).
- 239 bulletins: 209 hourly, 30 Morning/Midday/Evening/News At Nine.
- Split by whole days: train 6 days (144 bulletins); validation 2 days (48 bulletins: 08-16, 10-24); test 2 days (47 bulletins: 08-28, 09-06).
- Why whole days: adjacent hourly bulletins overlap in content, so splitting by sentence or hour would leak.
- A 22-day option B was planned and not downloaded.
- Consequence stated plainly: with two test days, results can reflect the stories of those two days.

**Speaker notes**
We did not hand-pick days. A fixed seed and a stratified rule chose ten days spread over the three months, with no two adjacent. The whole day is the unit of the split, because the same story often appears in neighbouring bulletins and would leak across a sentence-level split. The price is a small test set of two days. We say this in every result slide.

**Suggested visual**
Calendar strip for Aug-Oct 2026 with the 10 days coloured by split. Data: train = 08-10, 09-03, 09-30, 10-19, 10-21, 10-27; val = 08-16, 10-24; test = 08-28, 09-06. Table: split / days / bulletins = train 6 / 144; val 2 / 48; test 2 / 47.

**Sources**
config/sample_config.json (pilot_plan_s4: seed, rule, exclusions, option_A days and split, summary); data/sample_A/metadata.csv (split column); ROADMAP.md section 8a.

---

### Slide 5 - Transcription: Whisper speed on the RTX 2050
**Content**
- Engine: faster-whisper (Whisper models), model `small`, GPU, float16, voice-activity detection left at default (off).
- All 239 bulletins: 1,441.3 minutes (24.02 hours) of audio; 81.9 minutes of transcription, 82.2 minutes wall time including one model load; real-time factor (RTF) 0.0568.
- RTF by group: 209 hourly bulletins 0.0576; 30 other bulletins 0.0551.
- Download: 239 files, 782.9 MB, 0 failures, SHA-256 of every file verified.
- Earlier two-file test (two hourly bulletins, 9.50 minutes): GPU base RTF 0.042, GPU small 0.067; CPU base 0.100, CPU small 0.264; all single runs.
- The two-file small RTF (0.067) came from 2 files including warm-up; the whole-sample figure (0.0568) is the better estimate of sample throughput.
- Transcription quality (word error rate) is PENDING: no hand-corrected references exist yet.

**Speaker notes**
Transcribing a full day of audio takes minutes, not hours, on a 4 GB laptop GPU. A real-time factor of 0.0568 means one minute of audio takes about 3.4 seconds. The earlier small test over two files gave 0.067 because it included warm-up, so we use the whole-sample number. Speed does not tell us accuracy: word error rate needs human reference transcripts, which are still to be written.

**Suggested visual**
Bar chart of RTF. Data: whole sample 0.0568; hourly 0.0576; other 0.0551; two-file GPU base float16 0.042; two-file GPU small float16 0.067; two-file CPU base int8 0.100; two-file CPU small int8 0.264 (colour the two-file bars differently and label "2 files, 1 run").

**Sources**
ROADMAP.md section 8a ("S5 results") and section 5 (RTX 2050 table); data/sample_A/metadata.csv (whisper_model, device, compute_type, duration_s).

---

### Slide 6 - The pipeline
**Content**
- Ingest: transcripts processed by date, then hour, then file; hour stored as 0-23 or NULL with a flag; each segment carries its day-level split.
- Sentences: NLTK punkt; embedding: all-MiniLM-L6-v2, 384 dimensions; chunks are single sentences.
- Novelty gate: a sentence is dropped if its cosine similarity to any kept or stored sentence is at least 0.85.
- Genre: ten labels; backends = zero-shot BART (facebook/bart-large-mnli), fast zero-shot cross-encoder (cross-encoder/nli-MiniLM2-L6-H768), DistilBERT fine-tuned on silver labels (no checkpoint exists yet).
- Store: FAISS flat inner-product index plus a SQLite table.
- Two-tier retrieval: date and keyword-genre filter in SQL, then vector search over the candidates, then a relevance filter (best score below 0.20 returns nothing; otherwise keep scores of at least max(0.20, 0.65 x best); generic queries use 0.05).
- Answer: Gemini writes the answer from retrieved sentences, with an extractive fallback (model name hard-coded; may be retired, UNVERIFIED).
- Tests: a pytest suite with 118 test functions in 9 files (the last full run reported 151 passed, 1 skipped; that summary is not saved in a file).

**Speaker notes**
This is the system we evaluate. A transcript is cut into sentences, each sentence is embedded, and a streaming gate drops sentences that are too close to something already kept. Kept sentences get a genre label and go into a vector index and a database. At question time we begin by narrowing by date and genre, then search by vector, then drop weak matches, and only then ask a language model to write the answer. The answer step is not part of the pilot evaluation beyond a planned small human check.

**Suggested visual**
Use the existing diagram `AirInsight_Architecture.png` (also `AirInsight_Architecture.pdf`; regenerated by `draw_architecture.py`). Add a numbered overlay: 1 ingest, 2 segment+embed, 3 novelty gate (0.85), 4 genre, 5 store, 6 prefilter, 7 vector search, 8 relevance filter, 9 answer.

**Sources**
nlp_pipeline.py (GENRE_LABELS, EMBEDDING_MODEL, DEFAULT_MMR_THRESHOLD, classifier constants); rag_engine.py (_filter_by_relevance); vector_store.py; ingest_pipeline.py; ROADMAP.md sections 1, 2 (item 10), 8d; paper/draft.md section 4; AirInsight_Architecture.png; tests/*.py (count of "def test_" lines: 7+29+9+8+7+18+10+25+5 = 118; computed from the files).

---

## PART B - Phase 3 body: evaluation design and gold data

### Slide 7 - Why human-labelled gold data
**Content**
- The store's genre labels are produced by a model (silver). Scoring a model on its own labels, or on labels made by a model it was trained on, is circular.
- Therefore the evaluation needs labels typed by a person, on sentences the training data never saw.
- Gold sets are drawn only from validation and test days; training days feed silver training only.
- Four tasks need gold: genre (sentences), duplicate detection (sentence pairs), retrieval (queries with judged sentences), speech recognition (hand-corrected transcripts).
- Rule from the project checklist: no unlabelled data reported as gold; if annotation slips, shrink the set, never relax the rigor.
- Everything is labelled "pilot scale" wherever it appears.

**Speaker notes**
The opening design decision was to avoid circular evaluation. Our genre column was made by a model, so it cannot also be the answer key. We therefore draw sentences from days the training data never touched and have a person label them. The same logic applies to duplicate pairs, queries and transcripts. If time runs short, the plan is to label fewer items, not to relax how they are labelled.

**Suggested visual**
Two-column comparison diagram: "circular" (model -> silver labels -> same model scored on silver) versus "gold" (held-out day -> human label -> model scored). A small table listing the four tasks and the kind of gold each needs.

**Sources**
ROADMAP.md section 2 item 1, section 6 ("Pilot gold-set targets"), section 7 (strict-review checklist), section 8b; eval/README.md (Rules).

---

### Slide 8 - The four gold sets: sizes and sampling
**Content**
- Genre sheet: 400 sentences, 100 from each of 2026-08-16, 08-28, 09-06, 10-24; random within each day (seed 42), sentences of at least 4 words, project segmentation, not stratified by any model prediction. Pool: 3,903 sentences from 95 bulletins.
- Overlap subset: 175 of the 400, in a different random order (47, 42, 38 and 48 sentences from the four days; order seed 43).
- Pair sheet: 100 sentence pairs, 25 per day, from different bulletins of the same day, hour gap at most 2; 16 pairs in each cosine band 0.60-0.70, 0.70-0.80, 0.80-0.85, 0.85-0.90, 0.90-0.95, plus 20 random pairs below 0.40. Each sentence used once; pairs of 0.95 and above are excluded.
- Query sheet: 50 empty rows; 80 LLM draft queries exist for the human to select and edit (52 with a date constraint, 28 without).
- ASR references: 5 bulletins (3 hourly, 1 Morning, 1 Midday) from the test days, to be typed by a human from the audio.
- Only the 175 overlap sentences are human-labelled today (see slide 10).

**Speaker notes**
The gold sets are small on purpose. The genre sheet samples evenly from four held-out days, and a 175-sentence subset is where the independent human labels were made. The pair sheet is designed to put data on both sides of the 0.85 threshold, so it includes pairs across similarity bands; this means its class balance is not the corpus's. The query sheet is an empty template, and the ASR references do not exist yet.

**Suggested visual**
Table: set / size / unit / per-day split / status. Genre sheet 400 / sentences / 100-100-100-100 / sampled, LLM-pre-labelled; overlap 175 / sentences / 47-42-38-48 / human-labelled; pairs 100 / pairs / 25-25-25-25 / not human-reviewed; queries 50 rows / queries / n.a. / empty (80 drafts); ASR refs 5 / bulletins / test days / not written.

**Sources**
data/gold/genre_sheet_annotator1.csv, data/gold/genre_sheet_annotator2_overlap.csv, data/gold/duplicate_pairs_sheet.csv, data/gold/query_sheet.csv (row counts and the date column only); ROADMAP.md section 8b and 8f; data/gold/build_gold_sheets.py (SEED = 42, MIN_WORDS = 4); config/sample_config.json (asr_wer_candidates_from_option_A_test_days); results/genre_eval_20261101T180912Z.json (n_by_split).

---

### Slide 9 - Label definitions and the ten genres
**Content**
- Ten genre labels, exactly the project's list: Politics, Economy, Science & Technology, Sports, International, Defence & Security, Health, Environment, Society & Culture, Other.
- The code defines label names only. The descriptions annotators had were keyword hints from the project's keyword map (example hints: Sports = cricket, hockey, match, tournament; Economy = gdp, inflation, rbi, budget; Health = hospital, vaccine, disease; Environment = climate, flood, cyclone, weather; Other = none).
- One label per sentence; `Other` for sentences that fit none of the nine.
- `Other` collects bulletin boilerplate (sign-offs, headline announcements, newsreader names) and accident, collapse, fire and crime stories, which have no genre of their own; it is therefore inflated.
- Pair labels: same = same fact in nearly the same wording; paraphrase = same fact in different wording; follow-up = same story with new or updated information; different = a different fact.
- Written definitions of the ten genres are a TODO; the pair-label boundary between follow-up and different is the least certain part.

**Speaker notes**
Annotators needed a closed list of labels, and we used the labels already in the code. Since the code gives no written definitions, annotators relied on keyword hints and their own judgment, which is a weakness we state openly. The `Other` class is a catch-all, and it is bigger than a clean genre would be. For duplicate pairs, the four labels are defined by how much of the fact is shared and whether the story advanced.

**Suggested visual**
Two small tables. Table 1: label -> three example keyword hints (as listed above; Politics: parliament, election, minister; Science & Technology: isro, satellite, research; International: china, pakistan, united nations; Defence & Security: army, military, terror; Society & Culture: festival, education, religion). Table 2: the four pair labels with a one-line definition and a made-up-free example slot marked "TODO: choose an example from the sheet".

**Sources**
nlp_pipeline.py (GENRE_LABELS); rag_engine.py (GENRE_KEYWORD_MAP); data/gold/README.md; paper/draft.md section 5.2 (pair label definitions, `Other` rule); ROADMAP.md section 8f.

---

### Slide 10 - How the labels were made
**Content**
- 175 overlap sentences: labelled by one human from scratch, before that person saw any LLM label (as stated by the authors; no saved file records the order, UNVERIFIED by the repository). These are the gold labels used for scoring.
- LLM pre-labels: Claude Sonnet 5.5, 2026-10-31, one pass, for all 400 genre sentences and all 100 pairs, using only the sentence text and the label descriptions (no model predictions, silver labels, similarity scores, hidden key or human labels).
- The LLM labels are kept in separate files and are used only to measure human-versus-LLM agreement, never as gold.
- The sampling sheets (genre, pair, query templates) were also built with code written by an LLM assistant.
- There is no second human annotator, so no inter-annotator kappa exists and none is reported.
- The other 225 genre sentences and the 100 pairs have not been human-reviewed; they are not used as gold.
- ASR references: to be typed by a human from the audio, never copied from a Whisper output (PENDING).

**Speaker notes**
We use a language model in two places: it helped build the sampling sheets and it produced a separate set of labels. The gold labels, however, are the human's own, typed from scratch on 175 sentences before the human saw the LLM's labels. The LLM labels are only a comparison point, so we can say how closely a model and a person agree on the same sentences. With one human there is no inter-annotator kappa, and we do not call the human-versus-LLM number by that name.

**Suggested visual**
Flow diagram with three lanes. Lane 1 (gold): 175 sentences -> human labels from scratch -> scoring. Lane 2 (comparison): same 175 -> LLM labels (separate files) -> human-vs-LLM agreement. Lane 3 (pending): 225 sentences + 100 pairs -> LLM pre-label -> human review (TODO) -> future gold. Mark lane 3 "PENDING".

**Sources**
paper/draft.md section 5.2 (cites data/gold/llm/PROVENANCE.md for model, date and statement; that file was not opened for these slides); ROADMAP.md section 8f and 8h; eval/README.md (agreement_eval.py row).

---

### Slide 11 - Leakage controls and the whole-day split
**Content**
- Splits are whole days; gold sentences come only from validation and test days.
- Before any baseline is fitted, training-day segments whose normalised text equals a gold or validation/test sentence are removed: 17 of 2,520 training-day segments removed (4 match the gold sheet alone); 2,503 remain.
- Thresholds and models are to be chosen on validation data and reported on test data; gold labels are never used for training.
- Pair similarity scores are kept in a hidden key file that annotators never saw.
- Human label columns are never overwritten by code; LLM labels live in separate files; the agreement script checks the human labels before anything else and exits if they are empty.
- Known gaps: the novelty gate ran across all splits in date order, so gold sentences can be dropped; gold sentences were sampled from raw sentences, not from the post-gate store; one annotator.

**Speaker notes**
Leakage is the main way a small evaluation fools itself, so we put several guards in place. Days, not sentences, separate training from test. We remove training sentences whose text matches any gold or validation/test sentence, which removed 17 of 2,520 segments in the genre run. The hidden key keeps similarity scores away from annotators. Two gaps remain and we state them: the gate saw all splits, and the retrieval gold has to be mapped onto a store that dropped some sentences.

**Suggested visual**
Timeline diagram of days with colours (train / val / test) and arrows showing allowed data flow: train days -> silver training only; val+test days -> gold sampling; hidden key -> eval code only. Table: segments 2,520 -> removed 17 -> 2,503.

**Sources**
results/genre_eval_20261101T180912Z.json (baseline_training_data); ROADMAP.md section 8b ("Leakage rule"), section 8c (caveats); eval/finetune_genre.py and eval/genre_eval.py (docstrings); paper/draft.md section 5.5.

---

### Slide 12 - Metrics
**Content**
- Genre: macro-F1 over classes with at least 5 gold sentences, per-class precision/recall/F1 with support, accuracy, confusion matrix.
- Human-versus-LLM agreement: observed agreement, Cohen's kappa, per-label agree counts, confusion matrix (rows human, columns LLM); every output named human_vs_llm_agreement.
- Duplicates: precision, recall and F1 at each cosine threshold from 0.60 to 0.95 (step 0.01); positive class = same + paraphrase, with a variant counting only same.
- Retrieval: recall at 1, 3, 5, 10; mean reciprocal rank; nDCG at 5 with binary relevance; each system returns its top 20.
- Speech recognition: word error rate (WER) with substitutions, deletions, insertions, per file and overall.
- Anything trainable: 5 seeds (42 to 46), mean and sample standard deviation.

**Speaker notes**
Each task has the metric usually used for it. Macro-F1 gives every genre equal weight, which matters because the classes are uneven. For retrieval we look at how early the relevant sentence appears. For duplicate detection we sweep the threshold rather than assume 0.85. For agreement, we report both raw agreement and kappa, because raw agreement is inflated when one label is common.

**Suggested visual**
Matrix table: task x metric x unit of resampling (genre: sentences; dedup: pairs; retrieval: queries; ASR: words; agreement: sentences) with the evaluation script name (genre_eval.py, dedup_eval.py, retrieval_eval.py, asr_eval.py, agreement_eval.py).

**Sources**
eval/eval_config.py (MIN_CLASS_SUPPORT, DEDUP_THRESHOLDS, RETRIEVAL_KS, NDCG_K, RETRIEVAL_DEPTH, SEEDS_FOR_MULTI_RUN); eval/README.md; paper/draft.md section 5.3.

---

### Slide 13 - Baselines per task
**Content**
- Genre: majority class and TF-IDF + logistic regression (both trained only on training-day silver labels, leakage-filtered); the project's fast and BART zero-shot backends; fine-tuned classifiers on silver labels (PENDING: no checkpoint).
- Duplicates: exact string match, normalised-text match, TF-IDF cosine, word 5-gram Jaccard, MinHash estimate (word 3-gram shingles, 128 permutations, seed 42), and the project's MiniLM cosine.
- Retrieval: BM25 (k1 1.5, b 0.75), vector-only, date prefilter + vector, and the full system (genre and date prefilter, vector search, relevance filter, no LLM).
- Speech recognition: Whisper tiny, base and small; larger sizes are prepared for the cluster and not run.
- All baselines see no gold labels and are scored only on gold.

**Speaker notes**
A number alone means little, so each task has simple baselines to compare against. For genre the simplest is "always say the most common class", and the next is a bag-of-words classifier trained on the same silver labels. For duplicates we compare the embedding threshold with text-overlap methods. For retrieval we compare against keyword search and against vector search without filters. None of the baselines has seen the gold labels.

**Suggested visual**
Table: task / baselines / what each isolates. Example rows: genre / majority class / the class-balance floor; TF-IDF + LR / bag-of-words on silver; zero-shot fast and BART / no corpus training. Retrieval / BM25 vs vector-only vs prefilter vs full / the value of each stage.

**Sources**
eval/genre_eval.py, eval/dedup_eval.py, eval/retrieval_eval.py, eval/asr_eval.py (docstrings); eval/eval_config.py (MINHASH_SHINGLE_WORDS, MINHASH_PERMUTATIONS, ASR_MODELS); paper/draft.md section 5.4.

---

### Slide 14 - Bootstrap intervals and the minimum-support rule
**Content**
- Intervals are 95% percentile bootstrap intervals: 1000 resamples, seed 42, resampling sentences (genre, agreement), pairs (duplicates) or queries (retrieval).
- No statistical test is run. When two intervals overlap we write "not distinguishable on this gold set"; that is a statement about the intervals, not a test.
- Minimum-support rule: a class with fewer than 5 gold sentences gets no score ("insufficient support") and is left out of macro-F1.
- Per-split blocks (validation-only, test-only) apply the same rule, so some classes drop out there.
- With 175 sentences and 6 to 31 per class, per-class intervals are wide; with about 50 pairs per split or about 50 queries they will be wide too.
- Trainable systems: 5 seeds, mean and sample standard deviation (ddof = 1); LogisticRegression is deterministic, so its seeds give identical predictions.

**Speaker notes**
Small gold sets mean uncertainty, and we show it. The bootstrap resamples the evaluation items to see how much a score would move. We do not claim a difference between systems unless the intervals are well apart, and even then we avoid describing a difference as established because we ran no test. The five-example rule stops us from printing a per-class F1 that rests on two or three sentences.

**Suggested visual**
Illustration of overlapping versus separate intervals using the real genre result: horizontal interval bars for the four systems' macro-F1. Data: majority 0.0284 [0.0205, 0.0364]; TF-IDF+LR 0.1109 [0.0654, 0.1536]; fast 0.4333 [0.3450, 0.5119]; BART 0.4334 [0.3478, 0.4987]. Caption: "fast and BART intervals overlap: not distinguishable on this gold set".

**Sources**
eval/eval_config.py (BOOTSTRAP_RESAMPLES, SEED, MIN_CLASS_SUPPORT); eval/genre_eval.py; results/genre_eval_20261101T180912Z.json (systems.*.all_gold.macro_f1 and bootstrap.macro_f1_ci95; baseline_training_data).

---

### Slide 15 - Duplicate threshold: select on validation, report on test
**Content**
- Sweep the cosine threshold 0.60 to 0.95 in steps of 0.01 (36 values); baselines with a score are swept 0.00 to 1.00.
- Choose the best-F1 threshold on VALIDATION-day pairs only; ties go to the higher threshold; report that threshold on TEST-day pairs, with bootstrap intervals.
- 0.85 (the pipeline's current value) is shown on test only as a reference; it is not used for selection.
- Positive class (primary) = same + paraphrase; alternative = only same; both are reported and the choice is recorded in the result file.
- The pair sheet is sampled across similarity bands, so precision and recall describe this sample, not deployment.
- STATUS: PENDING. No result file exists (dedup_eval.py has not been run; the pair labels are not human-reviewed).
- What unlocks it: human review of the 100 pair labels and an agreed written definition of the four pair labels.

**Speaker notes**
The 0.85 threshold was fixed before any labelled data existed, so we do not trust it by default. The plan is to pick the threshold on the validation pairs and report how it behaves on the test pairs. This keeps test data out of the choice. We have no duplicate-detection result to show yet, because the pairs have been pre-labelled by a model but not reviewed by a person.

**Suggested visual**
Empty PENDING table with the exact columns the result will have: Method / positive-class definition / threshold chosen on validation / validation F1 / test precision / test recall / test F1 / test-F1 interval / n validation pairs / n test pairs. Beside it, a schematic (no numbers) of an F1-versus-threshold curve with a vertical line labelled "selected on validation" and a dashed line "0.85 reference".

**Sources**
eval/dedup_eval.py (docstring); eval/eval_config.py (DEDUP_THRESHOLDS, DEDUP_BASELINE_THRESHOLDS); ROADMAP.md section 8b and A7 row; no file in results/ named dedup_eval_*.json.

---

### Slide 16 - Retrieval evaluation design and the gold-to-store mapping
**Content**
- Gold: each query has a date constraint (empty, one day, or a range; validation/test days only) and the ids of relevant raw sentences from the 3,903-sentence pool.
- Problem: the store keeps only sentences that passed the novelty gate, so a relevant raw sentence may be missing from the store.
- Mapping: (1) exact text match to a store segment; (2) if the sentence was dropped by the gate, map to the kept segment that caused its rejection (recomputed from the pool the gate had at that moment, requiring cosine of at least the gate threshold); (3) otherwise unmapped. Counts of each kind are reported.
- Queries with a training-day date constraint, or with no mappable relevant sentence, are skipped and listed.
- Candidate pool: store_A segments of validation and test days; each system returns its top 20.
- Systems: BM25, vector-only, date prefilter + vector, full system.
- STATUS: PENDING. No result file exists; the queries are not written or judged.

**Speaker notes**
Retrieval evaluation has one awkward step. People judge relevance on the raw sentences, but the system searches a store that already dropped near-duplicates. We therefore map each relevant sentence to the stored segment that stands for it, and we report how many were mapped each way and how many could not be mapped. This keeps the evaluation honest about the gate's effect. None of this has been run on real queries yet, because the queries are still to be written and judged by a person.

**Suggested visual**
Diagram: raw gold sentence -> (exact?) -> store segment; else -> (rejected by gate?) -> causing segment; else -> unmapped. Empty PENDING tables: mapping counts (distinct relevant sentences / exact / via gate / unmapped / queries evaluated / queries skipped) and the metrics table (system / queries / recall@1,3,5,10 / MRR / nDCG@5, each with its interval).

**Sources**
eval/retrieval_eval.py (docstring); eval/eval_config.py (RETRIEVAL_KS, RETRIEVAL_DEPTH, NDCG_K); eval/README.md (query_sheet format); rag_engine.py (_filter_by_relevance); no file in results/ named retrieval_eval_*.json.

---

### Slide 17 - Ablations
**Content**
- Three switches act on the full system: genre/date prefilter on or off; relevance filter on or off; novelty gate on or off.
- Gate off needs a second store built with the gate disabled (threshold 1.01, nothing rejected): `store_A_nodedup`, built; 9,519 segments (train 5,560; validation 1,981; test 1,978); built in one CPU run of 1,856.2 s; 1,547 segments have no hour.
- Ablated runs write their own result files named retrieval_eval_ablation_<switches>.
- The fast zero-shot backend labelled both stores' genre column.
- STATUS: the store exists; NO ablation has been run. PENDING.
- What unlocks it: judged queries (same as slide 16).

**Speaker notes**
An ablation asks what happens when one part of the system is removed. We prepared the three switches and built the store with the gate turned off, so that the gate can be removed in the experiment. That store keeps all 9,519 sentences. We have not run any ablation, because they need the judged queries. Whatever they show will be reported as it is.

**Suggested visual**
Empty PENDING table: Prefilter / relevance filter / novelty gate / queries / recall@1 / recall@5 / recall@10 / MRR / nDCG@5, with rows "all on", "prefilter off", "relevance filter off", "gate off" (cells PENDING). Side box with the two store sizes: with gate 4,264 segments; without gate 9,519 segments.

**Sources**
results/store_reports/store_A_nodedup_build_report.json (segments_in_store, threshold, seconds, null_hour_total, sentences by split); results/store_reports/store_A_build_report.json; eval/retrieval_eval.py (flags and result names); build_store_A.py (--no-gate); ROADMAP.md section 8e.

---

### Slide 18 - Speech-recognition protocol and normalisation
**Content**
- Five bulletins from the test days: English-0105-0110-9 (hourly night, 2026-09-06), English-1505 (hourly day, 08-28), English-1905-1 (hourly evening, 09-06), morninng (Morning News, 09-06), Midday-News (Midday News, 08-28).
- Reference transcripts are typed by a human from the audio into data/gold/asr_refs/<stem>.txt; none exist yet (folder empty).
- Hypotheses: `small` = the option A transcripts; `tiny` and `base` transcribed on the GPU and cached for the same five bulletins (done); larger sizes prepared for the cluster (not run).
- Normalisation (applied to both sides): Unicode NFKC, lowercase, apostrophes deleted, hyphens to space, commas inside numbers deleted, other punctuation removed, decimal points kept; numbers are NOT converted between digits and words.
- WER = (substitutions + deletions + insertions) / reference words, from a word-level Levenshtein alignment; overall WER pools counts over files.
- Cross-check: our WER equals jiwer's on 306 random synthetic cases; the substitution/deletion/insertion split differs in 36 of them when several alignments cost the same.
- STATUS: WER PENDING (no references, no result file).

**Speaker notes**
Word error rate is the standard measure for transcription quality, and it needs a trusted reference. A person has to type the five reference transcripts from the audio; they must not be copied from a Whisper output, or the comparison would be circular. We fixed the normalisation rules in advance, including the decision not to convert numbers, which makes the rate slightly pessimistic where styles differ. Our own WER code agrees with the jiwer library on every synthetic case in total error; only the split among error types can differ on ties.

**Suggested visual**
Table of the five bulletins (stem / role / date / duration in seconds: 287.45, 283.56, 283.34, 883.87, 870.70 / reference status: not written). Worked toy example of an alignment: reference "the cat sat on the mat" versus hypothesis "the cat sit on mat" gives 1 substitution + 1 deletion, WER 2/6 (a hand-made illustration from the unit tests, not data).

**Sources**
config/sample_config.json (asr_wer_candidates_from_option_A_test_days); eval/asr_eval.py (docstring, NORMALISATION); ROADMAP.md section 8e (durations); tests/test_s9.py and tests/test_eval_metrics.py (WER examples and jiwer cross-check); data/gold/asr_refs/ (empty).

---

### Slide 19 - Reproducibility
**Content**
- Every evaluation writes results/<name>_<UTC timestamp>.json containing the seed, the git commit, and the SHA-256 of each input file.
- One command (resumable): run_all.py --stage all runs ingest, genre, dedup, retrieval, asr; --list shows state; it stops with exit code 3 and a message at the earliest stage whose gold labels are missing. Exit codes: 0 result written, 2 prerequisite missing, 3 gold missing.
- Seeds: 42 for day selection, gold sampling, bootstrap and MinHash; 42 to 46 for multi-seed runs.
- Committed copies of the store reports are in results/store_reports/ and are byte-identical (SHA-256) to the untracked originals.
- The repository has 7 commits; audio, the sampled audio folder, the stores, the virtual environment and backups are not committed.
- Environment: Python 3.11.9 (.venv_gpu), faster-whisper 1.2.1, ctranslate2 4.8.4, faiss-cpu 1.15.0; the PyTorch in this environment is a CPU build (2.14.0), so embeddings and genre classification ran on the CPU.
- Not yet saved: the full package list, the final commit hash for submission, the final test count.

**Speaker notes**
We designed the evaluation so that someone else can regenerate the tables. Each result file records which inputs it used, by hash, and which seed. The run_all script runs the stages in order and refuses to continue past a stage whose gold labels are missing. Not everything is finished: we still have to save the package list and record the commit hash and test count at submission time.

**Suggested visual**
Flow diagram of run_all.py stages: ingest -> genre -> dedup -> retrieval -> asr, each with a gate "gold present?" and a state file. Next to it a mock-up (field names only) of a result file header: name, timestamp_utc, seed, git_commit, inputs[path, sha256], results.

**Sources**
eval/eval_common.py (write_result, exit codes); run_all.py (docstring); eval/README.md; results/genre_eval_20261101T180912Z.json (top-level fields); results/store_reports/; ROADMAP.md sections 5 and 8h; git log (7 commits); requirements.txt (faiss-cpu 1.15.0).

---

### Slide 20 - Risks found and fixed during the work
**Content**
- BART cache bug: the genre classifier cached one pipeline for both backends, so after the fast model ran, the "BART" backend silently reused it. Fixed with a per-model cache; without the fix, the BART scores would have been the fast model's.
- Hour-field bug: batch ingest stored HHMM (for example 800) while live ingest stored 0-23, mixing sort order. Fixed: 0-23 everywhere; no valid time gives NULL plus a flag; values outside 0-23 are rejected.
- Filtered FAISS search: the old fallback searched the whole index, then filtered, and could return fewer results than exist. Fixed with an exact fallback; the failure was reproduced only for the fallback path, not for the primary path on the pinned FAISS version (UNVERIFIED that it ever fired).
- Novelty gate speed: per-sentence array stacking replaced by a preallocated pool; identical output; on synthetic vectors, 10,000 sentences took 48.4 s before and 1.6 s after (one run).
- An old test started the real agreement evaluation by accident once the human labels existed: its output was never read and was deleted; the test was replaced by one that forbids starting that script; the real run was made later with the same seed.
- jiwer cross-check: WER equal in all 306 cases; the error-type split differs on ties (documented).
- Excel-style files (UTF-8 with BOM, CRLF) read correctly through a shared reader; a test covers it.
- A second-annotator kappa could be mislabelled: it is now computed only with an explicit --two-humans flag, and the agreement script never uses the word inter-annotator.

**Speaker notes**
Several of these are the kind of problem that quietly corrupts results. The BART cache bug would have made two "different" systems identical. The hour-field bug would have mixed 800 and 8 in the same sort. We found them by writing tests and by reading our own code before running the evaluations. The accidental run is reported openly: the output was not read and was deleted, and the real run was performed afterwards on purpose.

**Suggested visual**
Table: problem / how found / effect if unfixed / fix / test. Add a bar pair for the gate speed with the data: before 48.4 s, after 1.6 s (10,000 synthetic sentences, one run). Label it "synthetic vectors, one run".

**Sources**
ROADMAP.md rows A1, A2, A4 (section 8), section 8d, section 8h; paper/draft.md sections 4.1 and 6.2; tests/test_vector_store_filter.py, tests/test_hour_unification.py, tests/test_novelty_gate.py, tests/test_s9.py, tests/test_s12.py, tests/test_bom_crlf.py.

---

### Slide 21 - What Phase 3 produced and what is pending
**Content**
- Produced: gold sampling sheets (genre 400, overlap 175, pairs 100, query template 50 rows, 80 draft queries); evaluation code for genre, duplicates, retrieval, ASR and agreement, tested on synthetic data; a resumable run_all.py; two stores (with and without the gate); tiny/base hypotheses for five bulletins; cluster job scripts (never submitted).
- Human labels: 175 genre sentences (from scratch).
- Result files that exist: genre evaluation, human-versus-LLM agreement (overlap only), same-slot check, store reports.
- PENDING (no result file): duplicate-pair evaluation, retrieval evaluation, ablations, word error rate, fine-tuned classifier (no checkpoint), scale benchmark, BART relabelling of the store, agreement on the 225 reviewed sentences.
- Open items: human review of 225 sentences and 100 pairs; queries written and judged; five reference transcripts; written genre definitions; licensing answer from AIR.
- Cluster: scripts written, headers not compared with the cluster's real template (UNVERIFIED), nothing submitted.

**Speaker notes**
Phase 3 delivered the design and the machinery, and one real evaluation: genre on 175 sentences, plus the agreement measure. Everything else is ready to run but waits for human labels or reference text. That is a deliberate state: we would rather show an empty table than an estimated number. The next phase reports what exists and marks the rest.

**Suggested visual**
Status board with three columns: DONE (result file exists) / READY, WAITING FOR LABELS / NOT STARTED, each item as a card. DONE: genre_eval, human_vs_llm_agreement (overlap), duplicate_pairs_check, store reports. READY: dedup_eval, retrieval_eval (+ ablations), asr_eval. NOT STARTED: fine-tuning, scale benchmark, BART relabel, cluster runs.

**Sources**
ROADMAP.md sections 8 and 8b to 8h; eval/README.md; ls results/ (genre_eval_20261101T180912Z.json, human_vs_llm_agreement_20261101T175909Z.json, duplicate_pairs_check.json, store_reports/); cluster/README.md.

---

## Glossary slide

### Slide 22 - Glossary (1 of 2)
**Content**
- WER (word error rate): (substitutions + deletions + insertions) divided by the number of reference words.
- RTF (real-time factor): transcription time divided by audio duration; 0.0568 means about 3.4 seconds per minute of audio (derived).
- Macro-F1: the average of per-class F1 scores, each class counting equally.
- F1: the harmonic mean of precision and recall.
- Cohen's kappa: agreement between two label lists corrected for chance; here used between human and LLM labels, not between two humans.
- Novelty gate: the step that drops a sentence whose cosine similarity to a kept sentence is at least 0.85.
- Cosine similarity: the angle-based similarity of two embedding vectors (1.0 means the same direction).
- nDCG@5: ranking quality in the top 5 results, with more credit for relevant items near the top.

**Speaker notes**
Keep this slide available during questions. The two terms most often misread are kappa, which here compares a person with a model, and the novelty gate's drop rate, which is a count of dropped sentences and not an accuracy. The real-time factor is lower for faster transcription. Macro-F1 weights a rare class like Health as much as a common one like International.

**Suggested visual**
Plain two-column glossary table; no chart.

**Sources**
eval/asr_eval.py, eval/genre_eval.py, eval/agreement_eval.py, eval/retrieval_eval.py, nlp_pipeline.py (definitions as implemented).

---

### Slide 23 - Glossary (2 of 2)
**Content**
- MRR (mean reciprocal rank): mean over queries of 1 divided by the rank of the highest-ranked relevant result.
- Recall@k: the share of a query's relevant items found in the top k results.
- Bootstrap interval: the range of a score over many resamples of the evaluation items (here 95%, 1000 resamples, seed 42).
- "Not distinguishable on this gold set": the two systems' intervals overlap; a statement about the intervals, not a statistical test.
- Silver versus gold labels: machine-made versus human-made labels.
- Zero-shot: a model used without training on this corpus.
- Leakage: information from evaluation data reaching training or model selection.
- Whole-day split: separating train, validation and test by calendar day.

**Speaker notes**
These are the evaluation terms that appear on the metric and leakage slides. The bootstrap interval is how we express uncertainty without running a test. Silver labels are what the pipeline stores; gold labels are the human ones used for scoring. If someone asks why days and not sentences, point to the leakage and whole-day split entries.

**Suggested visual**
Plain two-column glossary table; no chart.

**Sources**
eval/eval_config.py, eval/genre_eval.py, eval/retrieval_eval.py, paper/draft.md section 5.6.

---

# Likely questions from a strict professor, with honest answers

1. **Why should we trust your gold labels? There is only one annotator.**
   The 175 labels were typed by one person from scratch, and we say so. There is no inter-annotator kappa, so we cannot give a human ceiling. The only agreement figure is human-versus-LLM agreement on the same 175 sentences (observed 0.68, kappa 0.6351). Source: results/human_vs_llm_agreement_20261101T175909Z.json.

2. **You used an LLM. Is the evaluation circular?**
   The LLM labels are not the gold; they sit in separate files and are used only to measure agreement. The gold labels are the human's from-scratch labels. The LLM did build the sampling sheets and wrote code, and we disclose that. Source: paper/draft.md section 5.2.

3. **Did the human see the LLM labels before labelling?**
   The authors state that the 175 were labelled before the LLM labels were seen. No saved file proves the order, so the repository cannot verify it (UNVERIFIED by files).

4. **Why only 175 sentences and 2 test days?**
   Time: this is a pilot with one annotator. It means wide intervals and results that can reflect two days of news. We report intervals and the per-split blocks, and we call everything pilot scale. Source: results/genre_eval_20261101T180912Z.json.

5. **Why the threshold 0.85 for the gate?**
   It was fixed before any labelled data existed and is not tuned in the pipeline. The duplicate-pair evaluation, which is PENDING, is designed to select a threshold on validation pairs. We make no claim that 0.85 is right.

6. **What does the 55.2% drop rate mean?**
   It is the share of sentences the gate dropped (5,255 of 9,519). It is not a precision figure: whether each dropped sentence was truly a repeat has not been measured. Source: results/store_reports/store_A_dedup_report.json.

7. **Why whole-day splits instead of random sentences?**
   Adjacent hourly bulletins repeat content; a sentence-level split would put near-copies in training and test. The cost is a smaller, coarser test set.

8. **Why did you use the fast backend to label the store, when BART exists?**
   Speed on CPU: on 24 sentences BART took 1.65 s per sentence and the fast backend 0.18 s. The cost is label quality; on the gold set the two are not distinguishable on this gold set (intervals overlap). Source: ROADMAP.md section 8c; results/genre_eval_20261101T180912Z.json.

9. **Is the fine-tuned model better than zero-shot?**
   Unknown: no checkpoint has been trained and no fine-tuned result exists. PENDING.

10. **How do you handle that relevant sentences may have been dropped by the gate?**
    Each relevant sentence is mapped to the stored segment that stands for it (exact text, otherwise the segment that caused its rejection, otherwise unmapped) and the counts are reported. PENDING until queries exist. Source: eval/retrieval_eval.py.

11. **Why not report a statistical test?**
    With sets this small and one annotator we report bootstrap intervals and say "not distinguishable on this gold set" when intervals overlap. We do not claim more than the intervals show.

12. **What is in `Other`, and does it distort the scores?**
    It holds boilerplate (sign-offs, headline announcements, newsreader names) and accident/crime stories that have no genre of their own. It is 29 of the 175 gold sentences and the label every baseline leans on. Whether it distorts the scores has not been tested.

13. **Are the timings reliable?**
    They are single runs on one laptop GPU. The two-file comparison used 9.50 minutes of audio; the tiny/base timings use five bulletins; the small timing uses the whole sample. Other hardware is unmeasured.

14. **Why is the hour missing for some segments?**
    Morning, Midday and similar bulletins have no time in the file name; 710 stored segments have no hour and are excluded from hour-based features. Source: results/store_reports/store_A_build_report.json.

15. **Could the duplicate-slot files be copies?**
    In option A, no: all 9 pairs have different SHA-256 values, durations differing by 2.98 to 11.42 s, and almost no shared transcript text (Jaccard 0.0008 to 0.0388). Whether this holds elsewhere is UNVERIFIED. Source: results/duplicate_pairs_check.json.

16. **What about the accidental evaluation run?**
    An old test started the real agreement script once the human labels existed. The output was not read and was deleted; the test was replaced; the real run came later with the same seed. Source: ROADMAP.md section 8h.

17. **Are you allowed to use AIR content?**
    Unresolved. robots.txt allowed the crawl and we kept delays; the redistribution rights for audio and transcripts are a TODO, and the annotation sheets contain transcript sentences, so they should not be published before it is answered. Source: paper/draft.md section 8.

18. **Is the retrieval or answer step evaluated?**
    Not yet. Retrieval needs judged queries; answers get only a planned small human check (about 30 questions). Both PENDING.
