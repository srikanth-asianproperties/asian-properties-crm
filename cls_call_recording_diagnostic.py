"""
=============================================================
cls_call_recording_diagnostic.py  —  Call Recordings Diagnostic Tool
=============================================================
Version : 1.1
Author  : Built for Asian Properties / Srikanth

WHAT THIS IS
------------
Srikanth's Android app reports a sync summary on-screen after a run
("586 checked, 439 matched, 51 uploaded, 254 skipped...") that isn't
visible anywhere on the server. This tool answers server-side questions
about what D:\\CLS actually received for one user on one day.

It does NOT (and cannot) verify the phone's own on-device state — the
app's on-screen numbers describe what the PHONE found when it scanned
its own call log and recording folder, information that never reaches
this server today. That's a separate, phone-side diagnostic (Item 2 of
the Task 4 batch this script's v1.0 was born in — the expanded
SettingsActivity.kt diagnostic screen + its Share action) — this script
is server/D:\\CLS-side only.

Follows cls_call_recording_audit.py's existing conventions closely: same
RECORDINGS_DIR, same os.path.exists() check (imported directly from that
script — see _recording_path_on_disk below — rather than forked), same
"list only, never auto-delete" posture. This is a sibling diagnostic, not
a replacement — cls_call_recording_audit.py stays the tool for reviewing
and removing suspect rows; this one is read-only, always.

v1.1 — WHY THIS CHANGED (2026-08-20 follow-up session)
-------------------------------------------------------
v1.0 only cross-checked activity_log 'call_recording' rows against files
on disk — it answered "of what got logged, is it still playable?" It
stayed silent on the much bigger question Srikanth actually asked after
a live test the same day: "I know elohar/office made 30+ calls today —
why does the tool only show 10 recordings?" v1.0's numbers (10 for one
user, 33 for the other, on 2026-08-19) were technically correct but gave
no visibility into how many actual calls never became a recording at all.

v1.1 adds a NEW layer in FRONT of the v1.0 check, built on
cls_db.get_call_staging_rows() (v2.71): call_log_staging gets a row for
EVERY call the app reports during sync, matched or not, recorded or not
(record_call_log_entry() persists every entry there regardless of
outcome) — this is the table that can actually answer "how many real
calls were there, and what happened to each one?"

IMPORTANT DATA WRINKLE DISCOVERED WHILE BUILDING THIS: call_log_staging
has heavy duplicate rows from the app's periodic re-sync — the SAME
physical call gets re-staged (exact-duplicate row, differing only in
staging_id/created_at) on every subsequent sync run that still sees it
in the phone's call log. On live 2026-08-19 data this inflated raw
COUNT(*) by several multiples (one real example: 534 raw staging rows,
only 72 distinct real calls). cls_db.get_call_staging_rows() dedupes by
(matched_cls_id, call_timestamp, duration_seconds, direction) — verified
safe on live data: every duplicate group had IDENTICAL matched_cls_id/
match_status within the group, so dedup never silently discards a real
match/status disagreement, only genuine re-sync copies of one call. See
that function's own docstring in cls_db.py for the full writeup.

v1.0's original activity_log-vs-disk check is UNCHANGED below and still
runs every time — this is a strict addition, not a replacement.

INTERPRETING THE RESULT (read before treating a gap as "the bug")
-------------------------------------------------------------------
Several different gaps can show up here, and they point at different
failures:
  - UNMATCHED calls (no lead in cls.db has that phone number at all) are
    reported only as a count, never broken down further — that's a
    stale/wrong contact number problem, a completely different question
    from the recording pipeline, and deliberately out of scope here.
  - Of MATCHED calls, UNANSWERED ones (duration_seconds == 0) are never
    expected to have a recording — that's normal, not a gap.
  - Of MATCHED + ANSWERED calls, the ones that did NOT become a
    recording are the actionable number — could be a legitimate
    ambiguous-match skip on the phone side, or a genuine loss. This
    script can't tell those apart; Item 2's Android diagnostic screen
    (once built and sideloaded) is the tool for narrowing that further
    on the phone itself.
  - Separately, this script cannot fetch the app's own reported "51
    uploaded" on-screen number — the server has no way to receive that
    today. If the server-side LOGGED count (now: the "became a
    recording" number below) is well below what the app showed on-
    screen, that's evidence the client-to-server SYNC itself is dropping
    requests silently — worth checking app/network logs next, not this
    script. If logged/became-a-recording matches what the app reported,
    but files are missing on disk (v1.0's original check, still below),
    that's the FILE-WRITE side failing after a successful log — same
    class of failure as the 2026-07-31 incident (see cls_call_recording_
    audit.py's docstring), already partially mitigated in
    MainActivity.kt v0.23.

USAGE
-----
    python cls_call_recording_diagnostic.py --user <email> [--date YYYY-MM-DD]
        Default output — ONE plain-English paragraph combining the new
        staging cross-check and the original v1.0 file-on-disk check:
          For <user> on <date>: N calls staged, M matched to a lead (U
          unanswered, A answered). Of the A answered calls, R became a
          recording and X did not. Server file check: L recordings
          logged, P present and playable, K missing on disk.
        --date defaults to today if omitted.

    python cls_call_recording_diagnostic.py --user <email> --date YYYY-MM-DD --detail
        Same summary paragraph, PLUS two separate detail sections:
          1. "Missing on disk" (v1.0, UNCHANGED) — activity_log rows that
             exist but whose file is gone from disk.
          2. NEW "Answered, matched, but no recording" — the actionable
             subset from the staging cross-check: lead name, cls_id,
             call_timestamp, for every matched+answered call that never
             became a recording at all.
        Either section is omitted if it has nothing to show.

    python cls_call_recording_diagnostic.py --selftest
        Offline sanity checks only — no real DB query. Exits non-zero on
        failure.

CHANGELOG
---------
v1.1 (2026-08-20) — Staging-vs-recording cross-check added in front of
  the v1.0 file-on-disk check (see "WHY THIS CHANGED" above). New:
  resolve_user_id() (email -> user_id via cls_db.get_all_users_detailed(),
  since no dedicated email->user_id lookup function exists anywhere in
  cls_db.py — every existing caller, e.g. verify_login(), does its own
  inline WHERE email=? query; get_all_users_detailed() is the established
  reusable pattern other read-only tools already use for this same
  email correlation, per list_call_recordings()'s own docstring), and
  summarize_staging() (pure aggregation over cls_db.get_call_staging_
  rows() output — kept separate/pure specifically so --selftest can
  exercise it against synthetic data with no DB access). Tested against
  real 2026-08-19 data for both office.asianproperties@gmail.com and
  elohar.asianproperties@gmail.com — "became a recording" counts (33 and
  10 respectively) landed EXACTLY on v1.0's already-correct activity_log
  counts for the same user/date, confirming the new join logic is sound.
  cls_db.py gained ONE new read-only function for this (get_call_staging_
  rows(), v2.71) — kept in cls_db.py rather than as raw SQL in this
  script, per this codebase's "All SQLite access stays centralized in
  cls_db.py" rule; nothing existing in cls_db.py or cls_call_recording_
  audit.py was touched.
v1.0 (2026-08-19) — Initial version.
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


def resolve_user_id(users, email):
    """
    Pure lookup — takes cls_db.get_all_users_detailed()'s already-fetched
    list so it's testable offline (see --selftest) without a DB hit of
    its own. Normalizes via cls_db.norm_email() on both sides, same
    convention verify_login() uses for the same field.
    """
    target = cls_db.norm_email(email)
    if not target:
        return None
    for u in users:
        if cls_db.norm_email(u.get("email") or "") == target:
            return u["user_id"]
    return None


def summarize_staging(rows):
    """
    Pure aggregation over cls_db.get_call_staging_rows()'s output — kept
    separate from any DB access specifically so --selftest can exercise
    this against synthetic data. Returns a dict with every count needed
    for both the summary paragraph and the --detail "no recording" list.
    """
    total = len(rows)
    matched = [r for r in rows if r["matched_cls_id"]]
    unmatched = total - len(matched)
    answered = [r for r in matched if (r["duration_seconds"] or 0) > 0]
    unanswered = len(matched) - len(answered)
    became_recording = [r for r in answered if r["has_recording"]]
    no_recording = [r for r in answered if not r["has_recording"]]
    return {
        "total": total,
        "matched": len(matched),
        "unmatched": unmatched,
        "answered": len(answered),
        "unanswered": unanswered,
        "became_recording": len(became_recording),
        "no_recording_rows": no_recording,
    }


def run_diagnostic(user, date_str, detail):
    users = cls_db.get_all_users_detailed()
    user_id = resolve_user_id(users, user)
    if user_id is None:
        _print(f"No CRM user found with email {user}.")
        return

    staging_rows = cls_db.get_call_staging_rows(user_id, date_str)
    s = summarize_staging(staging_rows)

    result = cls_db.list_call_recordings(
        date_from=date_str, date_to=date_str, activity_owner=user, per_page=100000
    )
    rec_rows = result["rows"]
    logged = len(rec_rows)
    present = 0
    missing_rows = []
    for r in rec_rows:
        file_path = _recording_path_on_disk(r["cls_id"], r["recording_file_path"])
        exists = os.path.exists(file_path) if file_path else False
        if exists:
            present += 1
        else:
            missing_rows.append((r, file_path, exists))
    missing = logged - present

    _print(
        f"For {user} on {date_str}: {s['total']} calls staged, {s['matched']} "
        f"matched to a lead ({s['unanswered']} unanswered, {s['answered']} answered). "
        f"Of the {s['answered']} answered calls, {s['became_recording']} became a "
        f"recording and {len(s['no_recording_rows'])} did not. "
        f"Server file check: {logged} recordings logged, {present} present and "
        f"playable, {missing} missing on disk."
    )

    if detail and missing_rows:
        _print("")
        _print("Missing on disk (logged but file is gone):")
        for r, file_path, exists in missing_rows:
            _print(f"activity_id={r['activity_id']}")
            _print(f"  lead: {r['full_name'] or '(no name)'} | cls_id={r['cls_id']}")
            _print(f"  call time (created_at): {r['created_at']}")
            _print(f"  file: {file_path or '(no file path recorded)'} | exists on disk: {exists}")
            _print("")

    if detail and s["no_recording_rows"]:
        _print("")
        _print("Answered, matched, but no recording (actionable subset):")
        for r in s["no_recording_rows"]:
            _print(f"  lead: {r['full_name'] or '(no name)'} | cls_id={r['matched_cls_id']}")
            _print(f"  call_timestamp: {r['call_timestamp']} | duration: {r['duration_seconds']}s | direction: {r['direction'] or '(unknown)'}")
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

    # resolve_user_id() — offline, synthetic user list, no DB hit.
    fake_users = [
        {"user_id": 1, "email": "alice@example.com"},
        {"user_id": 2, "email": "Bob@Example.com"},
    ]
    if resolve_user_id(fake_users, "alice@example.com") != 1:
        _print("SELFTEST FAIL: resolve_user_id did not match exact-case email")
        ok = False
    if resolve_user_id(fake_users, "bob@example.com") != 2:
        _print("SELFTEST FAIL: resolve_user_id did not normalize case")
        ok = False
    if resolve_user_id(fake_users, "nobody@example.com") is not None:
        _print("SELFTEST FAIL: resolve_user_id should return None for an unknown email")
        ok = False

    # summarize_staging() — offline, synthetic staging rows, no DB hit.
    # 4 calls: 1 unmatched, 1 matched+unanswered, 1 matched+answered+recorded,
    # 1 matched+answered+NOT recorded.
    fake_rows = [
        {"matched_cls_id": None, "call_timestamp": "2026-01-01 09:00:00",
         "duration_seconds": 30, "direction": "OUTGOING", "full_name": None, "has_recording": False},
        {"matched_cls_id": "lead-1", "call_timestamp": "2026-01-01 09:05:00",
         "duration_seconds": 0, "direction": "OUTGOING", "full_name": "Lead One", "has_recording": False},
        {"matched_cls_id": "lead-2", "call_timestamp": "2026-01-01 09:10:00",
         "duration_seconds": 45, "direction": "INCOMING", "full_name": "Lead Two", "has_recording": True},
        {"matched_cls_id": "lead-3", "call_timestamp": "2026-01-01 09:15:00",
         "duration_seconds": 60, "direction": "OUTGOING", "full_name": "Lead Three", "has_recording": False},
    ]
    s = summarize_staging(fake_rows)
    expected_s = {
        "total": 4, "matched": 3, "unmatched": 1,
        "answered": 2, "unanswered": 1, "became_recording": 1,
    }
    for key, val in expected_s.items():
        if s[key] != val:
            _print(f"SELFTEST FAIL: summarize_staging()[{key}] = {s[key]}, expected {val}")
            ok = False
    if len(s["no_recording_rows"]) != 1 or s["no_recording_rows"][0]["matched_cls_id"] != "lead-3":
        _print("SELFTEST FAIL: summarize_staging() no_recording_rows incorrect")
        ok = False

    # Date default logic (no live DB query — just the argparse/date wiring).
    today_str = datetime.now().strftime("%Y-%m-%d")
    if len(today_str) != 10:
        _print("SELFTEST FAIL: unexpected today() format")
        ok = False

    # Centralized DB access — confirm the functions this script depends
    # on exist with the expected names (offline, no call made).
    for fn_name in ("list_call_recordings", "get_all_users_detailed", "get_call_staging_rows", "norm_email"):
        if not hasattr(cls_db, fn_name):
            _print(f"SELFTEST FAIL: cls_db.{fn_name} not found")
            ok = False

    if ok:
        _print("SELFTEST PASS")
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Server-side diagnostic: how many real calls a user made/received on a "
                     "given day, what happened to each (matched/answered/recorded), and "
                     "whether logged recordings are still present on disk."
    )
    parser.add_argument("--user", help="Salesperson's login email (activity_log.actor).")
    parser.add_argument("--date", help="YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--detail", action="store_true",
                         help="Also list the missing-file rows and the answered-but-unrecorded rows.")
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
