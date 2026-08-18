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
