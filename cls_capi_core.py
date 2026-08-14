"""
=============================================================
cls_capi_core.py  —  CLS Shared CAPI Payload + Inline Fire Logic
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.0 (2026-08-14) — NEW FILE. Part of the inline-CAPI-firing redesign
  that replaces Job C's full-table-scan cron model. Moved VERBATIM from
  cls_capi_firer.py v1.8 (hashing/payload logic unchanged):
  GRAPH_API_VERSION, TARGET_STAGES, STAGE_VALUES, STAGE_EVENT_MAP,
  CRM_EVENT_SOURCE, API_PAUSE_SEC, sha256_hash(), build_event_payload().

  One value deliberately changed: CRM_NAME "Sell.do" -> "Asian
  Properties CRM". Sell.do is fully retired; this is Meta-facing
  metadata only (custom_data.lead_event_source), not functional.

  One cleanup: the old file defined CRM_EVENT_SOURCE/CRM_NAME TWICE in
  a row (identical copy-paste block, second assignment silently
  overwrote the first with the same values). Consolidated to one
  definition here — no behavioural difference, just removed dead
  duplication.

  NEW — fire_single_lead_event(lead, env, dry_run=False): fires ONE
  lead's current-stage event synchronously (primary dataset, then a
  best-effort additional-dataset fan-out), confirms events_received > 0,
  and only then calls cls_db.mark_as_fired() + cls_db.record_event().
  Built so three call sites (crm/app.py's change_lead_stage() route,
  meta_leads_fetcher.py's new-lead insert, and cls_capi_firer.py v3.0's
  queue processor) share one fire implementation instead of three.

WHY THIS FILE EXISTS
---------------------
Job C's old model (cls_capi_firer.py v1.8) was a full-table cron scan:
every hour, find every lead whose stage changed, fire it. The redesign
fires inline instead — the moment a stage actually changes (app.py) or
a new lead lands (meta_leads_fetcher.py) — with a small failure queue
(cls_db.py's capi_fire_queue, v2.55) catching anything that fails so
cls_capi_firer.py v3.0 can retry it later. This file is the shared
payload-building + single-event-firing logic all three call sites use,
so the Meta-facing payload format only has one implementation to keep
correct.

cls_capi_firer.py v1.8's batch functions (fire_to_dataset(), run()'s
full-scan loop) are NOT moved here — that was the old cron-batch
machinery, superseded by this file's single-lead function plus
cls_capi_firer.py v3.0's queue-processing loop.
=============================================================
"""

import hashlib
import time

import requests

import cls_db   # the foundation layer

# ─────────────────────────────────────────────────────────────
# CONFIGURATION  —  moved verbatim from cls_capi_firer.py v1.8
# (see that file's own changelog for the history behind these values)
# ─────────────────────────────────────────────────────────────

GRAPH_API_VERSION = "v23.0"   # v19.0 deprecated May 21 2026; upgraded June 9 2026
                              # next planned upgrade: v25.0 in ~3-4 months

# ── Target stages — fires a CAPI event when a lead enters any of these ──
# Incoming : fires immediately on lead arrival → boosts lead coverage above
#            Meta's 60% threshold for Conversion Lead Optimisation
# Prospect, Opportunity, Site Visited : quality conversion signals
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

# ── CRM identity for Meta's CRM lead-conversion spec ──
# Meta wants every CRM-sourced event tagged with its origin so the
# Conversion Leads optimisation knows the signal came from a CRM (not a
# browser) and which CRM produced it. Sent inside custom_data on every
# event. Pulled into a constant so a future CRM switch is a one-line
# change — same "config-not-code" principle as form IDs in the projects
# table.
CRM_EVENT_SOURCE = "crm"                    # custom_data.event_source
CRM_NAME         = "Asian Properties CRM"   # custom_data.lead_event_source
                                             # was "Sell.do" (cls_capi_firer.py
                                             # v1.8) — Sell.do fully retired,
                                             # 2026-08-14.

# Small pause between CAPI calls — same courtesy delay as the old cron script.
API_PAUSE_SEC = 0.3

# Shorter than the old cron's 15s timeout — this runs inside a live HTTP
# request (app.py) or a per-lead insert loop (meta_leads_fetcher.py), not
# a background batch job, so a slow Meta response must not hang the
# caller for long.
INLINE_TIMEOUT_SEC = 7


# ─────────────────────────────────────────────────────────────
# HELPER: SHA256 hash for Meta CAPI PII compliance
# (identical to cls_capi_firer.py v1.8 — Meta requires PII pre-hashed)
# ─────────────────────────────────────────────────────────────

