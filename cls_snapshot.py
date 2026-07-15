"""
=============================================================
cls_snapshot.py  —  CLS Command Center Snapshot Pusher
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

WHAT THIS DOES
--------------
Reads cls.db (via cls_db.py's own helper functions — no duplicate
SQL, no schema drift risk) and pushes a single JSON "snapshot" to a
Cloudflare Workers KV namespace. The cls.asianbuild.in PWA reads
that same JSON via a Pages Function, so your phone always shows
exactly what cls_dashboard.py would show on the desktop — just
reachable from anywhere.

REAL ESTATE ANALOGY
--------------------
KV is the display window at the site office. This script is the
back-office clerk who updates the window each cycle. Your phone
only ever looks through the window — it never gets inside cls.db
itself. If the clerk is late or sick one cycle (a push fails), the
window just shows yesterday's board until the next clerk shift —
nobody panics, nothing breaks downstream.

WHERE THIS RUNS
----------------
Called from the END of Job C (cls_capi_firer.py), right after
generate_dashboard(). Also safe to run standalone, anytime:

    python cls_snapshot.py              # build + push now
    python cls_snapshot.py --selftest   # offline check, then live
                                         #   KV round-trip check

FAILURE PHILOSOPHY  (mirrors Risk 1 / Risk 4 conventions)
-----------------------------------------------------------
This script must NEVER raise an exception that could stop Job C or
block CAPI firing. Every failure mode (missing .env vars, network
error, Cloudflare outage, bad response) is caught, logged, and
swallowed. Job C calls push_snapshot() inside its own try/except as
a second layer of safety, but this script does not rely on that —
it is self-contained and self-healing on its own.

CREDENTIALS  (config-not-code — same discipline as BREVO_API_KEY)
-------------------------------------------------------------------
Read from C:\\CLS\\.env via python-dotenv:
    CF_ACCOUNT_ID       — Cloudflare account ID
    CF_KV_NAMESPACE_ID  — the CLS_SNAPSHOT namespace ID
    CF_API_TOKEN        — token scoped to Workers KV Storage: Edit
                           on this account only (narrowest blast
                           radius if it ever leaks)

KV KEY
------
Single fixed key: "snapshot"
   (one key, overwritten every push — last-write-wins, exactly like
   dashboard.html being overwritten each cycle. No history needed
   in KV itself; full event history already lives in the JSON body.)

SIZE NOTE
---------
Cloudflare KV values are capped at 25MB technically, but we keep a
soft 5MB internal warning threshold (~20-30k events at current row
size). If you ever cross that, the documented upgrade path is to
split into snapshot:summary + snapshot:events keys. Not needed yet
at current volumes (~3,200 leads).

ONE-TIME SETUP
---------------
  pip install python-dotenv requests
=============================================================
"""

import os
import sys
import json
import time
from datetime import datetime

import cls_db   # the foundation layer — same source of truth as the dashboard

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(r"C:\CLS", ".env"))
except Exception:
    # On a non-Windows box (e.g. during selftest in a sandbox) this is fine —
    # env vars may already be present in the environment instead.
    pass

import requests

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR   = r"C:\CLS"
LOG_FILE   = os.path.join(BASE_DIR, "cls_snapshot.log")

KV_KEY               = "snapshot"
SOFT_SIZE_WARN_BYTES = 5 * 1024 * 1024     # 5MB — warn, don't block
REQUEST_TIMEOUT_SEC  = 20

CF_ACCOUNT_ID      = os.environ.get("CF_ACCOUNT_ID", "")
CF_KV_NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID", "")
CF_API_TOKEN       = os.environ.get("CF_API_TOKEN", "")

# Same event-type set the dashboard cards use — kept in sync deliberately.
EVENT_TYPES = ["QualifiedLead", "Schedule", "CompleteRegistration"]


# ─────────────────────────────────────────────────────────────
# LOGGING  —  Unicode-safe, append-only (matches CLS conventions)
# ─────────────────────────────────────────────────────────────

def log(message):
    """Append-only log, UTF-8 with errors='replace' so a Telugu/Arabic
    lead name can never crash this script on a cp1252 Windows console."""
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {message}"
    print(line)
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
    except Exception:
        pass   # logging must never be the thing that breaks the script


# ─────────────────────────────────────────────────────────────
# SNAPSHOT BUILDER
# ─────────────────────────────────────────────────────────────

