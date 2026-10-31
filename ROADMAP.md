# AirInsight - Status and Research Roadmap

Legend: **P0** = blocks publication, **P1** = needed for a strong paper, **P2** = nice to have.
Tags: **UNVERIFIED** = stated from a screenshot, doc or memory, not confirmed. **TODO** = unknown, someone must find out. **OUT OF SCOPE (Thu)** = deliberately not done for the 5 Nov pilot paper, kept for the thesis.
Owners: **Member A** = code, pipeline, evaluation. **Member B** = communication, admin, coordination. **Both** = shared.

---

## 0. Current situation (read this first)

- **Project.** AirInsight is a pipeline that scrapes/ingests All India Radio (AIR) bulletins, transcribes them (Whisper), segments and embeds sentences (MiniLM), drops near-duplicate sentences (cosine >= 0.85), labels genre, stores everything in FAISS + SQLite, and answers questions through two-tier retrieval (SQL prefilter, then FAISS) + Gemini.
- **Status.** The engineering works. The research is almost entirely unmeasured: no gold labels, no evaluation results, and a corpus of only 5 transcripts (4 from May 2024, 1 live-stream test file). Claims in the repo that nothing reproduces: the "+5 pp" fine-tuning gain in `DEMO.md` (it is written as a decision threshold, not a measured result, but it reads like a claim) and a "35-45% redundancy reduction" figure that now survives only inside `generate_architecture_pdf.py` (the old ARCHITECTURE files are no longer in the folder). **We hold no data from the last 2-3 months; it must be scraped.**
- **Two deliverables.**
  1. A short **PILOT PAPER due Thursday 5 Nov 2026**. The professor is strict and will fail us if anything is done improperly or claimed without evidence.
  2. A **THESIS** later, which expands the paper into the full project.
- **Principle: honesty over scope.** A small, correct, clearly labelled pilot is acceptable. Inflated claims, unreproducible numbers and circular evaluation are not.
- **Today is Saturday 31 Oct 2026.** Group of two (Member A, Member B). Four working days remain after today: Sun 1, Mon 2, Tue 3, Wed 4 Nov, then submission Thu 5 Nov.

---

## 1. Implemented fully (working, no known gaps)

| # | Component | File | What it does |
|---|-----------|------|--------------|
| 1 | Archive scraper | `air_bulletins_scraper.py` | AJAX crawl of newsonair.gov.in (`filter_bulletins_audio`), robots.txt check, UA rotation, jittered delays, resume via existing URLs, SHA-256, optional Whisper, incremental CSV rows. *See section 2 items 13-16 for gaps found on re-check.* |
| 2 | Live stream ingestion | `live_stream_ingest.py` | `LiveStreamManager` background thread, ffmpeg 16 kHz PCM, 30 s chunks / 5 s overlap, faster-whisper + VAD, `strip_overlap` stitching, MP3 snapshots, reconnect with retries, start/stop/status |
| 3 | Batch ingest | `ingest_pipeline.py` | Reads `metadata.csv`, incremental via `processed_files.txt`, `--reindex`, writes `dedup_report.json` |
| 4 | Sentence segmentation | `nlp_pipeline.py` | NLTK punkt_tab, BOM stripping |
| 5 | Embeddings | `nlp_pipeline.py` | all-MiniLM-L6-v2, 384-d |
| 6 | Streaming novelty gate | `nlp_pipeline.py` | Cosine >= 0.85 against stored + in-batch pool, records rejected pairs |
| 7 | Three genre backends | `nlp_pipeline.py` | zero-shot BART, fast NLI MiniLM, fine-tuned DistilBERT with fallback |
| 8 | Dual store | `vector_store.py` | FAISS IndexFlatIP + SQLite `segments`, schema migration, stats, wipe, audio path resolution |
| 9 | Two-tier retrieval | `rag_engine.py` | Corpus-anchored date parsing, keyword genre extraction, SQL prefilter -> FAISS, relevance filter, timeline grouping |
| 10 | Generation | `rag_engine.py` | Gemini with grounded prompt + last 3 turns, probed once, extractive fallback |
| 11 | API + UI | `chatbot_api.py` | `/chat /timeline /audio /stats /dedup /health /stream/*`, inline SPA, path-traversal guard on audio |
| 12 | Training toolchain | `build_genre_training_data.py`, `train_genre_classifier.py` | Silver labels, synthetic augmentation, stratified split, class weights |
| 13 | Genre eval harness | `eval_genre.py` | Accuracy + confusion matrix, excludes training texts, zero-shot vs fine-tuned compare |

---

## 2. Implemented halfway (exists but weak, unverified, or buggy)

Ordered by how much each one hurts a paper. Items 13-16 were added after re-checking the scraper source against the data-source findings in section 4.

1. **P0 - Fine-tuned classifier has no trustworthy labels.** Trained on `genre_training_data.csv` (about 375 rows: 374 data rows + header) made of zero-shot silver labels plus synthetic template sentences. Comparing it with the zero-shot model that produced its labels is circular. No human-labelled gold set exists. *Pilot: fix by building a gold set (section 6).*
2. **P0 - No measured results anywhere.** `DEMO.md` states a "+5 pp" threshold for switching to the fine-tuned model; `generate_architecture_pdf.py` still contains a "35-45% redundancy reduction" figure. Nothing in the repo reproduces either. Corpus is 5 transcripts. *Both claims must be removed or backed by `results/` files.*
3. **P0 - Filtered FAISS search may be broken (UNVERIFIED, not yet tested).** `vector_store.semantic_search` passes `SearchParametersIVF` to an `IndexFlatIP`. If that raises, it falls into the `except` branch, which searches only the global top-k and then filters, so a narrow filter can return fewer results than exist, or none. Needs a test; fix with `IndexIDMap` + selector, or search over a reconstructed candidate subset.
4. **P1 - Dedup gate is simplistic.** One fixed threshold (0.85), no justification. Catches near-identical sentences, not paraphrases or follow-ups. The pool is re-stacked with `np.vstack` for every sentence (O(n^2)). Only the batch path writes `dedup_report.json`; the live path does not (confirmed in code).
5. **P1 - Multilingual is nominal.** The scraper accepts hindi/urdu, but segmentation, embedding model, genre keywords, Gemini prompt and classifier labels are English-only. *OUT OF SCOPE (Thu).*
6. **P1 - Sentence timestamps are heuristic.** Live ingest aligns sentences to Whisper segments by character matching. Batch ingest passes no timestamps, so `audio_start`/`audio_end` are NULL for archive bulletins (confirmed in code).
7. **P1 - Date parsing is regex only.** Handles "last N days / week / month / yesterday / today / on D Month / on YYYY-MM-DD / between X and Y". Missing "this week", "last year", "in March"; an unspecified year silently uses the anchor year.
8. **P1 - Genre extraction is keyword lists.** Ties return None; no learned query classifier; single genre only.
9. **P1 - Hour field is inconsistent (confirmed in code).** Batch stores HHMM (e.g. 800) parsed from the filename; live stores `now.hour` (0-23). Timeline sorting mixes the two.
10. **P2 - Gemini dependency.** `gemini-1.5-flash` is hard-coded and may be retired (UNVERIFIED); closed model hurts reproducibility.
11. **P2 - Operational limits.** One live stream at a time, in-memory chat sessions, no auth, SQLite connection opened per call, FAISS index rewritten to disk on every `add_segments`.
12. **P2 - Tests are scripts, not a suite.** `test_*.py` files exist but there is no pytest setup, CI or coverage.
12a. **FIXED in S1 (31 Oct 2026) - Scraper could not reach the live site.** (Was P0.) It posts to `www.newsonair.gov.in` without the WordPress `security` nonce and gets HTTP 403. `air_bulletins_scraper.py` now uses the working request (no-www endpoint, fresh nonce from the archive page, browser headers). Hour parsing now stores 0-23 or empty, never 0 as a placeholder; filenames with no usable time (14 of 167 in the S1 test week) are flagged. Backup of the old file: `air_bulletins_scraper.py.bak`.
13. **DONE in S1 (31 Oct 2026) - metadata-only and sampling modes.** `--metadata-only` writes a listing CSV with no download; `--sample` downloads all bulletins of days chosen by `config/sample_config.json`. (Was: scraper downloaded every item in the range.)
14. **FIXED in S2 + GPU follow-up for the scraper (31 Oct 2026).** Model loads once per run, `--device auto|cuda|cpu` and `--compute-type` replace the hard-coded int8, transcription is resumable, real duration and model settings go to the CSV, and the NVIDIA DLL folders are added automatically on Windows. **Measured on the RTX 2050 (4 GB):** see section 5 and the S2 row. **Still open:** `live_stream_ingest.py` still hard-codes `compute_type="int8"` (not changed), and the A6000 cluster has not been measured.
15. **P1 - Pagination ceiling.** `--max-pages` defaults to 200; with 12 items per page (confirmed by the S3 test) that caps one query at about 2,400 items. Observed English volume is about 24 items per day, so a 3-month range (roughly 2,200 items, extrapolated) sits just under the cap; crawl in date windows (e.g. one week per call) to stay safe. **Done in S1:** the scraper now crawls weekly windows (`--window-days`, default 7) and warns if a window hits `--max-pages`. The S1 test week used 14 of 200 pages.
16. **P1 - Scraper covers only the "Main Audio Bulletins" tab.** It calls `filter_bulletins_audio` with language/category/date. The "Main Audio Broadcast Program" tab (program name filter) has no support. *OUT OF SCOPE (Thu).* `check_robots_txt` only prints a warning when a URL is disallowed; it does not stop the crawl. `robots.txt` at newsonair.gov.in currently allows everything (empty `Disallow:`), checked on 31 Oct 2026.

