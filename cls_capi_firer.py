"""
=============================================================
cls_capi_firer.py  —  CLS Job C  |  CLS -> Meta CAPI Firer
=============================================================
Version : 3.5
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v3.5 (2026-09-21) — SELF-HEALING queue mode. After the retry queue, every
  scheduled run now also fires the leads that genuinely need an event
  (cls_db.get_capi_self_heal_leads(), cls_db v2.100): target stage, not
  manual-guarded, no events_log row for (cls_id, stage, CURRENT
  leadgen_id), stage changed within 7 days AND at least
  CAPI_PENDING_GRACE_MIN (10) minutes ago, and not already in
  capi_fire_queue. A re-engaged lead gets a NEW leadgen_id that Meta treats
  as a new lead needing its own "Incoming" event; nothing sent it before.
  Uses cls_capi_core.fire_single_lead_event() UNCHANGED (guard unchanged).
  A failure is queued once via queue_failed_fire() — no retry within the
  same run. Logs "SELF-HEAL: fired N pending lead(s)" when N > 0 and adds
  ", N self-healed" to the job_results line only then. FAST EXIT kept: with
  the retry queue AND the pending set both empty it exits after cheap
  queries, sets the 'capi_fire' flag (v3.3), makes no HTTP call.
  --catchup is unchanged: manual full mode, no grace period. --dry-run
  lists what would be healed; sends nothing, writes no DB rows, sets no
  flag (the pre-existing job_results.txt line is still written).

v3.4 (2026-09-21) — --catchup only: one new log line, "N lead(s) older than
  7 days skipped (too old to send)" (cls_db.count_capi_too_old(), v2.99),
  logged before the fire loop (also when nothing is left to fire). No
  change to firing behaviour — the list of leads to fire is whatever
  cls_db.get_unfired_leads() returns, which v2.99 narrowed to leads that
  genuinely need an event now.

v3.3 (2026-09-21) — queue mode: the "Queue is empty. Nothing to do." exit
  now also sets the 'capi_fire' completion flag (and logs "Completion flag
  'capi_fire' set."), skipped under --dry-run like the other paths. An
  empty-queue run IS a completed run — before this, the flag was only set
  when the queue had work, and since the queue is almost always empty the
  flag went stale (last set 2026-09-11), so cls_watchdog.py's flag check
  and the Telegram Listener's /health reported Job C as STALE although the
  task runs every 15 minutes. Nothing else changed.

v3.2 (2026-09-21) — log honesty for the CAPI guard. In BOTH the queue
  loop and the --catchup loop, a lead cls_capi_core.is_capi_skipped()
  (manual, no leadgen_id — never sent to Meta) is now logged as SKIPPED
  and counted in its own `skipped` counter instead of being counted/
  logged as OK. The run-summary log line and the job_results.txt line
  gain ", N skipped (manual, no leadgen_id)" ONLY when N > 0; with none
  skipped both lines are character-for-character what they were. Firing
  behaviour is unchanged (skipped queue rows are still cleared).
  No other counter counted skipped leads as fired: every "pending fire"
  figure (stats(), watchdog, Telegram, snapshot) goes through
  cls_db.get_unfired_leads(), which already excludes them (cls_db v2.97).

v3.1 (2026-09-21) — selftest only: one new offline case for the CAPI
  guard (cls_capi_core.py v1.2) — a manual lead with no leadgen_id
  returns (True, None) even with an EMPTY env (i.e. it exits before
  any credential check / HTTP call), while a manual lead WITH a
  leadgen_id does not take that early exit. No logic change.

v3.0 (2026-08-14) — FULL REWRITE. Replaces the old full-table-scan cron
  model with two-mode queue processing, backed by the inline firing
  redesign (crm/app.py v0.49, meta_leads_fetcher.py v1.8, cls_capi_core.py
  v1.0, cls_db.py v2.55's capi_fire_queue table).

  Default mode (no flags): processes ONLY cls_db.capi_fire_queue —
  leads that failed to fire inline from app.py or meta_leads_fetcher.py.
  Fast-exits with a single COUNT query + one log line if the queue is
  empty. The selldo_sync flag gate is RETIRED — Job B is permanently
  stopped, so that dependency no longer applies to anything in this file.

  --catchup mode: one-time full-table scan using cls_db.get_unfired_
  leads(), same universe cls_capi_firer.py v1.8's run() scanned, but
  using the shared cls_capi_core.fire_single_lead_event() instead of
  this file's own duplicated payload/hashing/fire logic. Failures are
  queued via cls_db.queue_failed_fire() instead of just logged — a
  --catchup failure gets the same retry path as an inline failure.

  Both modes read CLS_DB_PATH the normal way, via cls_db.py's existing
  DB_FILE resolution (os.environ.get("CLS_DB_PATH", .../CLS1.db)) — no
  hardcoded path in this file, same as v1.8.

  --selftest is unchanged in spirit — still offline, no API calls, no
  database access — but now delegates payload assertions to
  cls_capi_core's build_event_payload()/GRAPH_API_VERSION/
  STAGE_EVENT_MAP, since that logic no longer lives in this file.

  REMOVED (moved to cls_capi_core.py v1.0, not duplicated here):
  GRAPH_API_VERSION, TARGET_STAGES, STAGE_VALUES, STAGE_EVENT_MAP,
  CRM_EVENT_SOURCE, CRM_NAME, sha256_hash(), build_event_payload().
  RETIRED (no longer used by anything): the old fire_to_dataset() batch
  function, SELLDO_FLAG_MAX_AGE_MIN, and the selldo_sync gate check
  that used to open run().

WHAT THIS JOB DOES NOW
-----------------------
Two independent modes:

  DEFAULT (no flags) — queue processor. Reads cls_db.capi_fire_queue
  (rows created by app.py's change_lead_stage() route or meta_leads_
  fetcher.py's new-lead insert when an inline fire failed), retries
  each via cls_capi_core.fire_single_lead_event(), clears it from the
  queue on success, bumps its attempt count on failure (permanently
  giving up once cls_db.MAX_QUEUE_ATTEMPTS is reached). Meant to run on
  a short interval so a transient Meta outage clears itself quickly.

  --catchup — one-time full-table scan (cls_db.get_unfired_leads()),
  for recovering leads that were never queued at all (e.g. this
  redesign's own cutover, or a period where the inline hooks were
  broken). NOT part of the normal schedule — run manually when needed.

  --dry-run — combine with either mode: shows what WOULD fire /
  WOULD be retried, sends nothing, writes nothing.
  --selftest — offline checks, no API calls, no database access.

RUN
---
  python cls_capi_firer.py                  # queue mode (normal schedule)
  python cls_capi_firer.py --dry-run         # queue mode, no sends
  python cls_capi_firer.py --catchup         # one-time full-table scan
  python cls_capi_firer.py --catchup --dry-run
  python cls_capi_firer.py --selftest        # offline checks, no API
=============================================================
"""

