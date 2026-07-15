"""
=============================================================
cls_telecaller_report.py  —  CLS Telecaller Weekend Report
=============================================================
Version : 1.1
Author  : Built for Asian Properties / Srikanth

WHAT CHANGED IN v1.1
--------------------
- Column 2 added: Sell.do CRM ID (selldo_lead_id)
- Column 2 is a clickable link to the lead's Sell.do profile when
  the URL is available (extracted from =HYPERLINK() in Job B).
  Leads synced before v1.3 of cls_db.py show the ID as plain text
  until the next Job B run populates selldo_url.
- Plain-text log summary updated to include CRM ID column.

WHAT THIS SCRIPT DOES
---------------------
Queries cls.db for all leads currently in the 'Opportunity' stage
across ALL projects, formats them into a clean HTML email, and
sends it to the telecaller's inbox via Brevo.

The telecaller receives this email every Saturday and Sunday morning
at 09:00 AM, before site visits begin. She uses it to call leads
who are scheduled for a site visit that day — offloading the follow-up
work from the executive (Elohar / project-specific) who is busy
conducting visits on the ground.

WHY 'Opportunity' STAGE ONLY
-----------------------------
In Sell.do, 'Opportunity' = site visit scheduled. This is the
actionable pool for the telecaller:
  - Prospect     -> not yet scheduled; executive is still working them
  - Opportunity  -> SCHEDULED; telecaller confirms they're coming
  - Site Visited -> already done; no call needed

WHY THIS IS STANDALONE (NOT PART OF THE A-B-C CHAIN)
------------------------------------------------------
Jobs A, B, C form a data pipeline triggered by Meta and Sell.do.
This script serves a completely different audience (telecaller, not
Meta CAPI) on a different schedule (weekends only, fixed time).
Chaining it into the pipeline would complicate the flag logic for
no gain. It runs independently via its own Task Scheduler entry.

SCHEDULE (Task Scheduler -- add two separate entries)
------------------------------------------------------
  Saturday  09:00 AM  python C:\\CLS\\cls_telecaller_report.py
  Sunday    09:00 AM  python C:\\CLS\\cls_telecaller_report.py

ONE-TIME SETUP
--------------
  1. Add TELECALLER_EMAIL=telecaller@example.com to C:\\CLS\\.env
  2. No new pip installs -- uses sib-api-v3-sdk already installed for Job D.

RUN
---
  python cls_telecaller_report.py             # normal run (sends email)
  python cls_telecaller_report.py --dry-run   # print report; no email sent
  python cls_telecaller_report.py --selftest  # offline checks; no DB needed
=============================================================
"""

import os
import sys
from datetime import datetime

import cls_db

# -------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------

BASE_DIR = r"C:\CLS"
ENV_FILE = os.path.join(BASE_DIR, ".env")
LOG_FILE = os.path.join(BASE_DIR, "cls_telecaller_log.txt")

SENDER_EMAIL = "sales1@asianbuild.in"
SENDER_NAME  = "Asian Properties -- CLS"

TELECALLER_EMAIL_KEY = "TELECALLER_EMAIL"


# -------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------

def log(msg, level="INFO"):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# -------------------------------------------------------------
# ENV LOADER
# -------------------------------------------------------------

def load_env():
    env = {}
    try:
        from dotenv import dotenv_values
        env = dict(dotenv_values(ENV_FILE))
    except ImportError:
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


# -------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------

