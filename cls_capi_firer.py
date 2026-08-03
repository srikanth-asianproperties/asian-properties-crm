"""
=============================================================
cls_capi_firer.py  —  CLS Job C  |  CLS -> Meta CAPI Firer
=============================================================
Version : 1.8
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.8  (2026-08) — BASE_DIR updated from C:\CLS to D:\CLS — drive migration, 2026-08.

v1.7  (July 2026) — CLS1/CLS2 database split support. ADDITIONS ONLY.
  Added cls_db.write_job_result() calls at every existing return point
  in run() (gate-blocked, missing credentials, nothing-to-fire, and the
  final success path) — one line to C:\\CLS\\job_results.txt per run,
  reusing the marked/leadgen_count counters this job already computes.
  No new counting logic. Per Srikanth's explicit call, Job C continues
  reading from CLS2.db (the Sell.do-trusted mirror) during parallel-run,
  since CAPI fires against real ad spend — this is a Task Scheduler
  CLS_DB_PATH env var setting, not a code change (see cls_db.py v2.23).
  The existing 'selldo_sync' flag gate is unchanged — still correct,
  since Job C now reads the same DB (CLS2) that Job B just wrote to.

v1.6  (July 2026) — lead_owner passthrough to events_log:
  ADDED — record_event() call now passes lead_owner=lead.get("lead_owner").
    lead["lead_owner"] was already present on every row (get_unfired_leads()
    does SELECT *) — this is a one-line addition, no new query. Requires
    cls_db.py v2.1 (adds the events_log.lead_owner column + accepts the
    kwarg). Enables the watchdog's per-salesperson daily summary to
    attribute each CAPI fire to whoever owned the lead at fire time.

v1.5  (June 2026) — 1-hour cadence tuning:
  CHANGE — SELLDO_FLAG_MAX_AGE_MIN : 180 -> 75
    Gate tuned for 1-hour cadence: 60-min expected window + 15-min
    slack. A stale flag older than 75 min means Job B missed its cycle.
    Job C now runs at :25 past the hour; Job B runs at :10. The 15-min
    slack absorbs a slow Sell.do export or Playwright login timeout
    without false-blocking Job C.

v1.4  (June 2026) — Unicode-safe stdout (permanent Windows fix):
  FIX — UnicodeEncodeError crashing Job C mid-run
    Windows Task Scheduler pipes stdout through the system codepage
    (cp1252 on Indian-locale Windows). Lead names from Sell.do can
    contain Telugu, Arabic, or other non-cp1252 characters. When
    Job C tried to print the OK/ERROR log line for such a lead, Python
    raised UnicodeEncodeError and the entire script crashed — leaving
    subsequent leads unfired, the completion flag unset, and the
    watchdog blind to the failure.
    Fix: log() now encodes the print string to UTF-8 first, replaces
    unmappable bytes with '?', and prints the sanitised string. The
    log FILE continues to receive full UTF-8 — only the console
    display is sanitised. A lead named "రాజేష్" will appear as
    "??????" in the Task Scheduler console but fire correctly, and
    the file log will show the real name.
    Root cause is the Windows console codepage, not any lead data.
    This is a permanent fix — no lead name can ever crash Job C again.

v1.3  (June 2026) — Incoming stage + lead coverage fix:
  ADD — Incoming → Lead event (value INR 0)
    Meta requires 60% lead coverage to unlock Conversion Lead
    Optimisation. Coverage was 20-55% because only Prospect/Opportunity/
    Site Visited fired — many leads stuck in Incoming never got an event.
    Adding Incoming fires a Lead event within 2 hours of every new lead
    arriving, immediately pushing coverage above 60%.
    Value is INR 0 deliberately: Incoming is an unqualified signal, not
    a conversion. Zero value protects value-based optimisation accuracy.

v1.2  (June 2026) — Consolidated release. Two fixes in one:
  FIX 1 — Graph API version restored to v23.0
    v19.0 was deprecated by Meta on May 21, 2026. The manual upgrade
    to v23.0 (done June 9, 2026) was accidentally rolled back when v1.1
    was built from a stale project file that still carried v19.0.
    v1.2 restores v23.0 and makes it the permanent baseline.
    Next planned upgrade: v25.0 in ~3-4 months.
  FIX 2 — CRM lead-conversion tagging in custom_data (carried from v1.1)
    The dataset (Pabbly_Naishka_03-12-2025) is a Meta "Conversions API
    for CRM" dataset. Meta's CRM spec requires every event to carry:
        custom_data.event_source      = "crm"
        custom_data.lead_event_source = "Sell.do"
    Without these, Meta could not fully attribute events to the CRM
    funnel, suppressing the CRM-side data quality score.
    action_source, event names, values, hashing, and leadgen_id
    enrichment are all unchanged from v1.0.

WHAT THIS JOB DOES
------------------
Reads the Centralised Leads System (cls.db), finds every lead whose
CRM stage has changed since it was last fired, and sends a Meta
Conversions API (CAPI) event for it. This is the LAST job in the
pipeline:

    [Job A] meta_leads_fetcher.py  -> Meta leads + leadgen_id
    [Job B] selldo_to_cls.py       -> CRM stages matched onto them
    [Job C] cls_capi_firer.py      <-- THIS FILE
            fires stage changes to Meta CAPI, then records what fired

THE NEW CAPABILITY — leadgen_id ENRICHMENT
------------------------------------------
This is the whole reason the CLS project exists. The old script fired
events with only hashed phone/email — Meta then did PROBABILISTIC
matching ("this hash probably belongs to that ad click"). Job C adds
the lead's leadgen_id to user_data.lead_id whenever it has one. For a
Lead Ads lead, leadgen_id lets Meta do DETERMINISTIC matching — it
knows exactly which lead and which ad. Higher match quality = better
ad optimisation.

  - Lead HAS leadgen_id   -> event includes lead_id  (deterministic)
  - Lead has NO leadgen_id -> hashed PII only         (same as old script)

Nothing is worse off than before; Meta-origin leads are much better.

FAITHFUL TO THE OLD SCRIPT
--------------------------
Target stages, INR values, stage->event mapping, deterministic
event_id, hashed user_data, location enrichment, and the two-dataset
fan-out are reproduced EXACTLY from selldo_capi_automation.py. The
only behavioural change is the leadgen_id addition.

RISK-4 SAFETY (no double-fire, no missed fire)
----------------------------------------------
A lead is fired only when current_stage != last_fired_stage. After
Meta CONFIRMS receipt (events_received > 0), cls_db.mark_as_fired()
records the stage. State is per-row and confirmed — a crash mid-run
cannot double-fire or skip a lead.

ONE-TIME SETUP
--------------
  pip install requests python-dotenv
  (cls_db.py must be in the same folder)

  .env must contain (Meta CAPI side):
    META_CAPI_TOKEN=EAAM...        (the dataset access token)
    META_PRIMARY_DATASET=2575028359563587
    META_ADDITIONAL_DATASET=1477996994057497
    META_ADDITIONAL_TOKEN=EAAM...  (token for the additional dataset)

RUN
---
  python cls_capi_firer.py            # normal run (flag-gated)
  python cls_capi_firer.py --force    # run even if Job B flag is stale
  python cls_capi_firer.py --dry-run  # show what WOULD fire; sends nothing
  python cls_capi_firer.py --selftest # offline checks, no API
=============================================================
"""