import os
import sys
import time
from datetime import datetime

import cls_db          # the foundation layer
import cls_capi_core   # shared payload + single-fire logic (v1.0)

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR = r"D:\CLS"
ENV_FILE = os.path.join(BASE_DIR, ".env")
LOG_FILE = os.path.join(BASE_DIR, "cls_capi_log.txt")


# ─────────────────────────────────────────────────────────────
# LOGGING  (unchanged from v1.8 — Unicode-safe stdout)
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry     = f"[{timestamp}] [{level}] {message}"
    # Windows Task Scheduler pipes stdout through the system codepage
    # (cp1252 on most Indian-locale Windows machines) — sanitise the
    # console copy, keep the file copy full UTF-8. Same fix as v1.4.
    safe_entry = entry.encode("utf-8", errors="replace").decode("utf-8")
    try:
        print(safe_entry)
    except UnicodeEncodeError:
        print(safe_entry.encode("ascii", errors="replace").decode("ascii"))
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# .env LOADER  (unchanged from v1.8)
# ─────────────────────────────────────────────────────────────

def load_env():
    """Read .env into a dict (python-dotenv if available, else manual)."""
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
# OUTPUT REFRESH  (dashboard + KV snapshot — unchanged from v1.8)
# ─────────────────────────────────────────────────────────────

