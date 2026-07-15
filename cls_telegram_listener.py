"""
=============================================================
cls_telegram_listener.py  —  CLS Telegram Command Interface
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

WHAT THIS SCRIPT DOES
----------------------
Listens for commands you type in Telegram and replies with
live data from cls.db. Makes the watchdog bot two-way:

  YOU TYPE    BOT REPLIES WITH
  /help       list of all commands
  /stats      full DB summary (leads, CAPI, drip enrolled)
  /today      today's new leads + CAPI fires (by project)
  /health     on-demand health check (flags + pending queue)
  /pending    pending CAPI fire count, broken down by project

HOW IT WORKS — LONG POLLING
-----------------------------
Uses Telegram's getUpdates long-polling API.
Each call hangs for up to 30 seconds waiting for a new message.
When you type a command, the call returns immediately with it.
No webhook, no server, no new credentials.
Same bot token and chat_id already in .env.

SECURITY
--------
Checks every incoming message against TELEGRAM_CHAT_ID from
.env before responding. Any message from any other chat_id is
silently ignored — the bot is private to you.

OFFSET PERSISTENCE
------------------
Saves the last processed update_id to cls_telegram_offset.json
after every message. On restart, picks up from where it left
off — never re-processes an old command.

RESILIENCE
----------
If getUpdates times out (Telegram blocked, network outage):
logs the failure and retries after 60 seconds. Never crashes.

SCHEDULE — Task Scheduler
--------------------------
Run once at Windows startup. Loops forever internally.
  Program : python
  Args    : C:\CLS\cls_telegram_listener.py
  Trigger : At startup
  Settings: Restart on failure, every 1 minute

Or register via schtasks (see deployment instructions below).

RUN
---
  python cls_telegram_listener.py          # start listening
  python cls_telegram_listener.py --test   # send one test message, then exit

DEPLOYMENT — schtasks command (run once in Admin CMD)
------------------------------------------------------
  schtasks /Create /TN "CLS Telegram Listener" ^
    /TR "\"C:\\Users\\Srikanth\\AppData\\Local\\Programs\\Python\\Python314\\python.exe\" C:\\CLS\\cls_telegram_listener.py" ^
    /SC ONSTART /DELAY 0001:00 /RL HIGHEST /F
=============================================================
"""

import os
import sys
import json
import sqlite3
import requests
import time
from datetime import datetime

# Task Scheduler launches pythonw.exe from System32, not C:\CLS\,
# so Python's module search path won't include cls_db.py by default.
# BASE_DIR is defined here early (before the main config block) so
# the sys.path fix can reference it before import cls_db.
BASE_DIR = r"C:\CLS"
sys.path.insert(0, BASE_DIR)

import cls_db   # public functions: stats(), get_flag(), get_unfired_leads()

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

ENV_FILE     = os.path.join(BASE_DIR, ".env")
LOG_FILE     = os.path.join(BASE_DIR, "cls_listener_log.txt")
OFFSET_FILE  = os.path.join(BASE_DIR, "cls_telegram_offset.json")
DB_FILE      = os.path.join(BASE_DIR, "cls.db")

# Flag staleness threshold — same as watchdog (3 hours = one missed cycle)
FLAG_MAX_AGE_MIN = 180

# Long-poll wait time (seconds). Request hangs this long for new messages.
# Telegram max is 60s; 30s is safe and responsive.
POLL_TIMEOUT = 30

# Seconds to wait before retrying when getUpdates itself fails (network error)
RETRY_DELAY_SEC = 60

# ─────────────────────────────────────────────────────────────
# UNICODE SAFETY (Windows cp1252)
# ─────────────────────────────────────────────────────────────

# pythonw.exe has no console — sys.stdout is None.
# Guard before reconfiguring to avoid AttributeError at startup.
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

def log(msg, level="INFO"):
    ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] {msg}"
    # pythonw.exe: stdout is None — guard before printing
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
# DATABASE HELPER
# ─────────────────────────────────────────────────────────────

