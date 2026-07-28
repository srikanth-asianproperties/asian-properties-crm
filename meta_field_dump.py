"""
=============================================================
meta_field_dump.py  —  CLS Diagnostic  |  One-Time Meta Field Inventory
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

WHAT THIS DOES
--------------
Pulls a SMALL SAMPLE (default 8) of the most recent leads for each
active Meta Lead Ads form, requesting an EXPANDED field list —
including campaign/ad-set/ad/platform metadata that Job A
(meta_leads_fetcher.py) does NOT currently request — and dumps the
full raw response to a JSON file plus a readable console summary.

WHY THIS EXISTS
---------------
Sell.do's native Facebook integration was silently pulling
campaign/ad-level metadata that never showed up in CSV exports. Job A
only ever requested "id,created_time,field_data" (name/phone/email
from the form itself). This script is how you see, once, everything
else Meta is willing to hand over — so you can decide which fields
are worth adding to Job A permanently.

THIS SCRIPT IS READ-ONLY AND STANDALONE
----------------------------------------
- Does NOT import cls_db. Does NOT touch cls.db in any way.
- Does NOT modify meta_leads_fetcher.py or call any of its functions.
- Deliberately duplicates (rather than imports) the small pieces it
  needs from meta_leads_fetcher.py v1.1 (LEAD_FORMS, token resolution,
  the graph_get wrapper) — kept intentionally separate so running this
  diagnostic can never have any side effect on the production job, even
  if meta_leads_fetcher.py's internals change later. If you add/remove
  a campaign in meta_leads_fetcher.py's LEAD_FORMS, mirror the change
  here too if you re-run this script (it's a one-off tool, not a
  pipeline stage — drift here has zero production impact either way).
- Safe to run any number of times. Each run makes a handful of Graph
  API read calls (well under any rate limit) and writes ONLY a new
  timestamped dump file — never overwrites a previous run's output.

ONE-TIME SETUP
--------------
  Same folder as meta_leads_fetcher.py (needs the same .env):
    META_SYSTEM_USER_TOKEN=EAAX...
    META_APP_ID=...
    META_APP_SECRET=...
    META_BUSINESS_ID=...
  pip install requests python-dotenv   (same deps as Job A)

RUN
---
  python meta_field_dump.py
  python meta_field_dump.py --limit 15     # pull more/fewer per form

OUTPUT
------
  C:\\CLS\\meta_field_dump_<timestamp>.json   — full raw Meta response
  Console                                     — readable per-lead summary

CHANGE LOG
----------
v1.0 (2026-07) : Initial version.
=============================================================
"""

import os
import sys
import json
import hmac
import hashlib
import argparse
from datetime import datetime

import requests

# ─────────────────────────────────────────────────────────────
# CONFIGURATION  (duplicated from meta_leads_fetcher.py v1.1 —
# see docstring above for why this is deliberate)
# ─────────────────────────────────────────────────────────────

BASE_DIR  = r"C:\CLS"
ENV_FILE  = os.path.join(BASE_DIR, ".env")

GRAPH_API_VERSION = "v23.0"
GRAPH_BASE        = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Mirrors meta_leads_fetcher.py's active (non-paused) forms as of v1.1.
# Update this list if that one changes and you want this dump to match.
LEAD_FORMS = [
    {
        "project"  : "Grace Classic",
        "page_id"  : "1040065085855859",
        "form_id"  : "1481490140176052",
        "form_name": "Ad1_Adset1_Camp1_GraceClassic_26-03-2026",
    },
    {
        "project"  : "Naishka",
        "page_id"  : "393908937139353",
        "form_id"  : "933648612881057",
        "form_name": "Camp5_Naishka_08-05-2026",
    },
]

# The expanded field list — everything standard Meta exposes on a
# leadgen object beyond what Job A currently requests. field_data is
# included so you also see the form's own Q&A alongside the metadata.
FIELDS_TO_REQUEST = (
    "id,created_time,ad_id,ad_name,adset_id,adset_name,"
    "campaign_id,campaign_name,form_id,is_organic,platform,field_data"
)

DEFAULT_LIMIT = 8


