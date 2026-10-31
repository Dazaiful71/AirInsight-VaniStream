"""
ingest_pipeline.py - Orchestrator for AIR News Intelligence ingestion

Reads metadata.csv, finds unprocessed transcripts, runs the NLP pipeline,
and stores results in the FAISS + SQLite vector store.

CLI usage:
  python ingest_pipeline.py               # process all unprocessed files
  python ingest_pipeline.py --reindex     # wipe FAISS + DB and reindex everything
"""

import argparse
import csv
import json
import logging
import os
import re
from typing import Optional

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("ingest_pipeline")

METADATA_CSV = os.path.join("output", "metadata.csv")
PROCESSED_FILE = "processed_files.txt"


def _load_processed(path: str = PROCESSED_FILE) -> set[str]:
    """Load set of already-processed transcript file paths."""
    if not os.path.isfile(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _mark_processed(filepath: str, path: str = PROCESSED_FILE) -> None:
    """Append a transcript path to the processed-files tracker."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(filepath + "\n")


def _extract_hour_and_flag(filename: str) -> tuple[Optional[int], str]:
    """Broadcast hour 0-23 from the first standalone HHMM group in the filename, plus a flag.

    'English-0800-0810-1.txt' -> (8, ''). No time in the name -> (None, 'no_time_in_filename');
    a group that is not a valid HHMM -> (None, 'invalid_hhmm'). Never returns 0 for "unknown".
    Same rule as air_bulletins_scraper.parse_hour_from_url.
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"(?<!\d)(\d{4})(?!\d)", base)
    if not m:
        return None, "no_time_in_filename"
    hhmm = int(m.group(1))
    if hhmm // 100 > 23 or hhmm % 100 > 59:
        return None, "invalid_hhmm"
    return hhmm // 100, ""


def _extract_hour(filename: str) -> Optional[int]:
    """Broadcast hour 0-23, or None when the filename has no valid time (see _extract_hour_and_flag)."""
    return _extract_hour_and_flag(filename)[0]


class DedupStats:
    """Dedup statistics in one schema for batch ingest and live ingest (the dedup_report.json layout)."""

    def __init__(self, top_n: int = 20):
        self.top_n = top_n
        self.per_file: list[dict] = []
        self.top_rejected: list[dict] = []

    def add_file(self, source_file: str, total_sentences: int, novel_sentences: int, rejections: list[dict]) -> None:
        self.per_file.append({
            "source_file": source_file,
            "total_sentences": total_sentences,
            "novel_sentences": novel_sentences,
            "rejected_sentences": len(rejections),
        })
        self.top_rejected = sorted(self.top_rejected + list(rejections),
                                   key=lambda x: x["cosine_score"], reverse=True)[:self.top_n]

    def report(self) -> dict:
        tot = sum(f["total_sentences"] for f in self.per_file)
        nov = sum(f["novel_sentences"] for f in self.per_file)
        rej = sum(f["rejected_sentences"] for f in self.per_file)
        return {
            "totals": {
                "total_sentences": tot,
                "novel_sentences": nov,
                "rejected_sentences": rej,
                "reduction_pct": round((rej / tot * 100), 1) if tot > 0 else 0.0,
            },
            "per_file": self.per_file,
            "top_rejected_pairs": self.top_rejected,
        }

    def write(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.report(), f, indent=2, ensure_ascii=False)


def _read_metadata(csv_path: str = METADATA_CSV) -> list[dict]:
    """Read metadata.csv and return rows that have a transcript_file."""
    if not os.path.isfile(csv_path):
        logger.warning("Metadata CSV not found: %s", csv_path)
        return []
    rows = []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tf = (row.get("transcript_file") or "").strip()
            if tf:
                rows.append(row)
    return rows