def _db():
    """Open a direct sqlite3 connection to cls.db (read-only queries)."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────
# TELEGRAM API — INBOUND (getUpdates)
# ─────────────────────────────────────────────────────────────

def get_updates(bot_token, offset=None):
    """
    Long-poll Telegram for new messages.
    Hangs up to POLL_TIMEOUT seconds waiting for a message.
    Returns list of update dicts on success, None on network failure.
    Token is sanitized from any error logs.
    """
    url    = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params = {
        "timeout"         : POLL_TIMEOUT,
        "allowed_updates" : ["message"],
    }
    if offset is not None:
        params["offset"] = offset
    try:
        # timeout = POLL_TIMEOUT + 10 so the requests call doesn't
        # expire before Telegram's own server-side timeout does.
        resp = requests.get(url, params=params, timeout=POLL_TIMEOUT + 10)
        data = resp.json()
        if data.get("ok"):
            return data["result"]
        else:
            log(f"getUpdates API error: {data.get('description', 'unknown')}", "ERROR")
            return None
    except Exception as e:
        err_str = str(e).replace(bot_token, "***REDACTED***")
        log(f"getUpdates failed: {err_str}", "ERROR")
        return None


# ─────────────────────────────────────────────────────────────
# TELEGRAM API — OUTBOUND (sendMessage)
# ─────────────────────────────────────────────────────────────

def send_reply(bot_token, chat_id, text):
    """
    Send a reply to the chat. parse_mode=HTML for bold/code formatting.
    Returns True on success, False on failure.
    """
    url     = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id"    : chat_id,
        "text"       : text,
        "parse_mode" : "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            return True
        else:
            log(f"sendMessage error: {data.get('description', 'unknown')}", "ERROR")
            return False
    except Exception as e:
        err_str = str(e).replace(bot_token, "***REDACTED***")
        log(f"sendMessage failed: {err_str}", "ERROR")
        return False


# ─────────────────────────────────────────────────────────────
# OFFSET PERSISTENCE
# ─────────────────────────────────────────────────────────────

def load_offset():
    """Load last processed update_id from disk. Returns None if not found."""
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r") as f:
                return json.load(f).get("offset", None)
        except Exception:
            pass
    return None


def save_offset(offset):
    """Persist current offset so restarts don't re-process old commands."""
    try:
        with open(OFFSET_FILE, "w") as f:
            json.dump({"offset": offset}, f)
    except Exception as e:
        log(f"Could not save offset: {e}", "WARNING")


# ─────────────────────────────────────────────────────────────
# COMMAND HANDLERS
# Each returns a plain string (with HTML tags for bold/code).
# ─────────────────────────────────────────────────────────────

def handle_help():
    return (
        "🤖 <b>CLS Command Interface</b>\n\n"
        "Commands:\n\n"
        "/stats    — full DB summary\n"
        "/today    — today's new leads + CAPI fires\n"
        "/health   — on-demand health check\n"
        "/pending  — pending CAPI fire count\n"
        "/help     — this message"
    )


def handle_stats():
    """Full DB summary — leads, leadgen coverage, drip enrolment, pending fire."""
    try:
        s = cls_db.stats()
        conn = _db()
        drip = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE drip_enrolled_at IS NOT NULL"
        ).fetchone()["c"]
        conn.close()
        return (
            f"📊 <b>CLS Stats</b>\n\n"
            f"Total leads       : {s['total_leads']}\n"
            f"With leadgen_id   : {s['with_leadgen_id']}\n"
            f"Sell.do only      : {s['selldo_only']}\n"
            f"Drip enrolled     : {drip}\n"
            f"Pending CAPI fire : {s['pending_fire']}"
        )
    except Exception as e:
        return f"❌ /stats failed: {e}"