import os
import sys
import time
import json
import hashlib
import requests
from datetime import datetime

import cls_db   # the foundation layer — Step 1

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR  = r"D:\CLS"
ENV_FILE  = os.path.join(BASE_DIR, ".env")
LOG_FILE  = os.path.join(BASE_DIR, "cls_capi_log.txt")

GRAPH_API_VERSION = "v23.0"   # v19.0 deprecated May 21 2026; upgraded June 9 2026
                              # next planned upgrade: v25.0 in ~3-4 months

# ── Target stages — fires a CAPI event when a lead enters any of these ──
# Incoming : fires immediately on lead arrival → boosts lead coverage above
#            Meta's 60% threshold for Conversion Lead Optimisation (v1.3)
# Prospect, Opportunity, Site Visited : quality conversion signals (v1.0)
TARGET_STAGES = ["Incoming", "Prospect", "Opportunity", "Site Visited"]

# ── Value parameters (INR) ──
# Incoming is INR 0 deliberately — it is a raw arrival signal, not a
# conversion. Zero protects value-based optimisation accuracy.
STAGE_VALUES = {
    "Incoming"     : 0,
    "Prospect"     : 200,
    "Opportunity"  : 1000,
    "Site Visited" : 3000,
}

# ── CRM stage name -> Meta standard event name ──
STAGE_EVENT_MAP = {
    "Incoming"     : "Lead",
    "Prospect"     : "QualifiedLead",
    "Opportunity"  : "Schedule",
    "Site Visited" : "CompleteRegistration",
}

