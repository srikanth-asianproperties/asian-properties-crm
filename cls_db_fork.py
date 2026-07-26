"""
=============================================================
cls_db_fork.py  —  CLS1/CLS2 One-Time Migration Helper
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

PURPOSE
-------
One-time-use script that forks the single existing C:\\CLS\\cls.db into
CLS1.db ("our own CRM" — fed by Job A + the CRM app going forward) and
CLS2.db (the Sell.do mirror — fed only by Job B going forward). Run
this ONCE, manually, as the first step of the CLS1/CLS2 database split
migration — see cls_db.py v2.23 for the rest of the split.

WHAT IT DOES, IN ORDER
-----------------------
  1. Prints a warning asking YOU to confirm, manually, that every CLS
     Task Scheduler task and the Waitress CRM server are stopped. This
     is a best-effort reminder only — this script does not (and, from
     plain Python, reliably cannot) detect running Task Scheduler jobs
     or Windows services itself.
  2. Opens the existing cls.db and runs PRAGMA wal_checkpoint(FULL) —
     flushes the WAL file into the main db file, so the copies below
     are complete and consistent.
  3. Copies cls.db -> CLS1.db
  4. Copies cls.db -> CLS2.db
  5. Renames the original cls.db -> cls.db.pre_split_backup (never
     deletes it — an obvious rollback point).
  6. Prints final file sizes of all three files for visual confirmation.

Refuses to run if CLS1.db or CLS2.db already exist (won't silently
overwrite a prior run). Read-only against the original beyond the
checkpoint pragma. Does not touch app.py, any job script, or Task
Scheduler.

RUN
---
  python cls_db_fork.py
=============================================================
"""

import os
import sqlite3
import shutil

BASE_DIR    = r"C:\CLS"
SOURCE_DB   = os.path.join(BASE_DIR, "cls.db")
CLS1_PATH   = os.path.join(BASE_DIR, "CLS1.db")
CLS2_PATH   = os.path.join(BASE_DIR, "CLS2.db")
BACKUP_PATH = os.path.join(BASE_DIR, "cls.db.pre_split_backup")


def _p(msg=""):
    try:
        print(msg)
    except Exception:
        pass


def _size_mb(path):
    return os.path.getsize(path) / (1024 * 1024)


def main():
    _p("=" * 60)
    _p(" CLS1/CLS2 DATABASE FORK — one-time migration helper")
    _p("=" * 60)
    _p("")
    _p("BEFORE CONTINUING, manually confirm:")
    _p("  - All CLS Task Scheduler tasks (Jobs A/B/C/D) are STOPPED/disabled.")
    _p("  - The CRM app (Waitress / python app.py) is STOPPED.")
    _p("This script cannot verify that for you — it only checks file state below.")
    _p("")

    if not os.path.exists(SOURCE_DB):
        _p(f"[FAIL] {SOURCE_DB} not found. Nothing to fork.")
        return

    if os.path.exists(CLS1_PATH) or os.path.exists(CLS2_PATH):
        _p("[FAIL] CLS1.db and/or CLS2.db already exist in C:\\CLS.")
        _p("       Refusing to overwrite — this looks like the fork already ran.")
        _p("       Remove/rename them yourself first if you really want to re-run this.")
        return

    _p(f"Source: {SOURCE_DB}  ({_size_mb(SOURCE_DB):.2f} MB)")

    _p("")
    _p("Step 1/4 — Checkpointing WAL into the main db file...")
    conn = sqlite3.connect(SOURCE_DB, timeout=30)
    try:
        conn.execute("PRAGMA wal_checkpoint(FULL);")
    finally:
        conn.close()
    _p("  Done.")

    _p("")
    _p(f"Step 2/4 — Copying cls.db -> CLS1.db...")
    shutil.copy2(SOURCE_DB, CLS1_PATH)
    _p("  Done.")

    _p(f"Step 3/4 — Copying cls.db -> CLS2.db...")
    shutil.copy2(SOURCE_DB, CLS2_PATH)
    _p("  Done.")

    _p("")
    _p(f"Step 4/4 — Renaming original cls.db -> cls.db.pre_split_backup...")
    os.rename(SOURCE_DB, BACKUP_PATH)
    _p("  Done. Original is NOT deleted — it's your rollback point.")

    _p("")
    _p("=" * 60)
    _p(" FORK COMPLETE — confirm these three sizes match before proceeding:")
    _p("=" * 60)
    _p(f"  CLS1.db                 {_size_mb(CLS1_PATH):.2f} MB")
    _p(f"  CLS2.db                 {_size_mb(CLS2_PATH):.2f} MB")
    _p(f"  cls.db.pre_split_backup {_size_mb(BACKUP_PATH):.2f} MB")
    _p("=" * 60)


if __name__ == "__main__":
    main()
