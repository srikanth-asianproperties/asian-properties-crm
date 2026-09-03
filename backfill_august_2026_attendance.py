"""
backfill_august_2026_attendance.py
v1.0 (2026-09-03)

ONE-TIME, STANDALONE backfill script — NOT a permanent addition to
cls_db.py or any scheduled job. Same category as this codebase's other
confirmed one-off scripts (cls_fix_duplicate_lead_no.py etc.). Do not
add this file to cls_pk_bundle.py's INCLUDE_FILES.

PURPOSE
-------
August 2026's attendance rows are incomplete because the attendance
feature wasn't in full use for the whole month — the app simply wasn't
being punched into yet during the first several days of August for
these 3 users. This script backfills the real history Srikanth manually
confirmed, via the EXISTING audited correction pathway
(cls_db.apply_admin_attendance_exemption()), so August's record is
accurate BEFORE Fix 2's stricter absent-detection logic
(compute_salary_for_month() v2.90 — an attendance day with no row at
all now counts as absent unless it's a declared holiday) gets applied
to a month that predates that logic existing, and BEFORE the month
locks permanently on 2026-09-10 (10 calendar days after 2026-08-31).

REAL HISTORY (confirmed by Srikanth, spellings verified against the
live users table before this was written — user_id 2/3/4 respectively):
  - Elohar Peddi  : weekoff = Aug 3, 10, 18, 27, 31.  leave = Aug 12.
  - Devender Goud : weekoff = Aug 3, 10, 17, 27, 31.  leave = Aug 16.
  - Mounika Peddi : weekoff = Aug 3, 10, 18, 27, 31.  leave = Aug 12.
  - Aug 28 = company holiday (Rakhi) — every other day in August for
    these 3 users is backfilled as 'present'.

SAFETY RULES
------------
  1. Never overwrite a REAL punch. If the existing attendance row for
     (user, date) already has login_ts set, the date is SKIPPED
     entirely, regardless of what this script's target status says —
     logged as "skipped-punch-exists". (Verified against live data
     before this was written: Elohar's Aug 31 and Mounika's Aug 31 BOTH
     already have a real punch that in a review of Srikanth's stated
     history was expected to be a weekoff — both are correctly skipped
     by this rule, and since 'late'/'present' cost the same as
     'weekoff' in payroll math (both zero-deduction), this has NO net
     payroll effect either way. See the script's own dry-run output
     for the full list of what gets skipped and why.)
  2. If a row already exists with NO login_ts and its status ALREADY
     matches this script's target for that date (e.g. Aug 10 is
     already 'weekoff' for all three users, matching the target),
     the date is SKIPPED with "skipped-already-correct" — avoids
     growing the attendance_corrections audit trail with no-op entries
     for days that were never wrong. (cls_db.apply_admin_attendance_
     exemption() is documented as idempotent for this exact case, so
     this is a courtesy skip, not a correctness requirement.)
  3. Everything else (no row at all, or a row whose status disagrees
     with the target and has no real punch) is backfilled via
     cls_db.apply_admin_attendance_exemption(), logged as "applied".
  4. Aug 28 (the holiday) is never touched — no attendance row is
     expected or created for a company holiday.

USAGE
-----
    python backfill_august_2026_attendance.py --dry-run
        Prints every intended action (applied / skipped-punch-exists /
        skipped-already-correct) without writing anything or touching
        payroll. ALWAYS run this first and review the output.

    python backfill_august_2026_attendance.py
        REAL RUN — writes the backfill via apply_admin_attendance_
        exemption(), then recalculates August 2026 payroll
        (cls_db.compute_salary_for_month) and prints the resulting
        net_salary per user. Only run this on Srikanth's explicit
        go-ahead after reviewing the --dry-run output.

EXPECTED OUTCOME: based on the history Srikanth provided, none of the
three employees had any unexplained absence in August — the
recalculated net salary is expected to come out IDENTICAL to what was
already shown before this fix (Elohar Rs 25,000 / Devender Rs 18,000 /
Mounika Rs 16,000, per the live salary_snapshots row calculated
2026-09-02 under the pre-Fix-2 logic). If the recalculated numbers do
NOT match, this script stops short of claiming success — the mismatch
is printed for Srikanth to review, not silently accepted.

CHANGELOG
---------
v1.0 (2026-09-03) — initial version.
"""
import sys
import argparse

sys.path.insert(0, r"D:\CLS")
import cls_db  # noqa: E402


def safe_print(*a, **k):
    if sys.stdout is not None:
        print(*a, **k)


YEAR, MONTH = 2026, 8
HOLIDAY_DATE = "2026-08-28"
HOLIDAY_LABEL = "Rakhi"

# Config-not-code: name -> {"weekoff": [days...], "leave": [days...]}.
# Every other day in August (except HOLIDAY_DATE) backfills as 'present'.
LEGACY_HISTORY = {
    "Elohar Peddi":  {"weekoff": [3, 10, 18, 27, 31], "leave": [12]},
    "Devender Goud": {"weekoff": [3, 10, 17, 27, 31], "leave": [16]},
    "Mounika Peddi": {"weekoff": [3, 10, 18, 27, 31], "leave": [12]},
}


def resolve_user_ids(names):
    """Resolve each full_name to a user_id against the LIVE users
    table. Aborts (raises) with a clear error listing unresolved names
    if any don't match exactly — never guesses a spelling."""
    conn = cls_db._connect()
    try:
        resolved = {}
        unresolved = []
        for name in names:
            row = conn.execute(
                "SELECT user_id FROM users WHERE full_name=?", (name,)
            ).fetchone()
            if row:
                resolved[name] = row["user_id"]
            else:
                unresolved.append(name)
        if unresolved:
            raise SystemExit(
                f"ABORT: could not resolve these full_name(s) against the live "
                f"users table: {unresolved}. Verify exact spelling before re-running."
            )
        return resolved
    finally:
        conn.close()


