"""A2: hour is 0-23 everywhere; missing hours stay empty (NULL + flag), never 0."""
import sqlite3

import numpy as np
import pytest

import ingest_pipeline
import migrate_hour_to_0_23
import vector_store


@pytest.fixture(autouse=True)
def _no_output_dir(monkeypatch):
    monkeypatch.setattr(vector_store, "resolve_audio_path", lambda *a, **k: ("", False))


def _seg(text, i):
    v = np.zeros(vector_store.EMBEDDING_DIM, dtype=np.float32)
    v[i % vector_store.EMBEDDING_DIM] = 1.0
    return {"text": text, "genre": "Other", "genre_confidence": 0.5, "embedding": v}


@pytest.mark.parametrize("name,hour,flag", [
    ("English-0800-0810-1.txt", 8, ""),
    ("English-0005-0010-7.txt", 0, ""),
    ("English-2305-2310-18.txt", 23, ""),
    ("English1300.txt", 13, ""),
    ("Live-English-1435-0003.txt", 14, ""),
    ("morninng.txt", None, "no_time_in_filename"),
    ("Midday-News.txt", None, "no_time_in_filename"),
    ("English-2575-0010.txt", None, "invalid_hhmm"),
    ("English-1260-1270.txt", None, "invalid_hhmm"),
])
def test_extract_hour(name, hour, flag):
    assert ingest_pipeline._extract_hour_and_flag(name) == (hour, flag)
    assert ingest_pipeline._extract_hour(name) == hour


def test_extract_hour_matches_scraper_rule():
    from air_bulletins_scraper import parse_hour_from_url
    for name in ["English-0800-0810-1.mp3", "English-0005-0010-7.mp3", "morninng.mp3", "English-2575-0010.mp3",
                 "English1300.mp3", "2005ee-5.mp3", "Midday-News.mp3"]:
        _hhmm, h, _ = parse_hour_from_url(name)
        assert ingest_pipeline._extract_hour(name.replace(".mp3", ".txt")) == h, name


def test_missing_hours_stay_empty_in_the_store(tmp_path):
    ip, dp = str(tmp_path / "i.bin"), str(tmp_path / "s.db")
    h, flag = ingest_pipeline._extract_hour_and_flag("morninng.txt")
    vector_store.add_segments([_seg("a", 1)], "2026-01-01", h, "text/morninng.txt", ip, dp, hour_flag=flag)
    vector_store.add_segments([_seg("b", 2)], "2026-01-01", 0, "text/live.txt", ip, dp)   # a real midnight hour
    rows = sqlite3.connect(dp).execute("SELECT text, hour, hour_flag FROM segments ORDER BY text").fetchall()
    assert rows == [("a", None, "no_time_in_filename"), ("b", 0, "")]
    got = vector_store.semantic_search(_seg("a", 1)["embedding"], top_k=2, index_path=ip, db_path=dp)
    by_text = {r["text"]: r for r in got}
    assert by_text["a"]["hour"] is None and by_text["a"]["hour_flag"] == "no_time_in_filename"
    assert by_text["b"]["hour"] == 0


@pytest.mark.parametrize("bad", [800, 1305, 24, -1])
def test_add_segments_rejects_non_0_23_hours(tmp_path, bad):
    with pytest.raises(ValueError):
        vector_store.add_segments([_seg("x", 1)], "2026-01-01", bad, "t.txt", str(tmp_path / "i.bin"), str(tmp_path / "s.db"))


def test_mixed_batch_and_live_rows_sort_by_hour(tmp_path):
    """Batch rows (formerly HHMM) and live rows (formerly 0-23) end up in true chronological order."""
    ip, dp = str(tmp_path / "i.bin"), str(tmp_path / "s.db")
    items = [("batch-1305", "English-1305-1310-1.txt"), ("live-09", "Live-English-0915-0001.txt"),
             ("batch-0005", "English-0005-0010-3.txt"), ("batch-2305", "English-2305-2310-3.txt"),
             ("live-14", "Live-English-1435-0002.txt"), ("batch-nohour", "morninng.txt")]
    for n, (text, fname) in enumerate(items):
        h, flag = ingest_pipeline._extract_hour_and_flag(fname)
        vector_store.add_segments([_seg(text, n)], "2026-01-01", h, "text/" + fname, ip, dp, hour_flag=flag)
    q = np.ones(vector_store.EMBEDDING_DIM, dtype=np.float32)
    srcs = vector_store.semantic_search(q, top_k=10, index_path=ip, db_path=dp)
    assert len(srcs) == 6
    # same sort key rag_engine uses
    srcs.sort(key=lambda s: (s.get("date", ""), s.get("hour") is None, s.get("hour") or 0))
    assert [s["text"] for s in srcs] == ["batch-0005", "live-09", "batch-1305", "live-14", "batch-2305", "batch-nohour"]
    assert [s["hour"] for s in srcs] == [0, 9, 13, 14, 23, None]


def _old_schema_db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE segments (id INTEGER PRIMARY KEY AUTOINCREMENT, faiss_id INTEGER UNIQUE, text TEXT NOT NULL, genre TEXT, "
              "genre_confidence REAL, date TEXT, hour INTEGER, source_file TEXT, indexed_at TEXT, audio_start REAL, audio_end REAL)")
    rows = [  # (stored hour under the OLD code, source_file)
        (800, "text/2026-05-01/English-0800-0810-1.txt"),        # batch HHMM
        (5, "text/2026-05-01/English-0005-0010-7.txt"),          # batch 00:05 stored as 5 (collides with live hour 5)
        (0, "text/2026-05-01/morninng.txt"),                      # batch, no time -> stored 0
        (14, "text/2026-05-02/Live-English-1435-0003.txt"),       # live, already 0-23
        (0, "text/2026-05-02/Live-English-0010-0002.txt"),        # live, real midnight hour
        (2305, "text/2026-05-01/English-2305-2310-3.txt"),
    ]
    for n, (h, f) in enumerate(rows):
        c.execute("INSERT INTO segments (faiss_id, text, genre, date, hour, source_file) VALUES (?,?,?,?,?,?)",
                  (n, f"t{n}", "Other", "2026-05-01", h, f))
    c.commit()
    c.close()


def test_migration_on_a_copy(tmp_path):
    db = str(tmp_path / "copy.db")
    _old_schema_db(db)
    s = migrate_hour_to_0_23.migrate(db)
    assert s["rows"] == 6
    got = sqlite3.connect(db).execute("SELECT hour, hour_flag FROM segments ORDER BY id").fetchall()
    assert got == [(8, ""), (0, ""), (None, "no_time_in_filename"), (14, ""), (0, ""), (23, "")]
    again = migrate_hour_to_0_23.migrate(db)          # idempotent
    assert again["changed"] == 0


def test_migration_dry_run_changes_nothing(tmp_path):
    db = str(tmp_path / "copy.db")
    _old_schema_db(db)
    migrate_hour_to_0_23.migrate(db, dry_run=True)
    assert [r[0] for r in sqlite3.connect(db).execute("SELECT hour FROM segments ORDER BY id")] == [800, 5, 0, 14, 0, 2305]


def test_migration_refuses_the_project_store():
    with pytest.raises(SystemExit):
        migrate_hour_to_0_23.migrate("news_store.db")
