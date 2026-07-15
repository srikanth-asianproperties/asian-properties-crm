# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CLS ("Centralised Leads System") is a real-estate lead-management platform built for **Asian Properties**. It runs unattended on a single Windows laptop (Task Scheduler jobs) plus a small Cloudflare edge layer, backed by one SQLite database (`C:\CLS\cls.db`). There is no git repo here (`git-log.txt` is a stray export, not history) and no automated test suite — validation is done via each script's built-in `--selftest` / dry-run mode and manual review.

The system has three layers:
1. **Automation pipeline** (root `C:\CLS\*.py`) — scheduled jobs that pull leads from Meta and Sell.do, sync them into `cls.db`, and fire conversion events back to Meta.
2. **CRM web app** (`crm/`) — a Flask app where the sales team works leads directly (writes to `cls.db`).
3. **PWA / mobile dashboard** (`pwa/`) — a Cloudflare Pages site that reads a read-only JSON snapshot of `cls.db` via Workers KV, for phone access.

`cls_db.py` is the shared data-access layer imported by every Python component (`sys.path.insert(0, r"C:\CLS")` + `import cls_db`) — it is the single source of truth for schema, stage-transition rules, and business logic. Read its module docstring/changelog before touching schema or lead-lifecycle logic anywhere else in the codebase.

## Commands

There is no build step; everything runs as plain Python scripts against `cls.db`. Standard library + these third-party packages are used (installed globally, no root `requirements.txt`):
`requests`, `pandas`, `beautifulsoup4`, `python-dotenv`, `playwright` (+ `playwright install chromium`), `sib_api_v3_sdk` (Brevo).

**Always use `python -m pip`, never bare `pip`** — the Scripts folder is not on this machine's PATH, so a bare `pip` command fails immediately.

```
# CRM web app
cd crm
python -m pip install -r requirements.txt
python create_admin.py        # first-time: creates a login (users table starts empty)
python app.py                 # dev server -> http://127.0.0.1:5000
                               # set CRM_ENV=production in .env to serve via Waitress instead of Flask's dev server

# One-off DB migration/schema check
python migrate_db.py          # additive column migration, safe to re-run
python crm\schema_check.py

# Pipeline jobs — normally run by Windows Task Scheduler, but runnable manually:
python meta_leads_fetcher.py      # Job A
python selldo_to_cls.py           # Job B  — see "Never touch Job B" rule below
python cls_capi_firer.py          # Job C  (--force skips the Job B freshness gate)
python cls_email_drip.py          # Job D
python cleanup_comms_log.py       # Job D maintenance helper

# Supporting scripts
python cls_dashboard.py           # regenerate dashboard.html from cls.db
python cls_snapshot.py            # push JSON snapshot to Cloudflare KV (also: --selftest)
python cls_watchdog.py            # health check + Telegram/Slack-style alert digest
python cls_telegram_listener.py   # long-polling Telegram command bot (/stats /today /health /pending)
python cls_telecaller_report.py   # weekend Opportunity-stage report email
python cls_backup.py              # daily backup of C:\CLS to Google Drive via rclone
python setup_task_scheduler.py    # registers Job D in Windows Task Scheduler (run once, as Admin)

# Self-tests (each job's own offline sanity check; look for --selftest / SELFTEST in the file)
python cls_capi_firer.py --selftest   # style varies per script — check top-of-file docstring
```

Each job writes to its own `C:\CLS\*_log.txt` (e.g. `meta_leads_log.txt`, `selldo_cls_log.txt`, `cls_capi_log.txt`, `cls_drip_log.txt`, `cls_watchdog_log.txt`, `crm_app_log.txt`) — check these first when debugging a run instead of re-running blind.

## Architecture

### The A→B→C→D pipeline

Jobs run hourly (10:00–18:00) via Windows Task Scheduler and hand off through **completion flags** stored via `cls_db.set_flag()`/`get_flag()`/`is_flag_fresh()` (persisted in `cls_flags.json`), not direct chaining:

