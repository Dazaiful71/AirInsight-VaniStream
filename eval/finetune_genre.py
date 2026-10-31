"""Leakage-safe fine-tuning of the genre classifier on TRAIN-day SILVER labels, several seeds (S9). NOT run by default.

Training data = store_A segments with split == 'train' (silver genre labels), minus every sentence whose normalised text
is identical to a gold sentence or to any val/test sentence in data/gold/valtest_sentence_index.csv (the S6 leakage rule).
Each seed writes models/finetune_silver/seed_<n>/ (a checkpoint from train_genre_classifier.train) and a DONE marker;
a rerun skips seeds that are done (resumable). genre_eval.py scores the finished checkpoints on the gold sheet.

  .venv_gpu/Scripts/python.exe eval/finetune_genre.py --smoke     # tiny run: 64 examples, 1 epoch, 1 seed, separate folder
  .venv_gpu/Scripts/python.exe eval/finetune_genre.py             # all 5 seeds (GPU strongly recommended; see cluster/)
"""
import argparse
import csv
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eval_common as common  # noqa: E402
import eval_config as cfg  # noqa: E402

SILVER_ORIGIN = "SILVER: store_A genre column of train-day segments (fast/zero-shot classifier output, never gold)"


def normalise_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def leakage_filter(texts, labels, forbidden_texts):
    """Drop training sentences whose normalised text equals any forbidden (gold / val / test) sentence. Returns (texts, labels, removed)."""
    bad = {normalise_text(t) for t in forbidden_texts}
    keep = [i for i, t in enumerate(texts) if normalise_text(t) not in bad]
    return [texts[i] for i in keep], [labels[i] for i in keep], len(texts) - len(keep)


def load_train_silver(store_db: str):
    if not os.path.isfile(store_db):
        raise common.PrerequisiteMissing(f"store not found: {common.rel(store_db)} (run the ingest stage first)")
    con = sqlite3.connect(store_db)
    rows = con.execute("SELECT text, genre FROM segments WHERE split = 'train' AND genre IS NOT NULL ORDER BY rowid").fetchall()
    con.close()
    if not rows:
        raise common.PrerequisiteMissing("store has no train-split segments with a genre")
    return [r[0] for r in rows], [r[1] for r in rows]


def forbidden_sentences(gold_csv: str, sentence_index_csv: str = "") -> tuple:
    gold = [r["sentence_text"] for r in common.read_csv(gold_csv)] if gold_csv and os.path.isfile(gold_csv) else []
    allvt = [r["text"] for r in common.read_csv(sentence_index_csv)] if sentence_index_csv and os.path.isfile(sentence_index_csv) else []
    return gold, allvt


def build_training_set(store_db, gold_csv, sentence_index_csv=""):
    texts, labels = load_train_silver(store_db)
    gold, allvt = forbidden_sentences(gold_csv, sentence_index_csv)
    t2, l2, removed = leakage_filter(texts, labels, gold + allvt)
    _, _, removed_gold_only = leakage_filter(texts, labels, gold)
    info = {"source": "store_A segments with split == 'train'", "label_origin": SILVER_ORIGIN,
            "n_train_day_segments": len(texts), "n_removed_identical_to_gold_or_valtest": removed,
            "n_removed_identical_to_gold_sheet_only": removed_gold_only, "n_training_examples": len(t2),
            "class_counts": {l: l2.count(l) for l in sorted(set(l2))}}
    return t2, l2, info


def write_training_csv(path, texts, labels):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "true_genre"])
        w.writerows(zip(texts, labels))


def seed_dir(base: str, seed: int) -> str:
    return os.path.join(base, f"seed_{seed}")


def is_done(directory: str) -> bool:
    return os.path.isfile(os.path.join(directory, "DONE"))


def default_trainer(csv_path, out_dir, seed, epochs=5, batch_size=16):
    """train_genre_classifier.train on the given CSV; returns its exit code (0 = ok)."""
    import train_genre_classifier
    return train_genre_classifier.train(csv_path=csv_path, out_dir=out_dir, seed=seed, epochs=epochs, batch_size=batch_size)


def train_seed(texts, labels, seed, base_dir, info, trainer=default_trainer, **kw) -> dict:
    """Train one seed unless it is already done. The DONE marker records the training set size and seed."""
    d = seed_dir(base_dir, seed)
    if is_done(d):
        return {"seed": seed, "status": "skipped (already done)", "dir": d}
    csv_path = os.path.join(d, "train.csv")
    write_training_csv(csv_path, texts, labels)
    rc = trainer(csv_path, d, seed, **kw)
    if rc != 0:
        return {"seed": seed, "status": f"failed (trainer exit {rc})", "dir": d}
    with open(os.path.join(d, "DONE"), "w", encoding="utf-8") as f:
        json.dump({"seed": seed, "n_training_examples": len(texts), "training_set": info}, f, indent=2)
    return {"seed": seed, "status": "trained", "dir": d}


def hf_predictor(out_dir, texts, batch_size=32, max_len=128):
    """Predict genre labels with a checkpoint saved by train_genre_classifier (uses its label_map.json)."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(out_dir)
    model = AutoModelForSequenceClassification.from_pretrained(out_dir).eval()
    id2label = {int(k): v for k, v in json.load(open(os.path.join(out_dir, "label_map.json")))["id2label"].items()}
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(dev)
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            enc = tok(texts[i:i + batch_size], padding=True, truncation=True, max_length=max_len, return_tensors="pt").to(dev)
            out += [id2label[j] for j in model(**enc).logits.argmax(-1).cpu().tolist()]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="64 examples, 1 epoch, first seed only, written to models/finetune_silver_smoke")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--seeds", type=int, nargs="*", default=cfg.SEEDS_FOR_MULTI_RUN)
    a = ap.parse_args()
    try:
        texts, labels, info = build_training_set(cfg.STORE_DB, cfg.GOLD_GENRE, cfg.GOLD_SENTENCE_INDEX)
    except common.PrerequisiteMissing as e:
        print(f"[finetune_genre] CANNOT RUN: {e}")
        return 2
    base, seeds, epochs = cfg.FINETUNE_DIR, a.seeds, a.epochs
    if a.smoke:
        texts, labels, base, seeds, epochs = texts[:64], labels[:64], cfg.FINETUNE_DIR + "_smoke", seeds[:1], 1
        info = {**info, "smoke_test": True, "n_training_examples": len(texts)}
    print(f"[finetune_genre] {info['n_training_examples']} training examples "
          f"({info['n_removed_identical_to_gold_or_valtest']} removed as identical to gold/val/test text), seeds {seeds}")
    for s in seeds:
        r = train_seed(texts, labels, s, base, info, epochs=epochs, batch_size=a.batch_size)
        print(f"[finetune_genre] seed {s}: {r['status']}")
        if r["status"].startswith("failed"):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
