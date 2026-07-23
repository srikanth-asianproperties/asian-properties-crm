"""
=============================================================
selldo_to_cls.py  —  CLS Job B  |  Sell.do CRM -> CLS Sync
=============================================================
Version : 1.6
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.6  (July 2026) — 7-minute no-fail Gmail polling window (Task Scheduler
  trigger move :10 -> :02, external change, not in this file):
  CHANGE — MAX_ATTEMPTS : 6 -> 13
    Job B must now poll for a full 7 minutes (420s) total, without fail.
    Formula: EMAIL_WAIT_SECS (60) + (MAX_ATTEMPTS - 1) x CHECK_INTERVAL
    = 60 + 12x30 = 420s = 7 minutes exactly, checked every 30 seconds
    throughout. EMAIL_WAIT_SECS (60) and CHECK_INTERVAL (30) unchanged.
  FIX — fetch_csv_from_gmail()'s IMAP connection block used to return
    None (give up entirely) on the FIRST connection failure, regardless
    of how many attempts remained. A single transient Gmail hiccup could
    end the whole widened 7-minute window early. Now a connection failure
    on any attempt logs a WARNING and falls through to the same
    wait-CHECK_INTERVAL-and-retry path as a normal not-found-yet result;
    the function only returns None/gives up after all 13 attempts are
    exhausted. The per-email try/except blocks (search queries,
    INTERNALDATE fetch, RFC822 fetch) were not touched — they already
    retried correctly.

v1.5  (July 2026) — CSV lead-count sanity check baseline fix (Fix 4 companion):
  The v1.2 Fix 4 sanity check compared the CSV's row count against
  cls_db.stats()["total_leads"] * 0.85. Starting 21-Jul-2026, this
  began failing on EVERY cycle, not just on genuine wrong-email picks:
  cls_db.py v2.17 (Sell.do historical CSV bulk import) permanently
  added leads to cls.db with match_tier='imported', which inflated
  total_leads with rows Sell.do's own day-to-day export will never
  report again by design (a one-time historical backfill, not leads
  Sell.do is currently tracking). The CSV's real lead count could
  never clear 85% of a total that now includes leads structurally
  absent from every future export.
  FIX — compare against the new cls_db.py v2.18 stats()["syncable_leads"]
  (total_leads minus imported_historical) instead of total_leads. The
  SANITY FAIL log message now also reports syncable_leads and
  imported_historical alongside the CSV count, so the log is
  self-explanatory if this ever fires again. This is the ONLY change
  in this version — nothing else in Job B (Playwright login, Gmail
  polling, CSV parsing, matching logic) was touched.

v1.4  (July 2026) — Opportunity Warm/Hot temperature passthrough (v0.5 CRM):
  Sell.do's export has a separate "Lead Status" column (confirmed
  distinct from "Lead Stage" — Lead Stage itself stays exactly
  "Opportunity", never suffixed) holding Warm/Hot for leads at the
  Opportunity stage. Header text confirmed by Srikanth against a real
  downloaded export on 2026-07-08 — not a guess.
  This one-column read + passthrough to cls_db.upsert_selldo_lead()'s
  new opportunity_temperature param is the ONLY change in this version.
  Nothing else in Job B — the Playwright login, Gmail polling, CSV
  sanity check, matching logic — was touched. Deliberately minimal:
  this file is CLS's most fragile component (per the handoff brief),
  so every change here is scoped as tightly as possible and tested
  against a throwaway DB before redeploying against the live cls.db.

v1.3  (June 2026) — Fixed export window anchor + 90-day staleness signal:
  FIX 1 — EXPORT_DAYS (rolling 183-day window) replaced with
    EXPORT_START_DATE (fixed 2025-12-01 anchor)
    The old window was recalculated fresh every run as "today minus
    183 days," so its floor crept forward by 1 day every calendar day.
    On 30-Jun-2026 this caused a SANITY FAIL: leads created on
    28-Dec-2025 — CLS's original historical batch — aged out of the
    window and the CSV lead count dropped below the 85% threshold.
    Worse than the visible abort: any lead older than the rolling
    window that ISN'T re-synced never gets its current_stage updated
    again — frozen forever, no CAPI fire, no drip progression, no
    error. This violates Risk-3 "never discard" (this file's own
    design rule, see below) — CLS is supposed to be a COMPLETE
    registry, not a 6-month rolling snapshot. Fix: the export start
    date is now a fixed historical anchor that never moves, set safely
    before the very first lead ever entered Sell.do. No future date
    can ever cause leads to silently fall out of range again.
  FIX 2 — 90-day stage-staleness log line (cls_db.py v1.4 companion)
    Added a single log line per cycle reporting how many ACTIVE-stage
    leads (excludes Booked/Lost/Unqualified) have had no stage change
    in 90+ days. This is the early-warning signal for the exact
    silent-freeze failure mode Fix 1 just corrected, in case some
    other future bug causes it again. Read-only — does not affect
    fire state, drip state, or the sanity check above.

v1.2  (June 2026) — Gmail polling hardening (3 fixes):
  FIX 1 — MAX_ATTEMPTS : 4 -> 6
    Observed Sell.do export email arriving 13 minutes after trigger on
    slow-server days. Increasing from 4 to 6 attempts (adds 60s to the
    worst-case window) catches the majority of late arrivals.
  FIX 2 — Fast time-gate via IMAP INTERNALDATE (replaces full RFC822 fetch)
    Previously fetched the full email body of every candidate email just
    to read the Date header and decide to skip it. At 15:10 on 26-Jun-2026,
    6 old emails each took 5-51s to scan, burning the entire polling window.
    Now uses INTERNALDATE (server-received timestamp from Gmail's IMAP
    metadata — no body download needed) for the skip decision. Full RFC822
    body is only fetched for the one email that passes the time gate.
    Speed improvement for old-email skips: ~50x faster.
  FIX 3 — email_gate_ts captured AFTER trigger completes (not at job start)
    The Playwright export trigger takes 35-65s after job start. During that
    window, a late-arriving email from a previous FAILED cycle (e.g. the
    15:10 cycle's export arriving at 15:23) could appear "new" because
    run_start_utc_ts was already 60+ seconds old. Now captures the gate
    timestamp immediately after trigger_selldo_export() returns, so only
    emails that arrived AFTER this cycle's export was actually queued on
    Sell.do's servers are considered.
  FIX 4 — CSV lead-count sanity check
    On 26-Jun-2026 16:10 cycle, the script picked the wrong email out of
    two simultaneous 16:13 emails, downloading a file with 2558 leads vs
    the correct 2971. Sell.do sometimes sends two emails per export (one
    with export criteria summary, one with the file link); the script can
    pick the wrong one. Now aborts the run if the CSV lead count is below
    85% of the current CLS total, preventing silent partial syncs. The
    next cycle triggers a fresh export and self-heals cleanly.

v1.1  (June 2026) — 1-hour cadence tuning:
  CHANGE — EMAIL_WAIT_SECS  : 180 -> 60
    Sell.do's export email arrives in 45-90s in practice. The original
    3-minute flat wait was conservative carry-over from the old script.
    Trimming to 60s catches the typical case on the first Gmail check,
    removing 2 minutes of idle time from every cycle.
  CHANGE — MAX_ATTEMPTS : 7 -> 4
    Reduces the worst-case retry window from 7 min to 2 min
    (4 attempts × 30s CHECK_INTERVAL). Total Job B budget is now
    ~5-7 min worst-case, comfortably within the :10→:25 window.
  CHANGE — CHECK_INTERVAL : 60 -> 30
    Tighter polling suits the compressed schedule. If Sell.do's email
    arrives at second 75, the old script would wait until second 120
    before checking; the new one catches it at second 90.
  CHANGE — META_FLAG_MAX_AGE_MIN : 120 -> 75
    Gate tuned for 1-hour cadence: 60-min expected window + 15-min
    slack. A stale flag older than 75 min means Job A missed its cycle.

WHAT THIS JOB DOES
------------------
Pulls the full lead export from Sell.do CRM and writes every lead's
CURRENT PIPELINE STAGE into the Centralised Leads System (cls.db).
It matches each Sell.do lead to its existing CLS row by phone/email,
so a Meta lead pulled by Job A gets enriched with its CRM stage here.

    [Job A] meta_leads_fetcher.py   -> leads + leadgen_id into cls.db
       |                               sets flag 'meta_fetch'
       v
    [Job B] selldo_to_cls.py        <-- THIS FILE
       |    waits for 'meta_fetch' flag, then adds CRM stages to cls.db
       |    sets flag 'selldo_sync'
       v
    [Job C] cls_capi_firer.py       waits for 'selldo_sync', fires events

REFACTORED FROM selldo_capi_automation.py
-----------------------------------------
The Playwright login, the Select2-bypass export trigger, the Gmail
IMAP fetch and the CSV parse are reused almost verbatim from the
existing, debugged production script. What is REMOVED: the per-campaign
state-CSV diffing and the project/source filtering. What is CHANGED:
instead of firing CAPI events, every lead is upserted into cls.db.

  - Pull ALL leads (every project, every source). Walk-ins, 99acres
    and referral leads become source='selldo_only' rows in CLS — the
    Risk-3 "never discard" rule. CLS is a COMPLETE lead registry.
  - Stage diffing is no longer here. cls_db stores current_stage;
    Job C compares it to last_fired_stage. One job, one responsibility.

COMPLETION-FLAG GATING (Risk 1)
-------------------------------
Job B does NOT run on a fixed clock offset from Job A. It checks the
'meta_fetch' flag is fresh first. If Job A ran long or failed, Job B
skips this cycle rather than syncing against a half-built CLS.

ONE-TIME SETUP
--------------
  pip install playwright pandas requests beautifulsoup4 python-dotenv
  playwright install chromium
  (cls_db.py must be in the same folder)

RUN
---
  python selldo_to_cls.py                # normal run (flag-gated)
  python selldo_to_cls.py --force        # run even if Job A flag is stale
  python selldo_to_cls.py --latest-email # skip export trigger; sync from
                                         # the newest export email already
                                         # in the inbox (fast; good for
                                         # testing the CLS sync)
  python selldo_to_cls.py --selftest     # offline checks, no browser/API
=============================================================
"""

