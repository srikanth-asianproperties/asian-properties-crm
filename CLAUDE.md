# CLAUDE.md
<!--
Version: 1.3
Changelog:
  v1.0 (baseline, pre-existing) — original CLAUDE.md content, no version tracking.
  v1.1 (2026-07-28) — added mandatory "Session Closeout" section (Srikanth-requested):
                       every response that creates/edits a file must end with a
                       files-to-reupload list, plain-English verification steps,
                       a flags block (security/DPDP/scope/Job B/scheduler), and a
                       Resume-from-here checkpoint. Added version/changelog header
                       to this file itself, matching the convention already used
                       across every other script in this repo.
  v1.2 (2026-08-03) — updated all BASE_DIR/CLS_DB_PATH/live-path references from
                       C:\CLS to D:\CLS to reflect the completed drive migration;
                       added a new "The C:\CLS -> D:\CLS drive migration" section
                       documenting what moved, the C:\CLS rollback-backup convention,
                       and the git-history divergence between the two copies.
                       Documentation-only change, no behavior/process changes.
  v1.3 (2026-08-18) — Job B (`selldo_to_cls.py`) formally retired: Task Scheduler
                       entry removed, Sell.do subscription cancelled. Removed the
                       "Never touch Job B" rule and every reference presenting Job B
                       as an active/live pipeline job (Commands section, pipeline
                       diagram header, Session Closeout flags block), replacing them
                       with brief factual retirement notes. Historical/explanatory
                       content about why the CLS1/CLS2 split happened and how Job B
                       worked while it was live is preserved, not deleted.
-->

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CLS ("Centralised Leads System") is a real-estate lead-management platform built for **Asian Properties**. It runs unattended on a single Windows laptop (Task Scheduler jobs) plus a small Cloudflare edge layer. As of **2026-07-26** it is backed by **two** SQLite databases, `D:\CLS\CLS1.db` and `D:\CLS\CLS2.db` (previously a single `cls.db` — see "The CLS1/CLS2 database split" below). There is no git repo here (`git-log.txt` is a stray export, not history) and no automated test suite — validation is done via each script's built-in `--selftest` / dry-run mode and manual review.

The system has three layers:
1. **Automation pipeline** (root `D:\CLS\*.py`) — scheduled jobs that pull leads from Meta and Sell.do, sync them into CLS1.db/CLS2.db, and fire conversion events back to Meta.
2. **CRM web app** (`crm/`) — a Flask app where the sales team works leads directly (writes to CLS1.db).
3. **PWA / mobile dashboard** (`pwa/`) — a Cloudflare Pages site that reads a read-only JSON snapshot (sourced from CLS2.db, the DB Job C reads from) via Workers KV, for phone access.

`cls_db.py` is the shared data-access layer imported by every Python component (`sys.path.insert(0, r"D:\CLS")` + `import cls_db`) — it is the single source of truth for schema, stage-transition rules, business logic, **and which of the two databases a given process talks to** (via `CLS_DB_PATH`, see below). Read its module docstring/changelog before touching schema or lead-lifecycle logic anywhere else in the codebase.

## The CLS1/CLS2 database split (since 2026-07-26)

The original single `cls.db` was forked into two databases that now serve different roles:

- **CLS1.db** — "our own CRM" database. Fed by **Job A** (`meta_leads_fetcher.py`) and the **CRM app** (`crm/app.py`). This is the database the sales team's own CRM writes to and reads from.
- **CLS2.db** — the Sell.do mirror. Fed **only** by **Job B** (`selldo_to_cls.py`).
- **Job C** (`cls_capi_firer.py`) and **Job D** (`cls_email_drip.py`) both read/write **CLS2.db** during parallel-run. CAPI fires against real ad spend, so it deliberately stays on the Sell.do-trusted source rather than CLS1 — moving Job C/D onto CLS1 is a future decision that has **not** been made yet, contingent on parallel-run proving CLS1 reliable.

