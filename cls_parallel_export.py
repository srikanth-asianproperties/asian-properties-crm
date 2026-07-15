"""
=============================================================
cls_parallel_export.py  —  CLS Parallel-Run Sync-Health Checkpoint
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.0  (July 2026) — initial version, per Srikanth's locked design.

PURPOSE
-------
Measures how often a CRM-side stage or owner change gets silently
REVERTED by Job B's next Sell.do sync — a parallel-run sync-health
checkpoint, run manually whenever a read is wanted, NOT scheduled
alongside Jobs A-D. Read-only: makes no writes to cls.db, no schema
changes, and no direct sqlite3 access — the ONLY database call this
script makes is cls_db.get_latest_stage_and_owner_changes() (added in
cls_db.py v2.10). See that function's docstring for the query itself.

COMPARISON LOGIC (per lead, independently for stage and for owner)
--------------------------------------------------------------------
  - No change of that type ever logged for this lead -> skipped
    entirely for that category (nothing to compare against).
  - Logged change's new_value == the live column right now -> CLEAN
    (Job B's sync agrees with the CRM change, or hasn't touched it).
  - They differ AND less than JOB_B_SYNC_WINDOW_HOURS has passed since
    the change -> PENDING (Job B just hasn't run again yet; not
    necessarily a revert).
  - They differ AND JOB_B_SYNC_WINDOW_HOURS or more has passed ->
    REVERTED (Job B has had time to run and the CRM change did not
    survive it).

OUTPUT
------
  Console : combined totals (reverted/pending/clean) for stage drift
            and owner drift, each also broken down per salesperson
            (activity_log.actor). No lead-identifying data ever goes
            to the console.
  File    : full detail (lead names, phones, before/after values) to
            a timestamped .txt file in C:\\CLS, for local review only —
            never printed to console, never uploaded anywhere.

RUN
---
  python cls_parallel_export.py
=============================================================
"""

import os
import sys
from collections import defaultdict
from datetime import datetime

import cls_db   # the foundation layer — the ONLY way this script touches cls.db

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

# How long to give Job B to have run again since a CRM-side change
# before treating a still-mismatched value as REVERTED rather than
# just PENDING. Config-not-code, per Srikanth's locked design — matches
# Job B's own hourly sync cadence with headroom, not a magic number.
JOB_B_SYNC_WINDOW_HOURS = 3

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

DETAIL_FILE_PATH_TEMPLATE = os.path.join(
    cls_db.BASE_DIR, "parallel_export_{ts}.txt"
)


# ─────────────────────────────────────────────────────────────
# CONSOLE OUTPUT  —  guarded print (pythonw.exe sets stdout to None)
# ─────────────────────────────────────────────────────────────

def _print(message):
    """
    Guarded, UTF-8-safe console print. This script is normally run
    manually via python.exe (which has a console), not pythonw.exe —
    but the guard is kept for consistency with every other CLS script,
    per CLAUDE.md's "guard every print()" rule.
    """
    if sys.stdout is None:
        return
    safe_message = message.encode("utf-8", errors="replace").decode("utf-8")
    try:
        print(safe_message)
    except UnicodeEncodeError:
        print(safe_message.encode("ascii", errors="replace").decode("ascii"))


# ─────────────────────────────────────────────────────────────
# CLASSIFICATION
# ─────────────────────────────────────────────────────────────

def _parse_timestamp(value):
    return datetime.strptime(value, TIMESTAMP_FORMAT)


def classify_drift(logged_new_value, logged_at, live_value, now,
                    window_hours=JOB_B_SYNC_WINDOW_HOURS):
    """
    Returns "clean" / "pending" / "reverted", or None if there was no
    logged change of this type to compare (caller should skip it).
    """
    if logged_new_value is None:
        return None
    if logged_new_value == live_value:
        return "clean"
    elapsed_hours = (now - _parse_timestamp(logged_at)).total_seconds() / 3600.0
    if elapsed_hours >= window_hours:
        return "reverted"
    return "pending"


def _empty_counts():
    return {"reverted": 0, "pending": 0, "clean": 0}