import os
import re
import sys
import time
import email
import imaplib
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta

import cls_db   # the foundation layer — Step 1

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR  = r"C:\CLS"
ENV_FILE  = os.path.join(BASE_DIR, ".env")
LOG_FILE  = os.path.join(BASE_DIR, "selldo_cls_log.txt")

SELLDO_URL = "https://app.sell.do"
EXPORT_URL = ("https://app.sell.do/client/export/export_types"
              "?remote-state=/client/export/check_user_access/leads")

# Fixed historical anchor — NOT a rolling window (v1.3 fix; was
# EXPORT_DAYS=183, recalculated as "today minus 183 days" every run,
# which silently dropped leads from the export as the window crept
# forward — see changelog). CLS is a COMPLETE lead registry (Risk-3
# "never discard"): the export must always start before the very
# first lead ever entered Sell.do, so no lead's stage updates can
# ever silently fall outside the window again. Set once, safely
# before CLS went live, and never move it forward.
EXPORT_START_DATE = datetime(2025, 12, 1)

# Gmail wait tuning — tuned for 1-hour cadence (v1.1); widened in v1.6.
# Sell.do emails typically arrive in 45-90s; 60s catches the first check.
# 13 attempts × 30s = 6 min worst-case retry window.
# Total polling window: 7 min (60s initial wait + 12×30s) — must never
# fail early. Task Scheduler trigger now fires at :02 (external change).
EMAIL_WAIT_SECS = 60    # initial wait for Sell.do's export email (was 180)
MAX_ATTEMPTS    = 13    # Gmail retry attempts (was 6; v1.6 increase for :02-trigger 7-min no-fail window)
CHECK_INTERVAL  = 30    # seconds between retries (was 60)

