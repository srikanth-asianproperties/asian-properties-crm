"""
=============================================================
cls_monday_weekly_report.py  —  CLS Monday Morning Weekly Report
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.0 (2026-08-17) — Initial version. Automated 5-metric weekly summary
  (leads generated, site visits scheduled, site visits conducted,
  bookings weekday/weekend) for the most recently completed Mon-Sun
  week, sent via Telegram every Monday morning. Ops-only script, same
  status as cls_weekend_visits_report.py (not "Job E" in
  job_results.txt — see write_job_result() call below) — it doesn't
  participate in the A-B-C-D flag-gated hand-off chain, it just reads
  cls_db.get_monday_weekly_report_stats() (cls_db.py v2.60) on its own
  Monday-morning Task Scheduler trigger.

WHAT THIS SCRIPT DOES
----------------------
Every Monday morning (Task Scheduler, see run_cls_monday_weekly_
report.bat), computes the most recently completed Mon-Sun week and
sends Srikanth a Telegram message (HTML parse_mode, same as
cls_watchdog.py) with the 5 headline numbers plus a computed Total
Bookings line. Falls back to a Brevo email if Telegram is unavailable
— same primary/fallback pattern cls_watchdog.py's run() uses, reusing
its load_env()/send_telegram()/send_brevo_alert() rather than
duplicating that logic.

USAGE
-----
  python cls_monday_weekly_report.py             # normal run
  python cls_monday_weekly_report.py --selftest  # sends a fixed test
                                                    # message, no DB query
"""

import os
import sys
from datetime import datetime, timedelta

BASE_DIR = r"D:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db
import cls_watchdog   # reuse load_env()/send_telegram()/send_brevo_alert() —
                       # its own run logic lives behind __main__, so importing
                       # it here has no side effects.

LOG_FILE = os.path.join(BASE_DIR, "cls_monday_weekly_report_log.txt")

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

def _last_week_range():
    """
    The most recently completed Mon-Sun week, relative to today —
    robust to manual re-runs on any day of the week, not just Monday.
    """
    today = datetime.now().date()
    this_monday = today - timedelta(days=today.weekday())
    week_end = this_monday - timedelta(days=1)      # last Sunday
    week_start = week_end - timedelta(days=6)        # Monday before that
    return week_start, week_end


def build_message(stats, week_start, week_end):
    """
    Builds the HTML-formatted Telegram message. Returns a string.
    """
    date_range = f"{week_start.strftime('%a, %b %d')} – {week_end.strftime('%a, %b %d')}"

    lines = [
        f"📊 <b>Weekly Report — {date_range}</b>",
        "",
        f"🧲 Leads Generated: <b>{stats['leads_generated']}</b>",
        f"🗓️ Site Visits Scheduled: <b>{stats['site_visits_scheduled']}</b>",
        f"✅ Site Visits Conducted: <b>{stats['site_visits_conducted']}</b>",
        f"💼 Bookings (Weekdays): <b>{stats['bookings_weekday']}</b>",
        f"🏡 Bookings (Weekend): <b>{stats['bookings_weekend']}</b>",
        "",
        f"Total Bookings: <b>{stats['bookings_total']}</b>",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    log("=" * 55)
    log("CLS MONDAY WEEKLY REPORT — START")
    log("=" * 55)

    week_start, week_end = _last_week_range()
    stats = cls_db.get_monday_weekly_report_stats(week_start.isoformat(), week_end.isoformat())
    message = build_message(stats, week_start, week_end)
    log(f"Week {week_start.isoformat()} - {week_end.isoformat()}: "
        f"leads={stats['leads_generated']}, "
        f"visits_scheduled={stats['site_visits_scheduled']}, "
        f"visits_conducted={stats['site_visits_conducted']}, "
        f"bookings_weekday={stats['bookings_weekday']}, "
        f"bookings_weekend={stats['bookings_weekend']}")

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

    summary = f"week {week_start.isoformat()}-{week_end.isoformat()}, delivered via {'Telegram' if bot_token and chat_id else 'Brevo'}" \
        if sent else f"week {week_start.isoformat()}-{week_end.isoformat()} computed, but delivery FAILED (Telegram and Brevo both failed)"
    cls_db.write_job_result("Monday Weekly Report", sent, summary)

    log("CLS MONDAY WEEKLY REPORT — END")
    log("=" * 55)
    return sent


# ─────────────────────────────────────────────────────────────
# SELF-TEST MODE
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Sends a fixed test message via the same send path — no DB query.
    Same self-test shape as cls_weekend_visits_report.py --selftest.
    """
    print("=" * 55)
    print(" CLS MONDAY WEEKLY REPORT — SELF TEST")
    print("=" * 55)

    env = cls_watchdog.load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    msg = (
        "✅ <b>CLS Monday Weekly Report — Connection Test</b>\n"
        "If you see this, the Monday weekly report can reach you.\n"
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
