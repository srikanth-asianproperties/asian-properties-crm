"""
cls_fix_duplicate_lead_no.py
v1.1 (2026-09-02)

Fixes duplicate crm_lead_no values found by
cls_diag_duplicate_lead_no.py. Applies Srikanth's per-group rules
(2026-09-02 review of the diagnostic output):

  RULE 1 — Placeholder/test skip:
    If ANY row in the group has email_norm == 'optout@test.com' OR
    full_name == 'Opted Out Person' (case-insensitive), the ENTIRE
    group is skipped — no changes to any row in it. Flagged for
    Srikanth to handle deletion manually.

  RULE 2 — selldo_only vs meta:
    If the group is made up of exactly one row with source=
    'selldo_only' and one or more rows with source='meta' (and no
    other sources), the meta row(s) keep their current crm_lead_no.
    The selldo_only row is reassigned to the next free crm_lead_no.
    Edge case: if there is more than one meta row, the earliest meta
    row (by cls_created_at) is the keeper; any OTHER meta rows are
    renumbered too, same as the selldo_only row.

  RULE 3 — same-source fallback:
    Anything not covered by Rule 1 or Rule 2 (typically: all rows in
    the group share the same source). The row with the EARLIEST
    cls_created_at keeps its number; every other row in the group is
    reassigned to the next free crm_lead_no.

Across the whole run, "next free crm_lead_no" is computed once up
front and incremented as each renumber is assigned, so multiple
fixes in one run can't collide with each other.

Every actual renumber (Rule 2 or Rule 3) writes an activity_log row
on the affected lead via cls_db._log_activity() so there's a
permanent audit trail of what changed and why.

USAGE:
    python cls_fix_duplicate_lead_no.py --dry-run   (default, safe)
    python cls_fix_duplicate_lead_no.py --commit     (writes)

CHANGELOG:
  v1.1 (2026-09-02) — replaced flat "earliest row wins" logic with
    Rule 1/2/3 above, per Srikanth's review of the Phase 1 diagnostic
    output (11 groups: 1 flagged placeholder/test row skipped via
    Rule 1, 8 selldo_only/meta pairs via Rule 2, 2 genuine near-
    simultaneous Meta webhook/polling races — #8443, #8447 — via
    Rule 3).
  v1.0 (2026-09-02) — initial version (flat earliest-wins).
"""
import sys
import argparse
import cls_db

def safe_print(*a, **k):
    if sys.stdout is not None:
        print(*a, **k)

def _is_placeholder_row(r):
    email = (r["email_norm"] or "").strip().lower()
    name = (r["full_name"] or "").strip().lower()
    return email == "optout@test.com" or name == "opted out person"

def classify_group(rows):
    """
    rows: list of sqlite3.Row, already ordered by cls_created_at ASC.
    Returns one of:
      ("skip", rows)
      ("rule2", keeper_row, [(row, reason), ...])
      ("rule3", keeper_row, [(row, reason), ...])
    """
    if any(_is_placeholder_row(r) for r in rows):
        return ("skip", rows, None)

    sources = {r["source"] for r in rows}
    selldo_rows = [r for r in rows if r["source"] == "selldo_only"]
    meta_rows = [r for r in rows if r["source"] == "meta"]

    if len(selldo_rows) == 1 and len(meta_rows) >= 1 and sources <= {"selldo_only", "meta"}:
        meta_rows_sorted = sorted(meta_rows, key=lambda r: r["cls_created_at"])
        keeper = meta_rows_sorted[0]
        to_renumber = [(selldo_rows[0], "selldo_only vs meta")]
        for extra_meta in meta_rows_sorted[1:]:
            to_renumber.append((extra_meta, "selldo_only vs meta, extra meta row"))
        return ("rule2", keeper, to_renumber)

    # Rule 3 fallback — rows already ordered by cls_created_at ASC.
    keeper = rows[0]
    to_renumber = [(r, "same-source earliest-wins") for r in rows[1:]]
    return ("rule3", keeper, to_renumber)

