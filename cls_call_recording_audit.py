"""
=============================================================
cls_call_recording_audit.py  —  Call-Recording Privacy Audit
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

WHAT THIS IS
------------
One-off review/cleanup tool created after a confirmed privacy incident
(2026-07-31): a duration=0 (missed/unanswered) call log entry caused the
Android pilot's file-matching logic to wrongly attach an unrelated,
PERSONAL call's recording to a real lead's activity timeline. The root
cause is fixed separately in android_pilot's MainActivity.kt (v0.6 — hard
skip for duration=0 calls, ambiguity detection). This script is for
finding and reviewing whatever may already have been logged incorrectly
during testing before that fix existed.

Every activity_log row of type 'call_recording' currently in the database
was created during this week's Phase B testing (the feature is brand new
— there is no older, legitimate data to accidentally sweep up).

DOES NOT AUTO-DELETE ANYTHING. Default mode only lists. Deletion requires
explicitly naming the activity_id(s) to remove, after you've reviewed the
list yourself.

USAGE
-----
    python cls_call_recording_audit.py
        Lists every call_recording activity_log row: activity_id, lead
        name/phone/owner, the real call time, duration, matched phone,
        the recording's file path, and whether that file still exists on
        disk. Review this output yourself before deciding what to remove.

    python cls_call_recording_audit.py --delete 41 57
        Deletes ONLY activity_log rows with activity_id 41 and 57 (each
        must already be activity_type='call_recording' — see
        cls_db.delete_call_recording_activity()'s own scoping). Prints
        the on-disk file path for each deleted row but does NOT delete
        the file itself unless --delete-file is also passed.

    python cls_call_recording_audit.py --delete 41 57 --delete-file
        Same as above, and additionally deletes the underlying .mp3 file
        from C:\\CLS\\call_recordings\\<cls_id>\\<filename> for each row
        removed. This is the only way this script ever touches a file on
        disk — never during the default list-only mode.

CHANGELOG
---------
v1.0 (2026-07-31) — Initial version.
=============================================================
"""

import argparse
import os
import sys

BASE_DIR = r"C:\CLS"
RECORDINGS_DIR = os.path.join(BASE_DIR, "call_recordings")
sys.path.insert(0, BASE_DIR)
import cls_db  # noqa: E402


def _print(msg):
    try:
        if sys.stdout is not None:
            print(msg)
    except Exception:
        pass


def _recording_path_on_disk(cls_id, filename):
    if not filename:
        return None
    return os.path.join(RECORDINGS_DIR, cls_id, filename)


def list_activities():
    activities = cls_db.list_call_recording_activities()
    if not activities:
        _print("No call_recording activity_log rows found.")
        return

    _print(f"Found {len(activities)} call_recording activity_log row(s):\n")
    for a in activities:
        file_path = _recording_path_on_disk(a["cls_id"], a["recording_file_path"])
        file_exists = os.path.exists(file_path) if file_path else False
        _print(f"activity_id={a['activity_id']}")
        _print(f"  lead: {a['full_name'] or '(no name)'} | cls_id={a['cls_id']} | owner={a['lead_owner'] or '(none)'}")
        _print(f"  lead phone_norm: {a['phone_norm'] or '(none)'} | matched_phone logged: {a['matched_phone'] or '(none)'}")
        _print(f"  call time (created_at): {a['created_at']} | duration: {a['duration_seconds']}s")
        _print(f"  uploaded by: {a['actor']}")
        _print(f"  file: {file_path or '(no file path recorded)'} | exists on disk: {file_exists}")
        _print("")

    _print(
        "Review the above. To remove a specific row after confirming it's wrong:\n"
        "  python cls_call_recording_audit.py --delete <activity_id> [<activity_id> ...]\n"
        "Add --delete-file to also remove the underlying recording file from disk."
    )


def delete_activities(activity_ids, delete_file):
    for activity_id in activity_ids:
        activities = cls_db.list_call_recording_activities()
        match = next((a for a in activities if a["activity_id"] == activity_id), None)
        if not match:
            _print(f"activity_id={activity_id}: not found (or not a call_recording row) — skipped.")
            continue

        file_path = _recording_path_on_disk(match["cls_id"], match["recording_file_path"])

        ok, msg = cls_db.delete_call_recording_activity(activity_id)
        _print(f"activity_id={activity_id}: {msg}")
        if not ok:
            continue

        if file_path and os.path.exists(file_path):
            if delete_file:
                try:
                    os.remove(file_path)
                    _print(f"  Deleted file: {file_path}")
                except Exception as e:
                    _print(f"  Could not delete file {file_path}: {e}")
            else:
                _print(f"  File left on disk (pass --delete-file to also remove it): {file_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Review and (optionally) delete call_recording activity_log rows."
    )
    parser.add_argument(
        "--delete", nargs="+", type=int, metavar="ACTIVITY_ID",
        help="Delete these specific activity_id(s). Without this flag, the script only lists."
    )
    parser.add_argument(
        "--delete-file", action="store_true",
        help="With --delete, also remove the underlying recording file from disk."
    )
    args = parser.parse_args()

    if args.delete:
        delete_activities(args.delete, args.delete_file)
    else:
        list_activities()


if __name__ == "__main__":
    main()
