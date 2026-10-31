"""A6-A9: metric code checked on tiny SYNTHETIC inputs with hand-computed expected values.

Nothing here touches data/gold, store_A or output/. Fake gold files are written into pytest's temp folder.
"""
import csv
import json
import math
import os
import re
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "eval"))
sys.path.insert(0, ROOT)

import asr_eval  # noqa: E402
import dedup_eval  # noqa: E402
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402
import genre_eval  # noqa: E402
import retrieval_eval  # noqa: E402
import vector_store  # noqa: E402


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def load(path):
    return json.load(open(path, encoding="utf-8"))


# =============================================================== genre
Y_TRUE = ["A", "A", "A", "B", "B", "C"]
Y_PRED = ["A", "A", "B", "B", "A", "C"]
LABELS = ["A", "B", "C"]


def test_genre_hand_computed_macro_f1_and_per_class():
    m = genre_eval.genre_metrics(Y_TRUE, Y_PRED, LABELS, min_support=2, resamples=200)
    a, b = m["per_class"]["A"], m["per_class"]["B"]
    # A: tp 2, fp 1 (a B predicted A), fn 1 -> P = R = F1 = 2/3.  B: tp 1, fp 1, fn 1 -> P = R = F1 = 1/2
    assert (a["support"], a["precision"], a["recall"], a["f1"]) == (3, pytest.approx(2 / 3), pytest.approx(2 / 3), pytest.approx(2 / 3))
    assert (b["support"], b["precision"], b["recall"], b["f1"]) == (2, 0.5, 0.5, 0.5)
    assert m["per_class"]["C"]["status"] == genre_eval.INSUFFICIENT and "f1" not in m["per_class"]["C"]   # support 1 < 2
    assert m["macro_f1"] == pytest.approx((2 / 3 + 0.5) / 2)       # 7/12, over the two classes with support
    assert m["classes_scored"] == ["A", "B"] and m["classes_insufficient_support"] == ["C"]
    assert m["accuracy"] == pytest.approx(4 / 6)
    assert m["confusion_matrix"]["counts"] == [[2, 1, 0], [1, 1, 0], [0, 0, 1]]


def test_genre_macro_f1_with_all_classes_scored():
    m = genre_eval.genre_metrics(Y_TRUE, Y_PRED, LABELS, min_support=1, resamples=100)
    assert m["macro_f1"] == pytest.approx((2 / 3 + 0.5 + 1.0) / 3)   # 13/18


def test_genre_default_min_support_refuses_every_class_in_a_tiny_example():
    m = genre_eval.genre_metrics(Y_TRUE, Y_PRED, LABELS, resamples=50)   # default 5
    assert m["macro_f1"] == genre_eval.INSUFFICIENT
    assert all(v["status"] == genre_eval.INSUFFICIENT for v in m["per_class"].values())
    assert cfg.MIN_CLASS_SUPPORT == 5


def test_genre_bootstrap_states_seed_resamples_and_is_reproducible():
    a = genre_eval.genre_metrics(Y_TRUE, Y_PRED, LABELS, min_support=2, resamples=300, seed=7)
    b = genre_eval.genre_metrics(Y_TRUE, Y_PRED, LABELS, min_support=2, resamples=300, seed=7)
    assert a["bootstrap"]["seed"] == 7 and a["bootstrap"]["resamples"] == 300
    assert a["bootstrap"]["macro_f1_ci95"] == b["bootstrap"]["macro_f1_ci95"]
    lo, hi = a["bootstrap"]["macro_f1_ci95"]
    assert 0 <= lo <= hi <= 1
    perfect = genre_eval.genre_metrics(["A"] * 5 + ["B"] * 5, ["A"] * 5 + ["B"] * 5, ["A", "B"], resamples=100)
    assert perfect["macro_f1"] == 1.0 and perfect["bootstrap"]["macro_f1_ci95"] == [1.0, 1.0]