def _p(msg=""):
    # Guard against any environment where stdout might be unavailable —
    # same defensive pattern as the rest of the CLS pipeline, even
    # though this script is always run interactively, never via
    # pythonw.exe/Task Scheduler.
    try:
        print(msg)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# .env LOADER  (same as meta_leads_fetcher.py)
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
# SECURITY  —  appsecret_proof  (same as meta_leads_fetcher.py)
# ─────────────────────────────────────────────────────────────

def make_appsecret_proof(access_token, app_secret):
    return hmac.new(
        app_secret.encode("utf-8"),
        access_token.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


# ─────────────────────────────────────────────────────────────
# GRAPH API CALL  (same wrapper pattern as meta_leads_fetcher.py)
# ─────────────────────────────────────────────────────────────

def graph_get(path, access_token, app_secret, params=None):
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


def resolve_page_token(page_id, system_user_token, app_secret):
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
# THE DUMP
# ─────────────────────────────────────────────────────────────

def dump_leads_for_form(form, page_token, app_secret, limit):
    """
    Pull the most recent `limit` leads for one form with the expanded
    field list. Single page only — this is a sample, not a full pull,
    so pagination is deliberately not implemented here.
    """
    params = {
        "fields": FIELDS_TO_REQUEST,
        "limit" : limit,
    }
    data = graph_get(f"{form['form_id']}/leads", page_token, app_secret, params)
    return data.get("data", [])


def summarize_lead(raw_lead):
    """Readable console breakdown of one raw lead dict."""
    lines = []
    top_level_keys = [k for k in raw_lead.keys() if k != "field_data"]
    for k in top_level_keys:
        lines.append(f"      {k:<16s}: {raw_lead.get(k)}")
    for field in raw_lead.get("field_data", []):
        name   = field.get("name", "?")
        values = field.get("values", [])
        lines.append(f"      [form field] {name:<20s}: {values}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="One-off Meta lead field diagnostic dump")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                         help=f"Leads to pull per form (default {DEFAULT_LIMIT})")
    args = parser.parse_args()

    env = load_env()
    system_user_token = env.get("META_SYSTEM_USER_TOKEN")
    app_secret         = env.get("META_APP_SECRET")

    if not system_user_token or not app_secret:
        _p("[FAIL] META_SYSTEM_USER_TOKEN or META_APP_SECRET missing from .env")
        _p(f"       Expected at: {ENV_FILE}")
        sys.exit(1)

    _p("=" * 70)
    _p(" META FIELD DUMP  (read-only — no writes to cls.db)")
    _p(f" Requesting fields: {FIELDS_TO_REQUEST}")
    _p(f" Sample size per form: {args.limit}")
    _p("=" * 70)

    all_results = {}   # project -> list of raw lead dicts

    for form in LEAD_FORMS:
        project = form["project"]
        _p(f"\n[{project}] Resolving page token for page {form['page_id']}...")
        try:
            page_token, page_name = resolve_page_token(
                form["page_id"], system_user_token, app_secret
            )
        except RuntimeError as e:
            _p(f"  [FAIL] {e}")
            continue
        _p(f"  [OK] Page token resolved for '{page_name}'")

        _p(f"[{project}] Pulling {args.limit} most recent leads from "
           f"form '{form['form_name']}'...")
        try:
            leads = dump_leads_for_form(form, page_token, app_secret, args.limit)
        except RuntimeError as e:
            _p(f"  [FAIL] {e}")
            _p("  If the error mentions a specific field name, that field "
               "may not be supported on this form/vertical — remove it "
               "from FIELDS_TO_REQUEST at the top of this script and "
               "re-run.")
            continue

        _p(f"  [OK] {len(leads)} lead(s) returned\n")
        all_results[project] = leads

        for i, raw_lead in enumerate(leads, 1):
            _p(f"  --- Lead {i} (leadgen_id={raw_lead.get('id')}) ---")
            _p(summarize_lead(raw_lead))
            _p("")

    # ── Save full raw JSON for reference ──
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(BASE_DIR, f"meta_field_dump_{timestamp}.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        _p(f"\n[OK] Full raw dump saved to: {output_path}")
    except Exception as e:
        _p(f"\n[WARN] Could not save JSON dump file: {e}")
        _p("       (console output above still has everything.)")

    _p("\nDone. Review the fields above/in the JSON file and let me know "
       "which ones matter for tracking going forward.")


if __name__ == "__main__":
    main()
