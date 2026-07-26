"""
=============================================================
meta_leads_fetcher.py  —  CLS Job A  |  Meta Lead Ads Fetcher
=============================================================
Version : 1.3
Author  : Built for Asian Properties / Srikanth

CHANGE LOG
----------
v1.3 (July 2026)  : Campaign Routing support (Task 3 of the settings-GUI
                    batch; requires cls_db.py v2.25). ADDITIONS ONLY.
                    Each LEAD_FORMS dict may now carry an optional
                    "campaign_name" key — a cleaner routing key than the
                    raw form_name, for forms where Srikanth wants one.
                    Where absent, falls back to that form's own
                    form_name, so every existing entry keeps working
                    with zero edits. At the cls_db.upsert_meta_lead(...)
                    call site, campaign = form.get("campaign_name",
                    form["form_name"]) is now passed through — used only
                    at true first-insert time (cls_db.py's branch 3),
                    same as lead_owner's existing handling.
v1.2 (2026-07-24) : CLS1/CLS2 database split support. ADDITIONS ONLY.
                    Added cls_db.write_job_result() calls at every
                    existing return point in run() (both failure gates
                    and the final success path) — one line to
                    C:\\CLS\\job_results.txt per run, reusing the
                    total_pulled/total_upserted counters this job
                    already computes. No new counting logic. DB target
                    itself is unchanged code-wise — Job A picks up
                    CLS1.db automatically via cls_db.py's new
                    CLS_DB_PATH env var default (see cls_db.py v2.23).
v1.1 (2026-06-18) : Removed 2 paused-campaign forms from LEAD_FORMS.
                    Kept: GraceClassic (Camp1) + Naishka (Camp5).
                    Paused forms preserved as comments below for easy
                    re-activation when campaigns resume.
v1.0              : Initial release.

WHAT THIS JOB DOES
------------------
Pulls leads from Meta (Facebook) Lead Ads forms and writes each one
into the Centralised Leads System (cls.db) with its leadgen_id — the
deterministic identifier that gives Meta CAPI events high match
quality. This is the FIRST job in the CLS pipeline:

    [Job A] meta_leads_fetcher.py   <-- THIS FILE
       |    pulls Meta leads -> cls.db, then sets the 'meta_fetch' flag
       v
    [Job B] selldo_to_cls.py        (waits for Job A's flag)
       |    adds CRM stages from Sell.do
       v
    [Job C] cls_capi_firer.py       (waits for Job B's flag)
            fires stage changes back to Meta CAPI

THE TWO-HOP TOKEN PATTERN  (the fix for error #190)
---------------------------------------------------
Lead data lives INSIDE a Page. Meta requires a *Page* access token to
read it — the System User token alone gets "(#190) must be called with
a Page Access Token". So every run:
    Stage 1: System User token  --asks for-->  Page token (per Page)
    Stage 2: Page token         --reads----->  lead forms' leads
Think of the System User token as the master keyring, and each Page
token as the single key it hands you for one specific door.

BACKFILL vs INCREMENTAL  (automatic — no manual flag)
-----------------------------------------------------
First run for a form  : pull EVERYTHING the form still retains (~90d).
Every run after       : pull only leads newer than the newest
                        meta_created_time already in cls.db for that
                        form. The script decides which mode by checking
                        cls.db itself.

ONE-TIME SETUP
--------------
  pip install requests python-dotenv
  (cls_db.py must be in the same folder)

  .env file (same folder) must contain:
    META_SYSTEM_USER_TOKEN=EAAX...
    META_APP_ID=1633891014576130
    META_APP_SECRET=...
    META_BUSINESS_ID=456193307406464

RUN
---
  python meta_leads_fetcher.py            # normal run
  python meta_leads_fetcher.py --selftest # offline checks, no API calls
=============================================================
"""

import os
import sys
import time
import hmac
import json
import hashlib
import requests
from datetime import datetime

import cls_db   # the foundation layer — Step 1

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR  = r"C:\CLS"
ENV_FILE  = os.path.join(BASE_DIR, ".env")
LOG_FILE  = os.path.join(BASE_DIR, "meta_leads_log.txt")

