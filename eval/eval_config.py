"""Shared settings for every eval script: paths, seeds, split names, gold files, allowed labels.

Nothing in this file is a result. Change a path or seed here, not inside an eval script.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- seeds (the same value that built the gold sheets; evals that need randomness take it from here)
SEED = 42
SEEDS_FOR_MULTI_RUN = [42, 43, 44, 45, 46]   # 5 seeds for anything trainable (mean and std reported)

# ---- splits (whole days; the day lists live in config/sample_config.json, block pilot_plan_s4, option A)
SPLITS = ("train", "val", "test")
GOLD_SPLITS = ("val", "test")        # gold sentences exist only on these days; train days are silver-training only

# ---- paths
SAMPLE_CONFIG = os.path.join(ROOT, "config", "sample_config.json")
SAMPLE_DIR = os.path.join(ROOT, "data", "sample_A")
SAMPLE_METADATA = os.path.join(SAMPLE_DIR, "metadata.csv")
STORE_DIR = os.path.join(ROOT, "store_A")
STORE_DB = os.path.join(STORE_DIR, "news_store.db")
STORE_INDEX = os.path.join(STORE_DIR, "faiss_index.bin")
STORE_BUILD_REPORT = os.path.join(STORE_DIR, "build_report.json")
STORE_NODEDUP_DIR = os.path.join(ROOT, "store_A_nodedup")   # ablation store built with the gate off (build_store_A.py --no-gate); not built yet
FINETUNE_DIR = os.path.join(ROOT, "models", "finetune_silver")   # seed_<n>/ checkpoints from eval/finetune_genre.py
PROJECT_CHECKPOINT = os.path.join(ROOT, "models", "air-genre-classifier")   # the older checkpoint from train_genre_classifier.py, if present
RESULTS_DIR = os.path.join(ROOT, "results")
GOLD_DIR = os.path.join(ROOT, "data", "gold")

GOLD_GENRE = os.path.join(GOLD_DIR, "genre_sheet_annotator1.csv")
GOLD_GENRE_ANNOTATOR2 = os.path.join(GOLD_DIR, "genre_sheet_annotator2_overlap.csv")
GOLD_PAIRS = os.path.join(GOLD_DIR, "duplicate_pairs_sheet.csv")
GOLD_PAIRS_KEY = os.path.join(GOLD_DIR, "duplicate_pairs_HIDDEN_KEY.csv")   # only evals read this, never annotators
GOLD_QUERIES = os.path.join(GOLD_DIR, "query_sheet.csv")
GOLD_SENTENCE_INDEX = os.path.join(GOLD_DIR, "valtest_sentence_index.csv")
GOLD_ASR_DIR = os.path.join(GOLD_DIR, "asr_refs")   # one hand-corrected <audio file stem>.txt per WER bulletin (TODO: not created yet)
ASR_HYP_DIR = os.path.join(ROOT, "data", "asr_hyp")   # Whisper outputs per model: <model>/<stem>.txt (small = the option A transcripts)
SAMPLE_TEXT_DIR = os.path.join(SAMPLE_DIR, "text")

# ---- metric settings (all evals read these; they are settings, not results)
BOOTSTRAP_RESAMPLES = 1000          # percentile bootstrap, 95% CI (2.5th and 97.5th percentile), resampling items/pairs/queries
MIN_CLASS_SUPPORT = 5               # no per-class score below this many gold examples
DEDUP_THRESHOLDS = [round(0.60 + 0.01 * i, 2) for i in range(36)]            # 0.60 .. 0.95 for the project's cosine
DEDUP_BASELINE_THRESHOLDS = [round(0.01 * i, 2) for i in range(101)]         # 0.00 .. 1.00 for TF-IDF cosine / Jaccard baselines
RETRIEVAL_KS = (1, 3, 5, 10)
RETRIEVAL_DEPTH = 20                # every system returns its top 20 (rag_engine's timeline depth); ranks beyond count as a miss
NDCG_K = 5
ASR_MODELS = ("tiny", "base", "small")
MINHASH_SHINGLE_WORDS = 3           # word shingles of this size (sentences are short)
MINHASH_PERMUTATIONS = 128          # signature length; estimate error about 1/sqrt(128) = 0.09 at worst

# ---- label sets
PAIR_LABELS = ("same", "paraphrase", "follow-up", "different")   # definitions still TODO (see data/gold/README.md)


def genre_labels() -> list:
    """The project's own label set (nlp_pipeline.GENRE_LABELS)."""
    import sys
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from nlp_pipeline import GENRE_LABELS
    return list(GENRE_LABELS)