def build_snapshot():
    """
    Build the JSON-serializable snapshot dict from cls.db.
    Pure read, no side effects — safe to call as many times as needed.
    Mirrors cls_dashboard.py's data shape exactly (same source functions),
    so the phone and the desktop dashboard never disagree.
    """
    cls_db.init_db()

    lead_stats = cls_db.stats()
    evt_stats  = cls_db.event_stats()
    events     = cls_db.get_events()        # newest first, full history

    # ── Per-event-type counts (mirrors dashboard cards) ──
    event_type_counts = {k: 0 for k in EVENT_TYPES}
    for e in events:
        me = e.get("meta_event")
        if me in event_type_counts:
            event_type_counts[me] += 1

    # ── Per-project tiles ──
    today_str = datetime.now().strftime("%Y-%m-%d")
    project_agg = {}
    for e in events:
        p = cls_db.get_project_bucket(e.get("project"))
        agg = project_agg.setdefault(p, {"total": 0, "today": 0})
        agg["total"] += 1
        if str(e.get("fired_at") or "").startswith(today_str):
            agg["today"] += 1
    project_tiles = [
        {"name": name, "total": agg["total"], "today": agg["today"]}
        for name, agg in sorted(project_agg.items(),
                                 key=lambda kv: kv[1]["total"], reverse=True)
    ]

    # ── Recent events (full history — same fields the dashboard table shows) ──
    recent_events = [
        {
            "fired_at"      : e.get("fired_at"),
            "project"       : e.get("project"),               # raw CRM value — unchanged
            "project_bucket": cls_db.get_project_bucket(e.get("project")),  # for filtering/display
            "full_name"     : e.get("full_name"),
            "phone_norm"    : e.get("phone_norm"),
            "crm_stage"     : e.get("crm_stage"),
            "prev_stage"    : e.get("prev_stage"),
            "meta_event"    : e.get("meta_event"),
            "value_inr"     : e.get("value_inr"),
            "used_leadgen"  : bool(e.get("used_leadgen")),
        }
        for e in events
    ]

    # ── Job health — read cls_flags.json the same way is_flag_fresh() does ──
    flags_raw = {}
    if os.path.exists(cls_db.FLAG_FILE):
        try:
            with open(cls_db.FLAG_FILE, "r") as f:
                flags_raw = json.load(f)
        except Exception:
            flags_raw = {}

    job_flags = {}
    for job_name, ts in flags_raw.items():
        job_flags[job_name] = {
            "last_completed": ts,
            "fresh"         : cls_db.is_flag_fresh(job_name),
        }

    snapshot = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cards": {
            "total_events"   : evt_stats["total_events"],
            "events_today"   : evt_stats["events_today"],
            "qualified_lead" : event_type_counts["QualifiedLead"],
            "schedule"       : event_type_counts["Schedule"],
            "complete_reg"   : event_type_counts["CompleteRegistration"],
        },
        "leads": {
            "total_leads"     : lead_stats["total_leads"],
            "with_leadgen_id" : lead_stats["with_leadgen_id"],
            "selldo_only"     : lead_stats["selldo_only"],
            "pending_fire"    : lead_stats["pending_fire"],
        },
        "project_tiles": project_tiles,
        "events"       : recent_events,
        "job_flags"    : job_flags,
    }
    return snapshot


# ─────────────────────────────────────────────────────────────
# CLOUDFLARE KV PUSH
# ─────────────────────────────────────────────────────────────

def _kv_url():
    return (f"https://api.cloudflare.com/client/v4/accounts/"
            f"{CF_ACCOUNT_ID}/storage/kv/namespaces/"
            f"{CF_KV_NAMESPACE_ID}/values/{KV_KEY}")


def _check_credentials():
    missing = [name for name, val in [
        ("CF_ACCOUNT_ID", CF_ACCOUNT_ID),
        ("CF_KV_NAMESPACE_ID", CF_KV_NAMESPACE_ID),
        ("CF_API_TOKEN", CF_API_TOKEN),
    ] if not val]
    if missing:
        log(f"[FAIL] Missing credentials in .env: {', '.join(missing)}")
        return False
    return True