```
[Job A] meta_leads_fetcher.py   Pulls Meta Lead Ads leads -> cls.db (with leadgen_id), sets 'meta_fetch' flag
    |
    v
[Job B] selldo_to_cls.py        Waits for a fresh Job A flag; logs into Sell.do via Playwright, exports
    |                           CSV via Gmail polling, matches rows onto cls.db leads by phone/email,
    |                           writes current_stage. Sets 'selldo_sync' flag. NEVER MODIFIED — see rule below.
    v
[Job C] cls_capi_firer.py       Waits for a fresh Job B flag (15-min slack: B runs :10, C runs :25;
    |                           --force bypasses the gate). Fires stage-change events to Meta Conversions
    |                           API (CAPI) for match-quality-scored ad optimization. Calls
    |                           cls_dashboard.generate_dashboard() and cls_snapshot.push_snapshot() at
    |                           the end of every run (snapshot failures are always swallowed — must never
    |                           block CAPI firing).
    v
[Job D] cls_email_drip.py       Independent of the A-B-C flag chain (own 10:00/12:00/14:00/16:00/18:00
                                schedule via setup_task_scheduler.py). Sends staged nurture emails via
                                Brevo, syncs bounces, respects email_bounced/opted_out flags.
```

`cls_telecaller_report.py` (weekend cron) and `cls_watchdog.py`/`cls_telegram_listener.py` (monitoring) read `cls.db` but sit outside this chain.

Stage names and their legal transitions are defined once in `cls_db.STAGE_TRANSITIONS` (`Incoming → Prospect → Opportunity → Site Visited → Booked`, plus `Unqualified`/`Lost`/`Re Assigned` side-states) — both Sell.do's own rule engine and the CRM app's `change_lead_stage()` route enforce these same one-way rules. Do not add free-form stage changes; extend `STAGE_TRANSITIONS` instead.

### `cls_db.py` — shared foundation

Every job and the CRM app import this module the same way:
```python
BASE_DIR = r"C:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db
```
It owns: SQLite connection/schema init (self-healing additive `ALTER TABLE`s, never destructive), user auth (`create_user`/`verify_login`, password hashing), lead CRUD and stage/ownership logic, site-visit and follow-up scheduling, WhatsApp template CRUD, Meta-lead/Sell.do-lead upsert + phone/email matching (`norm_phone`, `norm_email`, `find_match`), CAPI event recording, email-drip queries, and the flag store used for pipeline gating. Read the top-of-file changelog before modifying schema or role/permission logic — it documents the reasoning behind non-obvious design decisions (e.g. why `role` is free-text with no CHECK constraint, why manager write access is deliberately NOT granted alongside its read access).

### CRM app (`crm/app.py`)

Flask app, single file, session-based auth via `login_required`/`admin_required` decorators. Three roles with a strict hierarchy: `admin` > `manager` > `salesperson` (`cls_db.CRM_ROLES`, `cls_db.OVERSIGHT_ROLES`). Visibility (who can *see* a lead) and write access (who can *change* a lead) are governed by two separate checks — do not conflate them when adding a role or a new view:
- **Read/visibility**: `cls_db.can_view_all_leads(role)` — admins and managers see every lead; salespeople see only their own (`owner_match_name`). Fails closed (unrecognized role → most-restricted view).
- **Write**: `_is_lead_owner_or_admin` / `_check_lead_ownership` in `app.py` — owner-or-admin only, unchanged by the manager role. A manager only writes to leads they personally own.

The app runs in **parallel-run mode** alongside Sell.do (by explicit design, not a migration bug) — writes made in the CRM do not yet replace Sell.do as the system of record; Job B's next sync can still overwrite `current_stage`/`lead_owner` from Sell.do. `CRM_ENV=production` in `.env` switches the session cookie to `Secure` and swaps the dev server for Waitress (see `run_production()`), intended to run as an unattended Windows service behind a Cloudflare Tunnel (never bind `CRM_HOST=0.0.0.0` in production — Cloudflare Tunnel connects over localhost).

### PWA (`pwa/`)

Static Cloudflare Pages site + two Pages Functions (`functions/api/snapshot.js`, `functions/_middleware.js`) that serve the JSON blob `cls_snapshot.py` pushes to Workers KV (binding `CLS_SNAPSHOT`). The PWA never touches `cls.db` directly — it only ever reads the last pushed snapshot, so a failed push just means a stale (not broken) view. Access is gated by Cloudflare Access in front of the Pages project, not by any app-level auth.

