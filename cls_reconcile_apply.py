"""
=============================================================
cls_reconcile_apply.py  —  ONE-TIME Parallel-Run Reconciliation
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth
Date    : 2026-08-14

PURPOSE
-------
One-time correction of 41 leads' current_stage, per Srikanth's
manual review of the 14 Aug 2026 08:47 PM parallel_diff_report.txt.
NOT a recurring job — do not schedule this. Run once, verify, retire.

WHY THIS BYPASSES STAGE_TRANSITIONS
------------------------------------
The normal update_lead_stage() path enforces STAGE_TRANSITIONS to stop
a salesperson from skipping steps in a LIVE sale. This script is not
simulating a live click-through — it's correcting cls.db to reflect
what has ALREADY happened (confirmed via Sell.do or via Srikanth's own
read of the CRM's terminal-stage call). Direct write via
cls_db.direct_set_stage_reconciliation() (added in cls_db.py v2.54),
whitelist check intentionally skipped here only.

SAFETY MODEL
------------
1. DRY-RUN BY DEFAULT. Run with no flags first — it shows exactly what
   would change, AND checks each lead's CURRENT stage against the
   'expected_before' value baked in below (captured at report time).
   If a lead has moved since 08:47 PM, it is SKIPPED with a warning
   rather than blindly overwritten.
2. Nothing is written until --apply is passed.
3. Every write is logged to activity_log (activity_type=
   'reconciliation_correction', actor tagged below) via cls_db's own
   _log_activity() helper — same pattern update_lead_stage() uses.
4. NO CAPI FIRING HAPPENS HERE. That is a deliberate, separate step —
   run cls_capi_firer.py --catchup AFTER this script and after the
   full reconciliation (including APX-421/APX-8053) is resolved.

RUN
---
  python cls_reconcile_apply.py            # dry-run — shows what would change
  python cls_reconcile_apply.py --apply    # actually writes + logs
=============================================================
"""

import sys
import cls_db

ACTOR_TAG = "reconciliation_2026-08-14"

# ── crm_lead_no : (expected_before_stage, target_stage) ──
# expected_before is the stage the 08:47 PM report showed. If the LIVE
# stage no longer matches this, the lead is skipped — it moved since
# the report ran and needs a fresh look, not a blind overwrite.
CORRECTIONS = {
    # ── Section A — clear funnel-forward (Sell.do was ahead) ──
    6882: ("Incoming", "Opportunity"),   # bypasses STAGE_TRANSITIONS — see note above
    6671: ("Incoming", "Prospect"),
    6338: ("Incoming", "Prospect"),
    5807: ("Prospect", "Opportunity"),
    5802: ("Incoming", "Prospect"),
    7824: ("Incoming", "Prospect"),
    3807: ("Incoming", "Prospect"),
    2933: ("Incoming", "Prospect"),
    7952: ("Prospect", "Opportunity"),
    7961: ("Incoming", "Prospect"),
    7969: ("Incoming", "Prospect"),
    8036: ("Incoming", "Prospect"),
    8051: ("Incoming", "Prospect"),
    8074: ("Incoming", "Prospect"),
    8101: ("Incoming", "Prospect"),
    8113: ("Incoming", "Prospect"),
    8116: ("Incoming", "Prospect"),
    8125: ("Incoming", "Prospect"),
    8140: ("Incoming", "Prospect"),
    8155: ("Incoming", "Prospect"),
    8156: ("Incoming", "Prospect"),
    8181: ("Incoming", "Opportunity"),   # bypasses STAGE_TRANSITIONS — see note above

    # ── C3 — CRM: Incoming / Sell.do: Unqualified — Sell.do final ──
    6798: ("Incoming", "Unqualified"),
    5206: ("Incoming", "Unqualified"),
    3427: ("Incoming", "Unqualified"),
    5975: ("Incoming", "Unqualified"),
    7795: ("Incoming", "Unqualified"),
    4267: ("Incoming", "Unqualified"),
    3908: ("Incoming", "Unqualified"),
    8003: ("Incoming", "Unqualified"),
    8043: ("Incoming", "Unqualified"),

    # ── C9 — CRM: Opportunity / Sell.do: Lost — Sell.do final ──
    6544: ("Opportunity", "Lost"),
    7668: ("Opportunity", "Lost"),
    8001: ("Opportunity", "Lost"),

    # ── C10 — CRM: Prospect / Sell.do: Unqualified — Sell.do final ──
    7849: ("Prospect", "Unqualified"),
    7863: ("Prospect", "Unqualified"),

    # ── C11 — CRM: Prospect / Sell.do: Lost — Sell.do final ──
    3295: ("Prospect", "Lost"),
    7947: ("Prospect", "Lost"),

    # ── C12 — single-occurrence patterns — Sell.do final ──
    5762: ("Re Assigned", "Prospect"),
    7694: ("Lost", "Re Assigned"),
    8064: ("Unqualified", "Opportunity"),
}


def log(msg):
    try:
        print(msg)
    except Exception:
        pass


def run(apply=False):
    log("=" * 55)
    log(f"CLS RECONCILE APPLY — {'LIVE APPLY' if apply else 'DRY RUN'}")
    log("=" * 55)

    cls_db.init_db()
    applied = skipped = missing = 0

    for crm_lead_no, (expected_before, target) in CORRECTIONS.items():
        lead = cls_db.get_lead_by_crm_no(crm_lead_no)
        if not lead:
            log(f"  [MISSING] APX-{crm_lead_no} — no lead found with this crm_lead_no")
            missing += 1
            continue

        current = lead.get("current_stage")
        if current != expected_before:
            log(f"  [SKIP] APX-{crm_lead_no} — expected '{expected_before}' but live "
                f"stage is '{current}'. Moved since the report ran — needs a fresh look.")
            skipped += 1
            continue

        if not apply:
            log(f"  [WOULD APPLY] APX-{crm_lead_no} — {current} -> {target}")
            applied += 1
            continue

        cls_db.direct_set_stage_reconciliation(
            lead["cls_id"], target, actor=ACTOR_TAG, prev_value=current
        )
        log(f"  [APPLIED] APX-{crm_lead_no} — {current} -> {target}")
        applied += 1

    log("-" * 55)
    log(f"{'Would apply' if not apply else 'Applied'}: {applied}  |  "
        f"Skipped (moved since report): {skipped}  |  Missing: {missing}")
    if not apply:
        log("This was a DRY RUN — nothing was written. Re-run with --apply to commit.")
    log("=" * 55)


if __name__ == "__main__":
    run(apply=("--apply" in sys.argv[1:]))
