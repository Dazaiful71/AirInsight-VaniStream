"""S9: jiwer cross-check, classifier scoring + multi-seed fine-tune path, MinHash, retrieval ablations, ASR caching,
cluster scripts. Synthetic data only, in pytest temp folders; nothing here is a result."""
import json
import os
import random
import shutil
import subprocess
import sys
import types

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "eval"))
sys.path.insert(0, ROOT)

import asr_eval  # noqa: E402
import dedup_eval  # noqa: E402
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402
import finetune_genre as ft  # noqa: E402
import genre_eval  # noqa: E402
import retrieval_eval  # noqa: E402
import scale_benchmark  # noqa: E402
from test_eval_metrics import _genre_fixture, _retrieval_fixture, fake_embed, load  # noqa: E402


# =============================================================== 1. WER vs jiwer
def test_wer_matches_jiwer_on_random_synthetic_cases():
    jiwer = pytest.importorskip("jiwer")
    rnd = random.Random(1)
    vocab = "a b c d e f g h".split()
    checked = 0
    for _ in range(300):
        ref = " ".join(rnd.choice(vocab) for _ in range(rnd.randint(1, 12)))
        hyp = " ".join(rnd.choice(vocab) for _ in range(rnd.randint(1, 12)))
        ours = asr_eval.align_counts(ref.split(), hyp.split())
        out = jiwer.process_words(ref, hyp)
        assert ours["wer"] == pytest.approx(jiwer.wer(ref, hyp)), (ref, hyp)
        # total errors agree; the split between S, D and I may differ when several optimal alignments exist
        assert ours["substitutions"] + ours["deletions"] + ours["insertions"] == out.substitutions + out.deletions + out.insertions
        checked += 1
    assert checked == 300


def test_wer_tie_case_documents_the_sdi_difference_from_jiwer():
    jiwer = pytest.importorskip("jiwer")
    ref, hyp = "f e f", "f b e"                     # two optimal alignments: 2 substitutions, or 1 deletion + 1 insertion
    ours, out = asr_eval.align_counts(ref.split(), hyp.split()), jiwer.process_words(ref, hyp)
    assert ours["wer"] == pytest.approx(jiwer.wer(ref, hyp)) == pytest.approx(2 / 3)
    assert (ours["substitutions"], ours["deletions"], ours["insertions"]) == (2, 0, 0)
    assert (out.substitutions, out.deletions, out.insertions) == (0, 1, 1)


# =============================================================== 2. genre: classifiers, leakage, multi-seed
def _result(m, **k):
    return {"macro_f1": m, "accuracy": k.get("acc", 0.5), "classes_scored": k.get("classes", ["A", "B"]),
            "per_class": {c: {"f1": k.get("f1", m)} for c in k.get("classes", ["A", "B"])}}


def test_aggregate_seeds_mean_and_std_hand_computed():
    agg = genre_eval.aggregate_seeds({1: _result(0.5), 2: _result(0.7), 3: _result(0.9)})
    assert agg["macro_f1"]["mean"] == pytest.approx(0.7)
    assert agg["macro_f1"]["std"] == pytest.approx(0.2)           # sample std: sqrt((0.04 + 0 + 0.04) / 2)
    assert agg["n_seeds"] == 3 and agg["per_class_f1"]["A"]["mean"] == pytest.approx(0.7)
    one = genre_eval.aggregate_seeds({1: _result(0.5)})
    assert one["macro_f1"]["std"] is None                          # one seed: no standard deviation
    mixed = genre_eval.aggregate_seeds({1: _result(0.5), 2: _result(genre_eval.INSUFFICIENT, classes=[])})
    assert mixed["macro_f1"] == genre_eval.INSUFFICIENT


def test_leakage_filter_removes_identical_text_ignoring_case_and_punctuation():
    texts = ["Cricket match won today!", "budget raised tax", "Heavy rain in Delhi."]
    labels = ["Sports", "Economy", "Environment"]
    t, l, removed = ft.leakage_filter(texts, labels, ["cricket match WON today", "unrelated gold sentence"])
    assert removed == 1 and t == texts[1:] and l == labels[1:]


