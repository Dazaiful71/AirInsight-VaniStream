"""A2 migration: make segments.hour mean 0-23 for every row (batch rows used to store HHMM, e.g. 800).

The stored number is NOT trusted (batch 0 meant "no time", live 0 meant midnight, and small HHMM such as 5 for
00:05 collides with live hour 5). The hour is re-derived from the source_file name with the same rule as
ingest_pipeline._extract_hour_and_flag: first standalone HHMM -> HHMM // 100; no valid time -> NULL plus
hour_flag ('no_time_in_filename' / 'invalid_hhmm'). Idempotent. Adds the hour_flag column if missing.

It refuses to run on the project's own store; work on a COPY:
  copy news_store.db to a temp folder, then
  .venv_gpu/Scripts/python.exe migrate_hour_to_0_23.py --db <copy> [--dry-run]
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter

from ingest_pipeline import _extract_hour_and_flag

PROTECTED = os.path.abspath("news_store.db")


def migrate(db_path: str, dry_run: bool = False) -> dict:
    if os.path.abspath(db_path) == PROTECTED:
        raise SystemExit("refusing to migrate the project's own news_store.db; run it on a copy")
    if not os.path.isfile(db_path):
        raise SystemExit(f"database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(segments)")]
    has_flag = "hour_flag" in cols
    if not has_flag and not dry_run:
        conn.execute("ALTER TABLE segments ADD COLUMN hour_flag TEXT")
        has_flag = True
    rows = conn.execute("SELECT id, hour, source_file" + (", hour_flag" if has_flag else "") + " FROM segments").fetchall()
    changed, kinds, null_after = 0, Counter(), 0
    for r in rows:
        new_hour, flag = _extract_hour_and_flag(os.path.basename(r["source_file"] or ""))
        null_after += new_hour is None
        old_flag = (r["hour_flag"] or "") if has_flag else ""
        if new_hour != r["hour"] or flag != old_flag:
            changed += 1
            kinds["now NULL (%s)" % flag if new_hour is None else "now 0-23"] += 1
            if not dry_run:
                conn.execute("UPDATE segments SET hour = ?, hour_flag = ? WHERE id = ?", (new_hour, flag, r["id"]))
    if not dry_run:
        conn.execute("UPDATE segments SET hour_flag = '' WHERE hour_flag IS NULL AND hour IS NOT NULL")
        conn.commit()
    conn.close()
    return {"rows": len(rows), "changed": changed, "changes": dict(kinds), "null_hours_after": null_after,
            "dry_run": dry_run}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="path to a COPY of news_store.db")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(migrate(a.db, a.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