## Conventions worth knowing before editing

- **"Never discard" / "never fail silently"**: recurring design rules referenced throughout the job scripts' docstrings (e.g. Sell.do's export window is a fixed historical anchor, not a rolling window, specifically so old leads can't silently age out of sync; `cls_snapshot.py` swallows all its own errors so a KV outage can never block Job C). Preserve this posture when modifying pipeline code — prefer loud logging + safe skip over exceptions that could kill a scheduled job.
- **Flag-gated hand-offs, not direct calls**: jobs communicate readiness via `cls_db.set_flag`/`get_flag`/`is_flag_fresh`, checked with a deliberate time-slack buffer, not by importing and calling each other.
- **Config-not-code for roles/permissions**: new role behavior should extend `cls_db.CRM_ROLES`/`OVERSIGHT_ROLES`/`can_view_all_leads()` rather than adding scattered `role == "..."` checks in `app.py`. The same principle applies everywhere else in this codebase — lists, thresholds, and rules belong in constants/dicts (e.g. `STAGE_TRANSITIONS`, drip schedules, lead-score rules), not hardcoded conditionals.
- **Every script's module docstring is authoritative**: each file in this repo carries a detailed changelog and "why" section at the top (deployment steps, known edge cases, prior incidents that motivated a fix). Read it before changing that file — the reasoning for non-obvious decisions lives there, not in commit history (there is none).

## How Srikanth wants this codebase worked on

These rules apply to every change, not just the ones below where they're most obviously relevant. When in doubt, ask rather than assume.

- **Never touch Job B.** `selldo_to_cls.py` is off-limits regardless of context, framing, or how small or reasonable a change sounds. It's the most fragile component in the pipeline (Playwright scraper against Sell.do's UI) and the one thing that must not break during parallel-run. If a task seems to require changing it, stop and flag that instead of proceeding.
- **Architecture before code.** For anything structural — new tables, new roles, new routes, changed write-paths — lock the design and get explicit confirmation before writing any code. Present options with a comparison/risk table and a clear recommendation when more than one approach is reasonable.
- **Complete files, not diffs.** Deliver whole, runnable files with a version header and changelog comment at the top — never "change line X" instructions.
- **Verify before editing.** Read the live version of a file from disk immediately before editing it — never regenerate from a stale copy or from memory of an earlier session.
- **`cls_db.py` changes need an explicit before/after diff**, with an "additions only, nothing existing removed or modified" confirmation, before being considered done.
- **All SQLite access stays centralized in `cls_db.py`.** No other script opens the database directly.
- **Schema changes are self-healing migrations only** — `ALTER TABLE ... IF NOT EXISTS` / try-except patterns, safe to redeploy against the live DB. Never destructive.
- **Test against a throwaway SQLite DB before calling anything done** — for the CRM app, this means a Flask test-client integration test; for `cls_db.py` functions, a standalone script against a temp copy of the schema.
- **Guard every `print()` / stdout call.** `pythonw.exe` sets stdout to `None`, so unguarded prints crash silent background jobs. Use a logging helper that checks for `None` first.
- **UTF-8-safe logging** everywhere — this system handles Indian names/addresses with non-ASCII characters.
- **Paused code is commented as `# PAUSED — <reason>`, never deleted.**
- **Flag security implications proactively** whenever a change touches auth, passwords, roles, tokens, or `.env` — don't implement silently and mention it after the fact.
- **Flag DPDP Act obligations** — especially call-recording consent — before any recording feature goes live. This applies directly once v1.0 Telephony work starts.
- **Parallel-run is sacred.** Sell.do is never cut over or cancelled until the team has lived in the CRM in parallel for at least 3–4 weeks with clean, validated sync. Don't write code that assumes or hastens cutover.
- **Scope discipline.** If a request is ahead of the currently agreed version (v0.1 Viewer → v0.5 Writer → v1.0 Telephony+cutover → v1.5+ Strategic), say clearly which version it belongs to before building it. Don't silently expand scope, and don't hard-block the idea either — just name it and confirm before proceeding.
- **Simple over complex.** Prefer the solution touching the fewest files and using data already in `cls.db` over a more elaborate architecture.