def test_cohen_kappa_known_answer():
    # 50 items: yes/yes 20, yes/no 5, no/yes 10, no/no 15 -> po 0.7, pe 0.5*0.6 + 0.5*0.4 = 0.5, kappa 0.4
    a = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert genre_eval.cohen_kappa(a, b) == pytest.approx(0.4)
    assert genre_eval.cohen_kappa(["x", "y", "x"], ["x", "y", "x"]) == pytest.approx(1.0)
    assert genre_eval.cohen_kappa(["x", "x"], ["x", "x"]) is None            # chance agreement 1: undefined
    assert genre_eval.cohen_kappa(["x", "y"], ["y", "x"]) == pytest.approx(-1.0)


def test_kappa_block_waits_for_annotator_2():
    a1 = {"1": "A", "2": "B", "3": "A", "4": "B"}
    rows = [{"id": "1", "annotator_2_label": "A"}, {"id": "2", "annotator_2_label": ""}]
    assert genre_eval.kappa_block(a1, rows, ["A", "B"])["status"].startswith("not computed")
    full = [{"id": k, "annotator_2_label": v} for k, v in {"1": "A", "2": "B", "3": "B", "4": "B"}.items()]
    kb = genre_eval.kappa_block(a1, full, ["A", "B"], resamples=100)
    # po 3/4; annotator 1: A2 B2, annotator 2: A1 B3 -> pe = (2*1 + 2*3)/16 = 0.5 -> kappa 0.5
    assert kb["kappa"] == pytest.approx(0.5) and kb["bootstrap"]["resamples"] == 100


def test_tfidf_logreg_baseline_separable_training_data():
    train = ["cricket match won today"] * 3 + ["budget tax rupee rise"] * 3
    labels = ["Sports"] * 3 + ["Economy"] * 3
    pred = genre_eval.tfidf_lr_predict(train, labels, ["cricket match", "tax rupee"])
    assert pred == ["Sports", "Economy"]


def _genre_fixture(tmp_path, with_annotator2=True):
    import sqlite3
    # gold: 10 Sports + 10 Economy sentences on a val day (2026-08-16) and a test day (2026-08-28)
    rows, ids = [], []
    for i in range(20):
        lab = "Sports" if i < 10 else "Economy"
        text = ("cricket match won again number %d" if lab == "Sports" else "budget tax rupee rise number %d") % i
        rows.append({"id": f"g{i}", "date": "2026-08-16" if i % 2 else "2026-08-28", "hour": "5", "source_file": "x.mp3",
                     "sentence_text": text, "annotator_1_label": lab})
    gold = tmp_path / "g.csv"
    write_csv(gold, rows, ["id", "date", "hour", "source_file", "sentence_text", "annotator_1_label"])
    a2 = tmp_path / "a2.csv"
    flip = {"g0": "Politics"}                                      # annotator 2 disagrees on one sentence
    write_csv(a2, [{"id": r["id"], "date": r["date"], "hour": "", "source_file": "", "sentence_text": r["sentence_text"],
                    "annotator_2_label": flip.get(r["id"], r["annotator_1_label"]) if with_annotator2 else ""} for r in rows[:10]],
              ["id", "date", "hour", "source_file", "sentence_text", "annotator_2_label"])
    db = str(tmp_path / "s.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE segments (id INTEGER PRIMARY KEY, text TEXT, genre TEXT, split TEXT)")
    for k in range(8):   # train silver: Sports x5 (majority), Economy x3, plus a test-split row that must be ignored
        con.execute("INSERT INTO segments (text, genre, split) VALUES (?,?,?)",
                    ("cricket match won today %d" % (k % 2), "Sports", "train") if k < 5 else ("budget tax rupee rise %d" % (k % 2), "Economy", "train"))
    con.execute("INSERT INTO segments (text, genre, split) VALUES ('ignore me', 'Health', 'test')")
    con.commit()
    con.close()
    return {"gold": str(gold), "annotator2": str(a2), "store_db": db, "sample_config": cfg.SAMPLE_CONFIG}


