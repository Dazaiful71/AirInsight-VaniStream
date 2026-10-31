# Gold annotation files (val/test days only)

All sentences come from the VALIDATION and TEST days of option A (2026-08-16, 2026-10-24 val; 2026-08-28, 2026-09-06 test). No train-day sentence is in any file here. The sheets contain no model prediction and no silver label.

## Genre labels (exactly `GENRE_LABELS` in `nlp_pipeline.py`)

The code defines the label NAMES only; it has no written definitions. The keywords below are the hints the project's own keyword map (`GENRE_KEYWORD_MAP` in `rag_engine.py`) uses for each label. They are examples from the code, not a complete definition, and not a rule you must follow.

| Label | Keywords in the code's map |
|---|---|
| Politics | parliament, election, minister, modi, bjp, congress, political, politics, vote, lok sabha, rajya sabha, bill |
| Economy | economy, gdp, inflation, rbi, rupee, stock, market, budget, trade, fiscal, tax, economic |
| Science & Technology | science, technology, isro, space, artificial intelligence, digital, research, satellite |
| Sports | cricket, football, hockey, tennis, olympics, sports, sport, match, tournament, athlete |
| International | china, pakistan, america, russia, united nations, united states, international, global, foreign, diplomat |
| Defence & Security | army, navy, military, defence, defense, security, terror, border |
| Health | health, covid, hospital, disease, vaccine, medical, doctor, pandemic |
| Environment | environment, climate, pollution, forest, wildlife, green, flood, drought, cyclone, weather |
| Society & Culture | culture, festival, education, society, women, caste, religion |
| Other | (none in the map) |

## Instructions (genre sheets)

1. Write exactly one label from the table above into the label column, spelled exactly as shown. Judge the sentence on its own, by what it is about.
2. Sentences come from automatic speech recognition and may contain errors; label what the sentence was evidently meant to say. Use `Other` if no label fits.
3. Work alone. Annotator 2 must not see annotator 1's labels (and vice versa) until both sheets are finished. If you are unsure, still pick one label and note the id elsewhere; do not leave blanks.

## Files

| File | Content |
|---|---|
| `genre_sheet_annotator1.csv` | 400 sentences, columns id, date, hour, source_file, sentence_text, annotator_1_label (empty) |
| `genre_sheet_annotator2_overlap.csv` | 175 of those sentences, different random order, annotator_2_label (empty) |
| `duplicate_pairs_sheet.csv` | 100 sentence pairs; label = same / paraphrase / follow-up / different (empty). Definitions of these four labels are NOT in the project code and are still TODO: agree on them before labelling |
| `duplicate_pairs_HIDDEN_KEY.csv` | cosine similarity and ids per pair. **Do not open while labelling.** |
| `query_sheet.csv` | 50 empty rows for queries (id, query_text, date_constraint, relevant_segment_ids) |
| `query_candidates.py` | shows candidate sentences for one query; see its docstring |
| `valtest_sentence_index.csv`, `valtest_embeddings.npy` | every val/test sentence with its segment id and embedding (used by the pair sheet and query tool) |
| `build_gold_sheets.py` | script that produced everything above (seed 42) |