class FakeKeywordModel:
    """Tiny stand-in for a fine-tuned model: the trainer stores the majority label per first word."""
    @staticmethod
    def trainer(csv_path, out_dir, seed, epochs=5, batch_size=16):
        rows = common.read_csv(csv_path)
        votes = {}
        for r in rows:
            votes.setdefault(r["text"].split()[0].lower(), []).append(r["true_genre"])
        model = {w: max(set(v), key=v.count) for w, v in votes.items()}
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "model.json"), "w") as f:
            json.dump({"seed": seed, "model": model, "n_train": len(rows)}, f)
        FakeKeywordModel.calls.append((seed, [r["text"] for r in rows]))
        return 0

    calls = []

    @staticmethod
    def predictor(out_dir, texts):
        m = json.load(open(os.path.join(out_dir, "model.json")))
        flip_first = m["seed"] - 42            # seed 42 perfect, seed 43 flips one prediction, ...
        preds = [m["model"].get(t.split()[0].lower(), "Other") for t in texts]
        for i in range(min(flip_first, len(preds))):
            preds[i] = "Other"
        return preds


def _fake_classifiers():
    gold_labels = {}

    def make(fn):
        return fn
    return {
        "project_fast_nli_minilm": {"key": "fast", "category": genre_eval.CAT_ZERO_SHOT, "model": "fake-fast",
                                    "predict": lambda texts: ["Sports" if "cricket" in t else "Economy" for t in texts]},
        "project_zero_shot_bart": {"key": "zero-shot", "category": genre_eval.CAT_ZERO_SHOT, "model": "fake-bart",
                                   "predict": lambda texts: (_ for _ in ()).throw(RuntimeError("model download failed"))},
    }


def _fixture_with_leaking_train_sentence(tmp_path):
    import sqlite3
    paths = _genre_fixture(tmp_path)
    con = sqlite3.connect(paths["store_db"])
    # a train-day sentence whose text equals gold sentence g3 ("cricket match won again number 3"): must be filtered out of training
    con.execute("INSERT INTO segments (text, genre, split) VALUES ('Cricket match won again number 3!', 'Sports', 'train')")
    con.commit()
    con.close()
    return paths


def test_genre_eval_scores_project_classifiers_and_marks_categories(tmp_path):
    paths = _genre_fixture(tmp_path)
    code, out = genre_eval.run(paths, str(tmp_path / "res"), systems=("baselines", "fast", "zero-shot"),
                               classifiers=_fake_classifiers())
    assert code == 0
    s = load(out)["results"]["systems"]
    fast = s["project_fast_nli_minilm"]
    assert fast["category"] == genre_eval.CAT_ZERO_SHOT and "zero-shot" in fast["category"]
    assert fast["all_gold"]["macro_f1"] == pytest.approx(1.0) and fast["all_gold"]["bootstrap"]["seed"] == cfg.SEED
    assert fast["all_gold"]["confusion_matrix"]["counts"] is not None and "per_class" in fast["all_gold"]
    bart = s["project_zero_shot_bart"]
    assert bart["status"].startswith("not run: RuntimeError") and "all_gold" not in bart      # failure is recorded, not hidden
    assert "trained-on-silver" in s["tfidf_logreg_train_silver"]["category"]
    assert "finetuned_on_silver_multi_seed" not in s                                           # not requested


def test_finetuned_without_checkpoints_is_not_run_and_never_trains(tmp_path):
    FakeKeywordModel.calls.clear()
    paths = _genre_fixture(tmp_path)
    ftc = {"dir": str(tmp_path / "ft"), "trainer": FakeKeywordModel.trainer, "predictor": FakeKeywordModel.predictor,
           "project_checkpoint": str(tmp_path / "no_ckpt")}
    code, out = genre_eval.run(paths, str(tmp_path / "res"), systems=("finetuned",), classifiers={}, finetune=ftc)
    assert code == 0 and FakeKeywordModel.calls == []
    blk = load(out)["results"]["systems"]
    assert blk["finetuned_on_silver_multi_seed"]["status"].startswith("not run: no finished checkpoint")
    assert blk["project_checkpoint_air_genre_classifier"]["status"].startswith("not run: no checkpoint")