def build_report(rows, now, window_hours=JOB_B_SYNC_WINDOW_HOURS):
    """
    Walks the rows from cls_db.get_latest_stage_and_owner_changes() and
    classifies stage drift and owner drift independently for each lead.

    Returns a dict:
      stage_totals, owner_totals   -> {"reverted": n, "pending": n, "clean": n}
      stage_by_actor, owner_by_actor -> {actor: {"reverted":.., ...}}
      stage_detail, owner_detail   -> list of dicts with full before/after
                                       values, for the local detail file only
    """
    stage_totals = _empty_counts()
    owner_totals = _empty_counts()
    stage_by_actor = defaultdict(_empty_counts)
    owner_by_actor = defaultdict(_empty_counts)
    stage_detail = []
    owner_detail = []

    for row in rows:
        stage_result = classify_drift(
            row["stage_change_new"], row["stage_change_at"],
            row["current_stage"], now, window_hours,
        )
        if stage_result is not None:
            stage_totals[stage_result] += 1
            actor = row["stage_change_actor"] or "(unknown)"
            stage_by_actor[actor][stage_result] += 1
            stage_detail.append({
                "cls_id": row["cls_id"],
                "full_name": row["full_name"],
                "phone_raw": row["phone_raw"],
                "actor": actor,
                "prev_value": row["stage_change_prev"],
                "logged_new_value": row["stage_change_new"],
                "live_value": row["current_stage"],
                "changed_at": row["stage_change_at"],
                "result": stage_result,
            })

        owner_result = classify_drift(
            row["owner_change_new"], row["owner_change_at"],
            row["lead_owner"], now, window_hours,
        )
        if owner_result is not None:
            owner_totals[owner_result] += 1
            actor = row["owner_change_actor"] or "(unknown)"
            owner_by_actor[actor][owner_result] += 1
            owner_detail.append({
                "cls_id": row["cls_id"],
                "full_name": row["full_name"],
                "phone_raw": row["phone_raw"],
                "actor": actor,
                "prev_value": row["owner_change_prev"],
                "logged_new_value": row["owner_change_new"],
                "live_value": row["lead_owner"],
                "changed_at": row["owner_change_at"],
                "result": owner_result,
            })

    return {
        "stage_totals": stage_totals,
        "owner_totals": owner_totals,
        "stage_by_actor": dict(stage_by_actor),
        "owner_by_actor": dict(owner_by_actor),
        "stage_detail": stage_detail,
        "owner_detail": owner_detail,
    }


# ─────────────────────────────────────────────────────────────
# CONSOLE SUMMARY
# ─────────────────────────────────────────────────────────────

def _print_counts_line(label, counts):
    _print(
        f"  {label}: reverted={counts['reverted']}  "
        f"pending={counts['pending']}  clean={counts['clean']}"
    )


def print_summary(report, detail_file_path):
    _print("=" * 60)
    _print(" CLS PARALLEL-RUN SYNC-HEALTH CHECKPOINT")
    _print("=" * 60)

    _print("")
    _print("STAGE DRIFT (CRM stage changes vs current_stage)")
    _print_counts_line("Total", report["stage_totals"])
    if report["stage_by_actor"]:
        _print("  By salesperson:")
        for actor in sorted(report["stage_by_actor"]):
            _print_counts_line(f"    {actor}", report["stage_by_actor"][actor])

    _print("")
    _print("OWNER DRIFT (CRM owner changes vs lead_owner)")
    _print_counts_line("Total", report["owner_totals"])
    if report["owner_by_actor"]:
        _print("  By salesperson:")
        for actor in sorted(report["owner_by_actor"]):
            _print_counts_line(f"    {actor}", report["owner_by_actor"][actor])

    _print("")
    _print(f"Full detail (names/phones/before-after) written to:")
    _print(f"  {detail_file_path}")
    _print("=" * 60)


# ─────────────────────────────────────────────────────────────
# LOCAL DETAIL FILE  —  never printed to console, never uploaded
# ─────────────────────────────────────────────────────────────

def _write_detail_section(f, title, detail_rows):
    f.write(f"{title}\n")
    f.write("-" * len(title) + "\n")
    if not detail_rows:
        f.write("  (none)\n\n")
        return
    for d in detail_rows:
        f.write(
            f"  [{d['result'].upper()}] {d['full_name']}  ({d['phone_raw']})  cls_id={d['cls_id']}\n"
            f"      actor={d['actor']}  changed_at={d['changed_at']}\n"
            f"      logged: {d['prev_value']} -> {d['logged_new_value']}   "
            f"live now: {d['live_value']}\n"
        )
    f.write("\n")


def write_detail_file(report, path, now):
    with open(path, "w", encoding="utf-8") as f:
        f.write("CLS PARALLEL-RUN SYNC-HEALTH — FULL DETAIL\n")
        f.write(f"Generated: {now.strftime(TIMESTAMP_FORMAT)}\n")
        f.write(f"Job B sync window used: {JOB_B_SYNC_WINDOW_HOURS} hours\n")
        f.write("=" * 60 + "\n\n")
        _write_detail_section(f, "STAGE DRIFT DETAIL", report["stage_detail"])
        _write_detail_section(f, "OWNER DRIFT DETAIL", report["owner_detail"])


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run():
    now = datetime.now()
    rows = cls_db.get_latest_stage_and_owner_changes()
    report = build_report(rows, now)

    detail_file_path = DETAIL_FILE_PATH_TEMPLATE.format(
        ts=now.strftime("%Y%m%d_%H%M%S")
    )
    write_detail_file(report, detail_file_path, now)
    print_summary(report, detail_file_path)


if __name__ == "__main__":
    run()
