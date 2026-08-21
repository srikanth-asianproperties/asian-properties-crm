"""
=============================================================
cls_notifications_poller.py  —  CLS Notifications v1.0 Poller
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.0 (2026-08-21) — Initial version, Notifications v1.0 build session.
  Same shape/header/changelog convention as cls_weekend_visits_report.py.
  Runs every 15 min via Task Scheduler -> run_cls_notifications_poller.bat
  (pythonw.exe, guarded stdout, UTF-8-safe logging — same posture as
  every other job in this codebase).

  Ops-only script, outside the Job A-D pipeline naming (not "Job E" in
  job_results.txt — same convention cls_weekend_visits_report.py and
  cls_monday_weekly_report.py already use). Targets CLS1.db via
  CLS_DB_PATH (set by its .bat wrapper) — the same database every other
  live CRM write-path uses.

WHAT THIS SCRIPT DOES
----------------------
Only handles the 5 due/overdue event types in cls_db.NOTIFICATION_TRIGGERS
(followup_due, followup_overdue_1d, visit_tomorrow, visit_due_now,
visit_overdue_1d). The other 3 event types (new_enquiry, lead_reengaged,
lead_reassigned) fire INSTANTLY from hooks inside cls_db.upsert_meta_lead()
/ reassign_lead_owner() (v2.72) — this poller never touches those.

For each (event_type -> (source_table, date_column, offset_hours,
extra_where)) entry, finds rows whose date_column has just crossed the
event's trigger point, then calls cls_db.insert_notification() (idempotent
-- a row is never double-notified even if the window logic ever double-
catches it) + cls_db.send_fcm_push() (a guarded no-op today, live the
moment Firebase creds exist) for each match.

TRIGGER-WINDOW MATH (clarifies a genuine ambiguity in the original
event_type -> offset_hours design, resolved by checking which reading
gives the correct real-world behavior for all 5 events, not just
picking one arbitrarily):
  target = now + offset_hours
  window = (target - POLL_WINDOW_MINUTES, target]
  MATCH:  scheduled_at falls inside that window.
Checked against all 5 events:
  - visit_tomorrow   (offset=+24) -> target = now+24h -> catches visits
    scheduled ~24h from now. Correct ("tomorrow").
  - visit_due_now / followup_due (offset=0) -> target = now -> catches
    rows whose scheduled_at is right now. Correct ("due now"/"due today").
  - visit_overdue_1d / followup_overdue_1d (offset=-24) -> target =
    now-24h -> catches rows scheduled ~24h ago, still open. Correct
    ("overdue by 1 day").
The window's right edge is inclusive, left edge exclusive, sized to
POLL_WINDOW_MINUTES (matching the 15-min Task Scheduler cadence) so a
row is caught by exactly one run, never zero, never two.

USAGE
-----
  python cls_notifications_poller.py             # normal run
  python cls_notifications_poller.py --dry-run   # logs what WOULD be
                                                    sent, writes/pushes
                                                    NOTHING — the
                                                    "dry-run against a
                                                    copy of cls.db
                                                    before registering
                                                    the Task Scheduler
                                                    trigger" step
  python cls_notifications_poller.py --selftest  # config sanity only,
                                                    no DB query, no send
"""

import os
import sys
from datetime import datetime, timedelta

BASE_DIR = r"D:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db

LOG_FILE = os.path.join(BASE_DIR, "cls_notifications_poller_log.txt")

# Matches the Task Scheduler cadence (every 15 min) — see module docstring.
POLL_WINDOW_MINUTES = 15

# pythonw.exe has no console — sys.stdout is None. Guard before reconfiguring.
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] {message}"
    try:
        if sys.stdout is not None:
            print(entry)
    except Exception:
        pass
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# TRIGGER SCAN
# ─────────────────────────────────────────────────────────────

def _window_for(offset_hours, now):
    """(window_start, window_end] for one NOTIFICATION_TRIGGERS entry —
    see module docstring TRIGGER-WINDOW MATH for the derivation."""
    target = now + timedelta(hours=offset_hours)
    window_start = target - timedelta(minutes=POLL_WINDOW_MINUTES)
    return window_start, target