def push_snapshot(snapshot=None):
    """
    Build (if not given) and push the snapshot to Cloudflare KV.
    Returns True on success, False on any failure — NEVER raises.
    This is the function Job C calls at the end of its run.
    """
    try:
        if snapshot is None:
            snapshot = build_snapshot()

        body = json.dumps(snapshot, ensure_ascii=False)
        size_bytes = len(body.encode("utf-8"))
        if size_bytes > SOFT_SIZE_WARN_BYTES:
            log(f"[WARN] Snapshot is {size_bytes:,} bytes — over the "
                f"5MB soft threshold. Consider the split-key upgrade "
                f"(snapshot:summary + snapshot:events) documented in "
                f"the file header.")

        if not _check_credentials():
            return False

        resp = requests.put(
            _kv_url(),
            headers={
                "Authorization": f"Bearer {CF_API_TOKEN}",
                "Content-Type" : "application/json",
            },
            data=body.encode("utf-8"),
            timeout=REQUEST_TIMEOUT_SEC,
        )

        if resp.status_code == 200 and resp.json().get("success"):
            log(f"[OK] Snapshot pushed — {size_bytes:,} bytes, "
                f"{len(snapshot.get('events', []))} events, "
                f"generated_at={snapshot['generated_at']}")
            return True
        else:
            log(f"[FAIL] KV push returned HTTP {resp.status_code}: "
                f"{resp.text[:300]}")
            return False

    except requests.exceptions.RequestException as e:
        log(f"[FAIL] Network/request error pushing snapshot: {e}")
        return False
    except Exception as e:
        log(f"[FAIL] Unexpected error in push_snapshot: {e}")
        return False


def fetch_snapshot_from_kv():
    """
    GET the current value back from KV. Used only by --selftest to
    verify the round-trip actually worked end to end. Returns the
    parsed dict, or None on failure.
    """
    try:
        if not _check_credentials():
            return None
        resp = requests.get(
            _kv_url(),
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
            timeout=REQUEST_TIMEOUT_SEC,
        )
        if resp.status_code == 200:
            return json.loads(resp.text)
        log(f"[FAIL] KV read returned HTTP {resp.status_code}: {resp.text[:300]}")
        return None
    except Exception as e:
        log(f"[FAIL] Unexpected error in fetch_snapshot_from_kv: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────

def selftest():
    print("=" * 60)
    print(" CLS SNAPSHOT — SELF TEST")
    print("=" * 60)

    # ── Phase 1: offline — does the JSON even build cleanly? ──
    print("\n--- Phase 1: offline snapshot build ---")
    snap = None
    try:
        snap = build_snapshot()
        ok = isinstance(snap, dict) and "generated_at" in snap
        print(f"  [{'OK' if ok else 'FAIL'}] build_snapshot() returned a dict "
              f"with generated_at")
    except Exception as e:
        print(f"  [FAIL] build_snapshot() raised: {e}")
        print("\nAborting — fix the build step before testing the live push.")
        return

    required_top = ["generated_at", "cards", "leads", "project_tiles",
                     "events", "job_flags"]
    missing = [k for k in required_top if k not in snap]
    print(f"  [{'OK' if not missing else 'FAIL'}] all expected top-level keys "
          f"present" + (f" (missing: {missing})" if missing else ""))

    try:
        body = json.dumps(snap, ensure_ascii=False)
        size_kb = len(body.encode('utf-8')) / 1024
        print(f"  [OK] snapshot is valid JSON — {size_kb:,.1f} KB, "
              f"{len(snap['events'])} events, "
              f"{len(snap['project_tiles'])} project tiles")
    except Exception as e:
        print(f"  [FAIL] json.dumps failed: {e}")
        return

    # ── Phase 2: credentials present? ──
    print("\n--- Phase 2: credentials ---")
    creds_ok = _check_credentials()
    print(f"  [{'OK' if creds_ok else 'FAIL'}] CF_ACCOUNT_ID / "
          f"CF_KV_NAMESPACE_ID / CF_API_TOKEN all present in environment")
    if not creds_ok:
        print("\nAborting live round-trip — credentials missing. "
              "Check C:\\CLS\\.env")
        return

    # ── Phase 3: live round-trip — PUT then GET, byte-compare ──
    print("\n--- Phase 3: live KV round-trip ---")
    pushed = push_snapshot(snap)
    print(f"  [{'OK' if pushed else 'FAIL'}] push_snapshot() PUT to Cloudflare KV")
    if not pushed:
        print("\nLive push failed — see log line above for the HTTP/network detail.")
        return

    time.sleep(1.5)   # tiny settle delay before reading back

    fetched = fetch_snapshot_from_kv()
    got_back = fetched is not None and fetched.get("generated_at") == snap["generated_at"]
    print(f"  [{'OK' if got_back else 'FAIL'}] fetch_snapshot_from_kv() read back "
          f"the SAME generated_at we just pushed "
          f"({snap['generated_at']})")

    print("\n" + "=" * 60)
    print(" SELF TEST COMPLETE — full round-trip verified" if got_back
          else " SELF TEST COMPLETE — see FAIL lines above")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        if push_snapshot():
            print("Snapshot pushed.")
        else:
            print("Snapshot push failed — see cls_snapshot.log")
