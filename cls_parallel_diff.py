"""
=============================================================
cls_parallel_diff.py  —  CLS1 vs CLS2 Parallel-Run Comparison
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

PURPOSE
-------
Compares CLS1.db ("our own CRM" — fed by Job A + the CRM app) against
CLS2.db (the Sell.do mirror — fed only by Job B) and reports, in plain
English, where the two disagree or where one has a lead the other
doesn't. Run manually whenever a read is wanted — NOT scheduled
alongside Jobs A-D.

Read-only. The ONLY database call this script makes is
cls_db.get_leads_snapshot(db_path), called once against CLS1.db and
once against CLS2.db — no direct sqlite3 access, no new DB functions
beyond what cls_db.py v2.23 already provides.

MATCHING LOGIC
--------------
Leads are matched between the two databases by phone_norm, falling
back to email_norm when phone_norm is blank on either side — NOT by
cls_id. Most Meta-sourced leads exist in BOTH databases under
DIFFERENT cls_id values: Job A gave a lead one cls_id in CLS1; Job B
independently creates a new row for the same person in CLS2, since
CLS2 never receives Job A's cls_id.

OUTPUT — three sections, full lead detail (not just counts)
-------------------------------------------------------------
  1. STAGE DIFFERS      — matched leads where current_stage differs.
  2. NOT YET IN YOUR CRM — in CLS2 (Sell.do), no match in CLS1. These
     are walk-ins/referrals/other-source leads sitting in Sell.do that
     were never entered into the new CRM.
  3. NOT YET IN SELL.DO  — in CLS1, no match in CLS2. Usually EXPECTED/
     benign: brand-new Meta leads Job A just pulled that Sell.do's own
     Meta integration hasn't ingested yet — not necessarily a problem.

Full report written to C:\\CLS\\parallel_diff_report.txt, overwritten
on every run (not timestamped/accumulating). A short count-only summary
is printed to the console, pointing at the file for detail.

RUN
---
  python cls_parallel_diff.py
=============================================================
"""

import os
from datetime import datetime

import cls_db   # the foundation layer — the ONLY way this script touches either DB

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR    = r"C:\CLS"
CLS1_PATH   = os.path.join(BASE_DIR, "CLS1.db")
CLS2_PATH   = os.path.join(BASE_DIR, "CLS2.db")
REPORT_FILE = os.path.join(BASE_DIR, "parallel_diff_report.txt")


def _p(msg=""):
    # Guard against pythonw.exe setting sys.stdout = None — harmless
    # no-op if stdout isn't available. This script is normally run
    # manually via python.exe, but guard anyway per house convention.
    try:
        print(msg)
    except Exception:
        pass


def _lead_line(lead):
    """One lead's display fields, reused across all three sections."""
    apx_id = f"APX-{lead['crm_lead_no']}" if lead.get("crm_lead_no") else "(no APX id)"
    phone  = lead.get("phone_raw") or lead.get("phone_norm") or "(no phone)"
    return apx_id, lead.get("full_name") or "(no name)", phone, lead.get("project") or "(no project)"


def build_lookup(leads, key):
    """Map key-field value -> lead dict, skipping blank keys. Last row wins on collision."""
    return {l[key]: l for l in leads if l.get(key)}


def compare(cls1_leads, cls2_leads):
    cls2_by_phone = build_lookup(cls2_leads, "phone_norm")
    cls2_by_email = build_lookup(cls2_leads, "email_norm")

    stage_matches   = 0
    stage_differs   = []   # [(cls1_lead, cls2_lead), ...]
    matched_cls2_ids = set()
    not_in_selldo   = []   # CLS1 leads with no CLS2 match

    for lead in cls1_leads:
        match = None
        if lead.get("phone_norm") and lead["phone_norm"] in cls2_by_phone:
            match = cls2_by_phone[lead["phone_norm"]]
        elif lead.get("email_norm") and lead["email_norm"] in cls2_by_email:
            match = cls2_by_email[lead["email_norm"]]

        if match is None:
            not_in_selldo.append(lead)
            continue

        matched_cls2_ids.add(match["cls_id"])
        if (lead.get("current_stage") or "") != (match.get("current_stage") or ""):
            stage_differs.append((lead, match))
        else:
            stage_matches += 1

    not_in_crm = [l for l in cls2_leads if l["cls_id"] not in matched_cls2_ids]

    return stage_matches, stage_differs, not_in_crm, not_in_selldo