def find_due_rows(event_type, now):
    """
    Returns a list of dicts (cls_id, full_name, lead_owner, scheduled_at)
    for every row of event_type's source_table that just crossed its
    trigger window. Read-only — never writes.
    """
    source_table, date_column, offset_hours, extra_where = cls_db.NOTIFICATION_TRIGGERS[event_type]
    window_start, window_end = _window_for(offset_hours, now)

    conn = cls_db._connect()
    try:
        sql = f"""
            SELECT t.cls_id AS cls_id, l.full_name AS full_name,
                   l.lead_owner AS lead_owner, t.{date_column} AS scheduled_at
            FROM {source_table} t
            JOIN leads l ON l.cls_id = t.cls_id
            WHERE t.{date_column} > ? AND t.{date_column} <= ?
              AND {extra_where}
        """
        rows = conn.execute(
            sql,
            (window_start.strftime("%Y-%m-%d %H:%M:%S"), window_end.strftime("%Y-%m-%d %H:%M:%S"))
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def process_event_type(event_type, now, dry_run=False):
    """
    Scans one event_type's due rows and notifies each lead's owner.
    Returns (matched_count, notified_count) — matched can exceed
    notified when a lead's owner has no linked login (skipped, logged,
    never a hard failure — one unresolvable owner must not block every
    other row in this run).
    """
    rows = find_due_rows(event_type, now)
    message_template = cls_db.NOTIFICATION_EVENTS[event_type]
    notified = 0

    for row in rows:
        full_name = row["full_name"] or "(no name)"
        message = message_template.format(full_name=full_name)
        user_id = cls_db.resolve_user_id_from_owner_name(row["lead_owner"])
        if not user_id:
            log(f"{event_type}: cls_id={row['cls_id']} owner={row['lead_owner']!r} "
                f"has no linked login — skipped.", "WARNING")
            continue

        if dry_run:
            log(f"[DRY-RUN] Would notify user_id={user_id}: {message}")
            notified += 1
            continue

        inserted = cls_db.insert_notification(user_id, row["cls_id"], event_type, message)
        if inserted:
            cls_db.send_fcm_push(user_id, "CLS Reminder", message)
            notified += 1

    return len(rows), notified


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main(dry_run=False):
    log("=" * 55)
    log(f"CLS NOTIFICATIONS POLLER — START{' (DRY RUN)' if dry_run else ''}")
    log("=" * 55)

    now = datetime.now()
    total_matched = 0
    total_notified = 0
    ok = True

    for event_type in cls_db.NOTIFICATION_TRIGGERS:
        try:
            matched, notified = process_event_type(event_type, now, dry_run=dry_run)
            total_matched += matched
            total_notified += notified
            if matched:
                log(f"{event_type}: {matched} row(s) matched, {notified} notification(s) sent/inserted.")
        except Exception as e:
            ok = False
            log(f"{event_type}: FAILED — {e}", "ERROR")

    summary = f"{total_matched} row(s) matched, {total_notified} notification(s) sent" \
        + (" (dry run — nothing written)" if dry_run else "")
    if not dry_run:
        cls_db.write_job_result("Notifications Poller", ok, summary)

    log(summary)
    log("CLS NOTIFICATIONS POLLER — END")
    log("=" * 55)
    return ok


# ─────────────────────────────────────────────────────────────
# SELF-TEST MODE
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Config sanity only — no DB query, no send. Confirms every
    NOTIFICATION_TRIGGERS event_type has a matching NOTIFICATION_EVENTS
    message template (a typo'd key here would silently KeyError mid-run
    otherwise), and that the window math is monotonic (window_start <
    window_end) for all 5 configured offsets.
    """
    print("=" * 55)
    print(" CLS NOTIFICATIONS POLLER — SELF TEST")
    print("=" * 55)
    now = datetime.now()
    all_ok = True
    for event_type, (source_table, date_column, offset_hours, extra_where) in cls_db.NOTIFICATION_TRIGGERS.items():
        if event_type not in cls_db.NOTIFICATION_EVENTS:
            print(f"[FAIL] {event_type}: no matching NOTIFICATION_EVENTS message template.")
            all_ok = False
            continue
        window_start, window_end = _window_for(offset_hours, now)
        if window_start >= window_end:
            print(f"[FAIL] {event_type}: window_start >= window_end ({window_start} >= {window_end}).")
            all_ok = False
            continue
        print(f"[OK]   {event_type}: {source_table}.{date_column}, offset={offset_hours}h, "
              f"window=({window_start.strftime('%H:%M')}, {window_end.strftime('%H:%M')}]")
    print()
    print("Self-test complete." if all_ok else "Self-test FAILED — see above.")
    print("=" * 55)
    return all_ok


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main(dry_run="--dry-run" in sys.argv)
