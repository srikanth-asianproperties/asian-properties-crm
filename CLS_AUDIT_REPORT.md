# CLS / APX CRM — Full Codebase Audit

Read-only audit. No source files were modified. Findings only.
Doctrine reference: determinism at core / LLM at edges; centralized SQLite in `cls_db.py`;
config-not-code; guarded prints; UTF-8 logging; paused-not-deleted; self-healing migrations.

Auditor model: Opus 4.8. Started: 2026-08-18.

---

# PASS 1 — Core application

Files read in full or in depth: `crm/app.py` (6104 lines), `cls_db.py` (11899),
`crm/cls_reports.py` (1379), `crm/create_admin.py`, `crm/schema_check.py`, plus a
structural scan of all 54 `crm/templates/*.html`.

## Compliance confirmed (no action — recorded so later passes don't re-check)

- **No stray SQLite.** `app.py` and `cls_reports.py` open **zero** direct `sqlite3`
  connections — every read/write goes through `cls_db._connect()`. `schema_check.py`
  opens its own connection, but that is the documented, read-only diagnostic exception.
  Doctrine "all SQLite access centralized in cls_db.py" is honoured in Pass-1 scope.
- **No SQL injection.** Every dynamically-assembled query interpolates only
  whitelisted identifiers (`SORT_OPTIONS`, `_STAGE_BREAKDOWN_GROUP_COLUMNS`, fixed
  column-name tuples, or `?`-placeholder counts). All *values* are parameterized. Spot-checked
  `_build_lead_filter_where`, `get_stage_breakdown`, `update_property_details`, `get_user_timeline`.
- **Print guards.** `app.py._log()` guards `sys.stdout is not None`; the only bare
  `print()` in `cls_db.py` is inside the `__main__` self-test. `pythonw.exe`-safe.
- **Auth is strong.** Passwords: PBKDF2-HMAC-SHA256, 260 000 iterations, per-user
  random salt, `secrets.compare_digest`, fails closed, no user-enumeration oracle
  (unknown email / wrong password / disabled account all return `None` identically).
  API tokens: 256-bit random, stored only as SHA-256, fail-closed, revocable.
- **Decorator stacking.** Every real `@admin_required` is preceded by `@login_required`
  (verified programmatically). `serve_recording` uses `secure_filename` + `send_from_directory`
  (safe_join) — no path traversal.
- **Paused-not-deleted.** The superseded `get_reengaged_count`/`get_reengaged_leads`
  block (`cls_db.py:4345-4420`) is commented with a dated reason. Compliant, not clutter.

---

## Findings

### F1 — Missing indexes on the three hottest `leads` columns
- **File:** `cls_db.py`
- **Function/Line:** `init_db()` — index creation block `cls_db.py:2535-2537` (only
  `phone_norm`, `email_norm`, `leadgen_id` are indexed on `leads`)
- **Category:** Future Scale Risk / Performance
- **Severity:** High
- **What you found:** The `leads` table has **no index** on `current_stage`,
  `lead_owner`, or `cls_created_at`. Nearly every dashboard count
  (`get_new_enquiries_count`, `get_no_future_activity_count`, `get_stage_snapshot_counts`,
  `get_owner_workload`…), the leads list (`get_leads_page` filters on `current_stage`,
  scopes on `LOWER(lead_owner)`, sorts on `cls_created_at`), and every report groups or
  filters on exactly these columns. Each such query is a full table scan today.
- **Why it matters:** This is the same root cause as the known 1–2 minute lead-list
  load, generalized: at ~8 000 leads (up from the ~3 000 the system was sized for) every
  count on the dashboard and every report already scans the whole table. It scales
  linearly — at 20–30k leads the dashboard itself (which fires ~6 of these counts per
  load) becomes the bottleneck, not just the list page.
- **Suggested direction:** Add self-healing `CREATE INDEX IF NOT EXISTS` statements in
  `init_db()` for `leads(current_stage)`, `leads(cls_created_at)`, and a
  `leads(lead_owner COLLATE NOCASE)` expression/index to match the `LOWER(lead_owner)`
  predicate. Consider a composite `(lead_owner, current_stage)` for the common
  owner-scoped-stage-count pattern.