def _describe(rule, keeper, row, old_no, new_no, all_meta):
    if rule == "rule2":
        if row["source"] == "selldo_only":
            return (f"Renumbered from duplicate #{old_no} to #{new_no} — "
                     f"stale selldo_only row, Meta lead #{old_no} kept its "
                     f"number (rule: selldo_only vs meta, 2026-09-02 fix).")
        else:
            return (f"Renumbered from duplicate #{old_no} to #{new_no} — "
                     f"later of multiple Meta rows in this group, earliest "
                     f"Meta lead #{old_no} kept its number (rule: selldo_only "
                     f"vs meta, extra meta row, 2026-09-02 fix).")
    # rule3
    if all_meta:
        return (f"Renumbered from duplicate #{old_no} to #{new_no} — later "
                 f"of two near-simultaneous Meta webhook/polling inserts "
                 f"(rule: same-source earliest-wins, 2026-09-02 fix).")
    return (f"Renumbered from duplicate #{old_no} to #{new_no} — later "
             f"duplicate sharing source '{row['source']}', earliest row "
             f"kept #{old_no} (rule: same-source earliest-wins, "
             f"2026-09-02 fix).")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true",
                         help="Actually write changes. Default is dry-run.")
    args = parser.parse_args()
    dry_run = not args.commit

    conn = cls_db._connect()
    try:
        dupes = conn.execute("""
            SELECT crm_lead_no FROM leads
            WHERE crm_lead_no IS NOT NULL
            GROUP BY crm_lead_no HAVING COUNT(*) > 1
            ORDER BY crm_lead_no
        """).fetchall()

        if not dupes:
            safe_print("No duplicates found. Nothing to do.")
            return

        next_free = conn.execute(
            "SELECT COALESCE(MAX(crm_lead_no), 0) m FROM leads"
        ).fetchone()["m"] + 1

        skipped_groups = []
        renumber_plan = []  # list of dicts per group for printing
        write_ops = []      # list of dicts: cls_id, full_name, old_no, new_no, description

        for d in dupes:
            lead_no = d["crm_lead_no"]
            rows = conn.execute("""
                SELECT cls_id, full_name, email_norm, source,
                       current_stage, cls_created_at
                FROM leads WHERE crm_lead_no = ?
                ORDER BY cls_created_at ASC
            """, (lead_no,)).fetchall()

            rule, keeper, to_renumber = classify_group(rows)

            if rule == "skip":
                skipped_groups.append((lead_no, rows))
                continue

            all_meta = all(r["source"] == "meta" for r in rows)
            group_entry = {
                "lead_no": lead_no,
                "rule": rule,
                "keeper": keeper,
                "assignments": [],
            }
            for row, reason in to_renumber:
                new_no = next_free
                next_free += 1
                description = _describe(rule, keeper, row, lead_no, new_no, all_meta)
                group_entry["assignments"].append({
                    "row": row, "old_no": lead_no, "new_no": new_no,
                    "reason": reason, "description": description,
                })
                write_ops.append({
                    "cls_id": row["cls_id"], "full_name": row["full_name"],
                    "old_no": lead_no, "new_no": new_no,
                    "description": description,
                })
            renumber_plan.append(group_entry)

        # ---- print plan ----
        safe_print(f"{'DRY RUN — ' if dry_run else ''}Duplicate crm_lead_no fix plan")
        safe_print(f"({len(renumber_plan)} group(s) to renumber, "
                    f"{len(skipped_groups)} group(s) skipped, "
                    f"{len(dupes)} total duplicated crm_lead_no values)\n")

        safe_print("=" * 70)
        safe_print("RENUMBER PLAN")
        safe_print("=" * 70)
        for g in renumber_plan:
            safe_print(f"\ncrm_lead_no = {g['lead_no']}  (rule: {g['rule']})")
            k = g["keeper"]
            safe_print(f"  KEEP unchanged : {k['full_name']!r} "
                        f"(cls_id={k['cls_id']}, source={k['source']}, "
                        f"created={k['cls_created_at']}) stays #{g['lead_no']}")
            for a in g["assignments"]:
                r = a["row"]
                safe_print(f"  RENUMBER       : {r['full_name']!r} "
                            f"(cls_id={r['cls_id']}, source={r['source']}, "
                            f"created={r['cls_created_at']}) "
                            f"#{a['old_no']} -> #{a['new_no']}  [{a['reason']}]")

        safe_print("\n" + "=" * 70)
        safe_print("SKIPPED — FLAGGED FOR MANUAL REVIEW (Rule 1: placeholder/test row)")
        safe_print("=" * 70)
        if not skipped_groups:
            safe_print("\n(none)")
        for lead_no, rows in skipped_groups:
            safe_print(f"\ncrm_lead_no = {lead_no}  — NO CHANGES MADE")
            for r in rows:
                safe_print(f"  cls_id={r['cls_id']}  full_name={r['full_name']!r}  "
                            f"email_norm={r['email_norm']!r}  source={r['source']}")

        if dry_run:
            safe_print("\nDry run only — no changes made. "
                        "Re-run with --commit to apply.")
            return

        now = cls_db._now()
        for op in write_ops:
            conn.execute(
                "UPDATE leads SET crm_lead_no=?, cls_updated_at=? "
                "WHERE cls_id=?",
                (op["new_no"], now, op["cls_id"])
            )
            cls_db._log_activity(
                conn, op["cls_id"], "lead_no_corrected", "system_diagnostic",
                prev_value=str(op["old_no"]), new_value=str(op["new_no"]),
                description=op["description"]
            )
        conn.commit()
        safe_print(f"\nCommitted {len(write_ops)} renumber(s) across "
                    f"{len(renumber_plan)} group(s). "
                    f"{len(skipped_groups)} group(s) left untouched for manual review.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