def test_finetuned_multi_seed_with_fake_model_leakage_and_mean_std(tmp_path):
    FakeKeywordModel.calls.clear()
    paths = _fixture_with_leaking_train_sentence(tmp_path)
    ftc = {"dir": str(tmp_path / "ft"), "trainer": FakeKeywordModel.trainer, "predictor": FakeKeywordModel.predictor,
           "train": True, "project_checkpoint": str(tmp_path / "no_ckpt")}
    code, out = genre_eval.run(paths, str(tmp_path / "res"), systems=("finetuned",), classifiers={}, finetune=ftc)
    assert code == 0
    blk = load(out)["results"]["systems"]["finetuned_on_silver_multi_seed"]
    assert "fine-tuned-on-silver" in blk["category"]
    assert blk["seeds_requested"] == cfg.SEEDS_FOR_MULTI_RUN == [42, 43, 44, 45, 46] and blk["seeds_scored"] == [42, 43, 44, 45, 46]
    # training set: 9 train-day rows, 1 identical to a gold sentence (case/punctuation differ) is removed -> 8 examples
    ts = blk["training_set"]
    assert ts["n_train_day_segments"] == 9 and ts["n_removed_identical_to_gold_or_valtest"] == 1 and ts["n_training_examples"] == 8
    assert "SILVER" in ts["label_origin"]
    assert len(FakeKeywordModel.calls) == 5 and all(len(texts) == 8 for _, texts in FakeKeywordModel.calls)
    assert all("Cricket match won again number 3!" not in texts for _, texts in FakeKeywordModel.calls)   # never trained on it
    # training set size and seed recorded per seed (also in the DONE marker on disk)
    for seed in (42, 43, 44, 45, 46):
        assert blk["per_seed"][str(seed)]["training"] == {"seed": seed, "n_training_examples": 8}
        done = json.load(open(os.path.join(tmp_path, "ft", f"seed_{seed}", "DONE")))
        assert done["seed"] == seed and done["n_training_examples"] == 8
    ms = blk["mean_std_over_seeds"]
    per = [blk["per_seed"][str(s)]["all_gold"]["macro_f1"] for s in (42, 43, 44, 45, 46)]
    assert ms["n_seeds"] == 5 and ms["macro_f1"]["mean"] == pytest.approx(np.mean(per))
    assert ms["macro_f1"]["std"] == pytest.approx(np.std(per, ddof=1)) and ms["macro_f1"]["std"] > 0
    assert per[0] == pytest.approx(1.0) and per[1] < per[0]          # seed 42 perfect, later seeds flip more predictions
    # rerun is resumable: finished seeds are not trained again
    FakeKeywordModel.calls.clear()
    genre_eval.run(paths, str(tmp_path / "res2"), systems=("finetuned",), classifiers={}, finetune=ftc)
    assert FakeKeywordModel.calls == []


def test_tfidf_baseline_records_multi_seed_and_leakage_filter(tmp_path):
    paths = _fixture_with_leaking_train_sentence(tmp_path)
    code, out = genre_eval.run(paths, str(tmp_path / "res"), systems=("baselines",), classifiers={})
    r = load(out)["results"]
    assert r["baseline_training_data"]["n_removed_identical_to_gold_or_valtest"] == 1
    ms = r["systems"]["tfidf_logreg_train_silver"]["multi_seed"]["mean_std_over_seeds"]
    assert ms["n_seeds"] == 5 and ms["macro_f1"]["std"] == pytest.approx(0.0)    # deterministic solver


def test_classifier_cache_is_per_model_and_device_override(monkeypatch):
    import nlp_pipeline
    loaded = []
    fake = types.SimpleNamespace(pipeline=lambda task, model=None, device=None: loaded.append((model, device)) or object())
    monkeypatch.setitem(sys.modules, "transformers", fake)
    monkeypatch.setenv("AIRINSIGHT_DEVICE", "cpu")
    monkeypatch.setattr(nlp_pipeline, "_classifier_pipeline", None)
    a = nlp_pipeline._get_classifier(fast=True)
    b = nlp_pipeline._get_classifier(fast=False)
    a2 = nlp_pipeline._get_classifier(fast=False)
    assert [m for m, _ in loaded] == [nlp_pipeline.FAST_CLASSIFIER_MODEL, nlp_pipeline.DEFAULT_CLASSIFIER_MODEL]
    assert a is not b and b is a2 and all(d == -1 for _, d in loaded)    # BART no longer silently reuses the fast model


def test_hour_of_default_systems_and_cli_flags():
    assert genre_eval.ALL_SYSTEMS == ("baselines", "fast", "zero-shot", "finetuned")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "eval", "genre_eval.py"), "--systems", "nonsense"],
                       cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 2 and "unknown systems" in p.stderr