def test_genre_eval_end_to_end_on_synthetic_gold(tmp_path):
    paths = _genre_fixture(tmp_path)
    res_dir = str(tmp_path / "res")
    code, out = genre_eval.run(paths, res_dir, systems=("baselines",))
    assert code == 0 and os.path.isfile(out)
    d = load(out)
    assert d["seed"] == cfg.SEED and d["inputs"][0]["sha256"] and d["name"] == "genre_eval"
    r = d["results"]
    assert r["baseline_training_data"]["majority_class"] == "Sports" and r["baseline_training_data"]["n_segments"] == 8
    assert r["gold_sheet"]["support_by_class"] == {"Sports": 10, "Economy": 10}
    maj = r["systems"]["majority_class_train_silver"]["all_gold"]
    assert maj["per_class"]["Sports"]["recall"] == 1.0 and maj["per_class"]["Sports"]["precision"] == 0.5
    assert maj["per_class"]["Economy"]["f1"] == 0.0 and maj["macro_f1"] == pytest.approx((2 / 3 + 0) / 2)
    assert r["systems"]["tfidf_logreg_train_silver"]["all_gold"]["macro_f1"] == pytest.approx(1.0)
    # per split blocks exist; with 10 gold sentences per day-class nothing falls below the support limit here
    assert "val_days_only" in r["systems"]["majority_class_train_silver"]
    k = r["kappa_annotator1_vs_annotator2"]
    # 10 overlap rows, one disagreement (g0): po 0.9; a1: Sports 10; a2: Sports 9 + Politics 1 -> pe = 10*9/100 = 0.9 -> kappa 0
    assert k["n_overlap"] == 10 and k["kappa"] == pytest.approx(0.0)


def test_genre_eval_exit_3_when_gold_unlabelled_and_writes_nothing(tmp_path):
    paths = _genre_fixture(tmp_path)
    rows = common.read_csv(paths["gold"])
    rows[3]["annotator_1_label"] = ""
    write_csv(paths["gold"], rows, list(rows[0]))
    code, out = genre_eval.run(paths, str(tmp_path / "res"))
    assert code == 3 and out is None and not os.path.exists(tmp_path / "res")


def test_genre_eval_exit_2_when_store_missing(tmp_path):
    paths = _genre_fixture(tmp_path)
    paths["store_db"] = str(tmp_path / "nope.db")
    code, out = genre_eval.run(paths, str(tmp_path / "res"))
    assert code == 2 and out is None


def test_genre_eval_rejects_a_label_outside_the_project_label_set(tmp_path):
    paths = _genre_fixture(tmp_path)
    rows = common.read_csv(paths["gold"])
    rows[0]["annotator_1_label"] = "Gossip"
    write_csv(paths["gold"], rows, list(rows[0]))
    assert genre_eval.run(paths, str(tmp_path / "res"))[0] == 3


# =============================================================== dedup
def test_dedup_sweep_hand_computed():
    score, y = [0.9, 0.8, 0.7, 0.6], [True, True, False, False]
    rows = {r["threshold"]: r for r in dedup_eval.sweep(score, y, [0.55, 0.65, 0.75, 0.85, 0.95], resamples=50)}
    r75 = rows[0.75]
    assert (r75["tp"], r75["fp"], r75["fn"], r75["tn"]) == (2, 0, 0, 2) and r75["precision"] == r75["recall"] == r75["f1"] == 1.0
    r65 = rows[0.65]                  # predicted positive: 0.9, 0.8, 0.7 -> tp 2 fp 1
    assert r65["precision"] == pytest.approx(2 / 3) and r65["recall"] == 1.0 and r65["f1"] == pytest.approx(0.8)
    r85 = rows[0.85]                  # only 0.9 predicted: tp 1, fn 1
    assert r85["precision"] == 1.0 and r85["recall"] == 0.5 and r85["f1"] == pytest.approx(2 / 3)
    r95 = rows[0.95]                  # nothing predicted: precision undefined, F1 0
    assert r95["precision"] is None and r95["recall"] == 0.0 and r95["f1"] == 0.0
    assert rows[0.55]["precision"] == 0.5 and rows[0.55]["recall"] == 1.0
    assert all(len(r["f1_ci95"]) == 2 for r in rows.values() if r["f1_ci95"])