**Job B retired 2026-08-18**: Job B (`selldo_to_cls.py`) was formally retired — its Task Scheduler entry was removed and the Sell.do subscription cancelled. It no longer runs and no longer writes to CLS2.db. The description above of Job B's original role is kept for historical/reference context (it explains why CLS2.db exists and how the split worked while Job B was live) — it does not describe current behavior. Job C's dependency on Job B's `selldo_sync` flag (see the pipeline diagram below) is now permanently stale and has not yet been re-evaluated; treat that as an open follow-up, not a bug fixed by this note.

**How the target DB is chosen**: `cls_db.py` reads the `CLS_DB_PATH` environment variable once at import time (`DB_FILE = os.environ.get("CLS_DB_PATH", ...\CLS1.db default...)`, `cls_db.py:1087`). This **must** be a real Windows/OS environment variable — **never** a line in `.env`. Reason: `crm/app.py` does `import cls_db` (which reads `os.environ` immediately) before it loads `.env` via `dotenv_values()` later in the file, and in any case `.env` values loaded via `dotenv_values()`/similar are read into a local dict, not written into `os.environ` — so a `.env`-only setting would never be seen by `cls_db.py`.

**How it's actually set in practice**: small `.bat` wrapper files set `CLS_DB_PATH` before invoking Python, and Task Scheduler's Program/script field points at the wrapper instead of `python.exe`/`pythonw.exe` directly:

```
run_selldo_to_cls.bat        set CLS_DB_PATH=D:\CLS\CLS2.db   (Job B — RETIRED 2026-08-18, kept for reference only)
run_cls_capi_firer.bat       set CLS_DB_PATH=D:\CLS\CLS2.db   (Job C)
run_cls_email_drip.bat       set CLS_DB_PATH=D:\CLS\CLS2.db   (Job D)
run_cls_watchdog.bat         set CLS_DB_PATH=D:\CLS\CLS2.db
run_cls_telegram_listener.bat set CLS_DB_PATH=D:\CLS\CLS2.db
run_app.bat                  set CLS_DB_PATH=D:\CLS\CLS1.db   (CRM app)
```
Job A (`meta_leads_fetcher.py`) has **no** wrapper — it relies on `cls_db.py`'s default (CLS1.db), which is correct for Job A and not accidental.

**Documented gotcha (real incident, 2026-07-26)**: a Task Scheduler task pointed directly at `python.exe`/a script — bypassing the `.bat` wrapper — silently falls back to the `CLS_DB_PATH` default (CLS1.db) instead of erroring. This is exactly what happened the day of the split: Job A and Job C briefly ran against the wrong database until their Task Scheduler entries were repointed at the correct wrapper `.bat` files. When adding or auditing a scheduled task, always confirm the Program/script field is the wrapper `.bat`, not the interpreter/script directly.

**The flag file is unaffected by the split.** `cls_flags.json` (`cls_db.set_flag`/`get_flag`/`is_flag_fresh`) is a single shared file on disk, not stored in either database — so flag-based hand-offs between jobs work exactly as before regardless of which DB each process targets.

**Rollback point**: the original `cls.db` was preserved as `cls.db.pre_split_backup` (not deleted). Keep it for at least several weeks from 2026-07-26 before considering removal.

## The C:\CLS → D:\CLS drive migration (2026-08-03)

**Date**: 2026-08-03. **D:\CLS is now the live project.** `C:\CLS` is a frozen backup from this migration — do not read from or write to anything under `C:\CLS` unless explicitly asked, e.g. for a rollback comparison.

**What moved**: all CLS Python files, all `.bat` wrappers, both databases (`CLS1.db`, `CLS2.db`), and 8 Task Scheduler entries — everything now lives on `D:\CLS`. `BASE_DIR` and every `.bat` wrapper's `CLS_DB_PATH` documented elsewhere in this file reflect the new `D:\CLS` location.

**C:\CLS is preserved, not deleted** — same "keep for a few weeks" convention already used for `cls.db.pre_split_backup`: retain `C:\CLS` as a frozen rollback point for at least several weeks from 2026-08-03 before considering removal.

**Git note**: `D:\CLS`'s git history diverged from `C:\CLS`'s at the moment of the robocopy performed for this migration. Commits made after that point — specifically the `BASE_DIR`-migration commits — exist **only** in `D:\CLS`'s history, not in `C:\CLS`'s. `C:\CLS`'s git log is frozen at the pre-migration state; do not treat it as a live or authoritative history going forward.