def handle_today():
    """Today's new leads (by project) + CAPI events fired today."""
    try:
        conn  = _db()
        today = datetime.now().strftime("%Y-%m-%d")

        # New leads ingested today (cls_created_at is set by Job A / Job B)
        new_leads = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE cls_created_at LIKE ?",
            (f"{today}%",)
        ).fetchone()["c"]

        # Breakdown by project
        proj_rows = conn.execute(
            """SELECT project, COUNT(*) c FROM leads
               WHERE cls_created_at LIKE ?
               GROUP BY project ORDER BY c DESC""",
            (f"{today}%",)
        ).fetchall()

        # CAPI events fired today (fired_at in events_log)
        capi_today = conn.execute(
            "SELECT COUNT(*) c FROM events_log WHERE fired_at LIKE ?",
            (f"{today}%",)
        ).fetchone()["c"]

        conn.close()

        proj_lines = "\n".join(
            f"  {r['project'] or 'Unknown'}: {r['c']}" for r in proj_rows
        ) or "  None"

        return (
            f"📅 <b>Today — {today}</b>\n\n"
            f"New leads: {new_leads}\n"
            f"{proj_lines}\n\n"
            f"CAPI events fired: {capi_today}"
        )
    except Exception as e:
        return f"❌ /today failed: {e}"


def handle_health():
    """On-demand health check: completion flags + pending fire queue."""
    try:
        now   = datetime.now()
        lines = [f"🏥 <b>CLS Health</b> — {now.strftime('%d %b, %I:%M %p')}\n"]

        # ── Completion flags ──
        flags = {
            "Job A (Meta Fetcher)": "meta_fetch",
            "Job B (Sell.do Sync)": "selldo_sync",
            "Job C (CAPI Firer)"  : "capi_fire",
        }
        lines.append("<b>── Completion Flags ──</b>")
        for label, flag_name in flags.items():
            ts = cls_db.get_flag(flag_name)
            if not ts:
                lines.append(f"🚨 {label} — flag MISSING")
            else:
                try:
                    completed = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    age_min   = (now - completed).total_seconds() / 60
                    if age_min > FLAG_MAX_AGE_MIN:
                        lines.append(
                            f"⚠️ {label} — STALE "
                            f"({age_min / 60:.1f}h ago)"
                        )
                    else:
                        lines.append(
                            f"✅ {label} — OK "
                            f"({age_min:.0f} min ago)"
                        )
                except Exception:
                    lines.append(f"⚠️ {label} — timestamp parse error")

        # ── Pending fire queue ──
        pending = len(cls_db.get_unfired_leads())
        lines.append("")
        lines.append("<b>── CAPI Fire Queue ──</b>")
        if pending == 0:
            lines.append("✅ Queue — 0 pending (all fired)")
        else:
            lines.append(f"⚠️ Queue — {pending} lead(s) pending fire")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ /health failed: {e}"


def handle_pending():
    """Pending CAPI fire count with per-project breakdown."""
    try:
        pending = len(cls_db.get_unfired_leads())

        if pending == 0:
            return "✅ <b>Pending CAPI Fire</b>\n\nQueue is empty — all leads fired."

        conn      = _db()
        proj_rows = conn.execute("""
            SELECT project, COUNT(*) c FROM leads
            WHERE current_stage IS NOT NULL
              AND current_stage != ''
              AND (last_fired_stage IS NULL
                   OR current_stage != last_fired_stage)
            GROUP BY project ORDER BY c DESC
        """).fetchall()
        conn.close()

        proj_lines = "\n".join(
            f"  {r['project'] or 'Unknown'}: {r['c']}" for r in proj_rows
        )
        return (
            f"⚠️ <b>Pending CAPI Fire: {pending} lead(s)</b>\n\n"
            f"{proj_lines}"
        )
    except Exception as e:
        return f"❌ /pending failed: {e}"


def handle_unknown(cmd):
    return (
        f"❓ Unknown: <code>{cmd}</code>\n"
        "Type /help to see available commands."
    )