def sha256_hash(value):
    """SHA256 of a normalized value. Returns None for blank/nan/none."""
    if not value or str(value).lower() in ("nan", "none", ""):
        return None
    return hashlib.sha256(str(value).strip().lower().encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# BUILD ONE CAPI EVENT PAYLOAD  (identical to cls_capi_firer.py v1.8)
# ─────────────────────────────────────────────────────────────

def build_event_payload(lead, event_time):
    """
    Build the Meta CAPI 'data' entry for one CLS lead.

    - user_data: hashed ph / em / fn / ln + hashed location (in/TG/Hyd)
    - deterministic event_id = md5(identifier + event_name)
    - custom_data: lead_stage, value (INR), currency

    leadgen_id enrichment: if the CLS lead has a leadgen_id, it is added
    as user_data['lead_id']. Meta uses this for DETERMINISTIC matching
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

    # ── leadgen_id for deterministic matching ──
    # Meta CAPI accepts the Lead Ads lead id as user_data['lead_id']
    # (an integer-like string). It is NOT hashed — it is an opaque id,
    # not PII. Present only for Meta-origin leads.
    used_leadgen = False
    leadgen_id = lead.get("leadgen_id")
    if leadgen_id:
        user_data["lead_id"] = int(leadgen_id) if str(leadgen_id).isdigit() \
                               else leadgen_id
        used_leadgen = True

    # ── Deterministic event_id ──
    # Same lead + same stage always yields the same id, so Meta
    # deduplicates automatically.
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
            # CRM origin tags — required by Meta's CRM dataset spec
            "event_source"     : CRM_EVENT_SOURCE,  # "crm"
            "lead_event_source": CRM_NAME,          # "Asian Properties CRM"
            # stage + value fields
            "lead_stage": stage,
            "value"     : value,
            "currency"  : "INR",
        },
    }
    return payload, used_leadgen


# ─────────────────────────────────────────────────────────────
# FIRE ONE LEAD'S EVENT SYNCHRONOUSLY  (NEW — v1.0)
# ─────────────────────────────────────────────────────────────

def fire_single_lead_event(lead, env, dry_run=False):
    """
    Fires ONE lead's current-stage event to Meta (primary dataset, then
    additional dataset if configured), confirms events_received > 0,
    and only then calls cls_db.mark_as_fired() + cls_db.record_event().
    Returns (success: bool, error: str | None). Never raises.
    """
    stage = lead.get("current_stage")
    if stage not in TARGET_STAGES:
        return True, None

    try:
        payload, used_leadgen = build_event_payload(lead, int(time.time()))
    except Exception as e:
        return False, f"payload build failed: {e}"

    primary_dataset = env.get("META_PRIMARY_DATASET", "")
    primary_token = env.get("META_CAPI_TOKEN", "")
    additional_dataset = env.get("META_ADDITIONAL_DATASET", "")
    additional_token = env.get("META_ADDITIONAL_TOKEN", "")

    if not primary_dataset or not primary_token:
        return False, "META_PRIMARY_DATASET or META_CAPI_TOKEN missing in .env"

    if dry_run:
        return True, None

    def _post(dataset_id, token):
        url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{dataset_id}/events"
        resp = requests.post(url, params={"access_token": token},
                              json={"data": [payload]}, timeout=INLINE_TIMEOUT_SEC)
        result = resp.json()
        return resp.status_code == 200 and result.get("events_received", 0) > 0, result

    try:
        confirmed, result = _post(primary_dataset, primary_token)
    except Exception as e:
        return False, f"primary dataset call failed: {e}"

    if not confirmed:
        return False, f"primary dataset did not confirm: {result}"

    if additional_dataset and additional_token:
        try:
            _post(additional_dataset, additional_token)
        except Exception:
            pass  # non-critical, matches old cron's behavior

    prev_stage = lead.get("last_fired_stage")
    cls_db.mark_as_fired(lead["cls_id"], stage)
    cls_db.record_event(
        cls_id=lead["cls_id"], leadgen_id=lead.get("leadgen_id"),
        full_name=lead.get("full_name"), phone_norm=lead.get("phone_norm"),
        project=lead.get("project"), crm_stage=stage, prev_stage=prev_stage,
        meta_event=payload["event_name"], value_inr=payload["custom_data"]["value"],
        used_leadgen=used_leadgen, dataset_id=primary_dataset,
        lead_owner=lead.get("lead_owner"),
    )
    return True, None