def _refresh_outputs(dry_run=False):
    """
    Refresh dashboard.html and push the KV snapshot to Cloudflare.
    Non-blocking: a dashboard or network failure here must never
    prevent the completion flag from being set.
    """
    if dry_run:
        log("DRY-RUN — skipping dashboard refresh and snapshot push.")
        return

    try:
        import cls_dashboard
        cls_dashboard.generate_dashboard()
        log("Dashboard refreshed: dashboard.html")
    except Exception as e:
        log(f"Dashboard refresh failed (non-critical): {e}", "WARNING")

    try:
        import cls_snapshot
        if cls_snapshot.push_snapshot():
            log("Snapshot pushed to Cloudflare KV (Command Center).")
        else:
            log("Snapshot push failed (non-critical) — see cls_snapshot.log",
                "WARNING")
    except Exception as e:
        log(f"Snapshot push error (non-critical): {e}", "WARNING")


# ─────────────────────────────────────────────────────────────
# DEFAULT MODE — process capi_fire_queue
# ─────────────────────────────────────────────────────────────

def run_queue_mode(dry_run=False):
    log("=" * 55)
    log("CLS JOB C — CAPI Firer — QUEUE MODE — START")
    if dry_run:
        log("MODE: --dry-run (no events will actually be sent)")
    log("=" * 55)

    cls_db.init_db()

    due = cls_db.get_due_retries()
    heal_preview = cls_db.get_capi_self_heal_leads()   # cheap query; the real set is re-read after the retry loop
    if not due and not heal_preview:
        log("Queue is empty. Nothing to do.")
        if not dry_run:
            cls_db.set_flag("capi_fire")
            log("Completion flag 'capi_fire' set.")
        log("=" * 55)
        log("CLS JOB C — CAPI Firer — DONE (queue empty)")
        log("=" * 55)
        cls_db.write_job_result("Job C (CAPI Firer)", True, "Queue empty — nothing to retry")
        return True

    env = load_env()
    if not env.get("META_PRIMARY_DATASET") or not env.get("META_CAPI_TOKEN"):
        log("META_PRIMARY_DATASET or META_CAPI_TOKEN missing in .env — aborting.", "ERROR")
        cls_db.write_job_result("Job C (CAPI Firer)", False,
                                 "META_PRIMARY_DATASET or META_CAPI_TOKEN missing in .env")
        return False

    if due:
        log(f"Queue has {len(due)} pending row(s) to retry.")
    else:
        log("Retry queue is empty.")

    ok = fail = skipped = 0
    for row in due:
        lead = cls_db.get_lead_by_id(row["cls_id"])
        if not lead:
            log(f"  [queue_id={row['queue_id']}] cls_id {row['cls_id']} no longer exists — clearing.",
                "WARNING")
            if not dry_run:
                cls_db.clear_from_queue(row["queue_id"])
            continue

        if dry_run:
            if cls_capi_core.is_capi_skipped(lead):
                log(f"  [queue_id={row['queue_id']}] DRY-RUN would skip (manual lead, no leadgen_id): "
                    f"{lead.get('full_name', '?')} | target={row['target_stage']}")
                skipped += 1
                continue
            log(f"  [queue_id={row['queue_id']}] DRY-RUN would retry: {lead.get('full_name', '?')} "
                f"| target={row['target_stage']} | attempt {row['attempts'] + 1}")
            ok += 1
            continue

        fired, err = cls_capi_core.fire_single_lead_event(lead, env)
        if fired:
            cls_db.clear_from_queue(row["queue_id"])
            if cls_capi_core.is_capi_skipped(lead):
                log(f"  [queue_id={row['queue_id']}] SKIPPED (manual lead, no leadgen_id) "
                    f"{lead.get('full_name', '?')} | {row['target_stage']}")
                skipped += 1
            else:
                log(f"  [queue_id={row['queue_id']}] OK {lead.get('full_name', '?')} | {row['target_stage']}")
                ok += 1
        else:
            cls_db.bump_queue_attempt(row["queue_id"], err)
            log(f"  [queue_id={row['queue_id']}] FAILED {lead.get('full_name', '?')} "
                f"| attempt {row['attempts'] + 1} | {err}", "ERROR")
            fail += 1

        time.sleep(cls_capi_core.API_PAUSE_SEC)

    skip_note = f", {skipped} skipped (manual, no leadgen_id)" if skipped else ""
    log("-" * 55)
    if dry_run:
        log(f"DRY-RUN complete — {ok} row(s) WOULD have been retried{skip_note}.")
    else:
        log(f"Retried {ok} OK, {fail} still failing (requeued or permanently failed){skip_note}.")

    # ── v3.5 SELF-HEAL: fire the leads that genuinely need an event ──
    # Re-read AFTER the retry loop: a lead the loop just fired now has an
    # events_log row and drops out; a lead it just re-queued is excluded.
    healed = heal_fail = 0
    for lead in cls_db.get_capi_self_heal_leads():
        if dry_run:
            log(f"  DRY-RUN would self-heal: {lead.get('full_name', '?')} | {lead['current_stage']}")
            healed += 1
            continue
        fired, err = cls_capi_core.fire_single_lead_event(lead, env)
        if fired:
            healed += 1
            log(f"  SELF-HEAL OK {lead.get('full_name', '?')} | {lead['current_stage']}")
        else:
            heal_fail += 1
            cls_db.queue_failed_fire(lead["cls_id"], lead["current_stage"], err)
            log(f"  SELF-HEAL FAILED (queued once) {lead.get('full_name', '?')} | {err}", "ERROR")
        time.sleep(cls_capi_core.API_PAUSE_SEC)
    if healed:
        log(f"SELF-HEAL: {'WOULD fire' if dry_run else 'fired'} {healed} pending lead(s)")
    heal_note = f", {healed} self-healed" if healed and not dry_run else ""
    if dry_run and healed:
        heal_note = f", {healed} would self-heal"

    _refresh_outputs(dry_run=dry_run)
    if not dry_run:
        cls_db.set_flag("capi_fire")
        log("Completion flag 'capi_fire' set.")

    log("=" * 55)
    log("CLS JOB C — CAPI Firer — DONE (queue mode)")
    log("=" * 55)
    cls_db.write_job_result(
        "Job C (CAPI Firer)", True,
        f"Queue mode — {ok} OK, {fail} failed{skip_note}{heal_note}" if not dry_run
        else f"DRY-RUN — {ok} would retry{skip_note}{heal_note}"
    )
    return True


