"""
=============================================================
cls_ai_daily_brief.py  —  Admin Daily AI Brief (AI-2)
=============================================================
Version : 0.1
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v0.1 (2026-09-29) — Initial version, AI phase Step 2.
  Runs once a day at 07:00 via Task Scheduler -> run_cls_ai_daily_brief.bat
  (sets CLS_DB_PATH=D:\\CLS\\CLS1.db; pythonw.exe, guarded stdout,
  UTF-8-safe logging). Ops-only script outside the Job A-D naming — logs
  to job_results.txt as "Daily AI Brief", same convention as the other
  report scripts.

WHAT IT DOES
------------
1. cls_db.get_daily_brief_stats() -> deterministic numbers for YESTERDAY.
2. ONE LLM call (cls_ai.call_llm, purpose "daily_brief") that turns those
   numbers into 5-8 plain-text lines. The prompt is built from the stats
   dict ONLY: counts plus employee FIRST names. It has no access to any
   lead name/phone/email/cls_id, so it cannot leak them (DPDP).
3. Message = numbers block (zero-value lines omitted) + optional
   "What this means:" narrative. FAIL-OPEN: if the LLM call fails, the
   brief still sends with numbers only and the job still reports SUCCESS.
4. cls_db.notify_daily_brief() -> one notification per active admin.

The generated narrative is stored in ai_suggestions (cls_id
'ai:daily_brief', key = md5(date + PROMPT_VERSION)) for audit, token
counts and the daily cap; a same-day re-run reuses it instead of calling
the LLM again.

Flags: --dry-run (print stats/prompt/message; no LLM call, no writes, no
send) and --selftest (config sanity only; no DB query).
"""

import hashlib
import os
import sys
from datetime import datetime

BASE_DIR = r"D:\CLS"
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "crm"))
import cls_db
import cls_ai

LOG_FILE = os.path.join(BASE_DIR, "cls_ai_daily_brief_log.txt")
PURPOSE = "daily_brief"
JOB_NAME = "Daily AI Brief"
BRIEF_CLS_ID = "ai:daily_brief"          # ai_suggestions.cls_id for the shared audit row
BRIEF_PROMPT_VERSION = "daily_brief_v1"  # bump to force a fresh narrative for the same date

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(message, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] {message}"
    try:
        if sys.stdout is not None:
            print(entry)
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# PROMPT + MESSAGE
# ─────────────────────────────────────────────────────────────
# (label, stats key) — a metric that is 0 gets no line, same
# "omit zero lines" convention as cls_db.format_eod_report_message().
NUMBER_LINES = [
    ("Leads created", "leads_created"),
    ("Stage movements", "stage_movements"),
    ("Site visits conducted", "site_visits_conducted"),
    ("Follow-ups due or overdue", "follow_ups_overdue"),
    ("Open leads gone stale", "stale_leads_count"),
]


def build_prompt(stats):
    facts = [f"- {label}: {stats[key]}" for label, key in NUMBER_LINES]
    idle = ", ".join(stats["idle_employees"]) or "none"
    facts.append(f"- Team members with no logged activity: {idle}")
    return (
        "You are writing a short morning brief for the admin of a real-estate CRM. "
        f"These are the team's numbers for {stats['date']} (the previous day):\n"
        + "\n".join(facts)
        + "\n\nIn 5 to 8 short plain-English lines, say what is notable and what needs "
          "attention today. Use only these numbers; do not invent facts. Plain text only, "
          "no headings, no bullets and no markdown."
    )


def build_message(stats, narrative=None):
    lines = [f"Daily AI Brief — {stats['date']}", ""]
    for label, key in NUMBER_LINES:
        if stats[key]:
            lines.append(f"{label}: {stats[key]}")
    if stats["idle_employees"]:
        lines.append("No activity logged by: " + ", ".join(stats["idle_employees"]))
    if narrative:
        lines += ["", "What this means:", narrative.strip()]
    return "\n".join(lines)


def _narrative_key(date_str):
    return hashlib.md5(f"{date_str}:{BRIEF_PROMPT_VERSION}".encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main(dry_run=False):
    log("=" * 55)
    log(f"DAILY AI BRIEF — START{' (DRY RUN)' if dry_run else ''}")
    log("=" * 55)
    try:
        conn = cls_db.connect()
    except Exception as e:
        log(f"DB unreachable: {e}", "ERROR")
        if not dry_run:
            try:
                cls_db.write_job_result(JOB_NAME, False, f"DB unreachable: {e}")
            except Exception:
                pass
        return False

    try:
        stats = cls_db.get_daily_brief_stats(conn)
        log(f"Stats: {stats}")
        prompt = build_prompt(stats)

        if dry_run:
            log("[DRY-RUN] Prompt that WOULD be sent:\n" + prompt)
            log("[DRY-RUN] Message that WOULD be sent (numbers only, no LLM call):\n"
                + build_message(stats))
            return True

        key = _narrative_key(stats["date"])
        cached = cls_db.get_cached_ai_suggestion(conn, BRIEF_CLS_ID, PURPOSE, key)
        narrative, llm_status = None, "failed"
        if cached and cached["output_text"]:
            narrative, llm_status = cached["output_text"], "cached"
        else:
            res = cls_ai.call_llm(prompt, PURPOSE, conn)
            if res["ok"]:
                narrative, llm_status = res["text"], "ok"
                cls_db.save_ai_suggestion(
                    conn, BRIEF_CLS_ID, PURPOSE, key, prompt, res["text"],
                    res.get("provider"), res.get("model"), res["tokens_in"],
                    res["tokens_out"], "system:daily_brief")
            else:
                log(f"LLM unavailable ({res['error']}) — sending numbers only.", "WARNING")

        message = build_message(stats, narrative)
        sent = cls_db.notify_daily_brief(message)
        summary = f"Brief sent for {stats['date']} to {sent} admin(s). LLM: {llm_status}."
        cls_db.write_job_result(JOB_NAME, True, summary)
        log(summary)
        return True
    except Exception as e:
        log(f"FAILED — {e}", "ERROR")
        try:
            cls_db.write_job_result(JOB_NAME, False, f"failed: {e}")
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass
        log("DAILY AI BRIEF — END")
        log("=" * 55)


# ─────────────────────────────────────────────────────────────
# SELF-TEST  (config only — no DB query, no send)
# ─────────────────────────────────────────────────────────────
def selftest():
    ok = True

    def check(cond, label):
        nonlocal ok
        ok = ok and cond
        log(f"[{'OK' if cond else 'FAIL'}] {label}")

    check(PURPOSE in cls_ai.DEFAULT_DAILY_CAPS, "'daily_brief' has a daily cap in cls_ai.DEFAULT_DAILY_CAPS")
    fake = {"date": "2000-01-01", "leads_created": 0, "stage_movements": 3,
            "site_visits_conducted": 0, "follow_ups_overdue": 2,
            "stale_leads_count": 0, "idle_employees": ["Asha"]}
    msg = build_message(fake, "Line one.")
    check("Leads created" not in msg and "Stage movements: 3" in msg, "zero-value metric lines are omitted")
    check("What this means:" in msg and "Line one." in msg, "narrative appended under plain-text label")
    check("What this means:" not in build_message(fake), "no narrative label when the LLM is unavailable")
    check("Asha" in build_prompt(fake) and "markdown" in build_prompt(fake), "prompt built from stats only")
    log("Self-test complete." if ok else "Self-test FAILED.")
    return ok


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main(dry_run="--dry-run" in sys.argv)
