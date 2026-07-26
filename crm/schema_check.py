#!/usr/bin/env python
"""
=============================================================
schema_check.py — CLS/CRM Live Schema Diagnostic (read-only)
=============================================================
Version : 1.1
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.1 (July 2026) — CLS1/CLS2 database split support. DB_FILE is no
  longer hardcoded to cls.db — it now takes an optional command-line
  argument (filename, resolved against C:\\CLS), defaulting to CLS1.db.

WHAT THIS DOES
--------------
Connects to the LIVE database (CLS1.db by default, or whatever file
you pass as an argument) and reports:
  - every table that currently exists
  - every column in each table (name + type)
  - a row count per table
  - whether the 'users' table (needed for CRM v0.1 login) exists yet

This script NEVER writes anything — not even init_db(). It exists so
you can see the real, current state of a CLS database before running
any migration, per the "verify the live version before editing" rule.
Safe to run any time, any number of times, including while Jobs A-D
are running (WAL mode allows concurrent reads).

IMPORTANT — do NOT run cls_db.py directly against a live DB
--------------------------------------------------------------
`python cls_db.py` runs that file's built-in self-test, which INSERTS
test rows (TEST_LG_1001, SD_555, SD_999, TEST_LG_OPTOUT) into whatever
database it's pointed at. That's fine on a throwaway DB, but you do
not want those rows in your real CLS1.db/CLS2.db. This script is the
safe way to look at the live schema instead.

USAGE
-----
  python schema_check.py            (checks CLS1.db)
  python schema_check.py CLS2.db    (checks CLS2.db)
=============================================================
"""

import os
import sys
import sqlite3

BASE_DIR = r"C:\CLS"
DB_NAME  = sys.argv[1] if len(sys.argv) > 1 else "CLS1.db"
DB_FILE  = os.path.join(BASE_DIR, DB_NAME)


def _p(msg=""):
    # Guard against pythonw.exe setting sys.stdout = None (Windows Task
    # Scheduler quirk) — harmless no-op if stdout isn't available.
    try:
        print(msg)
    except Exception:
        pass


def main():
    if not os.path.exists(DB_FILE):
        _p(f"[FAIL] Database not found at {DB_FILE}")
        _p("       Check the path/filename, or run this on the machine where CLS lives.")
        return

    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row

    _p("=" * 60)
    _p(" CLS/CRM SCHEMA CHECK (read-only)")
    _p(f" DB: {DB_FILE}")
    _p("=" * 60)

    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    ).fetchall()]

    if not tables:
        _p("[FAIL] No tables found — is this the right cls.db?")
        conn.close()
        return

    for t in tables:
        cols = conn.execute(f"PRAGMA table_info({t});").fetchall()
        count = conn.execute(f"SELECT COUNT(*) c FROM {t};").fetchone()["c"]
        _p(f"\n[TABLE] {t}  ({count} rows)")
        for c in cols:
            _p(f"    - {c['name']:<20s} {c['type']}")

    _p("\n" + "-" * 60)
    if "users" in tables:
        user_count = conn.execute("SELECT COUNT(*) c FROM users;").fetchone()["c"]
        _p(f"[OK]   'users' table already exists ({user_count} user(s)).")
    else:
        _p("[INFO] 'users' table does NOT exist yet.")
        _p("       It's created automatically the first time either")
        _p("       `python app.py` or `python create_admin.py` runs (both")
        _p("       call cls_db.init_db(), which only CREATEs missing")
        _p("       tables — it never touches existing data).")
    _p("-" * 60)

    conn.close()


if __name__ == "__main__":
    main()