# ─────────────────────────────────────────────────────────────
# --catchup MODE — one-time full-table scan
# ─────────────────────────────────────────────────────────────

def run_catchup_mode(dry_run=False):
    log("=" * 55)
    log("CLS JOB C — CAPI Firer — CATCHUP MODE — START")
    if dry_run:
        log("MODE: --dry-run (no events will actually be sent)")
    log("=" * 55)

    cls_db.init_db()

    env = load_env()
    if not env.get("META_PRIMARY_DATASET") or not env.get("META_CAPI_TOKEN"):
        log("META_PRIMARY_DATASET or META_CAPI_TOKEN missing in .env — aborting.", "ERROR")
        cls_db.write_job_result("Job C (CAPI Firer)", False,
                                 "META_PRIMARY_DATASET or META_CAPI_TOKEN missing in .env")
        return False

    unfired = cls_db.get_unfired_leads()
    unfired = [l for l in unfired if l["current_stage"] in cls_capi_core.TARGET_STAGES]

    try:
        log(f"{cls_db.count_capi_too_old()} lead(s) older than "
            f"{cls_db.CAPI_CATCHUP_MAX_AGE_DAYS} days skipped (too old to send)")
    except Exception as e:
        log(f"Could not count too-old leads: {e}", "WARNING")

    if not unfired:
        log("No stage changes to fire this run. Nothing to do.")
        _refresh_outputs(dry_run=False)
        if not dry_run:
            cls_db.set_flag("capi_fire")
        log("=" * 55)
        log("CLS JOB C — CAPI Firer — DONE (nothing to fire)")
        log("=" * 55)
        cls_db.write_job_result("Job C (CAPI Firer)", True, "Catchup — no stage changes to fire")
        return True

    log(f"Leads to fire: {len(unfired)}")

    ok = fail = skipped = 0
    for lead in unfired:
        if dry_run:
            if cls_capi_core.is_capi_skipped(lead):
                log(f"  DRY-RUN would skip (manual lead, no leadgen_id): {lead.get('full_name', '?')} | stage={lead['current_stage']}")
                skipped += 1
                continue
            log(f"  DRY-RUN would fire: {lead.get('full_name', '?')} | stage={lead['current_stage']}")
            ok += 1
            continue

        fired, err = cls_capi_core.fire_single_lead_event(lead, env)
        if fired:
            if cls_capi_core.is_capi_skipped(lead):
                skipped += 1
                log(f"  SKIPPED (manual lead, no leadgen_id) {lead.get('full_name', '?')} | {lead['current_stage']}")
            else:
                ok += 1
                log(f"  OK {lead.get('full_name', '?')} | {lead['current_stage']}")
        else:
            fail += 1
            cls_db.queue_failed_fire(lead["cls_id"], lead["current_stage"], err)
            log(f"  FAILED (queued for retry) {lead.get('full_name', '?')} | {err}", "ERROR")

        time.sleep(cls_capi_core.API_PAUSE_SEC)

    skip_note = f", {skipped} skipped (manual, no leadgen_id)" if skipped else ""
    log("-" * 55)
    if dry_run:
        log(f"DRY-RUN complete — {ok} events WOULD have fired{skip_note}.")
    else:
        log(f"Fired {ok} OK, {fail} failed (queued for retry){skip_note}.")

    s = cls_db.stats()
    log(f"CLS now holds: {s['total_leads']} leads "
        f"({s['with_leadgen_id']} with leadgen_id, "
        f"{s['pending_fire']} still pending fire)")

    _refresh_outputs(dry_run=dry_run)
    if not dry_run:
        cls_db.set_flag("capi_fire")
        log("Completion flag 'capi_fire' set.")

    log("=" * 55)
    log("CLS JOB C — CAPI Firer — DONE (catchup mode)")
    log("=" * 55)
    cls_db.write_job_result(
        "Job C (CAPI Firer)", True,
        f"Catchup — {ok} OK, {fail} failed{skip_note}" if not dry_run else f"DRY-RUN catchup — {ok} would fire{skip_note}"
    )
    return True