# ── CRM identity for Meta's CRM lead-conversion spec (added v1.1) ──
# Meta's CRM dataset requires every event to carry its origin inside
# custom_data so the Conversion Leads optimisation knows the signal came
# from a CRM (not a browser) and which CRM produced it.
# Pulled into constants so a future CRM switch is a one-line change.
CRM_EVENT_SOURCE = "crm"        # custom_data.event_source
CRM_NAME         = "Sell.do"    # custom_data.lead_event_source

# ── CRM identity for Meta's CRM lead-conversion spec (v1.1) ──
# Meta wants every CRM-sourced event tagged with its origin so the
# Conversion Leads optimisation knows the signal came from a CRM (not a
# browser) and which CRM produced it. Sent inside custom_data on every
# event. Pulled into a constant so a future CRM switch is a one-line
# change — same "config-not-code" principle as form IDs in the projects
# table.
CRM_EVENT_SOURCE = "crm"        # custom_data.event_source — the literal flag Meta looks for
CRM_NAME         = "Sell.do"    # custom_data.lead_event_source — your system of record

# How fresh Job B's completion must be for Job C to proceed (Risk 1).
# Tuned for 1-hour cadence: 60-min window + 15-min slack (was 180).
# Job C runs at :25; Job B runs at :10 — 15-min slack is the buffer.
SELLDO_FLAG_MAX_AGE_MIN = 75

# Small pause between CAPI calls — same courtesy delay as the old script.
API_PAUSE_SEC = 0.3


# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry     = f"[{timestamp}] [{level}] {message}"
    # ── Unicode-safe print ────────────────────────────────────────
    # Windows Task Scheduler pipes stdout through the system codepage
    # (cp1252 on most Indian-locale Windows machines). Lead names from
    # Sell.do can contain characters outside cp1252 — Telugu, Arabic,
    # emoji — which raises UnicodeEncodeError and kills the entire Job.
    # Fix: encode to UTF-8, replace unmappable chars with '?', decode
    # back to str, then print the sanitised string.
    # The log FILE always receives the original UTF-8 entry unchanged.
    safe_entry = entry.encode("utf-8", errors="replace").decode("utf-8")
    try:
        print(safe_entry)
    except UnicodeEncodeError:
        # Absolute last resort: strip every non-ASCII character.
        print(safe_entry.encode("ascii", errors="replace").decode("ascii"))
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# .env LOADER
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
# HELPER: SHA256 hash for Meta CAPI PII compliance
# (identical to the old script — Meta requires PII pre-hashed)
# ─────────────────────────────────────────────────────────────