def test_dedup_select_threshold_ties_go_to_higher_threshold():
    rows = dedup_eval.sweep([0.9, 0.8, 0.7, 0.6], [True, True, False, False], [0.55, 0.65, 0.75, 0.85], resamples=20)
    assert dedup_eval.select_threshold(rows) == 0.75
    rows = dedup_eval.sweep([0.9, 0.8, 0.7, 0.6], [True, True, False, False], [0.75, 0.80, 0.85], resamples=20)
    assert dedup_eval.select_threshold(rows) == 0.80        # 0.75 and 0.80 both F1 1.0 -> higher; 0.85 has F1 2/3
    none = dedup_eval.sweep([0.9, 0.8], [False, False], [0.5, 0.6], resamples=20)
    assert dedup_eval.select_threshold(none) is None


def test_dedup_text_baselines():
    assert dedup_eval.normalise("The CAT, sat!") == dedup_eval.normalise("the cat sat")
    assert dedup_eval.jaccard5("a b c d e f", "a b c d e f") == 1.0
    assert dedup_eval.jaccard5("a b c d e f", "x y z w v u") == 0.0
    assert dedup_eval.jaccard5("a b c d e f", "a b c d e g") == pytest.approx(1 / 3)   # grams {abcde,bcdef} vs {abcde,bcdeg}
    c = dedup_eval.tfidf_cosines(["india wins match"], ["india wins match"], ["india wins match", "budget tax"])
    assert c[0] == pytest.approx(1.0)


def _pair_fixture(tmp_path):
    spec = [  # id, label, cosine, split, text a, text b
        ("P1", "same", 0.95, "val", "alpha beta gamma delta epsilon zeta", "alpha beta gamma delta epsilon zeta"),
        ("P2", "paraphrase", 0.88, "val", "one two three four five six", "one two three four five seven"),
        ("P3", "follow-up", 0.65, "val", "red green blue yellow orange pink", "cold warm hot mild cool dry"),
        ("P4", "different", 0.62, "val", "lion tiger bear wolf fox deer", "oak pine elm ash fir yew"),
        ("P5", "same", 0.95, "test", "mars venus earth saturn jupiter pluto", "mars venus earth saturn jupiter pluto"),
        ("P6", "paraphrase", 0.86, "test", "tea coffee milk water juice soda", "tea coffee milk water juice cola"),
        ("P7", "different", 0.90, "test", "rome paris london berlin madrid vienna", "tokyo seoul delhi cairo lima oslo"),
        ("P8", "follow-up", 0.50, "test", "ant bee fly moth wasp gnat", "cup mug jar pot pan lid"),
    ]
    write_csv(tmp_path / "sheet.csv", [{"id": s[0], "sentence_a": s[4], "sentence_b": s[5], "label": s[1]} for s in spec],
              ["id", "sentence_a", "sentence_b", "label"])
    write_csv(tmp_path / "key.csv", [{"id": s[0], "cosine_all_MiniLM_L6_v2": s[2], "split": s[3], "date": "d"} for s in spec],
              ["id", "cosine_all_MiniLM_L6_v2", "split", "date"])
    return {"gold": str(tmp_path / "sheet.csv"), "key": str(tmp_path / "key.csv"), "sentence_index": ""}