GRAPH_API_VERSION = "v23.0"
GRAPH_BASE        = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# ── The lead forms to pull ──
# Each form is tied to a Page. To add a new form later (e.g. when a
# new campaign launches), just append a dict here — nothing else needs
# to change.
#
# "partner_shared": True marks a Page shared in from a DIFFERENT
# Business Manager. Such forms are pulled exactly like the others, but
# flagged in logs so that if their lead pull comes back empty, the
# partner-share scope is the obvious first suspect.
#
# "campaign_name" (v1.3, OPTIONAL): the key Campaign Routing rules are
# matched against (/settings/campaign-routing). Omit it and the form's
# own "form_name" is used instead — every entry below currently omits
# it, so nothing changes today; add it explicitly only when a cleaner
# routing key than the raw form_name is wanted for a future campaign.
#
# ── PAUSED FORMS (campaigns stopped 2026-06-18) ──
# Re-activate by uncommenting the relevant dict when campaign resumes.
#
# PAUSED — Naishka Camp3 (18-02-2026)
# {
#     "project"       : "Naishka",
#     "page_id"       : "393908937139353",
#     "form_id"       : "1440290974551962",
#     "form_name"     : "Camp3_Naishka_18-02-2026",
#     "partner_shared": False,
# },
#
# PAUSED — Prima Paradiso Camp1 (16-05-2026)
# {
#     "project"       : "Prima Paradiso",
#     "page_id"       : "634269686433846",
#     "form_id"       : "1486484632947733",
#     "form_name"     : "Camp1_Prima_16-05-2026",
#     "partner_shared": True,   # shared from a separate BM
# },

LEAD_FORMS = [
    {
        "project"       : "Grace Classic",
        "page_id"       : "1040065085855859",
        "form_id"       : "1481490140176052",
        "form_name"     : "Ad1_Adset1_Camp1_GraceClassic_26-03-2026",
        "partner_shared": False,
    },
    {
        "project"       : "Naishka",
        "page_id"       : "393908937139353",
        "form_id"       : "933648612881057",
        "form_name"     : "Camp5_Naishka_08-05-2026",
        "partner_shared": False,
    },
]

# Meta paginates lead results. 100 per page keeps requests light.
PAGE_SIZE     = 100
# Small pause between API calls — courteous, and avoids rate-limit bursts.
API_PAUSE_SEC = 0.4


# ─────────────────────────────────────────────────────────────
# LOGGING  —  same style as the existing CAPI script
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
        pass   # never let a logging failure crash the job


# ─────────────────────────────────────────────────────────────
# .env LOADER
# ─────────────────────────────────────────────────────────────

