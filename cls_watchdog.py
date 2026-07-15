"""
=============================================================
cls_watchdog.py  —  CLS Health Monitor & Alert System
=============================================================
Version : 2.4
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v2.4  (July 2026) — Real cycle count + per-salesperson daily summary:
  FIXED   — Daily summary said "CLS ran 5 cycles today (10:30 -> 18:30)"
              as a hardcoded string, left over from the old every-2-hours
              schedule. Jobs A/B/C actually run hourly (9 cycles/day,
              10:00-18:00) — the text was never updated when the cadence
              changed, so it silently under-reported every single day
              since the switch. Fixed by extract_daily_cycle_info():
              counts the ACTUAL number of completed Job A runs today
              (and their real first/last timestamps) straight from
              meta_leads_log.txt, so the line is correct regardless of
              cadence, and self-corrects again if the cadence ever
              changes a second time.
  ADDED   — Per-salesperson section in the daily summary, under a new
              "By Salesperson" heading — new leads fetched, stage
              changes, and CAPI events fired, broken out per lead_owner
              (e.g. Elohar, Mahesh) plus an "Unassigned" bucket for
              leads with no owner yet. Powered by cls_db.py v2.1's
              get_daily_owner_summary() — requires cls_db.py v2.1 and
              cls_capi_firer.py v1.6 (adds lead_owner to events_log).
              See cls_db.py's docstring for the one known edge case
              (same lead changing stage twice in one day counts once
              here vs. Job B's raw per-cycle total counting it twice).

v2.3  (June 2026) — Per-cycle counts + end-of-day daily summary:
  ADDED — Completion Flags section now shows per-run activity counts
            parsed directly from each job's existing log file.
            No changes required to any job script (A, B, or C).
            Example output:
              ✅ Job A — OK — last run 55 min ago — 3 new leads fetched this round
              ✅ Job B — OK — last run 40 min ago — 8 stage changes this round
              ✅ Job C — OK — last run 30 min ago — 5 events fired this round
  ADDED — End-of-day summary sent as a SEPARATE Telegram message on
            the last watchdog cycle of the day (17:55 run, hour==17).
            Scans the full day's logs and sums every matching line:
              📋 CLS Daily Summary — 25 Jun 2026
              📥 New leads fetched    : 7
              🔄 Stage changes        : 21
              🚀 CAPI events fired    : 14
  ADDED — extract_run_count(): reads last matching count from log tail.
  ADDED — extract_daily_total(): sums a regex pattern across today's log.
  ADDED — compose_daily_summary(): builds the end-of-day Telegram message.

v2.2  (June 2026) — Job C completion flag added to watchdog:
  FIXED   — JOB_FLAGS now includes "Job C (CAPI Firer)": "capi_fire".
              cls_capi_firer.py has always set this flag (line 568);
              the watchdog was simply not checking it. Completion Flags
              section now reports all three jobs A, B, and C.

v2.1  (June 2026) — Brevo email fallback + token log sanitization:
  ADDED   — send_brevo_alert(): fires watchdog report via Brevo email
              when Telegram is unavailable (ISP blocks, API downtime, etc.).
              Falls back automatically; no manual action needed.
              Uses BREVO_API_KEY already in .env — no new setup required.
              Alert delivered to sales1@asianbuild.in.
  FIXED   — Bot token no longer logged in plain text when Telegram fails.
              requests exceptions include the full URL (which contains the
              token); now sanitized to ***REDACTED*** before logging.
  UPDATED — selftest() now also tests Brevo connectivity when
              --selftest --brevo is passed.

v2.0  (June 2026) — Per-cycle Telegram report:
  CHANGED — Telegram now sends every 2-hour cycle, not once per day.
    Each report shows a green tick per job when healthy, and a
    red alert per job when something is wrong.
    This replaces the old "daily OK once + alert on failure" model.
  FIXED   — SyntaxWarning on Windows path in docstring (line 48).
  FIXED   — Log file names corrected to match actual script outputs:
      Job B: selldo_cls_log.txt  (was: selldo_log.txt)
      Job C: cls_capi_log.txt    (was: capi_log.txt)
      Job D: cls_drip_log.txt    (was: cls_email_drip_log.txt)

WHAT THIS SCRIPT DOES
----------------------
Monitors the health of all CLS jobs (A, B, C, D) and sends a
Telegram report after every 2-hour cycle. Shows green ticks on
healthy runs, instant alerts when anything is wrong. Runs every
2 hours via Task Scheduler, 5 minutes BEFORE the main jobs.

WHAT IT CHECKS
--------------
  1. Completion flags — did Jobs A, B, C set their flag within the
     expected window? Stale flag = job failed silently.
  2. ERROR lines in today's log files — scans the last 100 lines
     of each job's log for [ERROR] entries written today.
  3. Pending fire queue — are leads stuck waiting to fire to CAPI?
  4. cls.db accessibility — can the database be opened and queried?

TELEGRAM REPORT FORMAT (every cycle)
-------------------------------------
  Healthy run:
    ✅ CLS Health Report
    Time: 25 Jun 2026, 04:00 PM
    DB: 3309 leads | 3100 with leadgen_id | 0 pending fire
    Completion Flags
    ✅ Job A (Meta Fetcher) — OK — last run 55 min ago — 3 new leads fetched this round
    ✅ Job B (Sell.do Sync) — OK — last run 40 min ago — 8 stage changes this round
    ✅ Job C (CAPI Firer)   — OK — last run 30 min ago — 5 events fired this round
    Log File Scan
    ✅ Job A — no errors today
    ✅ Job B — no errors today
    ✅ Job C — no errors today
    ✅ Job D — no errors today
    CAPI Fire Queue
    ✅ Queue — 0 pending (all fired)

  On the last cycle of the day only (hour == 18) — a SECOND message is sent:
    📋 CLS Daily Summary — 25 Jun 2026
    📥 New leads fetched    : 7
    🔄 Stage changes        : 21
    🚀 CAPI events fired    : 14

    ── By Salesperson ──
    👤 Elohar
       New leads fetched : 4
       Stage changes     : 9
       CAPI events       : 6
    👤 Mahesh
       New leads fetched : 3
       Stage changes     : 12
       CAPI events       : 8

    CLS ran 9 cycle(s) today (10:32 AM → 06:31 PM).
    (cycle count/window is computed from today's actual log entries, not
     hardcoded — see extract_daily_cycle_info(), v2.4)

  Problem run: same layout, affected lines show alert emoji.

SCHEDULE (Task Scheduler)
--------------------------
  Runs shortly before each Jobs A/B/C cycle, whatever that cadence
  currently is (as of July 2026: hourly, 10:00-18:00 IST, 9 cycles/day —
  see cls_capi_firer.py v1.5). This docstring intentionally does NOT list
  exact clock times: the schedule already drifted out of sync with this
  file once (v2.3 said "every 2 hours" long after Jobs A/B/C moved to
  hourly, which is what caused the "5 cycles" bug fixed in v2.4). The
  daily summary now reports the actual count/window from today's log
  instead of a written-down number, so this section can't go stale again
  in the same way — but if you change the Task Scheduler cadence, still
  update FLAG_MAX_AGE_MIN below if the new gap between cycles changes.

ONE-TIME SETUP
--------------
  1. Create a Telegram bot:
     - Open Telegram -> search @BotFather -> /newbot
     - Name it "CLS Watchdog" -> copy the BOT_TOKEN it gives you
     - Send ANY message to your new bot (to activate the chat)
     - Visit: https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
     - Copy the "id" from result[0].message.chat.id

  2. Add to C:\\CLS\\.env:
       TELEGRAM_BOT_TOKEN=7123456789:AAFxxx...
       TELEGRAM_CHAT_ID=123456789

  3. No new pip installs needed — uses only stdlib (requests already
     installed for meta_leads_fetcher.py).

RUN
---
  python cls_watchdog.py                      # normal health check + Telegram report
  python cls_watchdog.py --selftest           # tests Telegram connectivity only
  python cls_watchdog.py --selftest --brevo  # tests both Telegram AND Brevo
  python cls_watchdog.py --force              # force-send a report regardless
=============================================================
"""