### F2 — `project_bucket` is derived, forcing full-table Python bucketing in 5+ functions
- **File:** `cls_db.py`
- **Function/Line:** `get_leads_page` (`3838-3843`), `get_leads_matching` (`3921-3927`),
  `get_project_pipeline` (`9781-9789`), `get_stage_breakdown` (`10427-10440`),
  `get_site_visits_by_campaign` (`10482-10488`) — each does
  `.fetchall()` then a Python `for` loop calling `get_project_bucket()` per row
- **Category:** Performance / Future Scale Risk
- **Severity:** Medium
- **What you found:** Because the display project name is *derived* at read time
  (`get_project_bucket()` maps Sell.do's spacing/dash/multi-project variants), none of
  these functions can `GROUP BY project` in SQL. They fetch the full matching row set
  into Python and bucket in a loop. `get_leads_page` is the known symptom; the same
  pattern is replicated across the reports layer.
- **Why it matters:** Every project-grouped report re-pays the "load all rows, loop in
  Python" cost the known lead-list issue already exposes. Fixing only `get_leads_page`
  leaves four more copies that will slow down as the table grows.
- **Suggested direction:** Store a normalized `project_bucket` column on `leads`,
  populated on every write (Job A / manual create / Sell.do import) and backfilled via a
  one-time additive migration, with `reload_project_bucket_cache()` triggering a
  re-backfill when aliases change. Then these five functions become SQL `GROUP BY` /
  `WHERE project_bucket = ?`, and F1's index can cover it.

### F3 — Current user re-loaded 4× per request, each on a fresh connection
- **File:** `crm/app.py`
- **Function/Line:** `_log_user_action` → `_actor()` (`2059`), `login_required` (`1959`),
  `inject_current_user` (`2033`), plus the route body (e.g. `leads_list` `3303`)
- **Category:** Performance
- **Severity:** Medium
- **What you found:** A single authenticated request calls `cls_db.get_user_by_id()`
  four times (before_request actor log, the login_required gate, the context processor,
  and again inside most route bodies), and `inject_current_user` additionally fires
  `get_unread_assignment_count` + `get_pending_reminder_count`. Each `get_user_by_id`
  opens a new `_connect()` that re-runs `PRAGMA journal_mode=WAL` + `PRAGMA foreign_keys=ON`.
  So ~7 connections/queries of pure per-request overhead run before any page work.
- **Why it matters:** Not fatal at this team's size, but it multiplies every page load's
  fixed cost and compounds with F1 (each of those loads competes with unindexed scans).
  It's low-risk, high-leverage cleanup.
- **Suggested direction:** Resolve the current user once per request and cache it on
  `flask.g` (populate in `login_required`/`before_request`, read everywhere else). Leave
  `cls_db.get_user_by_id` itself unchanged.

### F4 — Report date filters use non-sargable `substr(cls_created_at,1,10)`
- **File:** `cls_db.py`
- **Function/Line:** `get_source_performance:9709`, `get_project_pipeline:9773`,
  `get_stage_breakdown:10418`, `get_site_visits_by_campaign:10470`,
  `get_daily_owner_summary:9308/9316`, and siblings using
  `substr(<date_col>,1,10) BETWEEN ? AND ?`
- **Category:** Performance / Future Scale Risk
- **Severity:** Medium
- **What you found:** Report date-range predicates wrap the date column in `substr(...)`,
  which prevents any index on that column from being used — even once F1 adds one. (By
  contrast `get_leads_page` uses the sargable `cls_created_at >= ?`, so the two styles
  are inconsistent.)
- **Why it matters:** With the volume of date-ranged reports, these stay full scans
  regardless of indexing effort. It also means F1's benefit won't reach the reports layer
  until this is addressed.
- **Suggested direction:** Since `cls_created_at` is stored `YYYY-MM-DD HH:MM:SS`,
  compare it directly as a string range (`>= 'YYYY-MM-DD 00:00:00' AND <= 'YYYY-MM-DD 23:59:59'`),
  matching `get_leads_page`'s already-sargable style, so an index on the raw column applies.

### F5 — Inline CAPI fire records no local per-row fire state in CLS1 (verify in later pass)
- **File:** `crm/app.py`
- **Function/Line:** `change_lead_stage()` CAPI block `3645-3656`
- **Category:** Idempotency Risk
- **Severity:** Medium — **PLAUSIBLE** (depends on `cls_capi_core.fire_single_lead_event`,
  which is Pass 2/3 scope; flagging now to verify then)
- **What you found:** On a successful stage change into a target stage the CRM fires the
  event synchronously, but on the **success** path it only `_log()`s — it does not appear
  to call `cls_db.mark_as_fired()` or otherwise persist a per-row "fired" marker in CLS1.
  Only the failure path writes (`queue_failed_fire`). Meanwhile Job C fires the same lead
  independently from CLS2. De-duplication therefore rests entirely on Meta-side
  `event_id = md5(identifier+stage)`.
- **Why it matters:** The doctrine's Risk-4 (per-row fire state tracked independently) is
  effectively delegated to Meta rather than recorded locally on the CLS1 side. That is
  acceptable *if* `event_id` is truly deterministic and identical between the inline path
  and Job C — but if the two paths ever compute the identifier differently (e.g. different
  phone/email normalization, or one uses `leadgen_id` and the other phone), the same
  human stage change double-counts as a conversion against real ad spend.
- **Suggested direction:** In Pass 2, confirm `fire_single_lead_event` and
  `cls_capi_firer.py` derive `event_id` from the **same** normalized identifier + stage.
  Consider having the inline success path also record a local fire marker so CLS1 has an
  auditable per-row fire history, not just a failure queue.

### F6 — `get_leads_matching` fetches the entire matched set (bulk paths)
- **File:** `cls_db.py`
- **Function/Line:** `get_leads_matching()` `3912-3928`
- **Category:** Future Scale Risk
- **Severity:** Low
- **What you found:** The unpaginated sibling of `get_leads_page` loads **all** matching
  rows and buckets each in Python. Used by Bulk Reassign / Bulk Export, which legitimately
  need the full set — but "All leads" with no filter returns every row.
- **Why it matters:** A bulk export/reassign with loose filters materializes the whole
  `leads` table in memory and preview. Fine now; a watch item as volume grows.
- **Suggested direction:** No change needed short-term; fold into F2's stored-bucket work
  so at least the per-row Python bucketing disappears. Optionally cap/paginate the preview.

### F7 — Unbounded append-only tables with no visible retention
- **File:** `cls_db.py` / `crm/app.py`
- **Function/Line:** `_log_user_action` (before_request, `app.py:2083`) →
  `log_user_action` writes one `user_action_log` row **per authenticated request**;
  `get_events(limit=None)` (`cls_db.py:9352`) returns the whole `events_log`
  (`cls_dashboard.py:109` calls it with no limit)
- **Category:** Future Scale Risk
- **Severity:** Low
- **What you found:** `user_action_log` gains a row on every page view with no pruning
  path in Pass-1 scope; `events_log` is read in full by the dashboard generator.
- **Why it matters:** Slow, silent growth. `user_action_log` will eventually dominate DB
  size and slow the User Activity Log screen; an unbounded `get_events()` read grows with
  every CAPI fire.
- **Suggested direction:** Add a retention/rollup for `user_action_log` (e.g. keep N days),
  and give `get_events()` a sane default limit for the dashboard caller.

### F8 — `admin_required` reads `session["user_id"]` without a guard
- **File:** `crm/app.py`
- **Function/Line:** `admin_required` wrapper `app.py:1976`
- **Category:** Code Quality / Security (latent)
- **Severity:** Low
- **What you found:** `admin_required` does `cls_db.get_user_by_id(session["user_id"])`
  with a bare subscript. It's always stacked under `login_required` today (verified), so
  the key always exists — but the safety depends on call-site discipline, not the
  decorator itself. A future admin route that forgets `@login_required` would 500
  (KeyError) instead of redirecting to login.
- **Why it matters:** Defense-in-depth; a decorator named `*_required` should fail closed
  on its own.
- **Suggested direction:** Use `session.get("user_id")` and redirect/401 when absent,
  mirroring `login_required`'s own guard.

---

## Pass 1 Summary

- **Findings by severity:** High 1 · Medium 4 · Low 3 (8 total). Zero Critical.
- No doctrine violations found in Pass-1 scope (centralization, print guards, injection,
  paused-not-deleted all compliant); auth is notably solid.

**Top 3 priorities from Pass 1:**
1. **F1 — add the three missing `leads` indexes.** Cheapest, highest-leverage fix; a
   self-healing migration that directly attacks the same root cause as the known
   lead-list slowness across the whole dashboard and reports layer.
2. **F2 — stored/backfilled `project_bucket` column.** Removes the "fetch-all + loop in
   Python" pattern from five functions at once and lets F1's index reach the reports.
3. **F5 — verify inline-vs-Job-C `event_id` determinism (in Pass 2).** The only finding
   touching real ad spend; confirm the two fire paths can never disagree on `event_id`.

---

# PASS 2 — Background jobs & pipeline

Files read in full or in depth: `meta_leads_fetcher.py` (Job A, 746), `selldo_to_cls.py`
(Job B — audit-only, 990), `cls_capi_firer.py` (Job C, 400) + `cls_capi_core.py` (272),
`cls_email_drip.py` (Job D, 1002), `cls_weekend_visits_report.py` (233), `cls_watchdog.py`
(1126), `cls_backup.py` (628), `cls_parallel_diff.py` (204), `cls_telegram_listener.py`
(572), `migrate_db.py` (114), `setup_task_scheduler.py` (188), `cls_attendance_photo.py`
(257), `cls_dashboard.py` (469), `cls_telecaller_report.py` (568). Also inspected every
`run_*.bat` wrapper to establish each job's live `CLS_DB_PATH` and interpreter.

## Compliance confirmed (no action — recorded so Pass 3 doesn't re-check)

- **Pass-1 F5 is RESOLVED, favourably.** All three fire call sites (`crm/app.py`
  `change_lead_stage`, `meta_leads_fetcher.py` new-lead insert, `cls_capi_firer.py` queue
  processor) fire through the **single** `cls_capi_core.fire_single_lead_event()` →
  `build_event_payload()`. `event_id = md5(identifier + "_" + stage)` is therefore computed
  by one implementation everywhere — the two paths cannot disagree. And the success path
  **does** persist local per-row fire state (`cls_db.mark_as_fired()` + `record_event()`,
  `cls_capi_core.py:263-271`), contrary to F5's tentative worry — so doctrine Risk 4 is
  satisfied. Residual nuance carried forward as P2-6 (Low).
- **`cls_attendance_photo.py` is exemplary.** No SQLite; uses the `logging` module (UTF-8
  safe, guarded); config-not-code API key from a real env var; three-layer fallback where
  the public function provably cannot raise. No findings.
- **`cls_parallel_diff.py` is clean.** Read-only, uses only the documented
  `cls_db.get_leads_snapshot(db_path)` exception, guarded prints (`_p`). (It loads both full
  DBs into memory, but that is inherent to a whole-corpus diff and it is manual/unscheduled.)
- **Job D pause is clean.** `DRIP_PAUSED=True` guard at the very top of `run()`
  (`cls_email_drip.py:790`) exits before any work; nothing removed, dated reason in header.
  Compliant "paused not deleted".
- **Job B's `meta_fetch` gate is a clean pause** (`selldo_to_cls.py:785-801`) — commented
  out with a dated CLS1/CLS2-split reason, not deleted. Compliant.
- **Job A fires inline only on genuinely-new leads** (`is_new_lead`, `meta_leads_fetcher.py:618`)
  and queues on failure rather than blocking the pull loop — sound idempotency posture.

---

## Findings

### P2-1 — Job D bounce-sync opens a hardcoded, non-existent `cls.db` directly
- **File:** `cls_email_drip.py`
- **Function/Line:** `sync_bounces_from_brevo()` — `714-733` (called from `run()` at `818`)
- **Category:** Doctrine Violation / Idempotency-adjacent correctness (latent Critical)
- **Severity:** High (latent behind `DRIP_PAUSED`)
- **What you found:** The bounce writer does `db_path = os.path.join(BASE_DIR, "cls.db")`
  then `conn = sqlite3.connect(db_path)` and `UPDATE leads …`, with **no** try/except around
  the DB block. Two independent faults: (1) it opens a **raw** `sqlite3` connection (doctrine
  says all SQLite goes through `cls_db.py`); (2) `D:\CLS\cls.db` **no longer exists** — it was
  split into CLS1/CLS2 on 2026-07-26 and the original renamed to `cls.db.pre_split_backup`.
  `sqlite3.connect` silently **creates** an empty `cls.db`, then `UPDATE leads` raises
  `no such table: leads`, which propagates and crashes `run()`. It also bypasses
  `CLS_DB_PATH` entirely, so even if the file existed it would write to the wrong database
  (Job D's wrapper targets CLS2.db).
- **Why it matters:** The moment Job D is un-paused, its first substantive action crashes the
  whole job — or, if a stray `cls.db` is ever present, silently marks bounces in a phantom DB
  that nothing reads, so hard-bounced/complained addresses keep being emailed. That degrades
  Brevo sender reputation and is a spam-compliance exposure.
- **Suggested direction:** Add a `cls_db.mark_email_bounced(email, bounce_type)` helper that
  uses `cls_db._connect()` (honouring `CLS_DB_PATH`), delete the hardcoded path, and
  re-review Job D end-to-end before ever un-pausing it.

### P2-2 — Monitoring (watchdog + Telegram bot) reads CLS2, now frozen since Job B stopped
- **File:** `cls_watchdog.py`, `cls_telegram_listener.py` (+ their `.bat` wrappers)
- **Function/Line:** wrappers set `CLS_DB_PATH=D:\CLS\CLS2.db`; watchdog `cls_db.stats()`
  (`653/685`), `get_unfired_leads()` (`583/951`), `get_daily_owner_summary()` (`1017`);
  listener `_db()` queries (`288/311/317/325/403`)
- **Category:** Doctrine Violation (config/ops drift)
- **Severity:** Medium (High if the false signal masks a real CLS1 outage)
- **What you found:** `cls_capi_firer.py` v3.0 (2026-08-14) states **Job B is permanently
  stopped** and the redesign now centres on CLS1 (Job A + the CRM app write CLS1; the
  `capi_fire_queue` lives in CLS1; `run_cls_capi_firer.bat` points at **CLS1**). But both
  monitoring tools still target **CLS2** — the Sell.do mirror that no longer receives writes.
  So "new leads fetched", "pending fire", and the per-owner daily summary in the health digest
  and the Telegram `/stats` `/today` `/pending` commands are computed from a frozen database.
- **Why it matters:** The watchdog can report Job A as fetching 0 leads and show stale owner
  summaries while the live system (CLS1) is perfectly healthy — chronic false alarms that
  train the team to ignore the digest, and conversely it would **not** see a real problem in
  CLS1. Flags and `job_results.txt` are shared files so those checks still work; only the
  DB-backed numbers are wrong.
- **Suggested direction:** Decide the intended monitoring DB now that Job B is stopped; if
  CLS1 is the live source, repoint both wrappers to CLS1 (flag/job-result checks are
  unaffected). Reconcile CLAUDE.md, which still documents monitoring → CLS2.

### P2-3 — CLAUDE.md ↔ live wrapper drift on Job C's target DB (a wrong-DB-fallback trap)
- **File:** `run_cls_capi_firer.bat` vs `CLAUDE.md`
- **Line:** wrapper: `set CLS_DB_PATH=D:\CLS\CLS1.db`; CLAUDE.md documents Job C → CLS2.db
- **Category:** Doctrine Violation (documentation vs reality)
- **Severity:** Medium
- **What you found:** The live wrapper points Job C at **CLS1** (correct for the v3.0
  inline-firing redesign — the queue and leads it processes are in CLS1). CLAUDE.md still
  says Job C/D and monitoring run against CLS2. The docs describe the *pre*-redesign world.
- **Why it matters:** CLAUDE.md itself documents a real 2026-07-26 incident where a task ran
  against the wrong DB. An operator "correcting" `run_cls_capi_firer.bat` back to CLS2 to
  match the docs would silently break CAPI firing (the queue lives in CLS1) — real ad-spend
  signal loss with no error.
- **Suggested direction:** Update CLAUDE.md's database-split section to reflect the post-
  Job-B-stop reality (Job C → CLS1, monitoring TBD per P2-2), so the docs stop contradicting
  the wrappers.

### P2-4 — SQL executed outside `cls_db.py` in three jobs
- **File:** `meta_leads_fetcher.py`, `cls_telegram_listener.py`, `cls_email_drip.py`
- **Function/Line:** `meta_leads_fetcher.newest_meta_time_for_form` (`500-507`, `cls_db._connect()`
  + inline `SELECT MAX(...)`); `cls_telegram_listener._db()` (`172-176`) + inline queries
  (`288/311/317/325/403`, **raw** `sqlite3.connect`); `cls_email_drip.maintenance_pass`
  (`745-766`, `cls_db._connect()` + inline SELECT/loop) — the raw-`sqlite3` case in the same
  file is P2-1
- **Category:** Doctrine Violation
- **Severity:** Medium
- **What you found:** Doctrine: "All SQLite access stays centralized in `cls_db.py`. No other
  script opens the database directly." `cls_telegram_listener._db()` opens a **raw**
  `sqlite3.connect(DB_FILE)` and re-implements `row_factory`, re-deriving connection setup
  that could drift from `cls_db._connect()`'s PRAGMAs. The other two use `cls_db._connect()`
  (a softer deviation — right connection factory) but keep the SQL in the job file.
- **Why it matters:** Schema/normalization changes now have to be chased across job files
  instead of living in one place; the raw-connect path also silently skips `PRAGMA foreign_keys`
  / WAL that every `cls_db._connect()` sets.
- **Suggested direction:** Move each query behind a named `cls_db` function (e.g.
  `get_newest_meta_time_for_form`, the listener's stat queries, the drip pause/unpause scan);
  at minimum replace the raw `sqlite3.connect` in the listener with `cls_db._connect()`.

### P2-5 — Unguarded `print()` in several jobs' `log()` (pythonw crash risk)
- **File:** `meta_leads_fetcher.py`, `cls_watchdog.py`, `cls_email_drip.py`,
  `cls_telecaller_report.py`, `selldo_to_cls.py`; partial in `cls_capi_firer.py`, `cls_backup.py`
- **Function/Line:** `meta_leads_fetcher.py:231`, `cls_watchdog.py:297`, `cls_email_drip.py:169`,
  `cls_telecaller_report.py:90`, `selldo_to_cls.py:263` (bare `print(entry)`);
  `cls_capi_firer.py:104` and `cls_backup.py:218` catch only `UnicodeEncodeError`, **not** the
  `RuntimeError`/`ValueError` raised when `sys.stdout is None`
- **Category:** Doctrine Violation
- **Severity:** Medium for `meta_leads_fetcher.py` (Job A), Low for the rest
- **What you found:** Doctrine mandates guarding every `print()` because `pythonw.exe` sets
  `sys.stdout=None`. The correct pattern exists in this repo (`cls_telegram_listener.py:135`,
  `cls_weekend_visits_report.py:65`, `crm/app.py:1862`: `if sys.stdout is not None:`), but the
  files above skip it. The other jobs' wrappers launch `python.exe` (real console → stdout
  present today), so they don't crash **in practice** — but **Job A has no `.bat` wrapper**
  (it relies on `cls_db.py`'s default DB), so nothing pins its interpreter; if its Task
  Scheduler action uses `pythonw.exe`, `log()` crashes on the first line before any lead is
  pulled. Note the two report jobs that *do* run under `pythonw.exe` are correctly guarded.
- **Why it matters:** A silent background job that dies on its first log line looks like "it
  ran and did nothing", the hardest failure to notice — exactly what the guard rule exists to
  prevent.
- **Suggested direction:** Apply the `if sys.stdout is not None:` guard uniformly in every
  job's `log()` helper; widen the two `except UnicodeEncodeError` guards to also swallow the
  stdout-is-None case.

### P2-6 — Residual `event_id` fragility: identifier fallback chain + unbounded `record_event`
- **File:** `cls_capi_core.py`
- **Function/Line:** `build_event_payload` identifier pick (`186-189`); `record_event` call
  on every success (`264-271`)
- **Category:** Idempotency Risk
- **Severity:** Low
- **What you found:** `identifier = selldo_lead_id or phone_norm or cls_id`. The id is chosen
  fresh at fire time, not frozen per lead. If a lead's higher-priority identifier appears or
  changes **after** a first fire (e.g. a CLS1 lead later gains a `selldo_lead_id` via CSV
  import), a subsequent same-stage fire computes a **different** `event_id`, so Meta will not
  dedupe it → a possible double conversion against real spend. Separately, `record_event`
  appends one `events_log` row per successful fire with no dedupe, so a lead queued twice for
  the same stage inflates dashboard counts (local reporting only — Meta still dedupes on
  matching `event_id`).
- **Why it matters:** Narrow (needs an identifier to change plus a same-stage re-fire), but it
  touches real ad-spend accuracy, so worth closing rather than relying on "identifiers never
  change".
- **Suggested direction:** Pin `identifier` to one stable field per lead (prefer `cls_id`, or
  freeze whichever id was used at the lead's first fire) so `event_id` can never shift;
  optionally dedupe `record_event` on `(cls_id, stage)`.

### P2-7 — `cls_dashboard.generate_dashboard()` renders the entire `events_log` every run
- **File:** `cls_dashboard.py`
- **Function/Line:** `generate_dashboard()` — `cls_db.get_events()` with no limit (`109`),
  two full Python passes (`117-130`, incl. `get_project_bucket()` per row), full-table HTML build
- **Category:** Future Scale Risk / Performance
- **Severity:** Medium
- **What you found:** The dashboard pulls **every** CAPI event ever recorded, loops over all
  of them twice in Python (the same derived-bucket pattern as Pass-1 F2), and writes each one
  into a single `dashboard.html`. This runs at the end of **every** Job C cycle (up to 5×/day)
  via `_refresh_outputs`. It is the concrete caller behind Pass-1 F7's unbounded `get_events()`.
- **Why it matters:** `events_log` grows one row per fire forever, so both the generation time
  and the size of `dashboard.html` grow without bound. Job C swallows dashboard failures, so it
  won't break firing — it just quietly gets slower and heavier each cycle.
- **Suggested direction:** Cap `get_events()` for the dashboard (most-recent N, or a rolling
  window such as last 90 days) and summarize/paginate older events; pairs with F7's retention
  recommendation.

### P2-8 — `cls_backup.py`: live DB copied without a consistent snapshot; `.env` synced to Drive
- **File:** `cls_backup.py`
- **Function/Line:** whole-folder rclone sync of `D:\CLS` (config `170-206`); docstring lists
  `.env` among backed-up files (`84`)
- **Category:** Future Scale Risk (data integrity) + Security
- **Severity:** Medium
- **What you found:** (integrity) The backup rclone-copies `CLS1.db`/`CLS2.db` as raw files.
  The CRM app runs continuously as a service and can be mid-write (WAL) at the 09:30 backup;
  copying a WAL-mode DB without a checkpoint/online-backup can capture a torn or pre-commit
  state, and the `-wal`/`-shm` sidecars may not be consistent at copy time. `cls_db_fork.py`
  already shows the right move (`PRAGMA wal_checkpoint(FULL)` before copy). (security) The
  docstring confirms `.env` — Meta CAPI token, System-User token, Brevo key, Telegram token —
  is synced to Google Drive in plaintext; `attendance_photos/` (employee selfies + GPS) is
  also synced, whereas `call_recordings/` is correctly excluded on DPDP grounds.
- **Why it matters:** A restore from an inconsistent DB copy could silently drop or corrupt
  recent leads — the one scenario a backup exists to prevent. A compromised Drive account
  exposes every API credential and employee location/selfie data.
- **Suggested direction:** Stage a consistent DB copy first (`wal_checkpoint(FULL)` then copy,
  or sqlite `.backup`/`VACUUM INTO`) and back up that copy; consider excluding or encrypting
  `.env`, and review `attendance_photos/` against the same DPDP posture already applied to
  `call_recordings/`.

### P2-9 — `migrate_db.py` and `setup_task_scheduler.py` are stale one-time tools (wrong drive/DB, bypass the `.bat` wrapper)
- **File:** `migrate_db.py`, `setup_task_scheduler.py`
- **Function/Line:** `migrate_db.py:22` `DB_PATH = r"C:\CLS\cls.db"`; `setup_task_scheduler.py:31-32`
  `SCRIPT_PATH`/`START_DIR = C:\CLS`, XML Action `Command={python_exe}` + `Arguments={script}` (`91-94`)
- **Category:** Dead Code / Doctrine Violation
- **Severity:** Medium
- **What you found:** `migrate_db.py` points at the **frozen C:\ drive** and the **pre-split**
  `cls.db`; its four columns now live in `cls_db.init_db()`'s additive migration, so it is
  superseded — running it would migrate the frozen backup. `setup_task_scheduler.py` registers
  Job D pointing **straight at `sys.executable` + the `.py`**, with **no `CLS_DB_PATH`** and
  **not** the `run_cls_email_drip.bat` wrapper — precisely the documented 2026-07-26 failure
  mode (task bypasses the wrapper → silent CLS1.db fallback) — and it would re-enable the
  deliberately-paused Job D on the frozen `C:\CLS` path.
- **Why it matters:** Both are live footguns: re-running either does damage (migrate the wrong
  DB / register a mis-targeted, un-paused Job D) with no warning that they are historical.
- **Suggested direction:** Quarantine or delete both as historical, or update them to `D:\CLS`
  and point the Task Scheduler Action at the `.bat` wrapper; add a loud "superseded — do not
  run" banner. Do not run as-is.

---

## Pass 2 Summary

- **Findings by severity:** High 1 · Medium 6 · Low 2 (9 total). Zero Critical (P2-1 is a
  latent Critical held behind the Job-D pause, rated High).
- **Doctrine posture:** the newest code (`cls_capi_core.py`, `cls_attendance_photo.py`,
  inline-fire redesign) is clean and centralizes fire logic well; the debt is in **older/edge
  tooling** (Job D bounce sync, monitoring DB target, one-time scripts) and in **docs that
  now lag the code** (CLAUDE.md's CLS1/CLS2 roles).
- **Idempotency verdict:** core firing is sound — one shared implementation, deterministic
  `event_id`, local per-row fire state persisted (Pass-1 F5 resolved favourably). Only the
  Low P2-6 residual remains.

**Top 3 priorities from Pass 2:**
1. **P2-1 — fix Job D's hardcoded `cls.db` bounce writer before un-pausing.** A latent
   job-crash / phantom-DB write sitting one flag-flip away from live; also a clear doctrine
   violation. Cheap to fix via a `cls_db` helper.
2. **P2-2 / P2-3 — reconcile the CLS1/CLS2 target drift (monitoring + Job C + CLAUDE.md).**
   Monitoring is watching a frozen DB and the docs contradict the live wrappers; both invite
   the exact wrong-DB incident CLAUDE.md already records.
3. **P2-5 — guard Job A's `print()` (and unify the guard everywhere).** Job A is the only
   unguarded job with no wrapper pinning its interpreter — a first-line silent-death risk.
