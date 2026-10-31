"""
vector_store.py - FAISS + SQLite Vector Store for AIR News Intelligence System

Manages the local FAISS index with rich metadata for two-tier retrieval.
- FAISS IndexFlatIP (inner product / cosine similarity on unit vectors)
- SQLite metadata database (news_store.db)
- Embedding dimension: 384 (all-MiniLM-L6-v2)

CLI usage:
  python vector_store.py --stats
"""

import argparse
import csv
import datetime
import json
import logging
import os
import sqlite3
from typing import Optional

logging.getLogger("faiss.loader").setLevel(logging.WARNING)
import faiss
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("vector_store")

FAISS_INDEX_PATH = "faiss_index.bin"
SQLITE_DB_PATH = "news_store.db"
EMBEDDING_DIM = 384

# ---------------------------------------------------------------------------
# SQLite Schema
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faiss_id INTEGER UNIQUE,
    text TEXT NOT NULL,
    genre TEXT,
    genre_confidence REAL,
    date TEXT,
    hour INTEGER,          -- broadcast hour 0-23, NULL when unknown (never 0 for unknown)
    split TEXT,            -- train / val / test (day-level split) when known, else NULL
    hour_flag TEXT,        -- '' when hour is known, else why it is NULL (no_time_in_filename / invalid_hhmm)
    source_file TEXT,
    indexed_at TEXT,
    audio_start REAL,
    audio_end REAL
);
"""


def _get_db(db_path: str = SQLITE_DB_PATH) -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure the schema exists."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(CREATE_TABLE_SQL)
    # Ensure audio_start and audio_end columns exist for backward compatibility
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(segments)").fetchall()]
    if "audio_start" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN audio_start REAL")
    if "audio_end" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN audio_end REAL")
    if "hour_flag" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN hour_flag TEXT")
    if "split" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN split TEXT")
    conn.commit()
    return conn


def _load_or_create_index(index_path: str = FAISS_INDEX_PATH) -> faiss.Index:
    """Load an existing FAISS index from disk, or create a new one."""
    if os.path.isfile(index_path):
        logger.info("Loading existing FAISS index from %s", index_path)
        return faiss.read_index(index_path)
    logger.info("Creating new FAISS IndexFlatIP (dim=%d)", EMBEDDING_DIM)
    return faiss.IndexFlatIP(EMBEDDING_DIM)


def _save_index(index: faiss.Index, index_path: str = FAISS_INDEX_PATH) -> None:
    """Persist the FAISS index to disk."""
    faiss.write_index(index, index_path)
    logger.info("Saved FAISS index (%d vectors) to %s", index.ntotal, index_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_segments(
    segments: list[dict],
    date: str,
    hour: Optional[int],
    source_file: str,
    index_path: str = FAISS_INDEX_PATH,
    db_path: str = SQLITE_DB_PATH,
    hour_flag: str = "",
    split: Optional[str] = None,
) -> int:
    """Add novel segments (from nlp_pipeline) to FAISS and SQLite.

    Args:
        segments: List of dicts with keys: text, genre, genre_confidence, embedding.
        date: Broadcast date (YYYY-MM-DD).
        hour: Broadcast hour 0-23, or None when unknown (stored as NULL, never as 0).
        source_file: Path to the source transcript file.
        index_path: Path to the FAISS index file.
        db_path: Path to the SQLite database.
        hour_flag: Reason the hour is unknown (only used when hour is None).
        split: Day-level split label (train/val/test) stored with every segment, or None.

    Returns:
        Number of segments added.
    """
    if hour is not None and not (isinstance(hour, (int, np.integer)) and 0 <= hour <= 23):
        raise ValueError(f"hour must be 0-23 or None, got {hour!r} (HHMM values such as 800 are not allowed)")
    if hour is None and not hour_flag:
        hour_flag = "unknown"
    if hour is not None:
        hour, hour_flag = int(hour), ""
    if not segments:
        return 0

    index = _load_or_create_index(index_path)
    db = _get_db(db_path)

    # Build embedding matrix and normalise to unit vectors
    embeddings = np.vstack([seg["embedding"] for seg in segments]).astype(np.float32)
    faiss.normalize_L2(embeddings)

    # Starting FAISS ID = current total
    start_id = index.ntotal
    index.add(embeddings)

    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    for i, seg in enumerate(segments):
        fid = start_id + i
        db.execute(
            "INSERT INTO segments (faiss_id, text, genre, genre_confidence, date, hour, hour_flag, source_file, indexed_at, audio_start, audio_end, split) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fid,
                seg["text"],
                seg["genre"],
                seg["genre_confidence"],
                date,
                hour,
                hour_flag,
                source_file,
                now,
                seg.get("audio_start"),
                seg.get("audio_end"),
                split,
            ),
        )
    db.commit()
    db.close()

    _save_index(index, index_path)
    logger.info("Added %d segments (date=%s, hour=%s)", len(segments), date, hour if hour is not None else "unknown")
    return len(segments)


def metadata_prefilter(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    genre: Optional[str] = None,
    db_path: str = SQLITE_DB_PATH,
) -> list[int]:
    """Query SQLite for faiss_ids matching an optional date range and optional genre.

    Args:
        date_from: Optional start date (YYYY-MM-DD), inclusive.
        date_to: Optional end date (YYYY-MM-DD), inclusive.
        genre: Optional genre label to filter on (case- and whitespace-insensitive).
        db_path: Path to the SQLite database.

    Returns:
        List of faiss_ids matching the criteria.
    """
    db = _get_db(db_path)
    conditions = []
    params = []
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    if genre:
        conditions.append("LOWER(TRIM(genre)) = LOWER(TRIM(?))")
        params.append(genre)

    where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(f"SELECT faiss_id FROM segments{where_sql}", params).fetchall()
    db.close()
    return [row["faiss_id"] for row in rows]


def _filtered_search(index: faiss.Index, qvec: np.ndarray, faiss_ids: list[int], top_k: int):
    """Exact top-k of ``qvec`` restricted to ``faiss_ids``. Returns (scores, ids), each of shape (1, n).

    Uses an IDSelector with the base ``faiss.SearchParameters`` (the right class for a flat index;
    ``SearchParametersIVF`` is for IVF indexes). If that search is unavailable it scores the candidate
    vectors directly, so the answer is still the exact top-k of the candidates. Candidate ids that are
    not in the index and duplicate ids are ignored; fewer than ``top_k`` candidates returns all of them.
    """
    cand = np.unique(np.asarray(faiss_ids, dtype=np.int64))
    cand = cand[(cand >= 0) & (cand < index.ntotal)]
    k = min(top_k, len(cand))
    if k == 0:
        return np.empty((1, 0), dtype=np.float32), np.empty((1, 0), dtype=np.int64)
    try:
        params = faiss.SearchParameters()
        sel = faiss.IDSelectorBatch(cand)
        params.sel = sel
        scores, ids = index.search(qvec, k, params=params)
        return scores, ids
    except Exception:
        logger.warning("FAISS selector search unavailable; scoring %d candidates directly", len(cand))
        vecs = np.vstack([index.reconstruct(int(i)) for i in cand])
        sc = vecs @ qvec[0]
        order = np.argsort(-sc, kind="stable")[:k]
        return sc[order].reshape(1, -1).astype(np.float32), cand[order].reshape(1, -1)


def semantic_search(
    query_embedding: np.ndarray,
    faiss_ids: Optional[list[int]] = None,
    top_k: int = 5,
    index_path: str = FAISS_INDEX_PATH,
    db_path: str = SQLITE_DB_PATH,
) -> list[dict]:
    """Search the FAISS index, optionally filtering to a subset of IDs.

    Args:
        query_embedding: Query vector of shape (384,).
        faiss_ids: If provided, restrict search to these FAISS IDs only.
        top_k: Number of results to return.
        index_path: Path to the FAISS index file.
        db_path: Path to the SQLite database.

    Returns:
        List of dicts with keys: text, genre, date, hour (0-23 or None), hour_flag, score, faiss_id.
    """
    index = _load_or_create_index(index_path)
    if index.ntotal == 0:
        return []

    # Normalise query
    qvec = query_embedding.reshape(1, -1).astype(np.float32)
    faiss.normalize_L2(qvec)

    if faiss_ids is not None:
        if len(faiss_ids) == 0:
            return []
        scores, ids = _filtered_search(index, qvec, faiss_ids, top_k)
    else:
        scores, ids = index.search(qvec, min(top_k, index.ntotal))

    # Fetch metadata from SQLite
    db = _get_db(db_path)
    results = []
    for score, fid in zip(scores[0], ids[0]):
        if fid < 0:
            continue
        row = db.execute(
            "SELECT text, genre, date, hour, hour_flag, split, source_file, audio_start, audio_end FROM segments WHERE faiss_id = ?", (int(fid),)
        ).fetchone()
        if row:
            source_file = row["source_file"] or ""
            _, has_audio = resolve_audio_path(source_file)
            results.append({
                "text": row["text"],
                "genre": row["genre"],
                "date": row["date"],
                "hour": row["hour"],
                "hour_flag": row["hour_flag"] or "",
                "split": row["split"],
                "score": float(score),
                "faiss_id": int(fid),
                "source_file": source_file,
                "has_audio": bool(has_audio),
                "audio_start": row["audio_start"] if "audio_start" in row.keys() else None,
                "audio_end": row["audio_end"] if "audio_end" in row.keys() else None,
            })
    db.close()
    return results


def get_all_embeddings(index_path: str = FAISS_INDEX_PATH) -> Optional[np.ndarray]:
    """Return all stored embeddings as a numpy matrix.

    Used by the MMR novelty filter in nlp_pipeline at startup.

    Returns:
        Numpy array of shape (N, 384), or None if no index exists.
    """
    if not os.path.isfile(index_path):
        return None
    index = _load_or_create_index(index_path)
    if index.ntotal == 0:
        return None
    return faiss.rev_swig_ptr(index.get_xb(), index.ntotal * EMBEDDING_DIM).reshape(index.ntotal, EMBEDDING_DIM).copy()


def get_all_texts(db_path: str = SQLITE_DB_PATH) -> list[str]:
    """Return all stored segment texts ordered by faiss_id."""
    if not os.path.isfile(db_path):
        return []
    db = _get_db(db_path)
    rows = db.execute("SELECT text FROM segments ORDER BY faiss_id ASC").fetchall()
    db.close()
    return [r["text"] for r in rows]


def get_stats(
    index_path: str = FAISS_INDEX_PATH,
    db_path: str = SQLITE_DB_PATH,
) -> dict:
    """Return summary statistics about the vector store.

    Returns:
        Dict with total_segments, genres breakdown, and date_range.
    """
    index = _load_or_create_index(index_path)
    db = _get_db(db_path)

    total = index.ntotal
    genre_rows = db.execute("SELECT genre, COUNT(*) as cnt FROM segments GROUP BY genre").fetchall()
    genres = {row["genre"]: row["cnt"] for row in genre_rows}

    date_row = db.execute("SELECT MIN(date) as min_d, MAX(date) as max_d FROM segments").fetchone()
    date_range = {"from": date_row["min_d"], "to": date_row["max_d"]} if date_row else {}

    db.close()
    return {"total_segments": total, "genres": genres, "date_range": date_range}


def get_date_range(db_path: str = SQLITE_DB_PATH) -> tuple[Optional[str], Optional[str]]:
    """Return (MIN(date), MAX(date)) from the segments table. Returns (None, None) on empty DB."""
    if not os.path.isfile(db_path):
        return (None, None)
    db = _get_db(db_path)
    row = db.execute("SELECT MIN(date) as min_d, MAX(date) as max_d FROM segments").fetchone()
    db.close()
    if row and row["min_d"] is not None and row["max_d"] is not None:
        return (row["min_d"], row["max_d"])
    return (None, None)


_metadata_audio_cache: Optional[dict[str, str]] = None
_metadata_cache_mtime: float = 0.0


def _load_metadata_audio_map(metadata_csv: str = "output/metadata.csv") -> dict[str, str]:
    """Load transcript_file -> audio_file mapping from metadata.csv."""
    global _metadata_audio_cache, _metadata_cache_mtime
    if not os.path.isfile(metadata_csv):
        return {}
    try:
        mtime = os.path.getmtime(metadata_csv)
        if _metadata_audio_cache is not None and mtime == _metadata_cache_mtime:
            return _metadata_audio_cache
        mapping: dict[str, str] = {}
        with open(metadata_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t_file = (row.get("transcript_file") or "").strip().replace("\\", "/")
                a_file = (row.get("audio_file") or "").strip().replace("\\", "/")
                if t_file and a_file:
                    mapping[t_file] = a_file
        _metadata_audio_cache = mapping
        _metadata_cache_mtime = mtime
        return mapping
    except Exception:
        return {}


def resolve_audio_path(
    source_file: str,
    out_dir: str = "output",
    metadata_csv: str = "output/metadata.csv",
) -> tuple[str, bool]:
    """Resolve transcript source_file to its corresponding audio file path.

    Prefers 'audio_file' from metadata_csv if specified and non-empty;
    otherwise derives path by swapping leading 'text/' -> 'audio/' and '.txt' -> '.mp3'.

    Returns:
        (resolved_relpath, exists_on_disk)
    """
    if not source_file:
        return ("", False)

    norm_source = source_file.strip().replace("\\", "/")

    # Check metadata CSV first
    audio_rel = ""
    meta_map = _load_metadata_audio_map(metadata_csv)
    if norm_source in meta_map:
        audio_rel = meta_map[norm_source]

    if not audio_rel:
        # Derive from source_file
        derived = norm_source
        if derived.startswith("text/"):
            derived = "audio/" + derived[5:]
        if derived.endswith(".txt"):
            derived = derived[:-4] + ".mp3"
        audio_rel = derived

    full_path = os.path.normpath(os.path.join(out_dir, audio_rel)).replace("\\", "/")
    return (full_path, os.path.isfile(full_path))


def wipe(index_path: str = FAISS_INDEX_PATH, db_path: str = SQLITE_DB_PATH) -> None:
    """Delete the FAISS index and SQLite DB for full re-indexing."""
    for p in (index_path, db_path):
        if os.path.isfile(p):
            os.remove(p)
            logger.info("Removed %s", p)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point: print vector store stats."""
    parser = argparse.ArgumentParser(description="FAISS + SQLite vector store management.")
    parser.add_argument("--stats", action="store_true", help="Print segment count, genres, date range")
    args = parser.parse_args()

    if args.stats:
        stats = get_stats()
        print(json.dumps(stats, indent=2, default=str))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