---

## 3. Not implemented

Tags show the Thursday decision. Detailed pilot sizes are in section 6.

### P0 - without these the paper will be rejected
1. **Gold dataset.** Human-labelled genre (2 annotators + Cohen's kappa), duplicate pairs, relevance judgments, fixed splits. **PILOT SIZE for Thursday (section 6); full size is thesis.**
2. **ASR evaluation.** WER on hand-corrected reference transcripts; compare Whisper sizes. **PILOT: 3-5 bulletins, English only.** (Hindi: OUT OF SCOPE (Thu).)
3. **Retrieval evaluation.** Query set with relevance judgments; recall@k, MRR, nDCG@k; baselines BM25, vector-only, hybrid, relevance filter on/off. **PILOT: about 50 queries.**
4. **Dedup evaluation.** P/R/F1 against labelled pairs; threshold sweep 0.70-0.95; baselines MinHash, TF-IDF cosine, exact match. **PILOT: about 100 pairs.**
5. **Genre evaluation on gold data.** Per-class F1, macro-F1, confidence intervals, multiple seeds; zero-shot, fast, fine-tuned, plus TF-IDF + logistic regression baseline. **PILOT: gold set below.**
6. **Answer-quality evaluation.** **PILOT: reduced to a human check of about 30 questions, reported as such.** LLM-judge and no-retrieval baseline: thesis.
7. **Ablation study.** SQL prefilter on/off, relevance filter on/off + threshold sweep, dedup on/off, classifier backend. **In scope for Thursday.**

### P1 - makes it a strong paper
8. **Scalability benchmarks.** **Thursday: 10k segments only; 100k only if time remains. 1M: OUT OF SCOPE (Thu)** (thesis). Also replace the per-sentence `vstack` with a FAISS-based novelty check (task A4).
9. **Hybrid retrieval** is in the retrieval baselines (A6). **Cross-encoder reranker: OUT OF SCOPE (Thu).**
10. **Context-aware segments** (windows/paragraphs): **OUT OF SCOPE (Thu).**
11. **Open-weights generator baseline:** **OUT OF SCOPE (Thu).**
12. **Hindi / multilingual support:** **OUT OF SCOPE (Thu).** Reason: whole pipeline is English-only and the 5-day window cannot cover re-labelling and re-evaluating a second language honestly.
13. **Learned query understanding:** **OUT OF SCOPE (Thu).**
14. **User study / case study:** **OUT OF SCOPE (Thu).**

### P2 - polish (all OUT OF SCOPE (Thu))
15. Multi-label genres; story clustering across days (the "timeline" is currently sorted retrieval results).
16. Citation verification against retrieved segments and audio timestamps.
17. Multi-stream support, persistent sessions, auth, Docker image, CI.

---

## 4. Data source findings (https://newsonair.gov.in/audio-archive-search/)

Findings come from screenshots, a read of the scraper and the S3 one-week test (results below). Items still marked UNVERIFIED have not been tested.

> **S3 RESULT (31 Oct 2026): crawl succeeded, metadata only, 119 items, no audio downloaded.** Real numbers, from `data/test_crawl_metadata.csv` (English, `filter_bulletins_audio`, 2026-10-19 to 2026-10-25, all categories):
>
> - **Old scraper is broken for the live site.** It posts to `www.newsonair.gov.in` with no nonce and gets HTTP 403 `{"success":false,"data":"Invalid request"}`. The working request (in `crawl_test_metadata.py`) POSTs to `https://newsonair.gov.in/wp-admin/admin-ajax.php` with a WordPress nonce in field `security`, read fresh from the archive page's inline JS (`security: '...'` right after `action: 'get_listen_news_categories'`), plus Origin, Referer, `X-Requested-With: XMLHttpRequest`. Which of the two missing pieces (no-www host vs nonce) actually caused the 403 was not tested separately. **`air_bulletins_scraper.py` must be updated before any real crawl (task S1).**
> - **Response format:** HTML fragments. Categories call returns `<option>` tags (`morning-news, midday-news, evening-news, hourly-news, midday-news-hi, hourly-news-hi, urdu, news-at-nine`; the list is not filtered by language). Listing call returns `<li>` cards parsed by the existing `parse_bulletins`.
> - **Pagination:** 12 items per page, 10 pages for the week (12 x 9 + 11 = 119), last page reported no next link. 119 distinct audio URLs, no duplicates, no empty URLs, page cap (200) not approached.
> - **Date filter bounds are EXCLUSIVE on both ends (S3c, 31 Oct 2026; inferred from 4 first-page probes).** `date_from` and `date_to` return only days strictly between them. So the week crawl 19 to 25 Oct returned only 20-24 Oct (24, 24, 23, 24, 24 items), but **19 Oct and 25 Oct do exist in the archive** (they were skipped by the bounds, not missing):
>
>   | date_from | date_to | Result (page 1, newest first) | Pages |
>   |-----------|---------|-------------------------------|-------|
>   | 2026-10-19 | 2026-10-19 | `No posts found` (empty interval) | 0 |
>   | 2026-10-18 | 2026-10-20 | 12 items, all 19 Oct | 3 |
>   | 2026-10-24 | 2026-10-26 | 12 items, all 25 Oct (no 24 or 26 Oct on page 1) | 2 |
>   | 2026-10-30 | 2026-10-31 | `No posts found` (no whole day lies strictly between 30 and 31 Oct) | 0 |
>
>   Residual uncertainty from S3c (RESOLVED in S1): the 3 pages for 18-20 Oct implied 25-36 items on 19 Oct; the S1 crawl found exactly 25 on 19 Oct and 23 on 25 Oct, consistent with exclusive bounds. **30 Oct and 31 Oct exist** (S3d: 23 and 16 items; 31 Oct was still in progress when crawled). To include a day D the request needs `date_to = D + 1`; the scraper's windows do this.
> - **Window rule for the scraper (no day skipped, no day counted twice):** to fetch the days D1..Dn (inclusive), send `date_from = D1 - 1 day` and `date_to = Dn + 1 day`. For consecutive windows covering days a..b then b+1..c, send (a-1, b+1) then (b, c+1); the windows overlap only in the bounds, which are excluded, so there is no double count. Single day D: (D-1, D+1). Still de-duplicate by `audio_url` and check per-day counts after every crawl.
> - **Titles:** Hourly News 104, Morning News 5, Midday News 5, Evening News 5.
> - **Audio:** every item has a direct `.mp3` URL under `https://newsonair.gov.in/wp-content/uploads/YYYY/MM/`, e.g. `.../2026/10/English-2305-2310-18.mp3`, `.../2026/10/1905` style names like `English-1905-1.mp3`, `.../2026/10/2205ee-1.mp3`. Filenames are inconsistent (about 12 patterns).
> - **Hour of day:** parseable from the filename for **111 of 119** items with the scraper's rule (first standalone 4-digit group in the filename, `(?<!\d)(\d{4})(?!\d)`), all 111 valid as HHMM. The scraper stores the value as an integer, so leading zeros are lost (`0005` becomes 5, `0105` becomes 105): **hour = value // 100**. The 8 failures: 7 have no digits (`Mid-Day-English.mp3`, `midday-eng.mp3`, `middday-1.mp3`, `midday-english-4.mp3`, `Midday-News-Eng.mp3`, `News-At-Nine-1.mp3`, `nine-6.mp3`) and 1 has a 5-digit group (`English01055.mp3`). All 5 Midday News items have no hint. `ingest_pipeline._extract_hour` uses the same 4-digit regex on the transcript filename and returns 0 when it fails, so those items would be stored as hour 0 unless handled.
> - **Observed volume (S3d, measured):** see the "S3d RESULT" block below; the extrapolation of about 2,200 items for 3 months was close (measured 2,173).
> - **Same-time duplicates (measured in S3d, cause UNVERIFIED):** 124 (date, HHMM) pairs occur on 2 different audio files (250 items involved), e.g. 2026-08-07 `English-0105-0110-12.mp3` and `English-0105-0110-11.mp3`, or `English0305.mp3` and `English-0305-0310-6.mp3`. Different filenames and different numeric suffixes, so they are separate uploads at the same slot; whether the content is identical (re-upload) or two different bulletins was NOT checked. This affects de-duplication evaluation and must be checked on the sampled audio.
>
> **S3d RESULT (31 Oct 2026): 3-month metadata crawl, English, all categories, 2026-08-01 to 2026-10-31 (inclusive), `data/metadata_3month_english.csv`. No audio, no Whisper, no errors or blocks.**
>
> | Measure | Result |
> |---------|--------|
> | Total items | **2,173** (2,173 distinct audio URLs, **0 duplicates**) |
> | Weekly windows / pages | **14 windows** (13 full weeks + 31 Oct alone), **184 pages** (14 per full week, 2 for the last window), 0 truncation, 0 items outside windows |
> | Days covered | 92 of 92 days have items; **0 days with 0 items**; 728 items in Aug, 717 in Sep, 728 in Oct |
> | Per-day count | min 16, max 25, median 24, mean 23.6. Distribution: 24 items on 59 days, 23 on 23 days, 25 on 5, 22 on 3, 21 on 1, 16 on 1 |
> | Unusual days | **31 Oct = 16** (day still in progress when crawled; do not treat as complete). **15 Aug = 21** (Independence Day, lowest full day). 22 items on 6 Aug, 7 Oct, 16 Oct. 25 items on 19 Aug, 21 Aug, 22 Aug, 4 Sep, 19 Oct |
> | 30 / 31 Oct | present: 23 and 16 items |
> | Titles | Hourly News 1,896; Midday News 92; Morning News 92; Evening News 87; News At Nine 2; other 4 (`प्रति घंटा समाचार` x2, `दोपहर समाचार` x1, `Urdu` x1) |
> | Hour parsed (0-23) | **2,030 of 2,173**; **143 flagged** (141 `no_time_in_filename`, 2 `invalid_hhmm`: `9999.mp3`, `eng-6005.mp3`) |
> | Flagged by title | Midday News 61 of 92, Evening News 36 of 87, Hourly News 30 of 1,896, Morning News 12 of 92, News At Nine 2, Hindi/Urdu 2 |
>
> Notes: exactly one Morning and one Midday item per day (92 each). Evening News is missing on 5 days (11 Aug, 20 Aug, 15 Oct, 19 Oct, 31 Oct); two of the `News At Nine` items (11 Aug, 19 Oct) are on days that lack Evening News, so they are probably the same bulletin under a different title (UNVERIFIED). About 20.6 Hourly News items per day, so some of the 24 hourly slots are absent on most days. **4 items in the "english" listing are Hindi/Urdu bulletins** (e.g. `Hindi-1900-1905-11.mp3`, `hindi-2.mp3`, `uurdu-1.mp3`) and must be filtered out of the English corpus before sampling.
>
> **Extrapolation check:** the roadmap's estimate was about 2,200 items; measured 2,173 (1.2% lower). **Screenshot figure:** 1,686 pages x 12 is about 20,200 items. At the measured 23.6 items/day that equals roughly 857 days, about 2.3 years, i.e. an archive starting around mid-2024. That is consistent with our May 2024 sample files, but it is an inference: the full archive was NOT crawled, so the screenshot figure is still UNVERIFIED (the screenshot may also have mixed languages or categories).
> - The "1,686 pages / about 20,000 items" screenshot figure is still UNVERIFIED (not tested with a wide date range).

- The archive is current (bulletins dated 31 Oct 2026). Ignore the page footer's "Last Updated: 18th Aug 2026".
- Two tabs:
  - **"Main Audio Broadcast Program"**: filters are category, program name, date from/to.
  - **"Main Audio Bulletins"**: filters are type (English / Hindi / Urdu), category, date from/to. This is the tab our scraper's `filter_bulletins_audio` action matches.
- Results load via AJAX, **12 items per page (confirmed by S3)**, numbered pagination. Screenshots showed **1,686 pages for bulletins (about 20,000 items)** and **77 pages for Daily Broadcast**; the bulletins figure is plausible against the S3d measurement (2,173 English items in 92 days is about 23.6 per day, about 2.3 years for 20,200 items) but still UNVERIFIED because the full archive was not crawled; the Daily Broadcast figure is untested.
- Bulletin lengths seen: about 4.5-5 min each (e.g. "Hourly News"); "Morning News" about 14-15 min.
- Each card has an HTML audio player, a title and a date. The scraper reads the audio URL from `<audio><source src>` (**confirmed by S3: all 119 items had a direct `.mp3` URL**). **There is no time of day on the card**; the hour has to come from the audio URL/filename. The scraper does this with a 4-digit regex on the filename (`extract_time_hint`); **S3 result: it works for 111 of 119 filenames; the other 8 (all 5 Midday News plus 3 others) have no 4-digit time**, so they need a fallback or are excluded from hour-based features.
- **The card's "Transcript" is only an accessibility blurb (title + date), NOT the spoken content.** All text must come from our own Whisper transcription. The pages `/bulletins-detail-archive/` and `/text-archive-search/` may hold real text; they are **UNCHECKED**.
- Daily Broadcast contains Hindi programs (e.g. विश्व दर्पण, Surkhiyon Mein) of about 9-30 min. Not used for the pilot.
- `robots.txt` must be respected. The scraper checks it, but only warns on a block (section 2 item 16). Government-content licensing goes in the ethics/limitations section of the paper; whether audio or only transcripts may be redistributed is TODO.
- **Strategy.** Scrape METADATA for the whole range (about 2-3 months), but **download and transcribe only a SAMPLE**: full days spread over about 2-3 weeks, English only. Do not plan to transcribe the full archive. Scraping runs at HOME, not on the college cluster. The exact sample dates are TODO and must be chosen by a fixed rule and saved in a config file, not by hand-picking.

---

## 5. Compute environment

**Home GPU (Sat-Sun): NVIDIA GeForce RTX 2050, 4 GB VRAM** (driver 610.74, CUDA 13.3, `nvidia-smi` works). An earlier S2 check wrongly concluded there was no CUDA GPU: ctranslate2 reported 0 devices and PyTorch is a CPU build; that was a driver/library-state problem, not missing hardware (in the later check `ctranslate2.get_cuda_device_count()` returned 1 from the system Python too; why it returned 0 earlier is UNVERIFIED, possibly the GPU was asleep on this hybrid-graphics laptop; the missing piece for actually running was cuBLAS). **GPU environment: virtual environment `.venv_gpu` in the project folder** (Python 3.11.9; `faster-whisper 1.2.1`, `ctranslate2 4.8.4`, `nvidia-cublas-cu12 12.9.2.10`, `nvidia-cudnn-cu12 9.27.0.42`, plus the project requirements). Activate with `.venv_gpu\Scriptsctivate` (PowerShell/cmd) or `source .venv_gpu/Scripts/activate` (Git Bash); or call `.venv_gpu/Scripts/python.exe` directly. CTranslate2 4.x needs CUDA 12 + cuDNN 9 (evidence: the ctranslate2 4.7.1 wheel ships `cudnn64_9.dll`; the faster-whisper README states this requirement, quoted from memory, not re-checked), which is why the `nvidia-*-cu12` pip packages are installed. `air_bulletins_scraper.py` adds `site-packages/nvidia/*/bin` to the DLL search path and PATH at import, so no manual PATH step is needed; if that ever fails, the one-line fix is to add those `bin` folders to PATH. PyTorch in the venv is the CPU build unless a CUDA build is installed (not done; optional for fine-tuning, which falls back to CPU). **Measured transcription speed, faster-whisper on the RTX 2050, 2 hourly bulletins (4.76 and 4.74 min, 9.50 min total):**

| Model | Compute type | Real-time factor | Transcription time | Peak VRAM | Chars (file 1 / file 2) |
|---|---|---|---|---|---|
| base | float16 | **0.042** | 23.9 s | 369 MiB | 4390 / 4484 |
| base | int8_float16 | **0.043** | 24.6 s | 273 MiB | 4389 / 4510 |
| small | float16 | **0.067** | 38.2 s | 881 MiB | 4375 / 4512 |
| small | int8_float16 | **0.072** | 41.0 s | 593 MiB | 4375 / 4488 |
| base (CPU, int8) | int8 | 0.100 | 56.8 s | n/a | 4392 / 4497 |
| small (CPU, int8) | int8 | 0.264 | 150.6 s | n/a | 4377 / 4494 |

No combination ran out of memory. VRAM was sampled every 0.5 s with `nvidia-smi`; it was 0 MiB before each run. Transcript lengths agree with the CPU transcripts within about 0.5% (text was not compared word for word). The first file of each run includes GPU warm-up. The GPU is about 2.4x faster than CPU for `base` and 3.9x for `small`. `medium` was not measured (it should fit in 4 GB with float16 but this is UNVERIFIED). Only two hourly bulletins were timed, so Morning/Midday/Evening bulletins and a larger sample may behave differently. The laptop is used for scraping, downloading, development, small-scale tests and Whisper transcription, and as the fallback if the cluster is unusable.

**SPIT GPU cluster (Mon-Tue; Wed uncertain, so treat Tue night as the last time any GPU job can run).** Facts from the cluster docs:

| Item | Detail |
|------|--------|
| Hardware | 2x NVIDIA RTX A6000, 112 cores, 250 GB RAM |
| Scheduler | Slurm; max job time 7 days (partition: `general`) |
| Interactive apps | Jupyter, VS Code, Desktop via cluster.gpu.spit.ac.in; **capped at 1.5 hours**; development/testing only |
| Long jobs | **Must be submitted with `sbatch`** |
| Software | `module load python/3.11.14`, then `uv venv <env>`, `source <env>/bin/activate`, `uv pip install ...`. Conda (`module load miniconda3`) and Apptainer (`--nv`) also available |
| Templates | `templates/`: `gpu_single` (1 GPU, 32 cores, 64 GB) is the default; `gpu_max` only if truly needed |
| Their rules | Test locally first, then a short test job (`#SBATCH --time=00:05:00`), then the real job; monitor with `squeue -l` and `nvidia-smi`; use `gpu:1`; set `--job-name` and `--output` |
| Terms | GPUs only for the approved task; **misuse may mean a 2-year ban** |
| Admins | varun.jhaveri23@spit.ac.in, rehan.ansari24@spit.ac.in |

**UNVERIFIED (to be answered by the admins; see Member B tasks):** remote access from home (VPN?); internet access from compute nodes (newsonair.gov.in, pip, Hugging Face); whether ffmpeg is installed or a module exists; CUDA libraries for faster-whisper; queue wait times; whether our use counts as an approved task.

**Plan consequences:**
- All long stages (transcription, training, evals, scale test) run as `sbatch` jobs split into **resumable stages**.
- Copy audio, code and model weights to the cluster if compute nodes lack internet.
- The live-stream demo runs on our own machine, not the cluster.
- **Cluster smoke test (Sunday night):** a 5-minute `sbatch` job that checks CUDA, ffmpeg, imports, and one short transcription. Do not rely on the cluster for anything until this passes.

---

## 6. Scope decisions

### Thursday pilot paper (5 Nov)
**Contribution statement:** "a pilot-scale, human-labelled evaluation of a streaming novelty-filtering + two-tier retrieval pipeline over All India Radio bulletins, with baselines; the full dataset and large-scale evaluation are future work (thesis)."

**OUT OF SCOPE for Thursday, with reasons:**

| Item | Reason |
|------|--------|
| Hindi / multilingual | Whole pipeline is English-only; honest second-language evaluation does not fit in 5 days |
| 1M-segment benchmark (10k kept; 100k only if time remains) | Compute and time; a 10k result is enough for a pilot |
| Cross-encoder reranker | Not needed to answer the pilot question; adds a model to tune and defend |
| Open-weights generator baseline | Answer quality is a small human check only |
| User study | Needs recruiting and ethics handling |
| Learned query understanding | Regex/keyword parsing is stated as a limitation instead |
| Context-window chunking | Single-sentence chunks stated as a limitation |
| Multi-label genres, all P2 items | Not required for the pilot claim |
| Full answer-quality evaluation | Reduced to a human check of about 30 questions, reported as such |

**Pilot gold-set targets (state the exact final sizes in the paper):**
- about 300-500 genre-labelled sentences, with a 150-200 sentence overlap labelled by a SECOND annotator (report Cohen's kappa)
- about 100 duplicate pairs
- about 50 queries with relevance judgments
- WER on 3-5 hand-corrected bulletins across Whisper sizes

If annotation slips, shrink the gold set; never relax the rigor (no unlabelled data reported as gold).

### Thesis (after Thursday): keep the full plan
1,500+ genre-labelled sentences, 500+ duplicate pairs, 200+ queries, kappa >= 0.7; 3 months English + 1 month Hindi; all baselines, ablations, seeds, scale benchmarks (10k / 100k / 1M); hybrid + reranker; open-weights baseline; user or case study. The 16-week plan is kept below as **Thesis plan (after Thursday)** (section 12).

---

## 7. Strict-review checklist (replaces the old definition of done)

- [ ] **No circular evaluation.** Evaluate the fine-tuned classifier only on human-labelled gold data, with gold texts excluded from training. Never compare against the zero-shot model on its own silver labels.
- [ ] Every README/DEMO/script claim is removed or backed by a script that reproduces it from `results/` (known offenders: DEMO "+5 pp" wording, "35-45%" in `generate_architecture_pdf.py`).
- [ ] Baselines run: BM25, vector-only, TF-IDF + logistic regression (genre); MinHash, TF-IDF, exact match (dedup).
- [ ] Real second-annotator Cohen's kappa, even on a small subset.
- [ ] Seeds and config files saved; **one command regenerates every table**; every number in the paper comes from a saved file in `results/`.
- [ ] Dedup threshold chosen on validation data, not by hand.
- [ ] Confidence intervals reported; no "significant" without a test.
- [ ] Limitations stated plainly: small corpus, single-sentence chunks, keyword date/genre parsing, English only, single genre per sentence, ASR errors, government-content licensing, hallucination risk.
- [ ] FAISS filtered-search bug fixed and covered by a test.
- [ ] Hindi explicitly marked out of scope in the paper.
- [ ] Gold set labelled as pilot-scale everywhere it appears (paper, slides, README).

---

## 8. Day-by-day schedule

Style: one task per prompt, test before moving on. "Test" is what must pass before the next row starts.

### Sat 31 Oct - home GPU - Member A
| Step | Task | Test before moving on |
|------|------|-----------------------|
| A1 | **DONE (31 Oct 2026).** `vector_store._filtered_search`: base `faiss.SearchParameters` + `IDSelectorBatch` instead of `SearchParametersIVF`; the exception fallback now scores the candidate vectors directly (the old fallback searched the whole index and then filtered, so it returned fewer than k or nothing). Duplicate/out-of-range candidate ids are ignored; fewer candidates than k returns all of them. **UNVERIFIED / honest note:** with the pinned faiss 1.15.0 the OLD primary path (`SearchParametersIVF` on a flat index) returned correct results in 200 random trials, so the failure was NOT reproduced there; the test that failed on the old code is the fallback path (3 of 11 failed). Tests: `tests/test_vector_store_filter.py` (11 passed). | pytest: narrow filter on a 1,000-vector index returns exactly top-k from the candidates |
| A2 | **DONE for code and tests (31 Oct 2026); migration NOT run on a real store.** Batch ingest now stores 0-23 (`ingest_pipeline._extract_hour_and_flag`, same rule as the scraper's `parse_hour_from_url`); no/invalid time gives NULL plus `hour_flag` (`no_time_in_filename` / `invalid_hhmm`), never 0; `add_segments` rejects any hour outside 0-23 (so HHMM can no longer slip in); `rag_engine` sorts NULL hours last; the web UI formats 0-23. `migrate_hour_to_0_23.py --db <COPY> [--dry-run]` re-derives hours from `source_file` (the stored number is ambiguous: batch 5 = 00:05 collides with live hour 5, and 0 meant both 'no time' and midnight), is idempotent, and refuses the project's own `news_store.db`. **No `news_store.db` or `faiss_index.bin` exists in the project folder, so the migration was tested only on a synthetic old-schema copy; running it on the real store is TODO/UNVERIFIED.** Tests: `tests/test_hour_unification.py`. | Timeline sort test across batch + live rows |
| A4 | **DONE (31 Oct 2026).** `mmr_novelty_filter_detailed` uses a preallocated pool (no per-sentence `np.vstack`); output identical to the old version on 12 seeded fixtures plus edge cases (zero vector, exact tie, empty input, no existing pool); threshold still 0.85 (not changed here). Timing, 10,000 sentences x 384-d, one run on this laptop CPU: **old 48.4 s, new 1.6 s**, identical kept/dropped (6,951 / 3,049 on a synthetic input; not real data). Live path now calls the gate with `detailed=True` and writes `dedup_report_live.json` in the same schema as batch (`DedupStats`, now shared by both). **UNVERIFIED:** the live stream path was not run end-to-end (needs a stream and ffmpeg); only checked by `test_live_stream.py` and a source-level test; the live loop still does one `np.vstack` per chunk for its cache (not per sentence). Tests: `tests/test_novelty_gate.py` | Output identical to old implementation on the 5 sample transcripts; faster on a synthetic pool |
| A3 | pytest suite from the existing `test_*.py` | `pytest` passes from a clean checkout |
| S1 | **DONE (31 Oct 2026).** Scraper ported to the working request; robots.txt now stops the crawl; `--metadata-only`, weekly windows following the exclusive-bound rule, hour 0-23 or empty (flagged), `--sample` with `config/sample_config.json`, `--limit`, `--yes`. Test results: metadata-only 19-25 Oct = **167 items** (25, 24, 24, 23, 24, 24, 23 per day; equals the 119 from S3 plus 25 for 19 Oct and 23 for 25 Oct; 14 pages; 0 zero-item days; hour parsed for 153/167, 14 flagged). `--sample --limit 2` on the same week chose 19 and 24 Oct (49 items, 165 min estimated for 29 of them), downloaded 2 files, SHA-256 in the CSV matches a recomputed hash. Test outputs are under `data/` only; `output/` was not touched. | Both tests passed. **Left for later:** `ingest_pipeline._extract_hour` still returns 0 for filenames without a time (the 14 flagged items would be stored as hour 0 at ingest); the sample plan does not yet estimate duration for items without an HHMM-HHMM filename; Whisper code untouched (S2) |
| S3 | **ONE-WEEK PART DONE (31 Oct):** 119 items; bound behaviour resolved in S3c (exclusive bounds, see section 4 window rule). **S3d DONE (31 Oct):** 3-month crawl in 14 weekly windows, 2,173 items, 92/92 days covered, results in section 4. **Remaining:** none for S3; next is choosing the sample (not yet done) | 3-month crawl finished with 0 duplicates and 0 zero-item days |
| B1 | **DONE for option A (31 Oct 2026, S5):** 239 files, 782.9 MB, 0 failures, SHA-256 verified, all transcribed with `small` float16 on the RTX 2050 in 82 min (RTF 0.0568). Details in section 8a | `metadata.csv` rows match files on disk; SHA-256 stored; no robots.txt block |
| S2 | **DONE (31 Oct 2026); CPU numbers first, GPU numbers in section 5.** Model loaded once per run (confirmed: "model loads this run: 1"), `--device auto|cuda|cpu`, `--compute-type`, `--model`, resumable transcripts (rerun skipped both files), real duration (ffprobe) and model/device/compute type/seconds/RTF in the CSV, per-file line with audio duration, time and real-time factor, VAD left at default (off). Added `--transcribe-only` (no network, no download) to test on existing files. **Measured on the 2 files in `data/s1_test_out/` (hourly bulletins of 4.76 and 4.74 min, copied to `data/s2_test_*` for the test), faster-whisper, CPU, int8:** `base`: 56.8 s transcription for 9.50 min of audio, **real-time factor 0.100** (0.097 and 0.102), model load 1.5 s. `small`: 150.6 s for 9.50 min, **real-time factor 0.264** (0.258 and 0.271), model load 89 s (first download). **GPU runs were done afterwards (see section 5): RTX 2050, `base` float16 real-time factor 0.042, `small` float16 0.067** (the CPU-only note above was written before the GPU was working). | Both CPU runs produced non-empty transcripts (about 4,400 characters each). **Sample-size consequence (arithmetic from these 2 files only, at RTF 0.10 on this CPU, `base`):** 1 hour of audio takes about 6 minutes to transcribe; `small` about 16 minutes. Hourly bulletins are about 4.7 min (not the 5 min the filename implies), and measured durations exist only for these 2 hourly files; Morning/Midday/Evening durations are still unmeasured (TODO), so a per-day total is not yet known. Remaining: measure the A6000 on the cluster; `live_stream_ingest.py` still has `int8` hard-coded |

### Sun 1 Nov - home GPU - Member A unless noted
| Step | Task | Test before moving on |
|------|------|-----------------------|
| - | Finish transcription | All sampled files transcribed |
| A5 | **DONE (31 Oct 2026, skeleton only).** `eval/eval_config.py`, `eval/eval_common.py` (`write_result` stores timestamp, seed, git commit (null: not a repo) and SHA-256 of inputs), `eval/README.md` (result file -> proposed paper table; table numbers PROPOSED), stubs `genre_eval.py`, `dedup_eval.py`, `retrieval_eval.py`, `asr_eval.py`: with unlabelled gold they print a message and exit 3, with labelled gold they exit 4 (metrics not written); no stub writes a result or a number. Tests: `tests/test_eval_skeleton.py` | Any eval writes `results/<name>.json` |
| A6 | **CODE DONE (31 Oct 2026); real evaluation waiting for queries.** `eval/retrieval_eval.py`: gold-to-store mapping (exact / via gate rejection / unmapped, counts reported), BM25, vector-only, date-prefilter + vector, full system (genre + date prefilter + vector + relevance filter, no LLM); recall@1/3/5/10, MRR, nDCG@5, per-query results, bootstrap CIs. Tested on a synthetic store only (`tests/test_eval_metrics.py`). Exits 3 until `data/gold/query_sheet.csv` has judged queries. UNVERIFIED on real data. | Runs on a tiny hand-made query set and prints a table |
| A7 | **CODE DONE (31 Oct 2026); real evaluation waiting for pair labels.** `eval/dedup_eval.py`: sweep 0.60-0.95, bootstrap CIs, threshold chosen on val pairs and reported on test pairs, positive = same + paraphrase (alternative: only same, also reported), baselines exact / normalised / TF-IDF cosine / word 5-gram Jaccard. MinHash baseline NOT implemented (TODO). Synthetic tests only. The pair sheet is band-stratified, so results describe the sample, not deployment. UNVERIFIED on real data. | Runs on a tiny labelled pair set |
| A8 | **CODE DONE (31 Oct 2026); real evaluation waiting for genre labels.** `eval/genre_eval.py`: macro-F1 (classes with >= 5 gold examples only), per-class P/R/F1 + support, confusion matrix, bootstrap CIs, majority-class and TF-IDF + LR baselines trained on train-day SILVER labels only, Cohen's kappa on the overlap file. NOT done: scoring the project's own classifier; multi-seed runs. Synthetic tests only; UNVERIFIED on real data. | Runs and clearly prints "silver" in output |
| A9 | **CODE DONE (31 Oct 2026); real evaluation waiting for hand-corrected references** in `data/gold/asr_refs/` (none exist). `eval/asr_eval.py`: WER with S/D/I per file and overall for tiny/base/small, documented normalisation (numbers not converted). tiny/base outputs are transcribed on demand (that path has never been run; UNVERIFIED). Synthetic tests only. | Runs on 1-2 bulletins with a hand-corrected reference |
| - | **DONE as skeleton (31 Oct 2026):** `run_all.py` with stages ingest, genre, dedup, retrieval, asr, `--stage`, `--force`, `--list`, state in `results/run_all_state.json`, skip-if-done (inputs hashed), stops with exit 3 at the first stage whose gold is missing. **Not done / UNVERIFIED:** `--device` and `--model` flags (ingest stage has only `--classifier`); the full chain was never run end to end because no gold is labelled; the eval stages are stubs. Original task: `run_all.py` skeleton: resumable stages, `--device`, `--model` flags | Dry run on a tiny subset completes |
| Night | Copy code + sample to the cluster; run the **5-minute smoke test** (CUDA, ffmpeg, imports, one short transcription) | Smoke test passes, or fallback to home GPU is decided |
| Both | Start annotation (review Claude's pre-labels). Member B or a third person starts the second-annotator overlap subset. Start drafting paper sections | Gold files saved under `data/gold/` with the split recorded |

### Mon 2 Nov - cluster (sbatch) - Member A
| Task | Test |
|------|------|
| Run the full pipeline on the sample in resumable stages | Each stage writes a marker; re-running skips finished stages |
| Fine-tune the classifier; evaluate on gold only | Gold macro-F1 reported next to zero-shot and TF-IDF + LR |
| Run genre, dedup and retrieval evals on gold | Tables saved to `results/` |

### Tue 3 Nov - cluster (sbatch) - Member A
| Task | Test |
|------|------|
| ASR WER across Whisper sizes | Table in `results/` |
| Ablations: prefilter on/off, relevance filter on/off + threshold sweep, dedup on/off, classifier backend | One JSON per ablation |
| 10k scale benchmark | Latency and memory saved |
| **ALL tables final by Tue night** (last time any GPU job can run) | Table-generating command reproduces them |

### Wed 4 Nov - Both - buffer only
Fix failures, finish writing. **No new experiments.**

### Thu 5 Nov - Both
Polish, verify every number against `results/`, tick the section 7 checklist, submit.

**Priority if time runs short:** (1) A1, A2, A4; (2) A6-A8; (3) gold labels; (4) `run_all.py`; (5) everything else. If annotation slips, shrink the gold set, never the rigor.

---

## 8a. S4 - Sample plan (option A CHOSEN and DONE in S5; option B not downloaded)

### S5 results (31 Oct 2026, option A only, all MEASURED)

`--sample` now reads the explicit day lists from `config/sample_config.json` (`--sample-option A`); partial downloads go to `.part` and are renamed only when complete. Files are in `data/sample_A/` (`audio/`, `text/`, `metadata.csv`, `sample_plan.json`, `transcribe_log.txt`). `news_store.db`, `faiss_index.bin` and `output/` were not touched.

| Quantity | Estimate in S4 | **Measured in S5** |
|---|---|---|
| Files | 239 | **239**, 0 download failures, 0 leftover `.part`, all 239 SHA-256 values match a recomputed hash |
| Download size | about 0.4 GB (UNMEASURED) | **782.9 MB** (Morning/Midday/Evening/News At Nine files are about 14 MB each, so the estimate was too low) |
| Download time | 6-12 min (UNMEASURED) | **about 15 min** for 237 files (this run only, includes 1-3 s politeness delay per file) |
| Audio, total (ffprobe) | 1,441 min | **1,441.3 min (24.02 h)** |
| Hourly files | 4.74 min each (2 files) | **209 files, mean 4.78 min** (998.7 min) |
| Morning/Midday/Evening/News At Nine | 15 min each (assumed) | **30 files, mean 14.75 min** (442.6 min). The assumption held, but only for this sample |
| Transcription, Whisper `small`, GPU float16 | about 97 min (RTF 0.067) | **81.9 min of transcription, 82.2 min wall time incl. one model load, RTF 0.0568** |
| RTF, hourly files | 0.067 | **0.0576** (209 files, 57.5 min for 998.7 min of audio) |
| RTF, Morning/Midday/Evening/News At Nine | unmeasured | **0.0551** (30 files, 24.4 min for 442.6 min of audio) |
| Failed or empty transcripts | - | **0** (all 239 have a transcript file of at least 20 bytes; content quality not checked) |

The earlier RTF of 0.067 came from 2 files with warm-up included, so it was slightly pessimistic. Still unmeasured: RTF on the A6000, `medium` fit in 4 GB, sentence counts after segmentation, embedding/classification time.

**Duplicate-slot pairs inside option A (analysis only, `eval/duplicate_pairs_check.py`, `results/duplicate_pairs_check.json`).** 9 pairs found, as expected. In all 9, the two files have different SHA-256 values, different durations (differences 3.0 to 11.4 s), and almost no shared text: word 5-gram Jaccard between 0.0008 and 0.0388 (thresholds are our own choice and are saved in the JSON; 'different text' means Jaccard below 0.3). In this sample the same-slot files are therefore **different recordings, not copies**. All 9 pairs are 01:05 or 03:05 night bulletins. Not shown by these numbers: whether other slots, other months, or the ones outside option A behave the same way, and which of the two files is the 'right' one. These pairs should not be treated as duplicates of each other.

### Original S4 plan (kept for reference; estimates below were made before the S5 measurements)

Full machine-readable plan: `config/sample_config.json`, block `pilot_plan_s4` (explicit day lists are the source of truth and must not be re-drawn). Built offline from `data/metadata_3month_english.csv`.

**Pool.** 2,173 listed items, minus 31 Oct (incomplete day, 16 items) = 2,157, minus the 4 Hindi/Urdu items = **2,153 items over the 91 days 1 Aug to 30 Oct 2026**.

**Fixed seeded rule (seed 42).** Strata = month x {weekday, weekend}. Days are shuffled with `random.Random(42)` per stratum and accepted only if no two chosen days are consecutive calendar days (limits story overlap between splits). Option A is nested inside option B, so extending A to B never changes A's days or A's split. Splits are by WHOLE DAYS (never by sentence or hour, because adjacent hourly bulletins overlap), assigned by seeded rejection sampling so the test set has a weekend and a weekday and spans several months. Duplicate-slot pairs (two different audio files with the same date and the same parsed HHMM) were not a selection criterion; they were checked afterwards.

| | **Option A: 10 days** | **Option B: 22 days** (A + 12 more) |
|---|---|---|
| Days | 08-10, 08-16, 08-28, 09-03, 09-06, 09-30, 10-19, 10-21, 10-24, 10-27 | A plus 08-01, 08-07, 08-14, 08-21, 08-24, 09-10, 09-13, 09-17, 09-28, 10-03, 10-13, 10-29 |
| Mix | 3 weekend + 7 weekday; Aug 3 / Sep 3 / Oct 4 | 6 weekend + 16 weekday; Aug 8 / Sep 7 / Oct 7 |
| Items | **239** (209 hourly, 30 Morning/Midday/Evening/News At Nine) | **524** (458 hourly, 66 other) |
| Split (days / items) | train 6 / 144, val 2 / 48, test 2 / 47 | train 14 / 334, val 4 / 95, test 4 / 95 |
| Test days | 08-28 (Fri), 09-06 (Sun) | 08-21, 08-28, 09-06, 10-13 |
| Duplicate-slot pairs | **9** pairs on 8 of 10 days (train 5, val 2, test 2) | **29** pairs on 19 of 22 days (train 17, val 6, test 6) |
| Audio, central estimate | **about 1,441 min (24.0 h)**, range 1,291-1,591 | **about 3,161 min (52.7 h)**, range 2,831-3,491 |
| Transcription, GPU `small` float16 (RTF 0.067) | about 97 min | about 212 min |
| Transcription, GPU `base` float16 (RTF 0.042) | about 61 min | about 133 min |
| Transcription, CPU `base` int8 (RTF 0.100), for reference | about 144 min | about 316 min |
| Raw sentences before dedup (estimate, 33.5 per hourly bulletin) | about 7,000 | about 15,300 |
| Download (UNMEASURED) | about 6-12 min, about 0.4 GB | about 13-26 min, about 0.9 GB |

**What is measured and what is an estimate.** Measured: the hourly bulletin length, 4.74 min (2 files, 4.76 and 4.74), the real-time factors (2 hourly files, about 9.5 min, first file includes warm-up), about 33-34 sentences and about 680 words per hourly bulletin (the same 2 files), and file sizes (1.70 and 2.00 MB). **Estimates: every Morning, Midday, Evening and News At Nine duration (assumed 15 min each, range 10-20, from an unverified screenshot figure; only the 30 / 66 non-hourly items depend on it), the download times (one observation: 2 downloads about 3 s apart, including the 1-3 s politeness delay), and the sentence totals.** The 2 timed files are both hourly night bulletins from 19 Oct, so the speeds may not hold for longer Morning/Midday bulletins.

**What really limits us (reasoning from the numbers above).**
- **Transcription is not the problem for A.** About 1-1.6 h on the laptop GPU, can run in the background (even overnight) while labelling. For B it is about 2.2-3.5 h on the laptop, still feasible, or faster on the A6000 (unmeasured).
- **Download:** about 10-30 min, UNMEASURED; it only becomes the bottleneck if the site throttles. Check it on the first 20 files before committing.
- **The hand-labelling time is the real limit and is the same for A and B,** because the gold targets are fixed (about 300-500 genre sentences with a 150-200 sentence second-annotator overlap, about 100 duplicate pairs, about 50 queries, 3-5 hand-corrected bulletins) and A's test days alone already hold roughly 47 bulletins, about 1,500 raw sentences, enough to draw them from. Labelling speed per item is UNMEASURED (time the first 50 sentences).
- **Other possibly slow, UNMEASURED step:** after transcription, embedding plus classification of the sentences (zero-shot BART on 7,000 or 15,000 sentences). This grows with the option and was not timed.
- **Most likely bottleneck, option A:** the human labelling (and, for the WER bulletins, hand-correcting transcripts). **Option B:** the same labelling, plus about 2-3 extra hours of laptop transcription and a larger classification/dedup run; the extra days do not reduce the labelling work.

**Recommendation (your decision): start with A.** It is enough for every pilot target, finishes ASR in about 1-1.6 h, and every day of A stays valid if you later extend to B (nested), so nothing is wasted. Extend to B on Tuesday only if the A pipeline runs cleanly and there is cluster time. What B buys is statistical power (4 test days instead of 2), not less work. What A costs: only 2 test days (28 Aug and 6 Sep), so results can reflect those two days' stories; state this in the paper.

**ASR WER bulletins (3-5, hand-corrected), all from A's test days so they are valid for both options:**

| Role | Date | File |
|---|---|---|
| Hourly, night | 2026-09-06 | `English-0105-0110-9.mp3` |
| Hourly, daytime | 2026-08-28 | `English-1505.mp3` |
| Hourly, evening | 2026-09-06 | `English-1905-1.mp3` |
| Morning News | 2026-09-06 | `morninng.mp3` (no time in filename) |
| Midday News | 2026-08-28 | `Midday-News.mp3` (no time in filename) |

Three of the five fall on one day (6 Sep). Morning and Midday bulletins are longer (unmeasured), so hand-correcting them is the most expensive part; drop the Midday one first if time runs out (3 hourly + 1 Morning is the minimum mix). Correction time per bulletin is UNMEASURED; time the first one.

**Whisper sizes to compare on the laptop (RTX 2050, 4 GB):** `tiny`, `base`, `small`, and `medium` only after a one-file test shows it fits in 4 GB (UNVERIFIED; `small` float16 used 881 MiB). Later, the A6000 cluster can add larger runs (`large-v3` etc.); its speed is unmeasured.

**Open items before downloading (status after S5):** (1) option A picked and downloaded (DONE); (2) `--sample` reads the explicit day lists (DONE); (3) duplicate-slot pair content checked inside A: all 9 pairs are different recordings (DONE, see S5 results); (4) the 3 WER picks without a parsed hour (Morning and Midday) are stored with an empty hour (still true).

---

## 8b. S6 - Annotation files (built 31 Oct 2026; NOTHING LABELLED YET)

All files are in `data/gold/` (see its `README.md`); script `data/gold/build_gold_sheets.py`. No downloads, no transcription, no labels, no model predictions in any sheet.

**Leakage rule.** Val and test days (2026-08-16, 10-24 / 08-28, 09-06) feed the gold set only; train days (6 days) feed silver training only. No gold sentence, pair or query candidate comes from a train day. Gold is never used for training, threshold tuning or model selection except on val; the test days are for the final numbers. **TODO:** when building silver training data from the train days, also drop any sentence whose normalised text appears in a gold sheet (16 of the 400 genre sentences and 7 of the 100 pair sentences have exactly the same text as some train-day sentence, i.e. repeated stories/boilerplate across days).

**Seeds and sizes (all `random.Random(42)`; the overlap order uses seed 43).**

| Sheet | File | Rows | Per day (08-16 / 08-28 / 09-06 / 10-24) |
|---|---|---|---|
| Genre, annotator 1 | `genre_sheet_annotator1.csv` | 400 | 100 / 100 / 100 / 100 (proportional to the pool of 977 / 976 / 976 / 974 sentences with at least 4 words, 3,903 in all, from 95 bulletins) |
| Genre overlap, annotator 2 | `genre_sheet_annotator2_overlap.csv` | 175 (subset of the 400, different random order) | 47 / 42 / 38 / 48 |
| Duplicate pairs | `duplicate_pairs_sheet.csv` (+ `duplicate_pairs_HIDDEN_KEY.csv`) | 100 | 25 / 25 / 25 / 25 |
| Queries | `query_sheet.csv` | 50 empty rows | TODO: user writes the queries |

- **Genre sampling:** random within each day, not stratified by any prediction; sentences from the project's own `segment_sentences`; sentences under 4 words are not offered. 13 sentences in the sheet share their exact text with another sentence in the sheet (repeated headlines across hourly bulletins); they were not removed.
- **Pair sampling:** `all-MiniLM-L6-v2` embeddings (the project's model); candidates = same day, two different bulletin files, both hours known, hour gap at most 2 (220,857 candidates); 16 pairs in each band 0.60-0.70, 0.70-0.80, 0.80-0.85, 0.85-0.90, 0.90-0.95, plus 20 random pairs below 0.40; each sentence used in at most one pair; pair order and a/b side shuffled. Pairs at 0.95 and above are NOT in the sheet, and bulletins without a parsed hour (Morning/Midday) are not paired. Duplicate-slot file pairs are not used.
- **TODO:** written definitions for the four pair labels (same / paraphrase / follow-up / different) do not exist in the code and must be agreed before labelling; the genre label definitions in the README are only the project's keyword hints. No annotation, no kappa, no queries, no relevance judgments exist yet.

---

## 8c. S7 - Store A built (31 Oct 2026)

`build_store_A.py --classifier fast --reindex` created `store_A/news_store.db`, `store_A/faiss_index.bin`, `store_A/dedup_report.json`, `store_A/build_report.json`, `store_A/build.log`. No file named `news_store.db`, `faiss_index.bin` or `output/` content was created or touched outside `store_A/` (none existed at the project root). Code used: A1/A2/A4 as fixed, project embedding model `all-MiniLM-L6-v2`, novelty gate **0.85 (unchanged)**, 0-23 hour field, a new `split` column (train/val/test from `data/sample_A/metadata.csv`) on every segment. Files processed in (date, hour, file) order; the gate runs across ALL splits, so it is order dependent.

| Measured | Value |
|---|---|
| Transcripts ingested | 239 (all) |
| Sentences before the gate | 9,519 (train 5,560 / val 1,981 / test 1,978) |
| Segments after the gate (in the store) | **4,264** (train 2,520 / val 879 / test 865); 5,255 rejected = 55.2% |
| Segments with NULL hour | **710** (train 479 / val 80 / test 151), all flagged `no_time_in_filename` (Morning/Midday/Evening/News At Nine files); 0 segments with an hour outside 0-23 |
| Time | 978 s (16.3 min) wall, one uninterrupted run, CPU |

**Choices and caveats (UNVERIFIED where marked).**
- **CPU, not GPU:** the project's classifier code hard-codes `device=-1` and `.venv_gpu` has a CPU-only torch (`2.14.0+cpu`); the GPU there serves Whisper (ctranslate2) only.
- **Genre backend `fast` (cross-encoder/nli-MiniLM2-L6-H768), not the default zero-shot BART:** measured on 24 sentences, BART was 1.65 s/sentence on this CPU (about 4.4 h upper bound for all 9,519 sentences) versus 0.18 s with `fast`. The genre column in the store is therefore a SILVER label from the fast backend (1,601 of 4,264 are 'Other'); it is not gold and its quality is UNVERIFIED. A BART rerun is TODO (`--classifier zero-shot --reindex`) if wanted.
- **Gold vs store:** gold sentences and query judgments are raw val/test sentences, but the store keeps only sentences that passed the gate; gold sentences dropped by the gate are not in the store (mapping by text is TODO in the retrieval eval). The gate also lets a val/test sentence be dropped because of an earlier (including train-day) sentence.
- Dedup report per file and top rejected pairs: `store_A/dedup_report.json`. The silver genre counts are in `build_report.json`.

---

## 9. Member B tasks (communication and admin)

These are for a human to do. Nothing here has been sent or done.

- [ ] **TODAY (Sat)** Email the cluster admins (varun.jhaveri23@spit.ac.in, rehan.ansari24@spit.ac.in) and get **written** answers to: remote access from home / VPN; internet access from compute nodes (newsonair.gov.in, pip, Hugging Face); ffmpeg available or a module; CUDA support for faster-whisper; queue wait times; confirmation that our research use (transcribing AIR audio, training, evals) is an approved task. Report answers to Member A **before Sunday night**.
- [ ] **TODAY (Sat)** Tell the professor the agreed Thursday scope ("pilot-scale evaluation now; full dataset and evaluation are the thesis") and confirm the paper's venue/format, page limit and what he expects to see. Record his reply here: `TODO: ______`.
- [ ] **By Sunday** Find the second annotator for the overlap subset (a classmate is fine) and brief them on the genre labels.
- [x] Home GPU recorded: NVIDIA GeForce RTX 2050, 4 GB VRAM (measured, section 5). No action needed.
- [ ] Book or confirm cluster access for Mon-Tue; ask about Wednesday.
- [ ] Track the writing: owns the paper skeleton and the section 7 checklist; verifies each number in the paper maps to a file in `results/`.
- [ ] **Mon/Tue** Monitor `sbatch` jobs (`squeue -l`) and report failures to Member A immediately.

---

## 10. Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Wednesday GPU access uncertain | No experiments after Tue night | Plan treats Tue night as the last GPU time; Wed is buffer only |
| Cluster may lack internet or ffmpeg | Cannot scrape/transcribe there | Scrape at home, copy audio and weights; smoke test on Sunday night |
| Annotation slips | Smaller gold set | Shrink the set and say so; never reduce rigor |
| Fine-tuned model does not beat zero-shot or baselines | No method claim | Report honestly; per the existing rule the contribution then becomes the dataset and evaluation |
| Site layout change or rate-limiting during the crawl | Incomplete metadata | Keep delays, crawl in weekly windows, resume via existing URLs |
| Cluster-terms compliance (2-year ban) | Lose access | Use GPUs only for the approved task; get written confirmation (Member B) |
| Gold set is pilot-scale | Overclaiming | Label it pilot everywhere |
| Archive facts in section 4 turn out wrong | Plan changes | S3/S3c/S3d confirmed the format, bounds and 3-month volume; still UNVERIFIED: total archive size (1,686-page screenshot), Daily Broadcast tab. Same-slot files were checked inside option A (S5): all 9 pairs differ in audio and text |

---

## 11. Working agreement

- One task per prompt; state what changed and run the test.
- Do not proceed while a test fails.
- Back up `news_store.db`, `faiss_index.bin` and `output/` before overwriting them.
- Every number in a slide or paper comes from a saved file in `results/`.
- **Never put placeholder or invented numbers anywhere.**
- Develop and test locally before moving anything to the cluster.

---

## 12. Thesis plan (after Thursday)

Kept from the original 16-week plan. Not required for the 5 Nov pilot.

### Contribution options
| Option | Venue type | Core claim | Extra work |
|--------|-----------|------------|------------|
| A. Dataset + system | Resource / demo track, Indian-language NLP workshop | "First open, annotated corpus of AIR bulletins with a streaming retrieval baseline" | Section 3 items 1-7, license, release |
| B. Method | Workshop or main track | "Streaming novelty filtering + two-tier retrieval improves speech-news RAG vs. standard RAG" | Items 3, 4, 7, 8, 9, 10 |
| C. Systems | Demo | "End-to-end live broadcast to chatbot" | Items 2, 8, 14 |

Recommendation: Option A with B as the technical section.

### Milestones
| Phase | Weeks | Goal | Done when |
|-------|-------|------|-----------|
| 0 | 1 | Fix blockers | FAISS filtered search fixed + test; hour field unified; contribution written in one sentence |
| 1 | 2-6 | Collect data | At least 3 months English plus 1 month Hindi scraped and transcribed; `metadata.csv` complete; storage and license notes |
| 2 | 4-8 | Annotate | 1,500+ sentences genre-labelled by 2 annotators (kappa >= 0.7); 500+ duplicate pairs; 200+ queries; reference transcripts for 100 bulletin minutes |
| 3 | 7-10 | Evaluation code | One script per metric writing JSON; one command regenerates every table |
| 4 | 9-12 | Baselines and ablations | All baselines run; mean +/- std over seeds |
| 5 | 11-13 | Scale | Latency / memory at 10k / 100k / 1M; flat vs HNSW |
| 6 | 12-14 | Improvements | Hybrid / reranker / window chunks only if baselines show gaps and the ablation proves they help |
| 7 | 14-16 | Write and release | Paper, related work, limitations; public repo with license, seeds, configs; dataset release |

### Thesis targets (adjust after the first baseline run; these are goals, not results)
- Genre: report macro-F1 on the gold test set; aim for fine-tuned > zero-shot with a statistical test.
- Retrieval: full system must beat vector-only and BM25 on nDCG@5; if not, the contribution is the dataset, not the method.
- Dedup: threshold chosen on validation data; report F1.
- ASR: WER per language and model size.
- Latency: p95 chat response measured at 100k segments (target to be set after the 10k measurement).

### Paper outline
1. Introduction - problem and contributions
2. Related work - spoken document retrieval, topic detection and tracking, news dedup, RAG over news, Indian-language ASR and news datasets
3. Dataset - collection, statistics, annotation protocol, agreement, license
4. System - architecture diagram (`AirInsight_Architecture.png`, regenerated by `draw_architecture.py`)
5. Experiments - ASR, dedup, genre, retrieval, answer quality, ablations, scale
6. Analysis and error cases
7. Limitations and ethics
8. Conclusion