# ─────────────────────────────────────────────────────────────
# SELF-TEST  —  offline; no API calls, no database access
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Verifies payload construction without contacting Meta or opening the
    database — delegates the actual assertions to cls_capi_core.py,
    since that's where build_event_payload() now lives.
    """
    print("=" * 55)
    print(" CLS CAPI FIRER — SELF TEST (offline)")
    print("=" * 55)

    et = 1700000000

    meta_lead = {
        "cls_id": "c1", "leadgen_id": "1234567890",
        "selldo_lead_id": "SD1", "full_name": "Ravi Kumar",
        "phone_norm": "9876543210", "email_norm": "ravi@gmail.com",
        "current_stage": "Opportunity",
    }
    p1, used1 = cls_capi_core.build_event_payload(meta_lead, et)
    ok = (p1["event_name"] == "Schedule" and used1
          and p1["user_data"].get("lead_id") == 1234567890
          and p1["custom_data"]["value"] == 1000)
    print(f"  [{'OK' if ok else 'FAIL'}] Meta lead -> Schedule, value 1000, lead_id present")

    selldo_lead = {
        "cls_id": "c2", "leadgen_id": None,
        "selldo_lead_id": "SD2", "full_name": "Sita Reddy",
        "phone_norm": "9000000001", "email_norm": "",
        "current_stage": "Prospect",
    }
    p2, used2 = cls_capi_core.build_event_payload(selldo_lead, et)
    ok = (p2["event_name"] == "QualifiedLead" and not used2
          and "lead_id" not in p2["user_data"]
          and p2["custom_data"]["value"] == 200)
    print(f"  [{'OK' if ok else 'FAIL'}] contact-only lead -> QualifiedLead, no lead_id")

    ok = (p1["custom_data"]["event_source"] == "crm"
          and p1["custom_data"]["lead_event_source"] == "Asian Properties CRM")
    print(f"  [{'OK' if ok else 'FAIL'}] custom_data: event_source='crm' + "
          f"lead_event_source='Asian Properties CRM'")

    ok = cls_capi_core.GRAPH_API_VERSION == "v23.0"
    print(f"  [{'OK' if ok else 'FAIL'}] Graph API version is {cls_capi_core.GRAPH_API_VERSION} (expected v23.0)")

    ok = ("Booked" not in cls_capi_core.STAGE_EVENT_MAP
          and "Lost" not in cls_capi_core.STAGE_EVENT_MAP
          and "Re Assigned" not in cls_capi_core.STAGE_EVENT_MAP)
    print(f"  [{'OK' if ok else 'FAIL'}] non-target stages (Booked/Lost/Re Assigned) not in event map")

    # v3.1 — CAPI guard. env={} means anything past the guard would hit the
    # "credentials missing" error, so (True, None) proves the early exit.
    manual_no_lg = {"cls_id": "c3", "source": "manual_crm", "leadgen_id": None,
                    "current_stage": "Prospect", "full_name": "Walk In",
                    "phone_norm": "9000000002"}
    ok = cls_capi_core.fire_single_lead_event(manual_no_lg, {}) == (True, None)
    print(f"  [{'OK' if ok else 'FAIL'}] manual lead, no leadgen_id -> skipped (True, None), no send")

    manual_with_lg = dict(manual_no_lg, leadgen_id="1234567890")
    ok_flag, _err = cls_capi_core.fire_single_lead_event(manual_with_lg, {})
    print(f"  [{'OK' if not ok_flag else 'FAIL'}] manual lead WITH leadgen_id -> not skipped (normal path)")

    # v3.2 — is_capi_skipped() is the one home of the guard rule.
    ok = (cls_capi_core.is_capi_skipped(manual_no_lg)
          and not cls_capi_core.is_capi_skipped(manual_with_lg)
          and not cls_capi_core.is_capi_skipped(meta_lead)
          and not cls_capi_core.is_capi_skipped(selldo_lead))
    print(f"  [{'OK' if ok else 'FAIL'}] is_capi_skipped(): manual/no-leadgen only")

    print("=" * 55)
    print(" SELF TEST COMPLETE — offline logic verified (delegates to cls_capi_core.py).")
    print(" Use --dry-run (queue or --catchup mode) for a live no-send check against real CLS data.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
    elif "--catchup" in args:
        run_catchup_mode(dry_run=("--dry-run" in args))
    else:
        run_queue_mode(dry_run=("--dry-run" in args))
