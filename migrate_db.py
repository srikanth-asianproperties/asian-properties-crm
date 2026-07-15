"""
migrate_db.py  —  CLS Database Migration
=========================================
Run ONCE on your live C:\CLS\cls.db.

Adds four new columns to the `leads` table:
  1. email_bounced        INTEGER  DEFAULT 0   — 1 = Brevo confirmed bounce
  2. email_bounced_type   TEXT                 — 'hard' or 'soft'
  3. opted_out            INTEGER  DEFAULT 0   — 1 = lead replied STOP / clicked unsubscribe
  4. opted_out_at         TEXT                 — ISO timestamp when opt-out was recorded

Safe to run multiple times — skips any column that already exists.
Does NOT touch any existing data.
"""

import sqlite3
import os
import sys
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────
DB_PATH = r"C:\CLS\cls.db"
# ──────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())

def run_migration():
    if not os.path.exists(DB_PATH):
        log(f"ERROR: cls.db not found at {DB_PATH}")
        log("Check the DB_PATH constant at the top of this script.")
        sys.exit(1)

    log(f"Opening database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # ── Verify the leads table exists ─────────────────────────
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leads'")
    if not cur.fetchone():
        log("ERROR: 'leads' table not found. Wrong database?")
        conn.close()
        sys.exit(1)

    # ── Current row count (sanity check) ──────────────────────
    cur.execute("SELECT COUNT(*) FROM leads")
    lead_count = cur.fetchone()[0]
    log(f"leads table found — {lead_count} rows present. No rows will be changed.")

    # ── Migrations to apply ───────────────────────────────────
    migrations = [
        {
            "column"  : "email_bounced",
            "sql"     : "ALTER TABLE leads ADD COLUMN email_bounced INTEGER DEFAULT 0",
            "purpose" : "Flag for Brevo-confirmed email bounces (0=ok, 1=bounced)"
        },
        {
            "column"  : "email_bounced_type",
            "sql"     : "ALTER TABLE leads ADD COLUMN email_bounced_type TEXT",
            "purpose" : "Bounce type: 'hard' (permanent bad address) or 'soft' (temporary)"
        },
        {
            "column"  : "opted_out",
            "sql"     : "ALTER TABLE leads ADD COLUMN opted_out INTEGER DEFAULT 0",
            "purpose" : "Opt-out flag — 1 = lead replied STOP or clicked Brevo unsubscribe"
        },
        {
            "column"  : "opted_out_at",
            "sql"     : "ALTER TABLE leads ADD COLUMN opted_out_at TEXT",
            "purpose" : "ISO timestamp of when opt-out was recorded"
        },
    ]

    applied  = 0
    skipped  = 0

    log("-" * 55)
    for m in migrations:
        col = m["column"]
        if column_exists(cur, "leads", col):
            log(f"SKIP   — column '{col}' already exists")
            skipped += 1
        else:
            cur.execute(m["sql"])
            conn.commit()
            log(f"ADDED  — column '{col}'  |  {m['purpose']}")
            applied += 1

    log("-" * 55)

    # ── Final verification ────────────────────────────────────
    log("Verifying final schema of 'leads' table:")
    cur.execute("PRAGMA table_info(leads)")
    cols = cur.fetchall()

    new_cols = {m["column"] for m in migrations}
    for c in cols:
        marker = "  <-- NEW" if c[1] in new_cols else ""
        log(f"   col {c[0]:>3}  {c[1]:<30} {c[2]}{marker}")

    log("-" * 55)
    log(f"Migration complete.  Applied: {applied}   Skipped (already existed): {skipped}")
    log(f"Row count after migration: {lead_count}  (unchanged — no data was modified)")
    log("You can now replace cls_email_drip.py with the updated version.")

    conn.close()

if __name__ == "__main__":
    run_migration()