## Commands

There is no build step; everything runs as plain Python scripts against CLS1.db/CLS2.db (selected via `CLS_DB_PATH` — see above). Standard library + these third-party packages are used (installed globally, no root `requirements.txt`):
`requests`, `pandas`, `beautifulsoup4`, `python-dotenv`, `playwright` (+ `playwright install chromium`), `sib_api_v3_sdk` (Brevo).

**Always use `python -m pip`, never bare `pip`** — the Scripts folder is not on this machine's PATH, so a bare `pip` command fails immediately.

```
# CRM web app (targets CLS1.db)
cd crm
python -m pip install -r requirements.txt
python create_admin.py        # first-time: creates a login (users table starts empty)
python app.py                 # dev server -> http://127.0.0.1:5000
                               # set CRM_ENV=production in .env to serve via Waitress instead of Flask's dev server
                               # in production, launch via ..\run_app.bat, not `python app.py` directly, so CLS_DB_PATH is set

# One-off DB migration/schema check
python migrate_db.py                # additive column migration, safe to re-run
python crm\schema_check.py           # checks CLS1.db by default
python crm\schema_check.py CLS2.db   # or pass a filename to check CLS2.db instead

# Pipeline jobs — normally run by Windows Task Scheduler via the .bat wrappers below, but runnable manually:
python meta_leads_fetcher.py      # Job A  -> CLS1.db (default, no wrapper needed)
# Job B (selldo_to_cls.py) — RETIRED 2026-08-18. Task Scheduler entry removed, Sell.do
# subscription cancelled. No longer part of the live pipeline; do not schedule or run it.
python cls_capi_firer.py          # Job C  -> CLS2.db (via run_cls_capi_firer.bat) (--force skips the Job B freshness gate, now permanently stale since Job B's retirement — see Architecture section)
python cls_email_drip.py          # Job D  -> CLS2.db (via run_cls_email_drip.bat)
python cleanup_comms_log.py       # Job D maintenance helper

# Supporting scripts
python cls_dashboard.py           # regenerate dashboard.html
python cls_snapshot.py            # push JSON snapshot to Cloudflare KV (also: --selftest)
python cls_watchdog.py            # health check + Telegram/Slack-style alert digest (via run_cls_watchdog.bat -> CLS2.db)
python cls_telegram_listener.py   # long-polling Telegram command bot (/stats /today /health /pending) (via run_cls_telegram_listener.bat -> CLS2.db)
python cls_telecaller_report.py   # weekend Opportunity-stage report email
python cls_backup.py              # daily backup of D:\CLS to Google Drive via rclone
python setup_task_scheduler.py    # registers Job D in Windows Task Scheduler (run once, as Admin)
python cls_parallel_diff.py       # compares CLS1.db vs CLS2.db directly -> parallel_diff_report.txt (primary parallel-run health tool, see below)

# Self-tests (each job's own offline sanity check; look for --selftest / SELFTEST in the file)
python cls_capi_firer.py --selftest   # style varies per script — check top-of-file docstring
```

Each job writes to its own `D:\CLS\*_log.txt` (e.g. `meta_leads_log.txt`, `selldo_cls_log.txt`, `cls_capi_log.txt`, `cls_drip_log.txt`, `cls_watchdog_log.txt`, `crm_app_log.txt`) — check these first when debugging a run instead of re-running blind. See also `job_results.txt` below for a quick one-line-per-run status check across all jobs.

## Architecture

### The pipeline (Job B retired 2026-08-18 — see note below)

Jobs run hourly (10:00–18:00) via Windows Task Scheduler and hand off through **completion flags** stored via `cls_db.set_flag()`/`get_flag()`/`is_flag_fresh()` (persisted in `cls_flags.json`, a single shared file unaffected by the CLS1/CLS2 split), not direct chaining.