# How fresh Job A's completion must be for Job B to proceed (Risk 1).
# Tuned for 1-hour cadence: 60-min window + 15-min slack (was 120).
META_FLAG_MAX_AGE_MIN = 75


# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry     = f"[{timestamp}] [{level}] {message}"
    print(entry)
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# .env LOADER  —  Sell.do + Gmail credentials
# ─────────────────────────────────────────────────────────────

def load_env():
    """
    Read credentials from .env. Job B needs Sell.do login and Gmail
    IMAP access. Keeping them in .env (not hardcoded) means the old
    script and the new one share one credential store.
    Returns {} if .env is missing.
    """
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


# ─────────────────────────────────────────────────────────────
# PLAYWRIGHT HELPERS  —  reused verbatim from selldo_capi_automation.py
# Sell.do's Select2 dropdowns block normal automation; these JS
# injections bypass them. Proven code — do not "improve" without testing.
# ─────────────────────────────────────────────────────────────

def dismiss_select2_mask(page):
    try:
        page.evaluate("""
            () => {
                const mask = document.getElementById('select2-drop-mask');
                if (mask) mask.click();
                const drop = document.getElementById('select2-drop');
                if (drop) {
                    drop.classList.add('select2-display-none');
                    drop.classList.remove('select2-drop-active');
                }
            }
        """)
        time.sleep(0.8)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# STEP 1: Login to Sell.do and trigger the CSV export
# (refactored from trigger_selldo_export())
# ─────────────────────────────────────────────────────────────