import os
import re
import sys
import json
import sqlite3
import requests
from datetime import datetime, timedelta

import cls_db   # shared foundation — for flag checks and DB access

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR       = r"C:\CLS"
ENV_FILE       = os.path.join(BASE_DIR, ".env")
LOG_FILE       = os.path.join(BASE_DIR, "cls_watchdog_log.txt")
SNAPSHOT_FILE  = os.path.join(BASE_DIR, "cls_watchdog_snapshot.json")

# Log files to inspect for [ERROR] lines and activity counts
JOB_LOG_FILES = {
    "Job A (Meta Fetcher)": os.path.join(BASE_DIR, "meta_leads_log.txt"),
    "Job B (Sell.do Sync)": os.path.join(BASE_DIR, "selldo_cls_log.txt"),
    "Job C (CAPI Firer)"  : os.path.join(BASE_DIR, "cls_capi_log.txt"),
    "Job D (Email Drip)"  : os.path.join(BASE_DIR, "cls_drip_log.txt"),
}

# Completion flags to check (from cls_flags.json)
JOB_FLAGS = {
    "Job A (Meta Fetcher)": "meta_fetch",
    "Job B (Sell.do Sync)": "selldo_sync",
    "Job C (CAPI Firer)"  : "capi_fire",   # flag set at line 568 of cls_capi_firer.py
}