# =============================================================== 3. MinHash
def test_minhash_known_values():
    assert dedup_eval.shingles("a b c d", 3) == {("a", "b", "c"), ("b", "c", "d")}
    assert dedup_eval.shingles("a b", 3) == {("a", "b")} and dedup_eval.shingles("", 3) == set()
    a = " ".join(f"w{i}" for i in range(1, 13))
    b = " ".join([f"w{i}" for i in range(1, 12)] + ["zz"])
    assert dedup_eval.minhash_jaccard(a, a) == 1.0
    assert dedup_eval.minhash_jaccard(a, "x y z q r s t") == 0.0
    assert dedup_eval.minhash_jaccard("", a) == 0.0
    est = dedup_eval.minhash_jaccard(a, b)               # true Jaccard of the 3-shingle sets is 9/11
    assert abs(est - 9 / 11) < 0.12 and est == dedup_eval.minhash_jaccard(a, b)    # within 3 standard errors, deterministic
    assert cfg.MINHASH_SHINGLE_WORDS == 3 and cfg.MINHASH_PERMUTATIONS == 128


def test_minhash_baseline_is_in_the_dedup_result_with_parameters(tmp_path):
    from test_eval_metrics import _pair_fixture
    code, out = dedup_eval.run(_pair_fixture(tmp_path), str(tmp_path / "res"))
    assert code == 0
    r = load(out)["results"]
    assert r["minhash"]["permutations"] == 128 and "3-grams" in r["minhash"]["shingle"] and r["minhash"]["seed"] == cfg.SEED
    for d in r["definitions"].values():
        assert "minhash_jaccard_estimate" in d["methods"] and "word_5gram_jaccard" in d["methods"]


# =============================================================== 4. retrieval ablations
def _full_mrr(out, qid="Q1"):
    return load(out)["results"]["per_query"][qid]["systems"]["full_system"]["metrics"]["mrr"]


def test_ablation_flag_names_and_defaults():
    assert retrieval_eval.DEFAULT_FLAGS == {"prefilter": True, "relevance_filter": True, "dedup": True}
    assert retrieval_eval.result_name(retrieval_eval.DEFAULT_FLAGS) == "retrieval_eval"
    assert retrieval_eval.result_name({**retrieval_eval.DEFAULT_FLAGS, "prefilter": False, "dedup": False}) == \
        "retrieval_eval_ablation_noprefilter_nodedup"
    on = retrieval_eval.default_paths()
    off = retrieval_eval.default_paths({"dedup": False})
    assert on["store_db"] == cfg.STORE_DB and off["store_db"].startswith(cfg.STORE_NODEDUP_DIR)


def test_prefilter_switch_changes_full_system_when_the_silver_genre_is_wrong(tmp_path):
    # B1S1 ("Cricket team won the final match.") gets the WRONG silver genre; the genre prefilter then hides it
    paths, _ = _retrieval_fixture(tmp_path, [{"id": "Q1", "query_text": "cricket final match", "date_constraint": "",
                                              "relevant_segment_ids": "2026-08-16_English-0105-0110-1_s001"}])
    import sqlite3
    con = sqlite3.connect(paths["store_db"])
    con.execute("UPDATE segments SET genre = 'Politics' WHERE faiss_id = 0")
    con.commit()
    con.close()
    c_on, out_on = retrieval_eval.run(paths, str(tmp_path / "r_on"), embed_fn=fake_embed)
    c_off, out_off = retrieval_eval.run(paths, str(tmp_path / "r_off"), embed_fn=fake_embed, flags={"prefilter": False})
    assert c_on == c_off == 0
    assert _full_mrr(out_on) == 0.0 and _full_mrr(out_off) == 1.0
    assert os.path.basename(out_off).startswith("retrieval_eval_ablation_noprefilter_")
    d = load(out_off)["results"]
    assert d["ablation_flags"]["prefilter"] is False and d["ablation_flags"]["relevance_filter"] is True
    # the other systems do not use the switch
    assert load(out_on)["results"]["per_query"]["Q1"]["systems"]["bm25"]["metrics"] == \
        load(out_off)["results"]["per_query"]["Q1"]["systems"]["bm25"]["metrics"]