def load_env():
    """
    Read .env into a dict. Uses python-dotenv if available, else a
    tiny built-in parser so the script still runs if the package is
    missing. Returns {} if .env is absent.
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
# SECURITY  —  appsecret_proof
# ─────────────────────────────────────────────────────────────

def make_appsecret_proof(access_token, app_secret):
    """
    Meta's appsecret_proof: an HMAC-SHA256 of the access token, keyed
    by the App Secret. Sent alongside every call so Meta can verify the
    request genuinely came from someone holding the App Secret — not
    just someone who copied a token. Like a signature on a cheque: the
    account number alone is not enough.
    """
    return hmac.new(
        app_secret.encode("utf-8"),
        access_token.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


# ─────────────────────────────────────────────────────────────
# GRAPH API CALL  —  one wrapper, used for every request
# ─────────────────────────────────────────────────────────────

def graph_get(path, access_token, app_secret, params=None):
    """
    Perform one authenticated GET against the Graph API.
    Returns parsed JSON dict. Raises RuntimeError on a Meta error so
    the caller can decide whether to skip that form or abort the run.
    """
    params = dict(params or {})
    params["access_token"]    = access_token
    params["appsecret_proof"] = make_appsecret_proof(access_token, app_secret)

    url = f"{GRAPH_BASE}/{path}"
    resp = requests.get(url, params=params, timeout=30)
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"Non-JSON response (HTTP {resp.status_code}) from {path}")

    if "error" in data:
        err  = data["error"]
        code = err.get("code", "?")
        msg  = err.get("message", "unknown error")
        raise RuntimeError(f"Graph API error #{code}: {msg}")

    return data


# ─────────────────────────────────────────────────────────────
# STAGE 1  —  resolve a Page Access Token from the System User token
# ─────────────────────────────────────────────────────────────

def resolve_page_token(page_id, system_user_token, app_secret):
    """
    Exchange the System User token for a Page-specific token.
    This is the fix for error #190: lead endpoints need a Page token.

    A Page token derived from a non-expiring System User token is
    itself non-expiring — but we still resolve it fresh every run, so
    that adding a new Page later needs no token management at all.
    """
    data = graph_get(
        page_id,
        access_token=system_user_token,
        app_secret=app_secret,
        params={"fields": "access_token,name"},
    )
    token = data.get("access_token")
    name  = data.get("name", page_id)
    if not token:
        raise RuntimeError(
            f"Page {page_id} returned no access_token — the System User "
            f"may not have this Page assigned."
        )
    return token, name


# ─────────────────────────────────────────────────────────────
# STAGE 2/3  —  pull leads from one form (handles pagination)
# ─────────────────────────────────────────────────────────────

def fetch_leads_for_form(form, page_token, app_secret, since_unix=None):
    """
    Pull all leads for one form, following Meta's pagination.

    since_unix : if given, only leads created at/after this UNIX time
                 are requested (incremental mode). If None, every lead
                 the form still retains is pulled (first-run backfill).

    Returns a list of raw Meta lead dicts.
    """
    form_id   = form["form_id"]
    form_name = form["form_name"]
    tag       = "PARTNER" if form["partner_shared"] else "OWNED"

    params = {
        "fields": "id,created_time,field_data",
        "limit" : PAGE_SIZE,
    }
    if since_unix is not None:
        # Meta accepts a 'filtering' param to bound by created_time.
        params["filtering"] = json.dumps([{
            "field"   : "time_created",
            "operator": "GREATER_THAN",
            "value"   : int(since_unix),
        }])
        mode = f"incremental (since {datetime.fromtimestamp(since_unix)})"
    else:
        mode = "full backfill"

    log(f"  [{tag}] Form '{form_name}' — {mode}")

    leads    = []
    path     = f"{form_id}/leads"
    page_num = 0

    while True:
        page_num += 1
        data = graph_get(path, page_token, app_secret, params)
        batch = data.get("data", [])
        leads.extend(batch)
        log(f"    page {page_num}: {len(batch)} leads (running total {len(leads)})")

        # Meta returns a 'paging.next' URL when more pages exist.
        next_url = data.get("paging", {}).get("next")
        if not next_url or not batch:
            break

        # For subsequent pages we call the 'next' URL directly. It
        # already carries cursor + token, but we re-attach our params
        # by switching to a cursor-based call.
        after = data.get("paging", {}).get("cursors", {}).get("after")
        if not after:
            break
        params["after"] = after
        time.sleep(API_PAUSE_SEC)

    return leads


# ─────────────────────────────────────────────────────────────
# FIELD EXTRACTION  —  turn Meta's field_data into name/phone/email
# ─────────────────────────────────────────────────────────────

def extract_lead_fields(raw_lead):
    """
    Meta delivers answers as a list:
      field_data: [ {name:'full_name', values:['Ravi']},
                    {name:'phone_number', values:['+919876543210']}, ... ]
    Field names vary by how the form was built, so we match on a set
    of known aliases for each of name / phone / email.

    Returns dict: leadgen_id, created_time, full_name, phone, email.
    """
    out = {
        "leadgen_id"  : raw_lead.get("id", ""),
        "created_time": raw_lead.get("created_time", ""),
        "full_name"   : "",
        "phone"       : "",
        "email"       : "",
    }

    # NOTE: 'first_name' is deliberately NOT in name_keys. If it were,
    # the full_name branch below would grab it and stop, so a form with
    # separate First/Last fields would store only the first name. Keeping
    # it out lets the dedicated first/last branch stitch the full name.
    name_keys  = {"full_name", "name"}
    phone_keys = {"phone_number", "phone", "mobile", "mobile_number"}
    email_keys = {"email", "email_address"}

    first_name = ""
    last_name  = ""

    for field in raw_lead.get("field_data", []):
        key    = (field.get("name") or "").lower().strip()
        values = field.get("values") or [""]
        value  = str(values[0]).strip()

        if key in name_keys and not out["full_name"]:
            out["full_name"] = value
        elif key == "first_name":
            first_name = value
        elif key == "last_name":
            last_name = value
        elif key in phone_keys and not out["phone"]:
            out["phone"] = value
        elif key in email_keys and not out["email"]:
            out["email"] = value

    # If the form used separate first/last fields, stitch them.
    if not out["full_name"]:
        out["full_name"] = f"{first_name} {last_name}".strip()

    return out


# ─────────────────────────────────────────────────────────────
# INCREMENTAL HELPER  —  newest lead time already in CLS for a form
# ─────────────────────────────────────────────────────────────

def newest_meta_time_for_form(form_id):
    """
    Look in cls.db for the most recent meta_created_time among leads
    already pulled from this form. Returns a UNIX timestamp, or None
    if the form has never been pulled (-> first-run backfill).
    """
    conn = cls_db._connect()
    try:
        row = conn.execute(
            "SELECT MAX(meta_created_time) m FROM leads WHERE form_id=?",
            (form_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not row["m"]:
        return None

    # Meta created_time looks like '2026-05-21T10:30:00+0530'.
    raw = row["m"]
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).timestamp()
        except ValueError:
            continue
    return None   # unparseable -> safest is to treat as backfill


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run():
    log("=" * 55)
    log("CLS JOB A — Meta Leads Fetcher — START")
    log("=" * 55)

    # ── Make sure the CLS database exists ──
    cls_db.init_db()

    # ── Load credentials ──
    env = load_env()
    system_user_token = env.get("META_SYSTEM_USER_TOKEN", "")
    app_secret        = env.get("META_APP_SECRET", "")

    if not system_user_token or not app_secret:
        log("META_SYSTEM_USER_TOKEN or META_APP_SECRET missing in .env — aborting.",
            "ERROR")
        cls_db.write_job_result("Job A (Meta Leads Fetcher)", False,
                                 "META_SYSTEM_USER_TOKEN or META_APP_SECRET missing in .env")
        return False

    # ── Resolve a Page token once per unique Page (Stage 1) ──
    unique_pages = {f["page_id"] for f in LEAD_FORMS}
    page_tokens  = {}
    log(f"Resolving Page tokens for {len(unique_pages)} Page(s)...")
    for pid in unique_pages:
        try:
            token, name = resolve_page_token(pid, system_user_token, app_secret)
            page_tokens[pid] = token
            log(f"  OK — Page token resolved: '{name}' ({pid})")
        except Exception as e:
            log(f"  FAILED resolving Page {pid}: {e}", "ERROR")

    if not page_tokens:
        log("No Page tokens could be resolved — aborting.", "ERROR")
        cls_db.write_job_result("Job A (Meta Leads Fetcher)", False,
                                 "No Page tokens could be resolved")
        return False

    # ── Pull each form and upsert into CLS (Stages 2-4) ──
    total_pulled   = 0
    total_upserted = 0
    per_form_report = []

    for form in LEAD_FORMS:
        pid = form["page_id"]
        if pid not in page_tokens:
            log(f"Skipping form '{form['form_name']}' — its Page token failed.",
                "WARNING")
            per_form_report.append((form["form_name"], "SKIPPED", 0))
            continue

        try:
            since = newest_meta_time_for_form(form["form_id"])
            raw_leads = fetch_leads_for_form(
                form, page_tokens[pid], app_secret, since_unix=since
            )
        except Exception as e:
            log(f"  ERROR pulling form '{form['form_name']}': {e}", "ERROR")
            per_form_report.append((form["form_name"], "ERROR", 0))
            continue

        # Upsert every lead into CLS.
        upserted = 0
        for raw in raw_leads:
            fields = extract_lead_fields(raw)
            if not fields["leadgen_id"]:
                continue
            try:
                cls_db.upsert_meta_lead(
                    leadgen_id        = fields["leadgen_id"],
                    form_id           = form["form_id"],
                    project           = form["project"],
                    full_name         = fields["full_name"],
                    phone_raw         = fields["phone"],
                    email_raw         = fields["email"],
                    meta_created_time = fields["created_time"],
                    campaign          = form.get("campaign_name", form["form_name"]),
                )
                upserted += 1
            except Exception as e:
                log(f"    upsert failed for lead {fields['leadgen_id']}: {e}",
                    "WARNING")

        total_pulled   += len(raw_leads)
        total_upserted += upserted
        per_form_report.append((form["form_name"], "OK", upserted))

        time.sleep(API_PAUSE_SEC)

    # ── Per-form summary ──
    log("-" * 55)
    log("PER-FORM SUMMARY")
    for fname, status, count in per_form_report:
        log(f"  {status:8s} | {count:4d} leads | {fname}")
    log(f"TOTAL: {total_pulled} pulled, {total_upserted} upserted into CLS")

    # ── CLS health snapshot ──
    s = cls_db.stats()
    log(f"CLS now holds: {s['total_leads']} leads "
        f"({s['with_leadgen_id']} with leadgen_id, "
        f"{s['selldo_only']} selldo-only, {s['pending_fire']} pending fire)")

    # ── Completion flag (Risk 1) — tells Job B it is safe to run ──
    cls_db.set_flag("meta_fetch")
    log("Completion flag 'meta_fetch' set — Job B may now proceed.")

    log("=" * 55)
    log("CLS JOB A — Meta Leads Fetcher — DONE")
    log("=" * 55)
    cls_db.write_job_result("Job A (Meta Leads Fetcher)", True,
                             f"{total_pulled} leads pulled, {total_upserted} upserted")
    return True


# ─────────────────────────────────────────────────────────────
# SELF-TEST  —  offline, no API calls
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Verifies the pure-logic pieces without touching Meta's API:
      - appsecret_proof is a valid 64-char hex digest
      - field extraction handles full_name, first/last, aliases, blanks
    """
    print("=" * 55)
    print(" META LEADS FETCHER — SELF TEST (offline)")
    print("=" * 55)

    # ── appsecret_proof ──
    proof = make_appsecret_proof("dummy_token", "dummy_secret")
    ok = len(proof) == 64 and all(c in "0123456789abcdef" for c in proof)
    print(f"  [{'OK' if ok else 'FAIL'}] appsecret_proof = 64-char hex")

    # ── field extraction: standard full_name form ──
    lead1 = {
        "id": "LG1", "created_time": "2026-05-21T10:30:00+0530",
        "field_data": [
            {"name": "full_name",    "values": ["Ravi Kumar"]},
            {"name": "phone_number", "values": ["+91 98765 43210"]},
            {"name": "email",        "values": ["ravi@gmail.com"]},
        ],
    }
    f1 = extract_lead_fields(lead1)
    ok = (f1["leadgen_id"] == "LG1" and f1["full_name"] == "Ravi Kumar"
          and f1["phone"] == "+91 98765 43210" and f1["email"] == "ravi@gmail.com")
    print(f"  [{'OK' if ok else 'FAIL'}] extract: standard full_name form")

    # ── field extraction: separate first/last + alias 'mobile' ──
    lead2 = {
        "id": "LG2", "created_time": "2026-05-21T11:00:00+0530",
        "field_data": [
            {"name": "first_name", "values": ["Sita"]},
            {"name": "last_name",  "values": ["Reddy"]},
            {"name": "mobile",     "values": ["9000000001"]},
        ],
    }
    f2 = extract_lead_fields(lead2)
    ok = (f2["full_name"] == "Sita Reddy" and f2["phone"] == "9000000001"
          and f2["email"] == "")
    print(f"  [{'OK' if ok else 'FAIL'}] extract: first/last + 'mobile' alias + blank email")

    # ── field extraction: missing everything but id ──
    f3 = extract_lead_fields({"id": "LG3", "field_data": []})
    ok = (f3["leadgen_id"] == "LG3" and f3["full_name"] == ""
          and f3["phone"] == "" and f3["email"] == "")
    print(f"  [{'OK' if ok else 'FAIL'}] extract: empty field_data handled safely")

    # ── normalization round-trip via cls_db (the integration point) ──
    ph = cls_db.norm_phone(f1["phone"])
    em = cls_db.norm_email(f1["email"])
    ok = (ph == "9876543210" and em == "ravi@gmail.com")
    print(f"  [{'OK' if ok else 'FAIL'}] cls_db normalization: {f1['phone']!r} -> {ph!r}")

    print("=" * 55)
    print(" SELF TEST COMPLETE — offline logic verified.")
    print(" To test live API calls, run without --selftest.")
    print("=" * 55)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        run()