# How old (in minutes) a flag is allowed to be before we alert.
# Set to 3 hours = 180 min (pipeline runs every 2 hours, so 3h = one missed
# cycle before alerting — avoids noise from a single blip).
FLAG_MAX_AGE_MIN = 180

# How many lines to scan from the end of each log file
LOG_TAIL_LINES = 100

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    print(entry)
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# ENV LOADER
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# TELEGRAM ALERT SENDER
# ─────────────────────────────────────────────────────────────

def send_telegram(bot_token, chat_id, message):
    """
    Send a message to a Telegram chat via Bot API.
    Returns True on success, False on failure.
    parse_mode=HTML so we can bold/format the alert.
    Token is sanitized in error logs — never written in plain text.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id"    : chat_id,
        "text"       : message,
        "parse_mode" : "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            log("Telegram alert sent successfully.")
            return True
        else:
            log(f"Telegram API error: {data.get('description', 'unknown')}", "ERROR")
            return False
    except Exception as e:
        # Sanitize: requests includes the full URL (with token) in the exception
        # message — replace the token before logging.
        err_str = str(e).replace(bot_token, "***REDACTED***")
        log(f"Telegram send failed: {err_str}", "ERROR")
        return False


# ─────────────────────────────────────────────────────────────
# BREVO EMAIL FALLBACK
# ─────────────────────────────────────────────────────────────

def send_brevo_alert(env, report_msg):
    """
    Fallback alert channel: sends the watchdog report as an HTML email
    via Brevo when Telegram is unavailable (ISP blocks, API downtime, etc.).

    Uses BREVO_API_KEY already in .env — no new credentials needed.
    Sender/recipient: sales1@asianbuild.in (Srikanth's admin account).
    sib_api_v3_sdk v7.6.0 is already installed for Job D (cls_email_drip.py).

    Returns True on success, False on any failure.
    """
    try:
        import sib_api_v3_sdk
    except ImportError:
        log("sib_api_v3_sdk not installed — Brevo fallback unavailable.", "WARNING")
        return False

    brevo_key = env.get("BREVO_API_KEY", "")
    if not brevo_key:
        log("BREVO_API_KEY not found in .env — Brevo fallback skipped.", "WARNING")
        return False

    try:
        cfg = sib_api_v3_sdk.Configuration()
        cfg.api_key["api-key"] = brevo_key
        api = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(cfg))

        subject = (
            f"⚠️ CLS Watchdog — "
            f"{datetime.now().strftime('%d %b %Y, %I:%M %p')}"
            " [Telegram unavailable]"
        )

        # The report_msg already contains <b>, <code>, emoji — valid HTML email.
        # Wrap in a minimal styled container for readability.
        html_body = (
            "<html><body>"
            "<div style='font-family:Arial,sans-serif;font-size:14px;"
            "line-height:1.8;max-width:600px;'>"
            + report_msg.replace("\n", "<br>")
            + "<br><br>"
            "<small style='color:#aaa;'>Sent via Brevo fallback"
            " — Telegram was unavailable at send time.</small>"
            "</div></body></html>"
        )

        email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": "sales1@asianbuild.in", "name": "Srikanth"}],
            sender={"email": "sales1@asianbuild.in", "name": "CLS Watchdog"},
            subject=subject,
            html_content=html_body,
            # Suppress Brevo's injected footer (avoids Gmail 102 KB clip).
            headers={
                "List-Unsubscribe": (
                    "<mailto:sales1@asianbuild.in?subject=unsubscribe>"
                ),
            },
        )
        api.send_transac_email(email)
        log("Brevo email fallback sent to sales1@asianbuild.in.")
        return True

    except Exception as e:
        log(f"Brevo email fallback failed: {e}", "ERROR")
        return False


# ─────────────────────────────────────────────────────────────
# LOG COUNT HELPERS  (v2.3)
# ─────────────────────────────────────────────────────────────

def extract_run_count(log_path, pattern, zero_indicator=None):
    """
    Scan the last LOG_TAIL_LINES of a log file and return the integer
    from the LAST line that matches `pattern` (capture group 1).

    This gives the count from the most recent job run — exactly what
    we want for the per-cycle Completion Flags line.

    zero_indicator : if the main pattern is not found but this string
                     appears anywhere in the tail, return 0. Used for
                     Job C's "No stage changes to fire this run" case.

    Returns an int when found, or None if the job hasn't run yet /
    log doesn't exist / neither pattern matched.
    """
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        tail = lines[-LOG_TAIL_LINES:]
        # Scan reversed — want the most recent match
        for line in reversed(tail):
            m = re.search(pattern, line)
            if m:
                return int(m.group(1))
        # Pattern not found — check for the zero-activity indicator
        if zero_indicator and any(zero_indicator in l for l in tail):
            return 0
    except Exception:
        pass
    return None


def extract_daily_cycle_info(log_path, pattern):
    """
    (v2.4) Scan the FULL log file for lines that (a) contain today's date
    and (b) match `pattern` — one such line exists per completed run of
    that job. Returns (cycle_count, first_run_str, last_run_str) using the
    log's own [YYYY-MM-DD HH:MM:SS] timestamp prefix on those lines.

    This replaces a hardcoded cycle count/window in the daily summary.
    Whatever the actual cadence is today (hourly, every 2 hours, a cycle
    that got skipped, an extra manual run) — this counts what ACTUALLY
    ran, from the log, the same way extract_daily_total() sums activity.
    Hardcoding a schedule text string is exactly the kind of version-drift
    bug that caused "CLS ran 5 cycles" to keep showing after the pipeline
    moved to hourly (9 cycles) — self-reporting count avoids that recurring.

    Returns (0, None, None) if the file is missing or nothing matched.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    ts_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
    timestamps = []
    if not os.path.exists(log_path):
        return 0, None, None
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if today not in line:
                    continue
                if not re.search(pattern, line):
                    continue
                m = ts_pattern.match(line)
                if m:
                    timestamps.append(m.group(1))
    except Exception:
        pass
    if not timestamps:
        return 0, None, None
    first_run = datetime.strptime(timestamps[0], "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p")
    last_run  = datetime.strptime(timestamps[-1], "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p")
    return len(timestamps), first_run, last_run


def extract_daily_total(log_path, pattern):
    """
    Scan the FULL log file and sum the integers from every line that:
      (a) contains today's date, and
      (b) matches `pattern` (capture group 1).

    Used for the end-of-day summary — accumulates all 5 cycles.
    Returns an int (0 if file not found or no matches today).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0
    if not os.path.exists(log_path):
        return 0
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if today not in line:
                    continue
                m = re.search(pattern, line)
                if m:
                    total += int(m.group(1))
    except Exception:
        pass
    return total


# ─────────────────────────────────────────────────────────────
# HEALTH CHECKS
# ─────────────────────────────────────────────────────────────


def check_pending_fire_queue():
    """
    Detects if the pending-fire queue (leads where current_stage !=
    last_fired_stage) is stuck — i.e., same count as last cycle.
    Returns a list of problem strings.
    """
    problems = []
    try:
        current_pending = len(cls_db.get_unfired_leads())
        log(f"Current pending fire count: {current_pending}")

        # Load snapshot from previous run
        prev_pending  = None
        prev_ts       = None
        snapshot_data = {}
        if os.path.exists(SNAPSHOT_FILE):
            try:
                with open(SNAPSHOT_FILE, "r") as f:
                    snapshot_data = json.load(f)
                prev_pending = snapshot_data.get("pending_fire_count")
                prev_ts      = snapshot_data.get("timestamp")
            except Exception:
                pass

        # Check if count is stuck at a non-zero value
        if (prev_pending is not None
                and prev_pending > 0
                and current_pending == prev_pending):
            age_note = f" (unchanged since {prev_ts})" if prev_ts else ""
            problems.append(
                f"⚠️ <b>Pending CAPI Fire Queue STUCK</b> — {current_pending} lead(s) "
                f"are waiting to fire to Meta{age_note}.\n"
                f"   Job C may be failing or the flag gate is blocking it."
            )
            log(f"Pending fire queue stuck at {current_pending}.", "WARNING")

        # Save current snapshot for next cycle
        snapshot_data["pending_fire_count"] = current_pending
        snapshot_data["timestamp"]          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(SNAPSHOT_FILE, "w") as f:
            json.dump(snapshot_data, f, indent=2)

    except Exception as e:
        log(f"Could not check pending fire queue: {e}", "WARNING")
        problems.append(f"⚠️ <b>Pending fire check failed</b>: {e}")

    return problems


def check_database_accessible():
    """
    Verify cls.db can be opened and the leads table is queryable.
    Returns a list of problem strings.
    """
    problems = []
    db_path  = os.path.join(BASE_DIR, "cls.db")
    if not os.path.exists(db_path):
        problems.append(
            f"🚨 <b>cls.db NOT FOUND</b> at {db_path}.\n"
            f"   The entire CLS pipeline is broken — no data can be read or written."
        )
        log("cls.db missing!", "ERROR")
        return problems

    try:
        s = cls_db.stats()
        log(f"DB OK — {s['total_leads']} leads, {s['pending_fire']} pending fire.")
    except Exception as e:
        problems.append(
            f"🚨 <b>cls.db QUERY FAILED</b>: {e}\n"
            f"   The database file exists but cannot be read. Possible corruption."
        )
        log(f"DB query failed: {e}", "ERROR")

    return problems


# ─────────────────────────────────────────────────────────────
# COMPOSE CYCLE REPORT
# ─────────────────────────────────────────────────────────────

def compose_cycle_report(flag_results, log_results, pending_count, has_problems,
                         flag_counts=None):
    """
    Build a per-cycle Telegram report showing a green tick or red alert
    per job. Sent every 2-hour cycle regardless of health status.

    flag_results  : dict       — {label: (ok:bool, detail:str)}
    log_results   : dict       — {label: (ok:bool, detail:str)}
    pending_count : int        — current pending fire queue count
    has_problems  : bool       — True if any check failed
    flag_counts   : dict|None  — {label: int|None} per-run counts from logs
    """
    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    header  = "🚨 <b>CLS Alert</b>" if has_problems else "✅ <b>CLS Health Report</b>"

    try:
        s = cls_db.stats()
        stats_line = (
            f"📊 <b>DB:</b> {s['total_leads']} leads | "
            f"{s['with_leadgen_id']} with leadgen_id | "
            f"{pending_count} pending fire"
        )
    except Exception:
        stats_line = "📊 DB stats unavailable"

    lines = [
        header,
        f"🕐 <b>Time:</b> {now_str}",
        stats_line,
        "",
        "<b>── Completion Flags ──</b>",
    ]

    # Human-friendly suffix for each job's count
    _COUNT_SUFFIXES = {
        "Job A (Meta Fetcher)": "new leads fetched",
        "Job B (Sell.do Sync)": "stage changes",
        "Job C (CAPI Firer)"  : "events fired",
    }

    # Flag results per job — with optional per-cycle count appended
    for label, (ok, detail) in flag_results.items():
        icon = "✅" if ok else "🚨"
        count_str = ""
        if flag_counts:
            c = flag_counts.get(label)
            if c is not None:
                suffix = _COUNT_SUFFIXES.get(label, "processed")
                count_str = f" — {c} {suffix} this round"
        lines.append(f"{icon} <b>{label}</b> — {detail}{count_str}")

    lines += ["", "<b>── Log File Scan ──</b>"]

    # Log scan results per job
    for label, (ok, detail) in log_results.items():
        icon = "✅" if ok else "🔴"
        lines.append(f"{icon} <b>{label}</b> — {detail}")

    # Pending fire queue
    lines += ["", "<b>── CAPI Fire Queue ──</b>"]
    if pending_count == 0:
        lines.append("✅ <b>Queue</b> — 0 pending (all fired)")
    else:
        lines.append(f"⚠️ <b>Queue</b> — {pending_count} lead(s) pending fire")

    if has_problems:
        lines += [
            "",
            "─────────────────────────",
            "⚠️ <b>Action required.</b> Check C:\\CLS\\*_log.txt",
            "Run: <code>python cls_watchdog.py</code> after fixing.",
        ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# COMPOSE DAILY SUMMARY  (v2.3)
# ─────────────────────────────────────────────────────────────

def compose_daily_summary(a_total, b_total, c_total,
                          cycle_count=None, first_run=None, last_run=None,
                          owner_summary=None):
    """
    Build the end-of-day summary Telegram message.
    Sent once — on the last watchdog cycle of the day (hour == 18).

    Counts are totals across all of today's cycles, summed from each
    job's log file by extract_daily_total().

    v2.4:
      cycle_count/first_run/last_run — computed by extract_daily_cycle_info()
        from Job A's log instead of a hardcoded "5 cycles (10:30 -> 18:30)"
        string, so the line is always correct regardless of today's actual
        cadence or any missed/extra runs.
      owner_summary — list of dicts from cls_db.get_daily_owner_summary(),
        e.g. [{"owner": "Elohar", "new_leads": 4, "stage_changes": 9,
        "capi_fired": 6}, ...]. Appended as a per-salesperson breakdown
        section below the company-wide totals. Pass None/[] to omit the
        section entirely (e.g. if the DB query fails — the top summary
        still sends).
    """
    today_str = datetime.now().strftime("%d %b %Y")
    lines = [
        f"📋 <b>CLS Daily Summary — {today_str}</b>",
        "",
        f"📥 New leads fetched    : <b>{a_total}</b>",
        f"🔄 Stage changes        : <b>{b_total}</b>",
        f"🚀 CAPI events fired    : <b>{c_total}</b>",
    ]

    if owner_summary:
        lines += ["", "<b>── By Salesperson ──</b>"]
        for row in owner_summary:
            lines += [
                f"👤 <b>{row['owner']}</b>",
                f"   New leads fetched : {row['new_leads']}",
                f"   Stage changes     : {row['stage_changes']}",
                f"   CAPI events       : {row['capi_fired']}",
            ]

    lines.append("")
    if cycle_count:
        window = f" ({first_run} → {last_run})" if first_run and last_run else ""
        lines.append(f"CLS ran {cycle_count} cycle(s) today{window}.")
    else:
        lines.append("CLS cycle count unavailable today (Job A log had no matching runs).")

    return "\n".join(lines)


# (daily-ok-snapshot logic removed — watchdog now sends a report every cycle)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run(force_alert=False):
    log("=" * 55)
    log("CLS WATCHDOG — Health Check — START")
    log("=" * 55)

    # ── Load Telegram credentials ──
    env       = load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = env.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        log("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing from .env — "
            "report will be logged but NOT sent to Telegram.", "WARNING")
        telegram_ok = False
    else:
        telegram_ok = True

    # ── Check 1: Database ──
    log("--- Check 1: Database accessibility ---")
    db_problems = check_database_accessible()

    # ── Check 2: Completion flags — collect per-job results ──
    log("--- Check 2: Completion flags ---")
    flag_results  = {}   # {label: (ok, detail_str)}
    flag_problems = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    for label, flag_name in JOB_FLAGS.items():
        ts = cls_db.get_flag(flag_name)
        if not ts:
            detail = f"flag '{flag_name}' MISSING"
            flag_results[label]  = (False, detail)
            flag_problems.append(f"🚨 <b>{label}</b> — {detail}")
            log(f"Flag '{flag_name}' missing.", "WARNING")
        else:
            try:
                completed = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                age_min   = (datetime.now() - completed).total_seconds() / 60
                if age_min > FLAG_MAX_AGE_MIN:
                    hours  = age_min / 60
                    detail = f"STALE — last: {ts} ({hours:.1f}h ago)"
                    flag_results[label]  = (False, detail)
                    flag_problems.append(
                        f"⚠️ <b>{label}</b> — {detail}. "
                        f"Failed ~{int(hours // 2)} consecutive cycle(s)."
                    )
                    log(f"Flag '{flag_name}' stale: {hours:.1f}h ago.", "WARNING")
                else:
                    detail = f"OK — last run {age_min:.0f} min ago"
                    flag_results[label] = (True, detail)
                    log(f"Flag '{flag_name}' OK — last: {ts} ({age_min:.0f} min ago).")
            except Exception as e:
                detail = f"timestamp parse error: {ts}"
                flag_results[label]  = (False, detail)
                flag_problems.append(f"⚠️ <b>{label}</b> — {detail}")
                log(f"Flag '{flag_name}' parse error: {e}", "WARNING")

    # ── Per-cycle activity counts — parsed from log file tails (v2.3) ──
    # No changes to any job script needed — the counts are already in the logs.
    log("--- Reading per-cycle activity counts from logs ---")
    flag_counts = {
        "Job A (Meta Fetcher)": extract_run_count(
            JOB_LOG_FILES["Job A (Meta Fetcher)"],
            r"TOTAL: \d+ pulled, (\d+) upserted",
        ),
        "Job B (Sell.do Sync)": extract_run_count(
            JOB_LOG_FILES["Job B (Sell.do Sync)"],
            r"Stage changes detected this run: (\d+)",
        ),
        "Job C (CAPI Firer)": extract_run_count(
            JOB_LOG_FILES["Job C (CAPI Firer)"],
            r"Marked (\d+) leads as fired",
            zero_indicator="No stage changes to fire this run",
        ),
    }
    log(f"Counts this cycle — "
        f"A:{flag_counts['Job A (Meta Fetcher)']} "
        f"B:{flag_counts['Job B (Sell.do Sync)']} "
        f"C:{flag_counts['Job C (CAPI Firer)']}")

    # ── Check 3: Log files — collect per-job results ──
    log("--- Check 3: Log files for errors ---")
    log_results  = {}   # {label: (ok, detail_str)}
    log_problems = []
    today = datetime.now().strftime("%Y-%m-%d")
    for label, log_path in JOB_LOG_FILES.items():
        if not os.path.exists(log_path):
            log_results[label] = (True, "no log yet (job may not have run today)")
            log(f"Log not found (skipping): {log_path}")
            continue

        # Staleness check
        try:
            mtime     = os.path.getmtime(log_path)
            mtime_dt  = datetime.fromtimestamp(mtime)
            age_hours = (datetime.now() - mtime_dt).total_seconds() / 3600
            if age_hours > 4:
                detail = f"log NOT UPDATED in {age_hours:.1f}h (Task Scheduler issue?)"
                log_results[label]  = (False, detail)
                log_problems.append(f"⚠️ <b>{label}</b> — {detail}")
                log(f"Log stale ({age_hours:.1f}h): {log_path}", "WARNING")
                continue
        except Exception as e:
            log(f"Could not check mtime for {log_path}: {e}", "WARNING")

        # Error line scan
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail   = lines[-LOG_TAIL_LINES:]
            errors = [
                l.strip() for l in tail
                if "[ERROR]" in l and today in l
            ]
            if errors:
                shown   = errors[-3:]
                snippet = "\n".join(f"   <code>{e[:120]}</code>" for e in shown)
                detail  = f"{len(errors)} ERROR(s) in today's log"
                log_results[label]  = (False, detail)
                log_problems.append(
                    f"🔴 <b>{label}</b> — {detail}:\n{snippet}"
                    + (f"\n   ...and {len(errors)-3} more." if len(errors) > 3 else "")
                )
                log(f"{len(errors)} ERROR(s) found in {log_path} today.", "WARNING")
            else:
                log_results[label] = (True, "no errors today")
                log(f"No errors in {label} log today.")
        except Exception as e:
            log_results[label]  = (False, f"could not read log: {e}")
            log(f"Could not read log {log_path}: {e}", "WARNING")

    # ── Check 4: Pending fire queue ──
    log("--- Check 4: Pending fire queue ---")
    queue_problems = check_pending_fire_queue()
    try:
        pending_count = len(cls_db.get_unfired_leads())
    except Exception:
        pending_count = -1

    # ── Aggregate all problems ──
    all_problems = db_problems + flag_problems + log_problems + queue_problems
    has_problems = bool(all_problems)

    log("=" * 55)

    if has_problems:
        log(f"RESULT: {len(all_problems)} issue(s) found.", "WARNING")
    else:
        log("RESULT: All checks passed — CLS is healthy.")

    # ── Build and send per-cycle Telegram report ──
    # Sends every cycle — green ticks when healthy, alerts when not.
    if force_alert:
        log("--force flag used — sending test report.")

    report_msg = compose_cycle_report(
        flag_results, log_results, pending_count, has_problems, flag_counts
    )

    # Log the report
    log("Telegram report:")
    for line in report_msg.split("\n"):
        log(f"  {line}")

    if telegram_ok:
        tg_sent = send_telegram(bot_token, chat_id, report_msg)
        if not tg_sent:
            log("Telegram unavailable — attempting Brevo email fallback.", "WARNING")
            send_brevo_alert(env, report_msg)
    else:
        log("Telegram not configured — report logged only.", "WARNING")

    # ── End-of-day daily summary — sent ONLY on the 17:55 run (v2.3) ──
    # Scans the full log files and sums all 5 cycles for today.
    if datetime.now().hour == 18:
        log("--- Last cycle of the day — computing daily totals ---")
        a_total = extract_daily_total(
            JOB_LOG_FILES["Job A (Meta Fetcher)"],
            r"TOTAL: \d+ pulled, (\d+) upserted",
        )
        b_total = extract_daily_total(
            JOB_LOG_FILES["Job B (Sell.do Sync)"],
            r"Stage changes detected this run: (\d+)",
        )
        c_total = extract_daily_total(
            JOB_LOG_FILES["Job C (CAPI Firer)"],
            r"Marked (\d+) leads as fired",
        )
        log(f"Daily totals — A:{a_total} leads | B:{b_total} changes | C:{c_total} fired")

        # v2.4 — actual cycle count/window, computed instead of hardcoded
        cycle_count, first_run, last_run = extract_daily_cycle_info(
            JOB_LOG_FILES["Job A (Meta Fetcher)"],
            r"TOTAL: \d+ pulled, \d+ upserted",
        )
        log(f"Cycles today: {cycle_count} ({first_run} -> {last_run})")

        # v2.4 — per-salesperson breakdown, straight from cls.db
        try:
            owner_summary = cls_db.get_daily_owner_summary()
            log(f"Owner summary: {owner_summary}")
        except Exception as e:
            log(f"get_daily_owner_summary() failed: {e}", "WARNING")
            owner_summary = None

        daily_msg = compose_daily_summary(
            a_total, b_total, c_total,
            cycle_count=cycle_count, first_run=first_run, last_run=last_run,
            owner_summary=owner_summary,
        )

        log("Sending daily summary to Telegram...")
        if telegram_ok:
            tg_sent = send_telegram(bot_token, chat_id, daily_msg)
            if not tg_sent:
                log("Telegram unavailable for daily summary — trying Brevo.", "WARNING")
                send_brevo_alert(env, daily_msg)
        else:
            log("Telegram not configured — daily summary logged only.", "WARNING")

    log("CLS WATCHDOG — END")
    log("=" * 55)


# ─────────────────────────────────────────────────────────────
# SELF-TEST MODE
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Test alert channel connectivity — no DB or file checks.
    Run after setting up credentials to confirm delivery works.

      python cls_watchdog.py --selftest           # Telegram only
      python cls_watchdog.py --selftest --brevo  # Telegram + Brevo
    """
    print("=" * 55)
    print(" CLS WATCHDOG — SELF TEST")
    print("=" * 55)

    env       = load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = env.get("TELEGRAM_CHAT_ID", "")

    # ── Telegram ──
    if not bot_token:
        print("[FAIL] TELEGRAM_BOT_TOKEN not found in .env")
        print("       Add: TELEGRAM_BOT_TOKEN=your_token")
    elif not chat_id:
        print("[FAIL] TELEGRAM_CHAT_ID not found in .env")
        print("       Add: TELEGRAM_CHAT_ID=your_chat_id")
    else:
        print(f"[OK]   TELEGRAM_BOT_TOKEN found (last 6 chars: ...{bot_token[-6:]})")
        print(f"[OK]   TELEGRAM_CHAT_ID: {chat_id}")
        print()
        print("Sending test message to Telegram...")
        msg = (
            "✅ <b>CLS Watchdog — Connection Test</b>\n"
            "If you see this, Telegram alerts are working correctly.\n"
            f"Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
            "CLS monitoring is active."
        )
        success = send_telegram(bot_token, chat_id, msg)
        if success:
            print("[OK]   Test message delivered. Check your Telegram.")
        else:
            print("[FAIL] Telegram delivery failed. "
                  "Run with --selftest --brevo to test email fallback.")

    # ── Brevo (optional: only if --brevo flag passed) ──
    if "--brevo" in sys.argv:
        print()
        print("─" * 40)
        print("Testing Brevo email fallback...")
        brevo_key = env.get("BREVO_API_KEY", "")
        if not brevo_key:
            print("[FAIL] BREVO_API_KEY not found in .env")
        else:
            print(f"[OK]   BREVO_API_KEY found (last 6 chars: ...{brevo_key[-6:]})")
            test_msg = (
                "✅ <b>CLS Watchdog — Brevo Fallback Test</b>\n"
                "If you received this email, the Brevo fallback is working.\n"
                f"Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
                "This channel activates automatically when Telegram is unavailable."
            )
            ok = send_brevo_alert(env, test_msg)
            if ok:
                print("[OK]   Brevo email sent. Check sales1@asianbuild.in inbox.")
            else:
                print("[FAIL] Brevo send failed. Check BREVO_API_KEY and logs.")

    print()
    print("Self-test complete.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--force" in sys.argv:
        run(force_alert=True)
    else:
        run(force_alert=False)