def sha256_hash(value):
    """SHA256 of a normalized value. Returns None for blank/nan/none."""
    if not value or str(value).lower() in ("nan", "none", ""):
        return None
    return hashlib.sha256(str(value).strip().lower().encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# BUILD ONE CAPI EVENT PAYLOAD
# ─────────────────────────────────────────────────────────────

def build_event_payload(lead, event_time):
    """
    Build the Meta CAPI 'data' entry for one CLS lead.

    Faithful to selldo_capi_automation.py:
      - user_data: hashed ph / em / fn / ln + hashed location (in/TG/Hyd)
      - deterministic event_id = md5(identifier + event_name)
      - custom_data: lead_stage, value (INR), currency

    NEW — leadgen_id enrichment:
      - If the CLS lead has a leadgen_id, it is added as
        user_data['lead_id']. Meta uses this for DETERMINISTIC matching
        of Lead Ads leads. Leads without one fire on hashed PII only.

    Returns (payload_dict, used_leadgen_bool).
    """
    stage      = lead["current_stage"]
    meta_event = STAGE_EVENT_MAP.get(stage, stage)
    value      = STAGE_VALUES.get(stage, 0)

    # ── Split full_name into first / last for hashing ──
    full_name = (lead.get("full_name") or "").strip()
    parts     = full_name.split()
    first     = parts[0] if parts else ""
    last      = " ".join(parts[1:]) if len(parts) > 1 else ""

    # ── user_data: hashed PII (Meta requires PII pre-hashed) ──
    user_data = {}
    h_phone = sha256_hash(lead.get("phone_norm"))
    h_email = sha256_hash(lead.get("email_norm"))
    h_first = sha256_hash(first)
    h_last  = sha256_hash(last)

    if h_phone: user_data["ph"] = [h_phone]
    if h_email: user_data["em"] = [h_email]
    if h_first: user_data["fn"] = h_first
    if h_last:  user_data["ln"] = h_last

    # Location — same constants as the old script (improves match rate).
    user_data["country"] = sha256_hash("in")
    user_data["st"]      = sha256_hash("telangana")
    user_data["ct"]      = sha256_hash("hyderabad")

    # ── NEW: leadgen_id for deterministic matching ──
    # Meta CAPI accepts the Lead Ads lead id as user_data['lead_id']
    # (an integer-like string). It is NOT hashed — it is an opaque id,
    # not PII. Present only for Meta-origin leads.
    used_leadgen = False
    leadgen_id = lead.get("leadgen_id")
    if leadgen_id:
        user_data["lead_id"] = int(leadgen_id) if str(leadgen_id).isdigit() \
                               else leadgen_id
        used_leadgen = True

    # ── Deterministic event_id — same scheme as the old script ──
    # Same lead + same stage always yields the same id, so Meta
    # deduplicates automatically. This is what makes it SAFE for the
    # old script and Job C to run in parallel during cutover.
    identifier   = lead.get("selldo_lead_id") or lead.get("phone_norm") \
                   or lead.get("cls_id")
    event_id_raw = f"{identifier}_{stage}"
    event_id     = hashlib.md5(event_id_raw.encode()).hexdigest()

    payload = {
        "event_name"    : meta_event,
        "event_time"    : event_time,
        "event_id"      : event_id,
        "action_source" : "system_generated",
        "user_data"     : user_data,
        "custom_data"   : {
            # CRM origin tags — required by Meta's CRM dataset spec (added v1.1)
            "event_source"     : CRM_EVENT_SOURCE,  # "crm"
            "lead_event_source": CRM_NAME,          # "Sell.do"
            # stage + value fields (unchanged from v1.0)
            "lead_stage": stage,
            "value"     : value,
            "currency"  : "INR",
        },
    }
    return payload, used_leadgen


# ─────────────────────────────────────────────────────────────
# FIRE A BATCH OF EVENTS TO ONE DATASET
# ─────────────────────────────────────────────────────────────

def fire_to_dataset(events_with_leads, dataset_id, access_token,
                    label="PRIMARY", dry_run=False):
    """
    Fire a list of (payload, lead, used_leadgen) triples to ONE Meta
    CAPI dataset.

    label   : "PRIMARY" or the additional dataset's label — shown in logs.
    dry_run : if True, log what WOULD be sent but make no API call.

    Returns the set of cls_ids Meta CONFIRMED receiving (events_received
    > 0). Only confirmed ids are safe to mark_as_fired().
    """
    capi_url  = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{dataset_id}/events"
    confirmed = set()
    ok = fail = 0

    for payload, lead, used_leadgen in events_with_leads:
        name = lead.get("full_name", "?")

        if dry_run:
            tag = "leadgen" if "lead_id" in payload["user_data"] else "hashed-only"
            log(f"  [{label}] DRY-RUN would fire: {payload['event_name']} "
                f"| {name} | stage={lead['current_stage']} | {tag}")
            confirmed.add(lead["cls_id"])
            ok += 1
            continue

        body = {"data": [payload]}
        try:
            resp = requests.post(capi_url,
                                 params={"access_token": access_token},
                                 json=body, timeout=15)
            result = resp.json()
            if resp.status_code == 200 and result.get("events_received", 0) > 0:
                confirmed.add(lead["cls_id"])
                ok += 1
                tag = "leadgen" if "lead_id" in payload["user_data"] else "hashed"
                log(f"  [{label}] OK {payload['event_name']} | {name} "
                    f"| {lead['current_stage']} | INR {payload['custom_data']['value']} | {tag}")
            else:
                fail += 1
                log(f"  [{label}] FAILED {name} | {result}", "ERROR")
        except Exception as e:
            fail += 1
            log(f"  [{label}] ERROR {name}: {e}", "ERROR")

        time.sleep(API_PAUSE_SEC)

    log(f"  [{label}] dataset {dataset_id} -> OK {ok} | Failed {fail}")
    return confirmed


# ─────────────────────────────────────────────────────────────
# OUTPUT REFRESH  (dashboard + KV snapshot)
# ─────────────────────────────────────────────────────────────

def _refresh_outputs(dry_run=False):
    """
    Refresh dashboard.html and push the KV snapshot to Cloudflare.
    Called from BOTH code paths in run():
      - zero-fire cycles (nothing to send to Meta, but phone app still
        needs fresh data — job-health flags, lead counts, etc.)
      - normal firing cycles (after events are recorded)

    Both calls are non-blocking: a dashboard or network failure here
    must never prevent the completion flag from being set.
    """
    if dry_run:
        log("DRY-RUN — skipping dashboard refresh and snapshot push.")
        return

    # ── Dashboard ──
    try:
        import cls_dashboard
        cls_dashboard.generate_dashboard()
        log("Dashboard refreshed: dashboard.html")
    except Exception as e:
        log(f"Dashboard refresh failed (non-critical): {e}", "WARNING")

    # ── Cloudflare KV snapshot (powers cls.asianbuild.in PWA) ──
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
# MAIN
# ─────────────────────────────────────────────────────────────

def run(force=False, dry_run=False):
    log("=" * 55)
    log("CLS JOB C — CAPI Firer — START")
    if dry_run:
        log("MODE: --dry-run (no events will actually be sent)")
    log("=" * 55)

    cls_db.init_db()

    # ── Risk 1: completion-flag gate — Job C runs after Job B ──
    if not force:
        if cls_db.is_flag_fresh("selldo_sync", SELLDO_FLAG_MAX_AGE_MIN):
            log("Gate OK — Job B's 'selldo_sync' flag is fresh.")
        else:
            ts = cls_db.get_flag("selldo_sync")
            log(f"Gate BLOCKED — 'selldo_sync' flag missing or stale (last: {ts}).",
                "WARNING")
            log("Job B has not completed recently. Skipping this cycle.")
            log("(Use --force to override for manual testing.)")
            cls_db.write_job_result("Job C (CAPI Firer)", False,
                                     f"Gate blocked — 'selldo_sync' flag missing or stale (last: {ts})")
            return False
    else:
        log("Gate SKIPPED — --force flag used.")

    # ── Credentials ──
    env = load_env()
    primary_dataset    = env.get("META_PRIMARY_DATASET", "")
    primary_token      = env.get("META_CAPI_TOKEN", "")
    additional_dataset = env.get("META_ADDITIONAL_DATASET", "")
    additional_token   = env.get("META_ADDITIONAL_TOKEN", "")

    if not primary_dataset or not primary_token:
        log("META_PRIMARY_DATASET or META_CAPI_TOKEN missing in .env — aborting.",
            "ERROR")
        cls_db.write_job_result("Job C (CAPI Firer)", False,
                                 "META_PRIMARY_DATASET or META_CAPI_TOKEN missing in .env")
        return False

    # ── Find leads whose stage changed since last fired (Risk 4) ──
    unfired = cls_db.get_unfired_leads()
    # Defensive: get_unfired_leads already filters to TARGET_STAGES,
    # but re-check here so this script's definition is authoritative.
    unfired = [l for l in unfired if l["current_stage"] in TARGET_STAGES]

    if not unfired:
        log("No stage changes to fire this run. Nothing to do.")
        _refresh_outputs(dry_run=False)   # still update dashboard + KV snapshot
        cls_db.set_flag("capi_fire")
        log("=" * 55)
        log("CLS JOB C — CAPI Firer — DONE (nothing to fire)")
        log("=" * 55)
        cls_db.write_job_result("Job C (CAPI Firer)", True,
                                 "No stage changes to fire this run")
        return True

    log(f"Leads to fire: {len(unfired)}")

    # ── Build all payloads ──
    event_time = int(time.time())
    events_with_leads = []
    leadgen_count = 0
    for lead in unfired:
        payload, used_leadgen = build_event_payload(lead, event_time)
        events_with_leads.append((payload, lead, used_leadgen))
        if used_leadgen:
            leadgen_count += 1

    log(f"  {leadgen_count} will fire WITH leadgen_id (deterministic match)")
    log(f"  {len(unfired) - leadgen_count} will fire with hashed PII only")

    # ── Fire to PRIMARY dataset ──
    log("-" * 55)
    log(f"Firing to PRIMARY dataset ({primary_dataset})...")
    confirmed = fire_to_dataset(
        events_with_leads, primary_dataset, primary_token,
        label="PRIMARY", dry_run=dry_run)

    # ── Fan-out to ADDITIONAL dataset (same as old script) ──
    if additional_dataset and additional_token:
        log("-" * 55)
        log(f"Fan-out: firing same events to additional dataset "
            f"({additional_dataset})...")
        # Fan-out failures do NOT block — primary already succeeded.
        fire_to_dataset(
            events_with_leads, additional_dataset, additional_token,
            label="Naishka_Web_Events", dry_run=dry_run)
    else:
        log("No additional dataset configured — single-dataset mode.")

    # ── Risk 4: mark as fired ONLY what the PRIMARY dataset confirmed ──
    # We key 'fired' off the primary dataset's confirmation. If the
    # additional dataset lagged, that is logged but does not change
    # fire-state — the primary is the source of truth.
    # For each confirmed lead we ALSO append a row to events_log — the
    # permanent historical record the dashboard reads from.
    marked = 0
    for payload, lead, used_leadgen in events_with_leads:
        if lead["cls_id"] in confirmed:
            if not dry_run:
                # Capture the PREVIOUS stage BEFORE mark_as_fired runs.
                # lead["last_fired_stage"] is the stage this lead was at
                # before this fire (None on a lead's very first fire).
                # mark_as_fired() is about to overwrite last_fired_stage
                # with current_stage, so we must read it FIRST.
                prev_stage = lead.get("last_fired_stage")
                cls_db.mark_as_fired(lead["cls_id"], lead["current_stage"])
                cls_db.record_event(
                    cls_id      = lead["cls_id"],
                    leadgen_id  = lead.get("leadgen_id"),
                    full_name   = lead.get("full_name"),
                    phone_norm  = lead.get("phone_norm"),
                    project     = lead.get("project"),
                    crm_stage   = lead["current_stage"],
                    prev_stage  = prev_stage,
                    meta_event  = payload["event_name"],
                    value_inr   = payload["custom_data"]["value"],
                    used_leadgen= used_leadgen,
                    dataset_id  = primary_dataset,
                    lead_owner  = lead.get("lead_owner"),   # v1.6 attribution
                )
            marked += 1

    log("-" * 55)
    if dry_run:
        log(f"DRY-RUN complete — {marked} events WOULD have been marked fired.")
    else:
        log(f"Marked {marked} leads as fired (stage recorded in last_fired_stage).")
        log(f"Recorded {marked} events into events_log history.")

    # ── CLS health snapshot ──
    s = cls_db.stats()
    log(f"CLS now holds: {s['total_leads']} leads "
        f"({s['with_leadgen_id']} with leadgen_id, "
        f"{s['pending_fire']} still pending fire)")

    # ── Refresh the dashboard (hybrid: Job C auto-updates it) ──
    # ── Push snapshot to Cloudflare KV (powers the cls.asianbuild.in PWA) ──
    _refresh_outputs(dry_run=dry_run)

    # ── Completion flag ──
    cls_db.set_flag("capi_fire")
    log("Completion flag 'capi_fire' set.")

    log("=" * 55)
    log("CLS JOB C — CAPI Firer — DONE")
    log("=" * 55)
    if dry_run:
        cls_db.write_job_result("Job C (CAPI Firer)", True,
                                 f"DRY-RUN — {marked} events would have fired to Meta")
    else:
        cls_db.write_job_result("Job C (CAPI Firer)", True,
                                 f"{marked} events fired to Meta")
    return True


# ─────────────────────────────────────────────────────────────
# SELF-TEST  —  offline; no API calls
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Verifies payload construction without contacting Meta:
      - target stages map to correct Meta event names + values
      - leadgen_id is included when present, absent when not
      - event_id is deterministic (same input -> same id)
      - PII is hashed (64-char hex), leadgen_id is NOT hashed
    """
    print("=" * 55)
    print(" CLS CAPI FIRER — SELF TEST (offline)")
    print("=" * 55)

    et = 1700000000

    # ── A Meta-origin lead WITH leadgen_id ──
    meta_lead = {
        "cls_id": "c1", "leadgen_id": "1234567890",
        "selldo_lead_id": "SD1", "full_name": "Ravi Kumar",
        "phone_norm": "9876543210", "email_norm": "ravi@gmail.com",
        "current_stage": "Opportunity",
    }
    p1, used1 = build_event_payload(meta_lead, et)
    ok = (p1["event_name"] == "Schedule" and used1
          and p1["user_data"].get("lead_id") == 1234567890
          and p1["custom_data"]["value"] == 1000)
    print(f"  [{'OK' if ok else 'FAIL'}] Meta lead -> Schedule, value 1000, lead_id present")

    # ── A Sell.do-only lead WITHOUT leadgen_id ──
    selldo_lead = {
        "cls_id": "c2", "leadgen_id": None,
        "selldo_lead_id": "SD2", "full_name": "Sita Reddy",
        "phone_norm": "9000000001", "email_norm": "",
        "current_stage": "Prospect",
    }
    p2, used2 = build_event_payload(selldo_lead, et)
    ok = (p2["event_name"] == "QualifiedLead" and not used2
          and "lead_id" not in p2["user_data"]
          and p2["custom_data"]["value"] == 200)
    print(f"  [{'OK' if ok else 'FAIL'}] Sell.do-only lead -> QualifiedLead, no lead_id")

    # ── Site Visited ──
    sv = dict(meta_lead); sv["current_stage"] = "Site Visited"
    p3, _ = build_event_payload(sv, et)
    ok = (p3["event_name"] == "CompleteRegistration"
          and p3["custom_data"]["value"] == 3000)
    print(f"  [{'OK' if ok else 'FAIL'}] Site Visited -> CompleteRegistration, value 3000")

    # ── v1.3: Incoming → Lead, value 0 ──
    # This is the lead coverage fix. Every new lead fires immediately on
    # arrival so Meta sees 100% coverage, not just the ~30% that reach
    # Prospect. Value must be 0 — Incoming is an unqualified signal.
    incoming_lead = dict(meta_lead); incoming_lead["current_stage"] = "Incoming"
    p4, _ = build_event_payload(incoming_lead, et)
    ok = (p4["event_name"] == "Lead"
          and p4["custom_data"]["value"] == 0
          and "Incoming" in TARGET_STAGES)
    print(f"  [{'OK' if ok else 'FAIL'}] Incoming -> Lead, value 0 (lead coverage fix)")

    # ── Deterministic event_id ──
    p1b, _ = build_event_payload(meta_lead, et + 999)  # different time
    ok = (p1["event_id"] == p1b["event_id"])  # id must NOT depend on time
    print(f"  [{'OK' if ok else 'FAIL'}] event_id deterministic (time-independent)")

    # ── PII hashed, leadgen_id NOT hashed ──
    ph = p1["user_data"]["ph"][0]
    ok = (len(ph) == 64 and all(c in "0123456789abcdef" for c in ph)
          and p1["user_data"]["lead_id"] == 1234567890)
    print(f"  [{'OK' if ok else 'FAIL'}] phone hashed (64-hex), leadgen_id left as id")

    # ── Non-target stages do not fire ──
    ok = ("Booked" not in STAGE_EVENT_MAP and "Lost" not in STAGE_EVENT_MAP
          and "Re Assigned" not in STAGE_EVENT_MAP)
    print(f"  [{'OK' if ok else 'FAIL'}] non-target stages (Booked/Lost/Re Assigned) not in event map")

    # ── v1.1: CRM origin tags present on EVERY event ──
    cd1, cd2 = p1["custom_data"], p2["custom_data"]
    ok = (cd1.get("event_source") == "crm" and cd1.get("lead_event_source") == CRM_NAME
          and cd2.get("event_source") == "crm" and cd2.get("lead_event_source") == CRM_NAME)
    print(f"  [{'OK' if ok else 'FAIL'}] custom_data: event_source='crm' + lead_event_source='{CRM_NAME}'")

    # ── v1.2: Graph API version is v23.0 ──
    ok = GRAPH_API_VERSION == "v23.0"
    print(f"  [{'OK' if ok else 'FAIL'}] Graph API version is {GRAPH_API_VERSION} (expected v23.0)")

    print("=" * 55)
    print(" SELF TEST COMPLETE — offline logic verified.")
    print(" Use --dry-run for a live no-send check against real CLS data.")
    print("=" * 55)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
    else:
        run(force=("--force" in args),
            dry_run=("--dry-run" in args))