def _esc(value):
    """Minimal HTML-escape for values inserted into HTML."""
    s = "" if value is None else str(value)
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _fmt_phone(raw):
    """
    Strip country code and return a clean 10-digit number for display.
    """
    if not raw:
        return "—"
    digits = "".join(c for c in str(raw) if c.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits if digits else str(raw)


def _fmt_date(ts):
    """
    Format stage_updated_at (YYYY-MM-DD HH:MM:SS) to short readable form.
    e.g. '2026-06-10 14:32:00' -> 'Wed, 10 Jun'
    """
    if not ts:
        return "—"
    try:
        dt = datetime.strptime(str(ts)[:16], "%Y-%m-%d %H:%M")
        return dt.strftime("%a, %d %b")
    except ValueError:
        return str(ts)[:10]


def _crm_cell(selldo_lead_id, selldo_url):
    """
    Build the HTML for the CRM ID cell.
    - If selldo_url is available: render as a blue clickable link with an
      arrow indicator (↗) so the telecaller can tap directly into Sell.do.
    - If no URL yet (leads synced before v1.3): show the numeric ID as
      plain grey text. Will upgrade automatically on the next Job B run.
    """
    cid = _esc(selldo_lead_id) if selldo_lead_id else "—"
    if selldo_url:
        url = _esc(selldo_url)
        return (
            f'<a href="{url}" target="_blank" '
            f'style="color:#1A6FC4;font-weight:bold;text-decoration:none;'
            f'font-family:Arial,sans-serif;font-size:13px;">'
            f'{cid}&nbsp;&#8599;</a>'
        )
    else:
        return (
            f'<span style="color:#999;font-family:Arial,sans-serif;'
            f'font-size:12px;">{cid}</span>'
        )


# -------------------------------------------------------------
# BUILD THE EMAIL
# -------------------------------------------------------------

def build_email(leads, report_date_str):
    """
    Build the HTML email body and a plain-text summary string.

    leads           : list of dicts from cls_db.get_opportunity_leads()
    report_date_str : e.g. 'Saturday, 14 June 2026'

    Returns (html_body, subject_line, plain_summary).
    """
    total = len(leads)
    subject = (
        f"Site Visit Follow-up List \u2014 {report_date_str} "
        f"({total} lead{'s' if total != 1 else ''})"
    )

    # Group leads by project
    projects_seen = []
    by_project    = {}
    for lead in leads:
        proj = lead.get("project") or "Unknown Project"
        if proj not in by_project:
            by_project[proj] = []
            projects_seen.append(proj)
        by_project[proj].append(lead)

    # Build table rows
    sections_html = ""
    row_serial    = 0

    for proj in projects_seen:
        proj_leads = by_project[proj]
        proj_count = len(proj_leads)

        # Project section header
        sections_html += (
            f'<tr>'
            f'<td colspan="6" style="background:#1F2A44;color:#ffffff;'
            f'font-family:Arial,sans-serif;font-size:13px;font-weight:bold;'
            f'padding:8px 12px;letter-spacing:0.5px;">'
            f'{_esc(proj)}&nbsp;&middot;&nbsp;'
            f'{proj_count} lead{"s" if proj_count != 1 else ""}'
            f'</td></tr>\n'
        )

        for lead in proj_leads:
            row_serial += 1
            bg        = "#F7F9FC" if row_serial % 2 == 0 else "#FFFFFF"
            name      = _esc(lead.get("full_name") or "—")
            phone     = _esc(_fmt_phone(lead.get("phone_raw", "")))
            owner     = _esc(lead.get("lead_owner") or "—")
            scheduled = _esc(_fmt_date(lead.get("stage_updated_at")))
            crm_html  = _crm_cell(
                lead.get("selldo_lead_id"),
                lead.get("selldo_url", "")
            )
            td = 'style="padding:9px 12px;border-bottom:1px solid #E8ECF0;'

            sections_html += (
                f'<tr style="background:{bg};">'
                f'<td {td}font-family:Arial,sans-serif;font-size:13px;color:#444;">'
                f'{row_serial}</td>'
                f'<td {td}">{crm_html}</td>'
                f'<td {td}font-family:Arial,sans-serif;font-size:13px;'
                f'color:#1A1A1A;font-weight:bold;">{name}</td>'
                f'<td {td}font-family:Arial,sans-serif;font-size:14px;'
                f'color:#1A1A1A;letter-spacing:0.3px;">{phone}</td>'
                f'<td {td}font-family:Arial,sans-serif;font-size:13px;'
                f'color:#555;">{owner}</td>'
                f'<td {td}font-family:Arial,sans-serif;font-size:12px;'
                f'color:#888;">{scheduled}</td>'
                f'</tr>\n'
            )

    # Empty state
    if total == 0:
        sections_html = (
            '<tr><td colspan="6" style="padding:24px;text-align:center;'
            'font-family:Arial,sans-serif;font-size:14px;color:#888;">'
            'No leads are currently scheduled for a site visit.<br>'
            'No calls needed today.</td></tr>\n'
        )

    # Column header row
    th = ('style="padding:9px 12px;text-align:left;font-family:Arial,sans-serif;'
          'font-size:11px;font-weight:bold;color:#888;'
          'text-transform:uppercase;letter-spacing:0.6px;"')

    header_row = (
        f'<tr style="background:#EEF1F6;">'
        f'<th {th}>#</th>'
        f'<th {th}>CRM ID</th>'
        f'<th {th}>Name</th>'
        f'<th {th}>Phone</th>'
        f'<th {th}>Executive</th>'
        f'<th {th}>Scheduled</th>'
        f'</tr>\n'
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#F0F2F5;">

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#F0F2F5;padding:24px 0;">
  <tr><td align="center">

    <table width="640" cellpadding="0" cellspacing="0" border="0"
           style="background:#ffffff;border-radius:8px;
                  box-shadow:0 2px 8px rgba(0,0,0,0.08);
                  max-width:640px;width:100%;">

      <!-- Header -->
      <tr>
        <td style="background:#1F2A44;border-radius:8px 8px 0 0;padding:20px 24px;">
          <p style="margin:0;font-family:Arial,sans-serif;font-size:18px;
                    font-weight:bold;color:#ffffff;">Site Visit Follow-up List</p>
          <p style="margin:4px 0 0;font-family:Arial,sans-serif;font-size:13px;
                    color:#A8BAD8;">
            {_esc(report_date_str)}&nbsp;&middot;&nbsp;
            {total} lead{'s' if total != 1 else ''} scheduled
          </p>
        </td>
      </tr>

      <!-- Instruction -->
      <tr>
        <td style="padding:16px 24px 8px;">
          <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;
                    color:#555;line-height:1.6;">
            These leads are scheduled for a site visit today. Please call each one
            to confirm they are coming, note their ETA, and inform the executive on
            site. Tap the CRM ID to open the lead directly in Sell.do. If someone
            cannot make it, ask them to reschedule and let the executive know.
          </p>
        </td>
      </tr>

      <!-- Lead table -->
      <tr>
        <td style="padding:8px 24px 0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="border-collapse:collapse;border:1px solid #E8ECF0;
                        border-radius:6px;overflow:hidden;">
            {header_row}
            {sections_html}
          </table>
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="padding:16px 24px 24px;">
          <p style="margin:0;font-family:Arial,sans-serif;font-size:11px;
                    color:#AAAAAA;line-height:1.5;">
            Automated report from CLS. Data reflects the latest Sell.do sync.
            If a lead was rescheduled after the last sync, check the executive's
            Sell.do view. CRM ID links open the lead profile directly in Sell.do.
          </p>
        </td>
      </tr>

    </table>

  </td></tr>
</table>

</body>
</html>"""

    # Plain-text summary for log
    plain_lines = [f"TELECALLER REPORT -- {report_date_str}", "=" * 60]
    for proj in projects_seen:
        plain_lines.append(f"\n[{proj}]")
        for lead in by_project[proj]:
            nm  = lead.get("full_name") or "—"
            ph  = _fmt_phone(lead.get("phone_raw", ""))
            cid = lead.get("selldo_lead_id") or "—"
            own = lead.get("lead_owner") or "—"
            sch = _fmt_date(lead.get("stage_updated_at"))
            plain_lines.append(f"  {cid:<8} {nm:<25} {ph:<15} {own:<15} {sch}")
    if total == 0:
        plain_lines.append("  No leads scheduled -- no calls needed.")
    plain_summary = "\n".join(plain_lines)

    return html, subject, plain_summary


# -------------------------------------------------------------
# SEND VIA BREVO
# -------------------------------------------------------------

def send_via_brevo(brevo_key, to_email, subject, html_body):
    try:
        import sib_api_v3_sdk
        cfg = sib_api_v3_sdk.Configuration()
        cfg.api_key["api-key"] = brevo_key
        api = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(cfg))

        send_smtp = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email, "name": "Telecaller"}],
            sender={"email": SENDER_EMAIL, "name": SENDER_NAME},
            subject=subject,
            html_content=html_body,
        )
        resp  = api.send_transac_email(send_smtp)
        msg_id = getattr(resp, "message_id", str(resp))
        return True, msg_id
    except Exception as e:
        return False, str(e)


# -------------------------------------------------------------
# MAIN RUN
# -------------------------------------------------------------

def run(dry_run=False):
    log("=" * 55)
    log(f"CLS TELECALLER REPORT -- {'DRY RUN' if dry_run else 'LIVE'}")
    log("=" * 55)

    env = load_env()
    brevo_key        = env.get("BREVO_API_KEY", "")
    telecaller_email = env.get(TELECALLER_EMAIL_KEY, "")

    if not brevo_key:
        log("BREVO_API_KEY missing in .env -- aborting.", "ERROR")
        return False
    if not telecaller_email:
        log(f"{TELECALLER_EMAIL_KEY} missing in .env -- aborting.", "ERROR")
        log("Add a line like:  TELECALLER_EMAIL=priya@gmail.com", "ERROR")
        return False

    log(f"Telecaller email: {telecaller_email}")

    cls_db.init_db()
    leads = cls_db.get_opportunity_leads()
    log(f"Opportunity leads found: {len(leads)}")

    today           = datetime.now()
    report_date_str = today.strftime("%A, %d %B %Y")
    html_body, subject, plain_summary = build_email(leads, report_date_str)

    log("-" * 55)
    for line in plain_summary.splitlines():
        log(line)
    log("-" * 55)

    if dry_run:
        log("DRY RUN -- email not sent.")
        log("=" * 55)
        return True

    log(f"Sending via Brevo to {telecaller_email}...")
    ok, result = send_via_brevo(brevo_key, telecaller_email, subject, html_body)
    if ok:
        log(f"Email sent successfully. Brevo message_id: {result}")
    else:
        log(f"Email send FAILED: {result}", "ERROR")

    log("=" * 55)
    log("CLS TELECALLER REPORT -- DONE")
    log("=" * 55)
    return ok


# -------------------------------------------------------------
# SELF-TEST  --  offline; no DB, no API
# -------------------------------------------------------------

def selftest():
    print("=" * 55)
    print(" CLS TELECALLER REPORT v1.1 -- SELF TEST (offline)")
    print("=" * 55)

    # _fmt_phone
    cases = [
        ("919876543210", "9876543210"),
        ("9876543210",   "9876543210"),
        ("+919876543210","9876543210"),
        ("",             "—"),
    ]
    for raw, expected in cases:
        got = _fmt_phone(raw)
        got_d = "".join(c for c in got if c.isdigit())
        exp_d = "".join(c for c in expected if c.isdigit())
        ok = (got_d == exp_d) if exp_d else (got == expected)
        print(f"  [{'OK' if ok else 'FAIL'}] _fmt_phone({raw!r}) -> {got!r}")

    # _fmt_date
    for ts in ["2026-06-14 09:30:00", "", None]:
        result = _fmt_date(ts)
        ok = isinstance(result, str) and len(result) > 0
        print(f"  [{'OK' if ok else 'FAIL'}] _fmt_date({str(ts)!r}) -> {result!r}")

    # _crm_cell — with URL
    cell_with = _crm_cell("7340", "https://app.sell.do/leads/AbCdEf/overview")
    ok = "7340" in cell_with and "app.sell.do" in cell_with and "href" in cell_with
    print(f"  [{'OK' if ok else 'FAIL'}] _crm_cell with URL -> clickable link")

    # _crm_cell — without URL
    cell_without = _crm_cell("5891", "")
    ok = "5891" in cell_without and "href" not in cell_without
    print(f"  [{'OK' if ok else 'FAIL'}] _crm_cell without URL -> plain text")

    # build_email
    sample_leads = [
        {"full_name": "Ravi Kumar",  "phone_raw": "919876543210",
         "lead_owner": "Elohar",    "project": "Naishka",
         "selldo_lead_id": "7340",
         "selldo_url": "https://app.sell.do/leads/AbCdEfGhIj/overview",
         "stage_updated_at": "2026-06-12 10:00:00"},
        {"full_name": "Sita Reddy", "phone_raw": "9000000001",
         "lead_owner": "Mahesh",    "project": "Grace Classic",
         "selldo_lead_id": "4210",
         "selldo_url": "https://app.sell.do/leads/KlMnOpQrSt/overview",
         "stage_updated_at": "2026-06-11 15:30:00"},
        {"full_name": "Arjun Rao",  "phone_raw": "919988776655",
         "lead_owner": "",          "project": "Prima Paradiso",
         "selldo_lead_id": "5891",
         "selldo_url": "",
         "stage_updated_at": "2026-06-10 08:00:00"},
    ]
    html, subject, plain = build_email(sample_leads, "Saturday, 14 June 2026")

    ok = "Site Visit Follow-up List" in subject and "14 June 2026" in subject
    print(f"  [{'OK' if ok else 'FAIL'}] Subject line correct: {subject!r}")

    ok = "Ravi Kumar" in html and "9876543210" in html
    print(f"  [{'OK' if ok else 'FAIL'}] HTML contains lead name + clean phone")

    ok = "7340" in html and "4210" in html and "5891" in html
    print(f"  [{'OK' if ok else 'FAIL'}] HTML contains all Sell.do lead IDs")

    ok = "app.sell.do/leads/AbCdEfGhIj/overview" in html
    print(f"  [{'OK' if ok else 'FAIL'}] HTML contains clickable Sell.do URL")

    ok = "&#8599;" in html   # ↗ arrow for linked leads
    print(f"  [{'OK' if ok else 'FAIL'}] Link arrow present for leads with URL")

    ok = "href" not in _crm_cell("5891", "")
    print(f"  [{'OK' if ok else 'FAIL'}] No link for leads without URL (plain text)")

    ok = "Elohar" in html and "Mahesh" in html
    print(f"  [{'OK' if ok else 'FAIL'}] HTML contains executive names")

    ok = "Naishka" in html and "Grace Classic" in html and "Prima Paradiso" in html
    print(f"  [{'OK' if ok else 'FAIL'}] HTML contains all three project sections")

    ok = "CRM ID" in html
    print(f"  [{'OK' if ok else 'FAIL'}] CRM ID column header present")

    # Zero-lead state
    html0, subj0, _ = build_email([], "Sunday, 15 June 2026")
    ok = "0 lead" in subj0 and "No leads" in html0
    print(f"  [{'OK' if ok else 'FAIL'}] Zero-lead state handled correctly")

    ok = html.strip().startswith("<!DOCTYPE html>") and "</html>" in html
    print(f"  [{'OK' if ok else 'FAIL'}] HTML structure valid")

    print("=" * 55)
    print(" SELF TEST COMPLETE")
    print("=" * 55)
    print()
    print("Next: python cls_telecaller_report.py --dry-run")


# -------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
    elif "--dry-run" in args:
        run(dry_run=True)
    else:
        run(dry_run=False)