**Job B (`selldo_to_cls.py`) was formally retired 2026-08-18** — its Task Scheduler entry was removed and the Sell.do subscription cancelled. It no longer runs and no longer sets the `selldo_sync` flag. The diagram below (originally titled "The A→B→C→D pipeline") is kept as historical/reference documentation of how the pipeline worked while Job B was live, including why the CLS2.db split existed and how Job B fed it — it does not describe the current live pipeline. Job C's wait on a fresh `selldo_sync` flag is a known stale dependency left over from Job B's retirement and has not yet been re-evaluated; that's an open follow-up, not something this documentation update fixes.

```
[Job A] meta_leads_fetcher.py   Pulls Meta Lead Ads leads -> CLS1.db (with leadgen_id), sets 'meta_fetch' flag
    |
    v
[Job B] selldo_to_cls.py        RETIRED 2026-08-18 — historical description only, does not run anymore.
    |                           Logged into Sell.do via Playwright, exported CSV via Gmail polling, matched
    |                           rows onto CLS2.db leads by phone/email, wrote current_stage into CLS2.db.
    |                           Set 'selldo_sync' flag.
    |                           Its former gate on Job A's 'meta_fetch' flag was PAUSED (commented out,
    |                           not deleted) before retirement — CLS2 had become a self-contained Sell.do
    |                           mirror that no longer depended on Job A's output. See "database split"
    |                           section above.
    v
[Job C] cls_capi_firer.py       Waits for a fresh Job B 'selldo_sync' flag (15-min slack: B ran :10, C runs
    |                           :25; --force bypasses the gate) — this wait is now permanently stale since
    |                           Job B's retirement and needs review. Job C still reads CLS2.db. Fires
    |                           stage-change events to Meta Conversions API (CAPI) for match-quality-scored
    |                           ad optimization. Calls cls_dashboard.generate_dashboard() and
    |                           cls_snapshot.push_snapshot() at the end of every run (snapshot failures are
    |                           always swallowed — must never block CAPI firing).
    v
[Job D] cls_email_drip.py       Independent of the A-B-C flag chain (own 10:00/12:00/14:00/16:00/18:00
                                schedule via setup_task_scheduler.py). Reads/writes CLS2.db. Sends staged
                                nurture emails via Brevo, syncs bounces, respects email_bounced/opted_out flags.
```

`cls_telecaller_report.py` (weekend cron) and `cls_watchdog.py`/`cls_telegram_listener.py` (monitoring, both targeting CLS2.db via their `.bat` wrappers) read their target database but sit outside this chain.

Stage names and their legal transitions are defined once in `cls_db.STAGE_TRANSITIONS` (`Incoming → Prospect → Opportunity → Site Visited → Booked`, plus `Unqualified`/`Lost`/`Re Assigned` side-states) — both Sell.do's own rule engine and the CRM app's `change_lead_stage()` route enforce these same one-way rules. Do not add free-form stage changes; extend `STAGE_TRANSITIONS` instead.

### `cls_db.py` — shared foundation

Every job and the CRM app import this module the same way:
```python
BASE_DIR = r"D:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db
```
It owns: SQLite connection/schema init (self-healing additive `ALTER TABLE`s, never destructive), the `CLS_DB_PATH`-driven `DB_FILE` target (see database-split section above), user auth (`create_user`/`verify_login`, password hashing), lead CRUD and stage/ownership logic, site-visit and follow-up scheduling, WhatsApp template CRUD, Meta-lead/Sell.do-lead upsert + phone/email matching (`norm_phone`, `norm_email`, `find_match`), CAPI event recording, email-drip queries, the flag store used for pipeline gating, `write_job_result()` (see below), and `get_leads_snapshot(db_path)` — the **one** function in this module that opens a database file other than its own `DB_FILE`, narrowly scoped to `cls_parallel_diff.py`'s cross-database comparison and never used by any job or the CRM app during normal operation. Read the top-of-file changelog before modifying schema or role/permission logic — it documents the reasoning behind non-obvious design decisions (e.g. why `role` is free-text with no CHECK constraint, why manager write access is deliberately NOT granted alongside its read access, why `DB_FILE` is config-driven rather than hardcoded).

### CRM app (`crm/app.py`)