def test_relevance_filter_switch(tmp_path):
    # one shared word out of ten: cosine about 0.13 < 0.20, so the relevance filter returns nothing; switched off, B1S2 ranks first
    gid = "2026-08-16_English-0105-0110-1_s002"
    q = [{"id": "Q1", "query_text": "slabs foo bar baz qux quux corge grault garply", "date_constraint": "", "relevant_segment_ids": gid}]
    paths, _ = _retrieval_fixture(tmp_path, q)
    extra = {"id": gid, "date": "2026-08-16", "hour": "1", "source_file": "English-0105-0110-1.mp3", "position": "2",
             "split": "val", "text": "The budget raised income tax slabs."}
    rows = common.read_csv(paths["sentence_index"]) + [extra]
    from test_eval_metrics import write_csv
    write_csv(paths["sentence_index"], rows, ["id", "date", "hour", "source_file", "position", "split", "text"])
    _, out_on = retrieval_eval.run(paths, str(tmp_path / "r_on"), embed_fn=fake_embed)
    _, out_off = retrieval_eval.run(paths, str(tmp_path / "r_off"), embed_fn=fake_embed, flags={"relevance_filter": False})
    assert _full_mrr(out_on) == 0.0 and _full_mrr(out_off) == 1.0
    assert "noreleva" in os.path.basename(out_off) or "norelevancefilter" in os.path.basename(out_off)
    assert load(out_off)["results"]["ablation_flags"]["relevance_filter"] is False


def test_dedup_off_needs_its_own_store(tmp_path):
    paths = retrieval_eval.default_paths({"dedup": False})
    assert "store_A_nodedup" in paths["store_db"] and "store_A_nodedup" in paths["build_report"]
    q = [{"id": "Q1", "query_text": "cricket", "date_constraint": "", "relevant_segment_ids": "x"}]
    p, _ = _retrieval_fixture(tmp_path, q)
    p["store_db"] = str(tmp_path / "missing" / "news_store.db")
    assert retrieval_eval.run(p, str(tmp_path / "res"), embed_fn=fake_embed, flags={"dedup": False}) == (2, None)