def write_report(stage_matches, stage_differs, not_in_crm, not_in_selldo):
    lines = []
    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p").lstrip("0")
    lines.append(f"Parallel-Run Check — {now_str}")
    lines.append(f"{stage_matches} leads match on stage.")
    lines.append(f"{len(stage_differs)} leads have a different stage in your CRM vs Sell.do.")
    lines.append(f"{len(not_in_crm)} leads are in Sell.do but not yet in your CRM.")
    lines.append(f"{len(not_in_selldo)} leads are brand new in your CRM, not in Sell.do yet (expected).")
    lines.append("")

    lines.append("=" * 60)
    lines.append("SECTION 1 — Stage differs between your CRM and Sell.do")
    lines.append("=" * 60)
    if not stage_differs:
        lines.append("(none)")
    for cls1_lead, cls2_lead in stage_differs:
        apx_id, name, phone, project = _lead_line(cls1_lead)
        lines.append("")
        lines.append(f"{apx_id} — {name}")
        lines.append(f"  Phone: {phone}   Project: {project}")
        lines.append(f"  Your CRM: {cls1_lead.get('current_stage') or '(blank)'}"
                      f"  (owner: {cls1_lead.get('lead_owner') or '(unassigned)'})")
        lines.append(f"  Sell.do:  {cls2_lead.get('current_stage') or '(blank)'}"
                      f"  (owner: {cls2_lead.get('lead_owner') or '(unassigned)'})")
    lines.append("")

    lines.append("=" * 60)
    lines.append("SECTION 2 — In Sell.do but not yet in your CRM")
    lines.append("(walk-ins / referrals / other-source leads Sell.do has that never made it into the CRM)")
    lines.append("=" * 60)
    if not not_in_crm:
        lines.append("(none)")
    for lead in not_in_crm:
        _, name, phone, project = _lead_line(lead)
        lines.append("")
        lines.append(f"{name}")
        lines.append(f"  Phone: {phone}   Project: {project}")
        lines.append(f"  Sell.do stage: {lead.get('current_stage') or '(blank)'}"
                      f"   Sell.do owner: {lead.get('lead_owner') or '(unassigned)'}")
    lines.append("")

    lines.append("=" * 60)
    lines.append("SECTION 3 — In your CRM but not yet in Sell.do (usually expected)")
    lines.append("(brand-new Meta leads Job A just pulled — Sell.do's own Meta integration")
    lines.append(" hasn't ingested them yet. Not necessarily a problem.)")
    lines.append("=" * 60)
    if not not_in_selldo:
        lines.append("(none)")
    for lead in not_in_selldo:
        apx_id, name, phone, project = _lead_line(lead)
        lines.append("")
        lines.append(f"{apx_id} — {name}")
        lines.append(f"  Phone: {phone}   Project: {project}")
        lines.append(f"  Your CRM stage: {lead.get('current_stage') or '(blank)'}"
                      f"   Owner: {lead.get('lead_owner') or '(unassigned)'}")

    with open(REPORT_FILE, "w", encoding="utf-8", errors="replace") as f:
        f.write("\n".join(lines) + "\n")


def main():
    for label, path in (("CLS1.db", CLS1_PATH), ("CLS2.db", CLS2_PATH)):
        if not os.path.exists(path):
            _p(f"[FAIL] {label} not found at {path}. Nothing to compare.")
            return

    cls1_leads = cls_db.get_leads_snapshot(CLS1_PATH)
    cls2_leads = cls_db.get_leads_snapshot(CLS2_PATH)

    stage_matches, stage_differs, not_in_crm, not_in_selldo = compare(cls1_leads, cls2_leads)
    write_report(stage_matches, stage_differs, not_in_crm, not_in_selldo)

    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p").lstrip("0")
    _p(f"Parallel-Run Check — {now_str}")
    _p(f"✅ {stage_matches} leads match on stage.")
    _p(f"⚠️  {len(stage_differs)} leads have a different stage in your CRM vs Sell.do.")
    _p(f"📋 {len(not_in_crm)} leads are in Sell.do but not yet in your CRM.")
    _p(f"ℹ️  {len(not_in_selldo)} leads are brand new in your CRM, not in Sell.do yet (expected).")
    _p(f"Full details in {REPORT_FILE}")


if __name__ == "__main__":
    main()