def ensure_holiday(dry_run):
    """Verify the Aug 28 holiday row exists; insert it (label='Rakhi')
    only if genuinely missing. Never overwrites an existing row/label —
    this repo's live attendance_holidays already has 2026-08-28 with
    label 'Raksha Bandhan Holiday', which is left exactly as-is."""
    existing = [h for h in cls_db.get_holidays_in_month(YEAR, MONTH) if h["date"] == HOLIDAY_DATE]
    if existing:
        safe_print(f"Holiday {HOLIDAY_DATE} already exists: label={existing[0]['label']!r} — leaving as-is.")
        return
    safe_print(f"Holiday {HOLIDAY_DATE} is MISSING.")
    if dry_run:
        safe_print(f"  [DRY-RUN] would INSERT ({HOLIDAY_DATE}, {HOLIDAY_LABEL!r})")
        return
    cls_db.add_attendance_holiday(HOLIDAY_DATE, HOLIDAY_LABEL)
    safe_print(f"  APPLIED: inserted holiday ({HOLIDAY_DATE}, {HOLIDAY_LABEL!r})")


def target_status_for_day(rules, day):
    if day in rules["weekoff"]:
        return "weekoff"
    if day in rules["leave"]:
        return "leave"
    return "present"


def backfill_user(full_name, user_id, rules, dry_run, counts):
    holiday_day = int(HOLIDAY_DATE.split("-")[2])
    for day in range(1, 32):
        if day == holiday_day:
            continue  # never touch the holiday itself
        date_str = f"{YEAR}-{MONTH:02d}-{day:02d}"
        target_status = target_status_for_day(rules, day)

        existing = cls_db.get_attendance_for_date(user_id, date_str)

        if existing and existing.get("login_ts"):
            safe_print(f"  {date_str}  {full_name:15s}  skipped-punch-exists   "
                       f"(login_ts={existing['login_ts']}, would have set {target_status!r})")
            counts["skipped-punch-exists"] += 1
            continue

        if existing and existing.get("status") == target_status:
            safe_print(f"  {date_str}  {full_name:15s}  skipped-already-correct (status={target_status!r})")
            counts["skipped-already-correct"] += 1
            continue

        if dry_run:
            safe_print(f"  {date_str}  {full_name:15s}  [DRY-RUN] would apply -> status={target_status!r}")
            counts["applied"] += 1
            continue

        ok, message = cls_db.apply_admin_attendance_exemption(
            user_id, date_str, "status", target_status,
            note="August 2026 legacy backfill — pre-app-adoption period",
            actor="admin-backfill-script",
        )
        if ok:
            safe_print(f"  {date_str}  {full_name:15s}  applied -> status={target_status!r}")
            counts["applied"] += 1
        else:
            safe_print(f"  {date_str}  {full_name:15s}  FAILED: {message}")
            counts["failed"] += 1


def main():
    parser = argparse.ArgumentParser(description="One-time backfill of August 2026 legacy attendance.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Print intended actions only. Writes nothing. Run this first.")
    args = parser.parse_args()
    dry_run = args.dry_run

    safe_print("=" * 70)
    safe_print(f"backfill_august_2026_attendance.py — {'DRY RUN' if dry_run else 'REAL RUN (writes data)'}")
    safe_print("=" * 70)

    resolved = resolve_user_ids(list(LEGACY_HISTORY.keys()))
    safe_print(f"Resolved users: {resolved}")

    ensure_holiday(dry_run)

    counts = {"applied": 0, "skipped-punch-exists": 0, "skipped-already-correct": 0, "failed": 0}
    for full_name, rules in LEGACY_HISTORY.items():
        user_id = resolved[full_name]
        safe_print(f"\n--- {full_name} (user_id={user_id}) ---")
        backfill_user(full_name, user_id, rules, dry_run, counts)

    safe_print("\n" + "=" * 70)
    safe_print(f"Summary: {counts}")
    safe_print("=" * 70)

    if counts["failed"]:
        safe_print(f"\n{counts['failed']} date(s) FAILED — review the log above before proceeding. Stopping short of payroll recalculation.")
        return

    if dry_run:
        safe_print("\nDRY RUN complete — nothing was written. Re-run without --dry-run to apply, "
                   "only after Srikanth has reviewed this output.")
        return

    safe_print(f"\nRecalculating August 2026 payroll under the new holiday-aware logic...")
    ok, message = cls_db.compute_salary_for_month(YEAR, MONTH, actor="admin-backfill-script")
    safe_print(f"compute_salary_for_month(2026, 8): ok={ok} — {message}")
    if not ok:
        safe_print("Payroll recalculation did not run (see message above) — nothing further to report.")
        return

    safe_print("\nRecalculated net salary per user:")
    for snap in cls_db.list_salary_snapshots(YEAR, MONTH):
        safe_print(f"  {snap['full_name']:15s}  net_salary=Rs {snap['net_salary']:,.2f}  "
                   f"(absent_days={snap['absent_days']}, untracked_absent_days={snap['untracked_absent_days']}, "
                   f"holiday_days={snap['holiday_days']})")

    safe_print("\nEXPECTED: Elohar Rs 25,000.00 / Devender Rs 18,000.00 / Mounika Rs 16,000.00 — "
               "identical to the already-shown figures. If any of the above differs, STOP and report "
               "the discrepancy to Srikanth rather than assuming the backfill is correct.")


if __name__ == "__main__":
    main()
