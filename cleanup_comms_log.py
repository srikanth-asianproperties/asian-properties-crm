"""
cleanup_comms_log.py  --  One-time cleanup script
Shows all test/preview entries in comms_log and deletes them
safely before Job D goes live.

Run from C:\CLS:
  python cleanup_comms_log.py          # preview what will be deleted
  python cleanup_comms_log.py --delete # actually delete
"""

import sys, os
BASE_DIR = "C:\\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db

def main():
    delete_mode = "--delete" in sys.argv

    cls_db.init_db()
    conn = cls_db._connect()

    print("=" * 60)
    print(" comms_log Cleanup")
    print(" Mode: " + ("DELETE" if delete_mode else "PREVIEW (run with --delete to actually delete)"))
    print("=" * 60)

    # ── Show full current state ──
    total = conn.execute("SELECT COUNT(*) c FROM comms_log").fetchone()["c"]
    print("\nTotal rows in comms_log: " + str(total))

    if total == 0:
        print("\ncomms_log is already empty. Nothing to clean.")
        print("Job D is ready to go live.")
        conn.close()
        return

    # ── Break down by type ──
    print("\nBreakdown:")
    rows = conn.execute("""
        SELECT
            brevo_message_id,
            status,
            sender_email,
            COUNT(*)         as count,
            MIN(sent_at)     as earliest,
            MAX(sent_at)     as latest
        FROM comms_log
        GROUP BY brevo_message_id, status, sender_email
        ORDER BY latest DESC
    """).fetchall()

    for r in rows:
        mid = str(r["brevo_message_id"] or "")[:30]
        print("  " + r["status"].ljust(8) +
              " | " + mid.ljust(30) +
              " | count=" + str(r["count"]).rjust(4) +
              " | " + str(r["earliest"]) + " -> " + str(r["latest"]))

    # ── Identify test entries ──
    # Test entries are:
    #   1. brevo_message_id = 'dry_run'  (from cls_email_drip --dry-run)
    #   2. Any row with status = 'sent' written before today
    #      (all sends before today are previews/tests, not real leads)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    test_rows = conn.execute("""
        SELECT COUNT(*) c FROM comms_log
        WHERE brevo_message_id = 'dry_run'
           OR DATE(sent_at) < ?
    """, (today,)).fetchone()["c"]

    real_rows = total - test_rows

    print("\nTest/preview entries to delete: " + str(test_rows))
    print("Real lead entries to keep:      " + str(real_rows))

    if test_rows == 0:
        print("\nNo test entries found. comms_log is clean.")
        conn.close()
        return

    if not delete_mode:
        print("\nRun with --delete to remove the " + str(test_rows) + " test entries:")
        print("  python cleanup_comms_log.py --delete")
        conn.close()
        return

    # ── Delete ──
    conn.execute("""
        DELETE FROM comms_log
        WHERE brevo_message_id = 'dry_run'
           OR DATE(sent_at) < ?
    """, (today,))
    conn.commit()

    remaining = conn.execute("SELECT COUNT(*) c FROM comms_log").fetchone()["c"]
    print("\nDeleted " + str(test_rows) + " test entries.")
    print("Remaining rows: " + str(remaining))

    if remaining == 0:
        print("\ncomms_log is clean. Job D is ready to go live.")
    else:
        print("\nRemaining entries are real lead sends — kept intact.")

    conn.close()

if __name__ == "__main__":
    main()