def test_build_store_no_gate_refuses_store_A():
    p = subprocess.run([sys.executable, os.path.join(ROOT, "build_store_A.py"), "--no-gate"], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode != 0 and "store_A_nodedup" in (p.stderr + p.stdout)


# =============================================================== 5. ASR caching
def test_transcribe_cached_uses_cache_without_loading_a_model(tmp_path, monkeypatch):
    cache = tmp_path / "hyp" / "tiny" / "x.txt"
    cache.parent.mkdir(parents=True)
    cache.write_text("cached words", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "air_bulletins_scraper", None)           # an import would fail loudly
    assert asr_eval.transcribe_cached("missing.mp3", "tiny", str(cache)) == "cached words"


def test_transcribe_cached_transcribes_once_and_caches(tmp_path, monkeypatch):
    calls = []
    fake = types.SimpleNamespace(resolve_device=lambda t, d, c: ("cuda", "float16"),
                                 transcribe_with_stats=lambda audio, tr, model, dev, ct: calls.append((model, dev, ct)) or {"text": "hello world"})
    monkeypatch.setitem(sys.modules, "air_bulletins_scraper", fake)
    cache = str(tmp_path / "hyp" / "base" / "x.txt")
    assert asr_eval.transcribe_cached("a.mp3", "base", cache) == "hello world"
    assert asr_eval.transcribe_cached("a.mp3", "base", cache) == "hello world"
    assert calls == [("base", "cuda", "float16")] and os.path.isfile(cache)


@pytest.mark.skipif(os.environ.get("AIRINSIGHT_GPU_SMOKE") != "1", reason="GPU smoke test: set AIRINSIGHT_GPU_SMOKE=1 to run")
def test_gpu_smoke_tiny_model_transcribes_one_short_clip_and_caches(tmp_path):
    """Real Whisper tiny on the GPU, one 20-second clip cut from an option A bulletin (read-only); hypothesis cached in tmp."""
    src = None
    for root, _dirs, files in os.walk(os.path.join(cfg.SAMPLE_DIR, "audio")):
        for f in sorted(files):
            if f.endswith(".mp3"):
                src = os.path.join(root, f)
                break
        if src:
            break
    assert src, "no option A audio found"
    clip = str(tmp_path / "clip.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "30", "-t", "20", "-i", src, clip], check=True)
    import air_bulletins_scraper as scraper
    device, compute = scraper.resolve_device("faster-whisper", "auto", None)
    cache = str(tmp_path / "hyp" / "tiny" / "clip.txt")
    loads_before = scraper.MODEL_LOADS
    text = asr_eval.transcribe_cached(clip, "tiny", cache)
    print(f"\nSMOKE device={device} compute={compute} chars={len(text)} words={len(text.split())}")
    assert device == "cuda", f"expected the GPU, got {device}"
    assert len(text.split()) >= 5 and os.path.getsize(cache) > 0
    assert scraper.MODEL_LOADS == loads_before + 1
    assert asr_eval.transcribe_cached(clip, "tiny", cache) == text and scraper.MODEL_LOADS == loads_before + 1   # second call: cache


# =============================================================== scale benchmark (tiny, synthetic, in tmp)
def test_scale_benchmark_runs_small_and_is_resumable(tmp_path):
    res = scale_benchmark.run_benchmark(300, 5, workdir=str(tmp_path / "w"))
    assert res["n_segments"] == 300 and "SYNTHETIC" in res["data"]
    assert set(res["query_latency_ms"]) == {"unfiltered", "date_genre_prefilter"} and "p95" in res["query_latency_ms"]["unfiltered"]
    p = subprocess.run([sys.executable, os.path.join(ROOT, "eval", "scale_benchmark.py"), "--n", "300", "--queries", "3",
                        "--results-dir", str(tmp_path / "res")], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0 and len(os.listdir(tmp_path / "res")) == 1
    again = subprocess.run([sys.executable, os.path.join(ROOT, "eval", "scale_benchmark.py"), "--n", "300", "--queries", "3",
                            "--results-dir", str(tmp_path / "res")], cwd=ROOT, capture_output=True, text=True)
    assert "skipping" in again.stdout and len(os.listdir(tmp_path / "res")) == 1


# =============================================================== 6. cluster scripts
SCRIPTS = sorted(f for f in os.listdir(os.path.join(ROOT, "cluster")) if f.endswith(".sbatch"))


def test_four_sbatch_scripts_exist():
    assert SCRIPTS == ["01_bart_label_store.sbatch", "02_finetune_genre.sbatch", "03_asr_sizes.sbatch", "04_scale_benchmark.sbatch"]


@pytest.mark.parametrize("name", SCRIPTS)
def test_sbatch_script_has_required_directives_smoke_mode_and_unix_line_endings(name):
    raw = open(os.path.join(ROOT, "cluster", name), "rb").read()
    assert b"\r" not in raw, "sbatch scripts must use LF line endings"
    text = raw.decode("utf-8")
    for needle in ("#SBATCH --job-name=", "#SBATCH --output=logs/%x_%j.out", "#SBATCH --cpus-per-task=32", "#SBATCH --mem=64G",
                   "#SBATCH --time=", "--requeue", 'MODE="${1:-full}"', 'if [ "${MODE}" = "smoke" ]', "00:05:00"):
        assert needle in text, (name, needle)
    if name.startswith("04"):
        assert not any(l.startswith("#SBATCH --gres") for l in text.splitlines()) and "does NOT request a GPU" in text   # CPU-only, on purpose
    else:
        assert "#SBATCH --gres=gpu:1" in text
    bash = shutil.which("bash")
    if bash:
        assert subprocess.run([bash, "-n", os.path.join(ROOT, "cluster", name)], capture_output=True).returncode == 0


def test_transcribe_cached_reports_stats_only_when_it_transcribes(tmp_path, monkeypatch):
    fake = types.SimpleNamespace(resolve_device=lambda t, d, c: ("cuda", "float16"),
                                 transcribe_with_stats=lambda *a: {"text": "x y z", "duration_s": 10.0, "seconds": 0.5, "rtf": 0.05})
    monkeypatch.setitem(sys.modules, "air_bulletins_scraper", fake)
    cache = str(tmp_path / "h" / "tiny" / "a.txt")
    st = {}
    asr_eval.transcribe_cached("a.mp3", "tiny", cache, stats=st)
    assert st == {"duration_s": 10.0, "seconds": 0.5, "rtf": 0.05, "device": "cuda", "compute_type": "float16"}
    st2 = {}
    asr_eval.transcribe_cached("a.mp3", "tiny", cache, stats=st2)
    assert st2 == {}                                    # served from the cache: nothing was transcribed


def test_vram_sampler_handles_missing_nvidia_smi(monkeypatch):
    import asr_transcribe
    monkeypatch.setattr(asr_transcribe, "gpu_used_mib", lambda: None)
    with asr_transcribe.VramSampler(interval=0.01) as v:
        pass
    assert v.peak is None and v.baseline is None