Flask app, single file, session-based auth via `login_required`/`admin_required` decorators. Targets **CLS1.db** (via `run_app.bat` setting `CLS_DB_PATH`). Three roles with a strict hierarchy: `admin` > `manager` > `salesperson` (`cls_db.CRM_ROLES`, `cls_db.OVERSIGHT_ROLES`). Visibility (who can *see* a lead) and write access (who can *change* a lead) are governed by two separate checks — do not conflate them when adding a role or a new view:
- **Read/visibility**: `cls_db.can_view_all_leads(role)` — admins and managers see every lead; salespeople see only their own (`owner_match_name`). Fails closed (unrecognized role → most-restricted view).
- **Write**: `_is_lead_owner_or_admin` / `_check_lead_ownership` in `app.py` — owner-or-admin only, unchanged by the manager role. A manager only writes to leads they personally own.

The app runs in **parallel-run mode** alongside Sell.do (by explicit design, not a migration bug) — CLS1 (fed by the CRM app + Job A) and CLS2 (fed historically by Job B/Sell.do, until Job B's retirement 2026-08-18 — see Architecture section) are compared via `cls_parallel_diff.py` (see below), not reconciled automatically; CLS1 does not yet replace Sell.do/CLS2 as the system of record for CAPI/drip. `CRM_ENV=production` in `.env` switches the session cookie to `Secure` and swaps the dev server for Waitress (see `run_production()`), intended to run as an unattended Windows service behind a Cloudflare Tunnel (never bind `CRM_HOST=0.0.0.0` in production — Cloudflare Tunnel connects over localhost).

### PWA (`pwa/`)

Static Cloudflare Pages site + two Pages Functions (`functions/api/snapshot.js`, `functions/_middleware.js`) that serve the JSON blob `cls_snapshot.py` pushes to Workers KV (binding `CLS_SNAPSHOT`), sourced from whichever DB Job C targets (CLS2.db during parallel-run). The PWA never touches either database directly — it only ever reads the last pushed snapshot, so a failed push just means a stale (not broken) view. Access is gated by Cloudflare Access in front of the Pages project, not by any app-level auth.

## Parallel-run health checking: `cls_parallel_diff.py`

The primary tool for judging parallel-run health, replacing the old manual "eyeball 5-10 leads" approach. Compares **CLS1.db** and **CLS2.db** directly — hardcoded to those two files regardless of any process's `CLS_DB_PATH` — and writes a full report to `parallel_diff_report.txt`, overwritten each run.

Leads are matched between the two databases by **`phone_norm`/`email_norm`, not `cls_id`**: Job A gives a lead one `cls_id` in CLS1, but Job B independently creates its own row for the same person in CLS2 (CLS2 never inherits Job A's `cls_id`), so `cls_id` cannot be used as a join key across the two databases.

Three output sections, each with full lead detail (not just counts):
1. **Stage differs** — matched leads where `current_stage` disagrees between CLS1 and CLS2.
2. **Not yet in your CRM** — in CLS2 (Sell.do) but no match in CLS1 (e.g. walk-ins/referrals never entered into the new CRM).
3. **Not yet in Sell.do** — in CLS1 but no match in CLS2 — usually **expected/benign** (brand-new Meta leads Job A just pulled that Sell.do's own integration hasn't ingested yet).

Run manually (`python cls_parallel_diff.py`); not part of the scheduled A-D chain.

**Deprecated: `cls_parallel_export.py`** — superseded by `cls_parallel_diff.py`. It compared `activity_log` against `current_stage` within a single database, a comparison that stopped making sense once Job B stopped writing to CLS1. Do not use it as a reference for future work.

## Job result logging: `write_job_result()`

Every active job (`meta_leads_fetcher.py`, `cls_capi_firer.py`, `cls_email_drip.py`) calls `cls_db.write_job_result(job_name, success, summary)` at each of its return points, appending one plain-English line (`[timestamp] Job Name: SUCCESS/FAILED — summary`) to `D:\CLS\job_results.txt`. This is the quick human-glance status check across all jobs at once — separate from, and much shorter than, each job's own detailed `*_log.txt` file. (`selldo_to_cls.py` also called this while it was live, before its 2026-08-18 retirement — see Architecture section.)

## Historical migration tooling: `cls_db_fork.py`

One-time script used to perform the CLS1/CLS2 split on 2026-07-26: WAL-checkpoints the original `cls.db`, copies it to `CLS1.db` and `CLS2.db`, then renames the original to `cls.db.pre_split_backup`. Refuses to run if `CLS1.db`/`CLS2.db` already exist. Kept for historical/audit reference only — it is **not** part of ongoing operations and should not be run again.

## Future direction: Native Android APK (not PWA/TWA)

The end-plan for team-facing CRM access is a TRUE NATIVE Android APK —
an installable file sent directly to the team (not published to Play
Store, not a PWA-wrapper/TWA). Reasons: native app feel, native call
log / call recording auto-fetch access (READ_CALL_LOG permission),
and future ad-hoc native features not achievable in a browser context.

Implication for v1.0 Telephony: this likely REPLACES the originally-
planned rclone + Google Drive bridge and per-device OEM recording
folder matching, rather than coexisting with it. Do not build the
rclone/Drive bridge without re-confirming this with Srikanth first —
the 9 open Telephony architecture decisions need to be revisited
against "native app has direct call log access" before any of them
are locked.

Implication for auth: a native app cannot use Flask's session-cookie
login as-is. Moving to this will require token-based auth (app logs
in once, gets a token, sends it in a header on every request) and a
JSON API layer alongside (or replacing, for native clients) today's
HTML routes. This is real v1.0-scale scope — do not treat it as a
small addition to the current PWA.

Note: the User Activity Log (user_sessions / user_action_log,
cls_db.py v2.21+) is server-side and auth-mechanism-agnostic — it
will continue working unchanged once auth moves to tokens; only the
lookup of session_row_id needs to shift from session cookie to token.

## Conventions worth knowing before editing

- **"Never discard" / "never fail silently"**: recurring design rules referenced throughout the job scripts' docstrings (e.g. Sell.do's export window is a fixed historical anchor, not a rolling window, specifically so old leads can't silently age out of sync; `cls_snapshot.py` swallows all its own errors so a KV outage can never block Job C). Preserve this posture when modifying pipeline code — prefer loud logging + safe skip over exceptions that could kill a scheduled job.
- **Flag-gated hand-offs, not direct calls**: jobs communicate readiness via `cls_db.set_flag`/`get_flag`/`is_flag_fresh`, checked with a deliberate time-slack buffer, not by importing and calling each other. This is unaffected by the CLS1/CLS2 split — the flag file is shared regardless of which DB a process targets.
- **Config-not-code for roles/permissions/DB targets**: new role behavior should extend `cls_db.CRM_ROLES`/`OVERSIGHT_ROLES`/`can_view_all_leads()` rather than adding scattered `role == "..."` checks in `app.py`. The same principle applies everywhere else in this codebase — lists, thresholds, and rules belong in constants/dicts (e.g. `STAGE_TRANSITIONS`, drip schedules, lead-score rules), not hardcoded conditionals. The CLS_DB_PATH mechanism follows the same principle: which database a process uses is an environment setting, not an `if`/`else` branch in code.
- **Every script's module docstring is authoritative**: each file in this repo carries a detailed changelog and "why" section at the top (deployment steps, known edge cases, prior incidents that motivated a fix). Read it before changing that file — the reasoning for non-obvious decisions lives there, not in commit history (there is none).

## How Srikanth wants this codebase worked on

These rules apply to every change, not just the ones below where they're most obviously relevant. When in doubt, ask rather than assume.

- **Job B (`selldo_to_cls.py`) was retired 2026-08-18** — Task Scheduler entry removed, Sell.do subscription cancelled. Historical/reference only; it is no longer part of the live pipeline and does not run. The "never touch it live" concern that applied while it was active no longer applies in the same way, but treat any proposed change to it the same as touching dead/archival code: confirm with Srikanth why it needs to change before editing.
- **Architecture before code.** For anything structural — new tables, new roles, new routes, changed write-paths — lock the design and get explicit confirmation before writing any code. Present options with a comparison/risk table and a clear recommendation when more than one approach is reasonable.
- **Complete files, not diffs.** Deliver whole, runnable files with a version header and changelog comment at the top — never "change line X" instructions.
- **Verify before editing.** Read the live version of a file from disk immediately before editing it — never regenerate from a stale copy or from memory of an earlier session.
- **`cls_db.py` changes need an explicit before/after diff**, with an "additions only, nothing existing removed or modified" confirmation, before being considered done.
- **All SQLite access stays centralized in `cls_db.py`.** No other script opens the database directly. (The sole documented exception is `cls_db.get_leads_snapshot(db_path)`, added for `cls_parallel_diff.py`'s cross-database comparison — still centralized in `cls_db.py`, just parameterized on which file to open.)
- **Schema changes are self-healing migrations only** — `ALTER TABLE ... IF NOT EXISTS` / try-except patterns, safe to redeploy against the live DB. Never destructive.
- **Test against a throwaway SQLite DB before calling anything done** — for the CRM app, this means a Flask test-client integration test; for `cls_db.py` functions, a standalone script against a temp copy of the schema.
- **Guard every `print()` / stdout call.** `pythonw.exe` sets stdout to `None`, so unguarded prints crash silent background jobs. Use a logging helper that checks for `None` first.
- **UTF-8-safe logging** everywhere — this system handles Indian names/addresses with non-ASCII characters.
- **Paused code is commented as `# PAUSED — <reason>`, never deleted.**
- **Flag security implications proactively** whenever a change touches auth, passwords, roles, tokens, or `.env` — don't implement silently and mention it after the fact.
- **Flag DPDP Act obligations** — especially call-recording consent — before any recording feature goes live. This applies directly once v1.0 Telephony work starts.
- **Parallel-run is sacred.** Sell.do is never cut over or cancelled until the team has lived in the CRM in parallel for at least 3–4 weeks with clean, validated sync. Don't write code that assumes or hastens cutover. Use `cls_parallel_diff.py` output, not ad-hoc spot checks, to judge parallel-run health.
- **Scope discipline.** If a request is ahead of the currently agreed version (v0.1 Viewer → v0.5 Writer → v1.0 Telephony+cutover → v1.5+ Strategic), say clearly which version it belongs to before building it. Don't silently expand scope, and don't hard-block the idea either — just name it and confirm before proceeding.
- **Simple over complex.** Prefer the solution touching the fewest files and using data already in CLS1.db/CLS2.db over a more elaborate architecture.

## Session Closeout (mandatory — end every response that creates or edits a file with this)

This applies to every Claude Code response in this repo that creates, edits, or deletes a file — not just "big" sessions. No exceptions, no judgment call about whether it's "worth it" for a small change. If literally nothing was created or edited, state that plainly instead of the block below.

End the response with exactly this structure:

```
### Files to re-upload to Project Knowledge
- <full path> (v<X.Y> — one-line changelog of what changed)
- ...
(List ONLY files actually touched this turn. If none: "No files changed — nothing to re-upload.")

### How to check this worked
1. <plain English, numbered, no jargon — something Srikanth can literally do at
   his desk, e.g. "Open leads_list.html in the browser and confirm the new
   filter dropdown shows 5 options" — never "verify DOM state" or similar>
2. ...

### Flags
- Security/auth/roles/tokens/.env touched: none / <describe>
- DPDP Act relevance (esp. call-recording consent): none / <describe>
- Scope: within current version / belongs to v<X> — flagged, not built without confirmation
- Job B (`selldo_to_cls.py`) touched: no / yes — Job B was retired 2026-08-18 and is historical/reference only; flag any change before proceeding rather than just proceeding
- New script, or a changed schedule/frequency: no / yes — needs a `.bat` wrapper +
  Task Scheduler entry (or an update to an existing one) — <specify>

### Resume-from-here
1. Completed this session: <...>
2. Current file/version state: <...>
3. Next task: <...>
4. Open decisions awaiting Srikanth: <...>
```

Notes on filling this in:
- The changelog fragment next to each file should be short enough to scan in a few seconds, but specific enough that Srikanth can tell what changed without reopening the file.
- "How to check this worked" is deliberately in the same plain-English, jargon-free spirit as the diagnostic/safety-net tooling rule already in this file — one command or one click → one plain-English outcome, not a technical description of internals.
- A reminder to run `git` "Commit Changes" belongs in step 1 of Resume-from-here when files changed this session — don't skip it just because it feels like a formality.
