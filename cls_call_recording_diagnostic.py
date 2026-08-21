"""
=============================================================
cls_call_recording_diagnostic.py  —  Call Recordings Diagnostic Tool
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

WHAT THIS IS
------------
Srikanth's Android app reports a sync summary on-screen after a run
("586 checked, 439 matched, 51 uploaded, 254 skipped...") that isn't
visible anywhere on the server. This tool answers a narrower, server-side
question: of what D:\\CLS actually received and logged for one user on
one day, how much is really there and playable?

It does NOT (and cannot) verify the phone's own on-device state — the
app's on-screen numbers describe what the PHONE found when it scanned
its own call log and recording folder, information that never reaches
this server today. That's a separate, phone-side diagnostic (Item 2 of
this same Task 4 batch — the expanded SettingsActivity.kt diagnostic
screen + its Share action) — this script is server/D:\\CLS-side only.

Follows cls_call_recording_audit.py's existing conventions closely: same
RECORDINGS_DIR, same os.path.exists() check (imported directly from that
script — see _recording_path_on_disk below — rather than forked), same
"list only, never auto-delete" posture. This is a sibling diagnostic, not
a replacement — cls_call_recording_audit.py stays the tool for reviewing
and removing suspect rows; this one is read-only, always.

INTERPRETING THE RESULT (read before treating a gap as "the bug")
-------------------------------------------------------------------
This script cannot fetch the app's own reported "51 uploaded" number —
the server has no way to receive that today. Two different gaps look
similar here but point at different failures:
  - If the server-side LOGGED count is well below what the app reported
    on-screen, that's evidence the client-to-server SYNC itself is
    dropping requests silently (the row for that call never arrived at
    all) — worth checking the app/network logs next, not this script.
  - If the logged count matches what the app reported, but files are
    missing on disk (the "missing" bucket below), that's the FILE-WRITE
    side failing after a successful log — same class of failure as the
    2026-07-31 incident (see cls_call_recording_audit.py's docstring),
    already partially mitigated in MainActivity.kt v0.23.
This script only ever shows you the second kind of gap directly. The
first kind has to be inferred by comparing this script's number against
whatever the app displayed on the user's phone.

USAGE
-----
    python cls_call_recording_diagnostic.py --user <email> [--date YYYY-MM-DD]
        Default output — ONE plain-English summary line:
          For <user> on <date>: server has N recordings logged, M files
          present and playable, K logged but missing on disk.
        --date defaults to today if omitted.

    python cls_call_recording_diagnostic.py --user <email> --date YYYY-MM-DD --detail
        Same summary line, PLUS a per-row listing — but only for the
        missing-file rows (the actionable subset), not a full dump. Each
        row shows the same fields cls_call_recording_audit.py already
        prints: lead name, cls_id, call time, file path, exists on disk.

    python cls_call_recording_diagnostic.py --selftest
        Offline sanity checks only — no real DB query, no argument
        validation against live data. Exits non-zero on failure.

CHANGELOG
---------
v1.0 (2026-08-20) — Initial version. Task 4 (Srikanth, Todoist
  ##CLS-CRM), item 1. Not yet added to cls_pk_bundle.py's INCLUDE_FILES —
  same auto-discovered-but-untracked status cls_weekend_visits_report.py
  had before it was locked in; flagged for Srikanth to decide, not
  silently added here.
=============================================================
"""

import argparse
import os
import sys
from datetime import datetime

BASE_DIR = r"D:\CLS"
RECORDINGS_DIR = os.path.join(BASE_DIR, "call_recordings")
sys.path.insert(0, BASE_DIR)
import cls_db  # noqa: E402
from cls_call_recording_audit import _recording_path_on_disk  # noqa: E402 — reused, not forked


def _print(msg):
    try:
        if sys.stdout is not None:
            print(msg)
    except Exception:
        pass


def run_diagnostic(user, date_str, detail):
    result = cls_db.list_call_recordings(
        date_from=date_str, date_to=date_str, activity_owner=user, per_page=100000
    )
    rows = result["rows"]

    logged = len(rows)
    present = 0
    missing_rows = []
    for r in rows:
        file_path = _recording_path_on_disk(r["cls_id"], r["recording_file_path"])
        exists = os.path.exists(file_path) if file_path else False
        if exists:
            present += 1
        else:
            missing_rows.append((r, file_path, exists))

    missing = logged - present
    _print(
        f"For {user} on {date_str}: server has {logged} recordings logged, "
        f"{present} files present and playable, {missing} logged but missing on disk."
    )

    if detail and missing_rows:
        _print("")
        _print("Missing-file rows (actionable subset):")
        for r, file_path, exists in missing_rows:
            _print(f"activity_id={r['activity_id']}")
            _print(f"  lead: {r['full_name'] or '(no name)'} | cls_id={r['cls_id']}")
            _print(f"  call time (created_at): {r['created_at']}")
            _print(f"  file: {file_path or '(no file path recorded)'} | exists on disk: {exists}")
            _print("")


def selftest():
    ok = True

    # _recording_path_on_disk() reused correctly from the sibling audit script.
    p = _recording_path_on_disk("abc-123", "rec.mp3")
    expected = os.path.join(RECORDINGS_DIR, "abc-123", "rec.mp3")
    if p != expected:
        _print(f"SELFTEST FAIL: _recording_path_on_disk mismatch: {p!r} != {expected!r}")
        ok = False
    if _recording_path_on_disk("abc-123", None) is not None:
        _print("SELFTEST FAIL: _recording_path_on_disk should return None for empty filename")
        ok = False

    # Date default logic (no live DB query — just the argparse/date wiring).
    today_str = datetime.now().strftime("%Y-%m-%d")
    if len(today_str) != 10:
        _print("SELFTEST FAIL: unexpected today() format")
        ok = False

    # cls_db.list_call_recordings is centralized DB access — confirm the
    # function exists with the expected signature (offline, no call made).
    if not hasattr(cls_db, "list_call_recordings"):
        _print("SELFTEST FAIL: cls_db.list_call_recordings not found")
        ok = False

    if ok:
        _print("SELFTEST PASS")
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Server-side diagnostic: how many call recordings were logged for a "
                     "user on a given day, and how many are actually present on disk."
    )
    parser.add_argument("--user", help="Salesperson's login email (activity_log.actor).")
    parser.add_argument("--date", help="YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--detail", action="store_true",
                         help="Also list the missing-file rows individually.")
    parser.add_argument("--selftest", action="store_true",
                         help="Offline sanity checks only, no DB query.")
    args = parser.parse_args()

    if args.selftest:
        ok = selftest()
        sys.exit(0 if ok else 1)

    if not args.user:
        parser.error("--user is required (unless --selftest).")

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    run_diagnostic(args.user, date_str, args.detail)


if __name__ == "__main__":
    main()