def trigger_selldo_export(selldo_email, selldo_password, gmail_user):
    """
    Log into Sell.do via Playwright, open the export page, set the form
    fields directly through JavaScript (bypassing the Select2 dropdown
    issue), and submit. The export is then EMAILED by Sell.do — Step 2
    fetches it from Gmail.

    Returns True if the export was triggered, False otherwise.
    """
    from playwright.sync_api import sync_playwright

    log("-" * 55)
    log("STEP 1: Triggering Sell.do CSV export...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=400)
        context = browser.new_context()
        page    = context.new_page()

        try:
            # ── Login ──
            page.goto(f"{SELLDO_URL}/users/login", timeout=60000)
            page.wait_for_load_state("networkidle")
            page.fill('input[name="user[email]"]',    selldo_email)
            page.fill('input[name="user[password]"]', selldo_password)
            page.click('input[type="submit"], button[type="submit"]')
            page.wait_for_load_state("networkidle")
            log("Logged into Sell.do")

            # ── Open the export page ──
            page.goto(EXPORT_URL, timeout=60000)
            page.wait_for_load_state("networkidle")
            time.sleep(4)
            log("Export page loaded")

            # ── Set form values directly via JavaScript ──
            # This bypasses all Select2 UI issues. ALL leads: no project
            # or source filter is applied — Job B pulls everything.
            end_dt     = datetime.now()
            start_dt   = EXPORT_START_DATE
            date_range = f"{start_dt.strftime('%d/%m/%Y')} - {end_dt.strftime('%d/%m/%Y')}"

            page.evaluate(f"""
                () => {{
                    // Duration
                    const duration = document.querySelector('input[name="created_at"]');
                    if (duration) {{
                        duration.value = '{date_range}';
                        duration.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}
                    // Campaign Responses = All  (so re-engaged leads included)
                    const reEngaged = document.querySelector('input[name="re_engaged"]');
                    if (reEngaged) {{
                        reEngaged.value = 'all';
                        reEngaged.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}
                    // Delivery email
                    const emailInput = document.querySelector('input[name="email"]');
                    if (emailInput) {{
                        emailInput.value = '{gmail_user}';
                        emailInput.dispatchEvent(new Event('change', {{bubbles: true}}));
                        emailInput.dispatchEvent(new Event('input',  {{bubbles: true}}));
                    }}
                    // Update Select2 visible labels (cosmetic, keeps page consistent)
                    const crContainer = document.getElementById('s2id_autogen14');
                    if (crContainer) {{
                        const chosen = crContainer.querySelector('.select2-chosen');
                        if (chosen) chosen.textContent = 'All Responses';
                    }}
                    const emailContainer = document.getElementById('s2id_autogen3');
                    if (emailContainer) {{
                        const chosen = emailContainer.querySelector('.select2-chosen');
                        if (chosen) chosen.textContent = '{gmail_user}';
                    }}
                }}
            """)
            log(f"Export form set — date range {date_range}, all leads")
            time.sleep(2)

            # ── Submit the export — Sell.do's export is a TWO-STEP wizard ──
            # Page 1 sets the filters; you must click "Next >>" to reach
            # page 2, which holds the actual "Export" button. This is the
            # exact proven sequence from selldo_capi_automation.py.
            dismiss_select2_mask(page)

            # Step 1 of wizard: click "Next >>"
            page.evaluate("""
                () => {
                    const btn = document.getElementById('btn-next');
                    if (btn) btn.click();
                }
            """)
            time.sleep(3)
            log("Clicked 'Next >>' — advanced to export step")

            # Step 2 of wizard: click "Export" (by id, with a typed fallback)
            page.evaluate("""
                () => {
                    const btn = document.getElementById('btn-export');
                    if (btn) {
                        btn.click();
                    } else {
                        document.querySelectorAll('input[type="submit"]')
                            .forEach(b => { if (b.value === 'Export') b.click(); });
                    }
                }
            """)
            time.sleep(3)
            log("Export triggered — Sell.do will email the CSV to Gmail.")

            browser.close()
            return True

        except Exception as e:
            log(f"Sell.do export trigger failed: {e}", "ERROR")
            try:
                browser.close()
            except Exception:
                pass
            return False


# ─────────────────────────────────────────────────────────────
# STEP 2: Fetch the export CSV from Gmail
# (refactored from fetch_csv_from_gmail())
# ─────────────────────────────────────────────────────────────

def fetch_csv_from_gmail(gmail_user, gmail_app_pass, run_start_utc_ts,
                         ignore_time_gate=False):
    """
    Poll Gmail for the Sell.do export email, extract the download link,
    and download the CSV. Reused from the existing script, including
    the IMAP timezone fix (compare email time in UTC) and the
    extract-URLs-from-both-html-and-text fix.

    ignore_time_gate : if True, skip the "newer than run start" check
                       and simply take the most recent matching export
                       email already in the inbox. Used by --latest-email
                       to sync without triggering a fresh export.

    Returns the CSV text, or None on failure.
    """
    import calendar
    from email.utils import parsedate_to_datetime

    log("-" * 55)
    if ignore_time_gate:
        log("STEP 2: Using most recent export email already in inbox...")
        attempts = 1          # no need to wait/retry — email already exists
        initial_wait = 0
    else:
        log("STEP 2: Waiting for Sell.do export email...")
        attempts = MAX_ATTEMPTS
        initial_wait = EMAIL_WAIT_SECS

    if initial_wait:
        log(f"Initial wait: {initial_wait}s...")
        time.sleep(initial_wait)

    download_url = None

    for attempt in range(1, attempts + 1):
        log(f"Gmail check attempt {attempt}/{attempts}...")

        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(gmail_user, gmail_app_pass)
            mail.select("inbox")
        except Exception as e:
            # v1.6: don't give up on the first connection failure — fall
            # through to the same wait-and-retry path as a normal
            # not-found-yet result. Only return None once all attempts
            # are exhausted (see MAX_ATTEMPTS).
            log(f"Gmail connection failed: {e}", "WARNING")
            if attempt < attempts:
                log(f"Export email not found yet. Waiting {CHECK_INTERVAL}s...")
                time.sleep(CHECK_INTERVAL)
            continue

        since_date = datetime.now().strftime("%d-%b-%Y")
        search_queries = [
            f'(SUBJECT "export" SINCE {since_date})',
            f'(FROM "sell.do" SINCE {since_date})',
            f'(SUBJECT "lead" SINCE {since_date})',
        ]

        found_emails = []
        for query in search_queries:
            try:
                status, messages = mail.search(None, query)
                if status == "OK" and messages[0]:
                    for eid in messages[0].split():
                        if eid not in found_emails:
                            found_emails.append(eid)
            except Exception:
                continue

        found_emails = sorted(set(found_emails), key=lambda x: int(x), reverse=True)
        log(f"Found {len(found_emails)} candidate email(s).")

        for eid in found_emails:
            try:
                # ── v1.2: Fast time-gate using IMAP INTERNALDATE ──
                # Gmail assigns INTERNALDATE = the moment the email arrived on
                # their servers. We only need this timestamp to decide whether
                # an email is "new" (arrived after our export was triggered).
                # Fetching the full RFC822 body of every old email just to read
                # the Date header was slow (51s per email on 26-Jun-2026 15:10
                # with 6 candidates). Now we fetch INTERNALDATE + Subject only
                # (tiny metadata, no body), and download the full RFC822 body
                # only for the one email that passes the time gate.
                if not ignore_time_gate:
                    status, id_data = mail.fetch(
                        eid,
                        "(INTERNALDATE BODY.PEEK[HEADER.FIELDS (SUBJECT)])"
                    )
                    if status != "OK" or not id_data or \
                            not isinstance(id_data[0], tuple):
                        # Metadata fetch failed — fall through and try the full
                        # body; better than silently skipping a valid email.
                        log(f"INTERNALDATE fetch failed for {eid}, "
                            "fetching full body.", "WARNING")
                    else:
                        meta_line = id_data[0][0].decode("utf-8", errors="ignore")
                        subject   = email.message_from_bytes(
                            id_data[0][1]).get("Subject", "")
                        m = re.search(r'INTERNALDATE "([^"]+)"', meta_line)
                        if m:
                            email_utc_ts = calendar.timegm(
                                parsedate_to_datetime(
                                    m.group(1)).utctimetuple())
                            if email_utc_ts < run_start_utc_ts:
                                log(f"Skipping old email: '{subject}'")
                                continue
                            log(f"New email found: '{subject}'")
                        else:
                            # Pattern not matched — process the email anyway.
                            log("INTERNALDATE not found in response, "
                                "trying this email.", "WARNING")

                # ── Full body — only reached for emails that passed the gate ──
                status, msg_data = mail.fetch(eid, "(RFC822)")
                msg     = email.message_from_bytes(msg_data[0][1])
                subject = msg.get("Subject", "")

                if ignore_time_gate:
                    log(f"Using email: '{subject}'")

                # Collect body text + html.
                body_text, body_html = "", ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        if ctype == "text/plain":
                            body_text += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        elif ctype == "text/html":
                            body_html += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode("utf-8", errors="ignore")

                # Sell.do sometimes sends HTML as plain text — scan both.
                urls = []
                for body in [body_html, body_text]:
                    if not body:
                        continue
                    for href in re.findall(r"href=[\"']?(https?://[^\"'>\s]+)", body):
                        href = href.strip().rstrip("'\">.,;")
                        if href.startswith('http') and href not in urls:
                            urls.append(href)

                for url in urls:
                    if any(k in url.lower() for k in
                           ['export', 'download', 'csv', 'sell.do', 'amazonaws',
                            'digitalocean', 'storage', 'blob', 's3', 'file']):
                        download_url = url
                        break
                if not download_url and urls:
                    download_url = urls[0]

                if download_url:
                    log(f"Download URL selected.")
                    break

            except Exception as e:
                log(f"Error reading email {eid}: {e}", "WARNING")
                continue

        mail.logout()
        if download_url:
            break

        if attempt < attempts:
            log(f"Export email not found yet. Waiting {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)

    if not download_url:
        log("No download link found after all attempts", "ERROR")
        return None

    log("Downloading CSV...")
    try:
        resp = requests.get(download_url, timeout=60,
                            headers={"User-Agent": "Mozilla/5.0"})
        log(f"Download status: {resp.status_code}, size: {len(resp.text)} chars")
        return resp.text
    except Exception as e:
        log(f"CSV download failed: {e}", "ERROR")
        return None


# ─────────────────────────────────────────────────────────────
# STEP 3: Parse the CSV  (reused from parse_csv())
# ─────────────────────────────────────────────────────────────

def parse_csv(csv_data):
    """
    Sell.do's export has 9 header/metadata rows before the real table,
    so skiprows=9. Returns a DataFrame, or None on failure.
    """
    log("-" * 55)
    log("STEP 3: Parsing CSV...")
    try:
        df = pd.read_csv(StringIO(csv_data), skiprows=9)
        log(f"Total leads in CSV: {len(df)}")
        if "Lead Stage" in df.columns:
            log(f"Stages present: {sorted(set(str(s) for s in df['Lead Stage'].dropna().unique()))}")
        return df
    except Exception as e:
        log(f"CSV parse error: {e}", "ERROR")
        return None


# ─────────────────────────────────────────────────────────────
# STEP 4: Upsert every CSV row into CLS  (the NEW part)
# ─────────────────────────────────────────────────────────────

def _clean(value):
    """Trim a CSV cell; treat nan/none as empty string."""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none") else s


def sync_csv_to_cls(df):
    """
    For every lead row in the Sell.do CSV, call cls_db.upsert_selldo_lead().
    The matcher inside cls_db joins by phone/email to existing CLS rows
    (the Meta leads from Job A). Unmatched leads become 'selldo_only'
    rows — nothing is discarded (Risk 3).

    Returns a small report dict for logging.
    """
    log("-" * 55)
    log("STEP 4: Syncing leads into CLS...")

    # Column names as they appear in the Sell.do export (verified
    # against Naishka_All_Campaigns_state.csv headers).
    COL_LEAD_ID = "Lead's Id"
    COL_FIRST   = "First Name"
    COL_LAST    = "Last Name"
    COL_STAGE   = "Lead Stage"
    COL_PHONE   = "Phone"
    COL_EMAIL   = "Email"
    COL_PROJECT = "Projects"
    COL_OWNER   = "Attended By"   # v1.2 — executive assigned in Sell.do
    # v1.4 — Opportunity Warm/Hot status. This is a SEPARATE column from
    # "Lead Stage" in Sell.do's export — Lead Stage stays exactly
    # "Opportunity", never suffixed with Warm/Hot. Confirmed against a
    # real downloaded export (Srikanth, 2026-07-08): header is "Lead Status".
    COL_TEMPERATURE = "Lead Status"

    required = [COL_LEAD_ID, COL_STAGE, COL_PHONE]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        log(f"CSV missing required columns: {missing} — aborting sync.", "ERROR")
        return None

    total          = 0
    matched        = 0
    selldo_only    = 0
    stage_changes  = 0
    skipped        = 0

    for _, row in df.iterrows():
        lead_id = _clean(row.get(COL_LEAD_ID, ""))
        # Sell.do's "Lead's Id" is wrapped in a =HYPERLINK(...) formula:
        #   =HYPERLINK("https://app.sell.do/.../overview", 7340)
        # v1.3: extract the full URL and the numeric ID from the same cell.
        m_url      = re.search(r'HYPERLINK\("([^"]+)"', lead_id)
        selldo_url = m_url.group(1) if m_url else ""
        m = re.search(r"(\d+)\s*\)?\s*$", lead_id)
        selldo_lead_id = m.group(1) if m else lead_id

        stage = _clean(row.get(COL_STAGE, ""))
        if not selldo_lead_id or not stage:
            skipped += 1
            continue

        first = _clean(row.get(COL_FIRST, ""))
        last  = _clean(row.get(COL_LAST, ""))
        name  = f"{first} {last}".strip()

        phone      = _clean(row.get(COL_PHONE, ""))
        email_     = _clean(row.get(COL_EMAIL, ""))
        project    = _clean(row.get(COL_PROJECT, ""))
        lead_owner = _clean(row.get(COL_OWNER, ""))  # v1.2 — "Attended By"
        # v1.4 — only meaningful when stage == "Opportunity"; blank for
        # every other stage in Sell.do's own export, which is fine —
        # upsert_selldo_lead stores whatever it's given either way.
        temperature = _clean(row.get(COL_TEMPERATURE, ""))

        try:
            cls_id, changed = cls_db.upsert_selldo_lead(
                selldo_lead_id = selldo_lead_id,
                project        = project,
                full_name      = name,
                phone_raw      = phone,
                email_raw      = email_,
                current_stage  = stage,
                lead_owner     = lead_owner,          # v1.2
                selldo_url     = selldo_url,           # v1.3
                opportunity_temperature = temperature, # v1.4
            )
            total += 1
            if changed:
                stage_changes += 1
        except Exception as e:
            log(f"  upsert failed for Sell.do lead {selldo_lead_id}: {e}", "WARNING")
            skipped += 1

    # Counts of how the sync resolved, read back from CLS.
    s = cls_db.stats()
    log(f"Synced {total} Sell.do leads ({skipped} skipped).")
    log(f"  Stage changes detected this run: {stage_changes}")

    return {
        "synced"        : total,
        "skipped"       : skipped,
        "stage_changes" : stage_changes,
        "cls_stats"     : s,
    }


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run(force=False, latest_email=False):
    log("=" * 55)
    log("CLS JOB B — Sell.do -> CLS Sync — START")
    if latest_email:
        log("MODE: --latest-email (no new export; using newest inbox email)")
    log("=" * 55)

    cls_db.init_db()

    # ── Risk 1: completion-flag gate ──
    # Job B must run AFTER Job A. Instead of a fixed clock offset, we
    # check Job A's 'meta_fetch' flag is fresh. Stale/missing -> skip.
    if not force:
        if cls_db.is_flag_fresh("meta_fetch", META_FLAG_MAX_AGE_MIN):
            log("Gate OK — Job A's 'meta_fetch' flag is fresh.")
        else:
            ts = cls_db.get_flag("meta_fetch")
            log(f"Gate BLOCKED — 'meta_fetch' flag missing or stale (last: {ts}).",
                "WARNING")
            log("Job A has not completed recently. Skipping this cycle.")
            log("(Use --force to override, e.g. for manual testing.)")
            return False
    else:
        log("Gate SKIPPED — --force flag used.")

    # ── Credentials ──
    env = load_env()
    selldo_email    = env.get("SELLDO_EMAIL", "")
    selldo_password = env.get("SELLDO_PASSWORD", "")
    gmail_user      = env.get("GMAIL_USER", "")
    gmail_app_pass  = env.get("GMAIL_APP_PASS", "")

    # --latest-email only needs Gmail; a normal run needs Sell.do too.
    if latest_email:
        needed = [gmail_user, gmail_app_pass]
    else:
        needed = [selldo_email, selldo_password, gmail_user, gmail_app_pass]
    if not all(needed):
        log("Missing required credentials in .env — aborting.", "ERROR")
        log("Normal run needs: SELLDO_EMAIL, SELLDO_PASSWORD, GMAIL_USER, GMAIL_APP_PASS")
        return False

    run_start_utc_ts = time.time()

    if latest_email:
        # Skip Step 1 entirely — consume the newest export email present.
        csv_data = fetch_csv_from_gmail(
            gmail_user, gmail_app_pass, run_start_utc_ts,
            ignore_time_gate=True)
    else:
        # ── Step 1: trigger export ──
        triggered = trigger_selldo_export(selldo_email, selldo_password, gmail_user)

        # ── v1.2 Fix 3: capture gate AFTER trigger completes ──
        # The Playwright trigger takes 35-65s. If we used run_start_utc_ts
        # (captured at job start), a late-arriving email from a previous
        # failed cycle that landed in Gmail during the Playwright run would
        # pass the time gate. By capturing email_gate_ts here — immediately
        # after the export is queued on Sell.do's servers — any email older
        # than this moment is from a different cycle and is correctly excluded.
        # If trigger failed, fall back to run_start_utc_ts (safe default).
        email_gate_ts = time.time() if triggered else run_start_utc_ts

        if not triggered:
            log("Export trigger failed — attempting Gmail fetch anyway...", "WARNING")
        # ── Step 2: fetch CSV from Gmail ──
        csv_data = fetch_csv_from_gmail(
            gmail_user, gmail_app_pass, email_gate_ts)

    if not csv_data:
        log("Could not retrieve CSV — aborting this run.", "ERROR")
        return False

    # ── Step 3: parse ──
    df = parse_csv(csv_data)
    if df is None:
        log("CSV parsing failed — aborting this run.", "ERROR")
        return False

    # ── v1.2 Fix 4: CSV lead-count sanity check (v1.5: syncable_leads baseline) ──
    # Sell.do sometimes sends TWO emails per export cycle: one with export
    # criteria summary and one with the actual file link. When both arrive
    # simultaneously, the script (sorted newest IMAP ID first) may pick the
    # wrong one — observed on 26-Jun-2026 16:10: 2558 leads synced while the
    # correct export had 2971. The chars-per-lead ratio was identical, proving
    # it was a fully valid but wrong export file.
    # Guard: if the CSV has < 85% of the leads CLS already holds, the script
    # almost certainly picked a wrong/partial export. Abort cleanly — the next
    # cycle triggers a fresh export and self-heals.
    # v1.5: baseline switched from total_leads to syncable_leads (total_leads
    # minus imported_historical) — total_leads is now permanently inflated by
    # the v2.17 Sell.do historical CSV bulk import, whose match_tier='imported'
    # rows Sell.do's own export will never report again by design.
    s_pre = cls_db.stats()
    if s_pre["syncable_leads"] > 0 and len(df) < s_pre["syncable_leads"] * 0.85:
        log(
            f"SANITY FAIL — CSV has {len(df)} leads but CLS holds "
            f"{s_pre['syncable_leads']} syncable leads (threshold 85%; "
            f"total_leads={s_pre['total_leads']}, "
            f"imported_historical={s_pre['imported_historical']}). "
            "Likely picked the wrong export email. "
            "Aborting — next cycle will re-trigger and recover.",
            "ERROR",
        )
        return False

    # ── Step 4: sync into CLS ──
    report = sync_csv_to_cls(df)
    if report is None:
        log("CLS sync failed — flag NOT set.", "ERROR")
        return False

    # ── CLS health snapshot ──
    s = report["cls_stats"]
    log("-" * 55)
    log(f"CLS now holds: {s['total_leads']} leads "
        f"({s['with_leadgen_id']} with leadgen_id, "
        f"{s['selldo_only']} selldo-only, {s['pending_fire']} pending fire)")

    # ── v1.3: 90-day stage-staleness signal ──
    # Leads stuck on a non-terminal stage (i.e. not Booked/Lost/
    # Unqualified) with no movement in 90+ days. Early-warning for the
    # silent-freeze failure mode the EXPORT_START_DATE fix above just
    # corrected — read-only, does not affect fire state or drip state.
    stale_count = cls_db.get_stale_stage_count(days=90)
    log(f"Leads with no stage change in 90+ days (active stages only): {stale_count}")

    # ── Risk 1: set this job's flag — tells Job C it may proceed ──
    cls_db.set_flag("selldo_sync")
    log("Completion flag 'selldo_sync' set — Job C may now proceed.")

    log("=" * 55)
    log("CLS JOB B — Sell.do -> CLS Sync — DONE")
    log("=" * 55)
    return True


# ─────────────────────────────────────────────────────────────
# SELF-TEST  —  offline; no browser, no Gmail, no API
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Verifies the pure-logic pieces:
      - the =HYPERLINK(...) lead-id extraction
      - CSV parsing with the 9-row header skip
      - cleaning of nan/none cells
    """
    print("=" * 55)
    print(" SELLDO -> CLS — SELF TEST (offline)")
    print("=" * 55)

    # ── =HYPERLINK lead-id extraction ──
    samples = [
        ('=HYPERLINK("https://app.sell.do/leads/AbCdEfGh/overview", 1430)', "1430",
         "https://app.sell.do/leads/AbCdEfGh/overview"),
        ('=HYPERLINK("https://app.sell.do/leads/XyZwVuTs/overview", 1846)', "1846",
         "https://app.sell.do/leads/XyZwVuTs/overview"),
        ('98765', "98765", ""),
    ]
    for raw, expected_id, expected_url in samples:
        m_url = re.search(r'HYPERLINK\("([^"]+)"', raw)
        got_url = m_url.group(1) if m_url else ""
        m = re.search(r"(\d+)\s*\)?\s*$", raw)
        got_id = m.group(1) if m else raw
        flag_id  = "OK" if got_id  == expected_id  else "FAIL"
        flag_url = "OK" if got_url == expected_url else "FAIL"
        print(f"  [{flag_id}]  lead-id extract: {got_id!r}")
        print(f"  [{flag_url}] url extract:     {got_url!r}")

    # ── _clean ──
    checks = [("  Ravi  ", "Ravi"), ("nan", ""), ("NONE", ""), ("", "")]
    for raw, expected in checks:
        got = _clean(raw)
        flag = "OK" if got == expected else "FAIL"
        print(f"  [{flag}] _clean({raw!r}) -> {got!r}")

    # ── CSV parse with 9-row header skip ──
    fake_csv = "\n".join([f"meta line {i}" for i in range(9)]) + "\n"
    fake_csv += "Lead's Id,First Name,Last Name,Lead Stage,Phone,Email,Projects,Attended By\n"
    fake_csv += '"=HYPERLINK(""x"", 111)",Ravi,Kumar,Prospect,919876543210.0,ravi@gmail.com,Naishka Prism,Elohar\n'
    fake_csv += '"=HYPERLINK(""x"", 222)",Sita,,Opportunity,9000000001,,Grace Classic,Mahesh\n'
    df = parse_csv(fake_csv)
    ok = df is not None and len(df) == 2 and "Lead Stage" in df.columns
    print(f"  [{'OK' if ok else 'FAIL'}] CSV parse with skiprows=9 -> {len(df) if df is not None else 'None'} rows")

    print("=" * 55)
    print(" SELF TEST COMPLETE — offline logic verified.")
    print(" Live run requires Sell.do + Gmail credentials in .env.")
    print("=" * 55)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
    else:
        run(force=("--force" in args),
            latest_email=("--latest-email" in args))