# ─────────────────────────────────────────────────────────────
# COMMAND ROUTER
# ─────────────────────────────────────────────────────────────

def route_command(text):
    """
    Parse the first word of the message and dispatch to the right handler.
    Case-insensitive. /start is treated as /help (Telegram sends /start
    automatically when a user first opens the bot).
    """
    if not text:
        return None
    first_word = text.strip().lower().split()[0]
    if first_word in ("/help", "/start"):
        return handle_help()
    elif first_word == "/stats":
        return handle_stats()
    elif first_word == "/today":
        return handle_today()
    elif first_word == "/health":
        return handle_health()
    elif first_word == "/pending":
        return handle_pending()
    elif first_word.startswith("/"):
        return handle_unknown(first_word)
    else:
        # Plain text, not a command — ignore silently
        return None


# ─────────────────────────────────────────────────────────────
# MAIN POLLING LOOP
# ─────────────────────────────────────────────────────────────

def run(bot_token, authorized_chat_id):
    """
    Main loop. Long-polls Telegram for messages from authorized_chat_id,
    routes commands, sends replies. Never exits voluntarily — restarts
    on network failure after RETRY_DELAY_SEC.
    """
    log("=" * 55)
    log("CLS TELEGRAM LISTENER — START")
    log(f"Authorized chat_id: {authorized_chat_id}")
    log("=" * 55)

    offset = load_offset()
    log(f"Resuming from offset: {offset}")

    while True:
        updates = get_updates(bot_token, offset)

        if updates is None:
            # getUpdates failed (network error, ISP block, API outage)
            log(
                f"Telegram unreachable — retrying in {RETRY_DELAY_SEC}s.",
                "WARNING",
            )
            time.sleep(RETRY_DELAY_SEC)
            continue

        for update in updates:
            update_id = update.get("update_id")
            if update_id is None:
                continue

            # Advance offset immediately — even if we can't handle the
            # message, we never want to re-process it.
            offset = update_id + 1
            save_offset(offset)

            msg      = update.get("message", {})
            text     = msg.get("text", "")
            chat     = msg.get("chat", {})
            from_id  = str(chat.get("id", ""))
            from_usr = chat.get("username", "unknown")

            # Security gate — silently ignore any other chat
            if from_id != str(authorized_chat_id):
                log(
                    f"Ignored message from unauthorized "
                    f"chat_id={from_id} (@{from_usr})"
                )
                continue

            if not text:
                continue

            log(f"Command received: {text!r}")
            reply = route_command(text)
            if reply is None:
                # Not a command (plain text) — don't reply
                continue

            sent = send_reply(bot_token, authorized_chat_id, reply)
            log(f"Reply delivered: {sent}")


# ─────────────────────────────────────────────────────────────
# SELF-TEST MODE
# ─────────────────────────────────────────────────────────────

def selftest(bot_token, chat_id):
    """
    Send one test message and exit.
    Confirms Telegram is reachable and the bot can talk to you.
    Run this immediately after Telegram is unblocked on your ISP.
    """
    print("=" * 55)
    print(" CLS TELEGRAM LISTENER — SELF TEST")
    print("=" * 55)
    print("Sending test message to Telegram...")
    msg = (
        "✅ <b>CLS Listener — Online</b>\n\n"
        "Two-way Telegram interface is active.\n"
        f"Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n\n"
        "Type /help to see all commands."
    )
    ok = send_reply(bot_token, chat_id, msg)
    status = "[OK]  " if ok else "[FAIL]"
    print(f"{status} Test message {'sent — check your Telegram.' if ok else 'failed.'}")
    print()
    print("Self-test complete.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    env       = load_env()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = env.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        print("[FAIL] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing from .env")
        sys.exit(1)

    if "--test" in sys.argv:
        selftest(bot_token, chat_id)
    else:
        run(bot_token, chat_id)