def test_dedup_eval_end_to_end_selects_on_val_and_reports_on_test(tmp_path):
    paths = _pair_fixture(tmp_path)
    code, out = dedup_eval.run(paths, str(tmp_path / "res"))
    assert code == 0
    d = load(out)["results"]
    prim = d["definitions"]["primary_same_plus_paraphrase_positive"]
    alt = d["definitions"]["alternative_only_same_positive"]
    assert d["definitions"]["primary_same_plus_paraphrase_positive"] and prim["positives"] == 4 and alt["positives"] == 2
    cos = prim["methods"]["project_cosine_minilm"]
    # val pairs: positives 0.95 / 0.88, negatives 0.65 / 0.62 -> F1 = 1 for every threshold 0.66..0.88; ties -> 0.88
    assert cos["selected_threshold_on_val"] == 0.88
    t = cos["test_at_selected_threshold"]          # test: 0.95 (tp), 0.86 (fn), 0.90 (fp), 0.50 (tn)
    assert (t["tp"], t["fp"], t["fn"], t["tn"]) == (1, 1, 1, 1) and t["f1"] == 0.5
    # alternative definition (only 'same'): val positives 0.95 only -> best F1 for t in (0.88 .. 0.95]; ties -> 0.95
    assert alt["methods"]["project_cosine_minilm"]["selected_threshold_on_val"] == 0.95
    # parameter-free baselines
    assert prim["methods"]["exact_string_match"]["test_pairs"]["tp"] == 1      # P5 identical text
    assert prim["methods"]["normalised_text_match"]["val_pairs"]["fn"] == 1    # P2 differs in one word
    ref = cos["test_at_project_default_0.85_reference_only"]
    assert ref["threshold"] == 0.85 and (ref["tp"], ref["fp"], ref["fn"]) == (2, 1, 0)
    assert d["choice_recorded"].startswith("primary = same + paraphrase")
    assert d["bootstrap"]["resamples"] == cfg.BOOTSTRAP_RESAMPLES and d["bootstrap"]["seed"] == cfg.SEED
    assert [r["threshold"] for r in cos["sweep_val"]][0] == 0.6 and [r["threshold"] for r in cos["sweep_val"]][-1] == 0.95
    assert len(cos["sweep_val"]) == 36


def test_dedup_eval_exit_3_when_pairs_unlabelled(tmp_path):
    paths = _pair_fixture(tmp_path)
    rows = common.read_csv(paths["gold"])
    rows[0]["label"] = ""
    write_csv(paths["gold"], rows, list(rows[0]))
    assert dedup_eval.run(paths, str(tmp_path / "res")) == (3, None)


# =============================================================== retrieval
def test_retrieval_metrics_hand_computed():
    ranked, rel = [5, 3, 9, 1], [3, 1]
    assert retrieval_eval.recall_at_k(ranked, rel, 1) == 0.0
    assert retrieval_eval.recall_at_k(ranked, rel, 3) == 0.5
    assert retrieval_eval.recall_at_k(ranked, rel, 10) == 1.0
    assert retrieval_eval.reciprocal_rank(ranked, rel) == 0.5
    dcg = 1 / math.log2(3) + 1 / math.log2(5)           # relevant at ranks 2 and 4
    idcg = 1 / math.log2(2) + 1 / math.log2(3)
    assert retrieval_eval.ndcg_at_k(ranked, rel, 5) == pytest.approx(dcg / idcg)
    assert retrieval_eval.ndcg_at_k([1, 3], [1, 3], 5) == pytest.approx(1.0)
    assert retrieval_eval.reciprocal_rank([7, 8], [1]) == 0.0
    m = retrieval_eval.query_metrics([1, 2, 3], [1])
    assert m["recall@1"] == 1.0 and m["mrr"] == 1.0 and set(m) == {"recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@5"}


def test_retrieval_summary_mean_and_bootstrap():
    s = retrieval_eval.summarise({"q1": {"mrr": 1.0}, "q2": {"mrr": 0.5}}, resamples=200)
    assert s["n_queries"] == 2 and s["mrr"]["mean"] == 0.75
    lo, hi = s["mrr"]["ci95"]
    assert 0.5 <= lo <= 0.75 <= hi <= 1.0 and s["bootstrap"]["resamples"] == 200


def test_bm25_hand_ranking():
    bm = retrieval_eval.BM25([10, 11, 12], ["cricket match won", "budget tax rupee", "cricket world cup final cricket"])
    # idf(cricket) = ln((3-2+.5)/(2+.5)+1); d12 (tf 2, length 5) outscores d10 (tf 1, length 3); d11 has no query term
    assert bm.rank("cricket", 10) == [12, 10]
    assert bm.rank("quantum", 10) == []
    assert bm.rank("tax", 1) == [11]


