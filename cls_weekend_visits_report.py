"""
=============================================================
cls_weekend_visits_report.py  —  CLS Weekend Site Visits Report
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.0 (2026-08-17) — Initial version. Replaces Srikanth's manual Friday
  headcount ask ("how many site visits this weekend?") with an automated
  Telegram report. Ops-only script, outside the Job A-D pipeline naming
  (not "Job E" in job_results.txt — see write_job_result() call below) —
  it doesn't participate in the A-B-C-D flag-gated hand-off chain, it
  just reads cls_db.get_weekend_site_visits() (cls_db.py v2.59) on its
  own Friday-afternoon Task Scheduler trigger. No Sell.do-side check —
  Sell.do was fully retired 2026-08-15 (see cls_db.py v2.57's
  changelog), so site_visits is the sole, authoritative source now.

WHAT THIS SCRIPT DOES
----------------------
Every Friday afternoon (Task Scheduler, see run_cls_weekend_visits_
report.bat), pulls every 'scheduled' site visit falling on the coming
Saturday or Sunday, groups it by salesperson, and sends Srikanth a
Telegram message (HTML parse_mode, same as cls_watchdog.py) with a
per-salesperson breakdown. Falls back to a Brevo email if Telegram is
unavailable — same primary/fallback pattern cls_watchdog.py's run()
uses, reusing its load_env()/send_telegram()/send_brevo_alert() rather
than duplicating that logic.

USAGE
-----
  python cls_weekend_visits_report.py             # normal run
  python cls_weekend_visits_report.py --selftest  # sends a fixed test
                                                    # message, no DB query
"""

import os
import sys
from datetime import datetime, timedelta
from itertools import groupby

BASE_DIR = r"D:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db
import cls_watchdog   # reuse load_env()/send_telegram()/send_brevo_alert() —
                       # its own run logic lives behind __main__, so importing
                       # it here has no side effects.

LOG_FILE = os.path.join(BASE_DIR, "cls_weekend_visits_log.txt")

# pythonw.exe has no console — sys.stdout is None. Guard before reconfiguring.
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] {message}"
    try:
        if sys.stdout is not None:
            print(entry)
    except Exception:
        pass
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# MESSAGE BUILDING
# ─────────────────────────────────────────────────────────────

def _weekend_dates():
    """
    Saturday/Sunday of the upcoming weekend — same 'stay put if today
    IS Saturday' rule as cls_db.get_weekend_site_visits()'s SQL
    ('weekday 6'), computed here in Python purely for display in the
    Telegram header. Python's date.weekday(): Monday=0 ... Saturday=5,
    Sunday=6 — days_ahead=0 when today is already Saturday.
    """
    today = datetime.now().date()
    days_ahead = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_ahead)
    sunday = saturday + timedelta(days=1)
    return saturday, sunday


def _format_visit_time(scheduled_at):
    """Same 12-hour display convention as app.py's 'ampm' Jinja filter."""
    if not scheduled_at:
        return "—"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(scheduled_at, fmt)
            return dt.strftime("%a, %I:%M %p")
        except ValueError:
            continue
    return scheduled_at


def build_message(visits):
    """
    Builds the HTML-formatted Telegram message. Returns a string.
    Zero-visits case still returns a real message — never skip sending
    silently, Srikanth should know the job ran even when there's nothing
    to report.
    """
    saturday, sunday = _weekend_dates()
    date_range = f"{saturday.strftime('%a, %b %d')} – {sunday.strftime('%a, %b %d')}"
    total = len(visits)

    if total == 0:
        return (
            f"📅 <b>Weekend Site Visits — {date_range}</b>\n"
            f"No site visits scheduled for this weekend."
        )

    lines = [
        f"📅 <b>Weekend Site Visits — {date_range}</b>",
        f"Total: <b>{total}</b> visit(s) scheduled",
    ]
    for owner, owner_visits in groupby(visits, key=lambda v: v["lead_owner"] or "Unassigned"):
        owner_visits = list(owner_visits)
        lines.append(f"\n👤 <b>{owner}</b> ({len(owner_visits)})")
        for v in owner_visits:
            when = _format_visit_time(v["scheduled_at"])
            phone = v["phone_raw"] or "—"
            project = v["project"] or "—"
            lines.append(f"• {v['full_name']} — {phone} — {project} — {when}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    log("=" * 55)
    log("CLS WEEKEND SITE VISITS REPORT — START")
    log("=" * 55)

    visits = cls_db.get_weekend_site_visits()
    message = build_message(visits)
    log(f"{len(visits)} site visit(s) found for the upcoming weekend.")

    env = cls_watchdog.load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")

    sent = False
    if not bot_token or not chat_id:
        log("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing from .env — "
            "trying Brevo fallback directly.", "WARNING")
    else:
        sent = cls_watchdog.send_telegram(bot_token, chat_id, message)
        if not sent:
            log("Telegram send failed — attempting Brevo email fallback.", "WARNING")

    if not sent:
        sent = cls_watchdog.send_brevo_alert(env, message)

    summary = f"{len(visits)} visit(s), delivered via {'Telegram' if bot_token and chat_id else 'Brevo'}" \
        if sent else f"{len(visits)} visit(s) found, but delivery FAILED (Telegram and Brevo both failed)"
    cls_db.write_job_result("Weekend Site Visits Report", sent, summary)

    log("CLS WEEKEND SITE VISITS REPORT — END")
    log("=" * 55)
    return sent


# ─────────────────────────────────────────────────────────────
# SELF-TEST MODE
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Sends a fixed test message via the same send path — no DB query.
    Same self-test shape as cls_watchdog.py --selftest.
    """
    print("=" * 55)
    print(" CLS WEEKEND SITE VISITS REPORT — SELF TEST")
    print("=" * 55)

    env = cls_watchdog.load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    msg = (
        "✅ <b>CLS Weekend Site Visits Report — Connection Test</b>\n"
        "If you see this, the weekend visits report can reach you.\n"
        f"Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
    )

    if not bot_token or not chat_id:
        print("[FAIL] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env")
    else:
        print(f"[OK]   TELEGRAM_BOT_TOKEN found (last 6 chars: ...{bot_token[-6:]})")
        print(f"[OK]   TELEGRAM_CHAT_ID: {chat_id}")
        print()
        print("Sending test message to Telegram...")
        success = cls_watchdog.send_telegram(bot_token, chat_id, msg)
        if success:
            print("[OK]   Test message delivered. Check your Telegram.")
        else:
            print("[FAIL] Telegram delivery failed. Trying Brevo fallback...")
            ok = cls_watchdog.send_brevo_alert(env, msg)
            if ok:
                print("[OK]   Brevo fallback email sent. Check sales1@asianbuild.in inbox.")
            else:
                print("[FAIL] Brevo fallback also failed. Check .env credentials and logs.")

    print()
    print("Self-test complete.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