def run(
    reindex: bool = False,
    fast: bool = False,
    mmr_threshold: float = 0.85,
    metadata_csv: str = METADATA_CSV,
    classifier: str = "zero-shot",
    text_root: str = "output",
    index_path: str = "faiss_index.bin",
    db_path: str = "news_store.db",
    processed_file: str = PROCESSED_FILE,
    report_path: str = "dedup_report.json",
    sort_rows: bool = False,
) -> dict:
    """Run the full ingestion pipeline.

    Args:
        reindex: If True, wipe the vector store and reprocess everything.
        fast: Use the lightweight NLP classifier (shorthand for classifier='fast').
        mmr_threshold: MMR cosine similarity threshold for deduplication.
        metadata_csv: Path to the metadata CSV.
        classifier: Classifier backend -- 'zero-shot' | 'fast' | 'finetuned'.
                    --fast flag maps to 'fast' for backward compatibility.
        text_root: Folder the metadata's transcript_file paths are relative to.
        index_path, db_path: FAISS index and SQLite files to read/write (defaults = the project store).
        processed_file, report_path: resume tracker and dedup report locations.
        sort_rows: Process rows in (date, hour, file) order instead of metadata order.

    Returns:
        Summary dict: files_processed, segments_added, duplicates_filtered.
    """
    import vector_store
    from nlp_pipeline import process_transcript

    # Backward compat: --fast maps to classifier='fast'
    if fast and classifier == "zero-shot":
        classifier = "fast"
    logger.info("Classifier backend: %s", classifier)

    if reindex:
        logger.info("REINDEX mode: wiping existing FAISS index and SQLite DB")
        vector_store.wipe(index_path, db_path)
        # Clear processed tracker
        if os.path.isfile(processed_file):
            os.remove(processed_file)
        if os.path.isfile(report_path):
            os.remove(report_path)

    rows = _read_metadata(metadata_csv)
    if not rows:
        logger.info("No transcript rows found in metadata CSV")
        return {"files_processed": 0, "segments_added": 0, "duplicates_filtered": 0}

    if sort_rows:
        rows.sort(key=lambda r: (r.get("date", ""), _extract_hour(os.path.basename(r["transcript_file"].replace("\\", "/"))) is None,
                                 _extract_hour(os.path.basename(r["transcript_file"].replace("\\", "/"))) or 0, r["transcript_file"]))

    processed = set() if reindex else _load_processed(processed_file)
    logger.info("Found %d transcript rows, %d already processed", len(rows), len(processed))

    total_segments = 0
    total_duplicates = 0
    files_done = 0
    stats = DedupStats()

    for row in rows:
        transcript_rel = row["transcript_file"].replace("\\", "/")
        transcript_path = os.path.join(text_root, transcript_rel)

        if transcript_rel in processed:
            continue

        if not os.path.isfile(transcript_path):
            logger.warning("Transcript file missing: %s", transcript_path)
            continue

        date = row.get("date", "unknown")
        hour, hour_flag = _extract_hour_and_flag(os.path.basename(transcript_path))
        if hour is None:
            logger.warning("No valid broadcast time in filename %s (%s); hour stored as NULL", transcript_rel, hour_flag)

        with open(transcript_path, "r", encoding="utf-8") as f:
            text = f.read()

        if not text.strip():
            logger.warning("Empty transcript: %s", transcript_path)
            _mark_processed(transcript_rel, processed_file)
            continue

        # Load current embeddings and texts for dedup
        existing_embeddings = vector_store.get_all_embeddings(index_path)
        existing_texts = vector_store.get_all_texts(db_path)

        # Run NLP pipeline with detailed dedup reporting
        logger.info("Processing: %s (date=%s, hour=%s)", transcript_rel, date, "unknown" if hour is None else hour)
        segments, file_rejections = process_transcript(
            text,
            existing_embeddings=existing_embeddings,
            existing_texts=existing_texts,
            fast=fast,
            mmr_threshold=mmr_threshold,
            detailed=True,
            classifier=classifier,
        )

        from nlp_pipeline import segment_sentences
        original_count = len(segment_sentences(text))
        novel_count = len(segments)
        rejected_count = len(file_rejections)
        total_duplicates += rejected_count

        stats.add_file(transcript_rel, original_count, novel_count, file_rejections)

        # Store in vector store
        if segments:
            added = vector_store.add_segments(segments, date, hour, transcript_rel, index_path, db_path,
                                                hour_flag=hour_flag, split=(row.get("split") or None))
            total_segments += added

        _mark_processed(transcript_rel, processed_file)
        files_done += 1

    if stats.per_file:
        stats.write(report_path)
        logger.info("Saved dedup report to %s (%d rejected pairs)", report_path, total_duplicates)

    summary = {
        "files_processed": files_done,
        "segments_added": total_segments,
        "duplicates_filtered": total_duplicates,
    }
    logger.info(
        "Ingestion complete: %d files processed, %d segments added, %d duplicates filtered",
        summary["files_processed"],
        summary["segments_added"],
        summary["duplicates_filtered"],
    )
    return summary


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Ingest transcripts into the vector store.")
    parser.add_argument("--reindex", action="store_true",
                        help="Wipe FAISS + DB and reindex everything")
    parser.add_argument("--fast", action="store_true",
                        help="Use lighter NLP classifier model (shorthand for --classifier fast)")
    parser.add_argument(
        "--classifier",
        choices=["zero-shot", "fast", "finetuned"],
        default="zero-shot",
        help="Classifier backend: zero-shot (default), fast, or finetuned",
    )
    parser.add_argument("--mmr-threshold", type=float, default=0.85,
                        help="MMR cosine similarity threshold (default 0.85)")
    parser.add_argument("--csv", default=METADATA_CSV,
                        help="Path to metadata CSV")
    args = parser.parse_args()

    summary = run(
        reindex=args.reindex,
        fast=args.fast,
        mmr_threshold=args.mmr_threshold,
        metadata_csv=args.csv,
        classifier=args.classifier,
    )
    print(f"\n{'='*50}")
    print(f"  Files processed:     {summary['files_processed']}")
    print(f"  Segments added:      {summary['segments_added']}")
    print(f"  Duplicates filtered: {summary['duplicates_filtered']}")
    print(f"{'='*50}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