def fake_embed(texts):
    """Deterministic 384-d bag-of-words vectors (stand-in for MiniLM in tests)."""
    out = np.zeros((len(texts), vector_store.EMBEDDING_DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        for w in re.findall(r"[a-z0-9]+", t.lower()):
            out[i, (sum(map(ord, w)) * 31 + len(w)) % vector_store.EMBEDDING_DIM] += 1.0
    return out


B1S1 = "Cricket team won the final match."
B1S2 = "The budget raised income tax slabs."
B2S1 = "The cricket team won the final match yesterday."     # rejected by the gate in favour of B1S1 (cosine about 0.90)
B2S2 = "Heavy rain floods the city."
B2S3 = "Quantum chips arrive soon."                          # not in the store and not similar to anything: unmappable


def _retrieval_fixture(tmp_path, queries):
    sample = tmp_path / "sample"
    stems = {"b1": "English-0105-0110-1", "b2": "English-0205-0210-1"}
    for key, text in (("b1", f"{B1S1} {B1S2}"), ("b2", f"{B2S1} {B2S2} {B2S3}")):
        d = sample / "text" / "2026-08-16"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{stems[key]}.txt").write_text(text, encoding="utf-8")
    ip, dp = str(tmp_path / "i.bin"), str(tmp_path / "s.db")

    def seg(text, genre):
        return {"text": text, "genre": genre, "genre_confidence": 0.5, "embedding": fake_embed([text])[0]}
    vector_store.resolve_audio_path = lambda *a, **k: ("", False)
    vector_store.add_segments([seg(B1S1, "Sports"), seg(B1S2, "Economy")], "2026-08-16", 1, f"text/2026-08-16/{stems['b1']}.txt", ip, dp, split="val")
    vector_store.add_segments([seg(B2S2, "Environment")], "2026-08-16", 2, f"text/2026-08-16/{stems['b2']}.txt", ip, dp, split="val")
    # a train-day segment that is identical to B1S1 in content must never be returned (pool = val/test only)
    vector_store.add_segments([seg("Cricket team won the final match easily.", "Sports")], "2026-08-10", 1, "text/2026-08-10/x-0105-1.txt", ip, dp, split="train")
    idx = [{"id": f"2026-08-16_{stems['b1']}_s001", "date": "2026-08-16", "hour": "1", "source_file": stems["b1"] + ".mp3", "position": "1", "split": "val", "text": B1S1},
           {"id": f"2026-08-16_{stems['b2']}_s001", "date": "2026-08-16", "hour": "2", "source_file": stems["b2"] + ".mp3", "position": "1", "split": "val", "text": B2S1},
           {"id": f"2026-08-16_{stems['b2']}_s002", "date": "2026-08-16", "hour": "2", "source_file": stems["b2"] + ".mp3", "position": "2", "split": "val", "text": B2S2},
           {"id": f"2026-08-16_{stems['b2']}_s003", "date": "2026-08-16", "hour": "2", "source_file": stems["b2"] + ".mp3", "position": "3", "split": "val", "text": B2S3}]
    write_csv(tmp_path / "idx.csv", idx, ["id", "date", "hour", "source_file", "position", "split", "text"])
    write_csv(tmp_path / "q.csv", queries, ["id", "query_text", "date_constraint", "relevant_segment_ids"])
    return {"gold": str(tmp_path / "q.csv"), "sentence_index": str(tmp_path / "idx.csv"), "store_db": dp, "store_index": ip,
            "sample_dir": str(sample), "sample_config": cfg.SAMPLE_CONFIG, "build_report": str(tmp_path / "none.json")}, idx


def test_retrieval_mapping_exact_gate_and_unmapped(tmp_path):
    q = [{"id": "Q1", "query_text": "cricket final match", "date_constraint": "", "relevant_segment_ids": "x"}]
    paths, idx = _retrieval_fixture(tmp_path, q)
    rows, emb = retrieval_eval.load_store(paths)
    sent_index = {r["id"]: r for r in idx}
    m = retrieval_eval.map_relevant(list(sent_index), sent_index, rows, emb, paths["sample_dir"], fake_embed, 0.85)
    s1, s2, s3, s4 = (m[r["id"]] for r in idx)
    assert s1["status"] == "exact" and s1["faiss_id"] == 0                      # B1S1 is a kept segment
    assert s2["status"] == "gate" and s2["faiss_id"] == 0 and s2["cosine"] >= 0.85   # B2S1 was rejected because of B1S1
    assert s3["status"] == "exact" and s3["faiss_id"] == 2
    assert s4["status"] == "unmapped" and "below the gate threshold" in s4["reason"]


def test_retrieval_eval_end_to_end_on_synthetic_store(tmp_path):
    ids = ["2026-08-16_English-0105-0110-1_s001", "2026-08-16_English-0205-0210-1_s001"]
    queries = [
        {"id": "Q1", "query_text": "cricket final match", "date_constraint": "", "relevant_segment_ids": ";".join(ids)},
        {"id": "Q2", "query_text": "heavy rain city", "date_constraint": "2026-08-16", "relevant_segment_ids": "2026-08-16_English-0205-0210-1_s002"},
        {"id": "Q3", "query_text": "cricket", "date_constraint": "2026-08-10", "relevant_segment_ids": ids[0]},        # train day -> skipped
        {"id": "Q4", "query_text": "quantum", "date_constraint": "", "relevant_segment_ids": "2026-08-16_English-0205-0210-1_s003"},  # unmappable -> skipped
        {"id": "Q5", "query_text": "", "date_constraint": "", "relevant_segment_ids": ""},                              # empty row, ignored
    ]
    paths, _ = _retrieval_fixture(tmp_path, queries)
    code, out = retrieval_eval.run(paths, str(tmp_path / "res"), embed_fn=fake_embed)
    assert code == 0
    r = load(out)["results"]
    mp = r["mapping_of_gold_relevant_sentences"]
    assert (mp["exact_text_match"], mp["mapped_via_gate_rejection"], mp["unmapped"]) == (2, 1, 1)
    assert r["queries"]["written"] == 4 and r["queries"]["evaluated"] == 2
    assert {s["id"] for s in r["queries"]["skipped"]} == {"Q3", "Q4"}
    q1 = r["per_query"]["Q1"]
    assert q1["n_relevant_ids_given"] == 2 and q1["n_relevant_store_segments"] == 1       # two raw sentences -> one store segment
    for system in retrieval_eval.SYSTEMS:
        met = q1["systems"][system]["metrics"]
        assert met["recall@1"] == 1.0 and met["mrr"] == 1.0, system                      # the cricket segment ranks first everywhere
        assert 3 not in q1["systems"][system]["top5_faiss_ids"]      # the train-day segment (faiss id 3) never appears
    assert r["per_system"]["bm25"]["n_queries"] == 2 and r["per_system"]["full_system"]["mrr"]["mean"] == 1.0
    assert r["per_system"]["bm25"]["bootstrap"]["resamples"] == cfg.BOOTSTRAP_RESAMPLES


def test_retrieval_eval_exit_3_without_queries(tmp_path):
    paths, _ = _retrieval_fixture(tmp_path, [{"id": "Q1", "query_text": "", "date_constraint": "", "relevant_segment_ids": ""}])
    assert retrieval_eval.run(paths, str(tmp_path / "res"), embed_fn=fake_embed) == (3, None)


def test_retrieval_date_constraint_parsing():
    assert retrieval_eval.parse_date_constraint("") == (None, None)
    assert retrieval_eval.parse_date_constraint("2026-08-16") == ("2026-08-16", "2026-08-16")
    assert retrieval_eval.parse_date_constraint("2026-08-16:2026-08-28") == ("2026-08-16", "2026-08-28")


# =============================================================== asr
def test_asr_normalisation_documented_rules():
    assert asr_eval.normalise("India's GDP grew 3.5% — it's 1,000-odd") == ["indias", "gdp", "grew", "3.5", "its", "1000", "odd"]
    assert asr_eval.normalise("Three vs 3") == ["three", "vs", "3"]          # numbers are NOT converted
    assert asr_eval.normalise("state-of-the-art, e.g.") == ["state", "of", "the", "art", "e", "g"]


def test_asr_wer_hand_computed():
    w = asr_eval.align_counts("the cat sat on the mat".split(), "the cat sit on mat".split())
    assert (w["substitutions"], w["deletions"], w["insertions"], w["correct"]) == (1, 1, 0, 4)
    assert w["wer"] == pytest.approx(2 / 6)
    w2 = asr_eval.align_counts(["a", "b", "c"], ["a", "x", "b", "c", "y"])
    assert (w2["substitutions"], w2["deletions"], w2["insertions"]) == (0, 0, 2) and w2["wer"] == pytest.approx(2 / 3)
    assert asr_eval.align_counts(["a", "b"], [])["wer"] == 1.0
    assert asr_eval.align_counts(["a", "b"], ["a", "b"])["wer"] == 0.0
    p = asr_eval.pool([w, w2])                                              # N 9, S 1, D 1, I 2 -> 4/9
    assert (p["ref_words"], p["substitutions"], p["deletions"], p["insertions"]) == (9, 1, 1, 2) and p["wer"] == pytest.approx(4 / 9)


def test_asr_wer_matches_jiwer_when_installed():
    jiwer = pytest.importorskip("jiwer")
    ref, hyp = "the cat sat on the mat today", "a cat sit on mat today again"
    assert asr_eval.align_counts(ref.split(), hyp.split())["wer"] == pytest.approx(jiwer.wer(ref, hyp))


def _asr_fixture(tmp_path, skip_one=False):
    refs = tmp_path / "refs"
    refs.mkdir()
    stems = [c["stem"] for c in asr_eval.wer_candidates(cfg.SAMPLE_CONFIG)]
    for s in stems[:-1] if skip_one else stems:
        (refs / f"{s}.txt").write_text("The cat sat on the mat.", encoding="utf-8")
    return {"refs_dir": str(refs), "hyp_dir": str(tmp_path / "hyp"), "sample_text_dir": "", "sample_dir": "",
            "sample_config": cfg.SAMPLE_CONFIG}, stems


def test_asr_eval_end_to_end_with_fake_hypotheses(tmp_path):
    paths, stems = _asr_fixture(tmp_path)
    hyps = {"small": "the cat sat on the mat", "base": "The cat sit on mat!", "tiny": ""}
    code, out = asr_eval.run(paths, str(tmp_path / "res"), hyp_loader=lambda p, model, c: hyps[model])
    assert code == 0
    r = load(out)["results"]
    assert "NOT converted" in r["normalisation"]
    assert r["models"]["small"]["overall"]["wer"] == 0.0
    base = r["models"]["base"]
    assert base["overall"]["wer"] == pytest.approx(2 / 6) and base["overall"]["ref_words"] == 30
    assert (base["overall"]["substitutions"], base["overall"]["deletions"], base["overall"]["insertions"]) == (5, 5, 0)
    assert base["per_file"][stems[0]]["wer"] == pytest.approx(2 / 6)
    assert r["models"]["tiny"]["overall"]["wer"] == 1.0 and r["models"]["tiny"]["overall"]["deletions"] == 30
    assert set(r["models"]) == {"tiny", "base", "small"}


def test_asr_eval_exit_3_when_a_reference_is_missing(tmp_path):
    paths, _ = _asr_fixture(tmp_path, skip_one=True)
    assert asr_eval.run(paths, str(tmp_path / "res"), hyp_loader=lambda *a: "x") == (3, None)
    assert not os.path.exists(tmp_path / "res")
    assert "asr_refs" in cfg.GOLD_ASR_DIR.replace("\\", "/")


def test_real_gold_files_are_untouched_and_still_unlabelled():
    """Safety net: the synthetic tests above never write into data/gold, and the real sheets are still empty."""
    for name in ("genre_eval", "dedup_eval", "retrieval_eval", "asr_eval"):
        mod = sys.modules[name]
        assert mod.gold_status().ok is False, name
    assert not os.path.isdir(cfg.GOLD_ASR_DIR)
