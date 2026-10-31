# Provenance of the LLM annotations (data/gold/llm/)

**These are LLM labels. They are NOT gold and must be human-reviewed before any use as evidence.** They live in separate files and were never written into `annotator_1_label`, `annotator_2_label` or the pair `label` column of any human sheet.

- **Annotator:** Claude Sonnet 5.5 (model id `claude-sonnet-5-5`), running as Claude Code.
- **Date:** 2026-10-31.
- **Files produced:** `genre_llm_overlap.csv` (175), `genre_llm_rest.csv` (225), `pairs_llm.csv` (100), `query_candidates_draft.csv` (80 drafts), `uncertain_items.csv` (items I was unsure about, with the competing label), this file.

## Files read
- `data/gold/genre_sheet_annotator2_overlap.csv` and `data/gold/genre_sheet_annotator1.csv`: the `id` and `sentence_text` columns (the label columns were empty; checked).
- `data/gold/duplicate_pairs_sheet.csv`: `id`, `sentence_a`, `sentence_b` (the `label` column was empty; checked).
- `data/gold/valtest_sentence_index.csv`: only the `text` and `date` columns, through keyword counts per day, to check that the topics of the draft queries exist on the dates I attached to them.
- The label names are the project's `GENRE_LABELS`; the genre label descriptions available were the keyword hints in `data/gold/README.md` (the code has no written definitions). The pair label definitions are the ones in the instructions below.
- NOT opened: `duplicate_pairs_HIDDEN_KEY.csv`, anything in `store_A/` or `store_A_nodedup/`, any `results/` file, any silver or model genre label, any similarity score, any human label (none exist yet).

## Instructions used (from the user, step S11)
> LLM-assisted annotation, clearly separated from human labels. Label using ONLY the sentence text and the label definitions in data/gold/README.md. You must not see or use any model prediction, silver label, similarity score, hidden key file, or any human labels.
> Genre: for every sentence in the overlap file (175 rows) write genre_llm_overlap.csv with columns id, llm_label; then the remaining sentences of genre_sheet_annotator1.csv (not in the overlap) into genre_llm_rest.csv. Use exactly the project's label set and one label per sentence; if a sentence fits no genre, use "Other" rather than guessing.
> Pairs: for duplicate_pairs_sheet.csv write pairs_llm.csv with id, llm_label (same / paraphrase / follow-up / different). Do not open duplicate_pairs_HIDDEN_KEY.csv.
> Queries: write query_candidates_draft.csv with 80 DRAFT queries spread across topics and dates in the val/test days (some with a date constraint, some without), clearly marked as drafts to select and edit. Do not fill the relevant-segments column.
> Pair label definitions: same = the same fact in nearly the same wording; paraphrase = the same fact in different wording; follow-up = the same story with new or updated information; different = a different fact.
> Do not produce any ASR reference text.

## Statement
No human labels and no model predictions (silver labels, classifier outputs, similarity scores, hidden-key values) were used to produce these labels. The labels are my own judgement of the sentence text, typed in by hand per row; the script that wrote the files only mapped row positions to ids and validated the label sets.

## Things you should know when judging how independent this is
- I am the same assistant that built the sheets (S6) and the store (S7). I therefore know the sampling design of the pair sheet (about 80 pairs from cosine bands 0.60 to 0.95 plus 20 random low-similarity pairs) but I did not see any per-pair score, and the pair order in the sheet is shuffled. I also saw aggregate silver genre counts for the store, never per-sentence silver labels.
- One pass, one annotator, no second look: there was no consistency review beyond the rules below.
- Rules I applied to keep the labelling consistent (they are my interpretation, not project definitions):
  - Boilerplate (sign-offs, "end of bulletin", newsreader names, headlines announcements, sentences with no usable context) is `Other`.
  - Accidents, collapses, fire and crime stories with no genre of their own are `Other`; a flood or cyclone as a weather event is `Environment`.
  - Foreign disasters described by death tolls, missing people, aid or Indian nationals (Nepal, Indonesia) are `International`; river levels and weather alerts are `Environment`.
  - Drug-enforcement items are `Defence & Security`; drug-awareness speeches to youth are `Society & Culture`.
  - Education, festivals, pilgrimages, national days are `Society & Culture`; infrastructure openings, exports, farmer IDs and prices are `Economy`.
  - Pairs: `follow-up` is read at the level of the story (the same event with an added or updated fact, including a different statement from the same speech); a different newsreader name or an unrelated sentence is `different`; sign-offs with only ASR spelling differences are `same`.
- `uncertain_items.csv` lists every item where a different label was a real option.
- Draft queries: topics were checked against the dates through keyword counts, but I did not check that each query has a good answer, and I did not mark any relevant segment.
