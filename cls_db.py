"""
=============================================================
cls_db.py  —  Centralised Leads System (CLS) | Database Layer
=============================================================
Version : 2.91
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v2.91 (2026-09-03) — Payroll bug fix: blocks generation for an
  incomplete month, and removes "Absent" as a distinct payroll concept
  (folded into Leave). Prompted by a bad September 2026 snapshot
  generated mid-month (deleted from live CLS1.db, not a code change —
  3 rows, Elohar/Devender/Mounika, calculated 2026-09-03 15:19:12,
  drastically deflated net_salary since the still-to-come days of the
  month were counted as absent).
    - NEW is_salary_month_computable(year, month) — a month can only be
      calculated once _last_day_of_month(year, month) is in the past.
      Enforced in compute_salary_for_month() itself (defense in depth,
      not just hidden in the UI) as the FIRST check, before the
      existing is_salary_month_locked() check.
    - get_salary_month_status(): NEW 'computable' key alongside the
      existing has_snapshot/locked, for the admin page to show an
      incomplete-month message instead of a Generate button.
    - compute_salary_for_month(): 'absent' (explicit status rows AND
      untracked gap days alike) now feeds into leave_days_taken instead
      of a separate absent_days deduction — see this function's own
      docstring for the full before/after semantics. This CHANGES what
      leave_days_taken means going forward (every day not otherwise
      accounted for, not just self-marked leave) — an admin reading
      that column directly should know this.
    - salary_snapshots.absent_days column is kept (additive-only
      doctrine — old August rows still have real data in it) but is no
      longer written by new INSERT OR REPLACE calls (stays at its
      DEFAULT 0 for any month computed under this version).
    - ATTENDANCE_STATUSES/'absent' as a legal status elsewhere in the
      app (dashboard, corrections) is UNTOUCHED — this change is scoped
      to payroll math only.

v2.90 (2026-09-02) — Fix 2: holiday-aware, untracked-days-count-as-
  absent payroll fix. Root cause confirmed: this codebase has no
  automatic "mark absent" job — a day with no attendance row (no punch,
  no self-service leave/weekoff) contributed ZERO to every status
  bucket in get_attendance_totals_for_month(), invisible rather than
  "absent". Locked fix, confirmed by Srikanth: any such day now counts
  as absent for payroll deduction, UNLESS it's a company holiday
  (attendance_holidays table already existed but was unused by any
  consuming function before this — wired in for the first time here).
    - NEW get_holidays_in_month(year, month) — every attendance_
      holidays row in that month, first real consumer of that table.
    - salary_snapshots: NEW holiday_days/untracked_absent_days columns
      (self-healing PRAGMA table_info-checked ALTER TABLE, same idiom
      as attendance.last_modified_by v2.40 — additive only, existing
      rows default to 0).
    - compute_salary_for_month(): absent_days is now attendance
      'absent' PLUS untracked_absent_days = max((calendar_days -
      holiday_days) - tracked_days, 0), where tracked_days is every day
      that DID get an attendance row (present+late+half_day+absent+
      leave+weekoff). Both figures stored on the snapshot row for full
      auditability. present_days (half_day folded in) and per_day_rate
      (still base_salary / FULL calendar_days — a holiday doesn't
      shrink the rate denominator, same as a weekoff) are UNCHANGED.

v2.89 (2026-09-02) — Fix 1: Sittings Done date-range reporting, additive
  only, nothing existing removed or modified. Previously "Sittings
  Done" only existed in get_todays_activity_counts() (hardcoded to
  today) — this makes it reportable over an arbitrary date range via
  the already-built Salesperson Scorecard report.
    - ACTIVITY_METRIC_MAP: NEW 'sitting_done' -> 'sittings_done' entry,
      other 6 entries untouched. get_activity_counts_range() picks this
      up automatically (no other change to that function needed).

v2.88 (2026-09-02) — Task 6 item 7: "Today's Call Activity" card,
  additive only, nothing existing removed or modified.
    - NEW get_todays_call_stats(owner_scope=None) — deduped
      call_log_staging counts for today (same DISTINCT-on-(user_id,
      matched_cls_id, call_timestamp, duration_seconds, direction) dedup
      get_call_staging_rows() (v2.71) already uses, avoiding the known
      re-sync duplicate-inflation bug). owner_scope=None is company-wide;
      a user_id scopes to one salesperson. Returns outgoing_attempted/
      outgoing_answered/incoming_answered/total_synced.

v2.87 (2026-09-02) — Task 6 items 3 + 3b: Payroll v1.0 (admin-only, flat
  salary, monthly, push-button) and late/early punch admin notifications,
  additive only, nothing existing removed or modified. Admin (Srikanth)
  fully excluded from payroll — no salary_slabs row accepted for a
  role='admin' user, enforced in upsert_salary_slab() itself, not just
  the GUI. NO half-day concept in payroll math specifically — a
  'half_day'-status day is folded into "present" (zero cost) ONLY
  inside compute_salary_for_month(); ATTENDANCE_STATUSES and every other
  reader of 'half_day' elsewhere in this app is untouched.
    - NEW import calendar (module-level) — calendar.monthrange() is the
      single source of truth for both per-day-rate's denominator and
      the 10-day freeze window.
    - NEW salary_slabs / salary_snapshots tables (init_db(), self-
      healing CREATE TABLE IF NOT EXISTS). Self-healing INSERT OR IGNORE
      seed for Elohar Peddi (25000), Mounika Peddi (16000), Devender
      Goud (18000), resolved by full_name against the live users table
      at init time — skipped silently for any name that doesn't resolve
      to an active user, never raises.
    - NEW list_salary_slabs(), upsert_salary_slab(user_id,
      monthly_salary, actor), _last_day_of_month(year, month),
      is_salary_month_locked(year, month), _get_prev_month_snapshot
      (user_id, year, month), compute_salary_for_month(year, month,
      actor), list_salary_snapshots(year, month),
      get_salary_month_status(year, month), get_leave_balance(user_id).
      Paid-leave carry-forward capped at 5, state stored INSIDE each
      month's own salary_snapshots row (not a separate ledger) so
      recalculating the same month within the 10-day correction window
      is idempotent. ASSUMPTION, explicitly flagged (not confirmed by
      Srikanth): 'absent' days are deducted in full — only 'leave'/
      'weekoff'/'half_day' were explicitly ruled on when this was
      designed.
    - NOTIFICATION_EVENTS: NEW 'late_punch_in'/'early_punch_out' keys,
      other 9 keys untouched.
    - NEW notify_admins(event_type, message, cls_id=None) — fans an
      in-app + FCM notification out to every active admin, reusing
      _get_admin_user_ids()/insert_notification()/send_fcm_push()
      unchanged. IMPORTANT deviation from the original build spec,
      confirmed with Srikanth: callers MUST pass a per-employee-unique
      cls_id-like key (e.g. f"attn:{user_id}"), never the literal None
      the spec first proposed — insert_notification()'s event_id
      (md5(cls_id+event_type+today)) is GLOBALLY unique, so cls_id=None
      for every call of one event_type on one day would have collapsed
      every employee's late/early-punch event that day onto a single
      row, silently swallowing all but the first. See notify_admins()'s
      own docstring for the full reasoning; this does NOT fix the
      pre-existing, separate multi-admin fan-out collision already
      present in the new_enquiry hook — out of scope here.
    - NEW compute_early_leave_minutes(punch_dt) — mirrors compute_
      punch_in_timing()'s exact shape against WORKDAY_END_TIME ('17:30'
      default, previously unused). Read-only signal only — never writes
      to the attendance row, never affects status/late_minutes/payroll.

v2.86 (2026-09-02) — Task 6 item 2: leave-aware round-robin lead routing
  (Naishka Homes: Elohar / Devender), additive only, nothing existing
  removed or modified. Applies ONLY to rule_type='round_robin' campaign_
  routing_rules — rule_type='single' is untouched. Only 'leave'/
  'weekoff' (the two SELF_SERVICE_ATTENDANCE_STATUSES, known ahead of
  time) are checked; 'absent' is deliberately not special-cased here
  since it's only known after the fact.
    - NEW _owner_on_leave_today(conn, owner_full_name, today_str) —
      resolves owner_full_name -> attendance.status for today via
      users.full_name, treating "can't resolve"/"no row today" as
      available (never blocks routing on missing data).
    - resolve_owner_for_new_lead()'s round_robin branch: the picked
      owner (by cursor position) is skipped in favor of the next
      available teammate in rotation order if _owner_on_leave_today() is
      True, falling back to the originally-scheduled owner if everyone
      in rotation is on leave/weekoff. next_index read/increment is
      BYTE-FOR-BYTE unchanged — it still advances by exactly 1 per lead
      regardless of any skip, so rotation resumes exactly where it left
      off with zero extra state. _pick_cross_reassign_owner() (cross-
      project reassignment, v2.75) is untouched — separate feature.

v2.85 (2026-09-02) — Task 6 item 1: Sittings Done dashboard drill-down,
  additive only, nothing existing removed or modified. The count itself
  already existed (get_todays_activity_counts()'s METRIC_MAP has mapped
  'sitting_done' -> 'sittings_done' since v2.70) — this only adds the
  drill-down fetch function and its TODAY_PERFORMANCE_METRICS entry.
    - NEW get_sittings_done_today(actor_email=None) — same
      _activity_rows_today('sitting_done', ...) shape as the other 5
      Today's Performance drill-downs.
    - TODAY_PERFORMANCE_METRICS: NEW 'sittings_done' entry, other 5
      entries untouched.

v2.84 (2026-09-02) — Add record_call_log_entries_batch(), additive only,
  nothing existing removed or modified. Fixes a client-side timeout on
  /api/telephony/report-calls for users with large call-log backlogs
  (confirmed on Elohar's device — vivo V2141): the existing
  record_call_log_entry() opens its own SQLite connection and commits
  once PER call, so a 30+ call batch pushed total server response time
  past OkHttp's client-side timeout — the app reported "report-calls
  failed: timeout" even though the server eventually finished writing.
    - NEW record_call_log_entries_batch(user_id, calls) — same
      normalize+match+insert logic as record_call_log_entry() (reuses
      norm_phone()/find_match() unchanged, no new matching logic), but
      on ONE open connection for the whole batch, committing once at
      the end. Returns a list of per-entry result dicts in the same
      shape record_call_log_entry() returns, in input order.
      record_call_log_entry() itself is untouched.

v2.83 (2026-09-02) — Fix duplicate-counting bug in Missed Calls dashboard
  card, additive only, nothing else touched.
    - get_missed_calls_count() and get_missed_calls_list() now wrap
      their existing query in a dedup subquery — GROUP BY
      m.matched_cls_id, m.call_timestamp — before joining to leads,
      mirroring the precedent already established in
      get_call_staging_rows() (v2.71): the Android app's periodic
      re-sync re-stages already-seen calls, and record_call_log_entry()
      never dedupes on insert, so the same missed call could be counted
      (and listed) multiple times. get_missed_calls_list() additionally
      uses MIN(raw_phone) AS raw_phone inside the dedup subquery so the
      list has exactly one row per distinct (lead, call_timestamp) pair
      — this guarantees the list's row count always matches the
      count() badge exactly. Existing WHERE clause (direction='MISSED',
      matched_cls_id IS NOT NULL, call_timestamp window, NOT EXISTS
      outgoing callback) is unchanged inside the subquery. No data
      deleted — read-only query fix.

v2.82 (2026-09-02) — Prevent crm_lead_no race condition (UNIQUE index +
  retry-on-conflict), scoped fix only. Root-caused after Srikanth found
  lead #8447 duplicated (crm_lead_no had no uniqueness guard, just
  SELECT MAX(crm_lead_no)+1 as two separate steps in _next_crm_lead_no()
  — a live risk once the Meta webhook (real-time, since 2026-08-13)
  started running in parallel with Job A polling, doubling the chance
  of two near-simultaneous inserts reading the same MAX before either
  commits). Diagnosed with the new cls_diag_duplicate_lead_no.py
  (v1.0); 11 pre-existing duplicate crm_lead_no groups found and fixed
  with cls_fix_duplicate_lead_no.py (v1.1) before this migration ran —
  9 stale legacy selldo_only/meta collisions (8 auto-renumbered, 1
  manually deleted as a confirmed test row, 'Opted Out Person' /
  optout@test.com) plus the #8443/#8447 genuine near-simultaneous
  webhook/polling race pair (auto-renumbered). See those two scripts'
  own changelogs for the full renumbering detail — this entry covers
  only the schema + code hardening that stops it recurring.
    - NEW self-healing migration in init_db(): CREATE UNIQUE INDEX IF
      NOT EXISTS idx_leads_crm_lead_no ON leads(crm_lead_no), placed
      AFTER the crm_lead_no column migration + backfill (crm_lead_no
      is added via the drip_migrations self-healing ALTER TABLE loop,
      not the original CREATE TABLE — same placement fix v2.65 and
      v2.68 already applied here for idx_leads_owner/idx_leads_
      reengaged_at, needed again since an earlier placement of this
      index failed "no such column: crm_lead_no" against a fresh
      throwaway test DB during this change's own verification).
      Confirmed live against the production DB before this code
      change was written — only possible once the 11 pre-existing
      duplicates above were cleared, since a UNIQUE index create
      fails outright over existing duplicate values.
    - NEW _insert_lead_with_lead_no_retry(conn, do_insert, max_attempts=5)
      — shared helper, sits right after _next_crm_lead_no(). Calls
      do_insert(crm_lead_no) with a freshly recomputed crm_lead_no
      (via _next_crm_lead_no()) on each attempt; retries ONLY on a
      sqlite3.IntegrityError naming crm_lead_no (the exact race this
      exists to guard against) — any other IntegrityError propagates
      immediately without retrying, as does exhausting max_attempts.
    - upsert_meta_lead()'s new-insert branch, upsert_selldo_lead()'s
      new-insert branch, and create_manual_lead() — all three
      crm_lead_no assignment call sites — now route their INSERT
      through this helper instead of calling _next_crm_lead_no()
      directly. No signature or return-contract change to any of the
      three functions — every existing caller (app.py,
      meta_leads_fetcher.py, selldo_to_cls.py) is unaffected.
    - Scope: cls_db.py, this fix only. Nothing else existing removed
      or modified.

v2.81 (2026-09-01) — Missed Calls dashboard card gets a 7-day window,
  additive only, nothing else touched.
    - NEW module constant MISSED_CALLS_WINDOW_DAYS = 7.
    - get_missed_calls_count(owner=None, days=MISSED_CALLS_WINDOW_DAYS)
      and get_missed_calls_list(owner=None, days=MISSED_CALLS_WINDOW_DAYS)
      both gained a days= param and a
      "AND m.call_timestamp >= datetime('now', 'localtime', ?)" WHERE
      clause, superseding the v2.57 all-time behavior. Callers that
      don't pass days= (app.py's dashboard()/missed_calls_list() routes)
      are unaffected — they just get the new default of 7 days.

v2.80 (2026-09-01) — CAPI Events column-logic consolidation, pure
  refactor, zero behavior change. Companion to crm/app.py v0.63.
    - get_capi_events_export(date_from, date_to) — BREAKING RETURN-
      SHAPE CHANGE: now returns (rows, columns) instead of a bare rows
      list, by delegating directly to _flatten_capi_events() (which
      already computed both — the old version discarded the columns
      half). _flatten_capi_events() itself is UNTOUCHED by this
      version — this is a one-line change in its caller, not a
      behavior change to the shared helper.
    - _capi_events_columns_for_rows() / _prettify_capi_snapshot_
      column() / _CAPI_EVENTS_FIXED_COLUMNS (all introduced v2.79) are
      now the ONLY copy of this column-building logic anywhere in the
      codebase — crm/app.py v0.61's separate copy (CAPI_EVENTS_EXPORT_
      COLUMNS / _prettify_lead_column() / _capi_events_export_columns())
      was deleted in app.py v0.63, and _export_capi_events_report()
      there now just unpacks the columns this function already
      returns. See app.py v0.63's changelog for that side.
    - The ONLY caller of get_capi_events_export() in the whole
      codebase (confirmed via grep before this shipped) is crm/app.py's
      _export_capi_events_report(), updated in the same session to
      unpack (rows, columns) — so this return-shape change has exactly
      one call site to keep in sync, and it was kept in sync.
    - REGRESSION TESTED before shipping: Excel export headers, email
      export headers, and on-screen (paginated) table headers all
      confirmed byte-identical to their pre-consolidation output for
      the same test data — this is a pure refactor, not a feature or
      output change.
    - Scope: cls_db.py, this function pair only. Nothing else existing
      removed or modified.
v2.79 (2026-09-01) — CAPI Events pagination support.
    - REFACTOR (behavior-preserving): get_capi_events_export()'s SQL-
      fetch + JSON-flatten body extracted into new private helper
      _flatten_capi_events(date_from, date_to), which now ALSO computes
      the "Snapshot: "-labeled column list for the returned row set
      (new _CAPI_EVENTS_FIXED_COLUMNS constant + _prettify_capi_
      snapshot_column() + _capi_events_columns_for_rows() — this is new
      logic in cls_db.py, not present here before this version; it
      previously lived only in crm/app.py v0.61's CAPI_EVENTS_EXPORT_
      COLUMNS/_prettify_lead_column()/_capi_events_export_columns()).
      get_capi_events_export() itself still returns exactly what it
      returned before this refactor — a plain list of row dicts, no
      columns — confirmed via a regression test (same row count, same
      lead_* keys, byte-identical) against pre-refactor output before
      this version shipped.
    - KNOWN DUPLICATION, FLAGGED NOT FIXED: crm/app.py's v0.61 column-
      building helpers (used by the Excel/email export routes, which
      call cls_db.get_capi_events_export() for rows exactly as before)
      were NOT touched or consolidated with the new copy here — out of
      scope for this pagination-only change, which explicitly left the
      Excel/email routes untouched. Both copies must independently
      produce the same column set for the same rows; verified this
      version by comparing on-screen page-1 headers against an Excel
      export for the same date range (identical). Consolidating them
      into one copy is a reasonable follow-up, not done here since it
      wasn't asked for and would have widened this change's footprint.
    - NEW get_capi_events_export_page(date_from=None, date_to=None,
      page=1, per_page=200) — paginated view for the on-screen results
      table, same pagination shape/style as get_leads_page()/
      list_call_recordings() (fetch all, slice in Python, page clamped
      into [1, total_pages]). Columns computed from the FULL matching
      set via _flatten_capi_events(), so headers stay identical across
      pages. Returns {"rows", "total", "page", "per_page",
      "total_pages", "columns"}.
    - Scope: cls_db.py ONLY, this function family only. Nothing else
      existing removed or modified.
v2.78 (2026-09-01) — CAPI event snapshots, ADDITIVE ONLY. Freezes a
  lead's full state alongside every CAPI event fired, so events_log
  stops being just a log of WHAT fired and becomes a permanent record
  of what the lead looked like at that moment too.
    - Self-healing migration in init_db(): events_log gains
      lead_snapshot_json (TEXT) and snapshot_source (TEXT), added
      right alongside the existing prev_stage/lead_owner ALTER TABLE
      block (same pattern, same idempotent guard).
    - record_event() gains two new TRAILING optional params,
      lead_snapshot_json=None and snapshot_source=None — existing
      param order/defaults/positions untouched, every existing caller
      keeps working unchanged. Both threaded into the INSERT.
    - NEW get_capi_events_export(date_from=None, date_to=None) — reads
      events_log with the SAME substr(fired_at,1,10) BETWEEN ? AND ?
      convention get_activity_log_export() already uses, ordered
      fired_at DESC. Expands each row's lead_snapshot_json into
      lead_-prefixed flat keys (e.g. lead_full_name); rows with no
      snapshot yet simply carry no lead_* keys. Feeds crm/app.py's new
      CAPI Events export screen (Part 3, separate session).
    - NEW backfill_capi_event_snapshots(dry_run=True, verbose=False) —
      one-off, manually-invoked only (not called by any job or route).
      For every events_log row with lead_snapshot_json IS NULL, looks
      up the lead via get_lead_by_id() and freezes its CURRENT state
      in (snapshot_source='backfill_current_state' — distinct from
      the real fire-time capture cls_capi_core.py v1.1 now does going
      forward). A lead that no longer exists is skipped and counted
      as "orphaned", never raises. dry_run=True (default) counts only,
      writes nothing. Exposed via a new --backfill-capi-snapshots /
      --live / --verbose argparse gate in this file's own __main__
      block — no prior one-off-admin-function convention existed
      inside cls_db.py itself (the __main__ block was previously only
      ever the unconditional self-test), so this mirrors the
      --dry-run convention other one-off scripts in this codebase
      already use (e.g. cls_call_recording_audit.py). Plain
      `python cls_db.py` with no arguments is unaffected — still runs
      the self-test exactly as before.
    - Scope: cls_db.py ONLY, additive-only. Nothing existing removed
      or modified. Does NOT touch cross-project auto-reassignment
      (v2.75/2.76/2.77) — out of scope, not reopened.
v2.77 (2026-08-31) — Cross-Reassign Rules Admin GUI (Part B), backend
  only, ADDITIVE ONLY.
    - NEW list_cross_reassign_rules() / upsert_cross_reassign_rule() /
      delete_cross_reassign_rule() — CRUD for cross_project_reassign_
      rules (v2.75), mirroring list_campaign_routing_rules()/
      upsert_campaign_routing_rule()/delete_campaign_routing_rule()
      exactly in style and validation approach. upsert validates
      source_bucket != target_bucket, rule_type in ('single',
      'round_robin'), a non-empty owners_list, and exactly 1 owner for
      'single'; raises ValueError with a clear message on rejection.
      next_index resets to 0 only when the owners list actually changed
      from what's stored (same live-rotation-preserving rule as
      campaign routing's upsert) — re-saving to just flip active leaves
      an in-progress round robin exactly where it was.
    - Unlike campaign routing (separate toggle route, upsert always
      forces active=1), upsert_cross_reassign_rule() takes active as a
      direct parameter — the admin GUI's add/edit form includes the
      active checkbox itself rather than a separate toggle action, so
      one upsert call covers both create/edit AND activate/deactivate.
    - Scope: cls_db.py ONLY, additive-only. Nothing existing removed or
      modified.
v2.76 (2026-08-31) — Manual Project Editor (Part A), ADDITIVE ONLY.
    - NEW function update_lead_project(cls_id, new_bucket, actor) — lets
      a lead's owner manually change its project via Actions > Edit
      Property Details. Validates new_bucket against
      get_all_bucket_names() (same dropdown source as lead_new.html /
      the leads filter screen). No-op if unchanged (no pointless
      activity_log row or cls_updated_at bump). Sets BOTH leads.project
      and leads.project_bucket to new_bucket, same as
      _auto_cross_reassign_project() (v2.75) does. Does NOT touch
      current_stage, stage_reason, lead_owner, or cross_reassigned_at —
      fully independent of the auto-reassignment feature and its
      permanent ping-pong guard; a manual change never sets or checks
      that flag. Booked leads can have their project changed too, no
      restriction (Srikanth's explicit call). Logs a new 'project_changed'
      activity_log row.
    - Scope: cls_db.py ONLY, additive-only. Nothing existing removed or
      modified.
v2.75 (2026-08-31) — Cross-Project Auto-Reassignment, ADDITIVE ONLY.
    - NEW table cross_project_reassign_rules (init_db()) — mirrors
      campaign_routing_rules exactly in style: source_bucket/
      target_bucket pair, rule_type ('single'/'round_robin'), owners
      JSON array, next_index round-robin cursor, UNIQUE(source_bucket,
      target_bucket). Self-healing seed (INSERT OR IGNORE, never
      clobbers a row Srikanth already edited later via a future GUI):
      Naishka Homes -> Grace Classic (single, Mounika Peddi); Grace
      Classic -> Naishka Homes (round_robin, Elohar Peddi / Devender
      Goud). Owner spellings verified against the live users.full_name/
      leads.lead_owner columns before writing this seed.
    - NEW column leads.cross_reassigned_at (drip_migrations self-healing
      ALTER TABLE loop), nullable, NULL until a lead is auto-reassigned
      across project buckets. This is the PERMANENT ping-pong guard —
      Srikanth's explicit instruction (2026-08): once set for a lead,
      this feature can never fire again for it. If the lead goes Lost/
      Unqualified again on the new project too, it just stays there. No
      second bounce, ever.
    - NEW project_aliases seed row: ('Naishka Homes', 'Naishka Homes')
      — registers the bucket name itself as its own alias (previously
      only its sub-projects mapped to it). Cosmetic/completeness fix
      for /settings/projects display; get_project_bucket() already
      fell through safely without it.
    - NEW helpers _get_cross_reassign_rule(conn, source_bucket),
      _pick_cross_reassign_owner(conn, rule), and
      _auto_cross_reassign_project(conn, cls_id, source_bucket,
      new_stage, actor) — modeled directly on the existing
      _auto_cancel_open_schedules() helper (same file, same style, same
      silently-no-op-if-nothing-to-do posture). The picker reuses the
      exact same single/round_robin logic as the campaign routing
      picker used by resolve_owner_for_new_lead().
    - NEW NOTIFICATION_EVENTS key 'lead_cross_reassigned', shaped
      exactly like the existing 'lead_reassigned' entry. In-app bell
      only (insert_notification()) — deliberately no send_fcm_push()
      call here, same reasoning bulk_reassign_leads() already uses:
      this runs inside update_lead_stage()'s shared transaction, not a
      dedicated single-lead route, so a blocking network call per fire
      is skipped.
    - ONE new hook line in update_lead_stage(), inside the existing
      `if new_stage in AUTO_CANCEL_ON_STAGES:` block, immediately after
      the existing _auto_cancel_open_schedules() call: re-reads
      leads.project_bucket for this lead and calls
      _auto_cross_reassign_project() if it's set. AUTO_CANCEL_ON_STAGES
      itself is untouched — Lost/Unqualified already covers exactly the
      right cases.
    - Scope: cls_db.py ONLY, additive-only. Nothing existing removed or
      modified except the one new hook line inside update_lead_stage()
      described above. No changes to app.py, templates, or any other
      file — the admin GUI (/settings/cross-reassign) and the manual
      project-change dropdown are explicitly deferred to the next
      app.py-touching session.
v2.74 (2026-08-25) — Fix IST conversion bug in _format_meta_created_time(),
  ADDITIVE + ONE BUG FIX ONLY.
    - Confirmed repro: the Sahitya lead (#8335, 2026-08-24) — FB Leads
      Center showed this lead logging in at 18:33 IST, but Activity
      History in CLS showed 13:03. Root cause: _format_meta_created_time()
      parsed Meta's tz-aware created_time (UTC-offset ISO string, e.g.
      '2026-08-24T13:03:00+0000') with datetime.strptime(raw, fmt).
      strftime(...) directly — strptime keeps the parsed datetime's
      original wall-clock digits and attaches the offset as tzinfo, but
      the immediate .strftime() call never converts those digits to IST,
      so the UTC clock-face time (13:03) was displayed unchanged instead
      of the correct IST time (18:33).
    - FIX: added a module-level IST constant (timezone(timedelta(hours=5,
      minutes=30))) next to the datetime import. The tz-aware branch of
      _format_meta_created_time() now calls .astimezone(IST) on the
      parsed datetime BEFORE .strftime(), so the displayed digits are
      actually converted to IST wall-clock time. The naive-format branch
      ("%Y-%m-%d %H:%M:%S", no tzinfo — already a CLS-local timestamp) is
      untouched, same as before.
    - Scope: this function only. meta_leads_fetcher.py's
      newest_meta_time_for_form() was NOT touched — its use of
      .timestamp() is already timezone-correct (Unix timestamps are
      offset-agnostic by construction) and needed no change. No other
      function in this file was modified. meta_created_time's raw
      storage is unaffected — only this display/backdating formatter
      changed.
v2.73 (2026-08-24) — send_fcm_push() stale-token cleanup, ADDITIVE ONLY.
  Firebase project setup is done (secrets/*firebase-adminsdk*.json exists)
  and this is the first session actually activating the feature, so it's
  worth re-verifying: send_fcm_push() was NOT a no-op stub going into this
  session — v2.72 above already wired a real HTTP v1 send (google-auth +
  requests, reading FCM_SERVICE_ACCOUNT_KEY_PATH), just gated on
  credentials that didn't exist yet. That implementation is UNCHANGED here
  — no library swap, no env-var rename — per explicit confirmation this
  session, since CLAUDE.md/PK_BUNDLE.md already document google-auth +
  requests + FCM_SERVICE_ACCOUNT_KEY_PATH as the live convention and a
  second env var or SDK would only fork it.
    - NEW behavior added to send_fcm_push(), inserted between the existing
      200-OK success path and the existing generic-rejection log line
      (neither of those two lines changed): a 404 status code, or an
      "UNREGISTERED" errorCode in the response body's error.details[]
      (FCM's own signal that a token's app was uninstalled/reinstalled and
      will never succeed again), now triggers a DELETE FROM
      user_fcm_tokens WHERE user_id=? for that user, logged distinctly
      from a generic rejection. Without this, a stale token would be
      re-attempted forever on every future notification event for that
      user. A delete that turns out to be premature is harmless — the
      Android app re-registers on its next launch, and set_fcm_token()'s
      INSERT OR REPLACE just overwrites it.
    - No other line in send_fcm_push() changed. No change to
      set_fcm_token(), the user_fcm_tokens schema, or any of the 8
      notification-event call sites — this version touches nothing outside
      this one function.
v2.72 (2026-08-21) — Notifications v1.0 (Srikanth build session): unified
  in-app + FCM notification system, 8 event types.
    - NEW TABLE notifications (notification_id, user_id, cls_id, event_type,
      message, event_id UNIQUE, read_at, fcm_sent_at, created_at) + 2
      indexes (user_id+read_at for the bell query, event_id for the
      idempotency dedup lookup). Additive, self-healing CREATE TABLE IF
      NOT EXISTS, same as every other table in this file.
    - NEW config dicts NOTIFICATION_EVENTS (event_type -> message template)
      and NOTIFICATION_TRIGGERS (event_type -> (source_table, date_column,
      offset_hours, extra_where), for cls_notifications_poller.py's 5
      due/overdue event types) — config-not-code, same doctrine as
      STAGE_TRANSITIONS/RESET_STAGES_ON_REENGAGEMENT just above.
    - NEW insert_notification(user_id, cls_id, event_type, message,
      conn=None) — idempotent INSERT OR IGNORE keyed on event_id =
      md5(cls_id + event_type + today's date), same dedup idiom Job C
      uses for CAPI event_ids. Optional conn param, same reason/pattern
      as reassign_lead_owner()'s conn= (v2.28) — lets the poller batch
      many inserts in one transaction.
    - NEW get_unread_notification_count(user_id), get_notifications(
      user_id, limit=20) (joined to leads for full_name/crm_lead_no),
      mark_notification_read(notification_id), mark_all_notifications_
      read(user_id) — read-side of the bell, mirrors get_unread_
      assignment_count()/mark_lead_notification_read()'s existing shape.
    - NEW resolve_user_id_from_owner_name(owner_name) — SELECT user_id
      FROM users WHERE owner_match_name=? (trimmed), active=1. Verified
      live before writing: users.owner_match_name (v1.7) already IS the
      lead_owner<->user_id mapping column used by login/role logic
      elsewhere in this file — no new users column added, per the
      "verify first, don't invent a mapping if one exists" instruction
      this step was built under.
    - NEW _get_admin_user_ids(conn) — small internal helper (SELECT
      user_id FROM users WHERE role='admin' AND active=1), used only as
      new_enquiry's fallback target when resolve_user_id_from_owner_name()
      finds no linked login for the placeholder/fallback owner name.
    - NEW send_fcm_push(user_id, title, body) — looks up user_fcm_tokens
      (table has existed since v2.42; this is the first thing that
      actually calls FCM). Returns False and logs one line, NEVER raises,
      whenever user_fcm_tokens has no row for user_id OR the
      FCM_SERVICE_ACCOUNT_KEY_PATH env var is unset/points at a missing
      file — same pythonw.exe-safe guarded-print posture as every other
      stdout call in this file. Self-tested with no token and no
      credentials configured (see bottom of this file's SELF-TEST
      section) before being wired into any hook.
    - 3 hook call sites (upsert_meta_lead() branch 3 / new_enquiry,
      upsert_meta_lead() branch 2 right after its existing lead_reengaged
      _log_activity() call / lead_reengaged, reassign_lead_owner() right
      where owner_notified=0 is set / lead_reassigned) each now also call
      insert_notification() + send_fcm_push(). ADDITIVE ONLY — owner_
      notified / mark_lead_notification_read() / get_unread_assignment_
      count() are completely untouched, still the only thing driving the
      (currently unrendered) reassignment badge.
    - DEVIATION FROM THE ORIGINAL BUILD BRIEF, flagged not silently
      applied: the brief said to put the lead_reengaged hook INSIDE
      _apply_reengagement_marker(). Its live signature (conn, cls_id,
      prev_stage, now) has no full_name/owner to build a message from,
      and its own docstring already establishes the convention that
      lead_reengaged logging happens in the CALLER (upsert_meta_lead()),
      not the helper, for exactly this reason. Followed that existing
      convention instead of expanding the helper's signature.
    - Module-level `import sys` added (this file never needed it before
      — no logging of its own; every caller does its own). Needed solely
      for send_fcm_push()'s `sys.stdout is not None` guard, same
      pythonw.exe-safe convention every other script here already follows.
v2.71 (2026-08-20) — NEW get_call_staging_rows(user_id, date_str), read-
  only, built for cls_call_recording_diagnostic.py v1.1's staging-vs-
  recording cross-check (Srikanth found v1.0 silent on the real question:
  "I know elohar/office made 30+ calls today — why does the tool only
  show 10 recordings?"). Added here rather than left as raw SQL in the
  script, per this file's own centralization rule (CLAUDE.md: "All
  SQLite access stays centralized in cls_db.py"). DISTINCT-deduped by
  (matched_cls_id, call_timestamp, duration_seconds, direction) — see
  the function's own docstring for the real-data discovery that made
  this necessary: the Android app's periodic re-sync re-stages already-
  seen calls on every run (record_call_log_entry() never dedupes on
  insert), so raw call_log_staging row counts overstate real call volume
  by several multiples (534 raw rows -> 72 distinct real calls, one
  live example). Additive only — no existing function touched.
v2.70 (2026-08-20) — Task 4 batch (Srikanth, Todoist ##CLS-CRM, items 3/5/
  6/7):
    - Item 7 BUG FIX — get_new_enquiries_count()/get_new_enquiries_leads()
      lost their "clears the instant a human touches the lead" behavior
      when v2.57 replaced the old "zero activity_log rows" clause with
      reengaged_at IS NULL only. v2.57 was RIGHT to drop the old clause
      (broken by upsert_meta_lead()'s automatic lead_entered system row
      since v2.28) but should have replaced it with an actor-aware
      NOT EXISTS, not removed it outright. Both functions' WHERE clause
      now reads: current_stage='Incoming' AND reengaged_at IS NULL AND
      NOT EXISTS (a real, non-'system' activity_log row for this cls_id)
      — keeps v2.57's undercounting fix AND restores v2.11 behavior: a
      genuine call_attempted/note/stage-change tap by a real user drops
      the lead off the New Enquiries card immediately, even while it's
      still technically sitting at current_stage='Incoming'. Only the
      WHERE clause changed in each function — nothing else touched.
    - Item 6 — Srikanth explicitly reversed the "never Incoming on manual
      entry" decision (create_manual_lead() docstring, since v1.9).
      MANUAL_ENTRY_STAGES gains "Incoming" — config-only change, lead_new.
      html's dropdown already iterates this list, no template loop logic
      needed. create_manual_lead()'s docstring updated accordingly — see
      that function below for the reasoning, so a future session doesn't
      "fix" this back to the old restriction. Downstream effect (no code
      change needed, just noted for awareness): a manually-created lead
      at initial_stage='Incoming' is now eligible for the New Enquiries
      card (per the Item 7 fix above) until someone acts on it, exactly
      like a fresh Meta lead — consistent, not a bug.
    - Item 3 — NEW log_sitting_done(cls_id, actor, notes="") — activity_
      log-only event (activity_type='sitting_done'), same convention as
      call_attempted/note: no new table, single _log_activity() call.
      Mirrors log_walkin_site_visit()'s lead-exists-check shape, simpler
      since there's no site_visits row to insert. get_todays_activity_
      counts()'s METRIC_MAP gains "sitting_done": "sittings_done" so
      Today's Performance / the Daily Scorecard report pick this up
      automatically — zero new counting infrastructure, same mechanism
      site_visit_conducted already uses. (ACTIVITY_METRIC_MAP at
      get_activity_counts_range() is a deliberately separate constant
      per its own comment — "never touch unless explicitly flagged" —
      and is NOT touched here; not in scope for this item.)
    - Item 5 — NEW get_followups_count_for_day(date_str, owner=None) —
      counts follow_ups rows where substr(scheduled_at,1,10)=date_str
      AND status='scheduled', optionally scoped to one owner via the
      same follow_ups f JOIN leads l ON l.cls_id=f.cls_id / l.lead_owner
      pattern already used by get_todays_agenda()/get_due_by_kind() above.
      Feeds app.py's post-schedule flash message; no new route/template.
  All four items additive/behavior-restoring only — no existing function
  signature removed, no schema change.
v2.69 (2026-08-19) — Dashboard fix Part 2: site_visits.reminder_sent_at,
  a real stored column replacing get_site_visits_for_tomorrow()'s old
  correlated LIKE-against-activity_log lookup (the ~509ms bottleneck
  #2 flagged, and deliberately deferred, in the Dashboard diagnosis/
  Part-1 sessions). This ALSO FIXES A PRE-EXISTING BUG: under the old
  LIKE-based logic, a visit's "reminder sent" status incorrectly
  survived a reschedule — if a reminder was sent for a visit's original
  date, then the visit got rescheduled to a new date, the old lookup
  (keyed only on visit_id, not the scheduled_at it was sent for) still
  matched the old activity_log row and showed the rescheduled visit as
  already reminded, even though nobody had reminded the lead about the
  NEW date. The new column is explicitly reset to NULL on a genuine
  reschedule (see update_site_visit() below), so this can no longer
  happen.
    - Schema: site_visits gains reminder_sent_at (TEXT, nullable),
      self-healing ALTER TABLE, same visits_cols check already used for
      outcome_reason/project on this table. No index — table is a few
      hundred rows and every read is already date-scoped to "tomorrow."
    - Backfill (self-healing, gap-only, safe to leave running on every
      init_db() call indefinitely — same pattern as F2 Phase 1's
      project_bucket backfill): for every site_visits row where
      reminder_sent_at IS NULL, sets it to whatever the OLD LIKE-based
      lookup would have found (MAX(activity_log.created_at) for that
      visit_id's 'whatsapp_reminder_sent' rows), preserving historical
      accuracy for visits already correctly marked sent under the old
      system. A visit the old logic would also have found nothing for
      stays NULL — correctly still "not sent," not a change in meaning.
    - log_reminder_sent(visit_id, cls_id, actor): now ALSO writes
      site_visits.reminder_sent_at = now(), same connection/transaction
      as the existing activity_log write (which is UNCHANGED and KEPT —
      Srikanth wants the note in lead history regardless of this
      column's existence).
    - update_site_visit(): the "rescheduled" action branch now ALSO sets
      site_visits.reminder_sent_at = NULL, same transaction as the
      scheduled_at UPDATE, whenever new_scheduled_at is genuinely
      different from the visit's previous scheduled_at (a reschedule
      "to the same time" — never seen in practice, but checked for
      literally — is treated as a no-op and does not reset). This is
      the fix for the bug described above. schedule_site_visit()
      (initial creation, a brand-new row) is deliberately NOT touched —
      there is nothing to reset on a row that was never reminded yet.
    - get_site_visits_for_tomorrow(): rewritten to SELECT
      v.reminder_sent_at directly instead of the old correlated LIKE
      scalar subquery — simpler query, no subquery at all now.
      get_pending_reminder_count() needed no change — it already just
      calls this function and checks the same field name.
  Verified via a throwaway copy of live CLS1.db: backfilled values match
  the old LIKE-based lookup exactly for every existing tomorrow's-visit
  row; sending a reminder sets reminder_sent_at AND still writes the
  activity_log row; rescheduling that same visit resets reminder_sent_at
  to NULL and the visit correctly shows pending again for its new date;
  rescheduling a visit that was never reminded is a no-op, no errors.
v2.68 (2026-08-19) — Dashboard fix Part 1: two indexes targeting the two
  worst bottlenecks found in the Dashboard slowness diagnosis session
  (F1/F2-style audit, this time targeting Dashboard stat-card queries
  rather than lead-list queries). ONE of the two confirmed fixed; the
  other's index was added but is NOT actually used by SQLite's query
  planner at this table's current size — see honest writeup below,
  this is not being oversold as "fixed" when it measurably isn't:
    - idx_call_log_matched_direction_ts ON call_log_staging(matched_cls_id,
      direction, call_timestamp) — CONFIRMED FIX. get_missed_calls_count()'s
      outer WHERE (m.direction='MISSED' AND m.matched_cls_id IS NOT NULL)
      and its correlated NOT EXISTS subquery (o.matched_cls_id =
      m.matched_cls_id AND o.direction='OUTGOING' AND o.call_timestamp >
      m.call_timestamp) previously both fell back to SCAN on
      call_log_staging (56k rows), with the subquery re-scanning the full
      table per outer row — O(n^2) against the largest table in the DB.
      EXPLAIN QUERY PLAN now shows SEARCH...USING COVERING INDEX for both
      the outer query and the correlated subquery. Measured 16,415ms ->
      ~19-22ms steady-state on live CLS1.db (owner=None), a single
      one-off 1.8s run observed during the very first post-index query
      (index pages not yet in OS page cache) and not reproduced on any
      later run. Column order (matched_cls_id, direction, call_timestamp)
      chosen to serve the correlated subquery's exact
      equality-equality-range predicate directly, and to let the outer
      query's JOIN to leads probe this same index by matched_cls_id.
    - idx_leads_reengaged_at ON leads(reengaged_at) — ADDED, PLANNER DOES
      NOT USE IT. get_reengaged_count()'s WHERE reengaged_at IS NOT NULL
      still shows SCAN leads in EXPLAIN QUERY PLAN even with this index
      present, including after a diagnostic ANALYZE (run, checked, then
      reverted — no ANALYZE/sqlite_stat1 persisted by this change).
      SQLite's cost-based planner judges a full sequential scan of the
      leads table (8,044 rows, small) cheaper than an index seek + rowid
      lookup, which is a legitimate, correct call at this table size, not
      a bug in the index. A controlled A/B test (same warm-cache
      conditions, index present vs. DROP INDEX'd) showed IDENTICAL timing
      either way (~12-30ms) — meaning the diagnosis session's original
      404ms reading was a cache-state artifact of that specific run, not
      a reproducible cost of the SCAN itself. Net effect: get_reengaged_
      count() is already fast in steady state (~20-50ms) regardless of
      this index; the index is harmless and kept (may earn its keep if
      the leads table grows much larger and reengaged_at stays a small
      fraction of it), but is not, today, "the fix" for anything.
      Added in the same post-migration-loop location as idx_leads_owner
      (v2.65) since reengaged_at, like lead_owner, is only added via the
      self-healing ALTER TABLE loop, not the original CREATE TABLE —
      creating the index earlier would fail "no such column" on a fresh
      DB, same failure mode v2.65 already fixed once for idx_leads_owner.
  Both additions only — no existing index, query, or function signature
  touched; both COUNT(*) results verified identical before/after (271 and
  10 respectively). get_pending_reminder_count() (bottleneck #2, 509ms,
  part of inject_current_user() on every page load) is explicitly OUT OF
  SCOPE here — deferred to a follow-up session per Srikanth's
  instruction, its fix is a query/lookup rewrite, not an index.
v2.67 (2026-08-18) — F2 Phase 3: read-side SQL filtering on
  project_bucket. Every function that used to derive project_bucket
  per-row in Python via get_project_bucket() (after F2 Phase 1/2 made
  it a real, kept-in-sync leads column) now reads/filters it straight
  from SQL instead:
    - _build_lead_filter_where() gained project=None — when given,
      appends "AND project_bucket = ?" to the shared WHERE clause used
      by get_leads_page() and get_leads_matching(). None (default) is a
      no-op, so no other caller/behavior changes.
    - get_leads_page() / get_leads_matching() — project_bucket now
      SELECTed directly and the filter passed into
      _build_lead_filter_where(); removed the old fetch-everything,
      attach-project_bucket-per-row-in-Python, then filter-in-Python
      pattern entirely.
    - get_lead_by_id() — removed a redundant get_project_bucket() call;
      its SELECT * already returns the stored column.
    - get_bulk_job_lead_rows() — project_bucket now SELECTed directly
      (l.project_bucket) instead of computed per row after the fetch.
    - get_project_pipeline() — SELECTs project_bucket directly instead
      of project, uses it as the GROUP BY key with no per-row
      get_project_bucket() call.
    - get_stage_breakdown() — _STAGE_BREAKDOWN_GROUP_COLUMNS["project"]
      now points at "project_bucket" instead of "project"; the
      group_by=="project" branch uses the already-bucketed value
      directly (falsy-value fallback kept, defensive only — the column
      is never expected to be NULL/blank given F2 Phase 1/2 backfill +
      sync).
  Rationale: SQL-level filtering + idx_leads_project_bucket (added
  F2 Phase 1) index usage instead of full-table-scan-then-filter in
  Python — same motivation as the F1 index audit. No external function
  signature or parameter changed; every caller (app.py routes,
  templates) sees identical call shape and identical result shape.
  Verified via a throwaway-copy comparison against the OLD Python-side
  filtering logic for get_leads_page()/get_leads_matching(), both with
  and without a project filter — exact row-for-row match; see session
  notes. ADDITIVE/REFACTOR ONLY — no schema change, ordinary behavior
  for every caller is byte-for-byte unchanged. F2 is now complete (all
  3 phases: stored column, alias-change recompute, read-side SQL
  filtering).
v2.66 (2026-08-18) — F2 Phase 2: recompute leads.project_bucket on alias
  add/delete. NEW _recompute_all_project_buckets() — full pass over every
  DISTINCT leads.project value, bucket computed via get_project_bucket()
  (reused directly, not reimplemented), one grouped UPDATE per distinct
  value (NULL handled via its own "IS NULL" branch, since "project=NULL"
  never matches in SQL; blank-string values need no special case). Called
  from BOTH add_project_alias() and delete_project_alias(), always AFTER
  reload_project_bucket_cache() so get_project_bucket() sees the fresh
  alias mapping during recompute. Exceptions propagate uncaught — this
  runs synchronously inside an admin action, so a failure must surface
  to the admin rather than leave leads silently out of sync. Verified
  against a throwaway copy of CLS1.db (add-alias repoints matching leads
  to the new bucket, delete-alias falls them back to raw name/other
  alias per get_project_bucket()'s documented fallback, unrelated raw
  project values untouched) — see session notes. Not yet run against
  live CLS1.db/CLS2.db as of this commit; the live /settings/projects
  screen will trigger it automatically on the next real alias edit, no
  separate live-DB step needed. ADDITIVE ONLY — nothing existing removed
  or modified. Phase 3 (read-side SQL filtering on project_bucket) is
  explicitly NOT part of this change.
v2.65 (2026-08-18) — Fixed idx_leads_owner creation ordering — moved
  after lead_owner column migration to prevent failure on a genuinely
  fresh database (bug introduced in v2.63/F1). idx_leads_owner used to
  run immediately after CREATE TABLE leads, alongside idx_phone/idx_
  email/idx_leadgen/idx_leads_stage/idx_leads_created — but lead_owner
  is not part of the original CREATE TABLE, it's added later via the
  drip_migrations self-healing ALTER TABLE loop. On a brand-new/empty
  database this made init_db() fail with "no such column: lead_owner".
  Silent in production only because CLS1.db/CLS2.db already had lead_
  owner from prior runs. idx_leads_stage and idx_leads_created were NOT
  moved — both are genuinely part of the original CREATE TABLE, no
  issue there. ADDITIVE ONLY — nothing existing removed or modified,
  purely a reordering of one CREATE INDEX statement.
v2.64 (2026-08-18) — F2 Phase 1: stored leads.project_bucket column.
  NEW self-healing ALTER TABLE (leads.project_bucket TEXT) + idx_leads_
  project_bucket index, both in init_db(). NEW one-time-per-row backfill
  (also in init_db(), runs on every call but only touches rows where
  project_bucket IS NULL, so it's safe to leave permanently) — computed
  inline against the SAME open connection/transaction as the rest of
  init_db() rather than by calling get_project_bucket() itself, because
  that function opens its own connection via _connect() and would not
  see this transaction's own uncommitted project_aliases seed rows /
  schema changes on a truly fresh DB. Every known write path to
  leads.project is now kept in sync in the SAME transaction as its own
  write (no separate round-trip): create_manual_lead() (INSERT),
  upsert_meta_lead() (all 3 branches — leadgen_id-refresh UPDATE,
  contact-match-enrich UPDATE, brand-new INSERT), upsert_selldo_lead()
  (existing-row UPDATE, brand-new INSERT — still synced even though its
  only production caller, selldo_to_cls.py/Job B, is retired, because
  the function itself remains live infrastructure exercised by this
  file's own --selftest; confirmed with Srikanth before touching
  anything Job-B-adjacent), and import_selldo_csv_row() (brand-new
  INSERT only — its matched/existing branch deliberately never touches
  project, so project_bucket is correctly left untouched there too).
  Migration applied to both CLS1.db (8038 leads, 0 NULL project_bucket
  after) and CLS2.db (7973 leads, 0 NULL after) this session, 5-row
  spot-check clean on both. ADDITIVE ONLY — nothing existing removed or
  modified. Phase 2 (alias-change recompute hook) and Phase 3 (read-
  side SQL filtering on project_bucket) are explicitly NOT part of this
  change — the column exists and stays in sync, nothing reads it yet.
v2.63 (2026-08-18) — F1 (audit): added idx_leads_stage, idx_leads_owner,
  idx_leads_created on leads table. Fixes full table scan on every
  /leads page load (original "1-2 min" complaint). Verified via
  EXPLAIN QUERY PLAN against live CLS1.db — see session notes.
v2.62 (2026-08-18) — P3-4 — removed direct_set_stage_reconciliation,
  orphaned after cls_reconcile_apply.py deletion, zero callers confirmed.
  Audit cleanup per CLS_AUDIT_REPORT.md Pass 3, explicit delete (not
  paused) per Srikanth. Nothing else removed or modified.
v2.61 (2026-08-17) — Monday Weekly Report: per-salesperson breakdown. NEW
  get_monday_weekly_report_by_owner(week_start, week_end) — companion
  to get_monday_weekly_report_stats() (v2.60), same 4 underlying
  metrics (leads generated, site visits scheduled/conducted, bookings)
  but grouped by CURRENT lead_owner instead of summed company-wide.
  Bookings shown as a single combined total per owner, not split
  weekday/weekend — Srikanth confirmed 2026-08-17 that split only
  matters at company level. Owner attribution is today's lead_owner,
  same convention as get_bookings_by_owner_for_period()/get_leads_by_
  owner_for_period() (events aren't ownership-snapshotted at the time
  they occurred). For cls_monday_weekly_report.py's new Per Salesperson
  section. ADDITIVE ONLY — nothing existing removed or modified.
v2.60 (2026-08-17) — Monday Morning Weekly Report. NEW
  get_monday_weekly_report_stats(week_start, week_end) — 5 headline
  numbers (leads generated, site visits scheduled, site visits
  conducted, bookings weekday/weekend) for the most recently completed
  Mon-Sun week, for the new cls_monday_weekly_report.py ops script.
  site_visits_scheduled deliberately uses site_visits.created_at
  (scheduling activity within the week), not scheduled_at, so it pairs
  with site_visits_conducted as a same-week funnel (Decision A,
  confirmed by Srikanth 2026-08-17). bookings_weekday/weekend reuse the
  EVENT-count definition (activity_log stage_change -> Booked) already
  established by get_booking_summary_totals() (v2.31) — same reasoning,
  just split by strftime('%w', created_at) instead of summed. ADDITIVE
  ONLY — nothing existing removed or modified.
v2.59 (2026-08-17) — Weekend Site Visits Report. NEW
  get_weekend_site_visits(owner_match_name=None) — site visits scheduled
  for the upcoming Saturday+Sunday, same query shape and owner-scoping
  convention as get_site_visits_for_tomorrow() (v2.14), just swapping
  the date filter for SQLite's 'weekday 6' modifier (jumps to the next
  Saturday, or stays put if today IS Saturday) so it returns the
  correct weekend regardless of which day it's run on. No Sell.do-side
  check needed — Sell.do was fully retired 2026-08-18 (see v2.57's
  changelog), so site_visits is the sole, authoritative source for
  scheduling now. ADDITIVE ONLY — nothing existing removed or modified.
v2.58 (2026-08-16) — Task 3 Part B: Today's Agenda subsection. NEW
  get_todays_agenda(owner=None) — site visits and follow-ups scheduled
  for TODAY specifically (DATE(scheduled_at) = DATE('now'), status=
  'scheduled' only), returned as {"site_visits": [...], "follow_ups":
  [...]} for the new Today's Agenda block on dashboard_today.html.
  Deliberately separate from get_due_today()/get_due_by_kind() (which
  are <=today, overdue-inclusive) — copied their query structure/join
  pattern directly, only the date comparison changed (<= to =), so the
  two stay easy to compare. ADDITIVE ONLY — nothing existing removed
  or modified.
v2.57 (2026-08-16) — Task 3 Part A: dashboard metrics, lead_reengaged
  logging, New Enquiries bug fix. Job B (selldo_to_cls.py) is
  permanently retired as of 2026-08-18 — Job A (upsert_meta_lead()) is
  the only automated lead-entry path now.
    - BUG FIX: get_new_enquiries_count()/get_new_enquiries_leads() —
      silent undercounting since v2.28. The WHERE clause's "zero
      activity_log rows" test relied on an assumption that stopped
      being true the moment v2.28 gave upsert_meta_lead()'s branch 3
      a 'lead_entered' activity_log row on every genuinely-new insert;
      after that, "zero activity_log rows" could never be true for new
      intake, so the count silently degraded toward 0. Replaced with
      reengaged_at IS NULL — the same new-vs-repeat distinction
      upsert_meta_lead() already draws via _apply_reengagement_marker().
      Both functions' signatures unchanged, only the WHERE clause.
    - NEW: get_no_future_activity_count(owner=None) /
      get_no_future_activity_leads(owner=None) — open-pipeline leads
      (current_stage not in RESET_STAGES_ON_REENGAGEMENT, reused
      rather than a new literal tuple) with no scheduled site visit and
      no scheduled follow-up. Live-computed, same posture as
      get_reengaged_count().
    - NEW: get_missed_calls_count(owner=None) / get_missed_calls_list
      (owner=None) — call_log_staging MISSED rows with no later
      OUTGOING call to the same matched_cls_id. Scoped via the lead's
      CURRENT lead_owner (not call_log_staging.user_id) so a missed
      call always shows against whoever owns the lead right now, even
      after reassignment.
    - NEW: upsert_meta_lead()'s branch 2 (contact-match/enrich path)
      now logs one 'lead_reengaged' activity_log row immediately after
      _apply_reengagement_marker(), using the SAME `now` variable
      already stamped onto reengaged_at (not a fresh _now() call) —
      required so get_reengaged_count()/get_reengaged_leads()' "cleared
      the moment created_at > reengaged_at" rule doesn't immediately
      clear a lead off the Reengaged card just because this row exists.
      _apply_reengagement_marker() itself is unchanged (still just
      stamps reengaged_at/resets stage) — its signature was deliberately
      NOT expanded to take phone_raw/email_raw/meta_campaign_name, so
      the log call lives in upsert_meta_lead() where those are already
      in scope; see that helper's docstring for the reasoning.
  ADDITIVE ONLY except the Change 1 WHERE-clause fix described above —
  nothing else existing removed or modified.
v2.56 (2026-08-15) — Meta App Review screencast support: isolated
  test-lead viewer, no writes to production `leads` table, no
  interaction with Job A/B/C. NEW (additive): webhook_test_leads table
  (self-healing CREATE TABLE IF NOT EXISTS, init_db()), NEW
  log_webhook_test_lead(raw_payload) — best-effort leadgen_id/form_id/
  page_id extraction, never raises, stores the full raw payload — and
  NEW get_webhook_test_leads(limit=50). This is the ONLY new write path
  this version adds; nothing existing removed or modified.
v2.55 (2026-08-14) — capi_fire_queue table + queue functions, for
  inline CAPI firing redesign. Retires selldo_sync gate dependency
  since Job B is permanently stopped. NEW (additive): capi_fire_queue
  table (self-healing CREATE TABLE IF NOT EXISTS), MAX_QUEUE_ATTEMPTS
  constant, queue_failed_fire(), get_due_retries(), clear_from_queue(),
  bump_queue_attempt().

  NOT purely additive — one existing function's return signature
  changed, confirmed with Srikanth first: upsert_meta_lead() now
  returns (cls_id, is_new_lead) instead of bare cls_id on all three
  branches (was: identical `return cls_id` on every branch, giving
  callers no way to tell a genuinely-new insert from a leadgen_id
  refresh or a contact-match enrich). is_new_lead is True only on
  branch 3 ("genuinely new lead — insert"), False on branches 1 and 2.
  This mirrors the existing (cls_id, stage_changed) pattern
  upsert_selldo_lead() already uses in this same file. Exactly one
  production caller exists (meta_leads_fetcher.py:582, updated to
  meta_leads_fetcher.py v1.8 in the same batch) plus this file's own
  2 --selftest call sites (updated below). No other logic inside
  upsert_meta_lead() changed — same three branches, same SQL, same
  every-other-parameter behavior.
v2.54 (2026-08-14) — Added get_lead_by_crm_no() and
  direct_set_stage_reconciliation() — one-time parallel-run reconciliation
  support. Bypasses STAGE_TRANSITIONS deliberately for this one script
  only — see cls_reconcile_apply.py docstring for why. ADDITIVE ONLY,
  nothing existing removed or modified. direct_set_stage_reconciliation()
  logs its activity_log row via the existing _log_activity() helper
  (same atomic-with-the-write pattern update_lead_stage() already uses)
  rather than a raw INSERT, so it can't drift from that table's real
  column set.
v2.53 (2026-08-11) — Phase 5 of the 6-phase feature batch. NEW
  bulk_job_leads table (init_db(), self-healing CREATE TABLE IF NOT
  EXISTS) — per-job cls_id snapshot. NEW record_bulk_job_leads(job_id,
  cls_ids, conn=None) and get_bulk_job_lead_rows(job_id).
  NOT purely additive — two EXISTING functions changed, confirmed with
  Srikanth first (see Phase 5's "atomicity approach" decision):
    - create_bulk_job(): gained optional cls_ids=None, conn=None params
      and now RETURNS job_id (previously returned nothing). When cls_ids
      is passed, it calls record_bulk_job_leads() inside its OWN
      transaction before committing, so a bulk_jobs row can never exist
      without its snapshot (or vice versa). Every existing caller (there
      was exactly one, app.py's settings_bulk_reassign_commit()) passed
      neither new param and ignored the return value — behavior for
      those call sites is unchanged until app.py is updated to use them.
    - get_bulk_jobs(): now LEFT JOINs a per-job leads_snapshot_count
      (COUNT of bulk_job_leads rows) onto each returned dict. All
      existing keys/behavior unchanged, this only adds one new key.
v2.52 (2026-08-11) — Phase 4 of the 6-phase feature batch, ADDITIVE ONLY:
  NEW get_calls_made_today(), get_site_visits_scheduled_today(),
  get_site_visits_conducted_today(), get_follow_ups_scheduled_today(),
  get_follow_ups_completed_today() — row-level drill-downs behind the
  Today's Performance tab's 5 stat tiles, each actor_email-scoped (like
  get_todays_activity_counts(), which the tiles themselves already call),
  backed by a shared private _activity_rows_today() helper. Deliberately
  NOT reusing the existing owner-scoped get_site_visits_conducted()
  (Export) for the Site Visits Conducted drill-down — different scoping
  key (actor vs. lead_owner) that could disagree with that tile's own
  count. Nothing existing removed or modified.
v2.51 (2026-08-09) — Nine-item batch, ADDITIVE ONLY, nothing existing
  removed or modified except the four call sites named below:
    - get_today_attendance_overview(date_str): active-users query now
      excludes role='admin' — admin shouldn't appear in "who's present
      today," same posture as get_attendance_totals_for_month() below.
    - get_attendance_totals_for_month(): owner_scope=None branch's
      active-users query now excludes role='admin' too, for the same
      reason. owner_scope=<user_id> branch (a specific person, incl.
      an admin drilling into their OWN record on purpose) is untouched.
    - _build_lead_filter_where()'s search-term classification rewritten:
      "#"/"apx-" prefix now does an EXACT match on crm_lead_no (was
      LIKE); an all-digits term (no prefix) now matches phone_norm
      ONLY, no name/email; anything else keeps the existing combined
      name/phone/email LIKE. Closes the LIKE-on-lead-id gap (e.g. "#2"
      used to also match lead 20/200/...) and stops an all-digits
      search accidentally hitting name/email columns.
    - compute_punch_in_timing() now reads the NEW module constants
      WORKDAY_START_TIME/WORKDAY_END_TIME instead of app_settings
      ['attendance_late_after_time'] — one less DB round-trip per
      punch, and a value Srikanth can see and reason about directly in
      code. The app_settings row itself is left in place, untouched,
      unread by anything now — killing it is a separate decision.
    - NEW WORKDAY_START_TIME = "10:30", WORKDAY_END_TIME = "17:30"
      module constants (config-not-code, same idiom as
      ATTENDANCE_STATUSES) — WORKDAY_END_TIME doesn't drive any logic
      yet, added now so item 7 below and any future "workday" feature
      share one definition.
    - NEW get_todays_achievements(user_id): self-scoped "Daily
      Achievements" summary for the logout interstitial (see app.py
      v0.42's changelog) — get_todays_activity_counts()'s own-actions
      dict plus today's stage_change count (activity_log, actor=this
      user's email) and total time worked today (today's attendance
      row's logout_ts-login_ts, "still working" if logged in but not
      out yet, key omitted entirely if no attendance row exists today
      — e.g. roles that don't punch). Deliberately no "time spoken to
      customers" metric — no call-duration data exists pre-Telephony,
      same honest limit get_todays_activity_counts() already documents.
v2.50 (2026-08-07) — Manager view-mode toggle. Mounika is a player-coach
  (manager role, but also carries her own leads) — she needs to flip her
  OWN default leads/dashboard view between "team-wide" (today's unchanged
  manager behavior) and "own-leads-only" (see her pipeline the way a
  salesperson would), without touching her role, write access, or report
  access, all of which stay exactly as can_view_all_leads()/
  can_write_any_lead()/WRITE_ANYWHERE_ROLES already define them.
  ADDITIVE ONLY, nothing existing removed or modified:
    - Self-healing migration: `view_mode TEXT DEFAULT 'manager'` on
      users (guarded PRAGMA table_info check, same idiom as v1.7's
      owner_match_name / v2.38's assigned_project). DEFAULT 'manager'
      means every existing row — including every current admin and
      salesperson row, for whom this column is simply unused — keeps
      today's behavior with zero action required.
    - NEW get_view_mode(user): 'individual' only for role=='manager'
      AND view_mode=='individual' on that row; 'manager' for every
      other case (wrong role, unset, or any unexpected column value).
      Fails closed to the wider "manager" default, same posture as
      can_view_all_leads()'s own fail-closed-to-most-restricted
      docstring — except here "restricted" and "default" are the same
      value (company-wide), since this column only NARROWS an
      oversight role's own view, it never widens anyone's.
    - NEW effective_company_wide(user): can_view_all_leads(user["role"])
      AND get_view_mode(user) != 'individual'. This is the ONE new
      function app.py's view-SCOPING call sites (dashboard/leads-list/
      etc.) now call in place of can_view_all_leads(user["role"]) —
      see app.py v0.41's changelog for exactly which call sites did and
      did NOT change. can_view_all_leads() itself is completely
      unmodified and is still what every WRITE/ACCESS gate should keep
      using.
    - NEW set_view_mode(user_id, mode): validates mode is 'manager' or
      'individual'; no-ops (returns False) unless the target row's role
      is 'manager' — deliberately not settable for admin/salesperson
      rows even by direct call, so this column can never mean anything
      for a role other than manager. Returns True iff updated.
  Every pre-existing caller of can_view_all_leads()/can_write_any_lead()
  is byte-for-byte unaffected — this version adds three new functions
  and one new column, nothing else.
v2.49 (2026-08-07) — Surface call direction (incoming/outgoing) on
  recorded calls. Direction was already captured by the app and staged
  on call_log_staging.direction (v2.33) but dropped before reaching
  activity_log — log_call_recording() had nowhere to put it, so
  lead_detail.html had nothing to render. ADDITIVE ONLY: nullable
  `direction TEXT` column on activity_log (same guarded PRAGMA
  table_info migration pattern as the v2.33 trio). _log_activity()
  gains a `direction=None` param, passed through to the INSERT.
  log_call_recording() gains a `direction=None` param. NEW
  get_call_direction(cls_id, call_timestamp): looks up
  call_log_staging.direction by the same (matched_cls_id,
  call_timestamp) key record_call_log_entry() staged it under — used
  only by app.py's api_telephony_upload_recording() (requires app.py
  v0.40). Every pre-existing caller/row is unaffected.
v2.48 (2026-08-07) — Diagnostic-only companion to verify_api_token(),
  for the 401-with-zero-trace gap found while investigating Elohar/
  Devender's token failures. NEW diagnose_api_token_failure(raw_token):
  called ONLY from token_required's rejection path in app.py, ONLY
  after verify_api_token() has already returned None — never used to
  grant access, never returns the token or its hash, just a short
  reason string. Designed against the Option C generate/revoke split
  (v2.47 below): a token's own row going inactive no longer always
  means "regenerated" — revoke_api_token() also sets active=0 but,
  unlike generate_api_token(), deliberately does NOT insert a
  replacement. Distinguishes "superseded by a newer active token"
  (this user already has a working token from a later sync) from
  "revoked, no replacement yet" (needs a Sync-my-token tap) by
  checking whether any active row currently exists for the user.
  user_active is checked before token_active, so a deactivated CRM
  login is reported as that rather than misattributed to a token
  problem when both happen to be true. Additions only —
  verify_api_token()/generate_api_token()/revoke_api_token() are all
  unchanged.
v2.47 (2026-08-07) — Telephony token architecture change (Option C,
  self-service "Sync my token"): ADDITIVE ONLY, nothing existing
  removed or modified. Root cause this replaces: manual admin token
  generation + voice-relay to employees, which failed twice in one
  morning (a token silently invalidated by a same-day re-regeneration
  before the employee could use it; a token accidentally pasted into
  the wrong settings field). NEW revoke_api_token(user_id): admin
  "Revoke Token" kill-switch for Settings > Telephony (lost phone /
  departing employee) — deactivates the user's current active token
  WITHOUT minting a replacement, so there is no new token to relay.
  Deliberately duplicates the 2-line "deactivate current active
  token" UPDATE already inside generate_api_token() rather than
  refactoring generate_api_token() to share a helper — generate_api_
  token() itself is untouched, per this file's additions-only change
  posture. The employee's own next "Sync my token" tap in the app
  (new POST /api/my-token route, app.py) calls the EXISTING, unchanged
  generate_api_token() to mint their own fresh token — no separate
  DB-layer change needed for that side of the flow.
v2.46 (2026-08-06) — APX Attendance Chunk C: admin-only "who's present
  today" view + proactive exemption (additions only). Requires app.py
  v0.37 for the 2 new routes wiring these in.
  NEW get_today_attendance_overview(date_str): every ACTIVE user
  LEFT JOINed to their attendance row for that date (none silently
  omitted, same convention as get_attendance_totals_for_month()'s
  owner_scope=None branch). Returns the RAW status value when a row
  exists (present/late/absent/weekoff/leave/half_day — not collapsed
  to a smaller bucket set) plus a not_marked flag when no row exists
  yet, so "hasn't punched" renders distinctly from a recorded 'absent'.
  NEW apply_admin_attendance_exemption(user_id, date_str, field_changed,
  new_value, note, actor): proactive admin override that does NOT
  require a pending attendance_corrections row to exist first — chains
  the EXISTING create_correction_request() (validate+insert) straight
  into the EXISTING resolve_attendance_correction() (approve+write) on
  the row it just created, with NEITHER existing function modified in
  any way. The row is created and resolved in the same call, so it
  never sits pending — nothing left to duplicate or collide with. See
  the function's own docstring for one flagged (not fixed) pre-existing
  race if an employee has a separate pending request on the same field
  at the same time.

v2.45 (2026-08-06) — APX Attendance Chunk B: Weekoff/Leave rebuilt as
  range-capable, duplicate-protected self-service (additions only).
  NEW TABLES (additive, self-healing CREATE TABLE IF NOT EXISTS):
  weekoff_log (id, user_id, date, submitted_at) and leave_requests (id,
  user_id, start_date, end_date, submitted_at) — one leave_requests row
  per CONTIGUOUS date range, not one row per day (dates given as a flat
  list from the UI's multi-select calendar are grouped into contiguous
  runs by the new _group_contiguous_dates() helper). No status/approval
  column on either table by design — a row's existence means approved
  (auto-approved on submit, no admin step in this chunk).
  NEW submit_weekoff(user_id, date_str, actor) / submit_leave(user_id,
  dates, actor): both do a READ-ONLY validation pass FIRST (duplicate
  weekoff_log row, overlapping leave_requests range, cross-conflict
  between the two, plus the EXISTING punch-data/conflicting-status
  feasibility rule via new _can_self_service_mark() dry-run helper) —
  only if every check clears does either function write anything, and
  the write order is: sync attendance.status via the EXISTING
  set_self_service_attendance_status() first (so the Dashboard/export/
  today-badge these already read from keep working with zero Chunk C
  changes), THEN insert the weekoff_log/leave_requests row last. Any
  single failure returns before any write happens — no partial saves.
  This intentionally supersedes the v2.39 Weekoff/Leave UI entry point:
  app.py's OLD attendance_weekoff/attendance_leave routes are PAUSED
  (commented out, not deleted) in the same v0.36 change, since leaving
  them live would let a submission bypass all of the above. NOTHING
  else about set_self_service_attendance_status() itself changed — it
  is reused as-is, unmodified, by both new functions above.

v2.44 (2026-08-04) — Leads List Pipeline Stage filter, radio -> checkbox
  multi-select. get_leads_page() gained a NEW stages=None param (list,
  optional), passed straight through to the EXISTING _build_lead_filter_
  where() call inside it — that function already accepted/handled stages
  (v2.30, added for Bulk Reassign/Export), so no change there. ADDITIVE
  ONLY: the existing single-value stage= param and every current caller
  of get_leads_page() are untouched (default stages=None => no filter
  narrowing, identical to before this version). app.py's leads_list()
  route change to pass f["stages"] is reported alongside this one.

v2.43 (2026-08) — BASE_DIR updated from C:\CLS to D:\CLS — drive migration, 2026-08.

v2.42 (2026-08-02) — APX Attendance v0.9 pilot: token-auth API business
  logic (Build Order Step 4 of the v0.9 spec), additions only, plus one
  stale comment corrected (see below — not a schema/behavior change).
  New import: math (stdlib, for check_geofence_breach()'s haversine
  distance — no new dependency).
  - get_attendance_project_location(project_bucket) / check_geofence_
    breach(project_bucket, lat, lng): haversine distance vs the
    configured radius. Returns False (no breach) whenever there's
    nothing to compare against — no assigned project, no configured
    location, missing lat/lng — NEVER blocks; a breach is a flag for
    admin review only, per the v0.9 spec's explicit rule.
  - compute_punch_in_timing(punch_dt): status ('present'/'late') +
    late_minutes vs app_settings['attendance_late_after_time'] (v2.38
    seed '10:00'). Falls back to 10:00 if the setting is missing/
    malformed rather than failing the punch.
  - record_punch(user_id, direction, date_str, ts, lat, lng, breach,
    photo_path, status, late_minutes): upserts the attendance row for
    (user_id, date_str) — same-day re-punch is an UPDATE (the v2.38
    schema's documented UNIQUE constraint, now actually wired up). A
    punch-out with no existing row still creates one (status stays
    NULL) rather than being rejected.
  - record_location_ping(user_id, lat, lng, ts): accepted ONLY when
    that user has an OPEN attendance row today (login_ts set, logout_ts
    NULL) — silently no-ops (returns False) otherwise, per spec.
  - set_fcm_token(user_id, fcm_token): stores/replaces a push token.
    Does NOT send anything — send_fcm_push() itself is the separate,
    later FCM-wiring build-order step (needs Srikanth's one-time
    Firebase project setup first).
  - Corrected user_api_tokens' schema comment in init_db() (v2.33
    Telephony block): it said "2 telephony API endpoints"; as of this
    version the SAME token also gates the 4 new attendance endpoints —
    comment-only, no schema or behavior change.
  No route work here — that's app.py's v0.30 change, done and reported
  alongside this one.

v2.41 (2026-08-02) — APX Attendance v0.9 pilot: admin Dashboard data
  function (Build Order Step 3 of the v0.9 spec), additions only.
  New get_attendance_totals_for_month(year, month, owner_scope=None) —
  per-user present/late/absent/weekoff/leave/half_day counts + a
  geofence-breach count, for the Dashboard's totals row/table.
  owner_scope=None returns every active user including zero-attendance
  ones (never silently omitted); owner_scope=<user_id> scopes to one
  user regardless of active flag. Per-employee calendar detail reuses
  the EXISTING get_attendance_month() (v2.39) unchanged — no new
  function needed for that half of the Dashboard. No schema change
  this step. No route/export work here — that's app.py's v0.29 change,
  done and reported alongside this one.

v2.40 (2026-08-02) — APX Attendance audit column, additions only,
  nothing existing removed or modified beyond the two write paths
  named below. Self-healing ALTER TABLE attendance ADD COLUMN
  last_modified_by TEXT (same PRAGMA table_info-check pattern as
  v2.38's users.assigned_project). Wired into the two functions that
  can change a day's status/times outside the Step 4 punch-in/out API:
  set_self_service_attendance_status() (Weekoff/Leave — writes actor
  on both the insert and update paths) and resolve_attendance_
  correction() (writes actor on the attendance row when a correction
  is approved; rejecting still writes no attendance change, unchanged).
  Flagged after Step 2 as a minor gap, addressed now before Step 3 per
  Srikanth's explicit request. No other functions/tables touched.

v2.39 (2026-08-02) — APX Attendance v0.9 pilot: data-access functions
  (Build Order Step 2 of the v0.9 spec), additions only, nothing
  existing removed or modified except get_all_users_detailed()'s SELECT
  list (additive column, same v2.25 idiom — see its own docstring).
  New: get_attendance_for_date, get_attendance_month,
  set_self_service_attendance_status (Weekoff/Leave, refuses to
  overwrite punch data or a conflicting status), create_correction_request
  + list_attendance_corrections + resolve_attendance_correction (the
  employee correction-request queue, field_changed validated against the
  new ATTENDANCE_CORRECTION_FIELDS allowlist both at request time and
  apply time), list/add/delete_attendance_holiday, list_attendance_
  project_locations + set_attendance_project_location, and
  set_user_assigned_project. Also new config-not-code tuples
  ATTENDANCE_STATUSES, SELF_SERVICE_ATTENDANCE_STATUSES,
  ATTENDANCE_CORRECTION_FIELDS, same idiom as CRM_ROLES/OVERSIGHT_ROLES.
  No schema changes this step — v2.38's tables covered everything Step 2
  needed; no gap found. No route/API work here — that's app.py's v0.28
  change, done and reported alongside this one.

v2.38 (2026-08-02) — APX Attendance v0.9 pilot: schema only (Build Order
  step 1 of the v0.9 spec), additions only, nothing existing removed or
  modified. This is a SIBLING module — own tables, own API prefix (later
  step) — and must never touch leads/activity_log/assignments or any
  Job A-D logic. New tables, all self-healing CREATE TABLE IF NOT EXISTS
  inside init_db(), same idiom as the v2.33 Telephony block just above:
    - attendance_project_locations: one row per project bucket (matches
      project_aliases.project_bucket text, same loose string-match
      convention as owner_match_name/lead_owner elsewhere — no FK).
    - attendance: one row per user per day (UNIQUE(user_id,
      attendance_date) — same-day re-punch is an update, not a dup).
    - attendance_corrections: employee-initiated change requests,
      pending/approved/rejected queue.
    - attendance_holidays: admin-managed holiday calendar.
    - attendance_location_pings: hourly WorkManager pings while punched
      in; a separate future housekeeping script (mirrors cls_backup.py's
      cadence, NOT a Job A-D addition) should purge/archive rows older
      than 90 days — not built this step.
    - user_fcm_tokens: one row per user (INSERT OR REPLACE keyed on
      user_id, same idiom as user_recording_paths), for push-on-
      login/logout to admin-role users (FCM wiring itself is a later
      build-order step, not this one).
  Also: users.assigned_project TEXT (self-healing ALTER, same
  table_info-check pattern as v1.7's owner_match_name) — matches
  attendance_project_locations.project_bucket; set by an admin, not by
  this migration. And two app_settings seed keys via the existing
  INSERT OR IGNORE idiom (never clobbers an admin-set value on re-run):
  'attendance_late_after_time' -> '10:00', 'attendance_default_radius_m'
  -> '1500'. No new roles, no new routes, no API endpoints yet — those
  are later steps in the same v0.9 build order, done and reported on
  separately.

v2.37 (2026-08-01) — New get_leads_created_in_range(date_from, date_to) for
  the Pipeline Analysis dashboard's date-range-aware "Total Leads" tile
  (app.py's dashboard_pipeline() route). Additive only. Same
  substr(cls_created_at, 1, 10) BETWEEN ? AND ? pattern already used by
  list_call_recordings()'s date filter, including that filter's "both or
  neither" convention (no date_from/date_to together -> no filter, i.e.
  all-time count) so it composes cleanly with the existing DATE_PRESETS
  "maximum" preset, whose resolver returns ("", ""). Note: this uses
  leads.cls_created_at, NOT a plain "created_at" column — cls_created_at
  is the same column get_leads_created_today_count() already reads;
  there is no separate "created_at" column on the leads table.
  get_leads_created_today_count() is unchanged and still used by its one
  existing caller (dashboard_pipeline() itself, for the no-query-string
  default).

v2.36 (2026-08-01) — New list_call_recordings(...) for the admin "Synced
  Recordings" report page (app.py's new /settings/telephony/recordings).
  Additive only. Filtered/paginated variant of v2.34's
  list_call_recording_activities() — date range, answered/missed,
  lead_owner, activity_owner (activity_log.actor, an email), and lead-
  name search, with get_leads_page()'s exact pagination shape/style
  (Python-side slice, no SQL LIMIT/OFFSET). No schema change — every
  filter/column this needs already existed on activity_log since v2.33.

v2.35 (2026-07-31) — Bug 2 fix corrected: recover missing recording files
  instead of permanently blocking re-sync. Additions only.
    - call_recording_exists(cls_id, call_timestamp) (v2.34, a plain
      boolean) is REMOVED and replaced by get_call_recording_file_path()
      — same day, never committed/relied upon, so no back-compat concern.
      Root cause: on 2026-07-31, the call_recordings/ folder was
      accidentally deleted from disk (unrelated ops mistake — files only,
      no DB rows touched; see app.py v0.23 changelog). A row-exists-only
      duplicate check would have permanently blocked recovering those
      legitimate recordings via re-sync, since an existing row would
      always look like "already logged," file or no file.
    - New get_call_recording_file_path(cls_id, call_timestamp): returns
      the row's recorded file path (or None), so the caller can check
      whether that file is ACTUALLY still on disk before deciding
      duplicate-vs-recovery.
    - New update_call_recording_file(cls_id, call_timestamp, file_path,
      duration_seconds, matched_phone): UPDATEs the existing row's file/
      duration/matched_phone in place — does NOT insert a new row, so a
      recovered file never recreates the duplicate-row problem this fix
      exists to prevent. created_at/actor are left untouched.

v2.34 (2026-07-31) — Bug 2 fix (duplicate call recordings on repeat sync)
  + privacy-remediation audit tooling. Additions only — nothing existing
  removed or modified.
    - New call_recording_exists(cls_id, call_timestamp): checked by
      app.py's upload-recording route BEFORE any file write, so a retried
      upload (e.g. app crash after a successful upload but before it
      saves its own sync watermark) skips both the disk write and the
      duplicate activity_log row instead of creating a second identical
      one. SUPERSEDED by v2.35 above the same day — see that entry.
    - New list_call_recording_activities() / delete_call_recording_
      activity(activity_id): built for the new cls_call_recording_audit.py
      script, after a confirmed privacy incident where a personal call's
      recording was wrongly attached to a lead (root cause fixed
      separately in android_pilot's MainActivity.kt v0.6). Lists every
      call_recording activity_log row for human review; deletion is
      scoped to activity_type='call_recording' only and is a deliberate,
      explicitly-reviewed exception to activity_log's normal append-only
      posture — never auto-triggered, never a general-purpose deleter.

v2.33 (2026-07-31) — Phase B Telephony: call-recording matching schema.
  Additions only — nothing existing removed or modified. Server-side
  half of the "dumb app, smart server" architecture confirmed after the
  android_pilot Phase A finding (scoped storage doesn't block OEM
  recording-folder access): the Android app reports call-log metadata
  only; this file matches phone numbers against existing leads and
  decides which calls get a recording fetched.
    - Self-healing migration: 3 new nullable columns on activity_log —
      recording_file_path TEXT, duration_seconds INTEGER, matched_phone
      TEXT — for activity_type='call_recording' rows. cls_id and
      created_at (already backdatable via _log_activity's v2.28
      created_at param) were reused as-is; no JSON/payload column
      existed to repurpose, so these 3 were genuinely new.
    - 3 new tables: user_recording_paths (one row per user, admin-set
      OEM folder path), user_api_tokens (per-user hashed bearer token
      for the 2 new telephony endpoints, entirely separate from the
      session-cookie login), call_log_staging (every call-log entry
      reported by the app, matched or not — proves the "no scan
      without a lead match" policy; unmatched numbers are NEVER
      persisted anywhere else).
    - _log_activity() gained 3 optional keyword-only params
      (recording_file_path/duration_seconds/matched_phone), all
      default None — every pre-existing caller unaffected.
    - New functions: get_recording_path/set_recording_path,
      generate_api_token/verify_api_token, record_call_log_entry,
      log_call_recording. Phone matching reuses the existing
      norm_phone()/find_match() — no new normalization logic written.
    - See TELEPHONY_RECORDING_POLICY.md (new, C:\\CLS\\) for the locked
      scope policy this schema enforces, and DPDP note (consent-notice
      mechanics remain a separate open item, not covered by this change).

v2.32 (2026-07-30) — Meta "platform" capture + lead_entered description
  rebuild for Meta-sourced leads (meta_leads_fetcher.py v1.6). Fixes the
  bug where lead_detail.html had no {% elif %} branch for activity_type
  'lead_entered', so it fell through to the generic {% else %} and
  showed the literal string "lead_entered" instead of a description.
    - Self-healing migration: new nullable `meta_platform TEXT` column
      on `leads` (drip_migrations list), same ALTER TABLE ... IF NOT
      EXISTS pattern as the other meta_ columns. Additive only.
    - upsert_meta_lead() gained an optional meta_platform=None param,
      stored on branch 1 (leadgen_id-refresh UPDATE) and branch 3
      (brand-new INSERT) — identical treatment to meta_campaign_id/
      meta_adset_id/meta_ad_id. Branch 2 (Sell.do-only contact-match
      enrich) leaves it untouched, same as the other meta_ fields today.
    - Branch 3's lead_entered description rebuilt from the old
      single-line prose ("Lead entered via campaign 'X' — Name: ...")
      into a labeled, multi-line block — one field per line, in fixed
      order: Lead Source, Leadgen Id, Campaign Name, Adset Name, Ad
      Name, Platform, Lead Name, Lead Contact, Lead Email. Blank fields
      are omitted (same "omit rather than print None" convention as
      before), and Lead Source is always the fixed string "Facebook
      Lead Ads" for this branch. The extra_answers "Also answered — "
      text still appends below the block on its own line, same content
      as before. Scoped to THIS branch (genuinely-new Meta lead) ONLY —
      upsert_selldo_lead()'s and create_manual_lead()'s own lead_entered
      descriptions are untouched, out of scope per Srikanth's
      instruction. activity_log is append-only, so existing
      old-format lead_entered rows are unaffected and still render fine
      under lead_detail.html v9's new generic (description-agnostic)
      template branch.

v2.31 (2026-07-29) — Dashboard owner-scoping fix + "Leads to Booking
  Summary" tab (app.py v0.20).
    - Part A bug fix: get_new_enquiries_count(), get_new_enquiries_leads(),
      get_reengaged_count(), get_due_today(), get_due_by_kind() all gained
      owner=None — same "None = company-wide, a lead_owner string = scoped"
      convention as get_stage_snapshot_counts(owner=None). Previously these
      5 had no owner param at all, so every salesperson dashboard showed
      company-wide counts instead of their own — the same class of gap
      /leads and /leads/<id> were already closed against; these 4 dashboard
      cards + the due_today plumbing behind them were missed at the time.
      ADDITIVE — owner=None preserves every existing call site's behavior
      exactly (all 5 functions still default to company-wide with no arg).
    - Part C additions (NEW functions, nothing existing touched): totals/
      breakdown queries for the new booking-summary report page — see
      "BOOKING SUMMARY (v2.31)" section below for the full list. All take
      (date_from, date_to, project=None, source=None, owner=None) and are
      period-bound (a date range), unlike get_stage_snapshot_counts()'s
      live-snapshot semantics — deliberately NOT reusing that function.
    - NEW config dicts (config-not-code, per house convention):
      SOURCE_DISPLAY_LABELS (raw leads.source value -> human label) and
      SITE_VISIT_STATUS_LABELS (breakdown row label -> site_visits.status
      matching rule) — see their definitions below.

v2.30 (2026-07) — Export rework (app.py v0.18), Task C: stage/owner
  become checkbox multi-select on the Bulk Export screens ONLY.
  ADDITIVE, Export-only — the existing single-value stage/owner string
  params are untouched for every other caller (leads_filter.html's
  regular Leads filter, leads_list(), Bulk Reassign's own filter form,
  which still uses single-value radios).
    - _build_lead_filter_where() gained stages=None / owners=None (both
      lists) — OR-across-selected-values, same pattern as the existing
      campaigns/configuration/property_type/facing multi-selects.
      owners matches case-insensitively (LOWER(lead_owner)=LOWER(?)),
      same convention as the existing single `owner` param.
    - get_leads_matching() gained matching stages=/owners= passthrough
      params. get_leads_page() deliberately NOT touched — nothing calls
      it with these, per Srikanth's "Export-only" instruction.
    - get_site_visits_conducted() gained owners=None (list) — same
      OR-across-selected pattern, independent of its existing single
      `owner` param.

v2.29 (2026-07) — Follow-up to v2.28's Task 2.1: create_manual_lead()'s
  entry-into-CRM row now logs activity_type='lead_entered' (was
  'lead_created_manual') — reverses that version's "leave it, flagged
  not changed" call, per Srikanth's explicit follow-up: all three entry
  paths (Meta/Sell.do/manual) now share the same label. actor and
  description are unchanged (still the salesperson's email / "Manually
  entered by {actor}"). activity_log is append-only — this only affects
  rows written from now on; existing 'lead_created_manual' rows are
  untouched (no migration, none needed).

v2.28 (2026-07) — APX v0.7 batch: Complete Activity History (Task 2) +
  Bulk Reassign (Task 3) + Bulk Export (Task 4) + Lead Age (Task 5).
  ADDITIONS ONLY — nothing existing removed; two functions gained
  additive optional parameters (noted below), every pre-existing call
  site keeps working unchanged.

  Task 2.1 — lead_entered activity logging:
    - _log_activity() gained an optional created_at=None param (falls
      back to _now() exactly as before when omitted) — lets a caller
      backdate an activity row to when the lead actually arrived
      rather than when the write happened.
    - NEW _format_meta_created_time(raw) — parses Meta's
      created_time ('2026-05-21T10:30:00+0530') into CLS's own
      "%Y-%m-%d %H:%M:%S" format (same two-format try/except as
      meta_leads_fetcher.py's newest_meta_time_for_form); falls back to
      _now() if unparseable (display-only value, never used for
      matching).
    - upsert_meta_lead() gained optional extra_answers=None (list of
      {question, answer} dicts, from meta_leads_fetcher.py v1.5's
      extended extract_lead_fields()). Branch 3 (genuinely new lead)
      now writes ONE activity_log row (activity_type='lead_entered',
      actor='system', created_at=the lead's real Meta created_time, not
      Job A's poll time) describing which campaign/adset/ad it came via
      plus name/phone/email (blank pieces omitted), with any custom
      instant-form answers appended as "Also answered — ...". Branches
      1/2 untouched.
    - upsert_selldo_lead()'s INSERT branch (brand-new selldo_only row,
      Job B's own ongoing sync — NOT the historical CSV import, which
      already logs imported_from_selldo) now also writes ONE
      lead_entered row, actor='system'. This is a cls_db.py-only
      change — selldo_to_cls.py (Job B) itself is untouched, since all
      its DB writes already run through this one centralized function.
    - create_manual_lead() already logged an entry-into-CRM row
      (activity_type='lead_created_manual', actor=the salesperson's
      email, description="Manually entered by {actor}") — left as-is
      per Srikanth's "if it already happens, leave it" instruction.
      FLAGGED (not changed): the activity_type string differs from the
      'lead_entered' type the other two paths use — same semantic
      event, different label. Not touched here; surfaced for Srikanth's
      call on whether to unify it later.

  Task 2.2 — WhatsApp send logging:
    - NEW log_whatsapp_sent(cls_id, actor, description) — same
      activity_log-wrapper pattern as the existing log_reminder_sent(),
      distinct activity_type ('whatsapp_sent') so it stays
      distinguishable from that function's 'whatsapp_reminder_sent' in
      a lead's Activity History. Called by app.py's new
      /leads/<cls_id>/whatsapp/send route.

  Task 3 — Bulk Reassign support:
    - NEW _build_lead_filter_where(**filters) — the WHERE-clause
      builder extracted verbatim out of get_leads_page() (same filter
      semantics, byte-for-byte), so it can be shared instead of
      duplicated. get_leads_page() now calls it; behavior unchanged.
    - get_leads_page() and the new _build_lead_filter_where() both
      gained an optional campaigns=None param (list) — OR-LIKE
      multi-select across campaign, same pattern as the existing
      configuration/property_type/facing checkbox filters. The existing
      single-string `campaign` substring filter is untouched; both can
      be used independently.
    - NEW get_distinct_campaigns() — distinct non-blank leads.campaign
      values, for the new checkbox filters (Bulk Reassign + Bulk
      Export).
    - NEW get_leads_matching(**filters) — unpaginated sibling of
      get_leads_page(), same filters (via the shared WHERE-builder) and
      the same Python-side project-bucket filter, but returns every
      matching row instead of one page. Used by Bulk Reassign and Bulk
      Export, which need the full matched set, not a page of it.
    - NEW bulk_jobs table (self-healing CREATE TABLE IF NOT EXISTS):
      job_id, job_type, actor, filters_summary (short human-readable
      string built by the caller, e.g. "Project: Naishka, Stage:
      Prospect → reassigned to Devender Goud" — NOT a JSON dump, so the
      history page needs no second renderer), to_owner, lead_count,
      created_at. job_type is validated against NEW BULK_JOB_TYPES
      whitelist (config-not-code, mirrors SORT_OPTIONS/SOURCE_OPTIONS)
      — currently just ("bulk_reassign",), room for future bulk actions
      to reuse this same table.
    - NEW create_bulk_job(job_type, actor, filters_summary, to_owner,
      lead_count) / get_bulk_jobs() — write/read the history table.
    - reassign_lead_owner() gained an optional conn=None param. When
      given an OPEN connection it reuses it and skips its own commit
      (caller owns the transaction); every existing caller (which omits
      it) behaves byte-for-byte as before — own connection, own commit.
      This is what lets Bulk Reassign's route loop over every matched
      lead inside ONE atomic transaction instead of N separate commits.

  Task 4 — Bulk Export support:
    - NEW get_site_visits_conducted(date_from, date_to, owner) —
      site_visits joined to leads, status='conducted' only, date range
      on conducted_at. Feeds the "Export Site Visits Conducted" sheet.
    - NEW get_activity_log_export(date_from, date_to, cls_id) —
      activity_log joined to leads (cross-lead + date-ranged, unlike
      the existing single-lead get_activity_log_for_lead()). Feeds the
      "Export Activity History" sheet.
    - No new export mechanism — app.py's export routes shape these
      (and get_leads_matching()'s) rows into the same {columns, rows}
      dict cls_reports.build_report() already produces, then hand it to
      cls_reports.export_to_excel() unchanged.

  Task 5 — Lead age display:
    - get_leads_page() rows gain age_days: whole days since
      cls_created_at, computed only for the current page's rows (cheap,
      same "only the rendered rows" scoping as lead scoring). None for
      any lead whose current_stage is in DRIP_TERMINAL_STAGES (Booked /
      Lost / Unqualified) — reuses that existing constant rather than a
      second hardcoded copy of the same three strings, per Srikanth's
      instruction.

v2.27 (2026-07) — Meta ad/campaign metadata capture:
  Added meta_campaign_id, meta_campaign_name, meta_adset_id,
  meta_adset_name, meta_ad_id, meta_ad_name columns (self-healing
  migration, NULL on pre-existing rows). upsert_meta_lead() now
  accepts and stores all 6 from meta_leads_fetcher.py v1.4+.
  Deliberately kept separate from the campaign column and Campaign
  Routing (campaign_routing_rules, resolve_owner_for_new_lead()) —
  those are unchanged by this version. No change to Job B, no
  destructive ALTER TABLE.

v2.26 (July 2026) — Lead Scoring config GUI (Settings > Lead Scoring,
  Task 4 of the settings-GUI batch, final task). ADDITIONS ONLY —
  nothing existing removed or modified, except compute_lead_scores(),
  whose OUTPUT/SCORING LOGIC is unchanged line-for-line; only its data
  source moved from the module-level LEAD_SCORE_RULES/LEAD_SCORE_BANDS
  constants to get_lead_score_config() (reads app_settings fresh on
  every call — no caching, no restart needed for a config change to
  take effect).

  LEAD_SCORE_RULES / LEAD_SCORE_BANDS are now PAUSED (commented out,
  not deleted) — historical reference only, nothing reads them anymore.

  Reuses the app_settings table (Task 3, v2.25) rather than a second
  key/value table. Seeded ONCE (self-healing INSERT OR IGNORE, never
  clobbers a config Srikanth already tuned via the GUI) from
  _LEAD_SCORE_CONFIG_SEED — byte-for-byte the old LEAD_SCORE_RULES dict
  plus hot_threshold=70/warm_threshold=30, collapsed from LEAD_SCORE_
  BANDS' 3-tuple list. Band labels (Cold/Warm/Hot) stay fixed, not
  stored/editable — Srikanth's simplification call for this first
  version; flagged so full label editing can be requested later if
  wanted.

  NEW get_lead_score_config() / set_lead_score_config(config_dict) —
  the latter validates every required key (stage_points for all 8
  ALL_STAGES, temperature_points, the 5 fixed-point fields, decay
  settings, decay_exempt_stages, hot_threshold, warm_threshold),
  rejects with a clear ValueError message on anything missing or
  non-numeric where a number is expected, and only writes AFTER
  validation passes — an invalid submission never touches the stored
  config.

v2.25 (July 2026) — Campaign Routing (Settings > Campaign Routing GUI,
  Task 3 of the settings-GUI batch). ADDITIONS ONLY — nothing existing
  removed or modified, except upsert_meta_lead()'s signature (gained one
  new OPTIONAL trailing parameter, campaign=None — every existing call
  site keeps working unchanged) and its branch 3 insert (now also sets
  campaign and derives lead_owner via resolve_owner_for_new_lead()
  instead of the old DEFAULT_OWNER_BY_PROJECT.get() line — branches 2/3
  untouched, exactly mirroring how lead_owner has always been handled).

  NEW campaign_routing_rules + app_settings tables (self-healing CREATE
  TABLE IF NOT EXISTS in init_db()). app_settings is a small generic
  key/value store, seeded once with default_fallback_owner='Mounika
  Peddi' (self-healing INSERT OR IGNORE — never clobbers a value
  Srikanth already changed via the GUI); reused again by Task 4 (Lead
  Scoring config) rather than adding a second settings table.

  DEFAULT_OWNER_BY_PROJECT / FALLBACK_DEFAULT_OWNER are now PAUSED
  (commented out, not deleted) — historical reference only, nothing
  reads them anymore. NOTE: the project-keyed defaults do not carry
  over automatically to campaign-keyed routing rules; equivalent
  routing rules must be configured fresh if wanted.

  NEW resolve_owner_for_new_lead(conn, campaign_name) — takes the SAME
  OPEN CONNECTION the lead insert is happening on, so a round-robin
  next_index increment and the insert commit as one transaction, not
  two racing connections. NEW admin CRUD: list_campaign_routing_rules(),
  upsert_campaign_routing_rule() (rejects invalid rule_type/owner counts,
  resets next_index only when the owners list actually changed — a
  re-save that only flips `active` never resets a live rotation),
  delete_campaign_routing_rule(), get_fallback_owner()/set_fallback_owner(),
  and set_campaign_routing_rule_active() (narrower than a full upsert —
  needed for the GUI's active toggle, which must not force-reset
  next_index/owners the way a full re-save does).

  get_all_users_detailed() ADDITIVE change: now also selects
  owner_match_name (previously not selected) — needed to source the
  campaign-routing owner dropdown with the exact string that ends up
  written as leads.lead_owner. Existing consumers unaffected.

  leads.campaign column already existed (added under the v2.13
  drip_migrations self-healing block) — no new ALTER TABLE needed here.

v2.24 (July 2026) — Project Master List (Settings > Projects GUI, Task 2
  of the settings-GUI batch). ADDITIONS ONLY — nothing existing removed
  or modified except get_project_bucket(), whose OUTPUT BEHAVIOR is
  unchanged (same exact-match-first-then-fallback-to-raw-name logic),
  only its data source moved from the module-level PROJECT_BUCKETS dict
  to the new project_aliases table via a lazy cache.

  NEW project_aliases table (self-healing CREATE TABLE IF NOT EXISTS in
  init_db()), seeded ONE TIME ONLY from _PROJECT_ALIASES_SEED (the exact
  same pairs the old PROJECT_BUCKETS dict held) — seeding is gated on
  the table not existing BEFORE this init_db() call, not on it being
  empty, so a later admin action that empties the table (deleting every
  alias) can never trigger an accidental reseed on next restart.

  PROJECT_BUCKETS is now PAUSED (commented out, not deleted) — historical
  reference only, nothing reads it anymore.

  NEW _PROJECT_BUCKET_CACHE (module-level, lazy) + _load_project_bucket_
  cache() / reload_project_bucket_cache() — same lazy-cache-with-explicit-
  invalidation pattern used elsewhere in this file, not a new idiom.

  NEW list_project_buckets(), get_all_bucket_names(), add_project_alias(),
  delete_project_alias() — admin CRUD for the new /settings/projects
  screen. get_all_bucket_names() replaces the
  sorted(set(cls_db.PROJECT_BUCKETS.values())) pattern previously
  inlined at 5 call sites in app.py (leads_filter, lead_detail, lead_new,
  and both WhatsApp template admin screens — one more call site than
  originally scoped; verified against the live file rather than assumed).

v2.23 (July 2026) — CLS1/CLS2 database split support. ADDITIONS ONLY —
  nothing existing removed or modified, except DB_FILE's assignment
  (see below; every function that reads/writes data still goes through
  DB_FILE exactly as before, only where that constant points changed).

  DB_FILE now reads from the CLS_DB_PATH environment variable, defaulting
  to CLS1.db (was: hardcoded to cls.db). This is the mechanism behind
  splitting one shared database into CLS1.db ("our own CRM" — fed by
  Job A + the CRM app) and CLS2.db (Sell.do mirror — fed only by Job B).
  Each process's target DB is now config (an OS environment variable set
  per Task Scheduler task), not a code branch — consistent with the
  existing config-not-code convention used for roles/stages/thresholds
  elsewhere in this file. IMPORTANT: this must be a real Windows/OS
  environment variable, not a line in C:\\CLS\\.env — DB_FILE is computed
  once at import time from os.environ, and every script's .env loader
  (including this file's own callers) reads .env into a local dict well
  after that point, so a .env-only value would never be seen.

  NEW get_leads_snapshot(db_path) — the ONLY function in this module that
  opens a database file OTHER than DB_FILE. Read-only, narrowly scoped
  to cross-database diffing (cls_parallel_diff.py) — never used by any
  job or the CRM app during normal operation.

  NEW write_job_result(job_name, success, summary) — appends one line to
  C:\\CLS\\job_results.txt after a job run, for a human to glance at
  without opening per-job log files. Full detail stays in each job's own
  log file as before.

v2.22 (July 2026) — Job A insert-time stage/owner defaults (bug fix):
  upsert_meta_lead()'s brand-new-insert branch never set current_stage
  or lead_owner, leaving them NULL. Harmless when Job B syncs the same
  session and fills both in — but on a Job B failure, salespeople saw
  the lead with stage "Unknown" (unchangeable — STAGE_TRANSITIONS has
  no NULL key) and got "not the owner" on every action (lead_owner=""
  never matches any real owner name). FIX: insert now sets
  current_stage='Incoming' (the stage STAGE_TRANSITIONS' own comment
  already assumed Job A was setting) and lead_owner from the new
  DEFAULT_OWNER_BY_PROJECT map (fallback: Mounika Peddi). SAFE: Job
  B's existing-row UPDATE branch always overwrites current_stage
  unconditionally, and lead_owner via COALESCE(NULLIF(?,''), lead_owner)
  — so the moment Job B succeeds, these placeholders are corrected
  with the real Sell.do values. No schema change. Branches 1/2 of
  this function are untouched.

v2.21 (July 2026) — admin "User Activity Log" (Settings > User Activity).
  ADDITIONS ONLY — nothing existing removed or modified.

  NEW TABLES (self-healing CREATE IF NOT EXISTS in init_db(), same
  section style as impersonation_log): user_sessions (one row per login,
  auto-closed 'superseded' by a fresh login for the same user_id if a
  prior row is still open) and user_action_log (one row per logged-in
  request, FK'd to user_sessions.session_id). Kept separate from both
  activity_log (lead-scoped, pre-existing) and impersonation_log
  (account-level but flat, no parent/child grouping) — this feature
  needs one-session-has-many-actions grouping for the admin UI's one-
  card-per-session rendering.

  NEW start_user_session()/end_user_session()/log_user_action()/
  get_user_timeline() — see each docstring below. app.py v0.12 calls
  start_user_session() from login() and end_user_session() from
  logout(), and a new before_request hook calls log_user_action() on
  every logged-in request. None of these touch any existing table,
  function signature, or call site.

v2.20 (July 2026) — Task 3: precise "Re-engaged" redefinition (Srikanth's
  explicit call). ADDITIONS ONLY — nothing existing removed or modified,
  except get_reengaged_count()/get_reengaged_leads() which are commented
  out in place (tagged PAUSED, full bodies retained for reference
  directly above their replacements) and replaced by two new functions
  of the SAME names and SAME call signatures, so every existing call
  site (app.py's dashboard()/reengaged_list(), cls_reports.py's
  _build_reengagement()) needed zero changes.

  NEW COLUMN — leads.reengaged_at (TEXT, nullable), added via the
  existing self-healing drip_migrations ALTER TABLE loop in init_db().
  NULL for every pre-existing row at deploy; only ever set going
  forward. NEW CONFIG — RESET_STAGES_ON_REENGAGEMENT = ("Unqualified",
  "Lost", "Booked"), next to STAGE_TRANSITIONS.

  NEW TRIGGER — upsert_meta_lead()'s existing branch 2 (contact-match/
  enrich path, no leadgen_id row but phone/email matches an existing
  row — typically a Sell.do-only lead) now calls a new helper,
  _apply_reengagement_marker(conn, cls_id, prev_stage, now), BEFORE
  that branch's existing UPDATE. Always stamps reengaged_at=now; when
  the matched row's prior stage was in RESET_STAGES_ON_REENGAGEMENT,
  also resets current_stage='Incoming', stage_updated_at=now,
  stage_reason=NULL — otherwise the existing stage is left exactly as
  today. This is a raw sync write, same posture as every other Job A/B
  write on this row: it does NOT go through update_lead_stage()'s
  STAGE_TRANSITIONS gate (that gate is for CRM-initiated user actions
  only). Branch 1 (same-leadgen_id refresh) and branch 3 (brand-new
  insert) are UNTOUCHED. upsert_selldo_lead() / Job B are NOT touched —
  selldo_to_cls.py remains off-limits per standing instruction.

  NEW get_reengaged_count()/get_reengaged_leads() — LIVE-computed
  (reengaged_at IS NOT NULL AND no activity_log row since), same
  "computed at query time, no stored cleared flag" principle as every
  other missed/due status in this file. Both still accept a `days`
  kwarg for call-site signature compatibility only — it is UNUSED,
  since the new definition has no trailing-window concept.

  KNOWN LIMITATION, flagged not built: a Booked->Incoming reset does
  NOT also auto-cancel any open site visit/follow-up via the existing
  _auto_cancel_open_schedules() — recommended to skip since Booked
  leads essentially never have anything open scheduled; see
  _apply_reengagement_marker()'s docstring.

  EXPECTED, not a bug: every existing lead has reengaged_at=NULL right
  after this deploys, so get_reengaged_count() reads 0 until new
  re-entries happen through Job A's enrich path.

v2.19 (July 2026) — APX bug-fix + scoped-enhancement batch (3 items from
  Srikanth, parallel-run continues unaffected). ADDITIVE ONLY except where
  noted — no existing table, function signature, or call site removed.

  ITEM 1 — get_leads_page() search: lead-ID match now ONLY when the term
  is prefixed with "#" or "apx-" (case-insensitive, whitespace-trimmed).
  Previously a bare numeric term like "250" was OR'd into name/phone/
  email/lead-ID all at once, so it could accidentally match a phone
  number, an email, AND a lead ID in the same query. Now: "#250" or
  "APX-250" matches crm_lead_no exclusively (name/phone/email NOT
  searched in this case); anything else searches name/phone/email as
  before but crm_lead_no is excluded entirely — a bare "250" no longer
  matches lead ID 250. app.py/leads_search.html need no changes to call
  this function; only the caption text changes (see app.py's own
  changelog).

  ITEM 2 — NEW WRITE_ANYWHERE_ROLES = ("admin", "manager") and
  can_write_any_lead(role), mirroring OVERSIGHT_ROLES/can_view_all_leads()'s
  exact pattern (same fail-closed posture: unrecognised role -> False).
  Srikanth's explicit call (2026-07, flagged as security-relevant before
  building): a manager may now WRITE to ANY lead (stage, notes, assign,
  site visit/follow-up, property/contact edits, call tap), not just their
  own pipeline — REVERSING v2.9/v0.9.5's deliberate read/write split for
  the manager role. can_view_all_leads()'s docstring updated to flag this
  explicitly so a future reader doesn't assume the old split still holds.
  activity_log continues to record the ACTUAL acting user (the manager's
  own identity), never the lead's owner — unchanged, and the whole reason
  this is safe to grant. This constant does NOT touch Settings, the Team
  page, lead deletion, or source-editing — those stay admin-only exactly
  as today; see app.py's changelog for the corresponding write-gate change.

  ITEM 3 (Option B) — upsert_selldo_lead() existing-row UPDATE branch:
  cls_updated_at now only advances when something actually changed.
  ROOT CAUSE: this function (called by Job B on every sync pass, for
  every lead) unconditionally set cls_updated_at=now() even on a true
  no-op sync — stage_updated_at already avoided this via a CASE WHEN
  keyed off stage_changed, but cls_updated_at never got the same
  treatment, so the CRM's "Upd" column read as today for every lead
  regardless of whether anyone/anything had touched it. FIX: a new
  anything_changed boolean (mirrors stage_changed's existing pattern)
  is computed by predicting each COALESCE'd column's post-update value
  in Python — current_stage, project, full_name, phone_raw/norm,
  email_raw/norm, lead_owner, selldo_url, opportunity_temperature — and
  comparing against what's already stored; cls_updated_at now uses the
  same CASE WHEN ? THEN ? ELSE cls_updated_at END pattern already used
  for stage_updated_at. Every OTHER write path that sets cls_updated_at
  (pause_drip, mark_opt_out, mark_hard_bounce, contact/property edits,
  etc.) is untouched — those already only fire on genuine actions.
  Requires the EXISTING SELECT this function already ran to fetch more
  columns (project, full_name, phone/email raw+norm, lead_owner,
  selldo_url, opportunity_temperature) alongside the cls_id/current_stage
  it already fetched — read-only addition, no new query round-trip.
  DOES NOT touch selldo_to_cls.py (Job B) itself — only this shared
  function it calls. Tested against a throwaway DB with both no-op and
  real-change Sell.do-shaped rows before being considered done (see
  Srikanth's session for the test transcript).

v2.18 (July 2026) — stats() baseline fix for historical-import leads.
  ADDITIVE ONLY — no existing key removed or renamed, no existing
  caller's behavior changed.

  stats() now also returns "imported_historical" (COUNT(*) FROM leads
  WHERE match_tier='imported') and "syncable_leads" (total_leads minus
  imported_historical).

  Why: the v2.17 Sell.do historical CSV bulk import permanently added
  leads to cls.db with match_tier='imported'. Sell.do's own day-to-day
  export will never report these leads again by design — they were a
  one-time historical backfill, not leads Sell.do is currently tracking.
  Job B's CSV lead-count sanity check (selldo_to_cls.py v1.2 Fix 4)
  compares the CSV's row count against cls_db.stats()["total_leads"],
  which now permanently overcounts what Sell.do's export can ever
  contain again post-import. "syncable_leads" gives Job B (and any
  other caller) a baseline that excludes the imported rows, so the
  sanity check's 85% threshold is measured against leads Sell.do can
  actually still report.

v2.17 (July 2026) — Sell.do historical CSV bulk import (Option B).
  ALL additive — no existing table, function, or call site touched.
  No schema change: every column the import needs (selldo_lead_id,
  crm_lead_no, campaign, last_fired_stage, last_fired_at, drip_paused,
  drip_enrolled_at, match_tier, source) already existed.

  NEW "SELL.DO HISTORICAL CSV BULK IMPORT" section (after
  upsert_selldo_lead()): import_selldo_csv_row(csv_row, commit=False)
  — match-or-insert ONE row from a one-time historical Sell.do CSV
  export — plus one small companion function,
  log_duplicate_selldo_import(cls_id, old_selldo_id, description), so
  the CLI script's own phone-based dedupe (collapsing rows that share
  a phone number, keeping only the latest as primary) can still record
  each older Sell.do ID onto the primary lead's activity_log without
  ever opening sqlite3 directly (per CLS's centralized-DB-access
  rule) — it does not participate in matching/insert logic at all,
  it only appends one 'duplicate_selldo_id_from_import' activity_log
  row. Both are called only by the new cls_import_selldo_csv.py (NOT
  part of the A->B->C->D pipeline, NOT selldo_to_cls.py — Job B
  remains untouched and was neither read nor modified for this
  change).

  Matching reuses find_match() unchanged (tiered phone+email > phone >
  email), preceded by a Tier-0 check for an existing exact
  selldo_lead_id match. New inserts pin last_fired_stage/last_fired_at
  to the historical stage/time and drip_paused=1 with drip_enrolled_at
  pinned to the historical time, so an imported row can never trigger
  a CAPI re-fire or a drip email storm. Matched (already-known) leads
  get ONLY crm_lead_no overwritten (Option B — the Sell.do CSV's own
  Lead's Id becomes the lead's permanent crm_lead_no) plus
  selldo_lead_id/campaign backfilled ONLY if currently NULL/empty
  (Srikanth's Q3/Q4 decisions) — current_stage, stage_updated_at,
  project, lead_owner, contact fields, cls_created_at, fire state, and
  every drip_* column on a matched lead are left exactly as Job B's
  own sync last set them.

  Every insert/update writes matching activity_log rows
  (imported_from_selldo / lead_id_changed_from_import /
  backfilled_from_selldo_import) via the existing _log_activity()
  helper — no new audit table. Idempotent: re-running the same CSV
  does not create duplicate leads (a previously-imported row is found
  again via its own selldo_lead_id on Tier 0) or duplicate
  imported_from_selldo activity rows (explicit activity_log guard
  before any insert, belt-and-suspenders on top of the Tier-0 match).

  No schema change to any EXISTING table. No existing function's
  behavior changed.

v2.16 (July 2026) — APX v0.7 UI Polish, Search by Lead ID.
  get_leads_page() search now also matches on crm_lead_no. Accepts
  'APX-183' or plain '183'. No schema change. No other function
  touched. v2.14 (reminders) and v2.15 (impersonation) are unaffected
  by this change.

v2.15 (July 2026) — APX v0.11 Admin "View as" (impersonation). ALL
  additive — no existing table, function, or call site touched. All
  the session-swap logic and dual-attribution (the actor= string
  written to activity_log on every write made while impersonating)
  live entirely in app.py's new _actor() helper — this file's only
  change is a plain audit trail of when a view-as session started/
  ended, same append-only spirit as activity_log/events_log.

  NEW TABLE impersonation_log (self-healing, CREATE IF NOT EXISTS) —
  one row per impersonation session start/exit. Kept separate from
  activity_log rather than reusing it: this is an account-level
  session event, not a lead-scoped one (cls_id would be meaningless).

  NEW log_impersonation(admin_email, target_email, event) — event must
  be 'start' or 'exit' (raises ValueError otherwise, a caller-bug
  guard, not a user-facing error path).

  No schema change to any EXISTING table. No existing function's
  behavior changed.

v2.14 (July 2026) — APX v0.10 Tomorrow's Site-Visit WhatsApp Reminders.
  ALL additive — no existing table, function, or call site touched.

  NEW TABLE whatsapp_reminder_templates (self-healing, CREATE IF NOT
  EXISTS) — one reminder message per project, DELIBERATELY separate
  from whatsapp_templates (v2.7): different content, edited from a
  different Settings screen, even though the CRUD shape is identical
  (Srikanth's call — see the table's own comment in init_db()).

  NEW "WHATSAPP SITE-VISIT REMINDER TEMPLATES" section (after
  render_whatsapp_template()): get_whatsapp_reminder_templates(),
  upsert_whatsapp_reminder_template(project, message_body, actor),
  delete_whatsapp_reminder_template(template_id) — mirror the v2.7
  WhatsApp-template CRUD exactly. render_whatsapp_reminder_template
  (message_body, lead, scheduled_at_iso) — same {name}/{project}
  expansion as render_whatsapp_template() plus a new {time} placeholder
  (12-hour AM/PM, mirrors app.py's `ampm` Jinja filter's own strftime
  format; falls back to '' on an unparseable/missing timestamp so a
  bad scheduled_at can't blank the whole message).

  NEW get_site_visits_for_tomorrow(owner_match_name=None) — tomorrow's
  scheduled site visits (status='scheduled', DATE(scheduled_at) =
  DATE('now','localtime','+1 day') — same server-local convention as
  _now() everywhere else in this file, no timezone abstraction added),
  optionally scoped to one salesperson via leads.lead_owner. Each row
  includes reminder_sent_at, resolved via a correlated subquery against
  activity_log filtered on activity_type='whatsapp_reminder_sent' and
  description LIKE 'visit_id:<id>%'.

  NEW get_site_visit_by_id(visit_id) — single site_visits row lookup,
  needed because the mark-sent route's URL carries only a visit_id, not
  a cls_id (unlike every other site-visit write route in app.py).

  NEW get_pending_reminder_count(owner_match_name=None) — count of
  tomorrow's visits with reminder_sent_at IS NULL, built ON TOP OF
  get_site_visits_for_tomorrow() rather than a second query (small
  dataset, one definition of "sent" instead of two to keep in sync).
  Feeds the drawer badge and the new Dashboard tile.

  NEW log_reminder_sent(visit_id, cls_id, actor) — writes one
  activity_log row via the existing _log_activity() helper (no new
  audit table). description is EXACTLY f"visit_id:{visit_id}" —
  get_site_visits_for_tomorrow()'s LIKE lookup depends on this exact
  format; changing it without updating both sites will silently break
  the "already sent" detection.

  No schema change to any EXISTING table. No existing function's
  behavior changed.

v2.13 (July 2026) — APX v0.6.1 Reports Enhancements. ALL additive except
  the eight explicitly-flagged modified functions below (each gained
  ONLY new optional kwargs with defaults that reproduce prior exact
  behavior — no existing call site anywhere needed to change).

  DATA-AVAILABILITY FINDING surfaced to Srikanth before building (his
  call: build now, backfill later): leads.campaign is blank/NULL on
  3,728 of 3,729 leads (99.97%) as of 2026-07-17 — it's a manual,
  optional, salesperson-typed field (set via the /property-details
  route), never auto-populated by meta_leads_fetcher.py or
  selldo_to_cls.py. Every campaign-grouped function below buckets a
  blank/NULL campaign under the literal label "Unknown/Manual" (see
  _campaign_bucket()) rather than dropping those leads — so today
  these reports will show almost everything under that one bucket
  until campaign data is backfilled; that's expected, not a bug.

  NEW _campaign_bucket(raw) — trivial TRIM/blank-to-"Unknown/Manual"
  helper, same spirit as the existing get_project_bucket() but with no
  alias table (campaign is free text, no known-variant collapsing
  needed yet).

  NEW "REPORTS v0.6.1" functions (after get_call_activity()):
  get_activity_counts_range() (date-range generalization of
  get_todays_activity_counts(), kept as a SEPARATE new function rather
  than modifying that one — zero risk to its 3 existing call sites),
  get_leads_received_by_owner(), get_stage_breakdown(),
  get_site_visits_by_campaign(), get_campaign_lead_volume(),
  get_campaign_performance(), get_campaign_lost_reasons(),
  get_campaign_response_time().

  MODIFIED (additive optional date_from/date_to kwargs, default None
  on every one reproduces that function's exact prior behavior):
  get_source_performance(), get_project_pipeline(),
  get_followup_hit_rate(), get_lost_reason_breakdown(),
  get_conversion_funnel_trend() (date_from/date_to, when given,
  replace the trailing-`months`-window with the explicit range —
  months param unchanged/still governs the default trailing window),
  get_first_response_time() (same treatment as conversion_funnel_trend),
  get_reengaged_leads() (date_from/date_to, when given, replace the
  trailing-`days` cutoff with an explicit window), get_call_activity()
  (date_from/date_to, when given, replace the trailing-`days` window —
  used to retire report_view's old daily/weekly toggle in favor of the
  new universal date-range picker).

  No schema change. No existing function's behavior changed except the
  eight flagged above, and every one of those changes is inert unless
  the NEW date_from/date_to kwargs are actually passed.

v2.12 (July 2026) — APX v0.6 Reports section. ALL additive except the
  three explicitly-flagged modified functions below (each gained ONLY
  a new optional kwarg / new dict key with a default that reproduces
  its exact prior behavior — no existing call site anywhere in the
  codebase needed to change).

  NEW "CRM v0.6 — REPORTS" section (after drip_stats()): 8 new read-
  only functions — get_source_performance(), get_project_pipeline(),
  get_conversion_funnel_trend(), get_followup_hit_rate(),
  get_lost_reason_breakdown(), get_score_distribution(),
  get_first_response_time(), get_owner_workload(),
  get_call_activity() — one per report that needed a new aggregation.
  Reports #1 (Daily Scorecard), #2 (Pipeline Funnel Snapshot), and #9
  (Reengagement) reuse existing functions instead (see the three
  modifications below). See that section's own HONESTY NOTE block for
  two real data-limitation caveats worth reading before trusting the
  numbers: (1) activity_log 'stage_change' rows exist only for stage
  moves made through THIS app (update_lead_stage()), not Sell.do-
  driven syncs, so get_conversion_funnel_trend() undercounts pre-CRM-
  adoption months; (2) leads.source only ever holds 'meta' /
  'selldo_only' / 'manual_crm' (the capture channel), not a marketing
  sub-source like "99acres" — lead_source_detail is richer but NULL
  for the large majority of leads, so get_source_performance() reports
  on `source`, not `lead_source_detail`.

  MODIFIED get_stage_snapshot_counts() — NEW optional owner kwarg
  (default None, unchanged behavior for the zero-arg call
  dashboard_pipeline() already makes).

  MODIFIED get_reengaged_leads() — NEW optional owner kwarg (default
  None, unchanged behavior for reengaged_list()'s existing call).

  MODIFIED get_todays_activity_counts() — NEW 'note' -> 'notes_added'
  entry in METRIC_MAP, so its returned dict gained ONE new key
  (notes_added). Every existing key/value this function already
  returned is unchanged; dashboard_today() still works unmodified.

  cls_reports.py (new, crm/) owns report metadata, table/column
  shaping, and Excel/print-PDF export — it queries cls.db ONLY through
  these functions, never opens sqlite3 directly, per the centralized-
  access rule.

v2.11 (July 2026) — APX v0.5 polish pass, 5 independent additions
  (Srikanth's decisions 1/3/4/5; decision 2 is template-label-only and
  decision 4's root cause turned out to be template-only too — see
  app.py/lead_detail.html changelogs for those). ALL additive except
  the two explicitly-flagged modified functions below.

  REDEFINED get_new_enquiries_count() (decision 1) — was "current_
  stage='Incoming'" (v1.9); now ALSO requires zero activity_log rows
  for that cls_id, so a lead drops off the count the instant a human
  does anything to it (even before its stage moves off Incoming), not
  just when the stage changes. NEW get_new_enquiries_leads() — same
  criteria, row-returning, mirrors get_reengaged_leads().

  NEW STAGE_REASON_LISTS = {"Lost": UNQUALIFIED_REASONS, "Unqualified":
  UNQUALIFIED_REASONS} (decision 3) — Lost now shows the same 15
  Unqualified reasons instead of its own 8. MODIFIED update_lead_
  stage()'s reason validation to read this dict instead of two
  hardcoded if/elif branches against LOST_REASONS/UNQUALIFIED_REASONS;
  behavior for Unqualified is unchanged, Lost's required-reason list
  changed from LOST_REASONS to UNQUALIFIED_REASONS. LOST_REASONS itself
  is UNCHANGED and still exported — marked "# PAUSED — retained for
  historical Lost reason codes + easy revert", read by app.py's
  leads_filter_screen() so leads already marked Lost under the old
  codes stay filterable.

  NEW nullable leads columns alt_phone_raw / alt_phone_norm (decision
  5, self-healing ALTER TABLE, additive-only migration). MODIFIED
  update_lead_contact_info() — NEW optional alt_phone_raw kwarg
  (default None, existing callers unaffected), normalized through the
  SAME norm_phone() into alt_phone_norm for DISPLAY ONLY. alt_phone_
  norm is deliberately never read by find_match() or any matcher —
  storage/display only, per Srikanth's explicit instruction.

  No schema change removed or renamed anything; no existing function's
  behavior changed except the two flagged above, and both changes were
  explicitly requested (not incidental).

v2.10 (July 2026) — read-only feed for cls_parallel_export.py (parallel-
  run sync-health checkpoint, on-demand, not scheduled). Purely additive,
  ZERO schema change — reads existing activity_log + leads columns only.

  NEW get_latest_stage_and_owner_changes() — for every lead with at
    least one 'stage_change' and/or 'assignment_change' row in
    activity_log, returns that lead's identity (cls_id, full_name,
    phone_raw, email_raw), its CURRENT current_stage/lead_owner, and
    the MOST RECENT row of each change type (actor, prev_value,
    new_value, created_at — NULL for whichever type never happened).
    "Most recent" uses activity_id (autoincrement) as the tiebreaker,
    same as get_activity_log_for_lead()'s existing ORDER BY. Leads with
    NEITHER activity type are excluded — nothing to compare a sync
    outcome against, so they'd just be noise in both drift counts.
    Deliberately does NOT decide reverted/pending/clean itself — that
    "has enough time passed for Job B to run" policy is time-sensitive
    and belongs in the caller (cls_parallel_export.py), not baked into
    a DB-layer read. This is the ONLY DB access cls_parallel_export.py
    makes — it never opens sqlite3 directly, per the centralized-access
    rule.

v2.9  (July 2026) — NEW 'manager' role (oversight tier), for
  app.py v0.9.5. Config-not-code and ZERO schema migration:

  - role has always been free-text TEXT with no CHECK constraint
    (SQLite has no ENUM), so 'manager' needs no ALTER and no data
    migration — existing rows are untouched. This changelog entry and
    the two constants + one helper below are the WHOLE database-layer
    change.

  - NEW CRM_ROLES = ("admin", "manager", "salesperson") — the single
    source of truth create_admin.py now validates against, and the
    documented hierarchy: admin (top) > manager (middle) > salesperson.

  - NEW OVERSIGHT_ROLES = ("admin", "manager") + can_view_all_leads(role)
    — the ONE place the "who sees every lead" policy is defined. app.py
    consults this everywhere it used to hardcode role == "admin" for
    VISIBILITY (leads list, filter owner-dropdown, lead detail full view,
    company-wide Today's Performance). Fails CLOSED: an unrecognised/
    misspelled role is treated as a salesperson (own leads only), never
    given the widest view.

  - DELIBERATELY NOT a write capability. can_view_all_leads() governs
    READ/visibility only. Writing to a lead is still gated on ownership
    by app.py's _check_lead_ownership() (owner-or-admin), so a manager
    sees every pipeline but can only change stage / add notes / reassign
    on leads they personally own (their own owner_match_name). Admin
    remains the only write-anywhere role. See app.py v0.9.5's
    lead_detail() read-vs-write split for the full reasoning.

  - No new admin powers reach 'manager': Settings, the Team page, lead
    deletion, and source-editing all stay behind the untouched
    admin_required decorator / role == "admin" checks. Manager is purely
    additive on the oversight side.

v2.8  (July 2026) — walk-in site visits + user activate/deactivate,
  from testing feedback on v0.9.2. Two independent additions:

  NEW log_walkin_site_visit(cls_id, project, conducted_at, actor, notes)
    — logs a site visit that ALREADY happened with no prior scheduling
    (an existing, in-touch lead walked into a project unannounced).
    Inserts directly as status='conducted' — never touches the
    one-open-scheduled-slot rule schedule_site_visit()/update_site_visit()
    enforce, so it can't collide with a real open scheduled visit. Logs
    the SAME activity_type ('site_visit_conducted') the normal flow
    uses, so it's counted identically everywhere that already reads it
    (today's performance tile, lead scoring, Activity History) — no new
    counter, live-derived like every other CLS metric.
    SCHEMA: site_visits gained a nullable `project` column (self-healing
    ALTER, additive only) — NULL for every normally-scheduled visit;
    only walk-ins set it, since those aren't otherwise tied to a
    project_bucket at the moment they're logged.

  NEW get_all_users_detailed() / set_user_active(user_id, active,
    actor_user_id) — Settings > Team activate/deactivate. Reuses the
    EXISTING users.active column and enforcement path (verify_login()
    and get_user_by_id() already gate on active=1 — this is v0.1
    plumbing that had no admin-facing UI until now). Guards against an
    admin deactivating their own account (would lock them out
    mid-session with no in-app undo).

v2.7  (July 2026) — CRM: WhatsApp templates, admin lead deletion, and
  non-owner search. Three independent additions:

  NEW TABLE whatsapp_templates (self-healing, CREATE IF NOT EXISTS):
    project       TEXT (the template's title — one template per project,
                  UNIQUE), message_body TEXT (supports {name}/{project}
                  placeholders, expanded at send time by render_whatsapp_
                  template()), created_at/updated_at. Admin-managed only
                  (the ROUTE enforces admin, same as create_manual_lead's
                  source-lock reasoning — this layer just stores/returns).
    NEW get_whatsapp_templates(), get_whatsapp_template_for_project(),
    upsert_whatsapp_template(), delete_whatsapp_template(),
    render_whatsapp_template().

  NEW delete_lead(cls_id, actor) — ADMIN-ONLY at the route layer.
    Hard-deletes the lead AND every child row keyed to it (activity_log,
    site_visits, follow_ups, events_log, comms_log) in ONE transaction,
    so nothing is orphaned. This is a genuine wipe, not a soft-delete
    flag — Srikanth's explicit call (2026-07). NOTE, flagged in the
    route and here: if this same person still exists in Sell.do, Job B's
    next sync re-imports them as a fresh lead — accepted parallel-run
    reality, not a bug. A real suppression list is v1.0+ scope.

  CHANGED get_leads_page() — NEW search_all_owners flag (default False,
    so every existing caller is unchanged). When True AND a search term
    is present, the owner scope is IGNORED for that query only — lets a
    salesperson FIND a lead they don't own by name/phone/email (landing
    on the restricted read-only view built in app v0.9). A BLANK search
    with this flag still returns nothing cross-owner — the flag only
    ever widens an active search, never the default list. Modifies an
    existing function; flagged per the before/after-diff rule.

v2.6  (July 2026) — CRM v0.5: edit name/phone on an existing lead
  (item 10 of Srikanth's rebuild spec — fixes cases like a lead's
  email landing in the name field, or a phone number missing/wrong
  country code). Purely additive — one new function, no schema change.

  NEW update_lead_contact_info(cls_id, actor, full_name=None,
  phone_raw=None) — same "pass only what you want to change" pattern
  as update_property_details(). Re-normalizes phone_raw through the
  SAME norm_phone() the matcher itself uses, so phone_norm (the actual
  join key Job B's Sell.do sync matches on) stays in sync with
  whatever gets typed here — an edit that updated phone_raw but left
  phone_norm stale would silently break future Sell.do matching for
  that lead.

  FLAGGED RISK (surfaced to Srikanth during planning, not new
  information, restated here for anyone reading this changelog cold):
  correcting phone_norm/full_name here can change what Job B's
  Sell.do-sync matcher recognises as "the same lead" going forward.
  Every edit is logged to activity_log (old value -> new value, who,
  when) specifically so a resulting duplicate, if one ever appears, is
  traceable in two clicks rather than a mystery.

v2.5  (July 2026) — CRM v0.5: Leads list filter/search/sort overhaul
  (moves the top filter bar to a dedicated bottom-icon-bar-driven
  Filter screen + Search screen). MODIFIES get_leads_page()'s
  signature (new optional kwargs, all default None/unused so every
  existing call site — just app.py's leads_list() — keeps working
  unchanged until app.py is updated in the same deploy). Flagged here
  per the before/after-diff rule since this isn't a pure addition.

  NEW params on get_leads_page(): date_from, date_to (filters on
  cls_created_at), sort_by (whitelisted against SORT_OPTIONS — never
  raw SQL from the request), stage_reason (exact match), campaign
  (substring match), source (exact match on the SYSTEM-level
  meta/selldo_only/manual_crm column), sub_source (exact match on
  lead_source_detail — the MANUAL_SOURCE_OPTIONS column; deliberately
  a separate filter from `source` even though both are "where did this
  lead come from," because they're genuinely different columns
  answering different questions: `source` is CLS's own capture-path
  label, `sub_source` is what a human typed in for a manual entry),
  budget (exact match), configuration/property_type/facing (each a
  LIST — OR-matched via LIKE against the comma-separated multi-select
  columns from v2.3; a lead matches if ANY selected checkbox value
  appears anywhere in its column).

  NEW SORT_OPTIONS — config-not-code {key: SQL ORDER BY clause} dict.
  Whitelisted lookup only, exactly like STAGE_TRANSITIONS/BUDGET_
  BRACKETS elsewhere in this file — request-supplied sort keys that
  aren't in this dict silently fall back to "recent" rather than
  erroring or reaching raw SQL.

  NEW SOURCE_OPTIONS — the 3 real values leads.source ever holds
  (meta / selldo_only / manual_crm), for the Source filter dropdown.

  Pipeline-stage filter dropdown (app.py) now offers all of ALL_STAGES
  instead of just TARGET_STAGES (the 4 CAPI-firing stages) — TARGET_
  STAGES was never meant to gate what a salesperson can FILTER by, only
  what fires CAPI events; using it for the filter dropdown was
  accidentally hiding Lost/Unqualified/Booked/Re Assigned/Incoming as
  filter options. Fixed here as a byproduct of rebuilding this screen.

v2.4  (July 2026) — CRM v0.5: Dashboard restructure (Stats / Today's
  Performance / Pipeline Analysis). Purely additive — 3 new read-only
  query functions, no schema change, nothing existing modified.

  NEW get_stage_snapshot_counts() — current-moment count of leads in
    EACH of ALL_STAGES (8 stages), for the Pipeline Analysis tiles.
    Deliberately a live snapshot (COUNT(*) grouped by current_stage
    right now), not a point-in-time-as-of-today historical figure — a
    true daily snapshot would need its own snapshot table, which is
    unjustified complexity for a number that's glanced at once a day
    (Srikanth's call, 2026-07, simple-over-complex).

  NEW get_leads_created_today_count() — leads whose cls_created_at
    falls today. Feeds Pipeline Analysis's "Total Leads" tile — this
    ONE tile is a "created today" count, deliberately different from
    every other tile on that same page (which are live snapshots) —
    see get_stage_snapshot_counts()'s docstring for why.

  NEW get_todays_activity_counts(actor_email=None) — for the Today's
    Performance page. Reads ONLY activity_log (one table, one query,
    grouped by activity_type) rather than joining site_visits/
    follow_ups — every metric asked for already has a matching
    activity_type logged at the moment it happens, so a second data
    source would just be duplication. Returns calls_attempted,
    site_visits_created, site_visits_conducted, follow_ups_created,
    follow_ups_completed — all scoped to today (server local date,
    same substr(created_at,1,10) convention as get_daily_owner_summary).
    Pass actor_email to scope to one salesperson's own actions
    (app.py's call); omit it for a company-wide total (admin view).
    Deliberately does NOT include "total talk time" — that requires
    call duration/connected-status data that doesn't exist anywhere in
    this schema yet; it's v1.0 Telephony's job, exactly as roadmapped.

v2.3  (July 2026) — CRM v0.5 continued: qualification fields, Lost/
  Unqualified reason capture, reassignment notification flag.

  NEW COLUMNS on leads (self-healing migration, all nullable):
    - budget            TEXT  — one of BUDGET_BRACKETS
    - facing            TEXT  — comma-separated subset of FACING_OPTIONS
    - stage_reason       TEXT  — current Lost/Unqualified reason CODE
                                 (cleared to NULL the moment the lead
                                 moves to any other stage — this column
                                 answers "why is it CURRENTLY Lost/
                                 Unqualified," not "why was it ever,"
                                 which stays fully in activity_log)
    - owner_notified    INTEGER — 0/1. Powers the new "you were
                                 assigned a lead" badge. Defaults to 1
                                 (no pending badge) for all EXISTING
                                 rows on migration — only a NEW
                                 reassignment from this point on
                                 flips it to 0.

  BEHAVIOR CHANGE — configuration & property_type are now MULTI-SELECT
  (Srikanth's call, 2026-07): a lead can be interested in more than one
  configuration (e.g. "2 BHK, 3 BHK") or property type. Stored as the
  same TEXT column, just holding a comma-separated list now instead of
  one value. NEW _validate_multi_select() enforces every comma-split
  token is non-empty and in the allowed list; single-value inputs
  still work unchanged (a one-item list is valid multi-select input).
  update_property_details() signature changed to route configuration/
  property_type/facing through this new validator instead of a plain
  "in list" check — this modifies existing validation logic, not a
  pure addition; flagged here per Srikanth's before/after-diff rule.

  BEHAVIOR CHANGE — update_lead_stage() now REQUIRES reason_code (+
  mandatory reason_notes free text) whenever new_stage is 'Lost' or
  'Unqualified' — same "mandatory reason" pattern already used for
  site-visit/follow-up outcomes (v1.9). reason_code is validated
  against LOST_REASONS or UNQUALIFIED_REASONS depending on new_stage,
  written to the new leads.stage_reason column, and reason_notes is
  appended to the existing stage_change activity_log row's description
  (no new activity_type — stays queryable as a normal stage change).
  Moving OUT of Lost/Unqualified to any other stage clears stage_reason
  back to NULL in the same write. This modifies update_lead_stage()'s
  existing signature and body — flagged here, not a pure addition.

  NEW LOST_REASONS / UNQUALIFIED_REASONS / BUDGET_BRACKETS /
  FACING_OPTIONS — config-not-code, same pattern as STAGE_TRANSITIONS.

  reassign_lead_owner() now also sets owner_notified=0 on every
  reassignment (one new line in an existing function — flagged, not a
  pure addition). NEW mark_lead_notification_read(cls_id) flips it back
  to 1 (call this when the new owner opens the lead). NEW
  get_unread_assignment_count(owner_match_name) — count of an owner's
  leads still sitting at owner_notified=0, for the login-badge.

v2.2  (July 2026) — CRM: auto-cancel on Lost/Unqualified + lead scoring:
  - update_lead_stage() now auto-cancels any OPEN (status='scheduled')
    site visit and follow-up for a lead the moment it moves to Lost or
    Unqualified. Same transaction as the stage write (atomic — either
    both land or neither does). Each cancellation logs a normal
    site_visit_cancelled / follow_up_cancelled activity row with
    outcome_reason="Auto-cancelled — lead marked {stage}", so it
    renders in Activity History exactly like a manual cancellation.
    Deliberately does NOT auto-restore anything if the lead later
    moves back to Prospect — a salesperson schedules fresh ones
    (Srikanth's call, 2026-07).
  - NEW LEAD_SCORE_RULES / LEAD_SCORE_BANDS — config-not-code point
    values for lead scoring, same pattern as STAGE_TRANSITIONS/
    DRIP_SCHEDULE. Deliberately does NOT include a "reengaged" bonus:
    the only reengagement signal that exists today
    (get_reengaged_count/get_reengaged_leads) is explicitly labelled
    approximate — a time-elapsed heuristic, not "this specific person
    submitted a brand-new inquiry." Folding that into a score would
    conflate exactly the two things Srikanth's own design notes say
    must stay separate. Add it once the precise version (a marker at
    the moment find_match() succeeds) gets built.
  - NEW compute_lead_scores(cls_ids) — batch-computes {cls_id: {score,
    band}} in ONE connection for a list of leads (used for the leads
    list page and lead detail page). Deliberately NOT a stored column
    on `leads` — scoring reads live current_stage/opportunity_
    temperature/activity_log every call, so it's always current and
    needs zero coordination with Job A/B/C or any new migration.
    Simple-over-complex: at CLS's current scale, a few extra read-only
    queries per page view costs nothing worth optimising for yet.

v2.1  (July 2026) — per-salesperson daily attribution (CLS Jobs A/B/C,
  not the CRM):
  ADDED — lead_owner column on events_log (self-healing ALTER TABLE,
          same pattern as prev_stage). record_event() now accepts an
          optional lead_owner kwarg and stores it, so every CAPI fire
          is permanently attributed to whoever owned the lead AT THE
          MOMENT it fired — even if the lead is later reassigned
          (whether by Job B's Sell.do sync or the CRM's own
          reassign_lead_owner()). cls_capi_firer.py passes
          lead["lead_owner"] (already present on every row from
          get_unfired_leads()'s SELECT *) — no new query needed there.
  ADDED — get_daily_owner_summary(date_str=None): returns one row per
          distinct lead_owner (plus an "Unassigned" bucket for blank/
          NULL owners) with three counts for the day —
            new_leads      : leads created that day, by lead_owner
            stage_changes  : leads whose stage_updated_at falls that
                              day, by lead_owner (counts the LEAD, not
                              every transition — see docstring for the
                              one edge case this differs from Job B's
                              raw per-cycle "stage changes" total)
            capi_fired     : events_log rows fired that day, by the
                              lead_owner captured on the event itself
          Used by cls_watchdog.py's end-of-day summary. Deliberately
          separate from v0.5's activity_log (which only records the
          CRM app's own write actions, not Job B's automated Sell.do
          sync) — this reads leads/events_log directly so it captures
          ALL stage movement regardless of which path caused it.
          Config-not-code: the owner list is read live from the data
          (DISTINCT lead_owner), so a new salesperson shows up
          automatically — no code change needed here or in the watchdog.

v2.0  (July 2026) — richer lead data model, source tracking:
  - NEW lead_source_detail — for manually-entered leads only, one of
    MANUAL_SOURCE_OPTIONS (Walk-In / Meta / Channel Partner / Youtube /
    Referral / Website). Locked after creation — only update_lead_
    source_detail() can change it, and app.py restricts that route to
    admin only (a salesperson typing in a source once shouldn't be
    able to quietly change it later).
  - NEW funding_source (Loan/Self), property_type (Apartment/Villa/
    Plot/Duplex/Penthouse/Row House), configuration (1 BHK..6 BHK+),
    campaign (free text, optional) — all editable on ANY lead, not
    just manual ones, since a salesperson usually learns these from
    conversation with an auto-captured lead, not at creation time.
    All four have their own update function logging to activity_log.
  - All new columns are self-healing migrations, all nullable, all
    backward-compatible — no existing row, job, or query is affected
    by their absence on old data.

v1.9  (July 2026) — v0.5 refinements from first real mobile usage:
  - NEW crm_lead_no — a friendly sequential ID (e.g. "APX-183"), since
    cls_id is a UUID never meant to be read or typed aloud. Backfilled
    for all existing leads in cls_created_at order; assigned to every
    NEW lead (Meta, Sell.do-only, or manual) via _next_crm_lead_no().
    Computed as MAX(crm_lead_no)+1 at insert time — simple and correct
    for this system's actual write frequency, but not airtight against
    a true simultaneous double-insert across two processes. Flagging
    that honestly rather than over-engineering a dedicated counter
    table for a collision this system is very unlikely to ever hit.
  - Site visits and follow-ups gain real outcome tracking instead of
    one binary "conducted"/"completed": update_site_visit() now
    accepts action = conducted / rescheduled / cancelled / no_show;
    update_follow_up() accepts completed / cancelled / postponed.
    Rescheduled/postponed do NOT close the item — they update the same
    row's scheduled_at and keep status='scheduled', which is why they
    don't conflict with the new one-open-at-a-time rule below. Every
    other action closes the item. A reason is now MANDATORY for every
    outcome (including a successful Conducted/Completed) — stored in
    the new outcome_reason column (kept separate from the original
    scheduling `notes`, so "why it was scheduled" and "what happened"
    both stay visible).
  - NEW one-open-at-a-time rule: schedule_site_visit() /
    schedule_follow_up() now reject a new one while an existing
    scheduled (status='scheduled') item of that same kind exists for
    the lead. Close the current one first (any outcome).
  - NEW create_manual_lead() — for walk-ins, references, and offline
    inquiries. Initial stage is restricted to Prospect/Opportunity/
    Site Visited (MANUAL_ENTRY_STAGES) — never Incoming, since a
    manually-entered lead is definitionally not a fresh digital
    inquiry. source='manual_crm' on the row, distinguishing it from
    'meta'/'selldo_only' everywhere else in the system.
  - NEW log_call_tap() — logs a 'call_attempted' activity with a
    timestamp when someone taps a lead's phone number from inside the
    CRM. Deliberately named "attempted," not "made" or "completed" —
    a tel: link handoff to the phone's native dialer gives a web page
    zero visibility into whether the call connected or how long it
    lasted; that's an OS/browser boundary, not something fixable from
    here. Real duration/answered-status/recording is v1.0 Telephony's
    job (OEM call-recording bridge or cloud telephony), exactly as
    already roadmapped — this is a best-effort placeholder signal in
    the meantime, and only covers CRM-initiated taps (a lead calling
    directly, bypassing the CRM, is invisible to this or any web app).
  - get_new_enquiries_count() REDEFINED: was a time-window count
    (leads created in the last N days); now counts leads currently
    sitting at current_stage='Incoming' — i.e. genuinely untriaged,
    regardless of when they arrived. This is a deliberate behavior
    change, not a bug fix — the old definition answered "how many
    leads came in recently," the new one answers the more actionable
    "how many leads still need a first look." NEW get_reengaged_leads()
    is the list-returning counterpart to the existing (unchanged,
    still-approximate) get_reengaged_count().
  - NEW get_due_by_kind(kind) — same due/overdue logic as
    get_due_today(), filtered to just 'site_visit' or 'follow_up',
    feeding the two new dashboard cards (split from the one combined
    Due Today list).
  - NEW get_all_users() — email-to-full_name lookup, used by app.py to
    show a person's NAME instead of their raw email in Activity
    History (the email is still what's actually stored in
    activity_log.actor — accurate and unique for audit purposes — this
    is a display-layer resolution only).

v1.8  (July 2026) — v0.5 Writer: stage changes, notes, assignment,
  site visits, follow-ups. This is the CRM's first WRITE path into
  leads.current_stage / leads.lead_owner — everything before this was
  read-only w.r.t. those two columns from the CRM's side.

  STAGE-CHANGE RULE (locked with Srikanth, confirmed against the live
  Sell.do rule-based engine): stage changes are NOT free-form — only
  specific one-way transitions are allowed, matching Sell.do's own
  rule set exactly. See STAGE_TRANSITIONS below. ALL_STAGES (8 stages)
  is now the complete stage universe; TARGET_STAGES (4 stages) is
  UNCHANGED and still drives ONLY Job C's CAPI firing — the two lists
  serve different purposes and must not be conflated.

  - NEW ALL_STAGES — all 8 real-world stages (vs TARGET_STAGES' 4
    CAPI-firing stages). Purely descriptive/validation use.
  - NEW STAGE_TRANSITIONS — {from_stage: [allowed_to_stages]} whitelist,
    config-not-code, checked by update_lead_stage() before every write.
  - NEW update_lead_stage(cls_id, new_stage, actor) — writes DIRECTLY
    to leads.current_stage (same column Job B writes), validated
    against STAGE_TRANSITIONS using the LIVE stage read at write-time
    (not whatever the caller's page loaded with — closes a race where
    Job B's background sync moves the stage between page-load and
    submit). Logs to the new activity_log table. Every change here
    also unblocks Job C's very next cycle to fire on it (Risk 4's
    current_stage != last_fired_stage check doesn't care WHO wrote
    current_stage) — a genuine, if partial, preview of the
    "near-real-time CAPI firing" payoff, months before v1.0 cutover.
    Deliberately does NOT touch Job B/selldo_to_cls.py's own writes —
    if a salesperson forgets to also update Sell.do during the
    parallel-run period, Job B's next sync (<=2hrs) will overwrite
    this back to Sell.do's version. That's an intentional, code-free
    enforcement signal for the "update BOTH systems" parallel-run
    discipline, not a bug.
  - NEW add_note(cls_id, actor, text) — logs a 'note' activity.
  - NEW reassign_lead_owner(cls_id, new_owner, actor) — writes
    leads.lead_owner directly (same overwrite-on-next-Sell.do-sync
    dynamic as stage, same reasoning), logs 'assignment_change'.
  - NEW activity_log table — universal audit trail for every write
    action above plus site-visit/follow-up scheduling below. Doubles
    as full assignment/stage history without a dedicated table for
    either (Srikanth's call — simple over complex; a dedicated
    analytics table can be added later as a pure backfill if ever
    needed, no rework required).
  - NEW site_visits / follow_ups tables — "missed" status is NEVER
    stored, only computed at query time (now > scheduled_at AND
    status='scheduled') — Srikanth's own design insight from the
    v0.1 session, confirmed correct: a status column that has to be
    proactively flipped to 'missed' is a status that silently never
    flips if nobody remembers to run that job.
  - NEW schedule_site_visit / mark_site_visit_conducted,
    schedule_follow_up / mark_follow_up_completed, get_due_today()
    (feeds the dashboard's Due Today card — the agreed substitute for
    exact-time push notifications, which need a separate iOS 16.4+
    PWA push project).
  - NEW get_activity_log_for_lead(cls_id) — feeds the lead detail
    page's Activity History timeline.
  - upsert_selldo_lead() gains ONE new optional kwarg,
    opportunity_temperature (default "") — Sell.do's separate
    Warm/Hot status column for Opportunity-stage leads (confirmed
    distinct from "Lead Stage" itself). Stored on leads.
    opportunity_temperature via self-healing migration; purely
    additive, does not touch current_stage, TARGET_STAGES, or any
    CAPI-firing logic. selldo_to_cls.py v1.4 is the one caller that
    now passes this through.

  All migrations are self-healing (ALTER TABLE ... IF NOT EXISTS /
  CREATE TABLE IF NOT EXISTS), safe to redeploy against the live DB.
  Jobs A/C/D are completely unaffected by this version — only Job B
  (selldo_to_cls.py v1.4) has one new optional kwarg to pass, and even
  that's backward-compatible (defaults to "" if omitted).

v1.7  (July 2026) — lead-ownership scoping for the CRM (v0.1.4 polish):
  - users table gained owner_match_name (self-healing ALTER) — links a
    salesperson's login to leads.lead_owner (Sell.do's "Attended By"
    text), deliberately kept separate from full_name since the two
    rarely match exactly.
  - create_user() takes an optional owner_match_name param.
  - NEW update_user_owner_match(email, name) — fixes/sets it on an
    already-existing login without touching password or role.
  - get_leads_page() takes an optional owner= filter (case-insensitive
    exact match). app.py enforces this per-role: salespeople are
    force-filtered to their own owner_match_name; admins get an
    optional dropdown to view anyone's pipeline.
  - NEW get_distinct_owners() — powers that admin dropdown.
  All additive, all read-only w.r.t. leads/events_log/comms_log. Jobs
  A-D neither read nor write owner_match_name and are unaffected.

v1.6  (July 2026) — two dashboard stat functions for the CRM's mini
  dashboard (v0.1.2 polish pass):
    get_new_enquiries_count(days)  -> leads first created in the window
    get_reengaged_count(days)      -> APPROXIMATE reengagement signal
  Both are read-only, additive, and unrelated to Jobs A-D. The
  reengaged count is explicitly a heuristic — see its own docstring
  for the exact caveat about what it can't yet distinguish. A precise
  version needs a write-time marker in upsert_meta_lead/upsert_selldo_lead,
  deliberately deferred to v0.5 rather than rushed in here.

v1.5  (July 2026) — users table + auth helpers (CRM v0.1 — Viewer):
  Added for the new in-house CRM's login screen. Purely additive: one
  new table (`users`), created via the same CREATE TABLE IF NOT EXISTS
  pattern as every other table here, plus three new functions
  (create_user, verify_login, get_user_by_id) and four read-only CRM
  query helpers (get_leads_page, get_lead_by_id, get_events_for_lead,
  get_comms_for_lead). Nothing existing was touched — Jobs A/B/C/D
  never call any of this and are unaffected either way. Password
  hashing uses Python's stdlib (hashlib.pbkdf2_hmac + secrets)
  deliberately, NOT Werkzeug/Flask, so this file's dependency
  footprint stays sqlite3 + stdlib only — Jobs A-D keep working even
  if the CRM's Flask environment is ever set up separately from
  the CLS automation environment at C:\\CLS.

v1.4  (June 2026) — get_stale_stage_count() health-signal helper:
  Added as a companion fix to selldo_to_cls.py's EXPORT_START_DATE
  change (rolling 183-day export window replaced with a fixed
  2025-12-01 anchor — see selldo_to_cls.py changelog). That bug's
  most dangerous failure mode wasn't the visible SANITY FAIL abort —
  it was silent: leads that aged out of the old rolling window kept
  their current_stage frozen in cls.db forever, with no error, no
  CAPI fire, no drip progression. This function gives Job B a single
  number to log every cycle — leads stuck on a non-terminal stage for
  90+ days — as an early warning if that failure mode ever recurs in
  some other form.

v1.3  (June 2026) — upsert_selldo_lead accepts lead_owner + selldo_url:
  selldo_to_cls.py v1.3 passes two new kwargs (lead_owner, selldo_url)
  to upsert_selldo_lead(). This file was on v1.2 which did not accept
  those kwargs, causing every single upsert to raise TypeError and be
  silently skipped (2,988 leads, 0 synced). Fix: added both params to
  the function signature (with safe defaults), added them to the UPDATE
  and INSERT SQL, and added self-healing ALTER TABLE migrations so the
  columns appear in any existing cls.db automatically.

v1.2  (June 2026) — Incoming stage added to TARGET_STAGES:
  TARGET_STAGES drives the get_unfired_leads() SQL query. "Incoming"
  was added to cls_capi_firer.py v1.3 but this file's copy was not
  updated simultaneously, so the SQL filter never picked up Incoming
  leads. Both files must agree. This one-line fix unblocks the lead
  coverage improvement.

WHAT THIS FILE IS
-----------------
The single foundation module for the CLS architecture. Every other
job (meta_leads_fetcher, selldo_to_cls, cls_capi_firer) imports THIS
file and calls its functions. No other script talks to SQLite directly.

WHY A SINGLE DB LAYER
---------------------
Three scheduled jobs read and write the same data. If each job wrote
its own SQL, a schema change would mean editing three files, and a
normalization bug in one job would silently break matching everywhere.
One module = one source of truth for the schema AND the rules.

WHAT IT PROVIDES
----------------
  init_db()              -> create the database + table if missing
  norm_phone(raw)        -> India phone normalization (last 10 digits)
  norm_email(raw)        -> email normalization (lowercase, trimmed)
  upsert_meta_lead(...)  -> insert/update a row from a Meta lead   (Job A)
  upsert_selldo_lead(...)-> insert/update a row from a Sell.do lead(Job B)
  get_unfired_leads()    -> rows where current_stage != last_fired_stage (Job C)
  mark_as_fired(...)     -> record a successful CAPI fire          (Job C)
  set_flag() / get_flag()/ is_flag_fresh()  -> completion-flag gating (Risk 1)
  stats()                -> quick counts for logging / dashboards

  --- Job D (email drip) additions in v1.1 ---
  enroll_in_drip(cls_id) -> mark a lead as drip-eligible            (Job D)
  bulk_enroll_drip()     -> backfill: enroll all un-enrolled leads   (Job D)
  get_drip_due(...)      -> leads due for a specific drip email      (Job D)
  record_comms(...)      -> log an email sent to comms_log           (Job D)
  pause_drip / unpause   -> Re Assigned handling                     (Job D)
  mark_opt_out / bounce  -> hard stops                               (Job D)
  drip_stats()           -> email counts for logging                 (Job D)

  --- Auth + read queries added in v1.5 (CRM v0.1 — Viewer) ---
  create_user(...)         -> add a CRM login (admin/salesperson)     (CRM)
  verify_login(...)        -> check email+password, returns user row (CRM)
  get_user_by_id(...)      -> fetch a user row for session lookups    (CRM)
  get_leads_page(...)      -> paginated/filterable lead list          (CRM)
  get_lead_by_id(...)      -> one full lead row                       (CRM)
  get_events_for_lead(...) -> a lead's CAPI fire history              (CRM)
  get_comms_for_lead(...)  -> a lead's email history                  (CRM)

  --- Dashboard stats added in v1.6 (CRM v0.1.2 polish) ---
  get_new_enquiries_count(days) -> count of leads first seen in window (CRM)
  get_reengaged_count(days)     -> APPROX. reengagement signal, caveated (CRM)

  --- Writer functions added in v1.8 (CRM v0.5 — Writer) ---
  update_lead_stage(...)        -> validated stage change + activity log (CRM)
  add_note(...)                 -> log a free-text note                  (CRM)
  reassign_lead_owner(...)      -> change lead_owner + activity log      (CRM)
  schedule_site_visit(...)      -> new site_visits row + activity log    (CRM)
  mark_site_visit_conducted(...)-> flip a site visit to conducted        (CRM)
  schedule_follow_up(...)       -> new follow_ups row + activity log     (CRM)
  mark_follow_up_completed(...) -> flip a follow-up to completed         (CRM)
  get_activity_log_for_lead(...)-> one lead's full activity timeline     (CRM)
  get_site_visits_for_lead(...) -> one lead's full site-visit list       (CRM)
  get_follow_ups_for_lead(...)  -> one lead's full follow-up list        (CRM)
  get_due_today()               -> site visits/follow-ups due or missed  (CRM)

  --- v1.9 refinements (v0.5, first real mobile usage) ---
  update_site_visit(...)        -> conducted/rescheduled/cancelled/no_show (CRM)
  update_follow_up(...)         -> completed/postponed/cancelled          (CRM)
  create_manual_lead(...)       -> walk-in/reference/offline lead entry   (CRM)
  log_call_tap(...)             -> timestamp when a phone link is tapped  (CRM)
  get_reengaged_leads(...)      -> list counterpart to get_reengaged_count(CRM)
  get_due_by_kind(kind)         -> get_due_today() filtered to one kind   (CRM)
  get_all_users()               -> email->full_name lookup for display   (CRM)

  --- v2.10 addition — parallel-run sync-health checkpoint ---
  get_latest_stage_and_owner_changes() -> per-lead latest stage_change +
                                           assignment_change vs current
                                           state, for drift detection
                                           (cls_parallel_export.py, manual)

ONE-TIME SETUP
--------------
  pip install python-dotenv sib-api-v3-sdk
  (sqlite3 ships with Python — nothing else to install)
=============================================================
"""

import math
import os
import re
import sys
import uuid
import sqlite3
import hashlib
import secrets
import calendar
from datetime import datetime, timedelta, timezone

# v2.74: IST offset constant, used ONLY by _format_meta_created_time() to
# convert Meta's tz-aware created_time into actual IST wall-clock digits
# before display. Deliberately narrow — NOT a general timezone abstraction
# for the rest of this file, which stays on the existing server-local
# convention documented at get_site_visits_for_tomorrow() and elsewhere.
IST = timezone(timedelta(hours=5, minutes=30))

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
# All CLS files live in the same folder as the existing automation,
# so paths stay consistent with selldo_capi_automation.py (C:\automation).

BASE_DIR  = r"D:\CLS"
# v2.23: DB target is now config, not code — CLS_DB_PATH env var, defaulting
# to CLS1.db. Set per-process (Task Scheduler task / service launcher) as a
# real OS environment variable — NOT a line in .env (see v2.23 changelog).
DB_FILE   = os.environ.get("CLS_DB_PATH", os.path.join(BASE_DIR, "CLS1.db"))
FLAG_FILE = os.path.join(BASE_DIR, "cls_flags.json")  # completion flags between jobs — shared, unaffected by DB split

# Target CRM stages — same three as the existing CAPI script.
# Kept here so all CLS jobs share one definition.
TARGET_STAGES = ["Incoming", "Prospect", "Opportunity", "Site Visited"]

# ── ALL_STAGES + STAGE_TRANSITIONS (v1.8 — CRM v0.5 Writer) ──
# ALL_STAGES is the COMPLETE 8-stage universe — do not confuse this
# with TARGET_STAGES above, which is a DIFFERENT, smaller list that
# exists only to drive Job C's CAPI firing. Adding a stage here does
# NOT make Job C fire on it; that's TARGET_STAGES' job alone.
ALL_STAGES = [
    "Incoming", "Prospect", "Opportunity", "Site Visited",
    "Unqualified", "Lost", "Re Assigned", "Booked",
]

# Whitelist of allowed one-way transitions, matching Sell.do's own
# rule-based stage engine exactly (locked with Srikanth, 2026-07).
# Stage changes are NEVER free-form — update_lead_stage() rejects
# anything not listed here for the lead's CURRENT stage. Config-not-
# code: to change the rule, edit only this dict.
#
# Checked for consistency when this was designed: every stage has at
# least one outgoing transition (no dead ends — even Booked can unwind
# back to Prospect if a deal falls through), and every stage except
# Incoming has at least one incoming transition (no orphans — Incoming
# is correctly the only stage nothing transitions INTO, since it's
# where Job A places brand-new leads).
STAGE_TRANSITIONS = {
    "Incoming"     : ["Prospect", "Unqualified", "Re Assigned"],
    "Prospect"     : ["Opportunity", "Unqualified", "Re Assigned"],
    "Opportunity"  : ["Booked", "Lost", "Site Visited", "Re Assigned"],
    "Site Visited" : ["Booked", "Lost", "Re Assigned"],
    "Unqualified"  : ["Prospect", "Re Assigned"],
    "Lost"         : ["Prospect", "Re Assigned"],
    "Re Assigned"  : ["Prospect", "Opportunity", "Unqualified"],
    "Booked"       : ["Prospect"],
}

# v2.20 (July 2026) — Task 3: which stages get reset to "Incoming" when
# a lead re-enters through upsert_meta_lead()'s contact-match (enrich)
# branch. Config-not-code: to change which stages count as "dead enough
# to restart the funnel", edit only this tuple — see
# _apply_reengagement_marker() for where it's applied. A lead currently
# in any OTHER stage keeps its stage exactly as today (only
# reengaged_at gets stamped).
RESET_STAGES_ON_REENGAGEMENT = ("Unqualified", "Lost", "Booked")

# Allowed INITIAL stages for a manually-entered lead (v1.9). Never
# "Incoming" — a manual entry is definitionally not a fresh digital
# inquiry; it's a walk-in, a reference, or an offline call, so it
# starts wherever it genuinely is in the funnel already.
MANUAL_ENTRY_STAGES = ["Incoming", "Prospect", "Opportunity", "Site Visited"]

# ── Notifications v1.0 (v2.72) ──────────────────────────────────────
# Config-not-code, same doctrine as STAGE_TRANSITIONS/RESET_STAGES_ON_
# REENGAGEMENT above: adding a 9th event later is one dict entry here +
# one insert_notification() call site, never a new code branch.
#
# {full_name}/{project} are filled in with str.format() at insert time
# by whichever call site renders the message (each hook/the poller
# already has the lead row in hand).
NOTIFICATION_EVENTS = {
    "new_enquiry":         "New enquiry: {full_name} ({project})",
    "lead_reengaged":      "{full_name} re-engaged — was previously in your pipeline",
    "lead_reassigned":     "Lead reassigned to you: {full_name}",
    "lead_cross_reassigned": "Lead auto-reassigned to you: {full_name} ({project})",
    "followup_due":        "Follow-up due today: {full_name}",
    "followup_overdue_1d": "Follow-up overdue by 1 day: {full_name}",
    "visit_tomorrow":      "Site visit scheduled tomorrow: {full_name}",
    "visit_due_now":       "Site visit due now: {full_name}",
    "visit_overdue_1d":    "Site visit overdue by 1 day: {full_name}",
    "late_punch_in":       "{full_name} punched in late by {minutes} min today",
    "early_punch_out":     "{full_name} punched out early by {minutes} min today",
}

# Read by cls_notifications_poller.py only — new_enquiry/lead_reengaged/
# lead_reassigned are instant hooks (see upsert_meta_lead()/
# reassign_lead_owner()), not polled. offset_hours: 0 = due now,
# +24 = 24h before scheduled_at (tomorrow), -24 = 24h after (overdue by
# a day). extra_where is ANDed in raw (no user input reaches it — values
# are fixed strings here, never request data).
NOTIFICATION_TRIGGERS = {
    "followup_due":        ("follow_ups",  "scheduled_at", 0,   "status='scheduled'"),
    "followup_overdue_1d": ("follow_ups",  "scheduled_at", -24, "status='scheduled'"),
    "visit_tomorrow":      ("site_visits", "scheduled_at", 24,  "status='scheduled'"),
    "visit_due_now":       ("site_visits", "scheduled_at", 0,   "status='scheduled'"),
    "visit_overdue_1d":    ("site_visits", "scheduled_at", -24, "status='scheduled'"),
}

# PAUSED (v2.25) — superseded by Campaign Routing (campaign_routing_rules
# + app_settings['default_fallback_owner'], see resolve_owner_for_new_
# lead() below). Kept here as historical reference only; nothing reads
# these anymore. The project-keyed defaults below became campaign-keyed
# routing rules; the "Naishka"/"Grace Classic" project keys do NOT carry
# over automatically — routing rules must be configured fresh via
# /settings/campaign-routing if the same defaults are wanted per campaign.
#
# DEFAULT_OWNER_BY_PROJECT = {
#     "Naishka":       "Elohar Peddi",
#     "Grace Classic": "Devender Goud",
# }
# FALLBACK_DEFAULT_OWNER = "Mounika Peddi"

# v2.0 — source options for manually-entered leads only. Auto-captured
# leads keep their system-level source ('meta'/'selldo_only') as
# before; this is a separate, more specific classification, only ever
# set at manual-entry time and then locked (see update_lead_source_
# detail's docstring for why).
MANUAL_SOURCE_OPTIONS = ["Walk-In", "Meta", "Channel Partner", "Youtube", "Referral", "Website"]

# v2.0 — richer lead attributes, editable on any lead. Adjust these
# lists any time; they're config, not code.
FUNDING_SOURCES = ["Loan", "Self"]
PROPERTY_TYPES = ["Apartment", "Villa", "Plot", "Duplex", "Penthouse", "Row House"]
CONFIGURATIONS = ["1 BHK", "2 BHK", "3 BHK", "4 BHK", "5 BHK", "6 BHK+"]

# v2.3 — budget brackets, config-not-code. Deliberately brackets, not
# free text — a free-text budget field can't be filtered/sorted on the
# leads list (Srikanth's item 8), a bracket list can.
BUDGET_BRACKETS = ["<50L", "50L-75L", "75L-1Cr", "1Cr-1.5Cr", "1.5Cr+"]

# v2.3 — facing, multi-select (a corner unit can face two directions).
FACING_OPTIONS = ["East", "West", "North", "South"]

# v2.3 — Lost/Unqualified reason lists (Srikanth's exact wording,
# 2026-07). RADIO-style single selection per lead per stage-change —
# see update_lead_stage()'s reason_code param. Config-not-code: add or
# reword a reason here, no code change needed anywhere else.
#
# PAUSED — retained for historical Lost reason codes + easy revert
# (v2.11, July 2026). Srikanth's decision 5: the Lost picker now shows
# UNQUALIFIED_REASONS instead (see STAGE_REASON_LISTS below), but any
# lead already marked Lost with one of THESE codes must stay readable
# and filterable — leads_filter_screen()'s stage_reasons still unions
# this list with UNQUALIFIED_REASONS for exactly that reason. Not
# deleted, not dead code: still the source of truth for old data.
LOST_REASONS = [
    "Price negotiations failed",
    "Fund availability issue",
    "Bank loan declined",
    "Payment terms not adhered",
    "AOS not executed within agreed time",
    "Death of applicant",
    "Unit swap",
    "Other reasons",
]

UNQUALIFIED_REASONS = [
    "Looking for Under Construction",
    "Looking for ready to move",
    "Not Looking to buy now",
    "Budget does not match",
    "Location mismatch",
    "Looking for smaller property",
    "Looking for bigger property",
    "False enquiry",
    "Possession date mismatch",
    "Invalid customer contact",
    "Customer already booked somewhere else",
    "Not answering/responding to us",
    "Not Interested",
    "Is a channel partner",
    "Requirement floor not matching",
]

# v2.11 (July 2026) — STAGE_REASON_LISTS: which reason list gates each
# stage-change reason_code, keyed by new_stage. Srikanth's decision 5:
# Lost now uses the SAME 15 Unqualified reasons instead of its own
# 8-item list (LOST_REASONS above stays defined/PAUSED for historical
# data only — see its docstring). update_lead_stage() below validates
# reason_code against THIS dict instead of two hardcoded if/elif
# branches, so adding a third reason-gated stage later is a one-line
# dict entry, not a new elif. Config-not-code, single source of truth.
STAGE_REASON_LISTS = {
    "Lost":         UNQUALIFIED_REASONS,
    "Unqualified":  UNQUALIFIED_REASONS,
}

# v2.5 — leads-list Sort By filter. Config-not-code, whitelisted lookup
# ONLY — get_leads_page() falls back to "recent" for any key not in
# here, so a request can never smuggle raw SQL into ORDER BY.
SORT_OPTIONS = {
    "recent":       "cls_updated_at DESC",   # default — most recently touched first
    "created_desc": "cls_created_at DESC",   # newest inquiry first
    "created_asc":  "cls_created_at ASC",    # oldest inquiry first
    "name_asc":     "full_name COLLATE NOCASE ASC",
}

# v2.5 — leads-list Source filter. The 3 real values leads.source ever
# holds (see upsert_meta_lead / upsert_selldo_lead / create_manual_lead).
# Distinct from lead_source_detail (MANUAL_SOURCE_OPTIONS above) — see
# the v2.5 changelog for why both filters exist separately.
SOURCE_OPTIONS = ["meta", "selldo_only", "manual_crm"]

# v2.31 — human-readable labels for the raw SOURCE_OPTIONS values, used
# by the Leads to Booking Summary tab's Source filter + "Lead By Source"
# breakdown. Config-not-code: leads.source itself is unchanged, this is
# a display-layer mapping only (same principle as get_all_users()'s
# email->full_name resolution for Activity History).
SOURCE_DISPLAY_LABELS = {
    "meta": "Meta",
    "selldo_only": "Sell.do",
    "manual_crm": "Manually Entered",
}

# v2.31 — Leads to Booking Summary's "Site Visits By Status" breakdown.
# Sell.do's own report has 6 states (Missed/Conducted/Cancelled/
# Scheduled/Pending/Dropped); our site_visits.status column only has 4
# ('scheduled'/'conducted'/'cancelled'/'no_show' — see schema below).
# Decision 4 (Srikanth, July 2026): map what we actually have rather
# than invent permanent-zero rows for "Pending"/"Dropped", which we have
# no equivalent state for. "Scheduled" vs "Missed" aren't two different
# stored values — both are status='scheduled' rows, split live by
# whether scheduled_at has already passed (same missed-computation
# principle as get_due_today() above). "Didn't Visit" (not "Missed",
# which means something different in our system — see lead_detail.html)
# maps status='no_show'. get_site_visits_by_status_for_period() is the
# only reader of this dict; kept here, not inline, so the row order/
# labels are config, not scattered string literals.
SITE_VISIT_STATUS_LABELS = ["Conducted", "Cancelled", "Didn't Visit", "Scheduled", "Missed"]

# v2.28 — bulk_jobs.job_type whitelist (config-not-code, same pattern as
# SORT_OPTIONS/SOURCE_OPTIONS above). Only one bulk action ships in this
# batch; the table/constant are written generically so a future bulk
# action (e.g. a bulk export history log) can add its own type here
# rather than needing a second history table.
BULK_JOB_TYPES = ("bulk_reassign",)

# ── Drip email schedule (Job D) ──
# Each CRM stage that gets automated emails, and on which days.
# Day numbers are relative to MAX(drip_enrolled_at, stage_updated_at).
# To add a new stage or change timing, edit ONLY this dict — Job D
# reads it at runtime, so no code changes are needed.
DRIP_SCHEDULE = {
    "Incoming"     : [1, 3],         # 2 emails: Day 1, Day 3
    "Prospect"     : [1, 4, 10],     # 3 emails: Day 1, Day 4, Day 10
    "Opportunity"  : [1, 5],         # 2 emails: Day 1, Day 5
    "Site Visited" : [1],            # 1 email:  Day 1 only
}

# Stages that PAUSE the drip (lead is in transit, not a real funnel stage).
# When a lead exits one of these into a real stage, the drip unpauses
# and restarts at Day 1 of the new stage.
DRIP_PAUSE_STAGES = ["Re Assigned"]

# Terminal stages — lead leaves the funnel permanently. Drip stops forever.
DRIP_TERMINAL_STAGES = ["Booked", "Lost", "Unqualified"]

# ── Lead scoring (v2.2) ──
# PAUSED (v2.26) — superseded by the app_settings['lead_score_config']
# row (see _LEAD_SCORE_CONFIG_SEED + get_lead_score_config()/
# set_lead_score_config() below), editable via /settings/lead-scoring
# instead of a code change. Kept here as historical/audit reference
# only — compute_lead_scores() no longer reads either of these.
#
# LEAD_SCORE_RULES = {
#     "stage_points": {
#         "Incoming"     : 5,
#         "Prospect"     : 15,
#         "Opportunity"  : 30,
#         "Site Visited" : 50,
#         "Booked"       : 100,
#         "Unqualified"  : 0,
#         "Lost"         : 0,
#         "Re Assigned"  : 0,
#     },
#     "temperature_points": {"Warm": 15, "Hot": 30},
#     "site_visit_conducted": 25,
#     "site_visit_no_show"  : -15,
#     "follow_up_completed" : 10,
#     "note_points_per_day"     : 2,
#     "call_tap_points_per_day" : 5,
#     "decay_after_days"      : 14,
#     "decay_points_per_period": -10,
#     "decay_exempt_stages"    : ["Site Visited", "Opportunity", "Booked"],
# }
#
# LEAD_SCORE_BANDS = [
#     (70, "Hot"),
#     (30, "Warm"),
#     (0,  "Cold"),
# ]

# (v2.26) Live seed data for the ONE-TIME app_settings['lead_score_config']
# migration in init_db() — the exact same values as the PAUSED
# LEAD_SCORE_RULES dict above, plus hot_threshold/warm_threshold
# collapsed from LEAD_SCORE_BANDS' 3-tuple list (labels Cold/Warm/Hot
# stay fixed, not stored/editable — Srikanth's simplification call for
# this first version; full label editing can be added later if wanted).
_LEAD_SCORE_CONFIG_SEED = {
    "stage_points": {
        "Incoming"     : 5,
        "Prospect"     : 15,
        "Opportunity"  : 30,
        "Site Visited" : 50,
        "Booked"       : 100,
        "Unqualified"  : 0,
        "Lost"         : 0,
        "Re Assigned"  : 0,
    },
    "temperature_points": {"Warm": 15, "Hot": 30},
    "site_visit_conducted": 25,
    "site_visit_no_show"  : -15,
    "follow_up_completed" : 10,
    "note_points_per_day"     : 2,
    "call_tap_points_per_day" : 5,
    "decay_after_days"      : 14,
    "decay_points_per_period": -10,
    "decay_exempt_stages"    : ["Site Visited", "Opportunity", "Booked"],
    "hot_threshold"  : 70,
    "warm_threshold" : 30,
}

# (v2.26) Required numeric top-level keys for set_lead_score_config()'s
# validation — everything except stage_points/temperature_points (nested
# dicts, validated separately) and decay_exempt_stages (a list).
_LEAD_SCORE_CONFIG_REQUIRED_NUMERIC = [
    "site_visit_conducted", "site_visit_no_show", "follow_up_completed",
    "note_points_per_day", "call_tap_points_per_day",
    "decay_after_days", "decay_points_per_period",
    "hot_threshold", "warm_threshold",
]

# ── Project name → display bucket ──
# PAUSED (v2.24) — superseded by the project_aliases TABLE, seeded from
# this exact dict ONE TIME ONLY at migration (see _PROJECT_ALIASES_SEED
# + init_db() below). Kept here as historical/audit reference only —
# nothing in the codebase reads this dict anymore; do not resurrect a
# call site against it, use get_project_bucket()/get_all_bucket_names().
#
# PROJECT_BUCKETS = {
#     # ── Naishka Homes umbrella (Bandlaguda Jagir cluster — adjacent
#     #    projects bucketed together per Srikanth's call, 2026-06-21) ──
#     "Naishka"                          : "Naishka Homes",
#     "Naishka Prism"                    : "Naishka Homes",
#     "Naishka Pavilion"                 : "Naishka Homes",
#     "Naishka Prestige"                 : "Naishka Homes",
#     "Naishka Pristine"                 : "Naishka Homes",
#     "Pavan Classic"                    : "Naishka Homes",
#     "Sri Marvel"                       : "Naishka Homes",
#     "Madhavi Residency"                : "Naishka Homes",
#     "Saanvi Elite Bandlaguda Jagir"    : "Naishka Homes",
#
#     # ── Grace Classic (spacing/dash export variants only) ──
#     "Grace Classic"                    : "Grace Classic",
#     "Grace Classic - Kokapet"          : "Grace Classic",
#     "Grace Classic   Kokapet"          : "Grace Classic",   # double-space, no dash
#
#     # ── Prima Paradiso (already clean, listed for completeness) ──
#     "Prima Paradiso"                   : "Prima Paradiso",
#
#     # ── Praga Enclave — separate old project, still active, NOT merged
#     #    into Naishka Homes despite being nearby ──
#     "Praga Enclave"                    : "Praga Enclave",
# }

# (v2.24) The literal seed data for the ONE-TIME project_aliases migration
# in init_db() — byte-for-byte the same pairs as the PAUSED dict above.
# Kept as a separate, live (uncommented) constant because the dict above
# is intentionally inert; this is the actual source init_db() reads.
_PROJECT_ALIASES_SEED = {
    "Naishka"                          : "Naishka Homes",
    "Naishka Prism"                    : "Naishka Homes",
    "Naishka Pavilion"                 : "Naishka Homes",
    "Naishka Prestige"                 : "Naishka Homes",
    "Naishka Pristine"                 : "Naishka Homes",
    "Pavan Classic"                    : "Naishka Homes",
    "Sri Marvel"                       : "Naishka Homes",
    "Madhavi Residency"                : "Naishka Homes",
    "Saanvi Elite Bandlaguda Jagir"    : "Naishka Homes",
    "Grace Classic"                    : "Grace Classic",
    "Grace Classic - Kokapet"          : "Grace Classic",
    "Grace Classic   Kokapet"          : "Grace Classic",
    "Prima Paradiso"                   : "Prima Paradiso",
    "Praga Enclave"                    : "Praga Enclave",
}

# (v2.24) Module-level cache for project_aliases, {alias: project_bucket}.
# None means "not loaded yet" — get_project_bucket()/get_all_bucket_names()
# lazily populate it via _load_project_bucket_cache(). Invalidated by
# reload_project_bucket_cache(), called after every add/delete.
_PROJECT_BUCKET_CACHE = None


def _load_project_bucket_cache():
    """
    (v2.24) Loads every project_aliases row into the module cache as a
    plain {alias: project_bucket} dict, replacing whatever was cached
    before. Called lazily by get_project_bucket()/get_all_bucket_names()
    whenever the cache is None.
    """
    global _PROJECT_BUCKET_CACHE
    conn = _connect()
    try:
        rows = conn.execute("SELECT alias, project_bucket FROM project_aliases").fetchall()
    finally:
        conn.close()
    _PROJECT_BUCKET_CACHE = {r["alias"]: r["project_bucket"] for r in rows}
    return _PROJECT_BUCKET_CACHE


def reload_project_bucket_cache():
    """
    (v2.24) Invalidates the module-level project-bucket cache so the
    next get_project_bucket()/get_all_bucket_names() call reloads fresh
    from project_aliases. Call this after every
    add_project_alias()/delete_project_alias() — both already do.
    """
    global _PROJECT_BUCKET_CACHE
    _PROJECT_BUCKET_CACHE = None


def get_project_bucket(raw_project):
    """
    Collapse a raw events_log/leads `project` value into its display
    bucket using the project_aliases table (via the lazy module cache;
    see PAUSED PROJECT_BUCKETS note above for what this replaced).

    Handles three real-world shapes seen in Sell.do exports:
      1. A clean single name              -> looked up directly
      2. A known spacing/naming variant   -> looked up directly
      3. A comma-joined multi-project string (executives add projects
         to a lead's CRM record as interest expands after a site visit)
         -> the FIRST project listed is used (it's almost always the
            lead's original enquiry, before others were added)

    Unknown names fall through unchanged (so a brand-new project
    just works without needing a code change — it shows under its
    own raw name until someone adds it via /settings/projects).

    Returns "(unknown)" for None/blank input.
    """
    if not raw_project:
        return "(unknown)"

    if _PROJECT_BUCKET_CACHE is None:
        _load_project_bucket_cache()

    first = raw_project.split(",")[0].strip()
    return _PROJECT_BUCKET_CACHE.get(first, first)


def get_all_bucket_names():
    """
    (v2.24) Sorted distinct bucket names — drop-in replacement for the
    old sorted(set(PROJECT_BUCKETS.values())) call sites in app.py
    (leads_filter, lead_detail, lead_new, both WhatsApp template admin
    screens). Same output shape: a plain sorted list of strings.
    """
    if _PROJECT_BUCKET_CACHE is None:
        _load_project_bucket_cache()
    return sorted(set(_PROJECT_BUCKET_CACHE.values()))


def list_project_buckets():
    """
    (v2.24) All project aliases grouped by bucket, sorted by bucket name
    then alias, for the /settings/projects admin screen. Returns:
      [{"bucket": "Naishka Homes", "aliases": ["Naishka", "Naishka Prism", ...]}, ...]
    Reads straight from the DB (not the cache) so the admin screen always
    shows the true current state even mid-edit.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT alias, project_bucket FROM project_aliases "
            "ORDER BY project_bucket COLLATE NOCASE, alias COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()

    grouped = {}
    order = []
    for r in rows:
        bucket = r["project_bucket"]
        if bucket not in grouped:
            grouped[bucket] = []
            order.append(bucket)
        grouped[bucket].append(r["alias"])

    return [{"bucket": b, "aliases": grouped[b]} for b in order]


def add_project_alias(alias, project_bucket):
    """
    (v2.24) Add or repoint one alias -> bucket mapping. A brand-new
    project (no aliases yet) is just alias == project_bucket, e.g.
    add_project_alias("Prima Casa", "Prima Casa"). INSERT OR REPLACE
    keyed on alias (COLLATE NOCASE on the column), so re-adding the
    same alias (any case) with a different bucket simply repoints it.

    Raises ValueError if either argument is blank.
    """
    alias = (alias or "").strip()
    project_bucket = (project_bucket or "").strip()
    if not alias or not project_bucket:
        raise ValueError("Both an alias and a project bucket name are required.")

    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO project_aliases (alias, project_bucket, created_at) VALUES (?, ?, ?)",
            (alias, project_bucket, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    reload_project_bucket_cache()
    _recompute_all_project_buckets()


def delete_project_alias(alias):
    """
    (v2.24) Delete one alias row. No blocking logic needed — if every
    alias for a bucket ends up deleted, get_project_bucket() already
    falls through gracefully to the raw name unchanged, same as an
    unknown project today.
    """
    conn = _connect()
    try:
        conn.execute("DELETE FROM project_aliases WHERE alias=?", (alias,))
        conn.commit()
    finally:
        conn.close()
    reload_project_bucket_cache()
    _recompute_all_project_buckets()


def _recompute_all_project_buckets():
    """
    (v2.66) F2 Phase 2: full recompute of leads.project_bucket across
    every row, driven by the current project_aliases mapping. Called
    after reload_project_bucket_cache() in both add_project_alias() and
    delete_project_alias() — that order matters, so get_project_bucket()
    below picks up the freshly-invalidated/reloaded alias cache rather
    than a stale one.

    Intentionally a full recompute of every distinct leads.project value
    (not a targeted "which leads does this one alias affect" pass) —
    simpler and safe at ~8k rows, per the F2 Phase 2 planning decision.
    One UPDATE per distinct raw project value (grouped, not per-row), so
    this is cheap even though it's a full pass.

    Reuses get_project_bucket() directly for the bucket computation, so
    the stored column can never drift from what that function would
    return live. NULL project values are handled explicitly via a
    separate "IS NULL" branch, since "WHERE project = NULL" never
    matches in SQL — blank-string ("") values need no special case,
    ordinary equality matches those fine.

    Any exception propagates. This runs synchronously inside an admin
    action (alias add/delete); a failed recompute must surface as an
    error to the admin, not be swallowed while leads silently drift out
    of sync with the new alias mapping.
    """
    conn = _connect()
    try:
        rows = conn.execute("SELECT DISTINCT project FROM leads").fetchall()
        for r in rows:
            raw = r["project"]
            bucket = get_project_bucket(raw)
            if raw is None:
                conn.execute(
                    "UPDATE leads SET project_bucket=? WHERE project IS NULL",
                    (bucket,),
                )
            else:
                conn.execute(
                    "UPDATE leads SET project_bucket=? WHERE project=?",
                    (bucket, raw),
                )
        conn.commit()
    finally:
        conn.close()


def _campaign_bucket(raw_campaign):
    """
    (v2.13) Collapse a raw leads.campaign value into a display bucket
    for the Campaign Insights reports. No known-variant alias table
    like PROJECT_BUCKETS — campaign is free text with only one non-
    blank value in the live DB as of this writing (see v2.13 changelog
    HONESTY NOTE), so there's nothing to collapse yet. Blank/NULL
    becomes the literal "Unknown/Manual" bucket rather than being
    dropped, so campaign-grouped totals still add up to the full lead
    count in scope.
    """
    if raw_campaign and raw_campaign.strip():
        return raw_campaign.strip()
    return "Unknown/Manual"


# ─────────────────────────────────────────────────────────────
# CONNECTION HELPER
# ─────────────────────────────────────────────────────────────

def _connect():
    """
    Open a SQLite connection with settings tuned for THREE concurrent jobs.

    WAL mode  : Write-Ahead Logging. Lets readers and a writer work at the
                same time without blocking each other. Critical because
                Job A might be writing while Job C is reading.
    timeout=30: If the DB is briefly locked by another job, wait up to
                30s instead of crashing instantly.
    """
    os.makedirs(BASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row   # rows behave like dicts: row["phone_norm"]
    return conn


def _now():
    """Single timestamp format used everywhere in CLS."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _next_crm_lead_no(conn):
    """
    Next sequential display ID (v1.9) — computed as MAX+1 on the SAME
    open connection as the INSERT that will use it. See the v1.9
    changelog note on why this is "correct for this system's actual
    write frequency" rather than airtight against a true simultaneous
    double-insert across two separate processes.
    """
    row = conn.execute("SELECT COALESCE(MAX(crm_lead_no), 0) m FROM leads").fetchone()
    return row["m"] + 1


def _insert_lead_with_lead_no_retry(conn, do_insert, max_attempts=5):
    """
    Race-condition guard for crm_lead_no (v2.82). _next_crm_lead_no()'s
    SELECT MAX+1 is two separate steps with no atomic guard — fine at
    this system's original write frequency, but a live risk since the
    Meta webhook (real-time, since 2026-08-13) started running in
    parallel with Job A polling: two near-simultaneous inserts can read
    the same MAX before either commits, producing a duplicate
    crm_lead_no (see idx_leads_crm_lead_no, the UNIQUE index added in
    init_db() this same version, which is what actually surfaces the
    collision as an error instead of silently allowing it).

    do_insert(crm_lead_no) must perform the INSERT (and only the
    INSERT) using the crm_lead_no it's given. On a sqlite3.IntegrityError
    naming crm_lead_no, this recomputes a fresh next number (via
    _next_crm_lead_no()) and retries, up to max_attempts times total.
    Any OTHER IntegrityError (e.g. a real cls_id/PRIMARY KEY collision)
    propagates immediately, unretried. Returns the crm_lead_no that
    was actually used for the successful insert.

    Safe to retry within the same open transaction: SQLite's default
    ON CONFLICT behavior for a UNIQUE violation is ABORT, which rolls
    back only the failed statement, not the whole transaction — no
    connection/transaction reset needed between attempts.
    """
    last_err = None
    for _attempt in range(1, max_attempts + 1):
        crm_lead_no = _next_crm_lead_no(conn)
        try:
            do_insert(crm_lead_no)
            return crm_lead_no
        except sqlite3.IntegrityError as e:
            if "crm_lead_no" not in str(e):
                raise
            last_err = e
    raise last_err


# ─────────────────────────────────────────────────────────────
# SCHEMA  —  the CLS 'leads' table
# ─────────────────────────────────────────────────────────────

def init_db():
    """
    Create the database and the 'leads' table if they do not exist.
    Safe to call on every job run — does nothing if already present.

    SCHEMA RATIONALE (per column group):
      Identity   : cls_id is the PERMANENT key. leadgen_id is critical
                   data but NULLable (non-Meta leads have none).
      Match keys : phone_norm + email_norm are INDEXED — the matcher
                   joins on these, so indexes keep it fast.
      Fire state : current_stage vs last_fired_stage is the Risk-4 fix.
                   Job C fires only when they differ.
    """
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            -- ── Identity ──
            cls_id            TEXT PRIMARY KEY,   -- generated UUID, permanent
            leadgen_id        TEXT,               -- Meta lead id (deterministic match key)
            form_id           TEXT,               -- which Meta lead form
            project           TEXT,               -- Naishka / Grace Classic / Prima Paradiso

            -- ── Contact ──
            full_name         TEXT,
            phone_raw         TEXT,               -- as received, untouched
            phone_norm        TEXT,               -- last 10 digits — THE join key
            email_raw         TEXT,
            email_norm        TEXT,               -- lowercased — fallback join key

            -- ── Meta side ──
            meta_created_time TEXT,               -- when lead submitted on Meta

            -- ── Sell.do side ──
            selldo_lead_id    TEXT,               -- Sell.do "Lead's Id"
            current_stage     TEXT,               -- latest CRM stage
            stage_updated_at  TEXT,               -- when stage last changed in CLS
            match_tier        TEXT,               -- phone+email / phone / email / unmatched

            -- ── CAPI fire state (Risk 4) ──
            last_fired_stage  TEXT,               -- last stage fired to Meta
            last_fired_at     TEXT,               -- when last fired

            -- ── Bookkeeping ──
            source            TEXT,               -- meta / selldo_only
            cls_created_at    TEXT,
            cls_updated_at    TEXT
        );
    """)
    # Indexes on the match keys — the matcher does lookups on these constantly.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_phone ON leads(phone_norm);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email ON leads(email_norm);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leadgen ON leads(leadgen_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(current_stage);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(cls_created_at);")

    # ── events_log table — historical record of every CAPI fire ──
    # The 'leads' table holds each lead's CURRENT state (last_fired_stage).
    # This table is APPEND-ONLY: one row per fire event, ever. It is what
    # the dashboard reads to show a running history — the proper, queryable
    # successor to the old script's events_log.json file.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events_log (
            event_row_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            fired_at      TEXT,    -- when Job C fired this event
            cls_id        TEXT,    -- which lead (links to leads table)
            leadgen_id    TEXT,    -- Meta lead id, if the lead had one
            full_name     TEXT,
            phone_norm    TEXT,
            project       TEXT,
            crm_stage     TEXT,    -- the CRM stage that triggered the fire
            prev_stage    TEXT,    -- the stage the lead was at BEFORE this fire
            meta_event    TEXT,    -- the Meta event name sent
            value_inr     INTEGER, -- the INR value parameter
            used_leadgen  INTEGER, -- 1 = fired WITH leadgen_id, 0 = hashed only
            dataset_id    TEXT     -- which dataset it was fired to
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evt_firedat ON events_log(fired_at);")

    # ── Self-healing migration: add prev_stage to events_log if missing ──
    # The events_log table was originally created without a prev_stage
    # column. CREATE TABLE IF NOT EXISTS will NOT alter an existing table,
    # so for any cls.db built before this version we add the column here.
    # ALTER TABLE ADD COLUMN is safe and instant; existing rows get NULL,
    # which the dashboard renders as a dash. Idempotent — runs once.
    cols = [r["name"] for r in
            conn.execute("PRAGMA table_info(events_log)").fetchall()]
    if "prev_stage" not in cols:
        conn.execute("ALTER TABLE events_log ADD COLUMN prev_stage TEXT;")

    # ── Self-healing migration: add lead_owner to events_log (v2.1) ──
    # Captures WHO owned the lead at the moment it fired — permanent
    # historical attribution, immune to later reassignment. Same
    # ALTER TABLE pattern as prev_stage above.
    if "lead_owner" not in cols:
        conn.execute("ALTER TABLE events_log ADD COLUMN lead_owner TEXT;")

    # ── Self-healing migration: add lead_snapshot_json/snapshot_source
    # to events_log (v2.78) ──
    # Freezes the lead's full row (json.dumps) at the moment each CAPI
    # event fires, alongside the historical fields already captured
    # above (prev_stage, lead_owner) — so a later report can show
    # exactly what the lead looked like at fire time, not its
    # current (possibly since-changed) state. Same ALTER TABLE
    # pattern as prev_stage/lead_owner above.
    if "lead_snapshot_json" not in cols:
        conn.execute("ALTER TABLE events_log ADD COLUMN lead_snapshot_json TEXT;")
    if "snapshot_source" not in cols:
        conn.execute("ALTER TABLE events_log ADD COLUMN snapshot_source TEXT;")

    # ── comms_log table — every email Job D sends is logged here ──
    # Append-only, like events_log. One row per email sent. Job D checks
    # this before sending to avoid duplicates (same lead + same stage +
    # same day_number = already sent, skip). The dashboard can read this
    # to show email activity alongside CAPI fires.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comms_log (
            comms_row_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at         TEXT,       -- when Job D sent this email
            cls_id          TEXT,       -- which lead (links to leads table)
            project         TEXT,       -- Naishka / Grace Classic / Prima Paradiso
            drip_stage      TEXT,       -- CRM stage this email belongs to
            day_number      INTEGER,    -- Day 1 / Day 3 / Day 4 etc.
            template_key    TEXT,       -- identifies the template used
            sender_email    TEXT,       -- which sales@asianbuild.in sent it
            brevo_message_id TEXT,      -- Brevo's id for tracking/debugging
            status          TEXT        -- sent / bounced / failed
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comms_cls ON comms_log(cls_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comms_sent ON comms_log(sent_at);")

    # ── Self-healing migration: add drip columns to leads table ──
    # Same ALTER TABLE pattern as prev_stage above. Safe, instant,
    # idempotent. Existing leads get NULL / 0 defaults, which is correct:
    # NULL drip_enrolled_at = "not yet enrolled" (bulk_enroll_drip fills it).
    lead_cols = [r["name"] for r in
                 conn.execute("PRAGMA table_info(leads)").fetchall()]

    drip_migrations = [
        ("drip_enrolled_at",        "TEXT"),     # when this lead entered the drip system
        ("drip_paused",             "INTEGER"),  # 1 = paused (Re Assigned); 0/NULL = active
        ("email_opt_out",           "INTEGER"),  # 1 = never email again
        ("email_hard_bounce",       "INTEGER"),  # 1 = address is permanently invalid
        # v1.3 — sourced from Sell.do "Attended By" field
        ("lead_owner",              "TEXT"),     # executive assigned to this lead
        # v1.3 — Sell.do profile URL (=HYPERLINK extracted by Job B)
        ("selldo_url",              "TEXT"),     # direct link to lead in Sell.do
        # v1.8 — Sell.do's separate Warm/Hot column, meaningful only
        # when current_stage='Opportunity'. Purely additive/display;
        # does not affect current_stage, TARGET_STAGES, or CAPI firing.
        ("opportunity_temperature", "TEXT"),
        # v1.9 — friendly sequential ID (e.g. crm_lead_no=183 -> shown
        # as "APX-183"), since cls_id is a UUID never meant to be read
        # aloud. Backfilled below for any existing NULL rows.
        ("crm_lead_no",             "INTEGER"),
        # v2.0 — richer lead attributes, all optional/nullable, all
        # editable independently of when/how the lead was created.
        ("lead_source_detail",      "TEXT"),   # manual entries only; locked after creation
        ("funding_source",          "TEXT"),   # Loan / Self
        ("property_type",           "TEXT"),   # Apartment / Villa / Plot / ... (v2.3: comma-separated, multi-select)
        ("configuration",           "TEXT"),   # 1 BHK .. 6 BHK+ (v2.3: comma-separated, multi-select)
        ("campaign",                "TEXT"),   # free text, optional
        # v2.3 — qualification fields + reassignment badge.
        ("budget",                  "TEXT"),   # one of BUDGET_BRACKETS
        ("facing",                  "TEXT"),   # comma-separated subset of FACING_OPTIONS
        ("stage_reason",            "TEXT"),   # current Lost/Unqualified reason CODE; cleared on any other stage
        ("owner_notified",          "INTEGER"),# 0 = pending reassignment badge; 1/NULL = none pending
        # v2.11 — optional alternate contact number (Srikanth's decision
        # 5). Storage/display only: alt_phone_norm is NEVER passed to
        # find_match() or any matcher — see update_lead_contact_info()'s
        # v2.11 changelog note for why.
        ("alt_phone_raw",           "TEXT"),   # as typed, optional
        ("alt_phone_norm",          "TEXT"),   # normalized via norm_phone(), display/tel: link only
        # v2.20 — precise reengagement marker (Task 3). NULL until a
        # contact match re-enters through upsert_meta_lead()'s enrich
        # branch (see _apply_reengagement_marker()); never cleared once
        # set. Existing rows all start NULL at deploy.
        ("reengaged_at",            "TEXT"),
        # v2.27 — Meta's real Graph-API ad/campaign metadata, populated
        # by meta_leads_fetcher.py v1.4+. Deliberately separate from
        # the campaign column (owned by Campaign Routing, untouched by
        # this change). NULL on all leads created before this version.
        ("meta_campaign_id",   "TEXT"),
        ("meta_campaign_name", "TEXT"),
        ("meta_adset_id",      "TEXT"),
        ("meta_adset_name",    "TEXT"),
        ("meta_ad_id",         "TEXT"),
        ("meta_ad_name",       "TEXT"),
        # v2.32 — Meta's "platform" field (e.g. "fb"/"ig"), populated by
        # meta_leads_fetcher.py v1.6+. Same nullable/additive pattern as
        # the other meta_ columns above. NULL on all leads created before
        # this version.
        ("meta_platform",      "TEXT"),
        # v2.75 — Cross-Project Auto-Reassignment permanent ping-pong
        # guard. NULL until a lead is auto-reassigned across project
        # buckets (see _auto_cross_reassign_project() below); once set,
        # this feature can never fire again for this lead — Srikanth's
        # explicit instruction (2026-08): one bounce only, ever.
        ("cross_reassigned_at", "TEXT"),
    ]
    for col_name, col_type in drip_migrations:
        if col_name not in lead_cols:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type};")

    # ── v2.65 — idx_leads_owner moved here (fix) ──
    # lead_owner is NOT part of the original CREATE TABLE leads statement —
    # it's added above via the drip_migrations self-healing ALTER TABLE loop.
    # Creating this index immediately after CREATE TABLE (as v2.63 did) fails
    # with "no such column: lead_owner" on a genuinely fresh/empty database,
    # since it ran before the column existed. Moved here, after the loop
    # above guarantees the column exists, so it works on both fresh and
    # existing databases.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_owner ON leads(lead_owner);")

    # ── v2.68 — idx_leads_reengaged_at, same post-migration-loop placement
    # as idx_leads_owner above. reengaged_at (like lead_owner) is added via
    # the drip_migrations self-healing ALTER TABLE loop above, not the
    # original CREATE TABLE — indexing it before that loop runs would fail
    # "no such column: reengaged_at" on a fresh database, the same failure
    # mode v2.65 fixed for idx_leads_owner. NOTE: verified this index is
    # currently NOT selected by SQLite's planner for get_reengaged_count()
    # — it still SCANs leads (8k rows is cheap enough that a scan beats an
    # index seek here) even after ANALYZE. Kept anyway (harmless, may help
    # if the table grows) but do not assume it's "the fix" for that
    # function — see v2.68 changelog entry at top of file for the full,
    # honest before/after writeup.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_reengaged_at ON leads(reengaged_at);")

    # ── v2.64 — F2 Phase 1: stored project_bucket column (self-healing) ──
    # Mirrors get_project_bucket()'s live-computed value so read paths can
    # eventually filter/index on it directly instead of deriving it in
    # Python per row. Backfill for this lives further down, AFTER
    # project_aliases exists (see below) — this block only adds the column.
    if "project_bucket" not in lead_cols:
        conn.execute("ALTER TABLE leads ADD COLUMN project_bucket TEXT;")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_project_bucket ON leads(project_bucket);")

    # ── v2.3 backfill: owner_notified defaults to 1 (no pending badge)
    # for every row that existed before this column did. Only a fresh
    # reassign_lead_owner() call from this point forward sets it to 0.
    # Safe to re-run — only touches rows where it's still NULL.
    conn.execute("UPDATE leads SET owner_notified=1 WHERE owner_notified IS NULL;")

    # ── v1.9 backfill: assign crm_lead_no to any existing lead that
    # doesn't have one yet, in cls_created_at order, so the numbering
    # reflects when each lead genuinely first appeared. Safe to re-run —
    # only touches rows where crm_lead_no IS NULL.
    unnumbered = conn.execute(
        "SELECT cls_id FROM leads WHERE crm_lead_no IS NULL ORDER BY cls_created_at ASC"
    ).fetchall()
    if unnumbered:
        row = conn.execute("SELECT COALESCE(MAX(crm_lead_no), 0) m FROM leads").fetchone()
        next_no = row["m"] + 1
        for r in unnumbered:
            conn.execute("UPDATE leads SET crm_lead_no=? WHERE cls_id=?", (next_no, r["cls_id"]))
            next_no += 1

    # ── UNIQUE index on crm_lead_no (v2.82) ──
    # crm_lead_no is meant to be unique but had no DB-level guard until
    # this version — see _insert_lead_with_lead_no_retry()'s docstring
    # above for the race condition this closes. Placed here, AFTER the
    # crm_lead_no column migration and backfill immediately above —
    # same fix v2.65 (idx_leads_owner) and v2.68 (idx_leads_reengaged_at)
    # already applied to this file: crm_lead_no is added via the
    # drip_migrations self-healing ALTER TABLE loop, not the original
    # CREATE TABLE, so indexing it any earlier fails "no such column:
    # crm_lead_no" on a genuinely fresh/empty database. Self-healing
    # like every other migration here, but with one sharp edge specific
    # to UNIQUE: this CREATE will fail outright if any duplicate
    # crm_lead_no values already exist in the table. That's a feature,
    # not a bug, on an existing database — it means a duplicate slipped
    # through and needs cls_diag_duplicate_lead_no.py run again before
    # this migration can succeed. On this system it was confirmed clean
    # (all pre-existing duplicates fixed via cls_fix_duplicate_lead_no.py)
    # before this line shipped.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_crm_lead_no "
        "ON leads(crm_lead_no)"
    )

    # ── activity_log table — CRM v0.5 (Writer) universal audit trail ──
    # One row per write action taken from the CRM: notes, stage changes,
    # assignment changes, site-visit/follow-up scheduling and completion.
    # Append-only, same pattern as events_log/comms_log. Doubles as the
    # full stage-change AND assignment history — no separate table
    # needed for either (queryable via activity_type filter below).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            activity_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            cls_id        TEXT,    -- which lead
            activity_type TEXT,    -- note / stage_change / assignment_change /
                                    -- site_visit_scheduled / site_visit_conducted /
                                    -- follow_up_scheduled / follow_up_completed
            actor         TEXT,    -- user email who performed this
            prev_value    TEXT,    -- e.g. old stage, old owner
            new_value     TEXT,    -- e.g. new stage, new owner
            description   TEXT,    -- free-text note body / remarks
            created_at    TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_cls ON activity_log(cls_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at);")

    # v2.55 — capi_fire_queue: failure queue for the inline CAPI firing
    # redesign. A lead lands here when fire_single_lead_event() (see
    # cls_capi_core.py) fails synchronously from app.py's stage-change
    # route or meta_leads_fetcher.py's new-lead insert. cls_capi_firer.py
    # v3.0's default mode processes this queue on its own schedule.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS capi_fire_queue (
            queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cls_id TEXT,
            target_stage TEXT,
            attempts INTEGER DEFAULT 0,
            last_error TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            last_attempt_at TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON capi_fire_queue(status);")

    # v2.56 — webhook_test_leads: isolated landing table for Meta App
    # Review's screencast requirement (v1.5+ Meta Lead Ads webhook work,
    # done ahead of schedule solely to unblock App Review). Meta sends
    # fake test payloads to the existing /webhooks/meta-leadgen POST
    # branch during review — this table exists so those payloads have
    # somewhere to land that is NOT the real leads table. No routing,
    # no owner assignment, no CAPI firing touches this table; it is
    # write-only from log_webhook_test_lead() and read-only from
    # get_webhook_test_leads() below.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS webhook_test_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            leadgen_id TEXT,
            form_id TEXT,
            page_id TEXT,
            raw_payload TEXT NOT NULL
        );
    """)

    # ── Self-healing migration: call-recording columns (v2.33) ──
    # activity_type='call_recording' rows need 3 structured fields that
    # prev_value/new_value/description don't cleanly cover (two generic
    # slots, not three). All nullable — every pre-existing activity_type
    # leaves these NULL and is completely unaffected.
    activity_cols = [r["name"] for r in
                      conn.execute("PRAGMA table_info(activity_log)").fetchall()]
    if "recording_file_path" not in activity_cols:
        conn.execute("ALTER TABLE activity_log ADD COLUMN recording_file_path TEXT;")
    if "duration_seconds" not in activity_cols:
        conn.execute("ALTER TABLE activity_log ADD COLUMN duration_seconds INTEGER;")
    if "matched_phone" not in activity_cols:
        conn.execute("ALTER TABLE activity_log ADD COLUMN matched_phone TEXT;")

    # ── Self-healing migration: call direction (v2.49) ──
    # direction was already captured by the app and stored on
    # call_log_staging (v2.33's schema above) but dropped before it
    # reached activity_log — log_call_recording() had nowhere to put it.
    # Nullable, same convention as the v2.33 trio above: every
    # pre-existing row (and every non-call_recording activity_type)
    # leaves this NULL and is completely unaffected.
    if "direction" not in activity_cols:
        conn.execute("ALTER TABLE activity_log ADD COLUMN direction TEXT;")

    # ── site_visits / follow_ups — CRM v0.5 (Writer) scheduling ──
    # "Missed" is NEVER a stored value on either table — it's computed
    # at query time (now > scheduled_at AND status='scheduled') by
    # get_due_today() below. A status column that must be proactively
    # flipped to 'missed' by some job is a status that silently never
    # flips if that job doesn't run — Srikanth's own design call from
    # the v0.1 session, confirmed correct here.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_visits (
            visit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            cls_id        TEXT,
            scheduled_at  TEXT,
            conducted_at  TEXT,    -- NULL until closed (any outcome)
            status        TEXT,   -- 'scheduled' / 'conducted' / 'cancelled' / 'no_show'
            created_by    TEXT,
            notes         TEXT,    -- original scheduling context
            outcome_reason TEXT,   -- v1.9 — mandatory reason logged when closed/rescheduled
            created_at    TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_cls ON site_visits(cls_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_sched ON site_visits(scheduled_at);")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS follow_ups (
            followup_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            cls_id        TEXT,
            scheduled_at  TEXT,
            completed_at  TEXT,    -- NULL until closed (any outcome)
            status        TEXT,   -- 'scheduled' / 'completed' / 'cancelled'
            created_by    TEXT,
            notes         TEXT,    -- original scheduling context
            outcome_reason TEXT,   -- v1.9 — mandatory reason logged when closed/postponed
            created_at    TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_followups_cls ON follow_ups(cls_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_followups_sched ON follow_ups(scheduled_at);")

    # ── v1.9 self-healing migration: outcome_reason on both tables,
    # for any cls.db created before this version existed. ──
    visits_cols = [r["name"] for r in conn.execute("PRAGMA table_info(site_visits)").fetchall()]
    if "outcome_reason" not in visits_cols:
        conn.execute("ALTER TABLE site_visits ADD COLUMN outcome_reason TEXT;")
    if "project" not in visits_cols:
        # v2.8 — which project bucket a WALK-IN "Site Visit Conducted"
        # (see log_walkin_site_visit()) was for. NULL for every visit
        # scheduled the normal way (schedule_site_visit()) — those are
        # already tied to the lead's own project via leads.project, this
        # column only exists for the walk-in case where the admin/
        # salesperson picks it explicitly on the spot.
        conn.execute("ALTER TABLE site_visits ADD COLUMN project TEXT;")
    if "reminder_sent_at" not in visits_cols:
        # v2.69 — Dashboard fix Part 2: stored replacement for the old
        # correlated LIKE-against-activity_log lookup in
        # get_site_visits_for_tomorrow(). See that function and
        # log_reminder_sent()/update_site_visit() below, and the v2.69
        # changelog entry at top of file, for the full read/write-path
        # rationale (including the reschedule-bug fix this closes).
        conn.execute("ALTER TABLE site_visits ADD COLUMN reminder_sent_at TEXT;")
    followups_cols = [r["name"] for r in conn.execute("PRAGMA table_info(follow_ups)").fetchall()]
    if "outcome_reason" not in followups_cols:
        conn.execute("ALTER TABLE follow_ups ADD COLUMN outcome_reason TEXT;")

    # ── v2.69 — reminder_sent_at backfill (self-healing, gap-only, safe
    # to leave running on every init_db() call indefinitely — same
    # pattern as F2 Phase 1's project_bucket backfill). Only ever fills
    # rows where reminder_sent_at IS NULL, computing exactly what the OLD
    # LIKE-based lookup would have returned, so historical accuracy is
    # preserved for visits already correctly marked sent under the old
    # system. A visit the old logic would also have found nothing for is
    # set to NULL by this (a no-op), which is the correct "not sent"
    # state, not a change in meaning. Depends only on activity_log, which
    # is created well above this point in init_db(), so this is safe to
    # run here on both a fresh DB and an existing one.
    conn.execute("""
        UPDATE site_visits
        SET reminder_sent_at = (
            SELECT MAX(a.created_at) FROM activity_log a
            WHERE a.activity_type = 'whatsapp_reminder_sent'
              AND a.description LIKE 'visit_id:' || site_visits.visit_id || '%'
        )
        WHERE reminder_sent_at IS NULL
    """)

    # ── users table — CRM v0.1 (Viewer) login accounts ──
    # One row per person who logs into the CRM. Kept in cls.db itself —
    # same "one source of truth" principle as every other CLS table.
    # role is a plain string (SQLite has no ENUM) — the app layer treats
    # anything other than 'admin' as 'salesperson'.
    # active is a soft-delete flag: disabling someone sets active=0
    # rather than deleting the row (Srikanth's "paused != deleted" rule),
    # which also keeps their name intact on activity_log/assignments
    # rows once those tables exist in v0.5.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name        TEXT,
            email            TEXT UNIQUE,     -- login identifier
            password_hash    TEXT,            -- "salt_hex$hash_hex" — see _hash_password()
            role             TEXT,            -- 'admin' or 'salesperson'
            active           INTEGER DEFAULT 1,
            created_at       TEXT,
            last_login_at    TEXT,
            owner_match_name TEXT             -- v1.7: links this login to leads.lead_owner
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")

    # ── Self-healing migration: owner_match_name (v1.7) ──
    # Deliberately NOT the same string as full_name — full_name is what
    # someone typed when creating their own login; owner_match_name is
    # a separate, admin-set value that must match leads.lead_owner
    # (Sell.do's "Attended By" text) exactly. Existing users (created
    # before v1.7) get NULL here, which is treated as "not yet linked" —
    # see get_leads_page()'s owner_filter handling.
    user_cols = [r["name"] for r in
                 conn.execute("PRAGMA table_info(users)").fetchall()]
    if "owner_match_name" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN owner_match_name TEXT;")

    # ── Self-healing migration: assigned_project (v2.38, APX Attendance) ──
    # Matches attendance_project_locations.project_bucket (loose string
    # match, same convention as owner_match_name above). Admin-set from a
    # Settings > Attendance screen (later build-order step) — this
    # migration only adds the column, existing users get NULL, treated as
    # "not yet assigned" by the geofence check.
    if "assigned_project" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN assigned_project TEXT;")

    # ── Self-healing migration: view_mode (v2.50, manager view-mode toggle) ──
    # A manager's own default-scope preference for their leads/dashboard
    # views — 'manager' (company-wide, today's unchanged behavior) or
    # 'individual' (own-leads-only, like a salesperson). DEFAULT 'manager'
    # so every existing row (including admin/salesperson rows, which never
    # read this column — see get_view_mode()) needs no backfill. Meaningless
    # outside role=='manager'; get_view_mode()/effective_company_wide()
    # below are the only code that should ever interpret this column.
    if "view_mode" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN view_mode TEXT DEFAULT 'manager';")

    # ── v2.7 — WhatsApp message templates ──
    # One template per project (project is the title AND the unique key,
    # mirroring how Sell.do titles each template by project name).
    # Admin-managed via the Settings screen; the admin gate lives in the
    # route, not here. message_body may contain {name} and {project}
    # placeholders, expanded at send time by render_whatsapp_template().
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_templates (
            template_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            project       TEXT UNIQUE,   -- title + lookup key
            message_body  TEXT,
            created_at    TEXT,
            updated_at    TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_watemplates_project ON whatsapp_templates(project);")

    # ── v2.14 — WhatsApp SITE-VISIT REMINDER templates ──
    # Separate table from whatsapp_templates (v2.7, above) — deliberately
    # NOT reused, per Srikanth's call: welcome-message templates and
    # tomorrow's-visit reminder templates are different content edited
    # on different screens, even though the shape is identical. One
    # template per project (project is the title AND unique key, same
    # pattern as whatsapp_templates). Expanded at send time by
    # render_whatsapp_reminder_template() (adds a {time} placeholder on
    # top of {name}/{project}).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_reminder_templates (
            template_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            project      TEXT UNIQUE NOT NULL,
            message_body TEXT NOT NULL,
            updated_by   TEXT,
            updated_at   TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wareminder_project ON whatsapp_reminder_templates(project);")

    # ── v2.15 — admin "View as" (impersonation) audit trail ──
    # Append-only, same spirit as activity_log/events_log: one row per
    # impersonation session start/exit. Kept separate from activity_log
    # because this isn't a lead-scoped action (cls_id is meaningless
    # here) — it's an account-level session event.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS impersonation_log (
            log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_email  TEXT NOT NULL,
            target_email TEXT NOT NULL,
            event        TEXT NOT NULL,
            created_at   TEXT NOT NULL
        );
    """)

    # ── v2.21 — admin "User Activity Log" (Settings > User Activity) ──
    # Session-level audit trail, additive alongside (not replacing)
    # activity_log: activity_log is lead-scoped and existed long before
    # this; these two tables record EVERY logged-in request, lead-scoped
    # or not, grouped by login session. See the "USER ACTIVITY LOG"
    # section further down for the functions that read/write these.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER,
            actor          TEXT,
            login_at       TEXT,
            logout_at      TEXT,
            logout_reason  TEXT,
            ip_address     TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_login ON user_sessions(login_at);")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_action_log (
            log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER,
            actor        TEXT,
            method       TEXT,
            label        TEXT,
            cls_id       TEXT,
            created_at   TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_useraction_session ON user_action_log(session_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_useraction_created ON user_action_log(created_at);")

    # ── v2.24 — Project Master List (project_aliases table) ──
    # Superseded the PROJECT_BUCKETS module dict (now PAUSED above).
    # table_existed_before is checked BEFORE CREATE TABLE, not via an
    # emptiness check AFTER it — deliberately: an admin deleting every
    # alias later via delete_project_alias() (a legitimate, supported
    # action) must never get silently reseeded from the old hardcoded
    # dict on the next app/job restart. "Just created" means literally
    # created by this call, not "happens to be empty right now."
    table_existed_before = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='project_aliases'"
    ).fetchone() is not None

    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_aliases (
            alias           TEXT PRIMARY KEY COLLATE NOCASE,
            project_bucket  TEXT NOT NULL,
            created_at      TEXT NOT NULL
        );
    """)

    if not table_existed_before:
        seed_ts = _now()
        conn.executemany(
            "INSERT OR IGNORE INTO project_aliases (alias, project_bucket, created_at) VALUES (?, ?, ?)",
            [(alias, bucket, seed_ts) for alias, bucket in _PROJECT_ALIASES_SEED.items()]
        )

    # ── v2.64 — F2 Phase 1 backfill: fill project_bucket gaps only ──
    # Must run AFTER project_aliases exists/is seeded above — it needs
    # that table's alias map. Only ever fills NULL project_bucket rows,
    # never overwrites an already-computed value, so this is safe to
    # leave running on every init_db() call indefinitely (no separate
    # one-time migration script needed).
    #
    # Deliberately reimplements get_project_bucket()'s exact algorithm
    # (first-project-in-comma-list, alias lookup, "(unknown)" for
    # blank/None) INLINE against this same open `conn`/transaction,
    # rather than calling get_project_bucket() itself — that function
    # opens its own connection via _connect(), which on a first-ever
    # run would not yet see this transaction's uncommitted project_
    # aliases seed rows (or even the project_bucket column/table DDL
    # above) until this function's conn.commit() at the very end.
    # Keep this logic identical to get_project_bucket() if that
    # function's algorithm ever changes.
    _alias_rows = conn.execute("SELECT alias, project_bucket FROM project_aliases").fetchall()
    _alias_map = {r["alias"]: r["project_bucket"] for r in _alias_rows}

    def _backfill_bucket_for(raw_project):
        if not raw_project:
            return "(unknown)"
        first = raw_project.split(",")[0].strip()
        return _alias_map.get(first, first)

    _needs_backfill = conn.execute(
        "SELECT cls_id, project FROM leads WHERE project_bucket IS NULL"
    ).fetchall()
    if _needs_backfill:
        conn.executemany(
            "UPDATE leads SET project_bucket=? WHERE cls_id=?",
            [(_backfill_bucket_for(r["project"]), r["cls_id"]) for r in _needs_backfill]
        )

    # ── v2.25 — Campaign Routing (Single + Round Robin) + app_settings ──
    # Superseded DEFAULT_OWNER_BY_PROJECT/FALLBACK_DEFAULT_OWNER (now
    # PAUSED above). app_settings is a small generic key/value store —
    # reused again by Task 4 (Lead Scoring config) below, not duplicated.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_routing_rules (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name   TEXT NOT NULL COLLATE NOCASE UNIQUE,
            rule_type       TEXT NOT NULL CHECK (rule_type IN ('single','round_robin')),
            owners          TEXT NOT NULL,
            next_index      INTEGER NOT NULL DEFAULT 0,
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key     TEXT PRIMARY KEY,
            setting_value   TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
    """)

    # Self-healing seed: only inserts if the row doesn't already exist,
    # so re-running init_db() never clobbers a value Srikanth already
    # changed via /settings/campaign-routing.
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
        ("default_fallback_owner", "Mounika Peddi", _now())
    )

    # leads.campaign self-healing column already existed (added under
    # the drip_migrations block above, v2.13) — no new ALTER TABLE
    # needed here for Campaign Routing to write to it.

    # ── v2.26 — Lead Scoring config (Settings > Lead Scoring GUI) ──
    # Reuses the app_settings table created just above (Task 3) rather
    # than a second key/value table. Self-healing seed, same INSERT OR
    # IGNORE pattern as default_fallback_owner — never clobbers a config
    # Srikanth already tuned via the GUI.
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
        ("lead_score_config", json.dumps(_LEAD_SCORE_CONFIG_SEED), _now())
    )

    # ── v2.28 — bulk_jobs: audit history for admin bulk actions ──
    # Written generically (job_type column, validated against
    # BULK_JOB_TYPES) so a future bulk action can reuse this same table
    # instead of getting its own. filters_summary is a short human-
    # readable string built by the CALLER (app.py) — deliberately not a
    # JSON blob, so the history page can just print it, no second
    # renderer needed.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bulk_jobs (
            job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type        TEXT,
            actor           TEXT,
            filters_summary TEXT,
            to_owner        TEXT,
            lead_count      INTEGER,
            created_at      TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bulk_jobs_created ON bulk_jobs(created_at);")

    # ── v2.53 — bulk_job_leads: per-job cls_id snapshot (Phase 5) ──
    # Records the EXACT cls_ids a bulk job touched, at the moment it ran,
    # independent of what happens to those leads afterward (reassigned
    # again, stage-changed, even deleted) — so "Past Bulk Jobs" can offer
    # a reliable "download affected leads" export per row regardless of
    # current state. No FK enforcement on cls_id (SQLite FKs are off by
    # default project-wide and a deleted lead shouldn't break the
    # snapshot/export), only the job_id -> bulk_jobs FK.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bulk_job_leads (
            job_id  INTEGER NOT NULL REFERENCES bulk_jobs(job_id),
            cls_id  TEXT NOT NULL,
            PRIMARY KEY (job_id, cls_id)
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bulk_job_leads_job ON bulk_job_leads(job_id);")

    # ── Phase B Telephony schema (v2.33) ──
    # Server-side call-recording matching: the Android app reports call-log
    # metadata (never files) to /api/telephony/report-calls; only numbers
    # that match an existing lead get a recording fetched and uploaded to
    # /api/telephony/upload-recording. See TELEPHONY_RECORDING_POLICY.md.

    # One row per user — per-salesperson OEM recording-folder path,
    # configured by an admin from Settings > Telephony. user_id itself is
    # the primary key (not a separate autoincrement id) so "one row per
    # user" is structural and a save is a plain INSERT OR REPLACE.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_recording_paths (
            user_id               INTEGER PRIMARY KEY REFERENCES users(user_id),
            recording_folder_path TEXT,
            updated_at            TEXT
        );
    """)

    # Per-user bearer token — entirely separate from the session-cookie
    # login used by every other route. Originally issued for the 2
    # Telephony API endpoints only; as of v2.42 the SAME token also
    # gates the 4 /api/attendance/* endpoints (Build Order Step 4) —
    # deliberately one mobile-app token per user, not a second scheme
    # per feature. Only the SHA-256 hash is ever stored; the raw token
    # is shown once at generation time (Settings > Telephony) and never
    # logged. Regenerating deactivates the old row (active=0) rather
    # than deleting it, matching the codebase's "never discard" posture.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_api_tokens (
            token_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER REFERENCES users(user_id),
            token_hash    TEXT,
            created_at    TEXT,
            last_used_at  TEXT,
            active        INTEGER DEFAULT 1
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_api_tokens_hash ON user_api_tokens(token_hash);")

    # Raw call-log entries reported by the app, matched or not — proves
    # the "no scan without a lead match" policy is actually being
    # followed. Unmatched numbers are logged here with match_status=
    # 'no_lead_match' and are NEVER persisted anywhere else in the system.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS call_log_staging (
            staging_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER REFERENCES users(user_id),
            raw_phone        TEXT,
            phone_norm       TEXT,
            call_timestamp   TEXT,
            duration_seconds INTEGER,
            direction        TEXT,
            matched_cls_id   TEXT,
            match_status     TEXT,
            created_at       TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_call_log_staging_created ON call_log_staging(created_at);")

    # ── v2.68 — idx_call_log_matched_direction_ts. matched_cls_id/direction/
    # call_timestamp are all part of the CREATE TABLE above (not a later
    # ALTER TABLE addition), so this is safe immediately after table
    # creation, unlike the leads-table indexes elsewhere in this file that
    # had to wait for a self-healing migration loop. Column order matches
    # get_missed_calls_count()'s correlated NOT EXISTS subquery predicate
    # (o.matched_cls_id = m.matched_cls_id AND o.direction = 'OUTGOING' AND
    # o.call_timestamp > m.call_timestamp) exactly, and also serves that
    # function's outer JOIN/WHERE. Fixes a SCAN + per-row full-table-rescan
    # against this table's 56k rows (16,415ms -> ~19-22ms steady-state
    # measured on live CLS1.db) — see v2.68 changelog entry at top of file
    # for the full diagnosis/fix writeup.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_call_log_matched_direction_ts ON call_log_staging(matched_cls_id, direction, call_timestamp);")

    # ── APX Attendance v0.9 schema (v2.38) ──
    # SIBLING module to the lead-management engine — own tables, own API
    # prefix (later step). Nothing in this block touches leads,
    # activity_log, assignments, or any Job A-D logic. See the v2.38
    # changelog entry at the top of this file for the full rationale.

    # One row per project bucket. Matches project_aliases.project_bucket
    # text, same loose string-match convention as owner_match_name/
    # lead_owner elsewhere in this file — no FK enforcement.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_project_locations (
            project_bucket  TEXT PRIMARY KEY,
            latitude        REAL,
            longitude       REAL,
            radius_meters   INTEGER DEFAULT 1500,
            updated_at      TEXT
        );
    """)

    # One row per user per day. UNIQUE(user_id, attendance_date) means a
    # same-day re-punch is handled as an UPDATE by the caller, not a
    # second row — mirrors how leads.UNIQUE-style upserts already work
    # elsewhere in this file.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id                INTEGER REFERENCES users(user_id),
            attendance_date        TEXT,
            status                 TEXT,
            login_ts               TEXT,
            login_lat              REAL,
            login_lng              REAL,
            login_geofence_breach  INTEGER DEFAULT 0,
            login_photo_path       TEXT,
            logout_ts              TEXT,
            logout_lat             REAL,
            logout_lng             REAL,
            logout_geofence_breach INTEGER DEFAULT 0,
            logout_photo_path      TEXT,
            late_minutes           INTEGER DEFAULT 0,
            created_at             TEXT,
            updated_at             TEXT,
            UNIQUE(user_id, attendance_date)
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance(user_id, attendance_date);")

    # ── Self-healing migration: last_modified_by (v2.40, APX Attendance audit) ──
    # Same PRAGMA table_info-check pattern as users.assigned_project (v2.38)
    # above. Written by set_self_service_attendance_status() (Weekoff/Leave)
    # and resolve_attendance_correction() (an approved correction being
    # applied) — the two functions that change an attendance row's status/
    # times outside the punch-in/out API (Step 4, not built yet). Existing
    # rows get NULL, treated as "no record of who last touched this."
    attendance_cols = [r["name"] for r in
                       conn.execute("PRAGMA table_info(attendance)").fetchall()]
    if "last_modified_by" not in attendance_cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN last_modified_by TEXT;")

    # Employee-initiated change requests against an existing attendance
    # row. Approving one (later build-order step, Settings > Attendance >
    # Corrections) applies new_value to the attendance row and logs it
    # here — this migration only creates the queue table.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_corrections (
            correction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_id   INTEGER REFERENCES attendance(attendance_id),
            requested_by    TEXT,
            request_note    TEXT,
            field_changed   TEXT,
            old_value       TEXT,
            new_value       TEXT,
            status          TEXT DEFAULT 'pending',
            actor           TEXT,
            resolved_at     TEXT,
            created_at      TEXT
        );
    """)

    # ── Weekoff/Leave request log (v2.45, Chunk B) ──
    # A row's existence means approved — no status/approval column, since
    # this chunk auto-approves on submit (no admin step yet). weekoff_log
    # is one row per single day; leave_requests is one row per CONTIGUOUS
    # date range (start_date/end_date), not one row per day — see
    # submit_leave()'s docstring for how a multi-select of individual
    # dates gets grouped into ranges before insert. Both are populated
    # ONLY via submit_weekoff()/submit_leave() below, which also sync
    # attendance.status so the existing Dashboard/export/today-badge
    # keep reading a single consistent source.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weekoff_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER REFERENCES users(user_id),
            date          TEXT,
            submitted_at  TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_weekoff_log_user_date ON weekoff_log(user_id, date);")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER REFERENCES users(user_id),
            start_date    TEXT,
            end_date      TEXT,
            submitted_at  TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leave_requests_user_range ON leave_requests(user_id, start_date, end_date);")

    # Admin-managed holiday calendar.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_holidays (
            holiday_date  TEXT PRIMARY KEY,
            label         TEXT,
            created_at    TEXT
        );
    """)

    # Hourly WorkManager location pings while punched in. Housekeeping
    # (purge/archive rows older than 90 days) is a separate small script,
    # same category as cls_parallel_diff.py — not a Job A-D addition, and
    # not built in this step.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_location_pings (
            ping_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER,
            attendance_id  INTEGER,
            ts             TEXT,
            lat            REAL,
            lng            REAL,
            created_at     TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pings_created ON attendance_location_pings(created_at);")

    # One row per user — FCM push token, same INSERT OR REPLACE-keyed-on-
    # user_id idiom as user_recording_paths (v2.33) above. Populated by a
    # later build-order step (app start + Firebase token-refresh callback).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_fcm_tokens (
            user_id     INTEGER PRIMARY KEY REFERENCES users(user_id),
            fcm_token   TEXT,
            updated_at  TEXT
        );
    """)

    # Notifications v1.0 (v2.72) — one row per delivered notification,
    # in-app bell + FCM. event_id UNIQUE is what makes insert_notification()
    # idempotent (INSERT OR IGNORE keyed on it) — same md5-dedup idiom as
    # Job C's CAPI event_ids, just keyed on (cls_id, event_type, today's
    # date) instead of (identifier, stage). read_at/fcm_sent_at both
    # NULL-until-set, same "NULL means pending" convention as
    # site_visits.conducted_at / owner_notified elsewhere in this file.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER,           -- recipient, references users(user_id)
            cls_id           TEXT,               -- the lead this is about
            event_type       TEXT,               -- key into NOTIFICATION_EVENTS
            message          TEXT,               -- rendered at insert time
            event_id         TEXT UNIQUE,        -- md5(cls_id+event_type+today) — idempotency
            read_at          TEXT,               -- NULL = unread
            fcm_sent_at      TEXT,               -- NULL = not pushed yet
            created_at       TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, read_at);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_event ON notifications(event_id);")

    # Self-healing seed, same INSERT OR IGNORE pattern as
    # default_fallback_owner (v2.25) — never clobbers a value Srikanth
    # already changed via the (later) Settings > Attendance screen.
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
        ("attendance_late_after_time", "10:00", _now())
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
        ("attendance_default_radius_m", "1500", _now())
    )

    # ── v2.75 — Cross-Project Auto-Reassignment ──
    # Mirrors campaign_routing_rules exactly in style (same rule_type
    # CHECK constraint, same owners-as-JSON-array + next_index round-
    # robin cursor). One row per (source_bucket, target_bucket) pair —
    # UNIQUE enforces at most one active route out of a given source
    # bucket into a given target bucket. See _get_cross_reassign_rule()/
    # _pick_cross_reassign_owner()/_auto_cross_reassign_project() below
    # for how this is read, and update_lead_stage()'s hook for where
    # it's triggered (Lost/Unqualified transitions only).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cross_project_reassign_rules (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_bucket   TEXT NOT NULL COLLATE NOCASE,
            target_bucket   TEXT NOT NULL COLLATE NOCASE,
            rule_type       TEXT NOT NULL CHECK (rule_type IN ('single','round_robin')),
            owners          TEXT NOT NULL,
            next_index      INTEGER NOT NULL DEFAULT 0,
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            UNIQUE(source_bucket, target_bucket)
        );
    """)

    # Self-healing seed, same INSERT OR IGNORE pattern as
    # default_fallback_owner (v2.25) — never clobbers a row Srikanth
    # already edited later via a future GUI. Owner names verified
    # against the live users/leads tables before this was written.
    _cross_reassign_seed_ts = _now()
    conn.execute(
        "INSERT OR IGNORE INTO cross_project_reassign_rules "
        "(source_bucket, target_bucket, rule_type, owners, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Naishka Homes", "Grace Classic", "single",
         json.dumps(["Mounika Peddi"]), _cross_reassign_seed_ts, _cross_reassign_seed_ts)
    )
    conn.execute(
        "INSERT OR IGNORE INTO cross_project_reassign_rules "
        "(source_bucket, target_bucket, rule_type, owners, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Grace Classic", "Naishka Homes", "round_robin",
         json.dumps(["Elohar Peddi", "Devender Goud"]), _cross_reassign_seed_ts, _cross_reassign_seed_ts)
    )

    # Registers the "Naishka Homes" bucket name as its own alias.
    # Currently only the sub-projects (Naishka, Naishka Prism, etc.) map
    # to this bucket — the bucket name itself isn't registered.
    # Cosmetic/completeness fix so it displays correctly on
    # /settings/projects. get_project_bucket() already falls through
    # safely without this, so it was low-risk either way. Unconditional
    # INSERT OR IGNORE (not gated on table_existed_before above) since
    # project_aliases already exists on the live database.
    conn.execute(
        "INSERT OR IGNORE INTO project_aliases (alias, project_bucket, created_at) VALUES (?, ?, ?)",
        ("Naishka Homes", "Naishka Homes", _cross_reassign_seed_ts)
    )

    # ── v2.87 — Payroll v1.0 ──
    # Flat monthly salary per user, no incentive/commission component.
    # salary_slabs is the input (admin-edited); salary_snapshots is the
    # append/replace-per-month output of compute_salary_for_month(),
    # storing its own leave-balance carry-forward state per row so
    # recalculating one month is idempotent (reads the PRIOR month's row
    # for its opening balance, never a separate mutable ledger). See
    # compute_salary_for_month()'s docstring for the full formula.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS salary_slabs (
            user_id         INTEGER PRIMARY KEY REFERENCES users(user_id),
            monthly_salary  REAL NOT NULL,
            updated_at      TEXT,
            updated_by      TEXT
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS salary_snapshots (
            snapshot_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id               INTEGER NOT NULL REFERENCES users(user_id),
            year                  INTEGER NOT NULL,
            month                 INTEGER NOT NULL,
            base_salary           REAL NOT NULL,
            calendar_days         INTEGER NOT NULL,
            present_days          INTEGER NOT NULL DEFAULT 0,
            absent_days           INTEGER NOT NULL DEFAULT 0,
            leave_days_taken      INTEGER NOT NULL DEFAULT 0,
            weekoff_days          INTEGER NOT NULL DEFAULT 0,
            leave_balance_before  INTEGER NOT NULL DEFAULT 0,
            leave_balance_accrued INTEGER NOT NULL DEFAULT 1,
            leave_balance_available INTEGER NOT NULL DEFAULT 0,
            paid_leave_days_used  INTEGER NOT NULL DEFAULT 0,
            unpaid_leave_days     INTEGER NOT NULL DEFAULT 0,
            leave_balance_after   INTEGER NOT NULL DEFAULT 0,
            deducted_days         REAL NOT NULL DEFAULT 0,
            net_salary            REAL NOT NULL,
            calculated_at         TEXT NOT NULL,
            calculated_by         TEXT,
            UNIQUE(user_id, year, month)
        );
    """)

    # ── Self-healing migration: holiday_days / untracked_absent_days
    # (v2.90, Fix 2 — holiday-aware absent detection) ──
    # Same PRAGMA table_info-check pattern as attendance.last_modified_by
    # (v2.40) above. Existing salary_snapshots rows get 0 for both (their
    # DEFAULT), same "no data" posture as every other DEFAULT 0 column on
    # this table already has for a pre-migration row.
    salary_snapshots_cols = [r["name"] for r in
                             conn.execute("PRAGMA table_info(salary_snapshots)").fetchall()]
    if "holiday_days" not in salary_snapshots_cols:
        conn.execute("ALTER TABLE salary_snapshots ADD COLUMN holiday_days INTEGER NOT NULL DEFAULT 0;")
    if "untracked_absent_days" not in salary_snapshots_cols:
        conn.execute("ALTER TABLE salary_snapshots ADD COLUMN untracked_absent_days INTEGER NOT NULL DEFAULT 0;")

    # Self-healing seed, same INSERT OR IGNORE pattern as the cross-
    # reassign seed above — never clobbers a slab Srikanth already
    # edited via /settings/payroll/slabs. Names verified against the
    # live users table (same spellings the v2.75 cross-reassign seed
    # verified: "Elohar Peddi", "Devender Goud", "Mounika Peddi") before
    # this was written. Resolved by full_name at seed time; a name that
    # doesn't resolve to an active user is skipped silently rather than
    # raising, since init_db() must never fail because a seed name is
    # momentarily stale.
    _payroll_seed_ts = _now()
    _payroll_seed_slabs = {
        "Elohar Peddi":   25000,
        "Mounika Peddi":  16000,
        "Devender Goud":  18000,
    }
    for _seed_name, _seed_salary in _payroll_seed_slabs.items():
        _seed_user = conn.execute(
            "SELECT user_id FROM users WHERE full_name=? AND active=1", (_seed_name,)
        ).fetchone()
        if _seed_user:
            conn.execute(
                "INSERT OR IGNORE INTO salary_slabs (user_id, monthly_salary, updated_at, updated_by) "
                "VALUES (?, ?, ?, ?)",
                (_seed_user["user_id"], _seed_salary, _payroll_seed_ts, "system:init_db seed")
            )

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
# AUTH / USERS  —  CRM v0.1 (Viewer) login accounts
# ─────────────────────────────────────────────────────────────
# Password hashing uses ONLY the Python standard library (hashlib +
# secrets) — deliberately not Werkzeug/Flask — so this file keeps its
# original zero-extra-dependency footprint. Jobs A-D never call these
# and are unaffected either way.

# ─────────────────────────────────────────────────────────────
# ROLES  (v2.9 — config-not-code; the one place role policy lives)
# ─────────────────────────────────────────────────────────────
# role is stored as free-text TEXT in the users table (no CHECK
# constraint — SQLite has no ENUM), so adding a role needs NO schema
# migration. Enumerate the valid ones here so create_admin.py can
# validate against a single source of truth.
#
#   Hierarchy:  admin (top)  >  manager (middle)  >  salesperson (bottom)
CRM_ROLES = ("admin", "manager", "salesperson")

# The oversight tier — roles that SEE every lead and the company-wide
# dashboards. Everyone else is scoped to their own owner_match_name.
# This is the ONLY list that decides "sees all leads"; add a future
# role here (e.g. "team_lead") and every visibility site follows.
OVERSIGHT_ROLES = ("admin", "manager")


def can_view_all_leads(role):
    """
    (v2.9) True for oversight roles (admin, manager) — they see every
    lead and the company-wide dashboards. False for salespeople AND,
    deliberately, for any unrecognised/misspelled role: an unknown role
    falls through to the most restricted view (own leads only), never
    the widest one. Fails CLOSED, not open.

    IMPORTANT — this used to be a VISIBILITY-only capability, deliberately
    separate from write (v2.9/v0.9.5: a manager could view any lead but
    write only to their own). As of v2.19 that split is REVERSED for
    managers — see can_write_any_lead() below, which now also covers
    (admin, manager). A future reader must not assume read and write are
    still split for this role; they happen to be checked by two separate
    functions (this one, and can_write_any_lead()) but currently cover the
    same role set. app.py's _is_lead_owner_or_admin() is the write gate;
    it ORs the existing owner-or-admin check with can_write_any_lead().
    """
    return role in OVERSIGHT_ROLES


# v2.19 — WRITE side, reversing v2.9/v0.9.5's deliberate split. Srikanth's
# explicit call (2026-07): a manager must be able to WRITE to any lead
# (stage change, notes, assign, site visit/follow-up, property/contact
# edits, call tap) exactly as if they owned it, not just their own
# pipeline. Previously only admin could write anywhere; a manager could
# view every lead (can_view_all_leads above) but write only to their own.
# A FUTURE READER MUST NOT ASSUME THE OLD READ/WRITE SPLIT STILL HOLDS —
# read (can_view_all_leads) and write (can_write_any_lead) now cover the
# same role set (admin, manager), they just remain two separate functions/
# checks by design (app.py's _is_lead_owner_or_admin() calls this one
# alongside its existing owner-or-admin check) so the two concerns stay
# independently adjustable if they ever need to diverge again. Deliberately
# NOT widened past lead-level write routes: Settings, the Team page, lead
# deletion, and source-editing stay admin_required / role=="admin" only —
# this constant does not touch those.
WRITE_ANYWHERE_ROLES = ("admin", "manager")


def can_write_any_lead(role):
    """
    (v2.19) True for roles allowed to write to ANY lead, not just their
    own — mirrors can_view_all_leads()'s fail-closed posture: an unknown/
    unrecognised role returns False, never the widest permission. Used by
    app.py's _is_lead_owner_or_admin() as an additional OR alongside the
    existing "is this lead's own owner, or admin" check — it does not
    replace that check, it widens who satisfies it.
    """
    return role in WRITE_ANYWHERE_ROLES


# ─────────────────────────────────────────────────────────────
# VIEW MODE  (v2.50 — manager view-mode toggle, config-not-code)
# ─────────────────────────────────────────────────────────────
# A player-coach manager's own preference for what their DEFAULT leads/
# dashboard SCOPE shows — 'manager' (company-wide, today's unchanged
# behavior) or 'individual' (own-leads-only, like a salesperson). This
# is deliberately NOT a role and does not touch can_view_all_leads()/
# can_write_any_lead()/WRITE_ANYWHERE_ROLES above: a manager who flips
# to 'individual' still has full oversight WRITE access to every lead
# and full report access — only their own default VIEW narrows.

def get_view_mode(user):
    """
    (v2.50) Returns 'individual' only when this user's role is exactly
    'manager' AND their stored view_mode is exactly 'individual'.
    Returns 'manager' for every other case — wrong/unrecognised role,
    unset/NULL view_mode, or any unexpected value in that column. Fails
    closed to 'manager' (the wider, company-wide default), mirroring
    can_view_all_leads()'s own fail-closed posture: an unexpected input
    never produces the narrower/individual result for a role it wasn't
    explicitly set for. Takes the whole user dict (not just a column)
    so both checks read off the same row the caller already fetched.
    """
    if user.get("role") != "manager":
        return "manager"
    if user.get("view_mode") == "individual":
        return "individual"
    return "manager"


def effective_company_wide(user):
    """
    (v2.50) The function app.py's view-SCOPING call sites should call
    instead of can_view_all_leads(user["role"]) directly — wherever that
    call was deciding "does this login see everyone's leads by default,
    or just their own", not a WRITE gate (can_write_any_lead) or a
    report-ACCESS gate (_check_report_access in app.py), both of which
    stay on their existing role-only checks, unaffected by this.
    True for admins always (view_mode never applies to them). True for
    managers UNLESS they've toggled to 'individual'. False for
    salespeople, exactly as can_view_all_leads() already returned.
    """
    return can_view_all_leads(user["role"]) and get_view_mode(user) != "individual"


def set_view_mode(user_id, mode):
    """
    (v2.50) Flip a manager's own view_mode. `mode` must be exactly
    'manager' or 'individual' — anything else returns False untouched.
    Also no-ops (returns False) if the target user's role isn't
    'manager': deliberately not settable for admin or salesperson rows,
    even via direct call, so this column can never carry a meaningful
    value for a role get_view_mode() doesn't apply it to.

    Returns True iff a manager row was found and updated.
    """
    if mode not in ("manager", "individual"):
        return False
    conn = _connect()
    try:
        row = conn.execute("SELECT role FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row or row["role"] != "manager":
            return False
        conn.execute("UPDATE users SET view_mode=? WHERE user_id=?", (mode, user_id))
        conn.commit()
        return True
    finally:
        conn.close()


PBKDF2_ITERATIONS = 260_000  # OWASP-recommended floor for PBKDF2-SHA256 (2024+)


def _hash_password(password):
    """
    Return a "salt_hex$hash_hex" string for storage in users.password_hash.
    A fresh random salt is generated per password, so two users with the
    same password never produce the same stored value.
    """
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()
    return f"{salt}${digest}"


def _verify_password(password, stored):
    """
    Check a plaintext password against a "salt_hex$hash_hex" stored value.
    Returns False (never raises) for malformed/missing stored values, so
    a corrupted row fails closed rather than crashing the login route.
    """
    try:
        salt, digest = stored.split("$", 1)
    except (AttributeError, ValueError):
        return False
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()
    return secrets.compare_digest(check, digest)


def create_user(full_name, email, password, role="salesperson", owner_match_name=None):
    """
    Create a new CRM login. Called from create_admin.py (a one-off
    bootstrap script) for each teammate onboarded before v0.5 gets an
    in-app "add teammate" screen.

    owner_match_name (v1.7): for salesperson logins, this MUST match
    leads.lead_owner (Sell.do's "Attended By" text) exactly for that
    person to see their own leads. Leave it None for admin accounts —
    admins always see everything, unfiltered.

    Raises ValueError if the email is invalid or already registered —
    callers should catch this and show a friendly message.

    Returns the new user_id.
    """
    email_norm = norm_email(email)
    if not email_norm:
        raise ValueError(f"'{email}' is not a valid email address")

    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE email=?", (email_norm,)
        ).fetchone()
        if existing:
            raise ValueError(f"A user with email '{email_norm}' already exists")

        cur = conn.execute("""
            INSERT INTO users (full_name, email, password_hash, role, active, created_at, owner_match_name)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        """, (full_name, email_norm, _hash_password(password), role, _now(), owner_match_name or None))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_user_owner_match(email, owner_match_name):
    """
    Set/correct the owner_match_name for an EXISTING login — used when
    someone was created before this was set, or the Sell.do "Attended
    By" spelling didn't match what was originally entered. Does not
    touch password, role, or anything else.

    Returns True if a matching user was found and updated, False if
    no user exists with that email.
    """
    email_norm = norm_email(email)
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE users SET owner_match_name=? WHERE email=?",
            (owner_match_name or None, email_norm)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def verify_login(email, password):
    """
    Check email + password against the users table.

    Returns the user row (as a dict) on success, or None on ANY failure —
    wrong password, unknown email, or a disabled (active=0) account all
    return None identically, so a login form can't be used to fingerprint
    which emails exist in the system.

    On success, stamps last_login_at.
    """
    email_norm = norm_email(email)
    if not email_norm or not password:
        return None

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE email=? AND active=1", (email_norm,)
        ).fetchone()
        if not row:
            return None
        if not _verify_password(password, row["password_hash"]):
            return None

        conn.execute(
            "UPDATE users SET last_login_at=? WHERE user_id=?", (_now(), row["user_id"])
        )
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def get_user_by_id(user_id):
    """
    Fetch a user row by id — used on every request to reload the logged-in
    user from their session's user_id. Returns None if the id is unknown
    OR the account has since been deactivated (active=0). That's what lets
    an admin disable someone and have it take effect on their very next
    request, without waiting for a session to expire.
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id=? AND active=1", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# CRM v0.1 (Viewer)  —  READ-ONLY LEAD QUERIES
# ─────────────────────────────────────────────────────────────
# Everything below is additive and read-only w.r.t. leads/events_log/
# comms_log. This keeps the file's own "no other script talks to
# SQLite directly" rule intact for the CRM's read paths too —
# app.py calls these, and never opens sqlite3 itself.

CRM_PAGE_SIZE = 50  # config-not-code: change this one number to re-page everywhere


def _build_lead_filter_where(stage=None, search=None, owner=None,
                             date_from=None, date_to=None, stage_reason=None,
                             campaign=None, campaigns=None, source=None,
                             sub_source=None, budget=None, configuration=None,
                             property_type=None, facing=None,
                             search_all_owners=False, stages=None, owners=None,
                             project=None):
    """
    (v2.28) The WHERE-clause builder shared by get_leads_page() and
    get_leads_matching() — extracted out of get_leads_page() verbatim
    (same filter semantics, same params) so bulk actions (Bulk Reassign,
    Bulk Export) can match the SAME leads a filter screen would show,
    without a second copy of this logic drifting out of sync.

    project (v2.67, F2 Phase 3): exact match on the STORED leads.
    project_bucket column. Before v2.67 this filter couldn't live here
    because the bucket was DERIVED (get_project_bucket()) rather than a
    real column — both callers instead fetched everything and filtered
    in Python afterward. Now that project_bucket is a stored, kept-in-
    sync column (F2 Phase 1/2), it filters in SQL like every other
    param here. None (the default) applies no filter — unchanged
    behavior for any caller that doesn't pass it.

    campaigns (v2.28, list, optional): NEW OR-LIKE multi-select across
    leads.campaign, same pattern as configuration/property_type/facing
    below. Independent of the existing single-string `campaign`
    substring filter — both can be supplied at once (AND'd together,
    same as any other two filters here).

    stages / owners (v2.30, lists, optional): Export-only checkbox
    multi-select — OR-across-selected-values, same pattern as
    campaigns/configuration/property_type/facing. Independent of, and
    additive alongside, the existing single-value stage/owner params
    (Bulk Reassign and every other caller keeps using those unchanged).
    owners matches case-insensitively, same convention as `owner` below.

    Returns (where_sql: str, params: list) — a caller runs
    f"SELECT ... WHERE {where_sql}" with params.
    """
    where = ["1=1"]
    params = []

    if stage:
        where.append("current_stage = ?")
        params.append(stage)

    if stages:
        ors = " OR ".join("current_stage = ?" for _ in stages)
        where.append(f"({ors})")
        params.extend(stages)

    # v2.7 — an active search with search_all_owners drops the owner
    # scope for THIS query, so a salesperson can find (but only
    # view, restricted) a lead that isn't theirs. A blank search
    # keeps the owner scope even with the flag on.
    has_active_search = bool(search and search.strip())
    apply_owner_scope = owner and not (search_all_owners and has_active_search)

    if apply_owner_scope:
        where.append("LOWER(lead_owner) = LOWER(?)")
        params.append(owner)

    if owners:
        ors = " OR ".join("LOWER(lead_owner) = LOWER(?)" for _ in owners)
        where.append(f"({ors})")
        params.extend(owners)

    if has_active_search:
        search_term = search.strip().lower()
        # v2.19 — "#" or "apx-" prefix means LEAD-ID-ONLY search: match
        # crm_lead_no exclusively, not name/phone/email at all.
        # (v2.51) That match is now EXACT, not LIKE — a LIKE match on
        # a lead number let "#2" also hit 20/200/2005/etc, which isn't
        # what typing an exact lead ID means. A bare numeric term (no
        # prefix) is a separate case handled below — it no longer
        # implicitly matches lead ID either.
        if search_term.startswith("#"):
            id_term = search_term[1:].strip()
            where.append("CAST(crm_lead_no AS TEXT) = ?")
            params.append(id_term)
        elif search_term.startswith("apx-"):
            id_term = search_term[4:].strip()
            where.append("CAST(crm_lead_no AS TEXT) = ?")
            params.append(id_term)
        elif search_term.isdigit():
            # (v2.51) An all-digits term (any length, incl. a full
            # 10-digit phone number) matches phone_norm ONLY — no
            # name/email — so a phone-number search can't accidentally
            # hit an email address that happens to contain the same
            # digits.
            where.append("phone_norm LIKE ?")
            params.append(f"%{search_term}%")
        else:
            like = f"%{search_term}%"
            where.append(
                "(LOWER(full_name) LIKE ? OR phone_norm LIKE ? OR email_norm LIKE ?)"
            )
            params.extend([like, like, like])

    if date_from:
        where.append("cls_created_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("cls_created_at <= ?")
        params.append(f"{date_to} 23:59:59")

    if stage_reason:
        where.append("stage_reason = ?")
        params.append(stage_reason)

    if campaign:
        where.append("campaign LIKE ?")
        params.append(f"%{campaign.strip()}%")

    if campaigns:
        ors = " OR ".join("campaign = ?" for _ in campaigns)
        where.append(f"({ors})")
        params.extend(campaigns)

    if source:
        where.append("source = ?")
        params.append(source)

    if sub_source:
        where.append("lead_source_detail = ?")
        params.append(sub_source)

    if budget:
        where.append("budget = ?")
        params.append(budget)

    if project:
        where.append("project_bucket = ?")
        params.append(project)

    for col_name, selected in (
        ("configuration", configuration),
        ("property_type", property_type),
        ("facing", facing),
    ):
        if selected:
            ors = " OR ".join(f"{col_name} LIKE ?" for _ in selected)
            where.append(f"({ors})")
            params.extend(f"%{val}%" for val in selected)

    return " AND ".join(where), params


def get_leads_page(stage=None, project=None, search=None, owner=None,
                   page=1, per_page=CRM_PAGE_SIZE, date_from=None, date_to=None,
                   sort_by="recent", stage_reason=None, campaign=None,
                   campaigns=None, source=None, sub_source=None, budget=None,
                   configuration=None, property_type=None, facing=None,
                   search_all_owners=False, stages=None):
    """
    Paginated, filterable lead list for the CRM's /leads screen.

    stage       : exact current_stage match (e.g. "Prospect"), or None for all
    project     : matches the BUCKETED project (leads.project_bucket,
                  v2.67+ a stored column kept in sync — see F2 Phase
                  1-3), or None for all
    search      : matches full_name, phone_norm, or email_norm (substring)
    owner       : v1.7 — exact (case-insensitive) match on leads.lead_owner.
                  Used two ways: an admin's optional "view this person's
                  pipeline" dropdown, OR a salesperson's account-level
                  owner_match_name, enforced by the caller (app.py), not
                  by this function — this function just applies whatever
                  owner string it's given.
    page        : 1-indexed
    per_page    : rows per page

    v2.5 additions (all optional, all None/default = no filter applied):
    date_from, date_to : "YYYY-MM-DD" strings, filters on cls_created_at.
                          date_to is treated as END of that day.
    sort_by     : key into SORT_OPTIONS (whitelisted — an unrecognised
                  key silently falls back to "recent", never reaches
                  raw SQL).
    stage_reason: exact match on leads.stage_reason (current Lost/
                  Unqualified reason code from v2.3).
    campaign    : substring match on leads.campaign.
    campaigns   : v2.28 — list of exact leads.campaign values, OR'd
                  together (checkbox multi-select). Independent of the
                  single-string `campaign` filter above.
    stages      : v2.44 — list of exact leads.current_stage values, OR'd
                  together (checkbox multi-select), same pattern as
                  campaigns above. Independent of, and additive alongside,
                  the existing single-value `stage` param above.
    source      : exact match on leads.source (meta/selldo_only/manual_crm).
    sub_source  : exact match on leads.lead_source_detail (the manual-
                  entry source detail, MANUAL_SOURCE_OPTIONS) — a
                  DIFFERENT column from `source`, see v2.5 changelog.
    budget      : exact match on leads.budget.
    configuration, property_type, facing : each a LIST of selected
                  checkbox values. A lead matches if ANY value in the
                  list appears anywhere in that lead's comma-separated
                  column (v2.3 multi-select) — i.e. an OR across the
                  checked boxes, matching how checkboxes read
                  intuitively ("show me 2 BHK OR 3 BHK", not AND).

    search_all_owners : v2.7. When True AND `search` is non-empty, the
                  `owner` scope is IGNORED for this query — used to let
                  a salesperson FIND (not own) a lead by name/phone/
                  email, landing them on the restricted read-only view.
                  When True but `search` is empty, owner scope is STILL
                  applied — the flag only ever widens an active search,
                  never the default blank-list. Default False keeps
                  every pre-v2.7 caller unchanged.

    Returns {"rows": [...], "total": int, "page": int, "per_page": int,
             "total_pages": int}. Each row in "rows" also carries
             age_days (v2.28) — see that changelog entry / docstring
             note below the pagination slice.

    Note (v2.67, F2 Phase 3): project filtering now happens in SQL
    (project_bucket = ?, via _build_lead_filter_where()) against the
    stored, kept-in-sync leads.project_bucket column, same as every
    other filter here — no more fetch-everything-then-filter-in-Python.
    project_bucket is also SELECTed directly rather than recomputed
    per row.
    """
    conn = _connect()
    try:
        where_sql, params = _build_lead_filter_where(
            stage=stage, search=search, owner=owner, date_from=date_from,
            date_to=date_to, stage_reason=stage_reason, campaign=campaign,
            campaigns=campaigns, source=source, sub_source=sub_source,
            budget=budget, configuration=configuration,
            property_type=property_type, facing=facing,
            search_all_owners=search_all_owners, stages=stages,
            project=project,
        )
        order_sql = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["recent"])

        all_rows = conn.execute(f"""
            SELECT cls_id, full_name, phone_raw, phone_norm, email_raw,
                   project, project_bucket, current_stage, lead_owner, source,
                   stage_updated_at, cls_updated_at, cls_created_at, crm_lead_no
            FROM leads
            WHERE {where_sql}
            ORDER BY {order_sql}
        """, params).fetchall()

        rows = [dict(r) for r in all_rows]

        total = len(rows)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        page_rows = rows[start:start + per_page]

        # v2.28 — Task 5: lead age in days, active leads only. Computed
        # only for page_rows (the rows actually rendered), same "only
        # what's on screen" scoping as compute_lead_scores(). None for
        # any lead in DRIP_TERMINAL_STAGES (Booked/Lost/Unqualified) —
        # those are closed/terminal, an age readout doesn't apply.
        for r in page_rows:
            if r["current_stage"] not in DRIP_TERMINAL_STAGES and r.get("cls_created_at"):
                try:
                    created = datetime.strptime(r["cls_created_at"], "%Y-%m-%d %H:%M:%S")
                    r["age_days"] = (datetime.now() - created).days
                except ValueError:
                    r["age_days"] = None
            else:
                r["age_days"] = None

        return {
            "rows": page_rows,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }
    finally:
        conn.close()


def get_leads_matching(stage=None, project=None, search=None, owner=None,
                       date_from=None, date_to=None, stage_reason=None,
                       campaign=None, campaigns=None, source=None,
                       sub_source=None, budget=None, configuration=None,
                       property_type=None, facing=None, stages=None, owners=None):
    """
    (v2.28) Unpaginated sibling of get_leads_page() — returns EVERY
    matching lead row (full dicts, including project_bucket), not one
    page of them. For bulk actions (Bulk Reassign, Bulk Export) that
    need the complete matched set. Same filters, same semantics, via
    the shared _build_lead_filter_where() — a lead this returns is
    exactly a lead get_leads_page() would show under the same filters.

    No search_all_owners param — bulk actions are always scoped by
    whatever `owner` the caller passes (or none, for oversight roles),
    there's no "restricted view of someone else's lead" concept here.

    stages / owners (v2.30, lists, optional) — Export's checkbox multi-
    select, passed straight through to _build_lead_filter_where(). Bulk
    Reassign never passes these (still uses single-value stage/owner).

    Returns a plain list of row dicts, sorted by full_name — bulk
    screens list/preview matched leads, they don't need get_leads_page()'s
    "most recent" default ordering.

    project filtering (v2.67, F2 Phase 3): now applied in SQL via
    _build_lead_filter_where()'s project_bucket = ? clause, same as
    get_leads_page() — see that function's note.
    """
    conn = _connect()
    try:
        where_sql, params = _build_lead_filter_where(
            stage=stage, search=search, owner=owner, date_from=date_from,
            date_to=date_to, stage_reason=stage_reason, campaign=campaign,
            campaigns=campaigns, source=source, sub_source=sub_source,
            budget=budget, configuration=configuration,
            property_type=property_type, facing=facing,
            stages=stages, owners=owners, project=project,
        )
        all_rows = conn.execute(f"""
            SELECT cls_id, full_name, phone_raw, phone_norm, email_raw,
                   project, project_bucket, current_stage, lead_owner, source,
                   stage_updated_at, cls_updated_at, cls_created_at, crm_lead_no
            FROM leads
            WHERE {where_sql}
            ORDER BY full_name COLLATE NOCASE ASC
        """, params).fetchall()

        rows = [dict(r) for r in all_rows]

        return rows
    finally:
        conn.close()


def get_distinct_campaigns():
    """
    (v2.28) Distinct non-blank leads.campaign values, alphabetical —
    sources the NEW campaign checkbox multi-select on Bulk Reassign and
    Bulk Export (see `campaigns` param on get_leads_page()/
    get_leads_matching()). Separate from cls_reports._campaign_bucket()
    grouping — this is the raw stored values, not the report-side
    bucketing.
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT DISTINCT campaign FROM leads
            WHERE campaign IS NOT NULL AND TRIM(campaign) != ''
            ORDER BY campaign COLLATE NOCASE
        """).fetchall()
        return [r["campaign"] for r in rows]
    finally:
        conn.close()


def get_site_visits_conducted(date_from=None, date_to=None, owner=None, owners=None):
    """
    (v2.28) Task 4 — Export Site Visits Conducted. site_visits rows
    with status='conducted' (never 'no_show'/'cancelled'/'scheduled'),
    joined to leads for display context. Date range filters on
    conducted_at (when the visit actually happened), not scheduled_at.
    owner filters on leads.lead_owner, exact match — same convention as
    every other owner-scoped query in this file.

    owners (v2.30, list, optional) — Export's checkbox multi-select,
    OR-across-selected-values, independent of the existing single
    `owner` param (both can be given, AND'd together, though the export
    route only ever uses one or the other in practice).
    """
    conn = _connect()
    try:
        query = """
            SELECT v.visit_id, v.cls_id, l.crm_lead_no, l.full_name,
                   l.phone_raw, l.phone_norm, l.project, l.lead_owner,
                   v.scheduled_at, v.conducted_at, v.outcome_reason, v.notes
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE v.status = 'conducted'
        """
        params = []
        if date_from and date_to:
            query += " AND substr(v.conducted_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        if owner:
            query += " AND l.lead_owner = ?"
            params.append(owner)
        if owners:
            ors = " OR ".join("LOWER(l.lead_owner) = LOWER(?)" for _ in owners)
            query += f" AND ({ors})"
            params.extend(owners)
        query += " ORDER BY v.conducted_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_activity_log_export(date_from=None, date_to=None, cls_id=None, owner=None):
    """
    (v2.28) Task 4 — Export Activity History. Cross-lead, date-ranged
    activity_log rows joined to their lead for display context (name,
    lead number) — get_activity_log_for_lead() only ever scopes to ONE
    cls_id and doesn't join; this is the variant Export needs. INNER
    JOIN is safe here: delete_lead() hard-deletes a lead's activity_log
    rows in the same transaction, so there are never orphaned rows to
    silently drop.

    owner : exact match on leads.lead_owner — same convention as
    get_site_visits_conducted()/get_leads_matching(), so app.py can
    scope a salesperson's export to their own leads' activity in SQL
    rather than filtering rows in Python after the fact.
    """
    conn = _connect()
    try:
        query = """
            SELECT a.activity_id, a.cls_id, l.crm_lead_no, l.full_name,
                   a.activity_type, a.actor, a.prev_value, a.new_value,
                   a.description, a.created_at
            FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE 1=1
        """
        params = []
        if date_from and date_to:
            query += " AND substr(a.created_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        if cls_id:
            query += " AND a.cls_id = ?"
            params.append(cls_id)
        if owner:
            query += " AND l.lead_owner = ?"
            params.append(owner)
        query += " ORDER BY a.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_lead_by_id(cls_id):
    """
    Full lead row for the /leads/<cls_id> detail screen, or None.

    (v2.67, F2 Phase 3) project_bucket used to be recomputed here via
    get_project_bucket() after the fetch; SELECT * already returns the
    stored, kept-in-sync leads.project_bucket column (F2 Phase 1/2), so
    that recompute was dead code and has been removed.
    """
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def get_lead_by_crm_no(crm_lead_no):
    """Lookup by the human-readable APX number — used by cls_reconcile_apply.py."""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM leads WHERE crm_lead_no=?", (crm_lead_no,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_events_for_lead(cls_id):
    """All CAPI fire events for one lead, newest first (events_log)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM events_log WHERE cls_id=? ORDER BY fired_at DESC", (cls_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_comms_for_lead(cls_id):
    """All drip emails sent to one lead, newest first (comms_log)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM comms_log WHERE cls_id=? ORDER BY sent_at DESC", (cls_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# DASHBOARD STATS  —  CRM v0.1.2 polish (mini dashboard on login)
# ─────────────────────────────────────────────────────────────

def get_distinct_owners():
    """
    List of distinct lead_owner values currently in use — powers the
    admin's "view this person's pipeline" dropdown on /leads. Blank/
    NULL owners are excluded (unassigned leads aren't a "person" to
    filter by here).
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT DISTINCT lead_owner FROM leads
            WHERE lead_owner IS NOT NULL AND TRIM(lead_owner) != ''
            ORDER BY lead_owner
        """).fetchall()
        return [r["lead_owner"] for r in rows]
    finally:
        conn.close()


def get_new_enquiries_count(days=7, owner=None):
    """
    v1.9: was a time-window count (leads first created in the last
    `days` days); redefined to count leads currently sitting at
    current_stage='Incoming', regardless of when they arrived.

    v2.11 REDEFINED again (Srikanth's decision 1, July 2026): a lead
    can sit at current_stage='Incoming' for a while yet already have
    been looked at (a call attempted, a note added, a walk-in visit
    logged) — the v1.9 definition still counted those as "new," which
    overstated genuinely untouched inbound. Now counts current_stage=
    'Incoming' AND zero rows in activity_log for that cls_id — i.e.
    no human action has EVER been taken on it. `days` is kept as an
    unused parameter so existing call sites don't need updating.

    v2.57 BUG FIX (Task 3 Part A) — silent undercounting since v2.28:
    the v2.11 "zero activity_log rows" clause assumed integration
    ingestion writes no activity_log rows. That stopped being true in
    v2.28, when upsert_meta_lead()'s branch 3 (genuinely new lead, no
    phone/email match) started writing exactly ONE activity_log row
    (activity_type='lead_entered', actor='system') at the moment of
    insertion. From v2.28 onward, "zero activity_log rows" could never
    be true for any lead created through normal intake, so this count
    silently degraded toward 0 for all new leads. Replaced with
    reengaged_at IS NULL — the same distinction upsert_meta_lead()
    already draws: branch 3 (genuinely new) leaves reengaged_at NULL,
    branch 2 (contact match) stamps it via _apply_reengagement_marker().
    So "reengaged_at IS NULL" means exactly "never identified as a
    repeat contact" — i.e. genuinely new, regardless of activity_log
    contents.

    v2.70 BUG FIX (Task 4, item 7) — v2.57 above was right to drop the
    old "zero activity_log rows" clause, but dropped the "a human
    touched this" signal along with it instead of replacing it with an
    actor-aware version — regressing v2.11's "clears the instant a
    human touches the lead" behavior. Restored via NOT EXISTS (a real,
    actor != 'system' activity_log row for this cls_id): the automatic
    lead_entered/lead_reengaged system rows are ignored, but any genuine
    call_attempted/note/stage-change tap by a real user now drops the
    lead off this count immediately, even while it's still technically
    sitting at current_stage='Incoming'. Combined with the still-active
    reengaged_at IS NULL clause, this both keeps v2.57's undercounting
    fix and restores the lost v2.11 human-touch behavior.

    owner (v2.31): optional, default None (existing behavior, unchanged
    — dashboard() previously called this with zero args). Pass a
    lead_owner to scope to one salesperson's own leads, same convention
    as get_stage_snapshot_counts(owner=None).
    """
    conn = _connect()
    try:
        query = """
            SELECT COUNT(*) c FROM leads l
            WHERE l.current_stage='Incoming'
              AND l.reengaged_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM activity_log a
                  WHERE a.cls_id = l.cls_id AND a.actor != 'system'
              )
        """
        params = []
        if owner:
            query += " AND l.lead_owner = ?"
            params.append(owner)
        row = conn.execute(query, params).fetchone()
        return row["c"]
    finally:
        conn.close()


def get_new_enquiries_leads(owner=None):
    """
    (v2.11) List-returning counterpart to get_new_enquiries_count()
    above — SAME criteria, just returning rows instead of a count, so
    the dashboard card can link through to an actual filtered list.
    Mirrors get_reengaged_leads()'s shape.

    v2.57 BUG FIX (Task 3 Part A) — same reengaged_at IS NULL fix as
    get_new_enquiries_count() above; see that function's docstring for
    the full explanation of the silent-undercounting bug this replaces.

    v2.70 BUG FIX (Task 4, item 7) — same NOT EXISTS actor-aware fix as
    get_new_enquiries_count() above; see that function's docstring for
    the full explanation of the lost v2.11 behavior this restores.

    owner (v2.31): optional, default None (existing behavior, unchanged
    — new_enquiries_list() previously called this with zero args). Pass
    a lead_owner to scope to one salesperson's own leads.
    """
    conn = _connect()
    try:
        query = """
            SELECT * FROM leads l
            WHERE l.current_stage='Incoming'
              AND l.reengaged_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM activity_log a
                  WHERE a.cls_id = l.cls_id AND a.actor != 'system'
              )
        """
        params = []
        if owner:
            query += " AND l.lead_owner = ?"
            params.append(owner)
        query += " ORDER BY l.cls_created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_no_future_activity_count(owner=None):
    """
    (v2.57, Task 3 Part A) NEW — counts open-pipeline leads (not
    Unqualified/Lost/Booked — reuses RESET_STAGES_ON_REENGAGEMENT, the
    existing "dead enough" stage set, rather than a new literal tuple)
    that have no scheduled site visit AND no scheduled follow-up open
    against them right now. Live-computed at query time (NOT EXISTS
    against site_visits/follow_ups with status='scheduled'), same
    posture as get_reengaged_count()'s live computation — no stored
    "cleared" flag to drift out of sync.

    owner: optional, default None. Pass a lead_owner to scope to one
    salesperson's own leads, same convention as every other dashboard
    count function in this file.
    """
    conn = _connect()
    try:
        query = """
            SELECT COUNT(*) c FROM leads l
            WHERE l.current_stage NOT IN ({placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM site_visits v
                  WHERE v.cls_id = l.cls_id AND v.status = 'scheduled'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM follow_ups f
                  WHERE f.cls_id = l.cls_id AND f.status = 'scheduled'
              )
        """.format(placeholders=",".join("?" for _ in RESET_STAGES_ON_REENGAGEMENT))
        params = list(RESET_STAGES_ON_REENGAGEMENT)
        if owner:
            query += " AND l.lead_owner = ?"
            params.append(owner)
        row = conn.execute(query, params).fetchone()
        return row["c"]
    finally:
        conn.close()


def get_no_future_activity_leads(owner=None):
    """
    (v2.57, Task 3 Part A) List-returning counterpart to
    get_no_future_activity_count() above — SAME criteria, just
    returning rows instead of a count, so the dashboard card can link
    through to an actual filtered list. Mirrors get_new_enquiries_leads()'s
    shape.

    owner: optional, default None. Pass a lead_owner to scope to one
    salesperson's own leads.
    """
    conn = _connect()
    try:
        query = """
            SELECT * FROM leads l
            WHERE l.current_stage NOT IN ({placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM site_visits v
                  WHERE v.cls_id = l.cls_id AND v.status = 'scheduled'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM follow_ups f
                  WHERE f.cls_id = l.cls_id AND f.status = 'scheduled'
              )
        """.format(placeholders=",".join("?" for _ in RESET_STAGES_ON_REENGAGEMENT))
        params = list(RESET_STAGES_ON_REENGAGEMENT)
        if owner:
            query += " AND l.lead_owner = ?"
            params.append(owner)
        query += " ORDER BY l.cls_created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


MISSED_CALLS_WINDOW_DAYS = 7  # config-not-code: how far back get_missed_calls_count()/get_missed_calls_list() look


def get_missed_calls_count(owner=None, days=MISSED_CALLS_WINDOW_DAYS):
    """
    (v2.57, Task 3 Part A) NEW — counts missed calls with no later
    outgoing call back to the same matched lead. A call only counts if
    it matched a lead (matched_cls_id IS NOT NULL) — unmatched numbers
    are never persisted anywhere in call_log_staging beyond the staging
    row itself (see call_log_staging's own schema note), so there's
    nothing to join back to a lead here anyway.

    Deliberately scoped via leads.lead_owner (the CURRENT owner), not
    call_log_staging.user_id (whoever's phone the call landed on) — a
    missed call always shows against whoever owns the lead right now,
    even if it was reassigned after the call came in.

    owner: optional, default None. Pass a lead_owner to scope to one
    salesperson's own leads.

    (v2.81) Now windowed to `days` days (default MISSED_CALLS_WINDOW_DAYS
    = 7), superseding the all-time v2.57 behavior — a missed call older
    than the window no longer counts, even with no callback since.

    (v2.83) — deduped re-synced duplicate call_log_staging rows (same
    root cause documented in get_call_staging_rows()'s v2.71 docstring);
    no data deleted, this is a read-only query fix.
    """
    conn = _connect()
    try:
        query = """
            SELECT COUNT(*) c FROM (
                SELECT m.matched_cls_id, m.call_timestamp
                FROM call_log_staging m
                WHERE m.direction = 'MISSED'
                  AND m.matched_cls_id IS NOT NULL
                  AND m.call_timestamp >= datetime('now', 'localtime', ?)
                  AND NOT EXISTS (
                      SELECT 1 FROM call_log_staging o
                      WHERE o.matched_cls_id = m.matched_cls_id
                        AND o.direction = 'OUTGOING'
                        AND o.call_timestamp > m.call_timestamp
                  )
                GROUP BY m.matched_cls_id, m.call_timestamp
            ) m
            JOIN leads l ON l.cls_id = m.matched_cls_id
        """
        params = [f"-{days} days"]
        if owner:
            query += " WHERE l.lead_owner = ?"
            params.append(owner)
        row = conn.execute(query, params).fetchone()
        return row["c"]
    finally:
        conn.close()


def get_missed_calls_list(owner=None, days=MISSED_CALLS_WINDOW_DAYS):
    """
    (v2.57, Task 3 Part A) List-returning counterpart to
    get_missed_calls_count() above — SAME criteria, returning
    call_timestamp, raw_phone, full_name, cls_id, crm_lead_no ordered
    newest-first.

    owner: optional, default None. Pass a lead_owner to scope to one
    salesperson's own leads.

    (v2.81) Now windowed to `days` days (default MISSED_CALLS_WINDOW_DAYS
    = 7), superseding the all-time v2.57 behavior — a missed call older
    than the window no longer counts, even with no callback since.

    (v2.83) — deduped re-synced duplicate call_log_staging rows (same
    root cause documented in get_call_staging_rows()'s v2.71 docstring);
    no data deleted, this is a read-only query fix.
    """
    conn = _connect()
    try:
        query = """
            SELECT d.call_timestamp, d.raw_phone, l.full_name, l.cls_id, l.crm_lead_no
            FROM (
                SELECT m.matched_cls_id, m.call_timestamp, MIN(m.raw_phone) AS raw_phone
                FROM call_log_staging m
                WHERE m.direction = 'MISSED'
                  AND m.matched_cls_id IS NOT NULL
                  AND m.call_timestamp >= datetime('now', 'localtime', ?)
                  AND NOT EXISTS (
                      SELECT 1 FROM call_log_staging o
                      WHERE o.matched_cls_id = m.matched_cls_id
                        AND o.direction = 'OUTGOING'
                        AND o.call_timestamp > m.call_timestamp
                  )
                GROUP BY m.matched_cls_id, m.call_timestamp
            ) d
            JOIN leads l ON l.cls_id = d.matched_cls_id
        """
        params = [f"-{days} days"]
        if owner:
            query += " WHERE l.lead_owner = ?"
            params.append(owner)
        query += " ORDER BY d.call_timestamp DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# PAUSED — superseded by precise reengaged_at-based definition,
# Srikanth's July 2026 decision; retained for reference.
#
# def get_reengaged_count(days=7):
#     """
#     APPROXIMATE reengagement signal — labelled as such in the UI on
#     purpose. Counts leads that already existed BEFORE the window
#     (cls_created_at older than `days`) but were touched INSIDE the
#     window (cls_updated_at within `days`).
#
#     The caveat (deliberately not hidden): this can't yet distinguish
#     "a genuine new inbound inquiry from a returning customer" from "a
#     routine stage re-sync on an old lead" — both bump cls_updated_at
#     identically. A precise version means adding a marker at the exact
#     moment find_match() succeeds inside upsert_meta_lead/
#     upsert_selldo_lead, which is a production write-path change —
#     deliberately deferred rather than rushed into a read-only polish
#     pass. Until then, treat this number as directional, not exact.
#     """
#     conn = _connect()
#     try:
#         cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
#         row = conn.execute("""
#             SELECT COUNT(*) c FROM leads
#             WHERE cls_created_at < ? AND cls_updated_at >= ?
#         """, (cutoff, cutoff)).fetchone()
#         return row["c"]
#     finally:
#         conn.close()
#
#
# def get_reengaged_leads(days=7, owner=None, date_from=None, date_to=None):
#     """
#     List-returning counterpart to get_reengaged_count() above — SAME
#     approximate criteria (see that function's docstring for the full
#     caveat), just returning rows instead of a count, so the dashboard
#     card can link through to an actual filtered list.
#
#     owner (v2.12): optional, default None (existing behavior,
#     unchanged — reengaged_list() keeps calling this with no owner
#     arg). Pass a lead_owner to scope to one salesperson's own leads,
#     for Report #9's owner-filtered view.
#
#     date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings, default
#     None (existing behavior unchanged — `days` trailing window from
#     right now). When both given, the cutoff becomes date_from's start
#     of day (leads created before the selected period, reengaged AT OR
#     AFTER it starts) and matches are additionally capped at date_to's
#     end of day — "which existing leads came back DURING this period,"
#     not "...since N days ago."
#     """
#     conn = _connect()
#     try:
#         if date_from and date_to:
#             cutoff = f"{date_from} 00:00:00"
#             upper = f"{date_to} 23:59:59"
#             query = """
#                 SELECT * FROM leads
#                 WHERE cls_created_at < ? AND cls_updated_at >= ? AND cls_updated_at <= ?
#             """
#             params = [cutoff, cutoff, upper]
#         else:
#             cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
#             query = """
#                 SELECT * FROM leads
#                 WHERE cls_created_at < ? AND cls_updated_at >= ?
#             """
#             params = [cutoff, cutoff]
#         if owner:
#             query += " AND lead_owner = ?"
#             params.append(owner)
#         query += " ORDER BY cls_updated_at DESC"
#         rows = conn.execute(query, params).fetchall()
#         return [dict(r) for r in rows]
#     finally:
#         conn.close()


def get_reengaged_count(days=7, owner=None):
    """
    (v2.20, Task 3) PRECISE reengagement signal, superseding the old
    approximate cls_updated_at-window definition above. Counts leads
    whose reengaged_at marker is set (stamped by
    _apply_reengagement_marker(), called from upsert_meta_lead()'s
    contact-match/enrich branch) AND that have had NO activity_log
    entry since that marker — i.e. "came back, and nobody's touched it
    since." Computed LIVE at query time (no stored "cleared" flag),
    same principle as missed-status computation elsewhere in this file
    (get_due_by_kind() etc.) — the moment any activity is logged
    against the lead, it naturally drops out of this count on the very
    next read.

    `days` is accepted but UNUSED — kept only so this function's
    existing call sites (dashboard()'s get_reengaged_count(days=7))
    need no changes. There is no trailing-window concept in the new
    definition; a lead stays counted for as long as it remains
    genuinely untouched since re-entering, however long that is.

    owner (v2.31): optional, default None (existing behavior, unchanged
    — dashboard() previously called this with only days=7). Pass a
    lead_owner to scope to one salesperson's own leads, same convention
    as get_stage_snapshot_counts(owner=None).

    EXPECTED AT DEPLOY: every existing lead has reengaged_at=NULL (the
    migration is additive, nothing is backfilled), so this reads 0
    until new re-entries happen through Job A's enrich path — not a bug.
    """
    conn = _connect()
    try:
        query = """
            SELECT COUNT(*) c FROM leads
            WHERE reengaged_at IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM activity_log a
                WHERE a.cls_id = leads.cls_id AND a.created_at > leads.reengaged_at
              )
        """
        params = []
        if owner:
            query += " AND lead_owner = ?"
            params.append(owner)
        row = conn.execute(query, params).fetchone()
        return row["c"]
    finally:
        conn.close()


def get_reengaged_leads(days=7, owner=None, date_from=None, date_to=None):
    """
    (v2.20, Task 3) List-returning counterpart to get_reengaged_count()
    above — SAME precise, live-computed criteria (see that function's
    docstring). `days` is accepted but UNUSED, same reason as above —
    kept purely so reengaged_list()'s existing get_reengaged_leads(days=7)
    call needs no changes.

    owner : optional, default None (unchanged call-site behavior) —
    scopes to one salesperson's lead_owner, same as before.

    date_from/date_to : optional 'YYYY-MM-DD' strings, default None
    (unchanged call-site behavior). v2.20 CHANGE: when both given, they
    now bound reengaged_at (which existing leads came back DURING this
    period), not cls_updated_at as the old definition did — cls_reports.
    _build_reengagement() already passes these through unchanged, so
    the report's date-range picker keeps working with the new meaning.
    """
    conn = _connect()
    try:
        query = """
            SELECT * FROM leads
            WHERE reengaged_at IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM activity_log a
                WHERE a.cls_id = leads.cls_id AND a.created_at > leads.reengaged_at
              )
        """
        params = []
        if date_from and date_to:
            query += " AND reengaged_at >= ? AND reengaged_at <= ?"
            params.extend([f"{date_from} 00:00:00", f"{date_to} 23:59:59"])
        if owner:
            query += " AND lead_owner = ?"
            params.append(owner)
        query += " ORDER BY reengaged_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stage_snapshot_counts(owner=None):
    """
    (v2.4) Current-moment count of leads sitting in EACH of ALL_STAGES
    right now — feeds the Pipeline Analysis dashboard tiles. Every
    stage in ALL_STAGES is guaranteed a key in the returned dict, even
    if its count is 0, so the template never has to guard against a
    missing key.

    This is a live snapshot (COUNT(*) ... GROUP BY current_stage,
    read at request time), not a "stage distribution as it stood
    earlier today" historical figure — see the v2.4 changelog note for
    why that distinction is deliberate.

    owner (v2.12): optional, default None (existing behavior,
    unchanged — dashboard_pipeline() keeps calling this with zero
    args). Pass a lead_owner to scope the snapshot to one
    salesperson's own leads, for Report #2's owner-filtered view.
    """
    conn = _connect()
    try:
        query = "SELECT current_stage, COUNT(*) c FROM leads"
        params = []
        if owner:
            query += " WHERE lead_owner = ?"
            params.append(owner)
        query += " GROUP BY current_stage"
        rows = conn.execute(query, params).fetchall()
        live_counts = {r["current_stage"]: r["c"] for r in rows}
        return {stage: live_counts.get(stage, 0) for stage in ALL_STAGES}
    finally:
        conn.close()


def get_leads_created_today_count():
    """
    (v2.4) Count of leads whose cls_created_at falls today (server
    local date) — feeds Pipeline Analysis's "Total Leads" tile. Same
    substr(cls_created_at,1,10) convention as get_daily_owner_summary().
    """
    conn = _connect()
    try:
        today = _now()[:10]
        row = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE substr(cls_created_at, 1, 10) = ?",
            (today,)
        ).fetchone()
        return row["c"]
    finally:
        conn.close()


def get_leads_created_in_range(date_from=None, date_to=None):
    """
    (v2.37) New-lead count (by leads.cls_created_at date) within an
    inclusive date range — feeds Pipeline Analysis's date-range-aware
    "Total Leads" tile (dashboard_pipeline() route, app.py). Same
    substr(cls_created_at, 1, 10) BETWEEN ? AND ? pattern
    list_call_recordings() already uses for its own date filter,
    including that filter's "both or neither" rule: pass both
    date_from and date_to to filter, or leave either blank/None for an
    all-time count (this is what makes the "maximum" preset — whose
    resolver returns ("", "") — work correctly here with no special
    case). get_leads_created_today_count() is untouched; this is a
    separate, additive function, not a replacement.
    """
    conn = _connect()
    try:
        query = "SELECT COUNT(*) c FROM leads"
        params = []
        if date_from and date_to:
            query += " WHERE substr(cls_created_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        row = conn.execute(query, params).fetchone()
        return row["c"]
    finally:
        conn.close()


def get_todays_activity_counts(actor_email=None):
    """
    (v2.4) Today's Performance numbers, read entirely from activity_log
    (one table, one grouped query) — every metric asked for already
    has a matching activity_type logged the moment it happens, so
    there's no need to also query site_visits/follow_ups directly.

    actor_email : pass a salesperson's login email to scope to THEIR
                  own actions only (app.py does this for salesperson
                  logins). Omit (None) for a company-wide total across
                  everyone — app.py does this for admin logins.

    Returns a dict with fixed keys (0 if nothing happened today):
        calls_attempted, site_visits_created, site_visits_conducted,
        follow_ups_created, follow_ups_completed

    Deliberately does NOT return "total talk time" — that needs call
    duration/connected-status data this schema doesn't have yet; it's
    v1.0 Telephony's job, exactly as roadmapped. calls_attempted is a
    tap-count proxy, same honest limit as log_call_tap() itself.

    (v2.12) NEW 'notes_added' key (activity_type='note') for Report
    #1's Daily Scorecard — every other key this function already
    returned is unchanged.

    (v2.70, Task 4 item 3) NEW 'sittings_done' key (activity_type=
    'sitting_done', from the new log_sitting_done()) — same automatic
    pickup as every other METRIC_MAP entry, no separate counting code.
    """
    METRIC_MAP = {
        "call_attempted":        "calls_attempted",
        "site_visit_scheduled":  "site_visits_created",
        "site_visit_conducted":  "site_visits_conducted",
        "follow_up_scheduled":   "follow_ups_created",
        "follow_up_completed":   "follow_ups_completed",
        "note":                  "notes_added",
        "sitting_done":          "sittings_done",
    }
    result = {key: 0 for key in METRIC_MAP.values()}

    conn = _connect()
    try:
        today = _now()[:10]
        types_placeholder = ", ".join("?" for _ in METRIC_MAP)
        params = [today] + list(METRIC_MAP.keys())
        query = f"""
            SELECT activity_type, COUNT(*) c
            FROM activity_log
            WHERE substr(created_at, 1, 10) = ?
              AND activity_type IN ({types_placeholder})
        """
        if actor_email:
            query += " AND actor = ?"
            params.append(actor_email)
        query += " GROUP BY activity_type"

        rows = conn.execute(query, params).fetchall()
        for r in rows:
            result[METRIC_MAP[r["activity_type"]]] = r["c"]
        return result
    finally:
        conn.close()


def get_todays_achievements(user_id):
    """
    (v2.51) Self-scoped "Daily Achievements" summary — item 7, shown as
    an interstitial on logout (see app.py v0.42's changelog). Always
    scoped to user_id's own actions, never company-wide.

    Extends get_todays_activity_counts()'s dict (calls_attempted,
    site_visits_created/conducted, follow_ups_created/completed,
    notes_added — all today, all this user's own actor rows) with two
    more numbers:
      stage_changes : today's activity_log rows with
                       activity_type='stage_change' and actor=this
                       user's email — same actor-scoping convention
                       get_todays_activity_counts() already uses.
      time_worked   : today's attendance row's logout_ts-login_ts as
                       "Xh Ym", "still working" if login_ts is set but
                       logout_ts isn't yet, or the key is OMITTED
                       entirely if no attendance row exists today at
                       all (e.g. a role that doesn't punch) — omission,
                       not a zero/blank, so the template can tell "no
                       data" apart from "worked 0 minutes."

    Deliberately does NOT attempt a "time spoken to customers" metric
    — no call-duration data exists pre-Telephony, same honest limit
    get_todays_activity_counts() already documents for calls_attempted.

    Returns None if user_id doesn't resolve to a user at all.
    """
    user = get_user_by_id(user_id)
    if not user:
        return None

    today = _now()[:10]
    result = get_todays_activity_counts(actor_email=user["email"])

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) c FROM activity_log "
            "WHERE substr(created_at, 1, 10) = ? AND activity_type = 'stage_change' "
            "AND actor = ?",
            (today, user["email"])
        ).fetchone()
        result["stage_changes"] = row["c"] if row else 0
    finally:
        conn.close()

    attendance = get_attendance_for_date(user_id, today)
    if attendance and attendance.get("login_ts"):
        if attendance.get("logout_ts"):
            try:
                login_dt = datetime.strptime(attendance["login_ts"], "%Y-%m-%d %H:%M:%S")
                logout_dt = datetime.strptime(attendance["logout_ts"], "%Y-%m-%d %H:%M:%S")
                worked_minutes = max(0, int((logout_dt - login_dt).total_seconds() // 60))
                result["time_worked"] = f"{worked_minutes // 60}h {worked_minutes % 60}m"
            except ValueError:
                pass
        else:
            result["time_worked"] = "still working"

    return result


# ─────────────────────────────────────────────────────────────
# Today's Performance drill-downs (v2.52, Phase 4 of the 6-phase batch)
# ─────────────────────────────────────────────────────────────
# One small function per tile, each mirroring get_todays_activity_counts()'s
# own scoping EXACTLY: activity_log rows for TODAY, filtered by
# activity_type, optionally scoped to one actor_email (None = company-
# wide). This is actor-based scoping (WHO performed the action, matched
# by login email), deliberately NOT the owner-based scoping
# (leads.lead_owner) used almost everywhere else in this file — it has
# to match what the Today's Performance tile above each drill-down
# actually counts, and that tile is actor-scoped. Concretely this means
# get_site_visits_conducted() (owner-scoped, built for Export) is NOT
# reused here even though it queries a very similar shape — reusing it
# would let the drill-down list disagree with its own tile's number in
# edge cases (e.g. a manager conducting a visit on a rep's lead). Each
# function returns a list of dicts, one per matching activity_log row,
# newest first: {cls_id, crm_lead_no, full_name, lead_owner, actor,
# created_at, description}. description is whatever note text was
# recorded against that action, if any (may be None).

def _activity_rows_today(activity_type, actor_email):
    """(v2.52, internal) Shared row-fetch behind the 5 Today's Performance
    drill-down functions below — same query shape, only activity_type/
    actor_email differ, so this stays a private helper rather than 5
    copies of the same JOIN. Each public function keeps its own name/
    docstring so callers and this module's Report-style call sites read
    the same per-purpose way as everywhere else in this file."""
    conn = _connect()
    try:
        today = _now()[:10]
        query = """
            SELECT a.cls_id, l.crm_lead_no, l.full_name, l.lead_owner,
                   a.actor, a.created_at, a.description
            FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type = ?
              AND substr(a.created_at, 1, 10) = ?
        """
        params = [activity_type, today]
        if actor_email:
            query += " AND a.actor = ?"
            params.append(actor_email)
        query += " ORDER BY a.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_calls_made_today(actor_email=None):
    """(v2.52) Drill-down behind the Today's Performance "Calls Made"
    tile — today's activity_log 'call_attempted' rows (see
    log_call_tap()), actor-scoped to match that tile's own count."""
    return _activity_rows_today("call_attempted", actor_email)


def get_site_visits_scheduled_today(actor_email=None):
    """(v2.52) Drill-down behind the Today's Performance "Site Visits
    Scheduled" tile — today's activity_log 'site_visit_scheduled' rows,
    actor-scoped to match that tile's own count."""
    return _activity_rows_today("site_visit_scheduled", actor_email)


def get_site_visits_conducted_today(actor_email=None):
    """(v2.52) Drill-down behind the Today's Performance "Site Visits
    Conducted" tile — today's activity_log 'site_visit_conducted' rows,
    actor-scoped to match that tile's own count. NOT the same data
    source as get_site_visits_conducted() (Export, owner-scoped) — see
    this section's header comment for why."""
    return _activity_rows_today("site_visit_conducted", actor_email)


def get_follow_ups_scheduled_today(actor_email=None):
    """(v2.52) Drill-down behind the Today's Performance "Follow-ups
    Scheduled" tile — today's activity_log 'follow_up_scheduled' rows,
    actor-scoped to match that tile's own count."""
    return _activity_rows_today("follow_up_scheduled", actor_email)


def get_follow_ups_completed_today(actor_email=None):
    """(v2.52) Drill-down behind the Today's Performance "Follow-ups
    Completed" tile — today's activity_log 'follow_up_completed' rows,
    actor-scoped to match that tile's own count."""
    return _activity_rows_today("follow_up_completed", actor_email)


def get_sittings_done_today(actor_email=None):
    """(v2.85) Drill-down behind the Today's Performance "Sittings
    Done" tile — today's activity_log 'sitting_done' rows (see
    log_sitting_done()), actor-scoped to match that tile's own
    count."""
    return _activity_rows_today("sitting_done", actor_email)


# Config-not-code: metric-key -> (display label, drill-down fetch
# function), one entry per Today's Performance tile. Drives app.py's
# single /dashboard/today/<metric> route rather than 5 near-identical
# routes/if-branches. Must stay AFTER the 6 functions above since it
# references them directly.
TODAY_PERFORMANCE_METRICS = {
    "calls_made":              {"label": "Calls Made",              "fetch": get_calls_made_today},
    "site_visits_scheduled":   {"label": "Site Visits Scheduled",   "fetch": get_site_visits_scheduled_today},
    "site_visits_conducted":   {"label": "Site Visits Conducted",   "fetch": get_site_visits_conducted_today},
    "follow_ups_scheduled":    {"label": "Follow-ups Scheduled",    "fetch": get_follow_ups_scheduled_today},
    "follow_ups_completed":    {"label": "Follow-ups Completed",    "fetch": get_follow_ups_completed_today},
    "sittings_done":           {"label": "Sittings Done",           "fetch": get_sittings_done_today},
}


def get_latest_stage_and_owner_changes():
    """
    (v2.10) Read-only feed for cls_parallel_export.py — measures how
    often a CRM-side stage or owner change gets silently reverted by
    Job B's next Sell.do sync. For every lead that has AT LEAST ONE
    'stage_change' and/or 'assignment_change' row in activity_log,
    returns its identity, CURRENT current_stage/lead_owner, and the
    MOST RECENT row of each change type (actor, prev_value, new_value,
    created_at — NULL for whichever type this lead never had logged).

    "Most recent" is activity_id (autoincrement) MAX per (cls_id,
    activity_type) — the same tiebreaker get_activity_log_for_lead()
    already sorts by (created_at DESC, activity_id DESC), since
    created_at alone (second-granularity) can tie.

    Leads with NEITHER activity type are excluded entirely — there is
    no CRM-side change to compare against for them, so including them
    would just be noise in both the stage-drift and owner-drift counts.

    Deliberately returns raw data only — it does NOT decide reverted /
    pending / clean. That comparison needs "has enough time passed for
    Job B to have run since this change," which is a time-sensitive
    policy call that belongs in the caller (cls_parallel_export.py),
    not baked into a DB-layer read. This is the ONLY database access
    cls_parallel_export.py makes; it never opens sqlite3 directly.
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT
                l.cls_id, l.full_name, l.phone_raw, l.email_raw,
                l.current_stage, l.lead_owner,
                sc.actor      AS stage_change_actor,
                sc.prev_value AS stage_change_prev,
                sc.new_value  AS stage_change_new,
                sc.created_at AS stage_change_at,
                ac.actor      AS owner_change_actor,
                ac.prev_value AS owner_change_prev,
                ac.new_value  AS owner_change_new,
                ac.created_at AS owner_change_at
            FROM leads l
            LEFT JOIN (
                SELECT a.cls_id, a.actor, a.prev_value, a.new_value, a.created_at
                FROM activity_log a
                WHERE a.activity_type = 'stage_change'
                  AND a.activity_id = (
                      SELECT MAX(a2.activity_id) FROM activity_log a2
                      WHERE a2.cls_id = a.cls_id AND a2.activity_type = 'stage_change'
                  )
            ) sc ON sc.cls_id = l.cls_id
            LEFT JOIN (
                SELECT a.cls_id, a.actor, a.prev_value, a.new_value, a.created_at
                FROM activity_log a
                WHERE a.activity_type = 'assignment_change'
                  AND a.activity_id = (
                      SELECT MAX(a2.activity_id) FROM activity_log a2
                      WHERE a2.cls_id = a.cls_id AND a2.activity_type = 'assignment_change'
                  )
            ) ac ON ac.cls_id = l.cls_id
            WHERE sc.cls_id IS NOT NULL OR ac.cls_id IS NOT NULL
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# WRITER FUNCTIONS  —  CRM v0.5 (Writer)
# ─────────────────────────────────────────────────────────────
# Everything below is the CRM's first WRITE path into leads.current_stage
# and leads.lead_owner. Jobs A-D never call any of this and are
# unaffected either way — Job B's own writes to these same columns are
# untouched (see the v1.8 changelog note on why that's intentional).

def _log_activity(conn, cls_id, activity_type, actor, prev_value=None,
                  new_value=None, description=None, created_at=None,
                  recording_file_path=None, duration_seconds=None,
                  matched_phone=None, direction=None):
    """
    Internal helper — appends one row to activity_log. Takes an OPEN
    connection (not a fresh one) so callers can log the activity in
    the SAME transaction as the actual write, keeping them atomic:
    either both the write and its audit row land, or neither does.

    v2.28: optional created_at param — defaults to _now() exactly as
    before when omitted (every pre-existing caller). Lets a caller
    backdate the row to when the event actually happened rather than
    when this write ran — used by upsert_meta_lead()'s lead_entered
    row, which should read as the lead's real Meta created_time, not
    whenever Job A happened to poll it.

    v2.33: optional recording_file_path/duration_seconds/matched_phone
    params, all None by default — every pre-existing caller is
    unaffected. Used only by log_call_recording() for activity_type=
    'call_recording' rows (see Phase B Telephony schema above).

    v2.49: optional direction param, None by default — every pre-
    existing caller unaffected. Used only by log_call_recording() to
    carry call_log_staging.direction ('INCOMING'/'OUTGOING'/... as
    reported by the app) through onto the call_recording row.
    """
    conn.execute("""
        INSERT INTO activity_log (
            cls_id, activity_type, actor, prev_value, new_value,
            description, created_at, recording_file_path,
            duration_seconds, matched_phone, direction
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (cls_id, activity_type, actor, prev_value, new_value,
          description, created_at or _now(), recording_file_path,
          duration_seconds, matched_phone, direction))


# Stages that cancel any open schedule the moment a lead lands on them.
# Config-not-code — add a stage here if another one should ever behave
# the same way (v2.2, Srikanth's call).
AUTO_CANCEL_ON_STAGES = ["Lost", "Unqualified"]


def _auto_cancel_open_schedules(conn, cls_id, new_stage, actor):
    """
    Internal helper (v2.2) — called from INSIDE update_lead_stage()'s
    own open transaction, right after the stage write, whenever
    new_stage is in AUTO_CANCEL_ON_STAGES. Closes any OPEN
    (status='scheduled') site visit and/or follow-up for this lead by
    marking it cancelled, with a clear auto-generated outcome_reason,
    and logs the same activity_type a manual cancellation would
    (site_visit_cancelled / follow_up_cancelled) so Activity History
    shows no visible difference in how it renders — just who/why.

    Because of the existing one-open-at-a-time rule, this is AT MOST
    one site_visits row + one follow_ups row per call — never a bulk
    operation. Silently does nothing if there's nothing open (the
    common case), which is correct — most Lost/Unqualified leads won't
    have anything scheduled.
    """
    reason = f"Auto-cancelled — lead marked {new_stage}"
    now = _now()

    open_visit = conn.execute(
        "SELECT visit_id, scheduled_at FROM site_visits WHERE cls_id=? AND status='scheduled'",
        (cls_id,)
    ).fetchone()
    if open_visit:
        conn.execute("""
            UPDATE site_visits SET status='cancelled', outcome_reason=? WHERE visit_id=?
        """, (reason, open_visit["visit_id"]))
        _log_activity(conn, cls_id, "site_visit_cancelled", actor, description=reason)

    open_followup = conn.execute(
        "SELECT followup_id, scheduled_at FROM follow_ups WHERE cls_id=? AND status='scheduled'",
        (cls_id,)
    ).fetchone()
    if open_followup:
        conn.execute("""
            UPDATE follow_ups SET status='cancelled', outcome_reason=? WHERE followup_id=?
        """, (reason, open_followup["followup_id"]))
        _log_activity(conn, cls_id, "follow_up_cancelled", actor, description=reason)


def _get_cross_reassign_rule(conn, source_bucket):
    """
    Internal helper (v2.75) — reads the active cross_project_reassign_
    rules row for source_bucket, if any, on the SAME open connection.
    Returns None if no active rule exists for that bucket — this is
    what keeps the feature correctly inert for Prima Paradiso, Praga
    Enclave, or any future project bucket that never gets a rule row.
    """
    return conn.execute(
        "SELECT id, source_bucket, target_bucket, rule_type, owners, next_index "
        "FROM cross_project_reassign_rules WHERE source_bucket=? AND active=1",
        (source_bucket,)
    ).fetchone()


def _pick_cross_reassign_owner(conn, rule):
    """
    Internal helper (v2.75) — same logic as resolve_owner_for_new_lead()'s
    round-robin picker for campaign_routing_rules:
      - rule_type='single' -> owners[0].
      - rule_type='round_robin' -> owners[next_index % len(owners)], then
        next_index is incremented on that same row (same conn, not yet
        committed here — the caller's own commit covers it).
    """
    owners = json.loads(rule["owners"])
    if rule["rule_type"] == "single":
        return owners[0]

    picked = owners[rule["next_index"] % len(owners)]
    conn.execute(
        "UPDATE cross_project_reassign_rules SET next_index = next_index + 1 WHERE id=?",
        (rule["id"],)
    )
    return picked


def _auto_cross_reassign_project(conn, cls_id, source_bucket, new_stage, actor):
    """
    Internal helper (v2.75) — called from INSIDE update_lead_stage()'s
    own open transaction, right after _auto_cancel_open_schedules(),
    whenever the lead's project_bucket has an active cross-project
    reassignment rule configured. Model: _auto_cancel_open_schedules()
    above — same "silently no-op if nothing to do" posture.

    Permanent ping-pong guard: once leads.cross_reassigned_at is set for
    a lead, this can never fire again for that lead — Srikanth's
    explicit instruction (2026-08): after one auto-reassignment, if the
    lead goes Lost/Unqualified again on the new project too, it just
    stays there. No second bounce, ever.
    """
    rule = _get_cross_reassign_rule(conn, source_bucket)
    if not rule:
        return

    row = conn.execute(
        "SELECT full_name, cross_reassigned_at FROM leads WHERE cls_id=?", (cls_id,)
    ).fetchone()
    if not row or row["cross_reassigned_at"] is not None:
        return

    picked_owner = _pick_cross_reassign_owner(conn, rule)
    target_bucket = rule["target_bucket"]
    now = _now()

    conn.execute("""
        UPDATE leads
        SET current_stage='Re Assigned', stage_reason=NULL,
            project=?, project_bucket=?, lead_owner=?, cross_reassigned_at=?
        WHERE cls_id=?
    """, (target_bucket, target_bucket, picked_owner, now, cls_id))

    _log_activity(
        conn, cls_id, "cross_project_reassigned", actor,
        description=(
            f"Auto-reassigned: {source_bucket} -> {target_bucket}. "
            f"New owner: {picked_owner}. (Lead was marked {new_stage}.)"
        )
    )

    new_owner_user_id = resolve_user_id_from_owner_name(picked_owner)
    if new_owner_user_id:
        message = NOTIFICATION_EVENTS["lead_cross_reassigned"].format(
            full_name=row["full_name"] or "(no name)", project=target_bucket
        )
        insert_notification(new_owner_user_id, cls_id, "lead_cross_reassigned", message, conn=conn)


def update_lead_stage(cls_id, new_stage, actor, reason_code=None, reason_notes=None):
    """
    Change a lead's stage from the CRM, enforcing the SAME one-way
    transition rules as Sell.do's own rule-based engine (STAGE_TRANSITIONS
    above). Writes DIRECTLY to leads.current_stage — the same column
    Job B writes — so Job C's very next cycle can fire on it.

    Re-reads the lead's CURRENT stage from the database at write time
    (not whatever the caller believes it to be), because Job B can
    sync a Sell.do change in the background at any moment. This closes
    the race where a salesperson's page loaded with a now-stale stage
    and submits a transition that was valid a minute ago but isn't
    valid anymore.

    v2.2: if new_stage is in AUTO_CANCEL_ON_STAGES (Lost/Unqualified),
    any open site visit / follow-up for this lead is auto-cancelled in
    the SAME transaction — see _auto_cancel_open_schedules() above.

    v2.3: whenever new_stage is 'Lost' or 'Unqualified', reason_code
    (one value from the list STAGE_REASON_LISTS maps new_stage to) and
    reason_notes (non-empty free text) are now BOTH REQUIRED — same
    mandatory-reason pattern already used for site visit/follow-up
    outcomes. reason_code is written to leads.stage_reason; reason_notes
    is appended to this same stage_change activity_log row's description
    (no new activity_type). Moving OUT of Lost/Unqualified to any other
    stage clears stage_reason back to NULL in the same write, since it
    only ever describes the CURRENT Lost/Unqualified state — the full
    historical reason still lives permanently in activity_log regardless.

    v2.11: reason_code validation is now driven by STAGE_REASON_LISTS
    (config-not-code) instead of two hardcoded if/elif branches against
    LOST_REASONS/UNQUALIFIED_REASONS directly — see that dict's
    changelog entry. Any stage present as a key in STAGE_REASON_LISTS
    requires a reason_code from its list plus non-empty reason_notes; a
    stage absent from the dict (everything except Lost/Unqualified today)
    requires neither, same as before.

    Returns (ok: bool, message: str). Never raises for an invalid
    transition, a stale-stage race, or a missing/invalid reason — all
    are just ok=False with a clear message the route can show the user.
    """
    if new_stage not in ALL_STAGES:
        return False, f"'{new_stage}' is not a recognised stage."

    reason_notes = (reason_notes or "").strip()
    reason_list = STAGE_REASON_LISTS.get(new_stage)
    if reason_list is not None:
        if reason_code not in reason_list:
            return False, f"A {new_stage} reason is required, one of: {', '.join(reason_list)}."
        if not reason_notes:
            return False, f"A short explanation note is required when marking a lead {new_stage}."

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT current_stage FROM leads WHERE cls_id=?", (cls_id,)
        ).fetchone()
        if not row:
            return False, "Lead not found."

        live_stage = row["current_stage"]
        allowed = STAGE_TRANSITIONS.get(live_stage, [])

        if new_stage not in allowed:
            return False, (
                f"This lead is currently at '{live_stage}', which has "
                f"since changed since you opened this page, or "
                f"'{live_stage}' -> '{new_stage}' isn't an allowed "
                f"transition. Refresh and try again."
            )

        now = _now()
        new_stage_reason = reason_code if new_stage in STAGE_REASON_LISTS else None
        conn.execute("""
            UPDATE leads SET current_stage=?, stage_reason=?, stage_updated_at=?, cls_updated_at=?
            WHERE cls_id=?
        """, (new_stage, new_stage_reason, now, now, cls_id))

        activity_description = f"Reason: {reason_code}. {reason_notes}" if new_stage_reason else None
        _log_activity(conn, cls_id, "stage_change", actor,
                      prev_value=live_stage, new_value=new_stage,
                      description=activity_description)

        cancelled_note = ""
        if new_stage in AUTO_CANCEL_ON_STAGES:
            _auto_cancel_open_schedules(conn, cls_id, new_stage, actor)
            cancelled_note = " Any open site visit/follow-up was auto-cancelled."

            row = conn.execute(
                "SELECT project_bucket FROM leads WHERE cls_id=?", (cls_id,)
            ).fetchone()
            if row and row["project_bucket"]:
                _auto_cross_reassign_project(conn, cls_id, row["project_bucket"], new_stage, actor)

        conn.commit()
        return True, f"Stage changed: {live_stage} → {new_stage}.{cancelled_note}"
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# PHASE B TELEPHONY — call-recording matching (v2.33)
# ─────────────────────────────────────────────────────────────
# Server-side half of the "dumb app, smart server" architecture: the
# Android app reports call-log metadata only (never files) to
# /api/telephony/report-calls; record_call_log_entry() normalizes and
# matches each number against existing leads using the SAME
# norm_phone()/find_match() already used by the Meta/Sell.do sync paths
# — no new normalization logic. Only matched numbers get a recording
# fetched and uploaded via /api/telephony/upload-recording, which calls
# log_call_recording(). See TELEPHONY_RECORDING_POLICY.md for the
# locked scope rule this enforces.

def get_recording_path(user_id):
    """Return this user's configured OEM recording-folder path, or None if unset."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT recording_folder_path FROM user_recording_paths WHERE user_id=?",
            (user_id,)
        ).fetchone()
        return row["recording_folder_path"] if row else None
    finally:
        conn.close()


def set_recording_path(user_id, path):
    """
    Save (or clear) a user's OEM recording-folder path. Admin-only —
    the caller (app.py's Settings > Telephony route) is responsible for
    the @admin_required gate; this function does no role check itself,
    matching every other writer function in this file. user_id is the
    table's primary key, so this is a plain INSERT OR REPLACE (same
    idiom as add_project_alias()/app_settings elsewhere in this file).
    """
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO user_recording_paths (user_id, recording_folder_path, updated_at) VALUES (?,?,?)",
            (user_id, path, _now())
        )
        conn.commit()
    finally:
        conn.close()


def generate_api_token(user_id):
    """
    Issue a new telephony API token for this user, deactivating any
    previous one (kept, not deleted, for audit — same "never discard"
    posture as everything else in this file). Returns the RAW token —
    this is the only time it's ever available; only its SHA-256 hash is
    stored. Caller (the Settings > Telephony route) must show it once
    and never log it.
    """
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE user_api_tokens SET active=0 WHERE user_id=? AND active=1",
            (user_id,)
        )
        conn.execute(
            "INSERT INTO user_api_tokens (user_id, token_hash, created_at, active) VALUES (?,?,?,1)",
            (user_id, token_hash, _now())
        )
        conn.commit()
        return raw_token
    finally:
        conn.close()


def verify_api_token(raw_token):
    """
    Look up an active telephony API token by its SHA-256 hash. Returns
    the associated (active) user dict, or None if the token is missing,
    inactive, or belongs to a deactivated user. Stamps last_used_at on
    every successful check. Entirely independent of the session-cookie
    login used by every other route in app.py.
    """
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT u.* FROM user_api_tokens t
            JOIN users u ON u.user_id = t.user_id
            WHERE t.token_hash=? AND t.active=1 AND u.active=1
        """, (token_hash,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE user_api_tokens SET last_used_at=? WHERE token_hash=?",
            (_now(), token_hash)
        )
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def revoke_api_token(user_id):
    """
    v2.47 — Admin "Revoke Token" kill-switch (Settings > Telephony),
    part of the Option C self-service token-sync redesign. Deactivates
    this user's current active token WITHOUT minting a replacement —
    there is deliberately no new raw value to show/relay here. The
    employee's next "Sync my token" tap in the app (POST /api/my-token,
    app.py) mints their own fresh one via the existing, unmodified
    generate_api_token(). Mirrors the "deactivate current active
    token" half of that function's logic as its own small function
    (a 2-line duplication) rather than refactoring generate_api_token()
    to share it, so that existing, already-working function is not
    touched at all.
    """
    conn = _connect()
    try:
        conn.execute(
            "UPDATE user_api_tokens SET active=0 WHERE user_id=? AND active=1",
            (user_id,)
        )
        conn.commit()
    finally:
        conn.close()


def diagnose_api_token_failure(raw_token):
    """
    v2.48 — diagnostic-only companion to verify_api_token(). Call this
    ONLY after verify_api_token() has already returned None, to find
    out WHY for logging purposes. Never grants access, never returns
    the raw token or its hash — only a short human-readable reason.
    Distinguishes "superseded" (a newer active token already exists
    for this user) from "revoked, no replacement yet" (an admin hit
    Revoke Token and nothing new was minted) — see v2.48 changelog.
    """
    if not raw_token:
        return "empty token after Bearer prefix"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT t.active AS token_active, u.active AS user_active, u.user_id AS user_id
            FROM user_api_tokens t
            JOIN users u ON u.user_id = t.user_id
            WHERE t.token_hash=?
        """, (token_hash,)).fetchone()
        if not row:
            return "no matching token row"
        if not row["user_active"]:
            return f"user_id={row['user_id']} deactivated"
        if not row["token_active"]:
            current = conn.execute(
                "SELECT 1 FROM user_api_tokens WHERE user_id=? AND active=1",
                (row["user_id"],)
            ).fetchone()
            if current:
                return (f"token superseded by a newer active token "
                        f"(user_id={row['user_id']}) — device may be using a stale synced value")
            return (f"token revoked, no replacement yet "
                    f"(user_id={row['user_id']}) — needs to tap Sync my token in the app")
        return "unknown (verify_api_token failed for an unrecognized reason)"
    finally:
        conn.close()


def record_call_log_entry(user_id, raw_phone, call_timestamp, duration_seconds, direction):
    """
    Normalize + match one call-log entry reported by the app, and log
    it to call_log_staging regardless of outcome — this table is what
    proves the "no scan without a lead match" policy is being followed.
    Unmatched numbers are NEVER persisted anywhere else in the system.

    Returns a dict: {"matched": bool, "cls_id": str|None,
    "call_timestamp": ..., "duration_seconds": ...} for the route to
    build its response from.
    """
    phone_norm = norm_phone(raw_phone)
    conn = _connect()
    try:
        cls_id, _tier = find_match(conn, phone_norm, "") if phone_norm else (None, "unmatched")
        match_status = "matched" if cls_id else "no_lead_match"
        conn.execute("""
            INSERT INTO call_log_staging (
                user_id, raw_phone, phone_norm, call_timestamp,
                duration_seconds, direction, matched_cls_id,
                match_status, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
        """, (user_id, raw_phone, phone_norm, call_timestamp,
              duration_seconds, direction, cls_id, match_status, _now()))
        conn.commit()
        return {
            "matched": bool(cls_id),
            "cls_id": cls_id,
            "call_timestamp": call_timestamp,
            "duration_seconds": duration_seconds,
        }
    finally:
        conn.close()


def record_call_log_entries_batch(user_id, calls):
    """
    (v2.84) Batch counterpart to record_call_log_entry() above — SAME
    normalize+match+insert logic (norm_phone()/find_match() reused
    unchanged, no new matching logic), but on ONE open connection for
    the whole batch, committing once at the end instead of once per
    entry. Added to fix a client-side timeout on
    /api/telephony/report-calls for large call-log backlogs (confirmed
    on Elohar's device — vivo V2141): a 30+ call batch, each opening
    and committing its own SQLite connection via record_call_log_entry(),
    pushed total server response time past OkHttp's client-side
    timeout, so the app reported "report-calls failed: timeout" even
    though the server eventually finished writing.

    `calls` is a list of dicts with keys number/timestamp/duration/
    direction — the same shape app.py already parses from the request
    body. Returns a list of per-entry result dicts in the SAME shape
    record_call_log_entry() returns (matched/cls_id/call_timestamp/
    duration_seconds), in the same order as the input list, so the
    route's existing response-building loop only needs to change which
    function it calls, not its own logic.

    record_call_log_entry() itself is untouched — this is a pure
    addition, not a replacement.
    """
    results = []
    conn = _connect()
    try:
        for entry in calls:
            raw_phone = entry["number"]
            call_timestamp = entry["timestamp"]
            duration_seconds = entry["duration"]
            direction = entry["direction"]
            phone_norm = norm_phone(raw_phone)
            cls_id, _tier = find_match(conn, phone_norm, "") if phone_norm else (None, "unmatched")
            match_status = "matched" if cls_id else "no_lead_match"
            conn.execute("""
                INSERT INTO call_log_staging (
                    user_id, raw_phone, phone_norm, call_timestamp,
                    duration_seconds, direction, matched_cls_id,
                    match_status, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, (user_id, raw_phone, phone_norm, call_timestamp,
                  duration_seconds, direction, cls_id, match_status, _now()))
            results.append({
                "matched": bool(cls_id),
                "cls_id": cls_id,
                "call_timestamp": call_timestamp,
                "duration_seconds": duration_seconds,
            })
        conn.commit()
        return results
    finally:
        conn.close()


def get_call_recording_file_path(cls_id, call_timestamp):
    """
    (v2.35) Returns the recording_file_path already logged for this exact
    (cls_id, call_timestamp), or None if no call_recording row exists yet.

    Supersedes v2.34's call_recording_exists() (a plain boolean), which
    turned out to be the wrong check on its own: a caller needs to know
    not just THAT a row exists but WHAT file it points to, so it can
    check whether that file is still actually on disk before deciding a
    re-upload is a genuine duplicate versus a legitimate recovery of a
    file that went missing (confirmed real: recordings were accidentally
    deleted from disk on 2026-07-31 while their activity_log rows
    survived — a same-row-exists-only check would have permanently
    blocked recovering them via re-sync).
    """
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT recording_file_path FROM activity_log
            WHERE cls_id=? AND activity_type='call_recording' AND created_at=?
            LIMIT 1
        """, (cls_id, call_timestamp)).fetchone()
        return row["recording_file_path"] if row else None
    finally:
        conn.close()


def update_call_recording_file(cls_id, call_timestamp, file_path, duration_seconds, matched_phone):
    """
    (v2.35) Updates recording_file_path/duration_seconds/matched_phone on
    an EXISTING call_recording activity_log row for this exact (cls_id,
    call_timestamp) — used only when that row's previously-logged file
    has gone missing from disk and the app is re-uploading it. Does NOT
    insert a new row (that would recreate the exact duplicate-row problem
    the v2.34 dedupe check was fixing) and does not touch created_at
    (still the real call time) or actor. Returns (ok: bool, message: str).
    """
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT activity_id FROM activity_log
            WHERE cls_id=? AND activity_type='call_recording' AND created_at=?
            LIMIT 1
        """, (cls_id, call_timestamp)).fetchone()
        if not row:
            return False, "No existing call_recording row found to update."
        conn.execute("""
            UPDATE activity_log
            SET recording_file_path=?, duration_seconds=?, matched_phone=?
            WHERE activity_id=?
        """, (file_path, duration_seconds, matched_phone, row["activity_id"]))
        conn.commit()
        return True, "Recovered missing recording file for existing activity_log row."
    finally:
        conn.close()


def log_call_recording(cls_id, actor, file_path, duration_seconds, matched_phone, call_timestamp, direction=None):
    """
    Log an uploaded call recording to a lead's activity timeline.
    created_at is backdated to call_timestamp (the real call time, via
    _log_activity's v2.28 created_at param) rather than upload time —
    same convention as upsert_meta_lead()'s lead_entered row.

    v2.49: optional direction param ('INCOMING'/'OUTGOING'/... as
    captured by the app and staged in call_log_staging), None by
    default so this stays backwards-compatible with any caller that
    doesn't have it. app.py's api_telephony_upload_recording() looks
    it up via get_call_direction() and passes it through.

    Returns (ok: bool, message: str), same convention as add_note()/
    change_lead_stage().
    """
    conn = _connect()
    try:
        row = conn.execute("SELECT cls_id FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."
        _log_activity(
            conn, cls_id, "call_recording", actor,
            created_at=call_timestamp,
            recording_file_path=file_path,
            duration_seconds=duration_seconds,
            matched_phone=matched_phone,
            direction=direction,
        )
        conn.commit()
        return True, "Call recording logged."
    finally:
        conn.close()


def get_call_direction(cls_id, call_timestamp):
    """
    (v2.49) Looks up the call direction ('INCOMING'/'OUTGOING'/... as
    reported by the app) for one call, matched by the SAME key
    record_call_log_entry() staged it under: matched_cls_id +
    call_timestamp. Used only by api_telephony_upload_recording() to
    carry direction from call_log_staging (already captured there since
    v2.33) through to the activity_log.call_recording row that
    log_call_recording() creates — direction was captured all along but
    previously dropped at this exact handoff.

    Returns None if no matching staging row exists (or it has no
    direction) — the caller never blocks the upload on this, it just
    logs the recording with direction=None, same as any historical row.
    """
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT direction FROM call_log_staging
            WHERE matched_cls_id=? AND call_timestamp=?
            ORDER BY staging_id DESC LIMIT 1
        """, (cls_id, call_timestamp)).fetchone()
        return row["direction"] if row and row["direction"] else None
    finally:
        conn.close()


def get_call_staging_rows(user_id, date_str):
    """
    (v2.71) Read-only, for cls_call_recording_diagnostic.py v1.1's staging-
    vs-recording cross-check — one DISTINCT row per real physical call a
    salesperson made/received on date_str, with lead name and recording
    status already resolved, so the caller never has to touch SQL itself
    (centralization rule — see CLAUDE.md).

    DISTINCT-deduped by (matched_cls_id, call_timestamp, duration_seconds,
    direction) — NOT a plain SELECT of every call_log_staging row. Found
    during this function's own build/test session: the Android app's
    periodic re-sync re-stages already-seen calls on every run, inserting
    an exact duplicate call_log_staging row each time (same everything
    except staging_id/created_at — record_call_log_entry() always inserts,
    never dedupes on the way in, per its own docstring). A naive COUNT(*)
    against this table overstated real call volume by several multiples
    on live data (e.g. one real user/day: 534 raw rows, 72 distinct real
    calls) — confirmed harmless to dedupe this way because, across every
    such duplicate group checked on live data, matched_cls_id and
    match_status were IDENTICAL within the group (zero counterexamples
    found) — i.e. dedup never discards a genuine match/status disagreement,
    only genuine re-sync duplicates of the same physical call.

    has_recording is resolved via the SAME join key get_call_direction()
    above uses: matched_cls_id = activity_log.cls_id AND call_timestamp =
    activity_log.created_at (log_call_recording() backdates created_at to
    the real call_timestamp) AND activity_type='call_recording'. No actor
    filter — same precedent as get_call_direction().

    Returns a list of dicts: matched_cls_id, call_timestamp,
    duration_seconds, direction, full_name (lead name, or None if
    unmatched/lead since deleted), has_recording (bool).
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT d.matched_cls_id, d.call_timestamp, d.duration_seconds, d.direction,
                   l.full_name,
                   CASE WHEN a.activity_id IS NOT NULL THEN 1 ELSE 0 END AS has_recording
            FROM (
                SELECT DISTINCT matched_cls_id, call_timestamp, duration_seconds, direction
                FROM call_log_staging
                WHERE user_id = ? AND substr(call_timestamp, 1, 10) = ?
            ) d
            LEFT JOIN leads l ON l.cls_id = d.matched_cls_id
            LEFT JOIN activity_log a
                ON a.cls_id = d.matched_cls_id
                AND a.created_at = d.call_timestamp
                AND a.activity_type = 'call_recording'
            ORDER BY d.call_timestamp
        """, (user_id, date_str)).fetchall()
        return [
            {
                "matched_cls_id": r["matched_cls_id"],
                "call_timestamp": r["call_timestamp"],
                "duration_seconds": r["duration_seconds"] or 0,
                "direction": r["direction"],
                "full_name": r["full_name"],
                "has_recording": bool(r["has_recording"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_todays_call_stats(owner_scope=None):
    """(v2.88) Deduped counts from call_log_staging for today, same
    DISTINCT-on-(user_id, matched_cls_id, call_timestamp,
    duration_seconds, direction) dedup get_call_staging_rows() (v2.71)
    uses, avoiding the known re-sync duplicate-inflation bug.

    owner_scope: a user_id to scope to one salesperson, or None for
    company-wide. 'Answered' = duration_seconds > 0.

    Returns: {outgoing_attempted, outgoing_answered,
    incoming_answered, total_synced}."""
    conn = _connect()
    try:
        today = _now()[:10]
        query = """
            SELECT DISTINCT user_id, matched_cls_id, call_timestamp,
                   duration_seconds, direction
            FROM call_log_staging
            WHERE substr(call_timestamp, 1, 10) = ?
        """
        params = [today]
        if owner_scope:
            query += " AND user_id = ?"
            params.append(owner_scope)
        rows = conn.execute(query, params).fetchall()

        outgoing_attempted = sum(1 for r in rows if r["direction"] == "OUTGOING")
        outgoing_answered = sum(1 for r in rows if r["direction"] == "OUTGOING" and (r["duration_seconds"] or 0) > 0)
        incoming_answered = sum(1 for r in rows if r["direction"] == "INCOMING" and (r["duration_seconds"] or 0) > 0)
        return {
            "outgoing_attempted": outgoing_attempted,
            "outgoing_answered": outgoing_answered,
            "incoming_answered": incoming_answered,
            "total_synced": len(rows),
        }
    finally:
        conn.close()


def list_call_recording_activities():
    """
    (v2.34) Read-only audit list of every activity_log row of type
    'call_recording', newest first, joined to the lead's name/phone for
    human review. Built for cls_call_recording_audit.py after a confirmed
    privacy incident (a personal call's recording was wrongly attached to
    a lead) — surfaces every such row so Srikanth can review and choose
    which to delete via delete_call_recording_activity(), never auto.
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT a.activity_id, a.cls_id, a.actor, a.created_at,
                   a.recording_file_path, a.duration_seconds, a.matched_phone,
                   l.full_name, l.phone_norm, l.lead_owner
            FROM activity_log a
            LEFT JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type = 'call_recording'
            ORDER BY a.activity_id DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_call_recording_activity(activity_id):
    """
    (v2.34) Deletes ONE activity_log row by activity_id, scoped to
    activity_type='call_recording' only (refuses to touch any other
    activity type even if called with a mismatched id, so this can never
    be repurposed into a general-purpose activity_log deleter). This is a
    deliberate, human-reviewed exception to activity_log's normal
    append-only posture — used only for privacy remediation (a wrongly-
    matched recording), never as a general editing capability. Returns
    (ok: bool, message: str).
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT activity_id FROM activity_log WHERE activity_id=? AND activity_type='call_recording'",
            (activity_id,)
        ).fetchone()
        if not row:
            return False, "No call_recording activity found with that id."
        conn.execute(
            "DELETE FROM activity_log WHERE activity_id=? AND activity_type='call_recording'",
            (activity_id,)
        )
        conn.commit()
        return True, f"Deleted call_recording activity_id={activity_id}."
    finally:
        conn.close()


def list_call_recordings(date_from=None, date_to=None, call_status=None,
                          lead_owner=None, activity_owner=None, search=None,
                          page=1, per_page=25):
    """
    (v2.36) Filtered, paginated list of call_recording activity_log rows
    for the admin "Synced Recordings" page — the same underlying rows
    list_call_recording_activities() (v2.34) shows unfiltered for CLI
    audit use, but with real filters and pagination for a web table.

    WHERE-clause style follows get_call_activity()'s ad-hoc inline
    convention (few filters, not worth the extracted-helper pattern
    _build_lead_filter_where() uses for /leads' much larger filter set).
    Pagination follows get_leads_page()'s exact shape/style: fetch all
    matching rows, slice in Python (no SQL LIMIT/OFFSET), page clamped
    into [1, total_pages].

    call_status: 'answered' (duration_seconds > 0), 'missed' (== 0), or
    None/other (no filter). activity_owner is an email (activity_log.
    actor) — same value type callers get from cls_db.get_all_users_
    detailed(); lead_owner is free-text matching leads.lead_owner, same
    as everywhere else in this file. Does NOT resolve actor/lead_owner
    to display names itself — that's the route's job via get_all_users(),
    matching how every existing consumer of activity_log.actor works.

    Returns {"rows", "total", "page", "per_page", "total_pages"}.
    """
    conn = _connect()
    try:
        query = """
            SELECT a.activity_id, a.cls_id, a.actor, a.created_at,
                   a.recording_file_path, a.duration_seconds, a.matched_phone,
                   l.full_name, l.lead_owner, l.crm_lead_no
            FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type = 'call_recording'
        """
        params = []
        if date_from and date_to:
            query += " AND substr(a.created_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        if call_status == "answered":
            query += " AND a.duration_seconds > 0"
        elif call_status == "missed":
            query += " AND a.duration_seconds = 0"
        if lead_owner:
            query += " AND l.lead_owner = ?"
            params.append(lead_owner)
        if activity_owner:
            query += " AND a.actor = ?"
            params.append(activity_owner)
        if search:
            query += " AND l.full_name LIKE ?"
            params.append(f"%{search}%")
        query += " ORDER BY a.created_at DESC"

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

        total = len(rows)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        page_rows = rows[start:start + per_page]

        return {
            "rows": page_rows,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }
    finally:
        conn.close()


def add_note(cls_id, actor, text):
    """
    Log a free-text note against a lead. Pure activity_log entry —
    does not touch the leads table itself.

    Returns (ok: bool, message: str).
    """
    text = (text or "").strip()
    if not text:
        return False, "Note can't be empty."

    conn = _connect()
    try:
        row = conn.execute("SELECT cls_id FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."
        _log_activity(conn, cls_id, "note", actor, description=text)
        conn.commit()
        return True, "Note added."
    finally:
        conn.close()


def reassign_lead_owner(cls_id, new_owner, actor, conn=None):
    """
    Change a lead's owner (leads.lead_owner) from the CRM. Same
    overwrite-on-next-Sell.do-sync dynamic as update_lead_stage above,
    and for the same reason: Job B is left completely untouched, and a
    forgotten Sell.do update simply reverts on the next sync — an
    intentional, code-free signal during the parallel-run period.

    v2.3: also sets owner_notified=0, flagging this lead as a fresh,
    unseen reassignment for the NEW owner — see
    get_unread_assignment_count() / mark_lead_notification_read()
    below, which power the login badge.

    v2.28: optional conn param. Omitted (every pre-existing caller,
    e.g. the single-lead /leads/<cls_id>/assign route) — behaves
    exactly as before: opens its own connection, commits, closes it.
    Passed an OPEN connection — reuses it and does NOT commit or close;
    the caller owns the transaction. See bulk_reassign_leads() below,
    the only caller that uses this.

    v2.72 (Notifications v1.0): also inserts a 'lead_reassigned'
    notification for the new owner, right where owner_notified=0 is
    set above it — ADDITIVE, owner_notified/mark_lead_notification_read()/
    get_unread_assignment_count() are completely untouched. Uses
    insert_notification(conn=conn) so it lands in the SAME transaction
    on both the single-lead route (owns_conn=True, commits immediately
    after) and bulk_reassign_leads()'s loop (owns_conn=False, commits
    once at the end) — a bulk reassign of N leads either notifies all N
    new owners or none, same all-or-nothing guarantee the rest of this
    function already has.
    send_fcm_push() (the actual network call) is deliberately fired
    ONLY when owns_conn is True — i.e. only from the single-lead route,
    never from inside bulk_reassign_leads()'s loop. A bulk reassignment
    can touch hundreds of leads in one open SQLite transaction; doing a
    blocking HTTP push per lead inside that loop would serialize the
    whole bulk operation on network latency and hold the transaction
    open for its duration. The in-app bell notification (inserted
    above, cheap) still reaches every reassigned owner in both cases —
    only the push is scoped down.

    Returns (ok: bool, message: str).
    """
    new_owner = (new_owner or "").strip()
    if not new_owner:
        return False, "Owner name can't be empty."

    owns_conn = conn is None
    if owns_conn:
        conn = _connect()
    try:
        row = conn.execute("SELECT lead_owner, full_name FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."

        prev_owner = row["lead_owner"]
        full_name = row["full_name"]
        now = _now()
        conn.execute(
            "UPDATE leads SET lead_owner=?, cls_updated_at=?, owner_notified=0 WHERE cls_id=?",
            (new_owner, now, cls_id)
        )
        _log_activity(conn, cls_id, "assignment_change", actor,
                      prev_value=prev_owner, new_value=new_owner)

        new_owner_user_id = resolve_user_id_from_owner_name(new_owner)
        if new_owner_user_id:
            message = NOTIFICATION_EVENTS["lead_reassigned"].format(full_name=full_name or "(no name)")
            insert_notification(new_owner_user_id, cls_id, "lead_reassigned", message, conn=conn)
            if owns_conn:
                send_fcm_push(new_owner_user_id, "Lead reassigned", message)

        if owns_conn:
            conn.commit()
        return True, f"Reassigned: {prev_owner or '(unassigned)'} → {new_owner}."
    finally:
        if owns_conn:
            conn.close()


def bulk_reassign_leads(cls_ids, new_owner, actor):
    """
    (v2.28) Task 3 — reassigns every lead in cls_ids to new_owner, ALL
    in one transaction (either every lead reassigns and every
    activity_log row lands, or none do — a mid-loop failure can't leave
    a bulk-reassign half-applied). This is the whole reason
    reassign_lead_owner() gained its conn= param above: this function
    is the ONE caller that opens a connection and hands it in, keeping
    "all SQLite access stays in cls_db.py" true even for bulk actions —
    app.py's route never sees a raw connection.

    Returns the number of leads actually reassigned. A cls_id that no
    longer exists (deleted between the preview screen and confirming)
    is silently skipped, not an error — the count reflects reality.
    """
    conn = _connect()
    try:
        count = 0
        for cls_id in cls_ids:
            ok, _ = reassign_lead_owner(cls_id, new_owner, actor, conn=conn)
            if ok:
                count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def mark_lead_notification_read(cls_id):
    """
    Clears the "you were just assigned this lead" badge (v2.3) — call
    this when the current owner opens this lead's detail page. Silent
    no-op if the lead doesn't exist or was already acknowledged; never
    raises, since this is a best-effort UI nicety, not a critical write.
    """
    conn = _connect()
    try:
        conn.execute("UPDATE leads SET owner_notified=1 WHERE cls_id=?", (cls_id,))
        conn.commit()
    finally:
        conn.close()


def record_bulk_job_leads(job_id, cls_ids, conn=None):
    """
    (v2.53) Phase 5 — snapshots the exact cls_ids a bulk job touched,
    into bulk_job_leads(job_id, cls_id). This is what lets "Past Bulk
    Jobs" offer a reliable per-job "download affected leads" export
    regardless of what happens to those leads afterward (reassigned
    again, stage-changed, even deleted) — the snapshot is independent of
    current lead state.

    conn (optional, same reuse pattern as reassign_lead_owner() above):
    omitted, opens its own connection and commits/closes it. Passed an
    OPEN connection (create_bulk_job() does this — see below), reuses it
    and does NOT commit or close; the caller owns the transaction, so
    the job row and its snapshot land atomically together.

    INSERT OR IGNORE on the (job_id, cls_id) primary key — a duplicate
    cls_id in the input list (shouldn't happen, but matched_ids is
    caller-built) is silently deduped rather than erroring.
    """
    owns_conn = conn is None
    if owns_conn:
        conn = _connect()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO bulk_job_leads (job_id, cls_id) VALUES (?, ?)",
            [(job_id, cls_id) for cls_id in cls_ids]
        )
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


def create_bulk_job(job_type, actor, filters_summary, to_owner, lead_count, cls_ids=None, conn=None):
    """
    (v2.28) Writes one row to bulk_jobs — called once per bulk-action
    run, after the action itself has committed. job_type is validated
    against BULK_JOB_TYPES (raises ValueError otherwise, same fail-loud
    posture as create_manual_lead()'s validation) rather than accepting
    an ad-hoc string. filters_summary is a short human-readable string
    the CALLER builds (e.g. "Project: Naishka, Stage: Prospect →
    reassigned to Devender Goud") — this function stores it as-is, no
    JSON encoding/decoding.

    (v2.53) Phase 5 — two additions, both backward compatible with every
    existing caller (none of which passed these or used the return value):
      cls_ids (optional, list) — when given, this function ALSO snapshots
      those cls_ids into bulk_job_leads via record_bulk_job_leads(),
      reusing the SAME connection/transaction as the bulk_jobs INSERT
      below, so a job row can never exist without its snapshot (or vice
      versa) — the two either both commit or neither does. job_id only
      exists once this INSERT runs, so this is the only place that
      pairing can happen; app.py itself never holds a raw connection
      (see cls_db.py's "all SQLite access stays centralized here" rule),
      so this couldn't be split across two separate top-level calls
      from the route without losing that atomicity.
      conn (optional) — same reuse pattern as reassign_lead_owner().
      Omitted (every existing caller): opens its own connection, commits,
      closes it, exactly as before.

    Returns the new job_id (previously returned nothing — every existing
    caller already ignored the return value, so this is additive).
    """
    if job_type not in BULK_JOB_TYPES:
        raise ValueError(f"job_type must be one of: {', '.join(BULK_JOB_TYPES)}")

    owns_conn = conn is None
    if owns_conn:
        conn = _connect()
    try:
        cur = conn.execute("""
            INSERT INTO bulk_jobs (job_type, actor, filters_summary, to_owner, lead_count, created_at)
            VALUES (?,?,?,?,?,?)
        """, (job_type, actor, filters_summary, to_owner, lead_count, _now()))
        job_id = cur.lastrowid
        if cls_ids:
            record_bulk_job_leads(job_id, cls_ids, conn=conn)
        if owns_conn:
            conn.commit()
        return job_id
    finally:
        if owns_conn:
            conn.close()


def get_bulk_jobs():
    """
    (v2.28) Every bulk_jobs row, newest first — feeds the Settings >
    Bulk Jobs history page.

    (v2.53) Phase 5 — each row now also carries leads_snapshot_count
    (COUNT of its bulk_job_leads rows, via LEFT JOIN so a pre-migration
    job with zero snapshot rows still returns 0, not an excluded row).
    Lets the template distinguish "has an exportable snapshot" from
    "predates the bulk_job_leads migration, nothing to export" without a
    second per-row query. Existing columns/behavior unchanged.
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT j.*, COUNT(b.cls_id) AS leads_snapshot_count
            FROM bulk_jobs j LEFT JOIN bulk_job_leads b ON b.job_id = j.job_id
            GROUP BY j.job_id
            ORDER BY j.created_at DESC, j.job_id DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_bulk_job_lead_rows(job_id):
    """
    (v2.53) Phase 5 — leads to export for one bulk_jobs row, resolved
    from the bulk_job_leads SNAPSHOT (job_id, cls_id), not the leads'
    current owner/stage — that's the whole point of the snapshot: it
    stays a faithful "who did this job touch" record even after those
    leads are reassigned again, stage-changed, or deleted. INNER JOIN
    means a lead deleted since the job ran simply doesn't appear in the
    export (nothing to show for it), not a crash or a blank row.

    Same base column set as get_leads_matching()'s SELECT (crm_lead_no,
    full_name, phone_raw, project_bucket, current_stage, lead_owner,
    source, cls_created_at) so app.py's existing LEADS_EXPORT_COLUMNS
    can be reused as-is for this export — no new column mapping needed.

    Returns a plain list of row dicts, sorted by full_name.

    (v2.67, F2 Phase 3) project_bucket is now SELECTed directly from the
    stored, kept-in-sync leads.project_bucket column instead of being
    recomputed per row via get_project_bucket() after the fetch.
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT l.cls_id, l.full_name, l.phone_raw, l.project,
                   l.project_bucket, l.current_stage, l.lead_owner,
                   l.source, l.cls_created_at, l.crm_lead_no
            FROM bulk_job_leads b JOIN leads l ON l.cls_id = b.cls_id
            WHERE b.job_id = ?
            ORDER BY l.full_name COLLATE NOCASE ASC
        """, (job_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_unread_assignment_count(owner_match_name):
    """
    Count of leads currently owned by owner_match_name that still have
    a pending (unread) reassignment badge (v2.3) — feeds the login/
    dashboard badge. Returns 0 for a blank/None owner_match_name
    (unlinked accounts — same "no owner match yet" handling used
    elsewhere) rather than erroring.
    """
    owner_match_name = (owner_match_name or "").strip()
    if not owner_match_name:
        return 0
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE lead_owner=? AND owner_notified=0",
            (owner_match_name,)
        ).fetchone()
        return row["c"]
    finally:
        conn.close()


def schedule_site_visit(cls_id, scheduled_at, actor, notes=""):
    """
    Schedule a site visit for a lead. scheduled_at is a string in
    'YYYY-MM-DD HH:MM' format (matches _now()'s format so date
    comparisons in get_due_today() are simple string comparisons).

    v1.9 — only one OPEN (status='scheduled') site visit is allowed
    per lead at a time. Close the existing one (any outcome) before
    scheduling a new one. Rescheduling (see update_site_visit) does
    NOT count as a new one — it updates the same open row.

    Returns (ok: bool, message: str).
    """
    if not scheduled_at:
        return False, "Scheduled date/time is required."

    conn = _connect()
    try:
        row = conn.execute("SELECT cls_id FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."

        existing_open = conn.execute(
            "SELECT visit_id FROM site_visits WHERE cls_id=? AND status='scheduled'",
            (cls_id,)
        ).fetchone()
        if existing_open:
            return False, ("This lead already has an open site visit scheduled. "
                            "Close it (Conducted / Rescheduled / Cancelled / Didn't Visit) "
                            "before scheduling a new one.")

        now = _now()
        conn.execute("""
            INSERT INTO site_visits (
                cls_id, scheduled_at, status, created_by, notes, created_at
            ) VALUES (?,?,?,?,?,?)
        """, (cls_id, scheduled_at, "scheduled", actor, notes or "", now))
        _log_activity(conn, cls_id, "site_visit_scheduled", actor,
                      new_value=scheduled_at, description=notes or None)
        conn.commit()
        return True, "Site visit scheduled."
    finally:
        conn.close()


SITE_VISIT_OUTCOMES = {
    # action -> (new_status, closes_the_slot, activity_type)
    "conducted":  ("conducted", True,  "site_visit_conducted"),
    "rescheduled": ("scheduled", False, "site_visit_rescheduled"),  # stays open, same slot
    "cancelled":  ("cancelled", True,  "site_visit_cancelled"),
    "no_show":    ("no_show",   True,  "site_visit_no_show"),
}


def update_site_visit(visit_id, action, actor, reason, new_scheduled_at=None):
    """
    Record an outcome for a scheduled site visit (v1.9). action must be
    one of SITE_VISIT_OUTCOMES' keys: conducted / rescheduled /
    cancelled / no_show. A reason is REQUIRED for every action —
    including a successful "conducted" (what did the visit reveal?).

    "rescheduled" does NOT close the item — it updates THIS SAME row's
    scheduled_at to new_scheduled_at and leaves status='scheduled', so
    it still occupies the lead's one allowed open slot (see
    schedule_site_visit's one-open-at-a-time rule) rather than freeing
    it up for an unrelated second visit to be scheduled alongside it.
    Every other action closes the item and frees that slot.

    v2.69 — a genuine reschedule (new_scheduled_at actually different
    from the row's previous scheduled_at) also resets
    reminder_sent_at back to NULL, in the same transaction as the
    scheduled_at UPDATE. FIXES A PRE-EXISTING BUG: before this, a
    reminder sent for a visit's original date incorrectly kept showing
    as "sent" after the visit was rescheduled to a new date, even
    though nobody had reminded the lead about the new date. A reschedule
    "to the same time" (new_scheduled_at == previous scheduled_at) is
    treated as a no-op and does not reset — this should never happen in
    practice via the UI, but is checked for literally rather than
    assumed impossible.

    Returns (ok: bool, message: str).
    """
    if action not in SITE_VISIT_OUTCOMES:
        return False, f"'{action}' is not a recognised outcome."
    reason = (reason or "").strip()
    if not reason:
        return False, "A reason is required."
    if action == "rescheduled" and not new_scheduled_at:
        return False, "New date/time is required when rescheduling."

    new_status, closes, activity_type = SITE_VISIT_OUTCOMES[action]

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT cls_id, scheduled_at, status FROM site_visits WHERE visit_id=?",
            (visit_id,)
        ).fetchone()
        if not row:
            return False, "Site visit not found."
        if row["status"] != "scheduled":
            return False, "This site visit has already been closed."

        now = _now()
        if action == "rescheduled":
            conn.execute("""
                UPDATE site_visits SET scheduled_at=?, outcome_reason=? WHERE visit_id=?
            """, (new_scheduled_at, reason, visit_id))
            if new_scheduled_at != row["scheduled_at"]:
                # v2.69 — genuine reschedule (not a same-time no-op): the
                # old reminder, if any, was for the OLD date and is no
                # longer valid for the new one. See docstring above and
                # the v2.69 changelog entry at top of file.
                conn.execute(
                    "UPDATE site_visits SET reminder_sent_at=NULL WHERE visit_id=?",
                    (visit_id,)
                )
            _log_activity(conn, row["cls_id"], activity_type, actor,
                          prev_value=row["scheduled_at"], new_value=new_scheduled_at,
                          description=reason)
        else:
            conn.execute("""
                UPDATE site_visits SET status=?, conducted_at=?, outcome_reason=? WHERE visit_id=?
            """, (new_status, now, reason, visit_id))
            _log_activity(conn, row["cls_id"], activity_type, actor, description=reason)
        conn.commit()
        return True, f"Site visit marked {action}."
    finally:
        conn.close()


def log_walkin_site_visit(cls_id, project, conducted_at, actor, notes=""):
    """
    (v2.8) Log a WALK-IN site visit — a lead who already exists and is
    in touch, but showed up at the project without a prior scheduled
    visit (so schedule_site_visit()/update_site_visit()'s "conducted"
    flow doesn't fit — there's no open 'scheduled' row to close).

    Inserts a site_visits row that is ALREADY status='conducted' —
    scheduled_at and conducted_at are both set to conducted_at (there
    was no separate schedule time), so it never occupies the lead's
    one-open-slot rule and doesn't collide with a real open scheduled
    visit if one happens to exist.

    Logs activity_log activity_type='site_visit_conducted' — the SAME
    activity_type schedule_site_visit's "conducted" outcome uses — so
    this walk-in is counted identically everywhere that already reads
    that activity_type: get_todays_activity_counts()'s
    site_visits_conducted tile, compute_lead_scores()'s scoring rule,
    and the lead-page Activity History feed. No new counter needed;
    the count is live-derived from activity_log, same as every other
    metric in this file.

    conducted_at is a 'YYYY-MM-DD HH:MM' string, same format as every
    other scheduled_at/conducted_at value in this file.

    Returns (ok: bool, message: str).
    """
    if not conducted_at:
        return False, "Conducted date/time is required."
    project = (project or "").strip()
    if not project:
        return False, "Project is required."

    conn = _connect()
    try:
        row = conn.execute("SELECT cls_id FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."

        now = _now()
        conn.execute("""
            INSERT INTO site_visits (
                cls_id, scheduled_at, conducted_at, status, created_by,
                notes, outcome_reason, project, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
        """, (cls_id, conducted_at, conducted_at, "conducted", actor,
              "Walk-in — no prior scheduling", notes or "", project, now))
        _log_activity(conn, cls_id, "site_visit_conducted", actor,
                      new_value=conducted_at,
                      description=f"Walk-in visit — {project}" + (f": {notes}" if notes else ""))
        conn.commit()
        return True, "Site visit conducted logged."
    finally:
        conn.close()


def log_sitting_done(cls_id, actor, notes=""):
    """
    (v2.70, Task 4 item 3) Log a "sitting" — an in-office negotiation/
    paperwork session with a lead — as an activity_log-only event, same
    convention as call_attempted/note: no new table, no status to
    manage, just a timestamped row. Mirrors log_walkin_site_visit()'s
    lead-exists-check shape above, but simpler — there's no site_visits
    row to insert, since a sitting isn't a visit.

    Logs activity_type='sitting_done'. Picked up automatically by
    get_todays_activity_counts()'s METRIC_MAP (new sittings_done key) —
    no separate counting infrastructure needed, same mechanism
    site_visit_conducted already uses for Today's Performance and the
    Daily Scorecard report.

    Returns (ok: bool, message: str).
    """
    conn = _connect()
    try:
        row = conn.execute("SELECT cls_id FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."

        _log_activity(conn, cls_id, "sitting_done", actor, description=notes or "")
        conn.commit()
        return True, "Sitting done logged."
    finally:
        conn.close()


def schedule_follow_up(cls_id, scheduled_at, actor, notes=""):
    """
    Schedule a follow-up for a lead. Same shape/format as
    schedule_site_visit above, including the v1.9 one-open-at-a-time
    rule. Returns (ok: bool, message: str).
    """
    if not scheduled_at:
        return False, "Scheduled date/time is required."

    conn = _connect()
    try:
        row = conn.execute("SELECT cls_id FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."

        existing_open = conn.execute(
            "SELECT followup_id FROM follow_ups WHERE cls_id=? AND status='scheduled'",
            (cls_id,)
        ).fetchone()
        if existing_open:
            return False, ("This lead already has an open follow-up scheduled. "
                            "Close it (Completed / Cancelled / Postponed) before "
                            "scheduling a new one.")

        now = _now()
        conn.execute("""
            INSERT INTO follow_ups (
                cls_id, scheduled_at, status, created_by, notes, created_at
            ) VALUES (?,?,?,?,?,?)
        """, (cls_id, scheduled_at, "scheduled", actor, notes or "", now))
        _log_activity(conn, cls_id, "follow_up_scheduled", actor,
                      new_value=scheduled_at, description=notes or None)
        conn.commit()
        return True, "Follow-up scheduled."
    finally:
        conn.close()


def get_followups_count_for_day(date_str, owner=None):
    """
    (v2.70, Task 4 item 5) How many follow-ups are scheduled for one
    given day — feeds app.py's post-schedule flash message ("You have
    N follow-up(s) due on <date>") so a salesperson sees their day's
    load right after scheduling one, without a separate page visit.

    date_str is 'YYYY-MM-DD'. Counts follow_ups rows where
    substr(scheduled_at, 1, 10) = date_str AND status = 'scheduled' —
    same date-truncation and status-scoping convention used throughout
    this file (e.g. get_todays_activity_counts()'s substr(created_at,1,10)
    above).

    owner: optional, default None (company-wide). Pass a lead_owner
    string to scope to one salesperson's own leads, via the same
    follow_ups f JOIN leads l ON l.cls_id = f.cls_id / l.lead_owner
    pattern already used by get_todays_agenda()/get_due_by_kind() below.

    Returns an int.
    """
    conn = _connect()
    try:
        query = """
            SELECT COUNT(*) c
            FROM follow_ups f
            JOIN leads l ON l.cls_id = f.cls_id
            WHERE substr(f.scheduled_at, 1, 10) = ?
              AND f.status = 'scheduled'
        """
        params = [date_str]
        if owner:
            query += " AND l.lead_owner = ?"
            params.append(owner)
        row = conn.execute(query, params).fetchone()
        return row["c"]
    finally:
        conn.close()


FOLLOW_UP_OUTCOMES = {
    # action -> (new_status, closes_the_slot, activity_type)
    "completed": ("completed", True,  "follow_up_completed"),
    "postponed": ("scheduled", False, "follow_up_postponed"),  # stays open, same slot
    "cancelled": ("cancelled", True,  "follow_up_cancelled"),
}


def update_follow_up(followup_id, action, actor, reason, new_scheduled_at=None):
    """
    Record an outcome for a scheduled follow-up (v1.9). action must be
    one of FOLLOW_UP_OUTCOMES' keys: completed / postponed / cancelled.
    A reason is REQUIRED for every action. "postponed" behaves exactly
    like site visit's "rescheduled" — same row, new scheduled_at,
    stays open. See update_site_visit's docstring for the full
    reasoning.

    Returns (ok: bool, message: str).
    """
    if action not in FOLLOW_UP_OUTCOMES:
        return False, f"'{action}' is not a recognised outcome."
    reason = (reason or "").strip()
    if not reason:
        return False, "A reason is required."
    if action == "postponed" and not new_scheduled_at:
        return False, "New date/time is required when postponing."

    new_status, closes, activity_type = FOLLOW_UP_OUTCOMES[action]

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT cls_id, scheduled_at, status FROM follow_ups WHERE followup_id=?",
            (followup_id,)
        ).fetchone()
        if not row:
            return False, "Follow-up not found."
        if row["status"] != "scheduled":
            return False, "This follow-up has already been closed."

        now = _now()
        if action == "postponed":
            conn.execute("""
                UPDATE follow_ups SET scheduled_at=?, outcome_reason=? WHERE followup_id=?
            """, (new_scheduled_at, reason, followup_id))
            _log_activity(conn, row["cls_id"], activity_type, actor,
                          prev_value=row["scheduled_at"], new_value=new_scheduled_at,
                          description=reason)
        else:
            conn.execute("""
                UPDATE follow_ups SET status=?, completed_at=?, outcome_reason=? WHERE followup_id=?
            """, (new_status, now, reason, followup_id))
            _log_activity(conn, row["cls_id"], activity_type, actor, description=reason)
        conn.commit()
        return True, f"Follow-up marked {action}."
    finally:
        conn.close()


def get_site_visits_for_lead(cls_id):
    """
    All site visits for one lead, newest scheduled first — feeds the
    lead detail page's site-visit list (so 'Mark Conducted' works
    regardless of whether the visit is due today or not).

    Each row gets a computed 'missed' key (same live logic as
    get_due_today() — never stored) so the template doesn't need to
    fake its own "now" comparison against an unrelated column.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM site_visits WHERE cls_id=? ORDER BY scheduled_at DESC",
            (cls_id,)
        ).fetchall()
        now = _now()
        result = []
        for r in rows:
            d = dict(r)
            d["missed"] = (d["status"] == "scheduled" and d["scheduled_at"] < now)
            result.append(d)
        return result
    finally:
        conn.close()


def get_follow_ups_for_lead(cls_id):
    """
    All follow-ups for one lead, newest scheduled first — same purpose
    and same computed 'missed' key as get_site_visits_for_lead above.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM follow_ups WHERE cls_id=? ORDER BY scheduled_at DESC",
            (cls_id,)
        ).fetchall()
        now = _now()
        result = []
        for r in rows:
            d = dict(r)
            d["missed"] = (d["status"] == "scheduled" and d["scheduled_at"] < now)
            result.append(d)
        return result
    finally:
        conn.close()


def create_manual_lead(full_name, phone_raw, initial_stage, actor,
                       project="", email_raw="", lead_owner="", source_detail=""):
    """
    Create a lead manually from inside the CRM (v1.9, source_detail
    added v2.0) — for walk-ins, references, and offline inquiries that
    never came through Meta or Sell.do's digital intake.

    initial_stage MUST be one of MANUAL_ENTRY_STAGES (Incoming /
    Prospect / Opportunity / Site Visited).

    v2.70 (Task 4, item 6) — "Incoming" was previously excluded here on
    the reasoning that a manually-entered lead is definitionally not a
    fresh digital inquiry. Srikanth explicitly reversed that decision
    2026-08-20 (Task 4, item 6): a walk-in genuinely AT the very start
    of the funnel can now be entered as Incoming too, same as any other
    stage a manual entry might already be sitting at. Do NOT restore
    the old restriction without a fresh explicit instruction — this note
    exists specifically so a future session doesn't "fix" it back.

    source_detail MUST be one of MANUAL_SOURCE_OPTIONS if provided —
    this is set ONCE, here, at creation, and locked from then on (see
    update_lead_source_detail's docstring for the admin-only reasoning).

    source='manual_crm' on the row — distinguishes it from 'meta' and
    'selldo_only' everywhere else in the system (dashboard counts,
    leads list Source column, etc). If this SAME person later also
    gets entered into Sell.do (per parallel-run's double-entry
    discipline), Job B's existing phone/email matching logic will find
    and enrich THIS row rather than creating a duplicate — no new
    matching logic needed, that's already how upsert_selldo_lead works
    for any selldo_only row.

    Returns (ok: bool, message_or_cls_id: str).
    """
    full_name = (full_name or "").strip()
    if not full_name:
        return False, "Name is required."
    if initial_stage not in MANUAL_ENTRY_STAGES:
        return False, (f"Initial stage must be one of: "
                       f"{', '.join(MANUAL_ENTRY_STAGES)}.")
    if source_detail and source_detail not in MANUAL_SOURCE_OPTIONS:
        return False, (f"Source must be one of: "
                       f"{', '.join(MANUAL_SOURCE_OPTIONS)}.")

    phone_norm = norm_phone(phone_raw)
    if not phone_norm:
        return False, "A valid phone number is required."
    email_norm = norm_email(email_raw)

    conn = _connect()
    try:
        # Same dedup courtesy as the automated paths — don't create a
        # second row for a person already in cls.db.
        existing_id, _ = find_match(conn, phone_norm, email_norm)
        if existing_id:
            return False, ("A lead with this phone/email already exists "
                           f"(open it directly rather than creating a duplicate).")

        now = _now()
        cls_id = str(uuid.uuid4())

        def _do_insert(crm_lead_no):
            conn.execute("""
                INSERT INTO leads (
                    cls_id, project, project_bucket, full_name, phone_raw, phone_norm,
                    email_raw, email_norm, current_stage, stage_updated_at,
                    match_tier, source, lead_owner, crm_lead_no,
                    lead_source_detail, cls_created_at, cls_updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cls_id, project, get_project_bucket(project), full_name, phone_raw, phone_norm,
                  email_raw, email_norm, initial_stage, now,
                  "manual", "manual_crm", lead_owner, crm_lead_no,
                  source_detail or None, now, now))

        crm_lead_no = _insert_lead_with_lead_no_retry(conn, _do_insert)
        _log_activity(conn, cls_id, "lead_entered", actor,
                      new_value=initial_stage,
                      description=f"Manually entered by {actor}"
                                  + (f" (source: {source_detail})" if source_detail else ""))
        conn.commit()
        return True, cls_id
    finally:
        conn.close()


def update_lead_source_detail(cls_id, new_source_detail, actor):
    """
    Change a lead's source_detail AFTER creation (v2.0). Deliberately
    a separate, tightly-scoped function from create_manual_lead — this
    is the ONLY way source_detail can change post-creation. app.py
    restricts the route calling this to admin only: a salesperson
    logging where a lead came from once shouldn't be able to quietly
    edit that later, since it's meant to be an honest record of first
    contact, not something touched up after the fact.

    Returns (ok: bool, message: str).
    """
    if new_source_detail not in MANUAL_SOURCE_OPTIONS:
        return False, f"Source must be one of: {', '.join(MANUAL_SOURCE_OPTIONS)}."

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT lead_source_detail FROM leads WHERE cls_id=?", (cls_id,)
        ).fetchone()
        if not row:
            return False, "Lead not found."

        prev = row["lead_source_detail"]
        conn.execute(
            "UPDATE leads SET lead_source_detail=?, cls_updated_at=? WHERE cls_id=?",
            (new_source_detail, _now(), cls_id)
        )
        _log_activity(conn, cls_id, "source_changed", actor,
                      prev_value=prev, new_value=new_source_detail)
        conn.commit()
        return True, f"Source updated to {new_source_detail}."
    finally:
        conn.close()


def update_lead_contact_info(cls_id, actor, full_name=None, phone_raw=None, alt_phone_raw=None):
    """
    (v2.6) Correct a lead's name and/or phone number after creation —
    for the common real-world mess-ups: an email pasted into the name
    field, a missing/wrong country code on the phone number. Pass only
    what you want to change; the rest is left untouched.

    phone_raw is re-normalized through norm_phone() — the SAME
    function the matcher itself uses — so phone_norm (the actual join
    key Job B's Sell.do sync matches leads on) never goes stale
    relative to what's now stored in phone_raw. A rejected/empty
    normalization (e.g. an obviously invalid number) fails the whole
    call rather than silently writing a phone_raw that no longer has a
    working phone_norm behind it.

    FLAGGED RISK (not new — see v2.6 changelog): correcting these
    fields can change what Job B's Sell.do-sync matcher recognises as
    "the same lead" going forward. Every change is logged to
    activity_log with the old and new value, specifically so a
    resulting duplicate is traceable rather than a mystery.

    v2.11 — NEW optional alt_phone_raw (Srikanth's decision 5): a
    second contact number, same "pass only what you want to change"
    pattern as phone_raw. Re-normalized through the SAME norm_phone()
    into alt_phone_norm PURELY for display (a clickable tel: link) —
    alt_phone_norm is NEVER fed into find_match() or any matcher, and
    never will be; it carries no dedup/matching weight, unlike
    phone_norm above. An empty/invalid alt_phone_raw fails the call
    the same way an invalid phone_raw does, for the same reason.

    Returns (ok: bool, message: str).
    """
    full_name = full_name.strip() if full_name is not None else None
    if full_name is not None and not full_name:
        return False, "Name can't be blank."

    new_phone_norm = None
    if phone_raw is not None:
        phone_raw = phone_raw.strip()
        if not phone_raw:
            return False, "Phone can't be blank."
        new_phone_norm = norm_phone(phone_raw)
        if not new_phone_norm:
            return False, "That doesn't look like a valid phone number."

    new_alt_phone_norm = None
    if alt_phone_raw is not None:
        alt_phone_raw = alt_phone_raw.strip()
        if not alt_phone_raw:
            return False, "Alternate phone can't be blank."
        new_alt_phone_norm = norm_phone(alt_phone_raw)
        if not new_alt_phone_norm:
            return False, "That doesn't look like a valid alternate phone number."

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT full_name, phone_raw, phone_norm, alt_phone_raw FROM leads WHERE cls_id=?", (cls_id,)
        ).fetchone()
        if not row:
            return False, "Lead not found."

        updates, params, changed = [], [], []
        if full_name is not None and full_name != row["full_name"]:
            updates.append("full_name=?"); params.append(full_name)
            changed.append(f"Name: '{row['full_name']}' -> '{full_name}'")
        if phone_raw is not None and phone_raw != row["phone_raw"]:
            updates.append("phone_raw=?"); params.append(phone_raw)
            updates.append("phone_norm=?"); params.append(new_phone_norm)
            changed.append(f"Phone: '{row['phone_raw']}' -> '{phone_raw}'")
        if alt_phone_raw is not None and alt_phone_raw != row["alt_phone_raw"]:
            updates.append("alt_phone_raw=?"); params.append(alt_phone_raw)
            updates.append("alt_phone_norm=?"); params.append(new_alt_phone_norm)
            changed.append(f"Alt phone: '{row['alt_phone_raw']}' -> '{alt_phone_raw}'")

        if not updates:
            return False, "Nothing to update."

        updates.append("cls_updated_at=?"); params.append(_now())
        params.append(cls_id)
        conn.execute(f"UPDATE leads SET {', '.join(updates)} WHERE cls_id=?", params)
        _log_activity(conn, cls_id, "contact_info_updated", actor,
                      description="; ".join(changed))
        conn.commit()
        return True, "Contact info updated."
    finally:
        conn.close()


def delete_lead(cls_id, actor):
    """
    (v2.7) HARD-DELETE a lead and every child row keyed to it — a
    genuine wipe, not a soft-delete flag (Srikanth's explicit call).
    ADMIN-ONLY: the admin check lives in the ROUTE (app.py), not here;
    this function trusts its caller, exactly like every other write
    function in this file.

    Deletes, in ONE transaction so nothing is ever left orphaned:
      leads, activity_log, site_visits, follow_ups, events_log,
      comms_log — every table that references this cls_id.

    FLAGGED (also in the route + v2.7 changelog): if this person still
    exists in Sell.do, Job B's next sync re-imports them as a fresh
    lead. That's accepted parallel-run behaviour, not a bug — a real
    suppression list is deferred to v1.0+.

    `actor` is accepted for signature-consistency with the other write
    functions and so the route can log the deletion to the app log;
    it is NOT written to activity_log here, since that row is about to
    be deleted along with everything else.

    Returns (ok: bool, message: str). Never raises for a missing lead —
    returns ok=False so the route can flash a clean message.
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT crm_lead_no, full_name FROM leads WHERE cls_id=?", (cls_id,)
        ).fetchone()
        if not row:
            return False, "Lead not found (already deleted?)."

        label = f"#{row['crm_lead_no']} {row['full_name'] or '(no name)'}"

        # Order doesn't strictly matter (no FK constraints enforced in
        # this schema), but children-first keeps intent obvious.
        conn.execute("DELETE FROM activity_log WHERE cls_id=?", (cls_id,))
        conn.execute("DELETE FROM site_visits  WHERE cls_id=?", (cls_id,))
        conn.execute("DELETE FROM follow_ups   WHERE cls_id=?", (cls_id,))
        conn.execute("DELETE FROM events_log   WHERE cls_id=?", (cls_id,))
        conn.execute("DELETE FROM comms_log    WHERE cls_id=?", (cls_id,))
        conn.execute("DELETE FROM leads        WHERE cls_id=?", (cls_id,))
        conn.commit()
        return True, f"Lead {label} and all its data were permanently deleted."
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# WHATSAPP TEMPLATES  —  CRM v2.7 (admin-managed, per-project)
# ─────────────────────────────────────────────────────────────

def get_whatsapp_templates():
    """(v2.7) All WhatsApp templates, alphabetical by project. For the
    Settings admin screen and the lead-page picker."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM whatsapp_templates ORDER BY project COLLATE NOCASE ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_whatsapp_template_for_project(project):
    """(v2.7) One template by exact project title, or None."""
    if not project:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM whatsapp_templates WHERE project=?", (project,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_whatsapp_template(project, message_body, actor):
    """
    (v2.7) Create or update the template for a project. project is the
    UNIQUE key/title, so saving the same project again overwrites its
    body (edit), and a new project name inserts a new template. Both
    fields required. Admin-gate is in the route.

    Returns (ok: bool, message: str).
    """
    project = (project or "").strip()
    message_body = (message_body or "").strip()
    if not project:
        return False, "Project (template title) is required."
    if not message_body:
        return False, "Message body can't be empty."

    conn = _connect()
    try:
        now = _now()
        existing = conn.execute(
            "SELECT template_id FROM whatsapp_templates WHERE project=?", (project,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE whatsapp_templates SET message_body=?, updated_at=? WHERE project=?",
                (message_body, now, project)
            )
            msg = f"Template for '{project}' updated."
        else:
            conn.execute(
                "INSERT INTO whatsapp_templates (project, message_body, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (project, message_body, now, now)
            )
            msg = f"Template for '{project}' created."
        conn.commit()
        return True, msg
    finally:
        conn.close()


def delete_whatsapp_template(template_id):
    """(v2.7) Delete one template by id. Admin-gate is in the route.
    Returns (ok, message)."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT project FROM whatsapp_templates WHERE template_id=?", (template_id,)
        ).fetchone()
        if not row:
            return False, "Template not found."
        conn.execute("DELETE FROM whatsapp_templates WHERE template_id=?", (template_id,))
        conn.commit()
        return True, f"Template for '{row['project']}' deleted."
    finally:
        conn.close()


def render_whatsapp_template(message_body, lead):
    """
    (v2.7) Expand {name} and {project} placeholders in a template body
    against a lead dict. Unknown placeholders are left as-is rather than
    erroring — a template author's typo shouldn't blank the message.
    {name} falls back to a neutral 'there' when the lead has no name,
    so "Hi {name}" never renders as "Hi ." on a nameless lead.

    Returns the rendered string, ready to URL-encode into a wa.me link.
    """
    name = (lead.get("full_name") or "").strip() or "there"
    project = (lead.get("project") or "").strip()
    out = message_body.replace("{name}", name).replace("{project}", project)
    return out


# ─────────────────────────────────────────────────────────────
# WHATSAPP SITE-VISIT REMINDER TEMPLATES  —  CRM v2.14
# ─────────────────────────────────────────────────────────────
# Separate table/CRUD from the WHATSAPP TEMPLATES section above — see
# the whatsapp_reminder_templates table comment in init_db() for why
# this isn't a reuse of whatsapp_templates. Mirrors that section's CRUD
# shape exactly, for consistency.

def get_whatsapp_reminder_templates():
    """(v2.14) All site-visit reminder templates, alphabetical by
    project. For the Settings admin screen and the reminders page."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM whatsapp_reminder_templates ORDER BY project COLLATE NOCASE ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_whatsapp_reminder_template(project, message_body, actor):
    """
    (v2.14) Create or update the site-visit reminder template for a
    project. project is the UNIQUE key/title, so saving the same
    project again overwrites its body (edit), and a new project name
    inserts a new template. Both fields required. Admin-gate is in the
    route.

    Returns (ok: bool, message: str).
    """
    project = (project or "").strip()
    message_body = (message_body or "").strip()
    if not project:
        return False, "Project (template title) is required."
    if not message_body:
        return False, "Message body can't be empty."

    conn = _connect()
    try:
        now = _now()
        existing = conn.execute(
            "SELECT template_id FROM whatsapp_reminder_templates WHERE project=?", (project,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE whatsapp_reminder_templates SET message_body=?, updated_by=?, updated_at=? "
                "WHERE project=?",
                (message_body, actor, now, project)
            )
            msg = f"Reminder template for '{project}' updated."
        else:
            conn.execute(
                "INSERT INTO whatsapp_reminder_templates (project, message_body, updated_by, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (project, message_body, actor, now)
            )
            msg = f"Reminder template for '{project}' created."
        conn.commit()
        return True, msg
    finally:
        conn.close()


def delete_whatsapp_reminder_template(template_id):
    """(v2.14) Delete one reminder template by id. Admin-gate is in the
    route. Returns (ok, message)."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT project FROM whatsapp_reminder_templates WHERE template_id=?", (template_id,)
        ).fetchone()
        if not row:
            return False, "Template not found."
        conn.execute("DELETE FROM whatsapp_reminder_templates WHERE template_id=?", (template_id,))
        conn.commit()
        return True, f"Reminder template for '{row['project']}' deleted."
    finally:
        conn.close()


def render_whatsapp_reminder_template(message_body, lead, scheduled_at_iso):
    """
    (v2.14) Expand {name}, {project} and {time} placeholders in a
    reminder template body against a lead dict and a visit's
    scheduled_at. Unknown placeholders are left as-is (same tolerant
    behavior as render_whatsapp_template()). {name} falls back to
    'there' on a nameless lead. {time} is formatted 12-hour with
    AM/PM (mirrors app.py's `ampm` Jinja filter's own strftime format)
    and falls back to '' if scheduled_at_iso is missing or doesn't
    match either timestamp shape cls_db writes.

    Returns the rendered string, ready to URL-encode into a wa.me link.
    """
    name = (lead.get("full_name") or "").strip() or "there"
    project = (lead.get("project") or "").strip()
    time_str = ""
    if scheduled_at_iso:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                time_str = datetime.strptime(scheduled_at_iso, fmt).strftime("%I:%M %p")
                break
            except ValueError:
                continue
    out = (message_body.replace("{name}", name)
                        .replace("{project}", project)
                        .replace("{time}", time_str))
    return out


def get_site_visits_for_tomorrow(owner_match_name=None):
    """
    (v2.14) Tomorrow's scheduled site visits, for the WhatsApp reminders
    page (/reminders/site-visits-tomorrow). Scope: status='scheduled'
    AND DATE(scheduled_at) = tomorrow — server-local, via
    DATE('now','localtime','+1 day'), the SAME server-local convention
    _now()/datetime.now() use everywhere else in this file (no timezone
    abstraction here either). When owner_match_name is given, further
    filtered to that salesperson's own leads (leads.lead_owner).

    Returns a list of dicts: visit_id, cls_id, full_name, phone_raw,
    phone_norm, phone_e164 ("91" + phone_norm), project (from
    leads.project), scheduled_at, notes, reminder_sent_at (v2.69 — now
    read straight from the stored site_visits.reminder_sent_at column,
    set by log_reminder_sent() and reset to NULL on a genuine reschedule
    by update_site_visit() — see both functions and the v2.69 changelog
    entry at top of file. Previously a correlated LIKE-against-
    activity_log scalar subquery, which was both slow (~509ms measured
    in the Dashboard diagnosis session) and had a bug where a reminder's
    "sent" status incorrectly survived a reschedule to a new date).
    Sorted by scheduled_at ascending.
    """
    conn = _connect()
    try:
        query = """
            SELECT v.visit_id, v.cls_id, l.full_name, l.phone_raw, l.phone_norm,
                   l.project, v.scheduled_at, v.notes, v.reminder_sent_at
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE v.status = 'scheduled'
              AND DATE(v.scheduled_at) = DATE('now', 'localtime', '+1 day')
        """
        params = []
        if owner_match_name is not None:
            query += " AND l.lead_owner = ?"
            params.append(owner_match_name)
        query += " ORDER BY v.scheduled_at ASC"

        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["phone_e164"] = "91" + (d["phone_norm"] or "")
            results.append(d)
        return results
    finally:
        conn.close()


def get_weekend_site_visits(owner_match_name=None):
    """
    (v2.59) Site visits scheduled for the upcoming weekend (Saturday +
    Sunday), grouped implicitly by lead_owner for the caller to break
    down. Uses SQLite's 'weekday 6' modifier: jumps forward to the next
    Saturday (or stays on today if today IS Saturday), so this works
    correctly regardless of which day it's run on — Friday run shows
    tomorrow+Sunday, Saturday run shows today+tomorrow.

    When owner_match_name is given, scoped to that salesperson's own
    leads only (leads.lead_owner) — same scoping convention as
    get_site_visits_for_tomorrow().

    Returns a list of dicts: visit_id, cls_id, full_name, phone_raw,
    phone_norm, phone_e164, project, lead_owner, scheduled_at, notes.
    Sorted by lead_owner, then scheduled_at ascending — ready for a
    caller to group-by lead_owner without a separate sort step.
    """
    conn = _connect()
    try:
        query = """
            SELECT v.visit_id, v.cls_id, l.full_name, l.phone_raw, l.phone_norm,
                   l.project, l.lead_owner, v.scheduled_at, v.notes
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE v.status = 'scheduled'
              AND DATE(v.scheduled_at) BETWEEN
                  DATE('now', 'localtime', 'weekday 6')
                  AND DATE('now', 'localtime', 'weekday 6', '+1 day')
        """
        params = []
        if owner_match_name is not None:
            query += " AND l.lead_owner = ?"
            params.append(owner_match_name)
        query += " ORDER BY l.lead_owner ASC, v.scheduled_at ASC"

        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["phone_e164"] = "91" + (d["phone_norm"] or "")
            results.append(d)
        return results
    finally:
        conn.close()


def get_monday_weekly_report_stats(week_start, week_end):
    """
    (v2.60) Monday Morning Weekly Report — 5 headline numbers for the
    most recently completed Mon-Sun week. week_start/week_end are
    'YYYY-MM-DD' strings (Monday and Sunday of that week, inclusive).

    leads_generated       : leads.cls_created_at in range.
    site_visits_scheduled : site_visits.created_at in range — SCHEDULING
                             ACTIVITY this week (Decision A, confirmed by
                             Srikanth 2026-08-17). Deliberately NOT
                             scheduled_at, so this pairs with
                             site_visits_conducted as a same-week
                             scheduled->conducted funnel, not a mix of
                             old + new appointments.
    site_visits_conducted : site_visits.status='conducted' AND
                             conducted_at in range.
    bookings_weekday /
    bookings_weekend       : EVENT count — activity_log rows where
                             activity_type='stage_change' AND
                             new_value='Booked', a.created_at in range
                             (SAME definition as get_booking_summary_
                             totals()'s "bookings" — Decision 3 there:
                             deliberately NOT current_stage='Booked',
                             so a lead that unwinds and rebooks in-week
                             counts once per event, not zero or twice).
                             Split by SQLite strftime('%w', created_at):
                             '1'-'5' = weekday, '0'/'6' = weekend.
    """
    conn = _connect()
    try:
        start_ts = f"{week_start} 00:00:00"
        end_ts = f"{week_end} 23:59:59"

        leads_generated = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE cls_created_at >= ? AND cls_created_at <= ?",
            (start_ts, end_ts)
        ).fetchone()["c"]

        site_visits_scheduled = conn.execute(
            "SELECT COUNT(*) c FROM site_visits WHERE created_at >= ? AND created_at <= ?",
            (start_ts, end_ts)
        ).fetchone()["c"]

        site_visits_conducted = conn.execute(
            "SELECT COUNT(*) c FROM site_visits WHERE status='conducted' "
            "AND conducted_at >= ? AND conducted_at <= ?",
            (start_ts, end_ts)
        ).fetchone()["c"]

        bookings_weekday = conn.execute(
            "SELECT COUNT(*) c FROM activity_log "
            "WHERE activity_type='stage_change' AND new_value='Booked' "
            "AND created_at >= ? AND created_at <= ? "
            "AND strftime('%w', created_at) IN ('1','2','3','4','5')",
            (start_ts, end_ts)
        ).fetchone()["c"]

        bookings_weekend = conn.execute(
            "SELECT COUNT(*) c FROM activity_log "
            "WHERE activity_type='stage_change' AND new_value='Booked' "
            "AND created_at >= ? AND created_at <= ? "
            "AND strftime('%w', created_at) IN ('0','6')",
            (start_ts, end_ts)
        ).fetchone()["c"]

        return {
            "week_start": week_start,
            "week_end": week_end,
            "leads_generated": leads_generated,
            "site_visits_scheduled": site_visits_scheduled,
            "site_visits_conducted": site_visits_conducted,
            "bookings_weekday": bookings_weekday,
            "bookings_weekend": bookings_weekend,
            "bookings_total": bookings_weekday + bookings_weekend,
        }
    finally:
        conn.close()


def get_monday_weekly_report_by_owner(week_start, week_end):
    """
    (v2.61) Monday Morning Weekly Report — PER-SALESPERSON breakdown,
    companion to get_monday_weekly_report_stats() (company-wide totals).

    Same 4 metrics as the company version, minus the weekday/weekend
    booking split (shown as a single combined bookings_total per
    owner — Srikanth confirmed 2026-08-17 the weekday/weekend split
    only matters at company level, not per person).

    Owner attribution is CURRENT lead_owner (today's ownership), same
    convention as get_bookings_by_owner_for_period() and
    get_leads_by_owner_for_period() — activity_log/site_visits don't
    snapshot ownership at event time, so this intentionally reflects
    today's assignment, not owner-at-event-time.

    Returns a list of dicts, one per owner (blank/NULL owner grouped
    as 'Unassigned'), sorted by leads_generated desc:
        [{"owner": "Devender Goud", "leads_generated": 12,
          "site_visits_scheduled": 8, "site_visits_conducted": 5,
          "bookings_total": 1}, ...]
    Every owner that appears in ANY of the 4 metrics gets one row with
    all 4 keys present (defaulting to 0), not four separate partial rows.
    """
    conn = _connect()
    try:
        start_ts = f"{week_start} 00:00:00"
        end_ts = f"{week_end} 23:59:59"

        leads_rows = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(lead_owner), ''), 'Unassigned') AS owner, COUNT(*) c
            FROM leads WHERE cls_created_at >= ? AND cls_created_at <= ?
            GROUP BY owner
        """, (start_ts, end_ts)).fetchall()

        scheduled_rows = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(l.lead_owner), ''), 'Unassigned') AS owner, COUNT(*) c
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE v.created_at >= ? AND v.created_at <= ?
            GROUP BY owner
        """, (start_ts, end_ts)).fetchall()

        conducted_rows = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(l.lead_owner), ''), 'Unassigned') AS owner, COUNT(*) c
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE v.status='conducted' AND v.conducted_at >= ? AND v.conducted_at <= ?
            GROUP BY owner
        """, (start_ts, end_ts)).fetchall()

        bookings_rows = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(l.lead_owner), ''), 'Unassigned') AS owner, COUNT(*) c
            FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type='stage_change' AND a.new_value='Booked'
            AND a.created_at >= ? AND a.created_at <= ?
            GROUP BY owner
        """, (start_ts, end_ts)).fetchall()

        merged = {}

        def _add(rows, key):
            for r in rows:
                merged.setdefault(r["owner"], {
                    "owner": r["owner"], "leads_generated": 0,
                    "site_visits_scheduled": 0, "site_visits_conducted": 0,
                    "bookings_total": 0,
                })[key] = r["c"]

        _add(leads_rows, "leads_generated")
        _add(scheduled_rows, "site_visits_scheduled")
        _add(conducted_rows, "site_visits_conducted")
        _add(bookings_rows, "bookings_total")

        result = list(merged.values())
        result.sort(key=lambda r: r["leads_generated"], reverse=True)
        return result
    finally:
        conn.close()


def get_site_visit_by_id(visit_id):
    """
    (v2.14) One site_visits row by id, or None. Used by the reminders
    mark-sent route (/reminders/site-visits-tomorrow/mark-sent/<visit_id>
    — no cls_id in that URL) to resolve a visit_id back to its cls_id
    before running the ownership gate.
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM site_visits WHERE visit_id=?", (visit_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_pending_reminder_count(owner_match_name=None):
    """
    (v2.14) Count of tomorrow's site visits with no reminder sent yet —
    feeds the drawer badge and the Dashboard tile. Built on
    get_site_visits_for_tomorrow() rather than a separate query — the
    dataset (one day's worth of scheduled visits) is small enough that
    reuse costs nothing and keeps the "sent" definition in exactly one
    place.
    """
    return sum(
        1 for v in get_site_visits_for_tomorrow(owner_match_name)
        if not v["reminder_sent_at"]
    )


def log_reminder_sent(visit_id, cls_id, actor):
    """
    (v2.14) Records that a tomorrow's-site-visit WhatsApp reminder was
    sent, via the existing activity_log audit trail (no new table).
    description is EXACTLY f"visit_id:{visit_id}" — kept for the lead's
    Activity History even though get_site_visits_for_tomorrow() no
    longer LIKE-parses it (v2.69 — reads site_visits.reminder_sent_at
    directly instead, set below in this same transaction).

    v2.69 — ALSO writes site_visits.reminder_sent_at = now(), same
    connection/transaction as the activity_log write above (which stays
    UNCHANGED and KEPT — Srikanth wants the note in lead history
    regardless of this column's existence). See update_site_visit()'s
    "rescheduled" branch for where this gets reset back to NULL.
    """
    conn = _connect()
    try:
        now = _now()
        _log_activity(conn, cls_id, "whatsapp_reminder_sent", actor,
                      description=f"visit_id:{visit_id}")
        conn.execute(
            "UPDATE site_visits SET reminder_sent_at=? WHERE visit_id=?",
            (now, visit_id)
        )
        conn.commit()
    finally:
        conn.close()


def log_whatsapp_sent(cls_id, actor, description):
    """
    (v2.28) Task 2.2 — records a WhatsApp Templates send (whatsapp_picker
    screen) via the existing activity_log audit trail, same pattern as
    log_reminder_sent() above. Distinct activity_type
    ('whatsapp_sent') from that function's 'whatsapp_reminder_sent', so
    the two flows stay distinguishable in a lead's Activity History.
    """
    conn = _connect()
    try:
        _log_activity(conn, cls_id, "whatsapp_sent", actor, description=description)
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# IMPERSONATION  —  CRM v2.15 (admin "View as")
# ─────────────────────────────────────────────────────────────

def log_impersonation(admin_email, target_email, event):
    """
    (v2.15) Append one row to impersonation_log. event must be 'start'
    or 'exit' — anything else raises ValueError (a caller bug, not a
    user-facing error path, so this fails loud rather than silently
    writing a garbage event value).
    """
    if event not in ("start", "exit"):
        raise ValueError(f"log_impersonation: event must be 'start' or 'exit', got {event!r}")
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO impersonation_log (admin_email, target_email, event, created_at) "
            "VALUES (?, ?, ?, ?)",
            (admin_email, target_email, event, _now())
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# USER ACTIVITY LOG  —  CRM v2.21 (Settings > User Activity)
# ─────────────────────────────────────────────────────────────
# Session-level audit trail: one user_sessions row per login (auto-
# closed 'superseded' if a stale session for that user is still open
# when a new one starts), one user_action_log row per request app.py's
# before_request hook logs against that session's session_id.

def start_user_session(user_id, actor, ip_address):
    """
    (v2.21) Opens a new user_sessions row for a just-authenticated
    login. Before inserting, auto-closes any session for this user_id
    that is still open (logout_at IS NULL) — logout_reason='superseded'
    — so a user who closes their browser without logging out (or logs
    in again from a second device) never leaves two "still active"
    cards showing at once. Returns the new session_id (int) for
    app.py's login() to stash in session["session_row_id"].
    """
    conn = _connect()
    try:
        now = _now()
        conn.execute(
            "UPDATE user_sessions SET logout_at=?, logout_reason='superseded' "
            "WHERE user_id=? AND logout_at IS NULL",
            (now, user_id)
        )
        cur = conn.execute(
            "INSERT INTO user_sessions (user_id, actor, login_at, ip_address) "
            "VALUES (?, ?, ?, ?)",
            (user_id, actor, now, ip_address)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def end_user_session(session_id, reason="manual"):
    """
    (v2.21) Closes a user_sessions row — sets logout_at/logout_reason,
    but ONLY if logout_at is still NULL, so calling this on a session
    that's already closed (e.g. already auto-closed as 'superseded' by
    a later login elsewhere) never overwrites the existing close.
    """
    if not session_id:
        return
    conn = _connect()
    try:
        conn.execute(
            "UPDATE user_sessions SET logout_at=?, logout_reason=? "
            "WHERE session_id=? AND logout_at IS NULL",
            (_now(), reason, session_id)
        )
        conn.commit()
    finally:
        conn.close()


def log_user_action(session_id, actor, method, label, cls_id=None):
    """
    (v2.21) Appends one row to user_action_log. Guard: if session_id is
    None (e.g. a request that hit before any session existed, such as
    /login itself), this is a no-op — there is nothing to attach the
    action to, and logging a sessionless action would break the "one
    card per session" grouping get_user_timeline() relies on.
    """
    if session_id is None:
        return
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO user_action_log (session_id, actor, method, label, cls_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, actor, method, label, cls_id, _now())
        )
        conn.commit()
    finally:
        conn.close()


def get_user_timeline(user_id=None, date_from=None, date_to=None):
    """
    (v2.21) Admin Settings > User Activity Log data source. Returns a
    list of session dicts (most recent login first), each carrying an
    "events" list already merged in chronological order: a synthetic
    "Logged in" event first, then every user_action_log row for that
    session (in created_at order), then a synthetic "Logged out" (or
    "Still active" if logout_at IS NULL) event last — so the template
    can render one card per session with no grouping/sorting of its own.

    user_id=None means every user (the admin's default view).
    date_from/date_to are 'YYYY-MM-DD' strings, both optional; if
    neither is given, both default to today. If only one is given, the
    other is set equal to it (a single-day view).
    """
    if not date_from and not date_to:
        today = datetime.now().strftime("%Y-%m-%d")
        date_from = date_to = today
    elif not date_from:
        date_from = date_to
    elif not date_to:
        date_to = date_from

    conn = _connect()
    try:
        query = (
            "SELECT session_id, user_id, actor, login_at, logout_at, "
            "logout_reason, ip_address FROM user_sessions "
            "WHERE substr(login_at, 1, 10) BETWEEN ? AND ?"
        )
        params = [date_from, date_to]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY login_at DESC"
        sessions = [dict(r) for r in conn.execute(query, params).fetchall()]

        actions_by_session = {}
        session_ids = [s["session_id"] for s in sessions]
        if session_ids:
            placeholders = ",".join("?" * len(session_ids))
            action_rows = conn.execute(
                f"SELECT session_id, actor, method, label, cls_id, created_at "
                f"FROM user_action_log WHERE session_id IN ({placeholders}) "
                f"ORDER BY created_at ASC",
                session_ids
            ).fetchall()
            for r in action_rows:
                actions_by_session.setdefault(r["session_id"], []).append(dict(r))

        timeline = []
        for s in sessions:
            events = [{
                "type": "login",
                "label": "Logged in",
                "at": s["login_at"],
                "ip_address": s["ip_address"],
            }]
            for a in actions_by_session.get(s["session_id"], []):
                events.append({
                    "type": "action",
                    "label": a["label"],
                    "method": a["method"],
                    "cls_id": a["cls_id"],
                    "at": a["created_at"],
                })
            if s["logout_at"]:
                events.append({
                    "type": "logout",
                    "label": "Logged out" if s["logout_reason"] != "superseded"
                             else "Logged out (new login elsewhere)",
                    "at": s["logout_at"],
                })
            else:
                events.append({"type": "active", "label": "Still active", "at": None})
            s["events"] = events
            timeline.append(s)
        return timeline
    finally:
        conn.close()


def _validate_multi_select(value, allowed_list, label):
    """
    Internal helper (v2.3). Validates a comma-separated multi-select
    string (e.g. "2 BHK, 3 BHK" for configuration, "East,West" for
    facing) against an allowed-values list. Splits on comma, strips
    whitespace from each token, drops empty tokens, and rejects if any
    remaining token isn't in allowed_list or if nothing valid remains.

    A single value with no comma is still valid input here — that's
    just a one-item multi-select, so single-value callers (existing
    forms that haven't been updated to checkboxes yet) keep working
    unchanged.

    Returns (ok: bool, normalized_value_or_error: str). normalized_value
    is the cleaned, comma-joined string to actually store.
    """
    tokens = [t.strip() for t in value.split(",") if t.strip()]
    if not tokens:
        return False, f"{label} can't be empty."
    bad = [t for t in tokens if t not in allowed_list]
    if bad:
        return False, f"{label} must be from: {', '.join(allowed_list)}. Got invalid: {', '.join(bad)}."
    return True, ", ".join(tokens)


def update_property_details(cls_id, actor, funding_source=None, property_type=None,
                            configuration=None, campaign=None, budget=None, facing=None):
    """
    Update any combination of a lead's property-preference fields —
    funding_source, property_type, configuration, campaign (v2.0),
    budget, facing (v2.3). Editable on ANY lead regardless of source,
    since these are usually learned from conversation well after a
    lead first arrives. Pass only the fields you want to change; the
    rest are left untouched.

    v2.3: property_type, configuration, and facing are now MULTI-SELECT
    — pass a comma-separated string (e.g. "2 BHK, 3 BHK"); a single
    value with no comma still works fine. Each is validated token-by-
    token via _validate_multi_select() against PROPERTY_TYPES /
    CONFIGURATIONS / FACING_OPTIONS. budget is still single-select,
    validated against BUDGET_BRACKETS.

    Returns (ok: bool, message: str).
    """
    if funding_source is not None and funding_source not in FUNDING_SOURCES:
        return False, f"Funding source must be one of: {', '.join(FUNDING_SOURCES)}."
    if budget is not None and budget not in BUDGET_BRACKETS:
        return False, f"Budget must be one of: {', '.join(BUDGET_BRACKETS)}."

    if property_type is not None:
        ok, result = _validate_multi_select(property_type, PROPERTY_TYPES, "Property type")
        if not ok:
            return False, result
        property_type = result

    if configuration is not None:
        ok, result = _validate_multi_select(configuration, CONFIGURATIONS, "Configuration")
        if not ok:
            return False, result
        configuration = result

    if facing is not None:
        ok, result = _validate_multi_select(facing, FACING_OPTIONS, "Facing")
        if not ok:
            return False, result
        facing = result

    conn = _connect()
    try:
        row = conn.execute("SELECT cls_id FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."

        updates, params, changed = [], [], []
        if funding_source is not None:
            updates.append("funding_source=?"); params.append(funding_source); changed.append(f"Funding: {funding_source}")
        if property_type is not None:
            updates.append("property_type=?"); params.append(property_type); changed.append(f"Type: {property_type}")
        if configuration is not None:
            updates.append("configuration=?"); params.append(configuration); changed.append(f"Config: {configuration}")
        if campaign is not None:
            updates.append("campaign=?"); params.append(campaign); changed.append(f"Campaign: {campaign}")
        if budget is not None:
            updates.append("budget=?"); params.append(budget); changed.append(f"Budget: {budget}")
        if facing is not None:
            updates.append("facing=?"); params.append(facing); changed.append(f"Facing: {facing}")

        if not updates:
            return False, "Nothing to update."

        updates.append("cls_updated_at=?"); params.append(_now())
        params.append(cls_id)
        conn.execute(f"UPDATE leads SET {', '.join(updates)} WHERE cls_id=?", params)
        _log_activity(conn, cls_id, "property_details_updated", actor,
                      description="; ".join(changed))
        conn.commit()
        return True, "Property details updated."
    finally:
        conn.close()


def update_lead_project(cls_id, new_bucket, actor):
    """
    (v2.76) Manually change a lead's project (Actions > Edit Property
    Details). new_bucket must be one of get_all_bucket_names() — same
    dropdown source already used by lead_new.html and the leads filter
    screen.

    No-op (returns ok=True, unchanged message) if new_bucket equals the
    lead's current project_bucket — avoids a pointless activity_log row
    and cls_updated_at bump on an unchanged resubmit, same discipline as
    upsert_selldo_lead()'s existing "only write on actual change" fix.

    Sets BOTH leads.project and leads.project_bucket to new_bucket (the
    canonical bucket name), same as _auto_cross_reassign_project() does
    — keeps the two columns in sync without a second get_project_bucket()
    round-trip, since the admin/salesperson is choosing the bucket
    directly here, not a raw alias string.

    Does NOT touch current_stage, stage_reason, lead_owner, or
    cross_reassigned_at — this is a pure project-field edit, orthogonal
    to the auto-reassignment feature (Lost/Unqualified is not required
    or checked here; Booked leads can have their project changed too —
    no restriction).

    Returns (ok: bool, message: str).
    """
    if new_bucket not in get_all_bucket_names():
        return False, f"'{new_bucket}' is not a recognised project."

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT project_bucket FROM leads WHERE cls_id=?", (cls_id,)
        ).fetchone()
        if not row:
            return False, "Lead not found."

        old_bucket = row["project_bucket"]
        if old_bucket == new_bucket:
            return True, "Project unchanged."

        conn.execute(
            "UPDATE leads SET project=?, project_bucket=?, cls_updated_at=? WHERE cls_id=?",
            (new_bucket, new_bucket, _now(), cls_id)
        )
        _log_activity(
            conn, cls_id, "project_changed", actor,
            description=f"Project changed: {old_bucket} -> {new_bucket} (manual)"
        )
        conn.commit()
        return True, f"Project updated to {new_bucket}."
    finally:
        conn.close()


def log_call_tap(cls_id, actor):
    """
    Logs a 'call_attempted' activity with a timestamp when someone taps
    a lead's phone number from inside the CRM (v1.9). This is the
    honest limit of what a web page can ever know about a phone call —
    see the v1.9 changelog for the full explanation of why duration/
    answered-status/recording need v1.0's telephony integration
    instead. Fire-and-forget from the frontend; never blocks the tel:
    link itself.
    """
    conn = _connect()
    try:
        row = conn.execute("SELECT cls_id FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."
        _log_activity(conn, cls_id, "call_attempted", actor)
        conn.commit()
        return True, "Logged."
    finally:
        conn.close()


def get_activity_log_for_lead(cls_id):
    """
    Full activity timeline for one lead, newest first — feeds the lead
    detail page's Activity History section. Includes notes, stage
    changes, assignment changes, and site-visit/follow-up scheduling
    and completion events, all in one interleaved list.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM activity_log WHERE cls_id=? ORDER BY created_at DESC, activity_id DESC",
            (cls_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_due_today(owner=None):
    """
    Site visits and follow-ups due today or overdue, across ALL leads —
    feeds the dashboard's "Due Today" card. This is the agreed
    substitute for exact-time push notifications (a separate iOS
    16.4+ PWA push project) — gets most of the value at a fraction
    of the effort.

    "Missed" is computed here, live, never stored: a row counts as
    missed if scheduled_at has passed and status is still 'scheduled'.
    Cancelled/completed items are excluded entirely.

    owner (v2.31): optional, default None (existing behavior, unchanged
    — every existing call site keeps calling this with zero args). Pass
    a lead_owner to scope both the site-visit and follow-up lists to
    one salesperson's own leads, same convention as
    get_stage_snapshot_counts(owner=None).

    Returns a list of dicts: {kind, id, cls_id, full_name, scheduled_at,
    missed, notes}, sorted by scheduled_at ascending (most overdue /
    soonest first).
    """
    conn = _connect()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        results = []

        visit_query = """
            SELECT v.visit_id, v.cls_id, v.scheduled_at, v.notes, l.full_name, l.crm_lead_no
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE v.status = 'scheduled' AND DATE(v.scheduled_at) <= DATE(?)
        """
        visit_params = [today]
        if owner:
            visit_query += " AND l.lead_owner = ?"
            visit_params.append(owner)
        visits = conn.execute(visit_query, visit_params).fetchall()
        for v in visits:
            results.append({
                "kind": "site_visit",
                "id": v["visit_id"],
                "cls_id": v["cls_id"],
                "full_name": v["full_name"],
                "crm_lead_no": v["crm_lead_no"],
                "scheduled_at": v["scheduled_at"],
                "missed": v["scheduled_at"] < _now(),
                "notes": v["notes"],
            })

        followup_query = """
            SELECT f.followup_id, f.cls_id, f.scheduled_at, f.notes, l.full_name, l.crm_lead_no
            FROM follow_ups f JOIN leads l ON l.cls_id = f.cls_id
            WHERE f.status = 'scheduled' AND DATE(f.scheduled_at) <= DATE(?)
        """
        followup_params = [today]
        if owner:
            followup_query += " AND l.lead_owner = ?"
            followup_params.append(owner)
        follow_ups = conn.execute(followup_query, followup_params).fetchall()
        for f in follow_ups:
            results.append({
                "kind": "follow_up",
                "id": f["followup_id"],
                "cls_id": f["cls_id"],
                "full_name": f["full_name"],
                "crm_lead_no": f["crm_lead_no"],
                "scheduled_at": f["scheduled_at"],
                "missed": f["scheduled_at"] < _now(),
                "notes": f["notes"],
            })

        results.sort(key=lambda r: r["scheduled_at"])
        return results
    finally:
        conn.close()


def get_due_by_kind(kind, owner=None):
    """
    Same due/overdue logic as get_due_today() above, filtered to just
    one kind (v1.9) — feeds the two split dashboard cards (Follow-ups
    Due, Site Visits Due) instead of one combined list. kind must be
    'site_visit' or 'follow_up'.

    owner (v2.31): optional, default None (existing behavior, unchanged
    — due_list() previously called this with just kind). Passed straight
    through to get_due_today(owner=owner).
    """
    return [item for item in get_due_today(owner=owner) if item["kind"] == kind]


def get_todays_agenda(owner=None):
    """
    (v2.58, Task 3 Part B) Site visits and follow-ups scheduled for
    TODAY specifically (DATE match, not <=), status='scheduled' only.
    This is deliberately DIFFERENT from get_due_today()/get_due_by_kind()
    above, which are <=today (overdue-inclusive) — Today's Agenda should
    also show a visit scheduled for LATER today, not just overdue ones.
    Same query structure/column selection/join pattern as get_due_today()
    otherwise, just the WHERE date comparison swapped from <= to =, so
    the two stay easy to compare.

    Returns {"site_visits": [...], "follow_ups": [...]} — two separate
    lists (not interleaved like get_due_today()'s combined list),
    because the template renders them under two separate headings
    side by side.

    owner: optional, default None (company-wide) — same convention as
    get_due_today(owner=None)/get_stage_snapshot_counts(owner=None).
    Pass a lead_owner string to scope to one salesperson's own leads.
    """
    conn = _connect()
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        visit_query = """
            SELECT v.visit_id, v.cls_id, v.scheduled_at, v.notes,
                   l.full_name, l.crm_lead_no
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE v.status = 'scheduled' AND DATE(v.scheduled_at) = DATE(?)
        """
        visit_params = [today]
        if owner:
            visit_query += " AND l.lead_owner = ?"
            visit_params.append(owner)
        visit_query += " ORDER BY v.scheduled_at ASC"
        site_visits = [dict(r) for r in conn.execute(visit_query, visit_params).fetchall()]

        followup_query = """
            SELECT f.followup_id, f.cls_id, f.scheduled_at, f.notes,
                   l.full_name, l.crm_lead_no
            FROM follow_ups f JOIN leads l ON l.cls_id = f.cls_id
            WHERE f.status = 'scheduled' AND DATE(f.scheduled_at) = DATE(?)
        """
        followup_params = [today]
        if owner:
            followup_query += " AND l.lead_owner = ?"
            followup_params.append(owner)
        followup_query += " ORDER BY f.scheduled_at ASC"
        follow_ups = [dict(r) for r in conn.execute(followup_query, followup_params).fetchall()]

        return {"site_visits": site_visits, "follow_ups": follow_ups}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# BOOKING SUMMARY (v2.31) — "Leads to Booking Summary" dashboard tab
# ─────────────────────────────────────────────────────────────
# Every function below is PERIOD-bound (date_from/date_to, both required
# 'YYYY-MM-DD' strings), unlike get_stage_snapshot_counts()'s live-
# snapshot semantics — deliberately a separate set of functions, not an
# overload of that one (dashboard_pipeline() keeps its unrelated
# live-snapshot meaning). All take the SAME 4 filter args — date_from,
# date_to, project=None, source=None, owner=None — matching the tab's
# 4-control filter bar; owner is a lead_owner string, same convention
# as every other owner= param in this file.

def _booking_summary_where(date_col, date_from, date_to, project=None, source=None, owner=None,
                            project_col="l.project", source_col="l.source", owner_col="l.lead_owner"):
    """
    (v2.31) Shared WHERE-clause fragment builder for every Booking
    Summary query below — all of them filter by the same date range +
    optional project/source/owner, just against different date columns
    and (for site_visits/activity_log queries, joined to leads as `l`)
    different table aliases for the project/source/owner columns
    themselves. Returns (sql_fragment, params); caller supplies the
    surrounding WHERE/AND.

    date_from/date_to blank/blank (the "Maximum" quick-select preset,
    cls_reports._maximum_range()) means NO date filter at all (all-
    time) — same "" == no-filter convention every cls_reports.py
    builder already uses (see _maximum_range()'s own docstring), so the
    Booking Summary page's date picker behaves identically to every
    other report's. A bare "1=1" placeholder keeps the fragment valid
    SQL even when every optional filter is skipped.
    """
    clauses = ["1=1"]
    params = []
    if date_from and date_to:
        clauses.append(f"{date_col} >= ?")
        clauses.append(f"{date_col} <= ?")
        params.append(f"{date_from} 00:00:00")
        params.append(f"{date_to} 23:59:59")
    if project:
        clauses.append(f"{project_col} = ?")
        params.append(project)
    if source:
        clauses.append(f"{source_col} = ?")
        params.append(source)
    if owner:
        clauses.append(f"{owner_col} = ?")
        params.append(owner)
    return " AND ".join(clauses), params


def get_booking_summary_totals(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) The 3 computable Quick Summary numbers for the Booking
    Summary tab ("Value (INR)" is NOT computed here — Decision 1,
    deferred; the template shows "—" instead of a fake/zero number).

    total_leads : leads.cls_created_at in range, matching filters.
    site_visits : site_visits.scheduled_at in range, joined to leads
                  for the project/source/owner filters.
    bookings    : EVENT count (Decision 3) — activity_log rows where
                  activity_type='stage_change' AND new_value='Booked',
                  a.created_at in range, joined to leads for filters.
                  Deliberately NOT current_stage='Booked' (a live
                  snapshot would double- or zero-count a lead that
                  unwinds and rebooks within the period).
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("l.cls_created_at", date_from, date_to, project, source, owner)
        total_leads = conn.execute(f"SELECT COUNT(*) c FROM leads l WHERE {where}", params).fetchone()["c"]

        where, params = _booking_summary_where("v.scheduled_at", date_from, date_to, project, source, owner)
        site_visits = conn.execute(f"""
            SELECT COUNT(*) c FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE {where}
        """, params).fetchone()["c"]

        where, params = _booking_summary_where("a.created_at", date_from, date_to, project, source, owner)
        bookings = conn.execute(f"""
            SELECT COUNT(*) c FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type='stage_change' AND a.new_value='Booked' AND {where}
        """, params).fetchone()["c"]

        return {"total_leads": total_leads, "site_visits": site_visits, "bookings": bookings}
    finally:
        conn.close()


def get_stage_counts_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) "Lead By Stage" — leads grouped by current_stage, WITHIN the
    date range (leads.cls_created_at) — a period count, deliberately a
    different function from get_stage_snapshot_counts(owner=None), which
    ignores date range entirely and is a live right-now snapshot. Every
    ALL_STAGES key is always present (even 0), same guarantee as
    get_stage_snapshot_counts().
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("l.cls_created_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT current_stage, COUNT(*) c FROM leads l WHERE {where} GROUP BY current_stage
        """, params).fetchall()
        live_counts = {r["current_stage"]: r["c"] for r in rows}
        return {stage: live_counts.get(stage, 0) for stage in ALL_STAGES}
    finally:
        conn.close()


def get_leads_by_owner_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) "Lead By Sales" — leads grouped by lead_owner, within range.
    Unassigned/blank owners are grouped as "Unassigned" rather than
    silently dropped, so this breakdown's total always reconciles with
    the Total Leads card for the same filters. Ordered by count desc.
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("l.cls_created_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.lead_owner), ''), 'Unassigned') AS label, COUNT(*) c
            FROM leads l WHERE {where} GROUP BY label ORDER BY c DESC
        """, params).fetchall()
        return [{"label": r["label"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_leads_by_project_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) "Lead By Project" (Decision 2 relabel — ours is single-value
    leads.project, not Sell.do's multi-select "Interested Project(s)").
    Blank/NULL project grouped as "Not Available", the label already
    used elsewhere in this app for an unset project. Ordered by count desc.
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("l.cls_created_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.project), ''), 'Not Available') AS label, COUNT(*) c
            FROM leads l WHERE {where} GROUP BY label ORDER BY c DESC
        """, params).fetchall()
        return [{"label": r["label"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_leads_by_source_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) "Lead By Source" (Decision 2 relabel). Grouped by the raw
    leads.source value (or 'Not Available' if blank) — returns the raw
    value as `label` for the template to translate via
    SOURCE_DISPLAY_LABELS.get(label, label), same display-layer-
    resolution split as get_all_users() (email -> full_name).
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("l.cls_created_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.source), ''), 'Not Available') AS label, COUNT(*) c
            FROM leads l WHERE {where} GROUP BY label ORDER BY c DESC
        """, params).fetchall()
        return [{"label": r["label"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_site_visits_by_owner_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) "Site Visits By Owner" — via leads.lead_owner (a visit's
    owner is inherited from its lead; site_visits has no owner column
    of its own). Unassigned grouped as "Unassigned", same as leads.
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("v.scheduled_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.lead_owner), ''), 'Unassigned') AS label, COUNT(*) c
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE {where} GROUP BY label ORDER BY c DESC
        """, params).fetchall()
        return [{"label": r["label"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_site_visits_by_status_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) "Site Visits By Status" — see SITE_VISIT_STATUS_LABELS'
    definition above for the full status-mapping rationale (Decision 4).
    "Scheduled" and "Missed" are both status='scheduled' rows, split
    live by whether scheduled_at has already passed — same missed-
    computation principle as get_due_today(), never a stored value.
    Returns a dict with all 5 SITE_VISIT_STATUS_LABELS keys always
    present (even 0), same guarantee as get_stage_snapshot_counts().
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("v.scheduled_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT v.status, v.scheduled_at FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE {where}
        """, params).fetchall()
        now = _now()
        counts = {label: 0 for label in SITE_VISIT_STATUS_LABELS}
        for r in rows:
            if r["status"] == "conducted":
                counts["Conducted"] += 1
            elif r["status"] == "cancelled":
                counts["Cancelled"] += 1
            elif r["status"] == "no_show":
                counts["Didn't Visit"] += 1
            elif r["status"] == "scheduled":
                if r["scheduled_at"] < now:
                    counts["Missed"] += 1
                else:
                    counts["Scheduled"] += 1
        return counts
    finally:
        conn.close()


def get_site_visits_by_project_for_period(date_from, date_to, project=None, source=None, owner=None):
    """(v2.31) "Site Visits By Project" — via leads.project, 'Not Available' if blank."""
    conn = _connect()
    try:
        where, params = _booking_summary_where("v.scheduled_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.project), ''), 'Not Available') AS label, COUNT(*) c
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE {where} GROUP BY label ORDER BY c DESC
        """, params).fetchall()
        return [{"label": r["label"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_site_visits_by_source_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) "Site Visits By Source" — via leads.source (raw value,
    template translates via SOURCE_DISPLAY_LABELS, same as
    get_leads_by_source_for_period()).
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("v.scheduled_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.source), ''), 'Not Available') AS label, COUNT(*) c
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE {where} GROUP BY label ORDER BY c DESC
        """, params).fetchall()
        return [{"label": r["label"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_bookings_by_owner_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) "Bookings By Owner" — EVENT count (Decision 3), grouped by
    the lead's CURRENT lead_owner. activity_log doesn't snapshot who
    owned the lead at the moment of the stage_change event, so this
    intentionally reflects today's ownership, not the owner-at-booking-
    time — matching the spec's own wording ("grouped by current lead_owner").
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("a.created_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.lead_owner), ''), 'Unassigned') AS label, COUNT(*) c
            FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type='stage_change' AND a.new_value='Booked' AND {where}
            GROUP BY label ORDER BY c DESC
        """, params).fetchall()
        return [{"label": r["label"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_bookings_by_project_for_period(date_from, date_to, project=None, source=None, owner=None):
    """(v2.31) "Bookings By Project" — EVENT count (Decision 3), grouped by leads.project."""
    conn = _connect()
    try:
        where, params = _booking_summary_where("a.created_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.project), ''), 'Not Available') AS label, COUNT(*) c
            FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type='stage_change' AND a.new_value='Booked' AND {where}
            GROUP BY label ORDER BY c DESC
        """, params).fetchall()
        return [{"label": r["label"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_booked_leads_for_period(date_from, date_to, project=None, source=None, owner=None):
    """
    (v2.31) Bookings sub-tab's lead list — one row per Booked-transition
    EVENT in range (Decision 3; a lead booked twice in the same period,
    e.g. unwound and rebooked, appears twice — consistent with this
    being an event list, not a deduplicated lead list). Value column
    omitted entirely (Decision 1, deferred). Ordered most recent first.
    """
    conn = _connect()
    try:
        where, params = _booking_summary_where("a.created_at", date_from, date_to, project, source, owner)
        rows = conn.execute(f"""
            SELECT l.crm_lead_no, l.full_name, l.lead_owner, l.project, a.created_at AS booked_at
            FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type='stage_change' AND a.new_value='Booked' AND {where}
            ORDER BY a.created_at DESC
        """, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_users():
    """
    email -> full_name lookup (v1.9) — used to show a person's NAME
    instead of their raw email in Activity History. The email is
    still what's actually stored in activity_log.actor (accurate,
    unique, stable for audit purposes); this is a display-layer
    resolution only, not a change to what gets logged.
    """
    conn = _connect()
    try:
        rows = conn.execute("SELECT email, full_name FROM users").fetchall()
        return {r["email"]: r["full_name"] for r in rows}
    finally:
        conn.close()


def get_all_users_detailed():
    """
    (v2.8) Full user rows for the admin Settings > Team screen — unlike
    get_all_users() (email->full_name only, for Activity History display),
    this returns everything the toggle-active UI needs: user_id, full_name,
    email, role, active, created_at, last_login_at. Ordered by full_name
    so the list reads alphabetically, admins and salespeople mixed together
    (role is shown as a badge, not used to sort/group — a small team
    doesn't need two separate lists).

    v2.25 — ADDITIVE: also returns owner_match_name (previously not
    selected). Needed by /settings/campaign-routing to source its owner
    dropdown with the exact string that ends up written as leads.
    lead_owner — full_name/email would silently mismatch it. Existing
    consumers (Settings > Team) are unaffected; they access dict keys
    by name and simply ignore the new one.

    v2.39 — ADDITIVE: also returns assigned_project (APX Attendance),
    for the Settings > Team per-row project-assignment dropdown. Same
    "existing consumers ignore the new key" reasoning as v2.25 above.
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT user_id, full_name, email, role, active, created_at,
                   last_login_at, owner_match_name, assigned_project
            FROM users ORDER BY full_name COLLATE NOCASE
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_user_active(user_id, active, actor_user_id):
    """
    (v2.8) Activate/deactivate a CRM login (Settings > Team). This is
    the SAME 'active' column verify_login() and get_user_by_id() already
    check — no new flag, no new enforcement path. Deactivating someone
    takes effect on their very next request (get_user_by_id() re-reads
    active on every request already); it does NOT kill an already-open
    session token immediately, same behavior as get_user_by_id() always
    had.

    Guard: an admin can't deactivate their OWN account (actor_user_id ==
    user_id) — that would lock them out mid-session with no other admin
    action possible to undo it from inside the app. Deactivating another
    admin is allowed (Srikanth, as the account owner, may need to).

    Returns (ok: bool, message: str).
    """
    if int(user_id) == int(actor_user_id) and not active:
        return False, "You can't deactivate your own account."

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT full_name FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        if not row:
            return False, "User not found."
        conn.execute(
            "UPDATE users SET active=? WHERE user_id=?", (1 if active else 0, user_id)
        )
        conn.commit()
        verb = "activated" if active else "deactivated"
        return True, f"{row['full_name'] or 'User'} {verb}."
    finally:
        conn.close()


def get_lead_score_config():
    """
    (v2.26) Reads app_settings['lead_score_config'], JSON-decodes, and
    returns the dict compute_lead_scores() scores against — superseded
    the module-level LEAD_SCORE_RULES/LEAD_SCORE_BANDS constants (now
    PAUSED above). No caching: this is called at most a few times per
    page load and SQLite WAL reads are cheap, so a cache here would be
    over-engineering (contrast with the project-bucket cache above,
    which is looked up per-lead in tighter loops).
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key='lead_score_config'"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise RuntimeError("lead_score_config is missing from app_settings — run init_db() to seed it.")
    return json.loads(row["setting_value"])


def set_lead_score_config(config_dict):
    """
    (v2.26) Validates then overwrites app_settings['lead_score_config'].
    Required keys: stage_points (all 8 ALL_STAGES), temperature_points,
    site_visit_conducted, site_visit_no_show, follow_up_completed,
    note_points_per_day, call_tap_points_per_day, decay_after_days,
    decay_points_per_period, decay_exempt_stages, hot_threshold,
    warm_threshold.

    Raises ValueError with a clear message (and leaves the OLD config
    untouched in the DB — the write only happens after validation
    passes) if anything is missing or a should-be-numeric field isn't
    a number.
    """
    if not isinstance(config_dict, dict):
        raise ValueError("Lead score config must be a dict.")

    missing = []

    stage_points = config_dict.get("stage_points")
    if not isinstance(stage_points, dict):
        missing.append("stage_points")
    else:
        for stage in ALL_STAGES:
            if stage not in stage_points:
                missing.append(f"stage_points.{stage}")
            elif not isinstance(stage_points[stage], (int, float)) or isinstance(stage_points[stage], bool):
                raise ValueError(f"stage_points.{stage} must be a number.")

    if not isinstance(config_dict.get("temperature_points"), dict):
        missing.append("temperature_points")

    if not isinstance(config_dict.get("decay_exempt_stages"), list):
        missing.append("decay_exempt_stages")

    for key in _LEAD_SCORE_CONFIG_REQUIRED_NUMERIC:
        if key not in config_dict:
            missing.append(key)
        elif not isinstance(config_dict[key], (int, float)) or isinstance(config_dict[key], bool):
            raise ValueError(f"'{key}' must be a number.")

    if missing:
        raise ValueError(f"Lead score config is missing required key(s): {', '.join(missing)}")

    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
            ("lead_score_config", json.dumps(config_dict), _now())
        )
        conn.commit()
    finally:
        conn.close()


def compute_lead_scores(cls_ids):
    """
    Batch lead scoring (v2.2) — one connection, one pass, for however
    many leads the caller needs scored (a page of leads_list, or the
    single lead on lead_detail). Returns {cls_id: {"score": int,
    "band": "Hot"/"Warm"/"Cold"}}.

    Deliberately live-computed, not a stored column — see the v2.2
    changelog for why. Reads: leads.current_stage, leads.
    opportunity_temperature, leads.cls_updated_at (for staleness
    decay), and activity_log (for conducted visits, completed
    follow-ups, notes, and call taps). All point values come from
    get_lead_score_config() (v2.26 — was the module-level
    LEAD_SCORE_RULES/LEAD_SCORE_BANDS constants; edit via
    /settings/lead-scoring or set_lead_score_config(), not this
    function, to retune) — read fresh on every call, so a config
    change takes effect immediately with no restart needed.
    """
    if not cls_ids:
        return {}

    conn = _connect()
    try:
        placeholders = ",".join("?" * len(cls_ids))

        leads = conn.execute(f"""
            SELECT cls_id, current_stage, opportunity_temperature, cls_updated_at
            FROM leads WHERE cls_id IN ({placeholders})
        """, cls_ids).fetchall()

        activity_rows = conn.execute(f"""
            SELECT cls_id, activity_type, created_at
            FROM activity_log WHERE cls_id IN ({placeholders})
        """, cls_ids).fetchall()

        activity_by_lead = {}
        for a in activity_rows:
            activity_by_lead.setdefault(a["cls_id"], []).append(a)

        rules = get_lead_score_config()
        results = {}

        for l in leads:
            cls_id = l["cls_id"]
            score = rules["stage_points"].get(l["current_stage"], 0)

            if l["current_stage"] == "Opportunity" and l["opportunity_temperature"] in rules["temperature_points"]:
                score += rules["temperature_points"][l["opportunity_temperature"]]

            note_days, call_days = set(), set()
            for a in activity_by_lead.get(cls_id, []):
                atype = a["activity_type"]
                day = (a["created_at"] or "")[:10]
                if atype == "site_visit_conducted":
                    score += rules["site_visit_conducted"]
                elif atype == "site_visit_no_show":
                    score += rules["site_visit_no_show"]
                elif atype == "follow_up_completed":
                    score += rules["follow_up_completed"]
                elif atype == "note":
                    note_days.add(day)
                elif atype == "call_attempted":
                    call_days.add(day)

            score += len(note_days) * rules["note_points_per_day"]
            score += len(call_days) * rules["call_tap_points_per_day"]

            # Staleness decay — skipped entirely for exempt stages.
            if (l["current_stage"] not in rules["decay_exempt_stages"]
                    and l["cls_updated_at"]):
                try:
                    last_touch = datetime.strptime(l["cls_updated_at"], "%Y-%m-%d %H:%M:%S")
                    stale_days = (datetime.now() - last_touch).days
                    if stale_days >= rules["decay_after_days"]:
                        periods = stale_days // rules["decay_after_days"]
                        score += rules["decay_points_per_period"] * periods
                except ValueError:
                    pass  # malformed/legacy timestamp — skip decay, don't crash scoring

            score = max(0, score)
            if score >= rules["hot_threshold"]:
                band = "Hot"
            elif score >= rules["warm_threshold"]:
                band = "Warm"
            else:
                band = "Cold"

            results[cls_id] = {"score": score, "band": band}

        return results
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# NORMALIZATION  —  the rules that decide whether two leads match
# ─────────────────────────────────────────────────────────────
# CRITICAL: every job MUST use these. If Job A stores "+919876543210"
# and Job B stores "9876543210", the SAME lead never matches. By
# routing all phone/email cleaning through here, both sides agree.

def norm_phone(raw):
    """
    India phone normalization.
      '+91 98765 43210'  -> '9876543210'
      '098765 43210'     -> '9876543210'
      '919876543210.0'   -> '9876543210'   (pandas float artefact)
    Rule: strip everything non-digit, then take the LAST 10 digits.
          The last 10 are the true subscriber number; country code
          (91) and leading 0 fall away naturally.
    Returns '' if no usable number.
    """
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    if s in ("nan", "none", ""):
        return ""
    # Strip the pandas float artefact FIRST. A CSV phone read by pandas
    # arrives as '919876543210.0'. If we extracted digits naively, the
    # trailing '0' of '.0' would become a real digit -> wrong number.
    if s.endswith(".0"):
        s = s[:-2]
    digits = re.sub(r"\D", "", s)   # keep digits only
    if len(digits) >= 10:
        return digits[-10:]         # last 10 = subscriber number
    return ""                       # too short to be a real Indian mobile


def norm_email(raw):
    """
    Email normalization: lowercase + trim.
    Returns '' for blank/nan/none — and the matcher treats '' as
    'no email', so two blank emails NEVER match each other.
    """
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    if s in ("nan", "none", ""):
        return ""
    if "@" not in s:                # not an email at all
        return ""
    return s


# ─────────────────────────────────────────────────────────────
# MATCHING  —  tiered fallback: phone+email > phone > email
# ─────────────────────────────────────────────────────────────

def find_match(conn, phone_norm, email_norm):
    """
    Find an existing CLS row that matches the given normalized keys.
    Returns (cls_id, match_tier) or (None, 'unmatched').

    TIERED FALLBACK (your "use both" decision, as OR-logic):
      Tier 1  phone AND email both agree  -> highest confidence
      Tier 2  phone agrees                -> high   (phone is reliable in India)
      Tier 3  email agrees                -> medium
      else    no match                    -> caller will INSERT a new row

    Blank keys are skipped entirely — never match on an empty value.
    """
    # Tier 1: both keys present and both match the same row
    if phone_norm and email_norm:
        r = conn.execute(
            "SELECT cls_id FROM leads WHERE phone_norm=? AND email_norm=? LIMIT 1",
            (phone_norm, email_norm)
        ).fetchone()
        if r:
            return r["cls_id"], "phone+email"

    # Tier 2: phone matches
    if phone_norm:
        r = conn.execute(
            "SELECT cls_id FROM leads WHERE phone_norm=? LIMIT 1",
            (phone_norm,)
        ).fetchone()
        if r:
            return r["cls_id"], "phone"

    # Tier 3: email matches
    if email_norm:
        r = conn.execute(
            "SELECT cls_id FROM leads WHERE email_norm=? LIMIT 1",
            (email_norm,)
        ).fetchone()
        if r:
            return r["cls_id"], "email"

    return None, "unmatched"


# ─────────────────────────────────────────────────────────────
# UPSERT  —  Job A:  insert/update a row from a META lead
# ─────────────────────────────────────────────────────────────

def _apply_reengagement_marker(conn, cls_id, prev_stage, now):
    """
    (v2.20, Task 3) Called from INSIDE upsert_meta_lead()'s existing
    transaction, right before its enrich-branch UPDATE, whenever a
    contact match is found for a leadgen_id-less Meta lead — i.e. an
    existing contact is genuinely re-entering through Meta. Any FUTURE
    webhook/API ingestion function that re-matches an existing contact
    this same way should call this SAME helper rather than
    reimplementing the logic.

    Always stamps reengaged_at=now on the matched row. Additionally
    resets it back to the top of the funnel (current_stage='Incoming',
    stage_updated_at=now, stage_reason=NULL) when prev_stage is "dead
    enough" to restart — see RESET_STAGES_ON_REENGAGEMENT. Any other
    prev_stage is left exactly as-is by this helper — the caller's own
    COALESCE-based field merge (unchanged) handles retaining it.

    This is a raw sync write, like Job A/B's other writes on this row —
    it deliberately does NOT go through update_lead_stage()'s
    STAGE_TRANSITIONS validation gate, which exists for CRM-initiated
    user actions only, not pipeline sync writes.

    KNOWN LIMITATION (flagged, not built): a Booked->Incoming reset
    does NOT also auto-cancel any open site visit/follow-up via
    _auto_cancel_open_schedules() — deliberately skipped since Booked
    leads essentially never have anything open scheduled; revisit if
    that assumption turns out to be wrong in practice.

    v2.57: does NOT itself write an activity_log row. upsert_meta_lead()
    logs the 'lead_reengaged' row immediately after calling this helper
    instead, because that description needs phone_raw/email_raw/
    meta_campaign_name — none of which this helper's signature carries,
    and this signature is deliberately not being expanded to take them.
    A future caller of this helper is responsible for its own
    'lead_reengaged' logging the same way, using the SAME `now` passed
    in here.
    """
    if prev_stage in RESET_STAGES_ON_REENGAGEMENT:
        conn.execute("""
            UPDATE leads SET reengaged_at=?, current_stage='Incoming',
                stage_updated_at=?, stage_reason=NULL
            WHERE cls_id=?
        """, (now, now, cls_id))
    else:
        conn.execute("UPDATE leads SET reengaged_at=? WHERE cls_id=?", (now, cls_id))


def _owner_on_leave_today(conn, owner_full_name, today_str):
    """(v2.86) True if owner_full_name's attendance.status for today_str
    is 'leave' or 'weekoff' — the only two statuses set in advance via
    self-service (SELF_SERVICE_ATTENDANCE_STATUSES), so the only ones a
    real-time routing decision can act on. 'absent' is deliberately NOT
    checked here — it's only known after the fact, never ahead of time.
    Returns False (treat as available) if the owner can't be resolved
    to a user_id, or has no attendance row for today at all — 'no data'
    must never block a lead from being routed."""
    row = conn.execute(
        "SELECT a.status FROM attendance a "
        "JOIN users u ON u.user_id = a.user_id "
        "WHERE u.full_name = ? AND a.attendance_date = ?",
        (owner_full_name, today_str)
    ).fetchone()
    return bool(row and row["status"] in ("leave", "weekoff"))


def resolve_owner_for_new_lead(conn, campaign_name):
    """
    (v2.25) Decide the placeholder owner for a genuinely-new Meta lead
    (upsert_meta_lead() branch 3 only), superseding the old project-keyed
    DEFAULT_OWNER_BY_PROJECT dict. Takes the SAME OPEN CONNECTION the
    insert is happening on, so a round-robin cursor increment and the
    lead insert commit together as one transaction — never two separate
    connections that could interleave with a concurrent call.

    Rules, checked in order:
      1. Blank/None campaign_name -> app_settings['default_fallback_owner'].
      2. No ACTIVE campaign_routing_rules row matches (case-insensitive)
         -> same fallback.
      3. rule_type='single' -> owners[0].
      4. rule_type='round_robin' -> owners[next_index % len(owners)],
         then next_index is incremented on that same row (same conn,
         not yet committed here — the caller's own commit covers it).
         (v2.86) Leave-aware: if that picked owner is on 'leave' or
         'weekoff' today (_owner_on_leave_today()), the next available
         owner in rotation order is picked instead — next_index itself
         still advances by exactly 1, unaffected by the skip, so
         rotation resumes exactly where it left off. Falls back to the
         originally-scheduled owner if everyone in rotation is on
         leave/weekoff today, rather than leaving the lead unassigned.
         rule_type='single' is untouched by this — it always returns
         owners[0] regardless of attendance.

    Job B's own upsert (upsert_selldo_lead()) always overwrites this
    placeholder with the real Sell.do "Attended By" the moment it syncs
    successfully — same posture as the dict this replaces.
    """
    fallback_row = conn.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key='default_fallback_owner'"
    ).fetchone()
    fallback_owner = fallback_row["setting_value"] if fallback_row else "Mounika Peddi"

    if not campaign_name or not campaign_name.strip():
        return fallback_owner

    rule = conn.execute(
        "SELECT id, rule_type, owners, next_index FROM campaign_routing_rules "
        "WHERE campaign_name=? AND active=1",
        (campaign_name.strip(),)
    ).fetchone()

    if not rule:
        return fallback_owner

    owners = json.loads(rule["owners"])
    if not owners:
        return fallback_owner

    if rule["rule_type"] == "single":
        return owners[0]

    # round_robin
    # (v2.86) Leave-aware: the originally-scheduled owner (by cursor
    # position) is skipped in favor of the next available teammate in
    # rotation order if they're on 'leave'/'weekoff' today
    # (_owner_on_leave_today) — but the cursor itself still advances by
    # exactly 1 per lead, unaffected by any skip, so rotation resumes
    # exactly where it left off with zero extra state. If EVERY owner is
    # on leave/weekoff today, `picked` falls back to the originally
    # scheduled owner rather than leaving the lead unassigned.
    today_str = _now()[:10]
    original_index = rule["next_index"] % len(owners)
    picked = owners[original_index]
    if _owner_on_leave_today(conn, picked, today_str):
        for offset in range(1, len(owners)):
            candidate = owners[(original_index + offset) % len(owners)]
            if not _owner_on_leave_today(conn, candidate, today_str):
                picked = candidate
                break
        # loop never broke -> everyone's on leave/weekoff -> `picked`
        # stays the originally scheduled owner (intended fallback).
    conn.execute(
        "UPDATE campaign_routing_rules SET next_index = next_index + 1 WHERE id=?",
        (rule["id"],)
    )
    return picked


def list_campaign_routing_rules():
    """(v2.25) All campaign routing rules, owners JSON-decoded, for the
    /settings/campaign-routing admin screen."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, campaign_name, rule_type, owners, next_index, active, "
            "created_at, updated_at FROM campaign_routing_rules ORDER BY campaign_name COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d["owners"] = json.loads(d["owners"])
        result.append(d)
    return result


def upsert_campaign_routing_rule(campaign_name, rule_type, owners_list):
    """
    (v2.25) Create or update a campaign routing rule. Validates
    rule_type and owner-count requirements; raises ValueError with a
    clear message on rejection.

    next_index is reset to 0 ONLY if the owners list actually changed
    from what's currently stored — re-saving the same list (e.g. just
    flipping active) must not reset a live round-robin rotation.
    """
    campaign_name = (campaign_name or "").strip()
    if not campaign_name:
        raise ValueError("Campaign name is required.")
    if rule_type not in ("single", "round_robin"):
        raise ValueError("Rule type must be 'single' or 'round_robin'.")
    if not owners_list:
        raise ValueError("At least one owner is required.")
    if rule_type == "single" and len(owners_list) != 1:
        raise ValueError("A Single rule takes exactly one owner.")
    if rule_type == "round_robin" and len(owners_list) < 2:
        raise ValueError("A Round Robin rule needs at least 2 owners.")

    now = _now()
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT owners FROM campaign_routing_rules WHERE campaign_name=?",
            (campaign_name,)
        ).fetchone()

        owners_changed = True
        if existing:
            try:
                owners_changed = json.loads(existing["owners"]) != list(owners_list)
            except (ValueError, TypeError):
                owners_changed = True

        next_index = 0 if owners_changed else None  # None = "keep existing" below

        if existing:
            if next_index is None:
                conn.execute("""
                    UPDATE campaign_routing_rules
                    SET rule_type=?, owners=?, active=1, updated_at=?
                    WHERE campaign_name=?
                """, (rule_type, json.dumps(list(owners_list)), now, campaign_name))
            else:
                conn.execute("""
                    UPDATE campaign_routing_rules
                    SET rule_type=?, owners=?, next_index=0, active=1, updated_at=?
                    WHERE campaign_name=?
                """, (rule_type, json.dumps(list(owners_list)), now, campaign_name))
        else:
            conn.execute("""
                INSERT INTO campaign_routing_rules
                    (campaign_name, rule_type, owners, next_index, active, created_at, updated_at)
                VALUES (?, ?, ?, 0, 1, ?, ?)
            """, (campaign_name, rule_type, json.dumps(list(owners_list)), now, now))
        conn.commit()
    finally:
        conn.close()


def set_campaign_routing_rule_active(campaign_name, active):
    """(v2.25) Toggle a rule's active flag only — leaves owners/rule_type/
    next_index untouched. Narrower than upsert_campaign_routing_rule(),
    which always sets active=1 on save; the active toggle on
    /settings/campaign-routing needs to flip it independently of a
    full re-save."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE campaign_routing_rules SET active=?, updated_at=? WHERE campaign_name=?",
            (1 if active else 0, _now(), campaign_name)
        )
        conn.commit()
    finally:
        conn.close()


def delete_campaign_routing_rule(campaign_name):
    """(v2.25) Delete one campaign routing rule. A campaign left without
    a rule simply falls back to the default fallback owner — no
    blocking logic needed."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM campaign_routing_rules WHERE campaign_name=?", (campaign_name,))
        conn.commit()
    finally:
        conn.close()


def list_cross_reassign_rules():
    """(v2.77) All cross-project reassign rules for the /settings/
    cross-reassign admin screen. Same shape as
    list_campaign_routing_rules() — owners JSON-decoded before
    returning, ordered by source_bucket then target_bucket."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, source_bucket, target_bucket, rule_type, owners, next_index, "
            "active, created_at, updated_at FROM cross_project_reassign_rules "
            "ORDER BY source_bucket COLLATE NOCASE, target_bucket COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d["owners"] = json.loads(d["owners"])
        result.append(d)
    return result


def upsert_cross_reassign_rule(source_bucket, target_bucket, rule_type, owners_list, active=True):
    """
    (v2.77) Create or update one cross-project reassign rule — unique on
    (source_bucket, target_bucket), the table's own UNIQUE constraint.
    Mirrors upsert_campaign_routing_rule() exactly in style and
    validation approach.

    Validates:
      - source_bucket != target_bucket (no self-loop)
      - rule_type in ('single', 'round_robin')
      - owners_list non-empty
      - rule_type == 'single' requires exactly 1 owner

    next_index resets to 0 ONLY if the owners list actually changed from
    what's currently stored — same rule as upsert_campaign_routing_rule(),
    so re-saving unchanged owners (e.g. just toggling active) doesn't
    reset a live rotation.

    Raises ValueError with a clear message on any validation failure.
    """
    source_bucket = (source_bucket or "").strip()
    target_bucket = (target_bucket or "").strip()
    if not source_bucket or not target_bucket:
        raise ValueError("Source and target project are both required.")
    if source_bucket.lower() == target_bucket.lower():
        raise ValueError("Source and target project can't be the same.")
    if rule_type not in ("single", "round_robin"):
        raise ValueError("Rule type must be 'single' or 'round_robin'.")
    if not owners_list:
        raise ValueError("At least one owner is required.")
    if rule_type == "single" and len(owners_list) != 1:
        raise ValueError("A Single rule takes exactly one owner.")

    now = _now()
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT owners FROM cross_project_reassign_rules WHERE source_bucket=? AND target_bucket=?",
            (source_bucket, target_bucket)
        ).fetchone()

        owners_changed = True
        if existing:
            try:
                owners_changed = json.loads(existing["owners"]) != list(owners_list)
            except (ValueError, TypeError):
                owners_changed = True

        next_index = 0 if owners_changed else None  # None = "keep existing" below

        if existing:
            if next_index is None:
                conn.execute("""
                    UPDATE cross_project_reassign_rules
                    SET rule_type=?, owners=?, active=?, updated_at=?
                    WHERE source_bucket=? AND target_bucket=?
                """, (rule_type, json.dumps(list(owners_list)), 1 if active else 0, now,
                      source_bucket, target_bucket))
            else:
                conn.execute("""
                    UPDATE cross_project_reassign_rules
                    SET rule_type=?, owners=?, next_index=0, active=?, updated_at=?
                    WHERE source_bucket=? AND target_bucket=?
                """, (rule_type, json.dumps(list(owners_list)), 1 if active else 0, now,
                      source_bucket, target_bucket))
        else:
            conn.execute("""
                INSERT INTO cross_project_reassign_rules
                    (source_bucket, target_bucket, rule_type, owners, next_index, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """, (source_bucket, target_bucket, rule_type, json.dumps(list(owners_list)),
                  1 if active else 0, now, now))
        conn.commit()
    finally:
        conn.close()


def delete_cross_reassign_rule(rule_id):
    """(v2.77) Deletes one cross-project reassign rule row. No blocking
    logic needed — same posture as delete_project_alias(): if a lead's
    source_bucket has no active rule at the time it goes Lost/
    Unqualified, _auto_cross_reassign_project() already no-ops safely."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM cross_project_reassign_rules WHERE id=?", (rule_id,))
        conn.commit()
    finally:
        conn.close()


def get_fallback_owner():
    """(v2.25) Reads app_settings['default_fallback_owner']."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key='default_fallback_owner'"
        ).fetchone()
    finally:
        conn.close()
    return row["setting_value"] if row else "Mounika Peddi"


def set_fallback_owner(name):
    """(v2.25) Writes app_settings['default_fallback_owner']."""
    name = (name or "").strip()
    if not name:
        raise ValueError("A fallback owner name is required.")
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
            ("default_fallback_owner", name, _now())
        )
        conn.commit()
    finally:
        conn.close()


def _format_meta_created_time(raw):
    """
    (v2.28) Meta's created_time ('2026-05-21T10:30:00+0530') converted
    to CLS's own "%Y-%m-%d %H:%M:%S" format (_now()'s format) — used to
    backdate a lead_entered activity_log row to when the lead actually
    arrived, not when Job A happened to poll it. Same two-format
    try/except as meta_leads_fetcher.py's newest_meta_time_for_form().
    Falls back to _now() if raw is blank or unparseable — this is a
    display-only value, never used for matching/business logic, so a
    safe fallback beats raising.

    (v2.74) The tz-aware branch ("%Y-%m-%dT%H:%M:%S%z") now converts to
    IST via .astimezone(IST) before formatting — previously it kept the
    parsed datetime's original wall-clock digits (whatever offset Meta
    sent) and just relabeled them, which silently displayed UTC-offset
    times as if they were IST. The naive branch ("%Y-%m-%d %H:%M:%S")
    is untouched: it carries no tzinfo, is already a CLS-format local
    timestamp, and needs no conversion.
    """
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z") \
                .astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return _now()


def upsert_meta_lead(leadgen_id, form_id, project, full_name,
                     phone_raw, email_raw, meta_created_time, campaign=None,
                     meta_campaign_id=None, meta_campaign_name=None,
                     meta_adset_id=None, meta_adset_name=None,
                     meta_ad_id=None, meta_ad_name=None, meta_platform=None,
                     extra_answers=None):
    """
    Called by meta_leads_fetcher.py (Job A) for each Facebook lead.

    LOGIC:
      1. Normalize phone + email.
      2. If this leadgen_id already exists -> update it (idempotent;
         re-pulling the same lead does no harm).
      3. Else try to match an existing row by phone/email. If a
         Sell.do-only row already exists for this person, we ENRICH
         it with the leadgen_id rather than creating a duplicate.
      4. Else insert a brand-new row, source='meta'.

    campaign (v2.25, optional): only used at true first-insert time
    (branch 3 / "genuinely new lead" below), exactly mirroring how
    lead_owner is handled — passed to resolve_owner_for_new_lead() to
    pick the placeholder owner via Campaign Routing, then stored as-is
    on the new row. Branches 1/2 (leadgen_id refresh, contact-match
    enrich) leave campaign untouched, same as before this parameter
    existed — omitting it entirely (old call sites) defaults to None,
    which resolve_owner_for_new_lead() treats as "use the fallback
    owner", identical to pre-v2.25 behavior.

    meta_campaign_id / meta_campaign_name / meta_adset_id /
    meta_adset_name / meta_ad_id / meta_ad_name (v2.27, all optional):
    Meta's own real Graph-API ad/campaign metadata, stored as direct
    overwrites on every branch (idempotent — a re-pull of the same
    lead always carries the same values). Deliberately separate from
    the campaign column/Campaign Routing above — meta_ prefix avoids
    any confusion between Meta's own campaign_name and LEAD_FORMS's
    unrelated "campaign_name" routing config key.

    meta_platform (v2.32, optional): Meta's "platform" field (e.g.
    "fb"/"ig"), from meta_leads_fetcher.py v1.6+. Same idempotent
    direct-overwrite treatment as the other meta_ fields on branches 1
    and 3 (branch 2's contact-match enrich path leaves it untouched,
    identical to how the other meta_ fields are handled there today).

    extra_answers (v2.28, optional): ordered list of {"question",
    "answer"} dicts — any instant-form field_data entries that didn't
    match meta_leads_fetcher.py's name/phone/email alias sets (from
    extract_lead_fields() v1.5+). Used ONLY at true first-insert time
    (branch 3 below), appended to that lead's lead_entered activity_log
    description. Free text, log-only — never written to a column, never
    read back into any matching/scoring logic.

    Returns the cls_id of the affected row.
    """
    phone_norm = norm_phone(phone_raw)
    email_norm = norm_email(email_raw)
    now = _now()

    conn = _connect()
    try:
        # ── 1. Already have this exact Meta lead? Update in place. ──
        existing = conn.execute(
            "SELECT cls_id FROM leads WHERE leadgen_id=? LIMIT 1",
            (leadgen_id,)
        ).fetchone()

        if existing:
            cls_id = existing["cls_id"]
            conn.execute("""
                UPDATE leads SET
                    form_id=?, project=?, project_bucket=?, full_name=?,
                    phone_raw=?, phone_norm=?, email_raw=?, email_norm=?,
                    meta_created_time=?,
                    meta_campaign_id=?, meta_campaign_name=?,
                    meta_adset_id=?, meta_adset_name=?,
                    meta_ad_id=?, meta_ad_name=?, meta_platform=?,
                    cls_updated_at=?
                WHERE cls_id=?
            """, (form_id, project, get_project_bucket(project), full_name,
                  phone_raw, phone_norm, email_raw, email_norm,
                  meta_created_time,
                  meta_campaign_id, meta_campaign_name,
                  meta_adset_id, meta_adset_name,
                  meta_ad_id, meta_ad_name, meta_platform,
                  now, cls_id))
            conn.commit()
            return cls_id, False   # v2.55 — leadgen_id refresh, not a new lead

        # ── 2. No leadgen_id row — does a contact match exist? (enrich it) ──
        cls_id, tier = find_match(conn, phone_norm, email_norm)
        if cls_id:
            # v2.20 — Task 3: this contact-match IS the reengagement
            # trigger point (branch 2 only — never branch 1's same-
            # leadgen_id refresh above, never branch 3's brand-new
            # insert below). Read the matched row's stage BEFORE any
            # UPDATE below touches it, so the reset decision uses the
            # genuine pre-sync value.
            prev_row = conn.execute(
                "SELECT current_stage, project, full_name, lead_owner FROM leads WHERE cls_id=?", (cls_id,)
            ).fetchone()
            _apply_reengagement_marker(conn, cls_id, prev_row["current_stage"] if prev_row else None, now)

            # v2.64 — F2 Phase 1: project_bucket must track whatever the
            # UPDATE below's project=COALESCE(project,?) will actually
            # leave in the project column — computed here in Python from
            # the SAME pre-update row just read above, so it matches
            # exactly rather than being independently (and possibly
            # inconsistently) COALESCE'd in SQL.
            effective_project = (prev_row["project"] if prev_row and prev_row["project"] else project)

            # v2.57 — Task 3 Part A, Change 4: log a lead_reengaged
            # activity_log row at the SAME `now` used to stamp
            # reengaged_at above (not a fresh _now() call) — a second,
            # slightly later timestamp here would make
            # get_reengaged_count()/get_reengaged_leads() (which clear a
            # lead the moment created_at > reengaged_at) immediately
            # drop this lead off the Reengaged card, which is wrong: a
            # system-generated re-entry record isn't a human touching
            # the lead. Same labeled multi-line block convention as
            # branch 3's lead_entered description below (label: value
            # per line, blank fields omitted).
            reengage_parts = [("Lead Source", "Facebook Lead Ads")]
            if meta_campaign_name:
                reengage_parts.append(("Campaign Name", meta_campaign_name))
            if phone_raw:
                reengage_parts.append(("Lead Contact", phone_raw))
            if email_raw:
                reengage_parts.append(("Lead Email", email_raw))
            reengage_description = (
                "Lead Re-Engaged — previously enquired, submitted a new enquiry.\n"
                + "\n".join(f"{label}: {value}" for label, value in reengage_parts)
            )
            _log_activity(conn, cls_id, "lead_reengaged", "system",
                          description=reengage_description, created_at=now)

            # v2.72 — Notifications v1.0: notify the CURRENT owner (the
            # pre-update row's lead_owner — this branch's UPDATE below
            # never changes lead_owner, only project/leadgen_id/etc, so
            # prev_row's value is also the post-update value). Uses
            # prev_row's own full_name (COALESCE(NULLIF(...))'d the same
            # way the UPDATE below does) so the message shows the name
            # already on file, not a blank incoming Meta name.
            reengaged_owner_user_id = resolve_user_id_from_owner_name(
                prev_row["lead_owner"] if prev_row else None
            )
            if reengaged_owner_user_id:
                reengaged_full_name = (prev_row["full_name"] if prev_row and prev_row["full_name"] else full_name) or "(no name)"
                message = NOTIFICATION_EVENTS["lead_reengaged"].format(full_name=reengaged_full_name)
                insert_notification(reengaged_owner_user_id, cls_id, "lead_reengaged", message, conn=conn)
                send_fcm_push(reengaged_owner_user_id, "Lead re-engaged", message)

            # An existing row (likely selldo_only) is the same person.
            # Stamp the leadgen_id onto it — this is the back-fill case.
            conn.execute("""
                UPDATE leads SET
                    leadgen_id=?, form_id=?, project=COALESCE(project,?),
                    project_bucket=?,
                    full_name=COALESCE(NULLIF(full_name,''),?),
                    meta_created_time=?,
                    meta_campaign_id=?, meta_campaign_name=?,
                    meta_adset_id=?, meta_adset_name=?,
                    meta_ad_id=?, meta_ad_name=?,
                    cls_updated_at=?
                WHERE cls_id=?
            """, (leadgen_id, form_id, project, get_project_bucket(effective_project), full_name,
                  meta_created_time,
                  meta_campaign_id, meta_campaign_name,
                  meta_adset_id, meta_adset_name,
                  meta_ad_id, meta_ad_name,
                  now, cls_id))
            conn.commit()
            return cls_id, False   # v2.55 — contact-match enrich, not a new lead

        # ── 3. Genuinely new lead — insert. ──
        cls_id = str(uuid.uuid4())
        default_owner = resolve_owner_for_new_lead(conn, campaign)

        def _do_insert(crm_lead_no):
            conn.execute("""
                INSERT INTO leads (
                    cls_id, leadgen_id, form_id, project, project_bucket, full_name,
                    phone_raw, phone_norm, email_raw, email_norm,
                    meta_created_time, source, crm_lead_no,
                    current_stage, stage_updated_at, lead_owner, campaign,
                    meta_campaign_id, meta_campaign_name,
                    meta_adset_id, meta_adset_name,
                    meta_ad_id, meta_ad_name, meta_platform,
                    cls_created_at, cls_updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cls_id, leadgen_id, form_id, project, get_project_bucket(project), full_name,
                  phone_raw, phone_norm, email_raw, email_norm,
                  meta_created_time, "meta", crm_lead_no,
                  "Incoming", now, default_owner, campaign,
                  meta_campaign_id, meta_campaign_name,
                  meta_adset_id, meta_adset_name,
                  meta_ad_id, meta_ad_name, meta_platform,
                  now, now))

        crm_lead_no = _insert_lead_with_lead_no_retry(conn, _do_insert)

        # v2.28 — Task 2.1: one lead_entered row at the exact moment
        # this lead first exists in CLS, backdated to Meta's own
        # created_time (not "now", which is just whenever Job A polled
        # it).
        # v2.32 — rebuilt as a labeled, multi-line block (one field per
        # line, fixed order) instead of the old single-line prose
        # ("Lead entered via campaign 'X' / adset 'Y' — Name: ..."),
        # so lead_detail.html can render it plainly without re-parsing
        # prose. Same "omit rather than print None" convention as
        # before — a blank field just isn't a line, never "None".
        # Scoped to THIS branch only (genuinely-new Meta lead) — Job B's
        # upsert_selldo_lead() and the CRM's create_manual_lead() keep
        # their own existing single-line lead_entered descriptions
        # untouched.
        line_parts = [("Lead Source", "Facebook Lead Ads")]
        if leadgen_id:
            line_parts.append(("Leadgen Id", leadgen_id))
        if meta_campaign_name:
            line_parts.append(("Campaign Name", meta_campaign_name))
        if meta_adset_name:
            line_parts.append(("Adset Name", meta_adset_name))
        if meta_ad_name:
            line_parts.append(("Ad Name", meta_ad_name))
        if meta_platform:
            line_parts.append(("Platform", meta_platform))
        if full_name:
            line_parts.append(("Lead Name", full_name))
        if phone_raw:
            line_parts.append(("Lead Contact", phone_raw))
        if email_raw:
            line_parts.append(("Lead Email", email_raw))

        description = "\n".join(f"{label}: {value}" for label, value in line_parts)

        if extra_answers:
            qa = "; ".join(
                f"{a.get('question')}: {a.get('answer')}"
                for a in extra_answers if a.get("answer")
            )
            if qa:
                description += f"\nAlso answered — {qa}"

        _log_activity(conn, cls_id, "lead_entered", "system",
                      description=description,
                      created_at=_format_meta_created_time(meta_created_time))

        # v2.72 — Notifications v1.0: notify default_owner (resolved
        # above via resolve_owner_for_new_lead()) if that placeholder
        # name is actually linked to a login. If not (e.g. the
        # app_settings default_fallback_owner name was never given a
        # login), fall back to every active admin — a brand-new
        # enquiry must always reach SOMEONE, never silently land on an
        # unmonitored name.
        new_enquiry_message = NOTIFICATION_EVENTS["new_enquiry"].format(
            full_name=full_name or "(no name)", project=project or "(no project)"
        )
        new_enquiry_owner_id = resolve_user_id_from_owner_name(default_owner)
        new_enquiry_targets = [new_enquiry_owner_id] if new_enquiry_owner_id else _get_admin_user_ids(conn)
        for target_user_id in new_enquiry_targets:
            insert_notification(target_user_id, cls_id, "new_enquiry", new_enquiry_message, conn=conn)
            send_fcm_push(target_user_id, "New enquiry", new_enquiry_message)

        conn.commit()
        return cls_id, True   # v2.55 — genuinely new lead
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# UPSERT  —  Job B:  insert/update a row from a SELL.DO lead
# ─────────────────────────────────────────────────────────────

def upsert_selldo_lead(selldo_lead_id, project, full_name,
                       phone_raw, email_raw, current_stage,
                       lead_owner="", selldo_url="", opportunity_temperature=""):
    """
    Called by selldo_to_cls.py (Job B) for each Sell.do lead row.

    LOGIC (Risk 3 fix — upsert, never discard):
      1. Normalize phone + email.
      2. Try to match an existing CLS row (a Meta lead, ideally).
         - Match found  -> UPDATE its CRM stage + match_tier.
         - No match     -> INSERT a new row, source='selldo_only',
                           leadgen_id stays NULL. The lead is still
                           captured; it just can't be leadgen-enriched.
      3. stage_updated_at moves only when the stage actually changes,
         so Job C can tell a real transition from a no-op refresh.

    v1.3: lead_owner (Sell.do "Attended By") and selldo_url (profile
    link extracted from =HYPERLINK cell) added. Both default to "" so
    callers that omit them continue to work without error.

    v1.8: opportunity_temperature (Sell.do's separate Warm/Hot status
    column, meaningful only when current_stage='Opportunity') added,
    same default-"" backward-compatible pattern. Purely additive —
    does not affect current_stage, matching, or CAPI firing.

    Returns (cls_id, stage_changed_bool).
    """
    phone_norm = norm_phone(phone_raw)
    email_norm = norm_email(email_raw)
    now = _now()

    conn = _connect()
    try:
        # Prefer matching by Sell.do's own id if we've seen it before.
        existing_cols = ("cls_id, current_stage, project, full_name, "
                         "phone_raw, phone_norm, email_raw, email_norm, "
                         "lead_owner, selldo_url, opportunity_temperature")
        existing = conn.execute(
            f"SELECT {existing_cols} FROM leads WHERE selldo_lead_id=? LIMIT 1",
            (selldo_lead_id,)
        ).fetchone()
        match_tier = "selldo_id"

        if not existing:
            # Fall back to phone/email matching against Meta-sourced rows.
            cls_id, match_tier = find_match(conn, phone_norm, email_norm)
            if cls_id:
                existing = conn.execute(
                    f"SELECT {existing_cols} FROM leads WHERE cls_id=?",
                    (cls_id,)
                ).fetchone()

        # ── Existing row -> update CRM stage ──
        if existing:
            cls_id        = existing["cls_id"]
            prev_stage    = existing["current_stage"]
            stage_changed = (prev_stage != current_stage)

            # v2.19 (Option B) — anything_changed mirrors stage_changed's
            # existing pattern, extended to the other COALESCE'd fields
            # this UPDATE can actually change. Computed by predicting, in
            # Python, exactly what each column's post-COALESCE value would
            # be (same NULL/'' rules as the SQL below), then comparing
            # against what's already stored. Without this, cls_updated_at
            # was set to now() unconditionally on EVERY sync pass — even a
            # true no-op — which is why "Upd" read as today for every lead
            # regardless of whether anything had actually changed.
            new_project    = existing["project"] if existing["project"] is not None else project
            new_full_name  = existing["full_name"] or full_name
            new_phone_raw  = existing["phone_raw"] or phone_raw
            new_phone_norm = existing["phone_norm"] or phone_norm
            new_email_raw  = existing["email_raw"] or email_raw
            new_email_norm = existing["email_norm"] or email_norm
            new_lead_owner = lead_owner or existing["lead_owner"]
            new_selldo_url = selldo_url or existing["selldo_url"]
            new_opp_temp   = opportunity_temperature or None

            anything_changed = (
                stage_changed
                or new_project    != existing["project"]
                or new_full_name  != existing["full_name"]
                or new_phone_raw  != existing["phone_raw"]
                or new_phone_norm != existing["phone_norm"]
                or new_email_raw  != existing["email_raw"]
                or new_email_norm != existing["email_norm"]
                or new_lead_owner != existing["lead_owner"]
                or new_selldo_url != existing["selldo_url"]
                or new_opp_temp   != existing["opportunity_temperature"]
            )

            conn.execute("""
                UPDATE leads SET
                    selldo_lead_id=?, current_stage=?, match_tier=?,
                    project=COALESCE(project,?), project_bucket=?,
                    full_name=COALESCE(NULLIF(full_name,''),?),
                    phone_raw=COALESCE(NULLIF(phone_raw,''),?),
                    phone_norm=COALESCE(NULLIF(phone_norm,''),?),
                    email_raw=COALESCE(NULLIF(email_raw,''),?),
                    email_norm=COALESCE(NULLIF(email_norm,''),?),
                    stage_updated_at=CASE WHEN ? THEN ? ELSE stage_updated_at END,
                    lead_owner=COALESCE(NULLIF(?,  ''), lead_owner),
                    selldo_url=COALESCE(NULLIF(?,  ''), selldo_url),
                    opportunity_temperature=?,
                    cls_updated_at=CASE WHEN ? THEN ? ELSE cls_updated_at END
                WHERE cls_id=?
            """, (selldo_lead_id, current_stage, match_tier,
                  project, get_project_bucket(new_project), full_name,
                  phone_raw, phone_norm, email_raw, email_norm,
                  stage_changed, now,
                  lead_owner, selldo_url,
                  opportunity_temperature or None,
                  anything_changed, now, cls_id))
            conn.commit()
            return cls_id, stage_changed

        # ── No match anywhere -> INSERT selldo_only row (Risk 3) ──
        cls_id = str(uuid.uuid4())

        def _do_insert(crm_lead_no):
            conn.execute("""
                INSERT INTO leads (
                    cls_id, leadgen_id, project, project_bucket, full_name,
                    phone_raw, phone_norm, email_raw, email_norm,
                    selldo_lead_id, current_stage, stage_updated_at,
                    match_tier, source, lead_owner, selldo_url,
                    opportunity_temperature, crm_lead_no,
                    cls_created_at, cls_updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cls_id, None, project, get_project_bucket(project), full_name,
                  phone_raw, phone_norm, email_raw, email_norm,
                  selldo_lead_id, current_stage, now,
                  "unmatched", "selldo_only", lead_owner, selldo_url,
                  opportunity_temperature or None, crm_lead_no,
                  now, now))

        crm_lead_no = _insert_lead_with_lead_no_retry(conn, _do_insert)

        # v2.28 — Task 2.1: matches upsert_meta_lead() branch 3's new
        # lead_entered row, for Job B's own ONGOING sync (not the
        # separate historical CSV import, which already logs
        # imported_from_selldo). cls_db.py-only change — selldo_to_cls.py
        # itself is untouched, every one of its writes already routes
        # through this one centralized function.
        _log_activity(conn, cls_id, "lead_entered", "system",
                      description="Lead entered via Sell.do sync.")

        conn.commit()
        return cls_id, True   # brand-new row counts as a change
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# SELL.DO HISTORICAL CSV BULK IMPORT  —  one-time backfill (v2.17)
# ─────────────────────────────────────────────────────────────
# Called ONLY by cls_import_selldo_csv.py, a one-time, unscheduled
# operator-run script — NOT part of the A->B->C->D pipeline and NOT
# selldo_to_cls.py (Job B, which stays untouched). This is Option B:
# the historical Sell.do CSV export's own "Lead's Id" becomes each
# matched/inserted row's crm_lead_no (displayed as "APX-<id>"), so
# CLS's friendly IDs line up with Sell.do's for the whole backfilled
# history.
#
# cls_import_selldo_csv.py owns ALL CSV-format-specific work (reading
# the file with pandas, replacing pandas NaN artefacts with "", trying
# multiple "Created At" date formats, and deduping rows that share a
# phone number). By the time a row dict reaches this function, its
# values are already clean strings and "Created At" is already
# normalized to CLS's own "%Y-%m-%d %H:%M:%S" format (the same one
# _now() produces) — this function does not parse dates itself, only
# validates that what it was given is usable.
#
# csv_row is a dict keyed by the CSV's own column names:
#   "Lead's Id", "First Name", "Last Name", "Lead Stage", "Phone",
#   "Email", "Projects", "First-Campaign", "Attended By", "Created At"
# ("Lead Status", "Secondary Phones", "Secondary Emails",
#  "First-Sub Source", "Attended By Sales Id" are read by the CLI
#  script but never passed in here — nothing downstream needs them.)

def import_selldo_csv_row(csv_row, commit=False):
    """
    Match-or-insert ONE historical Sell.do CSV row against cls.db.

    commit=False (default): read-only. Runs the exact same matching
    logic and returns what WOULD happen, without writing anything —
    this is what powers the CLI script's dry-run preview.
    commit=True: performs the write (INSERT or UPDATE) + activity_log
    entries described below, inside one transaction.

    MATCHING (identical tiered order as find_match() — do not invent
    a new one):
      1. A CLS row already has this EXACT selldo_lead_id -> match.
      2. Else find_match(phone_norm, email_norm) tiered:
         phone+email > phone > email.
      3. Else -> this is a brand-new lead -> insert.

    NEW INSERT sets every guardrail field Srikanth specified so the
    imported row can NEVER trigger a CAPI storm (last_fired_stage /
    last_fired_at pinned to the historical stage/time) or an email
    storm (drip_paused=1, drip_enrolled_at pinned to the historical
    time): source='selldo_only', match_tier='imported'.

    MATCHED existing row: ONLY crm_lead_no (Option B), and selldo_lead_id
    / campaign IF currently NULL/empty (backfill-only, never overwrite —
    Srikanth's Q3/Q4 decisions). current_stage, stage_updated_at,
    project, lead_owner, phone/email, full_name, cls_created_at,
    last_fired_stage/at, and every drip_* column are left exactly as
    they are — Job B's own sync remains the system of record for those
    on a matched (already-CRM-known) lead.

    IDEMPOTENT: running the same CSV twice must not create duplicate
    leads or duplicate activity_log rows. The normal path already
    guarantees this — a row inserted once carries its selldo_lead_id
    forward, so tier-1 matching finds it on every later run and takes
    the update path instead of inserting again. As an explicit extra
    guard (belt-and-suspenders, per spec) the insert path also checks
    activity_log for a pre-existing 'imported_from_selldo' row for this
    exact selldo_lead_id before writing a new one, in case a row's
    selldo_lead_id/phone/email were later edited out from under it.

    Returns a dict:
        {
            "action":  "insert" | "update_id_only" | "update_id_and_backfill"
                      | "skip_duplicate_phone_in_csv" | "skip_invalid_row",
            "cls_id":  <str or None>,
            "prev_crm_lead_no": <int or None>,
            "new_crm_lead_no":  <int or None>,
            "backfilled": [<str>, ...],   # column names actually backfilled
            "warnings":   [<str>, ...],   # human-readable diagnostics
        }

    NOTE: "skip_duplicate_phone_in_csv" is never returned by this
    function itself — that classification happens one level up, in
    cls_import_selldo_csv.py's own dedup pass, BEFORE it ever calls
    this function for the older duplicate rows. It's listed here only
    because it's part of the same result-shape contract the CLI script
    uses for every row (real or synthesized) in its summary counts.
    """
    warnings = []

    def _invalid(msg):
        warnings.append(msg)
        return {
            "action": "skip_invalid_row",
            "cls_id": None,
            "prev_crm_lead_no": None,
            "new_crm_lead_no": None,
            "backfilled": [],
            "warnings": warnings,
        }

    sid = str(csv_row.get("Lead's Id") or "").strip()
    if sid.endswith(".0"):        # pandas float artefact, same rule as norm_phone
        sid = sid[:-2]
    raw_sid = csv_row.get("Lead's Id")
    try:
        crm_lead_no_val = int(sid)
    except (TypeError, ValueError):
        return _invalid("Unusable/non-numeric Lead's Id: {!r}".format(raw_sid))

    created_at_str = str(csv_row.get("Created At") or "").strip()
    try:
        datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return _invalid(f"Unparseable/missing Created At: {created_at_str!r}")

    first_name = str(csv_row.get("First Name") or "").strip()
    last_name  = str(csv_row.get("Last Name") or "").strip()
    full_name  = f"{first_name} {last_name}".strip()

    lead_stage = str(csv_row.get("Lead Stage") or "").strip()

    phone_raw = str(csv_row.get("Phone") or "").strip()
    email_raw = str(csv_row.get("Email") or "").strip()
    phone_norm = norm_phone(phone_raw)
    email_norm = norm_email(email_raw)
    if not phone_norm and not email_norm:
        return _invalid("No usable phone or email to match on")

    projects_raw = str(csv_row.get("Projects") or "").strip()
    project = None
    if projects_raw:
        parts = [p.strip() for p in projects_raw.split(",") if p.strip()]
        if parts:
            project = parts[0]
        if len(parts) > 1:
            warnings.append(f"Multiple projects in CSV ('{projects_raw}'); used first value '{project}'")

    campaign = str(csv_row.get("First-Campaign") or "").strip() or None
    lead_owner = str(csv_row.get("Attended By") or "").strip()  # verbatim, no lookup (Srikanth's Q4 decision)

    now = _now()
    conn = _connect()
    try:
        # ── Tier 0: exact same selldo_lead_id already in CLS -> match ──
        existing = conn.execute(
            "SELECT cls_id FROM leads WHERE selldo_lead_id=? LIMIT 1", (sid,)
        ).fetchone()

        if not existing:
            match_cls_id, _tier = find_match(conn, phone_norm, email_norm)
            if match_cls_id:
                existing = conn.execute(
                    "SELECT cls_id FROM leads WHERE cls_id=?", (match_cls_id,)
                ).fetchone()

        # ═══════════════════════════════════════════════════════
        # MATCHED — an existing CLS lead is this same person
        # ═══════════════════════════════════════════════════════
        if existing:
            cls_id = existing["cls_id"]
            row = conn.execute(
                "SELECT crm_lead_no, selldo_lead_id, campaign FROM leads WHERE cls_id=?",
                (cls_id,)
            ).fetchone()
            prev_crm_lead_no = row["crm_lead_no"]
            backfilled = []
            will_backfill_selldo_id = not row["selldo_lead_id"]
            will_backfill_campaign  = (not row["campaign"]) and campaign

            if commit:
                conn.execute(
                    "UPDATE leads SET crm_lead_no=?, cls_updated_at=? WHERE cls_id=?",
                    (crm_lead_no_val, now, cls_id)
                )
                if prev_crm_lead_no != crm_lead_no_val:
                    _log_activity(
                        conn, cls_id, "lead_id_changed_from_import", "cls_import_selldo_csv",
                        prev_value=(str(prev_crm_lead_no) if prev_crm_lead_no is not None else None),
                        new_value=str(crm_lead_no_val),
                        description="Lead ID changed to match Sell.do ID from imported_from_selldo",
                    )

                if will_backfill_selldo_id:
                    conn.execute("UPDATE leads SET selldo_lead_id=? WHERE cls_id=?", (sid, cls_id))
                    backfilled.append("selldo_lead_id")
                    _log_activity(
                        conn, cls_id, "backfilled_from_selldo_import", "cls_import_selldo_csv",
                        prev_value=None, new_value=sid,
                        description="Backfilled selldo_lead_id from Sell.do CSV import",
                    )
                elif row["selldo_lead_id"] != sid:
                    warnings.append(
                        f"Existing selldo_lead_id {row['selldo_lead_id']} differs from CSV {sid}; kept existing"
                    )

                if will_backfill_campaign:
                    conn.execute("UPDATE leads SET campaign=? WHERE cls_id=?", (campaign, cls_id))
                    backfilled.append("campaign")
                    _log_activity(
                        conn, cls_id, "backfilled_from_selldo_import", "cls_import_selldo_csv",
                        prev_value=None, new_value=campaign,
                        description="Backfilled campaign from Sell.do CSV import",
                    )

                conn.commit()
            else:
                if will_backfill_selldo_id:
                    backfilled.append("selldo_lead_id")
                elif row["selldo_lead_id"] != sid:
                    warnings.append(
                        f"Existing selldo_lead_id {row['selldo_lead_id']} differs from CSV {sid}; would keep existing"
                    )
                if will_backfill_campaign:
                    backfilled.append("campaign")

            action = "update_id_and_backfill" if backfilled else "update_id_only"
            return {
                "action": action,
                "cls_id": cls_id,
                "prev_crm_lead_no": prev_crm_lead_no,
                "new_crm_lead_no": crm_lead_no_val,
                "backfilled": backfilled,
                "warnings": warnings,
            }

        # ═══════════════════════════════════════════════════════
        # NO MATCH — brand-new historical lead -> insert
        # ═══════════════════════════════════════════════════════

        # Idempotency guard (belt-and-suspenders — see docstring): if
        # activity_log already shows this exact selldo_lead_id was
        # imported before, do NOT insert a second lead for it.
        already = conn.execute(
            "SELECT cls_id FROM activity_log "
            "WHERE activity_type='imported_from_selldo' AND new_value=? LIMIT 1",
            (sid,)
        ).fetchone()
        if already:
            warnings.append(
                f"activity_log already shows selldo_lead_id {sid} imported previously "
                f"(cls_id={already['cls_id']}); skipping duplicate insert"
            )
            return {
                "action": "skip_invalid_row",
                "cls_id": already["cls_id"],
                "prev_crm_lead_no": None,
                "new_crm_lead_no": None,
                "backfilled": [],
                "warnings": warnings,
            }

        if not commit:
            return {
                "action": "insert",
                "cls_id": None,
                "prev_crm_lead_no": None,
                "new_crm_lead_no": crm_lead_no_val,
                "backfilled": [],
                "warnings": warnings,
            }

        cls_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO leads (
                cls_id, leadgen_id, form_id, project, project_bucket, full_name,
                phone_raw, phone_norm, email_raw, email_norm,
                selldo_lead_id, current_stage, stage_updated_at, match_tier,
                last_fired_stage, last_fired_at,
                source, lead_owner, selldo_url, opportunity_temperature,
                crm_lead_no, campaign, lead_source_detail,
                drip_paused, drip_enrolled_at, owner_notified,
                cls_created_at, cls_updated_at
            ) VALUES (?,?,?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?, ?,?,?,?, ?,?,?, ?,?,?, ?,?)
        """, (
            cls_id, None, None, project, get_project_bucket(project), full_name,
            phone_raw, phone_norm, email_raw, email_norm,
            sid, lead_stage, created_at_str, "imported",
            lead_stage, created_at_str,
            "selldo_only", lead_owner, None, None,
            crm_lead_no_val, campaign, None,
            1, created_at_str, 1,
            created_at_str, now,
        ))

        description = (
            f"Imported from Sell.do CSV. Sell.do ID: {sid}. "
            f"Owner: {lead_owner or 'Unassigned'}. "
            f"Projects raw: {projects_raw}. "
            f"Stage: {lead_stage}."
        )
        _log_activity(
            conn, cls_id, "imported_from_selldo", "cls_import_selldo_csv",
            prev_value=None, new_value=sid, description=description,
        )
        conn.commit()

        return {
            "action": "insert",
            "cls_id": cls_id,
            "prev_crm_lead_no": None,
            "new_crm_lead_no": crm_lead_no_val,
            "backfilled": [],
            "warnings": warnings,
        }
    finally:
        conn.close()


def log_duplicate_selldo_import(cls_id, old_selldo_id, description):
    """
    Called by cls_import_selldo_csv.py ONLY, once per older Sell.do ID
    its own phone-based dedupe collapses into an already imported/
    matched primary lead. Appends a single 'duplicate_selldo_id_from_
    import' activity_log row.

    Kept as its own tiny function rather than folded into
    import_selldo_csv_row() (which is scoped to importing ONE CSV row
    at a time, and has no reason to know about sibling rows in the
    same phone group) so the CLI script never needs to open sqlite3
    directly — per CLS's "all DB access through cls_db.py" rule.
    """
    conn = _connect()
    try:
        _log_activity(
            conn, cls_id, "duplicate_selldo_id_from_import", "cls_import_selldo_csv",
            prev_value=None, new_value=old_selldo_id, description=description,
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# STALENESS CHECK  —  Job B health signal (v1.4)
# ─────────────────────────────────────────────────────────────

def get_stale_stage_count(days=90):
    """
    Called by selldo_to_cls.py (Job B) once per cycle, after the sync
    step completes. Purely a read-only health signal — does not affect
    fire state, drip state, or anything else.

    Counts leads whose current_stage has NOT changed in `days` or more,
    EXCLUDING DRIP_TERMINAL_STAGES (Booked / Lost / Unqualified) — those
    are SUPPOSED to sit unchanged forever once a deal closes or dies, so
    including them here would just be noise.

    Why this exists: the original bug (selldo_to_cls.py's rolling
    183-day export window) didn't fail loudly. It silently stopped
    Sell.do leads older than the window from ever being re-synced, so
    current_stage froze in cls.db even as the real Sell.do record kept
    moving — no CAPI fire, no drip progression, no error anywhere. A
    rising or unexpectedly high number here, on ACTIVE (non-terminal)
    leads, is the early-warning signal for that exact failure mode
    happening again in some other form (a different sync gap, a broken
    match, etc.) — not for genuinely cold leads, which is normal.

    Returns an int.
    """
    placeholders = ",".join("?" for _ in DRIP_TERMINAL_STAGES)
    conn = _connect()
    try:
        row = conn.execute(f"""
            SELECT COUNT(*) AS cnt FROM leads
            WHERE stage_updated_at IS NOT NULL
              AND current_stage NOT IN ({placeholders})
              AND DATE(stage_updated_at) <= DATE('now', 'localtime', ?)
        """, (*DRIP_TERMINAL_STAGES, f"-{days} days")).fetchone()
        return row["cnt"]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# FIRE STATE  —  Job C:  find what needs firing, record what fired
# ─────────────────────────────────────────────────────────────

def get_unfired_leads():
    """
    Called by cls_capi_firer.py (Job C).
    Returns rows where the CRM stage is a target stage AND it has
    NOT yet been fired at that stage (current_stage != last_fired_stage).

    This is the Risk-4 fix in SQL form: state is PER ROW and based on
    confirmed fires, not a per-run "since last time" guess. A crash
    mid-run cannot cause a double-fire or a missed fire.
    """
    placeholders = ",".join("?" for _ in TARGET_STAGES)
    conn = _connect()
    try:
        rows = conn.execute(f"""
            SELECT * FROM leads
            WHERE current_stage IN ({placeholders})
              AND (last_fired_stage IS NULL OR last_fired_stage != current_stage)
        """, TARGET_STAGES).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_as_fired(cls_id, fired_stage):
    """
    Called by Job C ONLY AFTER Meta confirms events_received > 0.
    Records last_fired_stage = the stage just fired, so the same
    stage is never fired twice for the same lead.
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute("""
            UPDATE leads SET
                last_fired_stage=?, last_fired_at=?, cls_updated_at=?
            WHERE cls_id=?
        """, (fired_stage, now, now, cls_id))
        conn.commit()
    finally:
        conn.close()


MAX_QUEUE_ATTEMPTS = 8


def queue_failed_fire(cls_id, target_stage, error):
    """
    Append one row to capi_fire_queue — called when fire_single_lead_
    event() (cls_capi_core.py) fails from an inline call site (app.py's
    stage-change route, meta_leads_fetcher.py's new-lead insert). Picked
    up later by cls_capi_firer.py v3.0's default (queue-only) mode.
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO capi_fire_queue (cls_id, target_stage, attempts, last_error, status, created_at, last_attempt_at)
            VALUES (?, ?, 1, ?, 'pending', ?, ?)
        """, (cls_id, target_stage, str(error)[:500], now, now))
        conn.commit()
    finally:
        conn.close()


def get_due_retries():
    """All pending capi_fire_queue rows — cls_capi_firer.py's default mode."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT queue_id, cls_id, target_stage, attempts
            FROM capi_fire_queue WHERE status='pending'
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def clear_from_queue(queue_id):
    """Remove a row after it fires successfully on retry."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM capi_fire_queue WHERE queue_id=?", (queue_id,))
        conn.commit()
    finally:
        conn.close()


def log_webhook_test_lead(raw_payload):
    """
    v2.56 — Meta App Review screencast support. Best-effort extraction of
    leadgen_id/form_id/page_id from Meta's typical webhook shape
    (entry[0].id as page_id, entry[0].changes[0].value.leadgen_id/form_id).
    Never raises — a shape mismatch just means those 3 columns stay NULL,
    since the full raw_payload is stored regardless and is what actually
    matters for the screencast. Deliberately the ONLY write path into
    webhook_test_leads; nothing else in this file touches this table.
    """
    leadgen_id = form_id = page_id = None
    try:
        entry = raw_payload.get("entry", [{}])[0]
        page_id = entry.get("id")
        change_value = entry.get("changes", [{}])[0].get("value", {})
        leadgen_id = change_value.get("leadgen_id")
        form_id = change_value.get("form_id")
    except Exception:
        pass

    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO webhook_test_leads (received_at, leadgen_id, form_id, page_id, raw_payload)
            VALUES (?, ?, ?, ?, ?)
        """, (_now(), leadgen_id, form_id, page_id, json.dumps(raw_payload)))
        conn.commit()
    finally:
        conn.close()


def get_webhook_test_leads(limit=50):
    """All webhook_test_leads rows, newest first — feeds the App Review screencast viewer page."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT * FROM webhook_test_leads ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def bump_queue_attempt(queue_id, error):
    """
    Record a failed retry. Once attempts reaches MAX_QUEUE_ATTEMPTS the
    row's status flips to 'failed_permanent' so get_due_retries() stops
    picking it up — a lead that fails 8 times needs a human, not another
    silent retry.
    """
    now = _now()
    conn = _connect()
    try:
        row = conn.execute("SELECT attempts FROM capi_fire_queue WHERE queue_id=?", (queue_id,)).fetchone()
        new_attempts = (row["attempts"] if row else 0) + 1
        new_status = "failed_permanent" if new_attempts >= MAX_QUEUE_ATTEMPTS else "pending"
        conn.execute("""
            UPDATE capi_fire_queue SET attempts=?, last_error=?, last_attempt_at=?, status=?
            WHERE queue_id=?
        """, (new_attempts, str(error)[:500], now, new_status, queue_id))
        conn.commit()
    finally:
        conn.close()


def record_event(cls_id, leadgen_id, full_name, phone_norm, project,
                 crm_stage, meta_event, value_inr, used_leadgen, dataset_id,
                 prev_stage=None, lead_owner=None,
                 lead_snapshot_json=None, snapshot_source=None):
    """
    Append one fire event to the events_log table — the historical record.
    Called by Job C for every event it successfully fires to the PRIMARY
    dataset. This table is append-only: it never updates or deletes, so it
    accumulates a permanent, queryable history of every conversion sent.
    The dashboard reads this to show the running event log.

    prev_stage  : the stage the lead was at BEFORE this fire (i.e. the row's
                  last_fired_stage at fire time). Optional and defaults to
                  None so any older caller still works unchanged.
    lead_owner  : (v2.1) who owned the lead at the moment it fired. Captured
                  here rather than joined live from `leads` at report time,
                  so attribution survives later reassignment. Optional and
                  defaults to None so any older caller still works unchanged.
    lead_snapshot_json : (v2.78) json.dumps() of the lead's full row at fire
                  time — a frozen record of what the lead looked like the
                  moment this event fired, independent of later edits.
                  Optional and defaults to None so any older caller still
                  works unchanged.
    snapshot_source : (v2.78) how lead_snapshot_json was captured — e.g.
                  "fire_time" (cls_capi_core.fire_single_lead_event(), same
                  call as this event) or "backfill_current_state"
                  (backfill_capi_event_snapshots(), a later best-effort
                  fill for pre-existing rows). Optional, defaults to None.
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO events_log (
                fired_at, cls_id, leadgen_id, full_name, phone_norm,
                project, crm_stage, prev_stage, meta_event, value_inr,
                used_leadgen, dataset_id, lead_owner,
                lead_snapshot_json, snapshot_source
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (now, cls_id, leadgen_id, full_name, phone_norm,
              project, crm_stage, prev_stage, meta_event, value_inr,
              1 if used_leadgen else 0, dataset_id, lead_owner,
              lead_snapshot_json, snapshot_source))
        conn.commit()
    finally:
        conn.close()


# ── CAPI Events export — fixed columns + "Snapshot: " dynamic-column
# derivation. Introduced here in v2.79 (so get_capi_events_export_
# page() could compute column headers from the FULL matching row set
# once and reuse them across every page — see _flatten_capi_events()'s
# docstring), at which point crm/app.py v0.61 still carried its own
# separate, not-yet-consolidated copy (CAPI_EVENTS_EXPORT_COLUMNS /
# _prettify_lead_column() / _capi_events_export_columns(), used by the
# Excel/email export routes) — flagged as known duplication in v2.79's
# changelog. v2.80 CONSOLIDATES: this is now the ONLY copy anywhere in
# the codebase. get_capi_events_export() (below) returns these same
# columns too, so app.py's Excel/email routes no longer need — and no
# longer have — a copy of their own; app.py v0.63 deleted it.
_CAPI_EVENTS_FIXED_COLUMNS = [
    ("fired_at", "Fired At"), ("meta_event", "Meta Event"),
    ("crm_stage", "CRM Stage"), ("prev_stage", "Previous Stage"),
    ("value_inr", "Value (INR)"), ("used_leadgen", "Used Leadgen ID"),
    ("dataset_id", "Dataset ID"), ("lead_owner", "Lead Owner"),
    ("snapshot_source", "Snapshot Source"),
]


def _prettify_capi_snapshot_column(key):
    """"lead_full_name" -> "Snapshot: Full Name" — same generic strip +
    title-case + "Snapshot: " prefix as crm/app.py's identically-behaved
    _prettify_lead_column() (v0.61) — the prefix avoids a duplicate
    "Lead Owner" header, since leads.lead_owner flattens to the row key
    "lead_lead_owner", which without a prefix would collide with the
    FIXED lead_owner column above (the fire-time capture)."""
    label = key[len("lead_"):] if key.startswith("lead_") else key
    return "Snapshot: " + label.replace("_", " ").title()


def _capi_events_columns_for_rows(rows):
    """
    _CAPI_EVENTS_FIXED_COLUMNS first, then every distinct "lead_*"
    snapshot key actually present across `rows`, sorted alphabetically
    and prettified — a union across rows because different events can
    carry a different lead_* key set (a row never backfilled has none
    at all). lead_owner (already a fixed column) and lead_snapshot_json
    (the raw JSON blob) are both excluded from the dynamic scan — both
    already start with "lead_" before this scan even runs, so without
    exclusion they'd each surface as a spurious/duplicate column.
    """
    fixed_keys = {k for k, _ in _CAPI_EVENTS_FIXED_COLUMNS}
    dynamic_keys = set()
    for row in rows:
        for k in row.keys():
            if k.startswith("lead_") and k not in fixed_keys and k != "lead_snapshot_json":
                dynamic_keys.add(k)
    return _CAPI_EVENTS_FIXED_COLUMNS + [(k, _prettify_capi_snapshot_column(k)) for k in sorted(dynamic_keys)]


def _flatten_capi_events(date_from=None, date_to=None):
    """
    (v2.79) SQL-fetch + JSON-flatten + column-derivation shared by
    get_capi_events_export() and get_capi_events_export_page() — the
    single place events_log rows become the flat "lead_*"-prefixed dict
    shape both those functions expose. Same date-filter convention as
    get_activity_log_export() (substr(fired_at,1,10) BETWEEN ? AND ?).

    Each row's lead_snapshot_json (if present) is expanded into the row
    dict with a "lead_" prefix per key (e.g. lead_full_name,
    lead_current_stage) — rows with no snapshot yet (never backfilled,
    see backfill_capi_event_snapshots()) simply carry no lead_* keys at
    all rather than blanks, since different rows can carry a different
    lead_* key set.

    Returns (rows, columns) — rows newest fired_at first; columns is
    the FULL, fixed-then-alphabetical "Snapshot: "-labeled column list
    for this exact row set (see _capi_events_columns_for_rows()), so a
    caller that only wants some of the rows (get_capi_events_export_
    page()'s per-page slice) can still show headers derived from every
    matching row, not just the ones on screen.
    """
    conn = _connect()
    try:
        query = "SELECT * FROM events_log WHERE 1=1"
        params = []
        if date_from and date_to:
            query += " AND substr(fired_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        query += " ORDER BY fired_at DESC"
        rows = conn.execute(query, params).fetchall()

        result = []
        for r in rows:
            row = dict(r)
            snap = row.get("lead_snapshot_json")
            lead = json.loads(snap) if snap else {}
            for k, v in lead.items():
                row[f"lead_{k}"] = v
            result.append(row)
    finally:
        conn.close()

    return result, _capi_events_columns_for_rows(result)


def get_capi_events_export(date_from=None, date_to=None):
    """
    (v2.78; refactored v2.79 to delegate to _flatten_capi_events();
    return shape CHANGED in v2.80 — see below)
    Cross-event, date-ranged events_log export for the CAPI Events
    Excel/email export routes (crm/app.py's unpaginated path — see
    get_capi_events_export_page() below for the on-screen paginated
    view).

    Returns (rows, columns) — rows is a list of flat dicts, newest
    fired_at first; columns is the same fixed-then-alphabetical
    "Snapshot: "-labeled list get_capi_events_export_page() already
    returns (see _capi_events_columns_for_rows()), now the ONE place
    that logic lives (v2.80 — crm/app.py's previously-separate copy,
    CAPI_EVENTS_EXPORT_COLUMNS/_prettify_lead_column()/
    _capi_events_export_columns(), was deleted in app.py v0.63; the
    Excel/email routes now use exactly the columns this function
    returns instead of rebuilding their own).

    v2.78-v2.79 callers took this as a bare rows list — this is a
    BREAKING return-shape change. The only caller in the codebase
    (crm/app.py's _export_capi_events_report()) was updated in the same
    session (app.py v0.63) to unpack (rows, columns); confirmed via
    grep before this version shipped that no other caller exists.
    """
    return _flatten_capi_events(date_from, date_to)


def get_capi_events_export_page(date_from=None, date_to=None, page=1, per_page=200):
    """
    (v2.79) Paginated view of CAPI events for the on-screen results
    table (crm/app.py's settings_export_capi_events_results route).
    Same pagination shape/style as get_leads_page()/
    list_call_recordings(): fetch all matching rows via
    _flatten_capi_events(), slice in Python (no SQL LIMIT/OFFSET), page
    clamped into [1, total_pages].

    Columns are computed from the FULL matching set (not just the
    current page) via _flatten_capi_events(), so column headers stay
    identical across pages even if older/newer rows have a different
    snapshot field set present.

    Returns {"rows", "total", "page", "per_page", "total_pages",
    "columns"}.
    """
    all_rows, columns = _flatten_capi_events(date_from, date_to)
    total = len(all_rows)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    page_rows = all_rows[start:start + per_page]
    return {
        "rows": page_rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "columns": columns,
    }


def backfill_capi_event_snapshots(dry_run=True, verbose=False):
    """
    (v2.78) One-off, manually-invoked backfill for events_log rows that
    predate the lead_snapshot_json/snapshot_source columns (both NULL).
    For each such row, looks up the lead's CURRENT state via
    get_lead_by_id() and freezes it in. This is a best-effort backfill,
    not a time machine — for pre-existing rows we only have the lead's
    state NOW, not what it looked like at the original fire time, hence
    snapshot_source='backfill_current_state' (distinct from 'fire_time',
    see cls_capi_core.py v1.1, which captures the real thing going
    forward).

    A lead that no longer exists (e.g. deleted since it fired) is
    skipped and counted as "orphaned" rather than raising — one missing
    lead must never abort the whole backfill.

    dry_run=True (default): counts only, writes nothing — safe to run
    repeatedly to see how many rows are pending. Call this manually;
    NOT invoked by any scheduled job or app.py route.
    dry_run=False: performs the UPDATEs, then prints the same summary.

    verbose=True additionally prints one line per row as it's
    processed; default is the single summary line only.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT event_row_id, cls_id FROM events_log WHERE lead_snapshot_json IS NULL"
        ).fetchall()

        backfilled = 0
        orphaned = 0
        for r in rows:
            lead = get_lead_by_id(r["cls_id"])
            if lead is None:
                orphaned += 1
                if verbose:
                    print(f"  [SKIP] event_row_id={r['event_row_id']} cls_id={r['cls_id']} — lead no longer exists")
                continue
            if not dry_run:
                conn.execute(
                    "UPDATE events_log SET lead_snapshot_json=?, snapshot_source=? WHERE event_row_id=?",
                    (json.dumps(lead, default=str), "backfill_current_state", r["event_row_id"])
                )
            backfilled += 1
            if verbose:
                action = "Backfilled" if not dry_run else "Would backfill"
                print(f"  [{action}] event_row_id={r['event_row_id']} cls_id={r['cls_id']}")

        if not dry_run:
            conn.commit()

        verb = "Backfilled" if not dry_run else "Would backfill"
        print(f"{verb} {backfilled} events. {orphaned} events skipped (lead no longer exists).")
    finally:
        conn.close()


def get_daily_owner_summary(date_str=None):
    """
    (v2.1) Per-salesperson breakdown for the watchdog's end-of-day summary.
    Covers Jobs A/B/C activity only — NOT the same thing as v0.5's
    activity_log, which records only the CRM app's own write actions.

    Returns a list of dicts, one per distinct lead_owner active that day
    (plus an "Unassigned" bucket for blank/NULL owners), sorted by
    new_leads + stage_changes + capi_fired descending:
        [{"owner": "Elohar", "new_leads": 4, "stage_changes": 9, "capi_fired": 6}, ...]

    date_str : "YYYY-MM-DD". Defaults to today (server local time, matching
               every other date() comparison in this file).

    DEFINITIONS / KNOWN EDGE CASES (read before treating these as exact):
      new_leads     — leads whose cls_created_at falls on date_str, grouped
                      by their CURRENT lead_owner. A lead fetched by Job A
                      late in the day may not yet have an owner if Job B
                      hasn't synced it — it lands in "Unassigned" until the
                      next Sell.do sync assigns it (that lead will then
                      count under its real owner in tomorrow's Unassigned
                      bucket check, not retroactively in today's report).
      stage_changes — leads whose stage_updated_at falls on date_str. This
                      counts the LEAD, not every transition — if one lead
                      changes stage twice in the same day (e.g. Prospect ->
                      Opportunity at 12:00, then Opportunity -> Site Visited
                      at 16:00), it is counted ONCE here. Job B's own
                      per-cycle "stage changes detected this run" total
                      (used for the aggregate b_total figure) counts every
                      transition separately, so on a day with same-lead
                      double-transitions the aggregate total and the sum of
                      this per-owner breakdown can legitimately differ by a
                      small amount. Flagged here rather than hidden.
      capi_fired    — events_log rows where fired_at falls on date_str,
                      grouped by the lead_owner captured on the event at
                      fire time (v2.1). This one has no edge case: it is
                      exact and matches the aggregate c_total figure.
    """
    if not date_str:
        date_str = _now()[:10]   # _now() returns "YYYY-MM-DD HH:MM:SS"

    conn = _connect()
    try:
        new_rows = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(lead_owner), ''), 'Unassigned') AS owner,
                   COUNT(*) AS n
            FROM leads
            WHERE substr(cls_created_at, 1, 10) = ?
            GROUP BY owner
        """, (date_str,)).fetchall()

        stage_rows = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(lead_owner), ''), 'Unassigned') AS owner,
                   COUNT(*) AS n
            FROM leads
            WHERE substr(stage_updated_at, 1, 10) = ?
            GROUP BY owner
        """, (date_str,)).fetchall()

        fired_rows = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(lead_owner), ''), 'Unassigned') AS owner,
                   COUNT(*) AS n
            FROM events_log
            WHERE substr(fired_at, 1, 10) = ?
            GROUP BY owner
        """, (date_str,)).fetchall()
    finally:
        conn.close()

    merged = {}
    for row in new_rows:
        merged.setdefault(row["owner"], {"new_leads": 0, "stage_changes": 0, "capi_fired": 0})
        merged[row["owner"]]["new_leads"] = row["n"]
    for row in stage_rows:
        merged.setdefault(row["owner"], {"new_leads": 0, "stage_changes": 0, "capi_fired": 0})
        merged[row["owner"]]["stage_changes"] = row["n"]
    for row in fired_rows:
        merged.setdefault(row["owner"], {"new_leads": 0, "stage_changes": 0, "capi_fired": 0})
        merged[row["owner"]]["capi_fired"] = row["n"]

    result = [
        {"owner": owner, **counts}
        for owner, counts in merged.items()
    ]
    result.sort(
        key=lambda r: r["new_leads"] + r["stage_changes"] + r["capi_fired"],
        reverse=True,
    )
    return result


def get_events(limit=None):
    """
    Return rows from events_log, newest first. Used by the dashboard.
    limit : if given, return only the most recent N events.
    """
    conn = _connect()
    try:
        sql = "SELECT * FROM events_log ORDER BY event_row_id DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def event_stats():
    """
    Summary counts from events_log for the dashboard's top cards.
    """
    conn = _connect()
    try:
        total   = conn.execute("SELECT COUNT(*) c FROM events_log").fetchone()["c"]
        leadgen = conn.execute("SELECT COUNT(*) c FROM events_log WHERE used_leadgen=1").fetchone()["c"]
        today   = datetime.now().strftime("%Y-%m-%d")
        today_n = conn.execute("SELECT COUNT(*) c FROM events_log WHERE fired_at LIKE ?",
                               (today + "%",)).fetchone()["c"]
        value   = conn.execute("SELECT COALESCE(SUM(value_inr),0) v FROM events_log").fetchone()["v"]
        return {
            "total_events"   : total,
            "leadgen_events" : leadgen,
            "events_today"   : today_n,
            "total_value_inr": value,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# DRIP ENROLLMENT & QUERY  —  Job D helpers
# ─────────────────────────────────────────────────────────────
# Job D sends automated email sequences keyed off CRM stage.
# These helpers manage enrollment, eligibility, and logging.

def enroll_in_drip(cls_id):
    """
    Mark a single lead as drip-enrolled. Sets drip_enrolled_at = now
    if not already set. Idempotent — calling twice does nothing.

    Returns True if newly enrolled, False if already enrolled.
    """
    now = _now()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT drip_enrolled_at FROM leads WHERE cls_id=?", (cls_id,)
        ).fetchone()
        if not row:
            return False
        if row["drip_enrolled_at"]:
            return False   # already enrolled
        conn.execute(
            "UPDATE leads SET drip_enrolled_at=?, cls_updated_at=? WHERE cls_id=?",
            (now, now, cls_id))
        conn.commit()
        return True
    finally:
        conn.close()


def bulk_enroll_drip():
    """
    Backfill: enroll ALL leads that have an email address and are not
    yet drip-enrolled. Called once when Job D is first deployed, and
    harmlessly on every subsequent run (finds zero un-enrolled leads).

    Returns the count of newly enrolled leads.
    """
    now = _now()
    conn = _connect()
    try:
        cur = conn.execute("""
            UPDATE leads SET drip_enrolled_at=?, cls_updated_at=?
            WHERE drip_enrolled_at IS NULL
              AND email_norm IS NOT NULL
              AND email_norm != ''
        """, (now, now))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_drip_due(drip_stage, day_number):
    """
    Find leads that are DUE for a specific drip email right now.

    A lead qualifies when ALL of these are true:
      1. current_stage matches drip_stage
      2. drip_enrolled_at is set (lead is in the drip system)
      3. drip_paused is NOT 1 (not in a Re Assigned hold)
      4. email_opt_out is NOT 1
      5. email_hard_bounce is NOT 1
      6. email_norm is not blank (has an email address)
      7. current_stage is not a terminal stage (Booked/Lost/Unqualified)
      8. Enough days have elapsed since the drip reference date
         (reference = the LATER of drip_enrolled_at and stage_updated_at)
      9. This exact email has NOT already been sent
         (no row in comms_log with same cls_id + drip_stage + day_number)

    Returns a list of lead dicts ready for emailing.
    """
    conn = _connect()
    try:
        # Calculate the cutoff: leads whose reference date is at least
        # day_number days ago. Reference = MAX(drip_enrolled_at, stage_updated_at).
        # SQLite date() handles this neatly.
        today = datetime.now().strftime("%Y-%m-%d")

        rows = conn.execute("""
            SELECT l.* FROM leads l
            WHERE l.current_stage = ?
              AND l.drip_enrolled_at IS NOT NULL
              AND COALESCE(l.drip_paused, 0) != 1
              AND COALESCE(l.email_opt_out, 0) != 1
              AND COALESCE(l.email_hard_bounce, 0) != 1
              AND l.email_norm IS NOT NULL AND l.email_norm != ''
              AND l.current_stage NOT IN ({terminals})
              AND DATE(MAX(l.drip_enrolled_at, COALESCE(l.stage_updated_at, l.drip_enrolled_at)),
                       '+' || ? || ' days') <= DATE(?)
              AND NOT EXISTS (
                  SELECT 1 FROM comms_log c
                  WHERE c.cls_id = l.cls_id
                    AND c.drip_stage = ?
                    AND c.day_number = ?
                    AND c.status = 'sent'
              )
        """.format(terminals=",".join("?" for _ in DRIP_TERMINAL_STAGES)),
            (drip_stage,
             *DRIP_TERMINAL_STAGES,
             day_number, today,
             drip_stage, day_number)
        ).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


def record_comms(cls_id, project, drip_stage, day_number, template_key,
                 sender_email, brevo_message_id, status="sent"):
    """
    Append one email-sent record to comms_log. Called by Job D after
    Brevo confirms delivery. Append-only — never updates or deletes.
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO comms_log (
                sent_at, cls_id, project, drip_stage, day_number,
                template_key, sender_email, brevo_message_id, status
            ) VALUES (?,?,?,?,?,?,?,?,?)
        """, (now, cls_id, project, drip_stage, day_number,
              template_key, sender_email, brevo_message_id, status))
        conn.commit()
    finally:
        conn.close()


def was_email_sent(cls_id, drip_stage, day_number):
    """
    Quick check: has this specific email already been sent?
    Used as a safety net in Job D before calling Brevo.
    """
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT 1 FROM comms_log
            WHERE cls_id=? AND drip_stage=? AND day_number=? AND status='sent'
            LIMIT 1
        """, (cls_id, drip_stage, day_number)).fetchone()
        return row is not None
    finally:
        conn.close()


def pause_drip(cls_id):
    """
    Pause a lead's drip (called when stage becomes 'Re Assigned').
    The lead receives no emails until unpause_drip() is called.
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE leads SET drip_paused=1, cls_updated_at=? WHERE cls_id=?",
            (now, cls_id))
        conn.commit()
    finally:
        conn.close()


def unpause_drip(cls_id):
    """
    Unpause a lead's drip (called when stage transitions from
    'Re Assigned' to a real stage). The new stage's drip sequence
    starts from Day 1 — stage_updated_at is already set by Job B's
    upsert, so the day count resets naturally.
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE leads SET drip_paused=0, cls_updated_at=? WHERE cls_id=?",
            (now, cls_id))
        conn.commit()
    finally:
        conn.close()


def mark_opt_out(cls_id):
    """
    Permanent email opt-out. The lead never receives another automated
    email. This is a hard stop — Job D checks this before every send.
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE leads SET email_opt_out=1, cls_updated_at=? WHERE cls_id=?",
            (now, cls_id))
        conn.commit()
    finally:
        conn.close()


def mark_hard_bounce(cls_id):
    """
    Record that this lead's email address is permanently invalid.
    Brevo reports hard bounces via webhook or API; Job D calls this
    when it detects one. Another hard stop — no further sends.
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE leads SET email_hard_bounce=1, cls_updated_at=? WHERE cls_id=?",
            (now, cls_id))
        conn.commit()
    finally:
        conn.close()


def drip_stats():
    """Summary counts for Job D logging and dashboard."""
    conn = _connect()
    try:
        enrolled = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE drip_enrolled_at IS NOT NULL"
        ).fetchone()["c"]
        paused = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE drip_paused=1"
        ).fetchone()["c"]
        opted_out = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE email_opt_out=1"
        ).fetchone()["c"]
        bounced = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE email_hard_bounce=1"
        ).fetchone()["c"]
        emails_sent = conn.execute(
            "SELECT COUNT(*) c FROM comms_log WHERE status='sent'"
        ).fetchone()["c"]
        today = datetime.now().strftime("%Y-%m-%d")
        today_sent = conn.execute(
            "SELECT COUNT(*) c FROM comms_log WHERE status='sent' AND sent_at LIKE ?",
            (today + "%",)).fetchone()["c"]
        return {
            "drip_enrolled"  : enrolled,
            "drip_paused"    : paused,
            "email_opt_out"  : opted_out,
            "hard_bounced"   : bounced,
            "emails_sent"    : emails_sent,
            "emails_today"   : today_sent,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# CRM v0.6 — REPORTS  (Srikanth's 12-report spec, July 2026)
# ─────────────────────────────────────────────────────────────
# All read-only, all NEW (v2.12) except the three functions flagged
# in this version's changelog entry above, each of which gained only
# a backward-compatible optional kwarg or dict key. crm/cls_reports.py
# owns report metadata, table shaping, and Excel/print-PDF export —
# it calls these functions, it never opens sqlite3 itself, per the
# centralized-access rule.
#
# HONESTY NOTES (read before trusting a report number):
#   - activity_log 'stage_change' rows are written ONLY by this
#     module's own update_lead_stage() — i.e. only for stage moves
#     made THROUGH the CRM app. Job B's Sell.do sync (upsert_selldo_
#     lead) updates leads.current_stage directly and logs nothing to
#     activity_log. During parallel-run, most historical stage moves
#     still happen via Sell.do, so get_conversion_funnel_trend()
#     below will undercount early months and fill in only as the
#     team's CRM usage matures — flagged again in its own docstring.
#   - leads.source only ever holds 'meta' / 'selldo_only' /
#     'manual_crm' (see SOURCE_OPTIONS) — the system-level capture
#     channel, not a marketing sub-source like "99acres". lead_
#     source_detail (MANUAL_SOURCE_OPTIONS) is richer but is set ONLY
#     at manual-entry time and locked after, so it's NULL for the
#     large majority of leads (anything auto-captured from Meta or
#     Sell.do). get_source_performance() below reports on the
#     universally-populated `source` column for that reason.
# ─────────────────────────────────────────────────────────────

def get_source_performance(date_from=None, date_to=None):
    """
    (v2.12) Report #3 — Lead Source Performance, admin-only (cross-
    salesperson comparison, not owner-filterable). For each value of
    leads.source ('meta' / 'selldo_only' / 'manual_crm' — see the
    HONESTY NOTE above on why this is the source column used, not
    lead_source_detail), a current-stage funnel snapshot: how many
    leads from that source have reached Prospect+, Opportunity+, Site
    Visited+, Booked, or ended Lost/Unqualified, right now.

    "Reached X+" means current_stage is X or any stage further along
    the funnel (Opportunity+ = currently at Opportunity, Site Visited,
    or Booked) — a live snapshot proxy for quality, not a historical
    cohort conversion rate (that's get_conversion_funnel_trend()'s job).

    date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings, default
    None (existing behavior, unchanged — every lead, all-time). When
    both given, scopes to leads whose cls_created_at falls in that
    range — "of the leads that CAME IN during this period, where do
    they stand now" rather than "of every lead ever, where do they
    stand now."

    Returns a list of dicts, one per source, sorted by total desc:
        [{"source": "meta", "total": 120, "prospect_plus": 80,
          "opportunity_plus": 40, "site_visited_plus": 15,
          "booked": 3, "lost_unqualified": 25}, ...]
    """
    PROSPECT_PLUS = ("Prospect", "Opportunity", "Site Visited", "Booked")
    OPPORTUNITY_PLUS = ("Opportunity", "Site Visited", "Booked")
    SITE_VISITED_PLUS = ("Site Visited", "Booked")

    conn = _connect()
    try:
        query = """
            SELECT COALESCE(NULLIF(TRIM(source), ''), '(unknown)') AS source,
                   current_stage, COUNT(*) c
            FROM leads
        """
        params = []
        if date_from and date_to:
            query += " WHERE substr(cls_created_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        query += " GROUP BY source, current_stage"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    by_source = {}
    for r in rows:
        src = r["source"]
        bucket = by_source.setdefault(src, {
            "source": src, "total": 0, "prospect_plus": 0,
            "opportunity_plus": 0, "site_visited_plus": 0,
            "booked": 0, "lost_unqualified": 0,
        })
        stage, c = r["current_stage"], r["c"]
        bucket["total"] += c
        if stage in PROSPECT_PLUS:
            bucket["prospect_plus"] += c
        if stage in OPPORTUNITY_PLUS:
            bucket["opportunity_plus"] += c
        if stage in SITE_VISITED_PLUS:
            bucket["site_visited_plus"] += c
        if stage == "Booked":
            bucket["booked"] += c
        if stage in ("Lost", "Unqualified"):
            bucket["lost_unqualified"] += c

    result = list(by_source.values())
    result.sort(key=lambda r: r["total"], reverse=True)
    return result


def get_project_pipeline(owner=None, date_from=None, date_to=None):
    """
    (v2.12) Report #4 — Project-wise Pipeline. Cross-tab of project
    bucket (v2.67, F2 Phase 3: read straight from the stored, kept-in-
    sync leads.project_bucket column — was previously computed per row
    via get_project_bucket(); same collapsing of Sell.do's spacing/dash
    variants and comma-joined multi-project strings into one row per
    real project, just read from the column instead of recomputed) x
    current_stage, optionally scoped to one salesperson's owned leads.

    owner : lead_owner to scope to (salesperson's own view). None =
            every lead (admin/manager view).

    date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings, default
    None (existing behavior, unchanged — every lead regardless of when
    created). When both given, scopes to leads whose cls_created_at
    falls in that range — turns this from a pure live snapshot into
    "of the leads created in this period, where do they stand now."

    Returns a dict keyed by project bucket, each value a dict keyed by
    every stage in ALL_STAGES (all present, 0 if empty) plus a "total"
    key: {"Naishka Homes": {"Incoming": 4, ..., "total": 37}, ...}
    """
    conn = _connect()
    try:
        query = "SELECT project_bucket, current_stage FROM leads"
        clauses = []
        params = []
        if owner:
            clauses.append("lead_owner = ?")
            params.append(owner)
        if date_from and date_to:
            clauses.append("substr(cls_created_at, 1, 10) BETWEEN ? AND ?")
            params.extend([date_from, date_to])
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    result = {}
    for r in rows:
        bucket = r["project_bucket"]
        entry = result.setdefault(bucket, {stage: 0 for stage in ALL_STAGES})
        entry["total"] = entry.get("total", 0)
        stage = r["current_stage"]
        if stage in entry:
            entry[stage] += 1
        entry["total"] += 1

    return result


def get_conversion_funnel_trend(months=6, date_from=None, date_to=None):
    """
    (v2.12) Report #5 — Conversion Funnel Over Time, admin-only.
    Month-over-month cohort: of the leads that FIRST entered Prospect
    in a given month (earliest activity_log 'stage_change' row with
    new_value='Prospect' for that cls_id), what % have SINCE reached
    Opportunity, and what % have SINCE reached Site Visited (as of
    right now — not "by end of that month").

    IMPORTANT CAVEAT: activity_log 'stage_change' rows are only
    written by the CRM app's own update_lead_stage() — see this
    section's HONESTY NOTE above. Sell.do-driven stage moves (the
    majority, during parallel-run) leave no activity_log trail, so
    months before the team's CRM adoption matured will show few or
    zero cohort entries here — a real gap in the data, not a bug.
    Read this report as "conversion rate for stage moves made inside
    the CRM," trending toward completeness as parallel-run continues.

    date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings. When
    BOTH given, the month bucket list is built from that explicit
    range instead of "the `months` trailing calendar months from
    today" — so picking "This Month" naturally yields one row, a wider
    custom range yields however many months it spans. When either is
    omitted, `months` governs the window exactly as before (unchanged
    default behavior).

    Returns a list of dicts, oldest month first:
        [{"month": "2026-02", "entered_prospect": 12,
          "reached_opportunity": 5, "reached_site_visited": 2,
          "opportunity_rate": 41.7, "site_visited_rate": 16.7}, ...]
    """
    conn = _connect()
    try:
        first_prospect = conn.execute("""
            SELECT cls_id, MIN(created_at) AS entered_at
            FROM activity_log
            WHERE activity_type = 'stage_change' AND new_value = 'Prospect'
            GROUP BY cls_id
        """).fetchall()

        cls_ids = [r["cls_id"] for r in first_prospect]
        current_stages = {}
        if cls_ids:
            placeholders = ",".join("?" * len(cls_ids))
            stage_rows = conn.execute(
                f"SELECT cls_id, current_stage FROM leads WHERE cls_id IN ({placeholders})",
                cls_ids
            ).fetchall()
            current_stages = {r["cls_id"]: r["current_stage"] for r in stage_rows}
    finally:
        conn.close()

    OPPORTUNITY_PLUS = ("Opportunity", "Site Visited", "Booked")
    SITE_VISITED_PLUS = ("Site Visited", "Booked")

    months_list = []
    if date_from and date_to:
        cursor = datetime.strptime(date_from, "%Y-%m-%d").replace(day=1)
        end_cursor = datetime.strptime(date_to, "%Y-%m-%d").replace(day=1)
        while cursor <= end_cursor:
            months_list.append(cursor.strftime("%Y-%m"))
            cursor = (cursor + timedelta(days=32)).replace(day=1)
    else:
        cursor = datetime.now().replace(day=1)
        for _ in range(months):
            months_list.append(cursor.strftime("%Y-%m"))
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        months_list.reverse()

    buckets = {m: {"entered_prospect": 0, "reached_opportunity": 0, "reached_site_visited": 0}
               for m in months_list}

    for r in first_prospect:
        month = (r["entered_at"] or "")[:7]
        if month not in buckets:
            continue
        buckets[month]["entered_prospect"] += 1
        stage = current_stages.get(r["cls_id"])
        if stage in OPPORTUNITY_PLUS:
            buckets[month]["reached_opportunity"] += 1
        if stage in SITE_VISITED_PLUS:
            buckets[month]["reached_site_visited"] += 1

    result = []
    for m in months_list:
        b = buckets[m]
        entered = b["entered_prospect"]
        result.append({
            "month": m,
            "entered_prospect": entered,
            "reached_opportunity": b["reached_opportunity"],
            "reached_site_visited": b["reached_site_visited"],
            "opportunity_rate": round(b["reached_opportunity"] / entered * 100, 1) if entered else 0.0,
            "site_visited_rate": round(b["reached_site_visited"] / entered * 100, 1) if entered else 0.0,
        })
    return result


def get_followup_hit_rate(owner=None, date_from=None, date_to=None):
    """
    (v2.12) Report #6 — Follow-up / Site-Visit Hit Rate. Of every
    scheduled follow_up/site_visit row, how many ended completed/
    conducted vs cancelled vs are still open-and-overdue ("missed",
    computed live the SAME way get_due_today() does — see that
    function's docstring for why "missed" is never a stored value) vs
    still open-and-upcoming.

    owner : scope to one salesperson's OWNED leads (joins to
            leads.lead_owner). None = everyone.

    date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings, default
    None (existing behavior, unchanged — every row, all-time). When
    both given, scopes to rows whose scheduled_at falls in that range
    — "of what was scheduled during this period, how did it turn out."

    Returns {"site_visits": {...}, "follow_ups": {...}}, each inner
    dict: {completed, cancelled, missed, upcoming, total} (site_visits
    also gets a "no_show" key — its own terminal status, distinct from
    a still-open "missed" row).
    """
    now = _now()
    conn = _connect()
    try:
        def _tally(table, done_status):
            query = f"""
                SELECT t.status, t.scheduled_at
                FROM {table} t JOIN leads l ON l.cls_id = t.cls_id
            """
            clauses = []
            params = []
            if owner:
                clauses.append("l.lead_owner = ?")
                params.append(owner)
            if date_from and date_to:
                clauses.append("substr(t.scheduled_at, 1, 10) BETWEEN ? AND ?")
                params.extend([date_from, date_to])
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            rows = conn.execute(query, params).fetchall()
            tally = {"completed": 0, "cancelled": 0, "missed": 0, "upcoming": 0, "total": 0}
            for r in rows:
                tally["total"] += 1
                if r["status"] == done_status:
                    tally["completed"] += 1
                elif r["status"] == "cancelled":
                    tally["cancelled"] += 1
                elif r["status"] == "scheduled":
                    if r["scheduled_at"] and r["scheduled_at"] < now:
                        tally["missed"] += 1
                    else:
                        tally["upcoming"] += 1
                # else: 'no_show' (site_visits only) — tallied separately below
            return tally

        site_visits = _tally("site_visits", "conducted")
        no_show_query = """
            SELECT COUNT(*) c FROM site_visits t JOIN leads l ON l.cls_id = t.cls_id
            WHERE t.status = 'no_show'
        """
        no_show_params = []
        if owner:
            no_show_query += " AND l.lead_owner = ?"
            no_show_params.append(owner)
        if date_from and date_to:
            no_show_query += " AND substr(t.scheduled_at, 1, 10) BETWEEN ? AND ?"
            no_show_params.extend([date_from, date_to])
        site_visits["no_show"] = conn.execute(no_show_query, no_show_params).fetchone()["c"]

        follow_ups = _tally("follow_ups", "completed")
        return {"site_visits": site_visits, "follow_ups": follow_ups}
    finally:
        conn.close()


def get_lost_reason_breakdown(date_from=None, date_to=None):
    """
    (v2.12) Report #7 — Lost/Unqualified Reason Breakdown, admin-only.
    Groups CURRENTLY Lost/Unqualified leads by (current_stage,
    stage_reason). Data-driven, not hardcoded to UNQUALIFIED_REASONS/
    LOST_REASONS — a lead marked Lost under the older LOST_REASONS
    codes (see that list's PAUSED docstring) still has its real
    stage_reason value and shows up here under its own code, exactly
    as it does in leads_filter_screen()'s reason dropdown.

    Only reflects leads' CURRENT reason — stage_reason is cleared the
    moment a lead moves OUT of Lost/Unqualified (see update_lead_
    stage()'s docstring), so a lead that was Lost and later reopened
    to Prospect does not appear here. The full historical reason still
    lives in that lead's activity_log regardless.

    date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings, default
    None (existing behavior, unchanged — every currently Lost/
    Unqualified lead, regardless of when). When both given, scopes to
    leads whose stage_updated_at (best available proxy for "when it
    became Lost/Unqualified" — there's no dedicated timestamp per
    reason) falls in that range.

    Returns a list of dicts sorted by count desc:
        [{"stage": "Lost", "reason": "Budget does not match", "count": 8}, ...]
    """
    conn = _connect()
    try:
        query = """
            SELECT current_stage AS stage,
                   COALESCE(NULLIF(TRIM(stage_reason), ''), '(no reason recorded)') AS reason,
                   COUNT(*) c
            FROM leads
            WHERE current_stage IN ('Lost', 'Unqualified')
        """
        params = []
        if date_from and date_to:
            query += " AND substr(stage_updated_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        query += " GROUP BY current_stage, reason ORDER BY c DESC"
        rows = conn.execute(query, params).fetchall()
        return [{"stage": r["stage"], "reason": r["reason"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


def get_score_distribution(owner=None):
    """
    (v2.12) Report #8 — Lead Score Distribution, by salesperson.
    Wraps the existing compute_lead_scores() (called exactly as it
    already is elsewhere, unmodified) over every lead in scope, then
    buckets by band and lead_owner.

    owner : scope to one salesperson (their row only). None = every
            owner (admin/manager view) — a cross-salesperson table is
            inherent to "by salesperson"; app.py's route decides who's
            allowed to pass owner=None, this function just obeys
            whatever it's given.

    Returns a list of dicts, one per owner (+ "Unassigned" bucket),
    sorted by total desc:
        [{"owner": "Elohar", "Hot": 3, "Warm": 5, "Cold": 2, "total": 10}, ...]
    """
    conn = _connect()
    try:
        query = """
            SELECT cls_id, COALESCE(NULLIF(TRIM(lead_owner), ''), 'Unassigned') AS owner
            FROM leads
        """
        params = []
        if owner:
            query += " WHERE lead_owner = ?"
            params.append(owner)
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    cls_ids = [r["cls_id"] for r in rows]
    scores = compute_lead_scores(cls_ids)

    by_owner = {}
    for r in rows:
        o = r["owner"]
        bucket = by_owner.setdefault(o, {"owner": o, "Hot": 0, "Warm": 0, "Cold": 0, "total": 0})
        band = scores.get(r["cls_id"], {}).get("band", "Cold")
        bucket[band] += 1
        bucket["total"] += 1

    result = list(by_owner.values())
    result.sort(key=lambda r: r["total"], reverse=True)
    return result


def get_first_response_time(months=6, date_from=None, date_to=None):
    """
    (v2.12) Report #10 — First-Response Time, admin-only. For every
    lead, time from cls_created_at to its EARLIEST activity_log row of
    any type (the first time a human touched it), bucketed by the
    lead's creation month. Leads with zero activity_log rows ever are
    counted separately as "no_response_yet" per month, not silently
    dropped or averaged in as infinite.

    date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings. When
    BOTH given, the month bucket list is built from that explicit
    range instead of "the `months` trailing calendar months from
    today" — same treatment as get_conversion_funnel_trend(). When
    either is omitted, `months` governs the window exactly as before.

    Returns a list of dicts, oldest month first:
        [{"month": "2026-02", "leads": 40, "responded": 36,
          "no_response_yet": 4, "avg_hours": 3.2, "median_hours": 1.1}, ...]
    (avg_hours/median_hours are None for a month with zero responded
    leads, never a division-by-zero crash or a misleading 0.0.)
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT l.cls_id, l.cls_created_at, MIN(a.created_at) AS first_activity
            FROM leads l LEFT JOIN activity_log a ON a.cls_id = l.cls_id
            GROUP BY l.cls_id
        """).fetchall()
    finally:
        conn.close()

    months_list = []
    if date_from and date_to:
        cursor = datetime.strptime(date_from, "%Y-%m-%d").replace(day=1)
        end_cursor = datetime.strptime(date_to, "%Y-%m-%d").replace(day=1)
        while cursor <= end_cursor:
            months_list.append(cursor.strftime("%Y-%m"))
            cursor = (cursor + timedelta(days=32)).replace(day=1)
    else:
        cursor = datetime.now().replace(day=1)
        for _ in range(months):
            months_list.append(cursor.strftime("%Y-%m"))
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        months_list.reverse()

    buckets = {m: {"leads": 0, "responded": 0, "no_response_yet": 0, "hours": []} for m in months_list}

    for r in rows:
        month = (r["cls_created_at"] or "")[:7]
        if month not in buckets:
            continue
        b = buckets[month]
        b["leads"] += 1
        if not r["first_activity"]:
            b["no_response_yet"] += 1
            continue
        try:
            created = datetime.strptime(r["cls_created_at"], "%Y-%m-%d %H:%M:%S")
            first = datetime.strptime(r["first_activity"], "%Y-%m-%d %H:%M:%S")
            hours = max(0.0, (first - created).total_seconds() / 3600)
            b["hours"].append(hours)
            b["responded"] += 1
        except (ValueError, TypeError):
            pass  # malformed/legacy timestamp — skip this lead's timing, still counted in "leads"

    result = []
    for m in months_list:
        b = buckets[m]
        hours_list = sorted(b["hours"])
        avg_hours = round(sum(hours_list) / len(hours_list), 1) if hours_list else None
        median_hours = round(hours_list[len(hours_list) // 2], 1) if hours_list else None
        result.append({
            "month": m,
            "leads": b["leads"],
            "responded": b["responded"],
            "no_response_yet": b["no_response_yet"],
            "avg_hours": avg_hours,
            "median_hours": median_hours,
        })
    return result


def get_owner_workload(owner=None):
    """
    (v2.12) Report #11 — Owner-wise Workload. Open leads (current_
    stage not in a closed-out state) and open follow-ups/site-visits
    (status='scheduled') per salesperson, right now.

    "Open lead" = current_stage NOT IN ('Booked', 'Lost', 'Unqualified')
    — Re Assigned counts as open (it's mid-handoff, not closed out). A
    NULL current_stage (a Meta lead Job A has fetched but Job B hasn't
    yet Sell.do-synced a stage onto) counts as open too — it's
    unambiguously unresolved, and SQL's NOT IN would otherwise exclude
    it silently via three-valued NULL logic, undercounting exactly the
    freshest, most attention-needing leads.

    owner : scope to one salesperson (their row only). None = every
            owner (+ "Unassigned"), sorted by open_leads desc.

    Returns a list of dicts:
        [{"owner": "Elohar", "open_leads": 14, "open_follow_ups": 5,
          "open_site_visits": 2}, ...]
    """
    CLOSED_STAGES = ("Booked", "Lost", "Unqualified")
    conn = _connect()
    try:
        lead_query = f"""
            SELECT COALESCE(NULLIF(TRIM(lead_owner), ''), 'Unassigned') AS owner, COUNT(*) c
            FROM leads
            WHERE current_stage IS NULL OR current_stage NOT IN ({','.join('?' * len(CLOSED_STAGES))})
        """
        lead_params = list(CLOSED_STAGES)
        if owner:
            lead_query += " AND lead_owner = ?"
            lead_params.append(owner)
        lead_query += " GROUP BY owner"
        lead_rows = conn.execute(lead_query, lead_params).fetchall()

        def _open_count(table):
            query = f"""
                SELECT COALESCE(NULLIF(TRIM(l.lead_owner), ''), 'Unassigned') AS owner, COUNT(*) c
                FROM {table} t JOIN leads l ON l.cls_id = t.cls_id
                WHERE t.status = 'scheduled'
            """
            params = []
            if owner:
                query += " AND l.lead_owner = ?"
                params.append(owner)
            query += " GROUP BY owner"
            return {r["owner"]: r["c"] for r in conn.execute(query, params).fetchall()}

        followup_counts = _open_count("follow_ups")
        visit_counts = _open_count("site_visits")
    finally:
        conn.close()

    merged = {}
    for r in lead_rows:
        merged.setdefault(r["owner"], {"owner": r["owner"], "open_leads": 0, "open_follow_ups": 0, "open_site_visits": 0})
        merged[r["owner"]]["open_leads"] = r["c"]
    for o, c in followup_counts.items():
        merged.setdefault(o, {"owner": o, "open_leads": 0, "open_follow_ups": 0, "open_site_visits": 0})
        merged[o]["open_follow_ups"] = c
    for o, c in visit_counts.items():
        merged.setdefault(o, {"owner": o, "open_leads": 0, "open_follow_ups": 0, "open_site_visits": 0})
        merged[o]["open_site_visits"] = c

    result = list(merged.values())
    result.sort(key=lambda r: r["open_leads"], reverse=True)
    return result


def get_call_activity(owner=None, days=7, date_from=None, date_to=None):
    """
    (v2.12) Report #12 — Call Activity Report. Calls tapped
    (log_call_tap()'s activity_type='call_attempted' rows — a tap-
    count proxy, same honest limit get_todays_activity_counts()'s
    docstring already explains; no duration/connected-status until
    v1.0 Telephony) per lead per salesperson, over the trailing `days`
    window.

    owner : scope to one salesperson's OWNED leads. None = everyone.
    days  : trailing window size — pass 1 for "today", 7 for "this week".
            Ignored when date_from/date_to are both given.

    date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings, default
    None (existing `days`-trailing-window behavior unchanged). When
    both given, scopes to activity_log rows in that explicit range
    instead — powers report_view's universal date-range picker, which
    replaced this report's old daily/weekly toggle.

    Returns a list of dicts, one per lead with >=1 call in the window,
    sorted by call_count desc:
        [{"cls_id": "...", "crm_lead_no": 42, "full_name": "...",
          "lead_owner": "Elohar", "call_count": 3,
          "last_call_at": "2026-07-16 11:03:00"}, ...]
    """
    conn = _connect()
    try:
        query = """
            SELECT l.cls_id, l.crm_lead_no, l.full_name, l.lead_owner,
                   COUNT(*) AS call_count, MAX(a.created_at) AS last_call_at
            FROM activity_log a JOIN leads l ON l.cls_id = a.cls_id
            WHERE a.activity_type = 'call_attempted'
        """
        params = []
        if date_from and date_to:
            query += " AND substr(a.created_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        else:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            query += " AND a.created_at >= ?"
            params.append(since)
        if owner:
            query += " AND l.lead_owner = ?"
            params.append(owner)
        query += " GROUP BY l.cls_id ORDER BY call_count DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# REPORTS v0.6.1 — NEW functions (all additive, v2.13)
# ─────────────────────────────────────────────────────────────

# Mirrors get_todays_activity_counts()'s local METRIC_MAP exactly, kept
# as a SEPARATE module-level constant rather than refactoring that
# function to share it — get_todays_activity_counts() has 3 existing
# call sites (dashboard_today(), the old Daily Scorecard builder) and
# is left byte-for-byte untouched here, per the "never touch unless
# explicitly flagged" rule.
ACTIVITY_METRIC_MAP = {
    "call_attempted":        "calls_attempted",
    "site_visit_scheduled":  "site_visits_created",
    "site_visit_conducted":  "site_visits_conducted",
    "follow_up_scheduled":   "follow_ups_created",
    "follow_up_completed":   "follow_ups_completed",
    "note":                  "notes_added",
    "sitting_done":          "sittings_done",
}


def get_activity_counts_range(actor_email=None, date_from=None, date_to=None):
    """
    (v2.13) Date-range generalization of get_todays_activity_counts() —
    same METRIC_MAP-driven shape (calls_attempted, site_visits_created,
    site_visits_conducted, follow_ups_created, follow_ups_completed,
    notes_added), but scoped to an explicit [date_from, date_to]
    'YYYY-MM-DD' window instead of hardcoded "today". Powers the
    renamed Salesperson Scorecard report (Requirement 5) and the
    Weekly Site Visits Conducted/Scheduled reports (W2/W3) — all three
    read "who did X, attributed via activity_log.actor" rather than
    site_visits/follow_ups.created_by, because created_by only ever
    records who SCHEDULED the row, not who conducted/completed it (the
    schema has no separate "conducted by" column — see v2.13 changelog
    for the schema check that confirmed this).

    date_from/date_to are required (both 'YYYY-MM-DD'); this is a new
    function with no prior all-time behavior to preserve, so unlike
    the modified functions above there's no None-default fallback.

    Returns the same fixed-key dict shape as get_todays_activity_counts().
    """
    result = {key: 0 for key in ACTIVITY_METRIC_MAP.values()}
    conn = _connect()
    try:
        types_placeholder = ", ".join("?" for _ in ACTIVITY_METRIC_MAP)
        params = [date_from, date_to] + list(ACTIVITY_METRIC_MAP.keys())
        query = f"""
            SELECT activity_type, COUNT(*) c
            FROM activity_log
            WHERE substr(created_at, 1, 10) BETWEEN ? AND ?
              AND activity_type IN ({types_placeholder})
        """
        if actor_email:
            query += " AND actor = ?"
            params.append(actor_email)
        query += " GROUP BY activity_type"

        rows = conn.execute(query, params).fetchall()
        for r in rows:
            result[ACTIVITY_METRIC_MAP[r["activity_type"]]] = r["c"]
        return result
    finally:
        conn.close()


def get_leads_received_by_owner(date_from, date_to, owner=None):
    """
    (v2.13) Weekly Report W1 — Weekly Leads Received. Count of leads
    whose cls_created_at falls in [date_from, date_to], grouped by
    their CURRENT lead_owner.

    Uses current lead_owner, not "who it was assigned to at creation
    time" — this schema doesn't track assignment history separately
    from the lead's current state (same limitation every other owner-
    grouped report in this file already has). A lead created this week
    and reassigned since would show under its new owner, not its
    original one — an approximation, same honesty class as the
    Reengagement report's caveat.

    owner : scope to one salesperson's row only. None = every owner
            (+ "Unassigned"), admin/manager view.

    Returns a list of dicts sorted by count desc:
        [{"owner": "Elohar", "count": 7}, ...]
    """
    conn = _connect()
    try:
        query = """
            SELECT COALESCE(NULLIF(TRIM(lead_owner), ''), 'Unassigned') AS owner, COUNT(*) c
            FROM leads
            WHERE substr(cls_created_at, 1, 10) BETWEEN ? AND ?
        """
        params = [date_from, date_to]
        if owner:
            query += " AND lead_owner = ?"
            params.append(owner)
        query += " GROUP BY owner ORDER BY c DESC"
        rows = conn.execute(query, params).fetchall()
        return [{"owner": r["owner"], "count": r["c"]} for r in rows]
    finally:
        conn.close()


_STAGE_BREAKDOWN_GROUP_COLUMNS = {
    "owner": "lead_owner",
    "project": "project_bucket",
    "campaign": "campaign",
}


def get_stage_breakdown(group_by, date_from=None, date_to=None, owner=None):
    """
    (v2.13) Lead Stage Analysis report — views A (by owner), B (by
    project), and C (by campaign), plus Campaign Insights C2 (Campaign
    Stage Distribution, which is exactly view C reused). One
    parameterized function rather than three near-identical ones,
    since the only thing that differs between the views is which
    column to GROUP BY on top of the same leads x current_stage cross-
    tab already used by get_project_pipeline() — group_by is checked
    against a fixed whitelist (_STAGE_BREAKDOWN_GROUP_COLUMNS), never
    interpolated from unchecked input, so there's no injection surface
    even though it ends up in the SQL text.

    group_by : "owner" | "project" | "campaign"
    date_from/date_to : optional 'YYYY-MM-DD' strings. When both
        given, scopes to leads whose cls_created_at falls in range.
        None = every lead regardless of creation date.
    owner : scope to one salesperson's owned leads (independent of
        group_by — e.g. group_by="project" with owner set shows one
        salesperson's own project-wise breakdown).

    "project" grouping (v2.67, F2 Phase 3) reads the stored, kept-in-
    sync leads.project_bucket column directly — previously ran raw
    leads.project values through get_project_bucket() per row; "campaign"
    grouping still runs raw campaign values through _campaign_bucket()
    (blank/NULL -> "Unknown/Manual" — see this module's v2.13 HONESTY
    NOTE on why that bucket currently holds almost everything).

    Returns a dict keyed by group value, each value a dict keyed by
    every stage in ALL_STAGES (all present, 0 if empty) plus "total":
        {"Elohar": {"Incoming": 4, ..., "total": 37}, ...}
    """
    if group_by not in _STAGE_BREAKDOWN_GROUP_COLUMNS:
        raise ValueError(f"get_stage_breakdown: unknown group_by {group_by!r}")
    column = _STAGE_BREAKDOWN_GROUP_COLUMNS[group_by]

    conn = _connect()
    try:
        query = f"SELECT {column} AS raw_group, current_stage FROM leads"
        clauses = []
        params = []
        if owner:
            clauses.append("lead_owner = ?")
            params.append(owner)
        if date_from and date_to:
            clauses.append("substr(cls_created_at, 1, 10) BETWEEN ? AND ?")
            params.extend([date_from, date_to])
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    result = {}
    for r in rows:
        raw = r["raw_group"]
        if group_by == "project":
            # project_bucket is a stored, kept-in-sync column (F2 Phase
            # 1/2) — no per-row recompute needed. Defensive fallback
            # only, mirroring get_project_bucket()'s own falsy-input
            # handling, in case a row somehow predates backfill.
            key = raw if raw else "(unknown)"
        elif group_by == "campaign":
            key = _campaign_bucket(raw)
        else:
            key = raw.strip() if raw and raw.strip() else "Unassigned"
        entry = result.setdefault(key, {stage: 0 for stage in ALL_STAGES})
        entry["total"] = entry.get("total", 0)
        stage = r["current_stage"]
        if stage in entry:
            entry[stage] += 1
        entry["total"] += 1

    return result


def get_site_visits_by_campaign(date_from=None, date_to=None, owner=None):
    """
    (v2.13) Lead Stage Analysis view D, and standalone Campaign
    Insights C6 (Site Visits by Campaign) — the same underlying data,
    reused rather than queried twice (Srikanth's call: keep C6 as its
    own report too, but it reads through this one function).

    Counts EVERY site_visits row (conducted + scheduled + cancelled +
    no_show — "site visits" as booked activity, not just completed
    ones, matching the requirement's "conducted + scheduled" wording)
    whose created_at falls in [date_from, date_to] when given, grouped
    by the owning lead's campaign bucket (_campaign_bucket()).

    Returns a list of dicts sorted by count desc:
        [{"campaign": "Unknown/Manual", "count": 41}, ...]
    """
    conn = _connect()
    try:
        query = """
            SELECT l.campaign AS raw_campaign, COUNT(*) c
            FROM site_visits t JOIN leads l ON l.cls_id = t.cls_id
        """
        clauses = []
        params = []
        if date_from and date_to:
            clauses.append("substr(t.created_at, 1, 10) BETWEEN ? AND ?")
            params.extend([date_from, date_to])
        if owner:
            clauses.append("l.lead_owner = ?")
            params.append(owner)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " GROUP BY raw_campaign"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    by_campaign = {}
    for r in rows:
        key = _campaign_bucket(r["raw_campaign"])
        by_campaign[key] = by_campaign.get(key, 0) + r["c"]

    result = [{"campaign": k, "count": v} for k, v in by_campaign.items()]
    result.sort(key=lambda r: r["count"], reverse=True)
    return result


def get_campaign_lead_volume(date_from=None, date_to=None):
    """
    (v2.13) Campaign Insights C1 — Campaign Lead Volume. Simple lead
    count per campaign bucket, scoped to cls_created_at in
    [date_from, date_to] when given.

    Returns a list of dicts sorted by count desc:
        [{"campaign": "Unknown/Manual", "count": 118}, ...]
    """
    conn = _connect()
    try:
        query = "SELECT campaign AS raw_campaign FROM leads"
        params = []
        if date_from and date_to:
            query += " WHERE substr(cls_created_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    by_campaign = {}
    for r in rows:
        key = _campaign_bucket(r["raw_campaign"])
        by_campaign[key] = by_campaign.get(key, 0) + 1

    result = [{"campaign": k, "count": v} for k, v in by_campaign.items()]
    result.sort(key=lambda r: r["count"], reverse=True)
    return result


def get_campaign_performance(date_from=None, date_to=None):
    """
    (v2.13) Campaign Insights C3 — Campaign Conversion Rate. Exactly
    get_source_performance()'s logic, grouped by campaign bucket
    instead of source. Returns the same shape so cls_reports.py can
    shape both with near-identical code:
        [{"campaign": "Unknown/Manual", "total": 118, "prospect_plus": 40,
          "opportunity_plus": 18, "site_visited_plus": 6, "booked": 1,
          "lost_unqualified": 22}, ...]
    """
    PROSPECT_PLUS = ("Prospect", "Opportunity", "Site Visited", "Booked")
    OPPORTUNITY_PLUS = ("Opportunity", "Site Visited", "Booked")
    SITE_VISITED_PLUS = ("Site Visited", "Booked")

    conn = _connect()
    try:
        query = "SELECT campaign AS raw_campaign, current_stage, COUNT(*) c FROM leads"
        params = []
        if date_from and date_to:
            query += " WHERE substr(cls_created_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        query += " GROUP BY raw_campaign, current_stage"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    by_campaign = {}
    for r in rows:
        camp = _campaign_bucket(r["raw_campaign"])
        bucket = by_campaign.setdefault(camp, {
            "campaign": camp, "total": 0, "prospect_plus": 0,
            "opportunity_plus": 0, "site_visited_plus": 0,
            "booked": 0, "lost_unqualified": 0,
        })
        stage, c = r["current_stage"], r["c"]
        bucket["total"] += c
        if stage in PROSPECT_PLUS:
            bucket["prospect_plus"] += c
        if stage in OPPORTUNITY_PLUS:
            bucket["opportunity_plus"] += c
        if stage in SITE_VISITED_PLUS:
            bucket["site_visited_plus"] += c
        if stage == "Booked":
            bucket["booked"] += c
        if stage in ("Lost", "Unqualified"):
            bucket["lost_unqualified"] += c

    result = list(by_campaign.values())
    result.sort(key=lambda r: r["total"], reverse=True)
    return result


def get_campaign_lost_reasons(date_from=None, date_to=None):
    """
    (v2.13) Campaign Insights C4 — Campaign Lost Reason Breakdown.
    Exactly get_lost_reason_breakdown()'s logic, grouped by campaign
    bucket in addition to (kept as its own column, not merged with)
    reason, so cls_reports.py can render either a campaign x reason
    table or a grouped bar chart.

    Returns a list of dicts sorted by count desc:
        [{"campaign": "Unknown/Manual", "reason": "Budget does not match",
          "count": 8}, ...]
    """
    conn = _connect()
    try:
        query = """
            SELECT campaign AS raw_campaign,
                   COALESCE(NULLIF(TRIM(stage_reason), ''), '(no reason recorded)') AS reason,
                   COUNT(*) c
            FROM leads
            WHERE current_stage IN ('Lost', 'Unqualified')
        """
        params = []
        if date_from and date_to:
            query += " AND substr(stage_updated_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        query += " GROUP BY raw_campaign, reason"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    by_key = {}
    for r in rows:
        camp = _campaign_bucket(r["raw_campaign"])
        key = (camp, r["reason"])
        by_key[key] = by_key.get(key, 0) + r["c"]

    result = [{"campaign": c, "reason": rsn, "count": cnt} for (c, rsn), cnt in by_key.items()]
    result.sort(key=lambda r: r["count"], reverse=True)
    return result


def get_campaign_response_time(date_from=None, date_to=None):
    """
    (v2.13) Campaign Insights C5 — Campaign First-Response Time.
    Exactly get_first_response_time()'s per-lead hours-to-first-
    activity computation, grouped by campaign bucket instead of month.

    date_from/date_to : optional 'YYYY-MM-DD' strings scoping to leads
        whose cls_created_at falls in range. None = every lead.

    Returns a list of dicts sorted by leads desc:
        [{"campaign": "Unknown/Manual", "leads": 118, "responded": 95,
          "no_response_yet": 23, "avg_hours": 4.1, "median_hours": 1.8}, ...]
    (avg_hours/median_hours are None for a campaign with zero responded
    leads, never a division-by-zero crash or a misleading 0.0.)
    """
    conn = _connect()
    try:
        query = """
            SELECT l.campaign AS raw_campaign, l.cls_created_at,
                   MIN(a.created_at) AS first_activity
            FROM leads l LEFT JOIN activity_log a ON a.cls_id = l.cls_id
        """
        params = []
        if date_from and date_to:
            query += " WHERE substr(l.cls_created_at, 1, 10) BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        query += " GROUP BY l.cls_id"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    buckets = {}
    for r in rows:
        camp = _campaign_bucket(r["raw_campaign"])
        b = buckets.setdefault(camp, {"leads": 0, "responded": 0, "no_response_yet": 0, "hours": []})
        b["leads"] += 1
        if not r["first_activity"]:
            b["no_response_yet"] += 1
            continue
        try:
            created = datetime.strptime(r["cls_created_at"], "%Y-%m-%d %H:%M:%S")
            first = datetime.strptime(r["first_activity"], "%Y-%m-%d %H:%M:%S")
            hours = max(0.0, (first - created).total_seconds() / 3600)
            b["hours"].append(hours)
            b["responded"] += 1
        except (ValueError, TypeError):
            pass  # malformed/legacy timestamp — skip this lead's timing, still counted in "leads"

    result = []
    for camp, b in buckets.items():
        hours_list = sorted(b["hours"])
        avg_hours = round(sum(hours_list) / len(hours_list), 1) if hours_list else None
        median_hours = round(hours_list[len(hours_list) // 2], 1) if hours_list else None
        result.append({
            "campaign": camp,
            "leads": b["leads"],
            "responded": b["responded"],
            "no_response_yet": b["no_response_yet"],
            "avg_hours": avg_hours,
            "median_hours": median_hours,
        })
    result.sort(key=lambda r: r["leads"], reverse=True)
    return result


# ─────────────────────────────────────────────────────────────
# COMPLETION FLAGS  —  Risk 1 fix: chain jobs by signal, not clock
# ─────────────────────────────────────────────────────────────
# Instead of "Job B runs 10 min after Job A", Job A writes a flag
# when it FINISHES. Job B checks the flag is present AND fresh
# before running. If Job A ran long or failed, Job B safely skips.

import json

def set_flag(job_name):
    """Job calls this on successful completion. Stamps current time."""
    flags = {}
    if os.path.exists(FLAG_FILE):
        try:
            with open(FLAG_FILE, "r") as f:
                flags = json.load(f)
        except Exception:
            flags = {}
    flags[job_name] = _now()
    with open(FLAG_FILE, "w") as f:
        json.dump(flags, f, indent=2)


def get_flag(job_name):
    """Return the ISO timestamp string of a job's last completion, or None."""
    if not os.path.exists(FLAG_FILE):
        return None
    try:
        with open(FLAG_FILE, "r") as f:
            return json.load(f).get(job_name)
    except Exception:
        return None


def is_flag_fresh(job_name, max_age_minutes=120):
    """
    True if <job_name> completed within the last <max_age_minutes>.
    A downstream job calls this to decide 'is my upstream data current
    enough to proceed?'. If stale or missing -> downstream job skips
    this cycle rather than acting on old/absent data.
    """
    ts = get_flag(job_name)
    if not ts:
        return False
    try:
        completed = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - completed) <= timedelta(minutes=max_age_minutes)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# STATS  —  quick counts for logs and sanity checks
# ─────────────────────────────────────────────────────────────

def stats():
    """Return a small dict of CLS counts — useful in every job's log."""
    conn = _connect()
    try:
        total      = conn.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]
        with_lg    = conn.execute("SELECT COUNT(*) c FROM leads WHERE leadgen_id IS NOT NULL").fetchone()["c"]
        selldo_only= conn.execute("SELECT COUNT(*) c FROM leads WHERE source='selldo_only'").fetchone()["c"]
        unfired    = len(get_unfired_leads())
        imported_historical = conn.execute("SELECT COUNT(*) c FROM leads WHERE match_tier='imported'").fetchone()["c"]
        return {
            "total_leads"      : total,
            "with_leadgen_id"  : with_lg,
            "selldo_only"      : selldo_only,
            "pending_fire"     : unfired,
            "imported_historical" : imported_historical,
            "syncable_leads"   : total - imported_historical,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# CROSS-DATABASE DIFF  —  v2.23, CLS1/CLS2 split support
# ─────────────────────────────────────────────────────────────
# The ONLY function in this module that opens a database file other than
# DB_FILE. Kept narrowly scoped and read-only — this is the sole exception
# to "every job/route reads/writes through this module's own DB_FILE."

def get_leads_snapshot(db_path):
    """
    Read-only. Opens db_path directly (NOT the module DB_FILE) and
    returns every lead's comparison-relevant fields, for cross-database
    diffing only (cls_parallel_diff.py). Never used by any job or the
    CRM app during normal operation.
    Returns a list of dicts: cls_id, crm_lead_no, full_name, phone_raw,
    phone_norm, email_norm, project, current_stage, lead_owner,
    stage_updated_at.
    """
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT cls_id, crm_lead_no, full_name, phone_raw, phone_norm,
                   email_norm, project, current_stage, lead_owner,
                   stage_updated_at
            FROM leads
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# JOB RESULT LOG  —  v2.23, one-line-per-run human-glance status
# ─────────────────────────────────────────────────────────────

def write_job_result(job_name, success, summary):
    """
    Appends ONE line to C:\\CLS\\job_results.txt after every job run.
    Format: [YYYY-MM-DD HH:MM:SS] Job Name: SUCCESS/FAILED — summary
    This file is for a human to glance at — no stack traces, no
    multi-line detail. Full detail stays in the job's own log file.
    """
    status = "SUCCESS" if success else "FAILED"
    line = f"[{_now()}] {job_name}: {status} — {summary}\n"
    path = os.path.join(BASE_DIR, "job_results.txt")
    with open(path, "a", encoding="utf-8", errors="replace") as f:
        f.write(line)


# ─────────────────────────────────────────────────────────────
# APX ATTENDANCE  —  v0.9 pilot, Build Order Step 2 (v2.39)
# ─────────────────────────────────────────────────────────────
# Data-access functions only — schema was added in v2.38 (see that
# changelog entry for the full table list). This is a SIBLING module:
# nothing here reads or writes leads/activity_log/assignments, and
# nothing in the lead-management code calls into this section.

# Config-not-code, same idiom as CRM_ROLES/OVERSIGHT_ROLES above.
ATTENDANCE_STATUSES = ("present", "late", "absent", "weekoff", "leave", "half_day")

# (v2.51) Hardcoded workday window — replaces the app_settings
# ['attendance_late_after_time'] lookup compute_punch_in_timing() used
# to do on every punch. The app_settings row itself is left in place,
# untouched, just no longer read by anything. WORKDAY_END_TIME isn't
# wired into any logic yet — added now so it and WORKDAY_START_TIME
# share one definition for whatever reads a "workday" boundary next.
WORKDAY_START_TIME = "10:30"
WORKDAY_END_TIME = "17:30"

# The only two statuses an employee can self-service set via
# set_self_service_attendance_status() below. present/late/absent are
# punch-derived only (Step 4's API endpoints), never settable here.
SELF_SERVICE_ATTENDANCE_STATUSES = ("weekoff", "leave")

# The only attendance columns a correction request may target. Used
# BOTH when a request is created (create_correction_request) and when
# it's applied (resolve_attendance_correction) — the same allowlist in
# both places means a crafted field_changed value can never reach raw
# SQL as a column name, even though field_changed is text a
# salesperson controls via a form.
ATTENDANCE_CORRECTION_FIELDS = ("status", "login_ts", "logout_ts")


def get_attendance_for_date(user_id, date_str):
    """(v2.39) One user's attendance row for one date ('YYYY-MM-DD'),
    or None if nothing recorded yet. Powers the employee /attendance
    page's "today's status" tile."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM attendance WHERE user_id=? AND attendance_date=?",
            (user_id, date_str)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_attendance_month(user_id, year, month):
    """(v2.39) All of one user's attendance rows within one calendar
    month, keyed by 'YYYY-MM-DD', for the /attendance mini calendar.
    Days with no row simply aren't in the dict — the template renders
    those as blank/no-status, not as "absent" (absence is a punch-
    derived status computed elsewhere, not the mere lack of a row)."""
    conn = _connect()
    try:
        prefix = f"{year:04d}-{month:02d}"
        rows = conn.execute(
            "SELECT * FROM attendance WHERE user_id=? AND attendance_date LIKE ? "
            "ORDER BY attendance_date",
            (user_id, f"{prefix}%")
        ).fetchall()
        return {r["attendance_date"]: dict(r) for r in rows}
    finally:
        conn.close()


def get_attendance_totals_for_month(year, month, owner_scope=None):
    """
    (v2.41) Per-user status counts + a geofence-breach count for one
    calendar month — powers the admin Attendance Dashboard's totals
    row/table (Build Order Step 3).

    owner_scope=None returns every ACTIVE user (the oversight-role
    "All employees" view), including a user with ZERO attendance rows
    that month — shown as all-zero counts, not silently omitted, so a
    forgotten/never-punched teammate is visible rather than invisible.
    owner_scope=<user_id> scopes to exactly that one user (a
    salesperson's own view, or an admin/manager drilling into one
    employee), regardless of active flag — an admin reviewing a
    recently-deactivated employee's last month should still see them.
    (v2.51) owner_scope=None also excludes role='admin' from the "All
    employees" list — admin isn't a scoped employee to report on. This
    does NOT apply to owner_scope=<user_id>: an admin drilling into
    their OWN or another specific user's record still works unchanged.

    One query for the user list, one query for every attendance row in
    the month, merged in Python — deliberately not a single GROUP BY
    (this codebase's small team size, ~4 sales executives per the
    handoff brief, doesn't need it; see cls_db.py's own "don't
    pre-optimise" precedent re: SQLite/WAL and small concurrency).

    Returns a list of dicts: {user_id, full_name, email, <one key per
    ATTENDANCE_STATUSES value>, geofence_breaches}, ordered by
    full_name.
    """
    conn = _connect()
    try:
        if owner_scope is not None:
            users = conn.execute(
                "SELECT user_id, full_name, email FROM users WHERE user_id=?",
                (owner_scope,)
            ).fetchall()
        else:
            users = conn.execute(
                "SELECT user_id, full_name, email FROM users WHERE active=1 "
                "AND role != 'admin' ORDER BY full_name COLLATE NOCASE"
            ).fetchall()

        prefix = f"{year:04d}-{month:02d}"
        if owner_scope is not None:
            rows = conn.execute(
                "SELECT user_id, status, login_geofence_breach, logout_geofence_breach "
                "FROM attendance WHERE user_id=? AND attendance_date LIKE ?",
                (owner_scope, f"{prefix}%")
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT user_id, status, login_geofence_breach, logout_geofence_breach "
                "FROM attendance WHERE attendance_date LIKE ?",
                (f"{prefix}%",)
            ).fetchall()

        by_user = {}
        for r in rows:
            entry = by_user.setdefault(r["user_id"], {s: 0 for s in ATTENDANCE_STATUSES})
            if r["status"] in entry:
                entry[r["status"]] += 1
            if r["login_geofence_breach"] or r["logout_geofence_breach"]:
                entry["_breaches"] = entry.get("_breaches", 0) + 1

        totals = []
        for u in users:
            counts = by_user.get(u["user_id"], {})
            totals.append({
                "user_id": u["user_id"], "full_name": u["full_name"], "email": u["email"],
                **{s: counts.get(s, 0) for s in ATTENDANCE_STATUSES},
                "geofence_breaches": counts.get("_breaches", 0),
            })
        return totals
    finally:
        conn.close()


def get_today_attendance_overview(date_str):
    """
    (v2.46) Chunk C — "Who's present today" admin view. Every ACTIVE
    user LEFT JOINed to their attendance row for date_str (if any),
    same "every active user shown, none silently omitted" convention
    as get_attendance_totals_for_month()'s owner_scope=None branch.
    (v2.51) Excludes role='admin' — admin doesn't appear in "who's
    present today," same exclusion as get_attendance_totals_for_month()
    below.

    Returns a list of dicts, one per active user, ordered by
    full_name: {user_id, full_name, email, status, not_marked,
    login_ts, logout_ts, late_minutes, login_geofence_breach,
    logout_geofence_breach}. status is the RAW attendance.status value
    (present/late/absent/weekoff/leave/half_day) when a row exists —
    deliberately not collapsed to a smaller "not binary" bucket set,
    since that would hide real data the schema already tracks and the
    existing Dashboard already surfaces. When no row exists yet for
    today (nothing punched, no self-service status set), status is
    None and not_marked is True — the caller/template should render
    that as "Not marked yet," distinct from an explicit 'absent'
    status, since the two mean different things (hasn't acted yet vs.
    a recorded absence).
    """
    conn = _connect()
    try:
        users = conn.execute(
            "SELECT user_id, full_name, email FROM users WHERE active=1 "
            "AND role != 'admin' ORDER BY full_name COLLATE NOCASE"
        ).fetchall()
        rows = conn.execute(
            "SELECT * FROM attendance WHERE attendance_date=?", (date_str,)
        ).fetchall()
        by_user = {r["user_id"]: r for r in rows}

        overview = []
        for u in users:
            a = by_user.get(u["user_id"])
            overview.append({
                "user_id": u["user_id"],
                "full_name": u["full_name"],
                "email": u["email"],
                "status": a["status"] if a else None,
                "not_marked": a is None,
                "login_ts": a["login_ts"] if a else None,
                "logout_ts": a["logout_ts"] if a else None,
                "late_minutes": a["late_minutes"] if a else 0,
                "login_geofence_breach": a["login_geofence_breach"] if a else 0,
                "logout_geofence_breach": a["logout_geofence_breach"] if a else 0,
            })
        return overview
    finally:
        conn.close()


def _get_or_create_attendance_row(conn, user_id, date_str):
    """(v2.39, internal) Returns an attendance_id for user_id+date_str,
    creating a bare row (no status/punch data) if none exists yet.
    Used by create_correction_request() so a correction can be
    requested even for a day with no punch at all (e.g. a forgotten
    punch-in) — takes an already-open conn/transaction, never opens
    its own, so the INSERT and the correction row it enables land in
    the SAME commit."""
    row = conn.execute(
        "SELECT attendance_id FROM attendance WHERE user_id=? AND attendance_date=?",
        (user_id, date_str)
    ).fetchone()
    if row:
        return row["attendance_id"]
    now = _now()
    cur = conn.execute(
        "INSERT INTO attendance (user_id, attendance_date, created_at, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (user_id, date_str, now, now)
    )
    return cur.lastrowid


def set_self_service_attendance_status(user_id, date_str, status, actor):
    """
    (v2.39) Employee self-service Weekoff/Leave marking. status must be
    in SELF_SERVICE_ATTENDANCE_STATUSES — present/late/absent are
    punch-derived only and never settable through this function.

    Refuses to overwrite a day that already has punch data (login_ts
    set) — same "never discard" posture as the rest of this file; a
    mis-click can't silently erase a punched day's photo/geofence
    record. A day with an existing DIFFERENT self-service status (e.g.
    already marked leave, now trying weekoff) is also refused, so a
    double-submit needs an explicit admin correction, not a silent
    overwrite. Re-submitting the SAME status is a harmless no-op.

    actor (v2.40) is written to attendance.last_modified_by on both the
    insert and update paths below — the "who last touched this row"
    audit trail flagged after Step 2 and added in v2.40's self-healing
    column.

    Returns (ok: bool, message: str).
    """
    if status not in SELF_SERVICE_ATTENDANCE_STATUSES:
        return False, "Invalid status."
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT * FROM attendance WHERE user_id=? AND attendance_date=?",
            (user_id, date_str)
        ).fetchone()
        now = _now()
        if existing is None:
            conn.execute(
                "INSERT INTO attendance (user_id, attendance_date, status, created_at, "
                "updated_at, last_modified_by) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, date_str, status, now, now, actor)
            )
        elif existing["login_ts"]:
            return False, ("That day already has a punch-in recorded — "
                            "submit a Correction Request instead.")
        elif existing["status"] and existing["status"] != status:
            return False, (f"That day is already marked '{existing['status']}' — "
                            "submit a Correction Request instead.")
        else:
            conn.execute(
                "UPDATE attendance SET status=?, updated_at=?, last_modified_by=? WHERE attendance_id=?",
                (status, now, actor, existing["attendance_id"])
            )
        conn.commit()
        return True, f"Marked {date_str} as {status}."
    finally:
        conn.close()


def _can_self_service_mark(conn, user_id, date_str, status):
    """
    (v2.45) Read-only dry run of set_self_service_attendance_status()'s
    own feasibility rule, on an ALREADY-OPEN connection so callers can
    check every date in a multi-date submission before writing anything.
    Returns (ok: bool, error_message_or_None).
    """
    existing = conn.execute(
        "SELECT * FROM attendance WHERE user_id=? AND attendance_date=?",
        (user_id, date_str)
    ).fetchone()
    if existing is None:
        return True, None
    if existing["login_ts"]:
        return False, (f"{date_str} already has a punch-in recorded — "
                        "submit a Correction Request instead.")
    if existing["status"] and existing["status"] != status:
        return False, (f"{date_str} is already marked '{existing['status']}' — "
                        "submit a Correction Request instead.")
    return True, None


def _group_contiguous_dates(dates):
    """
    (v2.45) Sorted/deduped list of 'YYYY-MM-DD' strings -> list of
    (start, end) tuples, merging consecutive calendar days into one
    range each. A single non-adjacent date becomes its own (d, d) range.
    """
    if not dates:
        return []
    parsed = sorted(datetime.strptime(d, "%Y-%m-%d").date() for d in set(dates))
    ranges = []
    range_start = prev = parsed[0]
    for d in parsed[1:]:
        if (d - prev).days == 1:
            prev = d
            continue
        ranges.append((range_start.strftime("%Y-%m-%d"), prev.strftime("%Y-%m-%d")))
        range_start = prev = d
    ranges.append((range_start.strftime("%Y-%m-%d"), prev.strftime("%Y-%m-%d")))
    return ranges


def submit_weekoff(user_id, date_str, actor):
    """
    (v2.45) Chunk B — employee self-service Weekoff via the new
    weekoff_log table. Order of checks, all read-only before any write:
      1. Duplicate — a weekoff_log row already exists for this user+date.
      2. Conflict — date falls inside an existing leave_requests range
         for this user.
      3. Feasibility — the day can actually be marked (no punch data,
         no conflicting different status), via _can_self_service_mark().
    Only if all three pass: syncs attendance.status='weekoff' via the
    EXISTING set_self_service_attendance_status() (so the Dashboard/
    export/today-badge keep working unchanged), THEN inserts the
    weekoff_log row last. Returns (ok: bool, message: str).
    """
    conn = _connect()
    try:
        dup = conn.execute(
            "SELECT 1 FROM weekoff_log WHERE user_id=? AND date=?",
            (user_id, date_str)
        ).fetchone()
        if dup:
            return False, f"Already marked as Weekoff for {date_str}."

        leave_conflict = conn.execute(
            "SELECT 1 FROM leave_requests WHERE user_id=? AND start_date<=? AND end_date>=?",
            (user_id, date_str, date_str)
        ).fetchone()
        if leave_conflict:
            return False, f"{date_str} already has an approved Leave covering it."

        ok, err = _can_self_service_mark(conn, user_id, date_str, "weekoff")
        if not ok:
            return False, err
    finally:
        conn.close()

    ok, message = set_self_service_attendance_status(user_id, date_str, "weekoff", actor)
    if not ok:
        return False, message

    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO weekoff_log (user_id, date, submitted_at) VALUES (?, ?, ?)",
            (user_id, date_str, _now())
        )
        conn.commit()
        return True, f"Weekoff confirmed for {date_str}."
    finally:
        conn.close()


def submit_leave(user_id, dates, actor):
    """
    (v2.45) Chunk B — employee self-service Leave via the new
    leave_requests table. `dates` is a list of individual 'YYYY-MM-DD'
    strings from the UI's multi-select calendar (order/duplicates don't
    matter — deduped/sorted here). Consecutive calendar days are merged
    into ONE leave_requests row per contiguous run via
    _group_contiguous_dates() — the chosen interpretation of the
    start_date/end_date schema, not one row per individual day.

    Validates ALL resulting ranges before writing anything:
      1. Past dates — defense in depth. The UI already disables these,
         but a request must never trust client-only validation for a
         date range going into the DB.
      2. Each range against every existing leave_requests row for this
         user (any overlap) and every weekoff_log date for this user
         inside that range.
      3. Feasibility of every individual date in every range, via
         _can_self_service_mark().
    Any single failure rejects the WHOLE submission — nothing is
    inserted, same "no partial save" rule as submit_weekoff(). Only
    after every range clears every check does it sync attendance.status
    for every date (existing set_self_service_attendance_status()),
    then insert one leave_requests row per range. Returns (ok: bool,
    message: str).
    """
    if not dates:
        return False, "No dates selected."

    today_str = datetime.now().strftime("%Y-%m-%d")
    if any(d < today_str for d in dates):
        return False, "Leave can only be requested for today or a future date."

    ranges = _group_contiguous_dates(dates)

    conn = _connect()
    try:
        for start, end in ranges:
            overlap = conn.execute(
                "SELECT 1 FROM leave_requests WHERE user_id=? AND start_date<=? AND end_date>=?",
                (user_id, end, start)
            ).fetchone()
            if overlap:
                return False, f"{start} to {end} overlaps an existing Leave request."

            weekoff_conflict = conn.execute(
                "SELECT 1 FROM weekoff_log WHERE user_id=? AND date>=? AND date<=?",
                (user_id, start, end)
            ).fetchone()
            if weekoff_conflict:
                return False, f"{start} to {end} includes a date already marked Weekoff."

        all_dates = []
        for start, end in ranges:
            d = datetime.strptime(start, "%Y-%m-%d").date()
            end_d = datetime.strptime(end, "%Y-%m-%d").date()
            while d <= end_d:
                all_dates.append(d.strftime("%Y-%m-%d"))
                d += timedelta(days=1)

        for date_str in all_dates:
            ok, err = _can_self_service_mark(conn, user_id, date_str, "leave")
            if not ok:
                return False, err
    finally:
        conn.close()

    for date_str in all_dates:
        ok, message = set_self_service_attendance_status(user_id, date_str, "leave", actor)
        if not ok:
            return False, message

    conn = _connect()
    try:
        now = _now()
        for start, end in ranges:
            conn.execute(
                "INSERT INTO leave_requests (user_id, start_date, end_date, submitted_at) VALUES (?, ?, ?, ?)",
                (user_id, start, end, now)
            )
        conn.commit()
        if len(ranges) == 1:
            return True, f"Leave confirmed for {ranges[0][0]} to {ranges[0][1]}."
        return True, f"Leave confirmed for {len(ranges)} date range(s)."
    finally:
        conn.close()


def create_correction_request(user_id, date_str, field_changed, new_value, note, actor):
    """
    (v2.39) Employee-initiated attendance_corrections row, status=
    'pending'. field_changed is validated against
    ATTENDANCE_CORRECTION_FIELDS; new_value is additionally validated
    against ATTENDANCE_STATUSES when field_changed=='status', or
    parsed as 'YYYY-MM-DD HH:MM:SS' when correcting login_ts/logout_ts
    — rejected up front with a friendly message rather than stored as
    unusable text that only surfaces as a problem when an admin later
    tries to approve it.

    Auto-creates the day's attendance row if none exists yet (e.g. a
    forgotten punch-in) via _get_or_create_attendance_row(), on the
    SAME connection/transaction as the correction insert.

    Returns (ok: bool, message: str).
    """
    if field_changed not in ATTENDANCE_CORRECTION_FIELDS:
        return False, "Invalid field selected."
    if field_changed == "status":
        if new_value not in ATTENDANCE_STATUSES:
            return False, "Invalid status value."
    else:  # login_ts / logout_ts
        try:
            datetime.strptime(new_value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return False, "Time must be in YYYY-MM-DD HH:MM:SS format."

    conn = _connect()
    try:
        attendance_id = _get_or_create_attendance_row(conn, user_id, date_str)
        old_row = conn.execute(
            "SELECT * FROM attendance WHERE attendance_id=?", (attendance_id,)
        ).fetchone()
        old_value = old_row[field_changed] if old_row else None
        now = _now()
        conn.execute(
            "INSERT INTO attendance_corrections "
            "(attendance_id, requested_by, request_note, field_changed, old_value, "
            " new_value, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (attendance_id, actor, note, field_changed, old_value, new_value, now)
        )
        conn.commit()
        return True, "Correction request submitted."
    finally:
        conn.close()


def list_attendance_corrections(status=None):
    """(v2.39) Admin Settings > Attendance > Corrections queue. Joins
    attendance + users for display context (who, which day). status=
    None returns every request regardless of status (for a combined
    pending+history view); pass 'pending' to scope to the actionable
    queue only."""
    conn = _connect()
    try:
        query = (
            "SELECT c.*, a.user_id, a.attendance_date, u.full_name, u.email "
            "FROM attendance_corrections c "
            "JOIN attendance a ON a.attendance_id = c.attendance_id "
            "JOIN users u ON u.user_id = a.user_id"
        )
        params = ()
        if status:
            query += " WHERE c.status = ?"
            params = (status,)
        query += " ORDER BY c.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def resolve_attendance_correction(correction_id, approve, actor):
    """
    (v2.39) Approve or reject one pending attendance_corrections row.
    Approving applies new_value to the linked attendance row's
    field_changed column — field_changed is re-checked against
    ATTENDANCE_CORRECTION_FIELDS here too (belt-and-suspenders with the
    check already done at request-creation time in
    create_correction_request(), since this is the function that
    actually interpolates a column name into SQL). Rejecting just
    marks the row resolved with no attendance change. Refuses to
    re-resolve a request that's already been approved/rejected.

    actor (v2.40) is written to the attendance row's last_modified_by
    when approving — same audit column set_self_service_attendance_
    status() writes, so "who last touched this row" covers both paths
    that can change a day's status/times outside the Step 4 punch API.

    Returns (ok: bool, message: str).
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM attendance_corrections WHERE correction_id=?",
            (correction_id,)
        ).fetchone()
        if not row:
            return False, "Correction request not found."
        if row["status"] != "pending":
            return False, "This request has already been resolved."

        now = _now()
        if approve:
            field = row["field_changed"]
            if field not in ATTENDANCE_CORRECTION_FIELDS:
                return False, "Unrecognized field — cannot apply."
            conn.execute(
                f"UPDATE attendance SET {field}=?, updated_at=?, last_modified_by=? WHERE attendance_id=?",
                (row["new_value"], now, actor, row["attendance_id"])
            )
        conn.execute(
            "UPDATE attendance_corrections SET status=?, actor=?, resolved_at=? "
            "WHERE correction_id=?",
            ("approved" if approve else "rejected", actor, now, correction_id)
        )
        conn.commit()
        return True, ("Correction approved." if approve else "Correction rejected.")
    finally:
        conn.close()


def apply_admin_attendance_exemption(user_id, date_str, field_changed, new_value, note, actor):
    """
    (v2.46) Chunk C — proactive admin override, usable WITHOUT a
    pending attendance_corrections row already existing (unlike the
    reactive employee-submit -> admin-approve flow above). Wiring:
    calls the EXISTING create_correction_request() unmodified (same
    field_changed/new_value validation an employee's own submission
    goes through — note defaults to "Proactive admin exemption" if
    none given, so it reads distinctly from a real employee request in
    the Corrections history), looks up the 'pending' row it just
    inserted, then calls the EXISTING resolve_attendance_correction()
    unmodified with approve=True. Neither existing function's code or
    signature changes — this only glues the two together back-to-back
    instead of leaving a human approval step between them. The row is
    created and resolved within the same call, so it never sits
    pending — nothing is left around to duplicate or collide with.

    KNOWN EDGE CASE (pre-existing category, not introduced here): if
    an employee has a SEPARATE pending request open on the same
    attendance_id/field_changed at the same moment an admin uses this,
    whichever gets resolved last simply wins (plain last-write-wins on
    the attendance row) — the same race that already exists if two
    corrections ever targeted the same field on the same day. Not
    solved here; flagged for awareness only.

    Returns (ok: bool, message: str).
    """
    ok, message = create_correction_request(
        user_id, date_str, field_changed, new_value,
        note or "Proactive admin exemption", actor
    )
    if not ok:
        return False, message

    conn = _connect()
    try:
        attendance_id = _get_or_create_attendance_row(conn, user_id, date_str)
        row = conn.execute(
            "SELECT correction_id FROM attendance_corrections "
            "WHERE attendance_id=? AND field_changed=? AND status='pending' "
            "ORDER BY correction_id DESC LIMIT 1",
            (attendance_id, field_changed)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return False, "Could not locate the request just created."

    return resolve_attendance_correction(row["correction_id"], True, actor)


def list_attendance_holidays():
    """(v2.39) Full holiday calendar, date-ascending, for the admin
    Settings > Attendance > Holidays screen."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM attendance_holidays ORDER BY holiday_date"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_attendance_holiday(holiday_date, label):
    """(v2.39) Add/overwrite one holiday. INSERT OR REPLACE keyed on
    holiday_date (the table's PK) — re-saving the same date just
    updates its label, same idiom as project_aliases elsewhere."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO attendance_holidays (holiday_date, label, created_at) "
            "VALUES (?, ?, ?)",
            (holiday_date, label, _now())
        )
        conn.commit()
    finally:
        conn.close()


def delete_attendance_holiday(holiday_date):
    """(v2.39) Remove one holiday. No blocking logic, same "deletes are
    safe" reasoning as delete_project_alias()."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM attendance_holidays WHERE holiday_date=?", (holiday_date,))
        conn.commit()
    finally:
        conn.close()


def list_attendance_project_locations():
    """(v2.39) All configured project GPS locations, for the admin
    Settings > Attendance > Projects screen."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM attendance_project_locations ORDER BY project_bucket"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_attendance_project_location(project_bucket, latitude, longitude, radius_meters):
    """(v2.39) Add/overwrite one project's GPS location + geofence
    radius. INSERT OR REPLACE keyed on project_bucket (the table's PK),
    same idiom as add_attendance_holiday() above."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO attendance_project_locations "
            "(project_bucket, latitude, longitude, radius_meters, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_bucket, latitude, longitude, radius_meters, _now())
        )
        conn.commit()
    finally:
        conn.close()


def set_user_assigned_project(user_id, project_bucket):
    """(v2.39) Admin-set link from a user to their attendance geofence
    project (users.assigned_project, the v2.38 self-healing column).
    project_bucket='' from a form is normalized to NULL (not yet
    assigned), not stored as an empty string."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE users SET assigned_project=? WHERE user_id=?",
            (project_bucket or None, user_id)
        )
        conn.commit()
    finally:
        conn.close()


# ── APX Attendance v0.9 pilot — token-auth API business logic (v2.42, Build Order Step 4) ──
# Reuses the EXISTING user_api_tokens/verify_api_token() mechanism
# (see the v2.42 changelog note on user_api_tokens above) — no second
# auth scheme. These functions are called by app.py's 4 new
# /api/attendance/* routes, never directly by a template.

def get_attendance_project_location(project_bucket):
    """(v2.42) One project's configured GPS location, or None if
    project_bucket is falsy or has no attendance_project_locations row
    yet — the caller (check_geofence_breach) treats "no config" as
    "can't check, so no breach", never an error."""
    if not project_bucket:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM attendance_project_locations WHERE project_bucket=?",
            (project_bucket,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def check_geofence_breach(project_bucket, lat, lng):
    """
    (v2.42) True if (lat, lng) is outside the configured radius for
    project_bucket's attendance_project_locations row, via the
    haversine great-circle distance formula (stdlib math only, no new
    dependency). False whenever there's nothing to compare against —
    no assigned_project, no configured lat/long/radius for it, or a
    missing lat/lng reading — "can't determine" defaults to "no
    breach", NEVER to "breach"/block. Per the v0.9 spec: a geofence
    breach is a flag for admin review, never a reason to refuse a
    punch — this function only ever adds information, never gates one.
    """
    if lat is None or lng is None:
        return False
    loc = get_attendance_project_location(project_bucket)
    if not loc or loc["latitude"] is None or loc["longitude"] is None or not loc["radius_meters"]:
        return False

    R = 6371000  # Earth radius, meters
    lat1, lng1, lat2, lng2 = map(math.radians, [lat, lng, loc["latitude"], loc["longitude"]])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    distance_m = 2 * R * math.asin(math.sqrt(a))
    return distance_m > loc["radius_meters"]


# ─────────────────────────────────────────────────────────────
# PAYROLL v1.0 (v2.87)
# ─────────────────────────────────────────────────────────────
# Flat monthly salary per user (salary_slabs), no incentive/commission
# component. Admin is fully excluded — no salary_slabs row is ever
# created or accepted for an admin (see upsert_salary_slab()'s refusal
# below), same posture as get_today_attendance_overview()'s existing
# role != 'admin' exclusion elsewhere in this file. Push-button, admin-
# triggered only (compute_salary_for_month()) — NOT a scheduled job.
#
# 'half_day' is folded into "present" — zero cost — ONLY inside this
# section's math. ATTENDANCE_STATUSES/the attendance schema itself is
# untouched; 'half_day' still means whatever it always meant everywhere
# else in this app.
#
# 'absent' days are deducted in full — ASSUMPTION, flagged here because
# Srikanth has not explicitly ruled on 'absent'; only 'leave'/'weekoff'/
# 'half_day' were addressed when this was designed.
#
# Paid-leave carry-forward, capped at 5, replaces the old "first leave
# day free" rule entirely. All of this month's balance state is stored
# INSIDE that month's own salary_snapshots row (leave_balance_before/
# _accrued/_available/_after) — month N reads month N-1's
# leave_balance_after as ITS leave_balance_before
# (_get_prev_month_snapshot()), never a separate mutable ledger. This
# makes recalculating the SAME month idempotent (INSERT OR REPLACE, safe
# to re-run inside the 10-day correction window without double-accruing
# or double-consuming). A missing prior-month snapshot is treated as a
# balance of 0, not an error — months should be generated in order for
# the balance to reflect reality (documented limitation, not enforced).

def list_salary_slabs():
    """(v2.87) Every active non-admin user LEFT JOINed to salary_slabs,
    so a user with no slab yet still shows up (monthly_salary=None) —
    the admin Payroll > Salary Slabs screen needs to see everyone it
    could set a salary for, not just the ones already configured.
    Ordered by full_name."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT u.user_id, u.full_name, u.email,
                   s.monthly_salary, s.updated_at, s.updated_by
            FROM users u
            LEFT JOIN salary_slabs s ON s.user_id = u.user_id
            WHERE u.active = 1 AND u.role != 'admin'
            ORDER BY u.full_name COLLATE NOCASE
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_salary_slab(user_id, monthly_salary, actor):
    """(v2.87) INSERT OR REPLACE keyed on user_id (the table's PK), same
    idiom as set_fcm_token(). Validates monthly_salary > 0, raises
    ValueError otherwise. Refuses (raises ValueError) if user_id
    resolves to role='admin' — enforced here, not just at the GUI layer,
    since salary data is the most sensitive data class in this database."""
    try:
        monthly_salary = float(monthly_salary)
    except (TypeError, ValueError):
        raise ValueError("Monthly salary must be a number")
    if monthly_salary <= 0:
        raise ValueError("Monthly salary must be greater than 0")

    conn = _connect()
    try:
        user = conn.execute("SELECT role FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            raise ValueError("Unknown user")
        if user["role"] == "admin":
            raise ValueError("Admin accounts are excluded from payroll")
        conn.execute(
            "INSERT OR REPLACE INTO salary_slabs (user_id, monthly_salary, updated_at, updated_by) "
            "VALUES (?, ?, ?, ?)",
            (user_id, monthly_salary, _now(), actor)
        )
        conn.commit()
    finally:
        conn.close()


def _last_day_of_month(year, month):
    """(v2.87, internal) The date of the last calendar day of year/month
    via calendar.monthrange — single source of truth for the 10-day
    freeze window (is_salary_month_locked())."""
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day).date()


def is_salary_month_computable(year, month):
    """(v2.91) A month can only be calculated once it has fully ended —
    payroll is an end-of-month computation, not a live running total.
    Returns False for the current month (even on its last day, until
    that day has fully passed) and for any future month. This is the
    fix for the "future/remaining days counted as absent/leave" bug —
    a month with days that haven't happened yet can never be safely
    computed."""
    return _last_day_of_month(year, month) < datetime.now().date()


def is_salary_month_locked(year, month):
    """(v2.87) True only if BOTH: (a) at least one salary_snapshots row
    exists for this year/month, AND (b) today's date is more than 10
    calendar days after _last_day_of_month(year, month). A month with
    zero snapshots is never locked, no matter how late — this is what
    lets a forgotten month always be generated for the first time."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) c FROM salary_snapshots WHERE year=? AND month=?",
            (year, month)
        ).fetchone()
        has_snapshot = bool(row and row["c"] > 0)
    finally:
        conn.close()
    if not has_snapshot:
        return False
    days_since_month_end = (datetime.now().date() - _last_day_of_month(year, month)).days
    return days_since_month_end > 10


def _get_prev_month_snapshot(user_id, year, month):
    """(v2.87, internal) The salary_snapshots row for this user for the
    calendar month immediately before (year, month), handling year
    rollover (month=1 -> prev is December of year-1), or None if it
    doesn't exist. Used only to read leave_balance_after as this
    month's leave_balance_before."""
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM salary_snapshots WHERE user_id=? AND year=? AND month=?",
            (user_id, prev_year, prev_month)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_holidays_in_month(year, month):
    """(v2.90) List of {date, label} dicts for every attendance_holidays
    row falling in year/month, ordered by date. First real consumer of
    this table — it existed in the schema but nothing read from it
    before Fix 2 (holiday-aware absent detection, compute_salary_for_
    month() below)."""
    conn = _connect()
    try:
        prefix = f"{year:04d}-{month:02d}"
        rows = conn.execute(
            "SELECT holiday_date, label FROM attendance_holidays "
            "WHERE holiday_date LIKE ? ORDER BY holiday_date",
            (f"{prefix}%",)
        ).fetchall()
        return [{"date": r["holiday_date"], "label": r["label"]} for r in rows]
    finally:
        conn.close()


def compute_salary_for_month(year, month, actor):
    """
    (v2.87) Generates or recalculates salary_snapshots for every user in
    salary_slabs, for the given year/month. Refuses (returns
    (False, message)) if is_salary_month_computable(year, month) is
    False (the month hasn't fully ended yet) or if
    is_salary_month_locked(year, month) is True.

    Per-user math (see this section's header comment for the paid-leave
    carry-forward reasoning):
      present_days   = attendance 'present' + 'late' + 'half_day'
                        (half_day folded into present here only)
      (v2.91) "Absent" is no longer a distinct payroll concept — folded
                        into leave_days_taken instead. Both an explicit
                        'absent' status row (legacy/rare, from an old
                        admin correction) and any UNTRACKED gap day (no
                        attendance row at all — this codebase has no
                        automatic "mark absent" job, so such a day was
                        previously invisible to every status bucket) now
                        draw against the SAME leave balance a self-
                        marked leave day does:
                          holiday_days = count of that month's declared
                                         holidays
                          workable_days = calendar_days - holiday_days
                          tracked_days  = present+late+half_day+absent+
                                          leave+weekoff (every day that
                                          DID get an attendance row)
                          untracked_days = max(workable_days -
                                               tracked_days, 0)
                          leave_days_taken = leave + absent + untracked_days
                        salary_snapshots.absent_days is no longer written
                        (column kept, additive-only doctrine — old rows
                        still have real data in it). leave_days_taken's
                        own meaning has therefore changed: it's no longer
                        only self-marked leave, it's every day not
                        otherwise accounted for.
      leave_balance_available = min(prior month's leave_balance_after
                                     (0 if no prior snapshot) + 1, 5)
      paid_leave_days_used    = min(leave_days_taken, available)
      unpaid_leave_days       = max(leave_days_taken - available, 0)
      deducted_days  = unpaid_leave_days (absent_days no longer feeds
                        this — see above)
      per_day_rate   = monthly_salary / calendar_days_in_month (the FULL
                        calendar month — a holiday is a free day, like a
                        weekoff: it doesn't shrink the rate denominator,
                        it just can't be flagged as a day taken)
      net_salary     = max(monthly_salary - deducted_days * per_day_rate, 0)

    Returns (True, "Salary calculated for N employee(s), <Month Year>.")
    on success.
    """
    if not is_salary_month_computable(year, month):
        return (False, "This month hasn't ended yet — payroll can "
                        "only be calculated once it's complete.")
    if is_salary_month_locked(year, month):
        month_label = f"{calendar.month_name[month]} {year}"
        return False, f"{month_label} is locked — more than 10 days have passed since it ended."

    conn = _connect()
    try:
        slabs = conn.execute("SELECT user_id, monthly_salary FROM salary_slabs").fetchall()
        calendar_days = calendar.monthrange(year, month)[1]
        holidays = get_holidays_in_month(year, month)
        holiday_days = len(holidays)
        now = _now()
        count = 0

        for slab in slabs:
            user_id = slab["user_id"]
            monthly_salary = slab["monthly_salary"]

            totals = get_attendance_totals_for_month(year, month, owner_scope=user_id)
            if not totals:
                continue
            c = totals[0]
            present_days = c.get("present", 0) + c.get("late", 0) + c.get("half_day", 0)
            weekoff_days = c.get("weekoff", 0)

            # (v2.91) A day with no attendance row at all is invisible
            # to `c` above — neither present nor absent nor anything
            # else. Any such day, plus any explicit 'absent' status row,
            # now feeds into leave_days_taken instead of a separate
            # "Absent" concept — see this function's docstring.
            tracked_days = (c.get("present", 0) + c.get("late", 0) + c.get("half_day", 0)
                             + c.get("absent", 0) + c.get("leave", 0) + c.get("weekoff", 0))
            workable_days = calendar_days - holiday_days
            untracked_days = max(workable_days - tracked_days, 0)
            leave_days_taken = c.get("leave", 0) + c.get("absent", 0) + untracked_days

            prev = _get_prev_month_snapshot(user_id, year, month)
            leave_balance_before = prev["leave_balance_after"] if prev else 0
            leave_balance_accrued = 1
            leave_balance_available = min(leave_balance_before + leave_balance_accrued, 5)
            paid_leave_days_used = min(leave_days_taken, leave_balance_available)
            unpaid_leave_days = max(leave_days_taken - leave_balance_available, 0)
            leave_balance_after = leave_balance_available - paid_leave_days_used

            deducted_days = unpaid_leave_days
            per_day_rate = monthly_salary / calendar_days
            net_salary = max(monthly_salary - deducted_days * per_day_rate, 0)

            conn.execute("""
                INSERT OR REPLACE INTO salary_snapshots (
                    user_id, year, month, base_salary, calendar_days,
                    present_days, leave_days_taken, weekoff_days,
                    leave_balance_before, leave_balance_accrued, leave_balance_available,
                    paid_leave_days_used, unpaid_leave_days, leave_balance_after,
                    deducted_days, net_salary, calculated_at, calculated_by,
                    holiday_days, untracked_absent_days
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                user_id, year, month, monthly_salary, calendar_days,
                present_days, leave_days_taken, weekoff_days,
                leave_balance_before, leave_balance_accrued, leave_balance_available,
                paid_leave_days_used, unpaid_leave_days, leave_balance_after,
                deducted_days, net_salary, now, actor,
                holiday_days, untracked_days
            ))
            count += 1

        conn.commit()
        month_label = f"{calendar.month_name[month]} {year}"
        return True, f"Salary calculated for {count} employee(s), {month_label}."
    finally:
        conn.close()


def list_salary_snapshots(year, month):
    """(v2.87) All salary_snapshots rows for year/month, JOINed to
    users.full_name, ordered by full_name — powers the admin payroll
    page's results table."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT s.*, u.full_name
            FROM salary_snapshots s
            JOIN users u ON u.user_id = s.user_id
            WHERE s.year = ? AND s.month = ?
            ORDER BY u.full_name COLLATE NOCASE
        """, (year, month)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_salary_month_status(year, month):
    """(v2.87) {'has_snapshot': bool, 'locked': bool, 'computable':
    bool} for the admin page to decide whether to show 'Generate' vs
    'Recalculate' vs a disabled locked state vs (v2.91 NEW) an
    incomplete-month message with no button/table at all."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) c FROM salary_snapshots WHERE year=? AND month=?",
            (year, month)
        ).fetchone()
        has_snapshot = bool(row and row["c"] > 0)
    finally:
        conn.close()
    return {
        "has_snapshot": has_snapshot,
        "locked": is_salary_month_locked(year, month),
        "computable": is_salary_month_computable(year, month),
    }


def get_leave_balance(user_id):
    """(v2.87) Convenience read: this user's leave_balance_after from
    their MOST RECENT salary_snapshots row (highest year, then month),
    or 0 if no snapshot exists yet. For any future screen that wants to
    show "current paid leave balance" without pulling a full snapshot
    row."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT leave_balance_after FROM salary_snapshots WHERE user_id=? "
            "ORDER BY year DESC, month DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        return row["leave_balance_after"] if row else 0
    finally:
        conn.close()


def compute_punch_in_timing(punch_dt):
    """
    (v2.42) Given a punch-in datetime, compares its time-of-day against
    the WORKDAY_START_TIME module constant ('HH:MM') and returns
    (status, late_minutes): status is 'late' with the exact number of
    minutes past the threshold, or 'present' with late_minutes=0.

    (v2.51) Reads the WORKDAY_START_TIME constant directly instead of
    app_settings['attendance_late_after_time'] — one less DB round-trip
    per punch. Still falls back to 10:00 if the constant is somehow
    malformed rather than raising — a punch must never fail because of
    a bad config value.
    """
    raw = WORKDAY_START_TIME or "10:00"
    try:
        threshold_h, threshold_m = (int(p) for p in raw.split(":")[:2])
    except (ValueError, AttributeError):
        threshold_h, threshold_m = 10, 0

    threshold_minutes = threshold_h * 60 + threshold_m
    punch_minutes = punch_dt.hour * 60 + punch_dt.minute
    if punch_minutes > threshold_minutes:
        return "late", punch_minutes - threshold_minutes
    return "present", 0


def compute_early_leave_minutes(punch_dt):
    """(v2.87) Minutes early a punch-out is vs WORKDAY_END_TIME ('17:30'
    default). Returns 0 if at/after threshold. Does NOT write to the
    attendance row or affect status/late_minutes — a real-time
    notification signal only (see notify_admins()'s 'early_punch_out'
    hook in api_attendance_punch_out()), no deduction. Falls back to
    17:30 if the constant is somehow malformed, same posture as
    compute_punch_in_timing()."""
    raw = WORKDAY_END_TIME or "17:30"
    try:
        threshold_h, threshold_m = (int(p) for p in raw.split(":")[:2])
    except (ValueError, AttributeError):
        threshold_h, threshold_m = 17, 30
    threshold_minutes = threshold_h * 60 + threshold_m
    punch_minutes = punch_dt.hour * 60 + punch_dt.minute
    if punch_minutes < threshold_minutes:
        return threshold_minutes - punch_minutes
    return 0


def record_punch(user_id, direction, date_str, ts, lat, lng, geofence_breach, photo_path,
                  status=None, late_minutes=0):
    """
    (v2.42) Records one punch-in or punch-out into the attendance row
    for (user_id, date_str) — UNIQUE(user_id, attendance_date) means a
    same-day re-punch is an UPDATE of the same row, not a duplicate
    (the v2.38 schema's documented intent, now actually wired up).
    direction: 'in' or 'out'. For 'in', status/late_minutes are
    written (from compute_punch_in_timing()); for 'out', only the
    logout_* columns change — status/late_minutes are never touched by
    a logout. A punch-out with no existing row for that date (e.g. a
    missed punch-in) still creates one rather than being rejected, same
    "never discard" posture as the rest of this file — status stays
    NULL, left for a human/correction to resolve later, not silently
    invented.

    Returns the attendance_id of the affected row.
    """
    if direction not in ("in", "out"):
        raise ValueError("direction must be 'in' or 'out'")
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT attendance_id FROM attendance WHERE user_id=? AND attendance_date=?",
            (user_id, date_str)
        ).fetchone()
        now = _now()
        actor = f"api:punch-{direction}"

        if direction == "in":
            if existing is None:
                conn.execute(
                    "INSERT INTO attendance (user_id, attendance_date, status, login_ts, "
                    "login_lat, login_lng, login_geofence_breach, login_photo_path, "
                    "late_minutes, created_at, updated_at, last_modified_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (user_id, date_str, status, ts, lat, lng, int(geofence_breach), photo_path,
                     late_minutes, now, now, actor)
                )
            else:
                conn.execute(
                    "UPDATE attendance SET status=?, login_ts=?, login_lat=?, login_lng=?, "
                    "login_geofence_breach=?, login_photo_path=?, late_minutes=?, updated_at=?, "
                    "last_modified_by=? WHERE attendance_id=?",
                    (status, ts, lat, lng, int(geofence_breach), photo_path, late_minutes, now,
                     actor, existing["attendance_id"])
                )
        else:  # 'out'
            if existing is None:
                conn.execute(
                    "INSERT INTO attendance (user_id, attendance_date, logout_ts, logout_lat, "
                    "logout_lng, logout_geofence_breach, logout_photo_path, created_at, "
                    "updated_at, last_modified_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (user_id, date_str, ts, lat, lng, int(geofence_breach), photo_path,
                     now, now, actor)
                )
            else:
                conn.execute(
                    "UPDATE attendance SET logout_ts=?, logout_lat=?, logout_lng=?, "
                    "logout_geofence_breach=?, logout_photo_path=?, updated_at=?, "
                    "last_modified_by=? WHERE attendance_id=?",
                    (ts, lat, lng, int(geofence_breach), photo_path, now,
                     actor, existing["attendance_id"])
                )
        conn.commit()

        result = conn.execute(
            "SELECT attendance_id FROM attendance WHERE user_id=? AND attendance_date=?",
            (user_id, date_str)
        ).fetchone()
        return result["attendance_id"]
    finally:
        conn.close()


def record_location_ping(user_id, lat, lng, ts):
    """
    (v2.42) Hourly WorkManager location ping (Step 6, not built yet —
    this is the server side only). Accepted ONLY if user_id has an
    OPEN attendance row for today (login_ts set, logout_ts still NULL)
    — silently no-ops otherwise (returns False), per the v0.9 spec:
    "a stray ping after logout or a killed WorkManager job can never
    corrupt data." Returns True if the ping was recorded.
    """
    today = ts[:10] if ts else _now()[:10]
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT attendance_id, login_ts, logout_ts FROM attendance "
            "WHERE user_id=? AND attendance_date=?",
            (user_id, today)
        ).fetchone()
        if not row or not row["login_ts"] or row["logout_ts"]:
            return False
        conn.execute(
            "INSERT INTO attendance_location_pings (user_id, attendance_id, ts, lat, lng, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, row["attendance_id"], ts, lat, lng, _now())
        )
        conn.commit()
        return True
    finally:
        conn.close()


def set_fcm_token(user_id, fcm_token):
    """(v2.42) Store/replace this user's FCM push token. INSERT OR
    REPLACE keyed on user_id (the table's PK), same idiom as
    user_recording_paths. Actually SENDING a push (send_fcm_push(), on
    login/logout) is deferred to the FCM wiring build-order step, which
    needs Srikanth's one-time Firebase project setup first — this
    function only stores the token so that step has something to send
    to once it exists."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO user_fcm_tokens (user_id, fcm_token, updated_at) VALUES (?, ?, ?)",
            (user_id, fcm_token, _now())
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# NOTIFICATIONS v1.0 (v2.72)
# ─────────────────────────────────────────────────────────────
# Unified in-app bell + FCM push, 8 event types (NOTIFICATION_EVENTS
# above). 3 events fire instantly from hooks inside upsert_meta_lead()/
# reassign_lead_owner(); 5 are polled by cls_notifications_poller.py
# via NOTIFICATION_TRIGGERS. All routed through insert_notification()
# so every event type — instant or polled — gets the same idempotency
# guarantee and the same read/unread bookkeeping.

def insert_notification(user_id, cls_id, event_type, message, conn=None):
    """
    Idempotent notification insert — INSERT OR IGNORE keyed on
    event_id = md5(cls_id + event_type + today's date), same dedup
    idiom Job C uses for CAPI event_ids. Re-running the poller (or a
    hook that somehow fires twice for the same lead on the same day)
    never double-notifies — the second insert is silently ignored by
    SQLite's own UNIQUE constraint, no pre-check query needed.

    Optional conn param, same reason/pattern as reassign_lead_owner()'s
    conn= (v2.28): omitted (every instant-hook call site below) opens
    its own connection, commits, closes it. Passed an OPEN connection
    (cls_notifications_poller.py, batching many inserts per run) reuses
    it and does NOT commit or close — the caller owns the transaction.

    Silent no-op (returns False) if user_id is blank — every call site
    below already treats "no user to notify" as nothing-to-do, not an
    error.

    Returns True if a new row was actually inserted, False if it was a
    no-op (blank user_id, or a duplicate event_id).
    """
    if not user_id:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    event_id = hashlib.md5(f"{cls_id}|{event_type}|{today}".encode("utf-8")).hexdigest()
    now = _now()

    owns_conn = conn is None
    if owns_conn:
        conn = _connect()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO notifications "
            "(user_id, cls_id, event_type, message, event_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, cls_id, event_type, message, event_id, now)
        )
        inserted = cur.rowcount == 1
        if owns_conn:
            conn.commit()
        return inserted
    finally:
        if owns_conn:
            conn.close()


def get_unread_notification_count(user_id):
    """Count of this user's unread notifications, for the bell badge."""
    if not user_id:
        return 0
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read_at IS NULL",
            (user_id,)
        ).fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()


def get_notifications(user_id, limit=20):
    """
    This user's most recent notifications, newest first, LEFT JOINed
    to leads for full_name/crm_lead_no display (LEFT, not INNER — a
    notification must never disappear from someone's list just because
    the lead it was about was later deleted). Returns a list of dicts.
    """
    if not user_id:
        return []
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT n.notification_id, n.cls_id, n.event_type, n.message,
                   n.read_at, n.created_at,
                   l.full_name, l.crm_lead_no
            FROM notifications n
            LEFT JOIN leads l ON l.cls_id = n.cls_id
            WHERE n.user_id=?
            ORDER BY n.created_at DESC, n.notification_id DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_notification_read(notification_id):
    """Clears one notification's unread state. Silent no-op if it's
    already read or doesn't exist — best-effort UI nicety, matching
    mark_lead_notification_read()'s posture for the reassignment badge."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE notifications SET read_at=? WHERE notification_id=? AND read_at IS NULL",
            (_now(), notification_id)
        )
        conn.commit()
    finally:
        conn.close()


def mark_all_notifications_read(user_id):
    """Clears every unread notification for this user (the bell's
    'mark all read' action)."""
    if not user_id:
        return
    conn = _connect()
    try:
        conn.execute(
            "UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL",
            (_now(), user_id)
        )
        conn.commit()
    finally:
        conn.close()


def resolve_user_id_from_owner_name(owner_name):
    """
    owner_name (a leads.lead_owner-style display name) -> the user_id
    of the login linked to it via users.owner_match_name (v1.7) — the
    SAME column login/role logic elsewhere in this file already uses
    to go the other direction (owner_match_name -> which leads a
    salesperson may see). Verified against the live schema before this
    was written; no new users column was added for this.

    Case/whitespace-loose match, same convention as owner_match_name's
    other lookups in this file. Returns None if owner_name is blank or
    no ACTIVE user is linked to it (e.g. a placeholder/fallback owner
    name that was never actually given a login) — callers should treat
    None as "no single owner to notify" and fall back to
    _get_admin_user_ids() where that makes sense (see upsert_meta_lead()'s
    new_enquiry hook).
    """
    owner_name = (owner_name or "").strip()
    if not owner_name:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT user_id FROM users WHERE TRIM(owner_match_name)=? COLLATE NOCASE AND active=1 LIMIT 1",
            (owner_name,)
        ).fetchone()
        return row["user_id"] if row else None
    finally:
        conn.close()


def _get_admin_user_ids(conn):
    """
    Internal helper, scoped to Notifications v1.0's new_enquiry fallback
    only: every active admin's user_id, for when
    resolve_user_id_from_owner_name() finds no login linked to a brand-
    new lead's placeholder/fallback owner name. Takes an OPEN connection
    (called from inside upsert_meta_lead()'s existing transaction).
    """
    rows = conn.execute(
        "SELECT user_id FROM users WHERE role='admin' AND active=1"
    ).fetchall()
    return [r["user_id"] for r in rows]


def send_fcm_push(user_id, title, body):
    """
    Best-effort FCM push notification. Looks up user_fcm_tokens
    (table has existed since v2.42; this is the first thing that
    actually calls FCM with it) and requires the
    FCM_SERVICE_ACCOUNT_KEY_PATH env var to point at a real Firebase
    service-account JSON key. Either missing -> logs one guarded line
    and returns False immediately, exactly like every other new-feature
    stub in this codebase before its real credentials exist.

    v2.73 — a 404 / "UNREGISTERED" response (FCM's own signal that this
    token's app was uninstalled/reinstalled) now clears the stale token
    from user_fcm_tokens so it isn't retried forever. See this file's
    v2.73 changelog entry for the full reasoning.

    NEVER raises. Every failure path (no token on file, no/invalid
    creds configured, the 'google-auth'/'requests' packages not
    installed, a network error, FCM itself rejecting the token) is
    caught here and turned into a guarded log line + False — the
    caller (an instant hook inside a lead-write transaction, or the
    15-min poller) must never be blocked or crashed by a push failure.
    Guarded like every other pythonw.exe-safe stdout call in this file
    (pythonw.exe sets sys.stdout=None).

    The actual HTTP v1 send needs the 'google-auth' and 'requests'
    packages for OAuth2 service-account signing — NEITHER is yet in
    this project's installed package list (see CLAUDE.md "Commands").
    They're imported locally inside the try below (not at module level)
    specifically so cls_db.py stays importable by every job/the CRM app
    today, before those packages exist and before
    FCM_SERVICE_ACCOUNT_KEY_PATH is ever set — run
    `python -m pip install google-auth requests` once Srikanth's
    Firebase project setup is done and this is actually going live.
    """
    try:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT fcm_token FROM user_fcm_tokens WHERE user_id=?", (user_id,)
            ).fetchone()
        finally:
            conn.close()
    except Exception as e:
        if sys.stdout is not None:
            print(f"[send_fcm_push] DB lookup failed for user_id={user_id}: {e}")
        return False

    if not row or not row["fcm_token"]:
        if sys.stdout is not None:
            print(f"[send_fcm_push] No FCM token on file for user_id={user_id} — skipped.")
        return False

    key_path = os.environ.get("FCM_SERVICE_ACCOUNT_KEY_PATH", "")
    if not key_path or not os.path.isfile(key_path):
        if sys.stdout is not None:
            print(f"[send_fcm_push] FCM_SERVICE_ACCOUNT_KEY_PATH unset or missing ({key_path!r}) — skipped.")
        return False

    try:
        import json as _json
        import requests as _requests
        from google.oauth2 import service_account as _service_account
        from google.auth.transport.requests import Request as _GARequest

        with open(key_path, "r", encoding="utf-8") as f:
            key_data = _json.load(f)
        project_id = key_data.get("project_id")
        if not project_id:
            if sys.stdout is not None:
                print("[send_fcm_push] Service account key has no project_id — skipped.")
            return False

        credentials = _service_account.Credentials.from_service_account_file(
            key_path, scopes=["https://www.googleapis.com/auth/firebase.messaging"]
        )
        credentials.refresh(_GARequest())

        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        payload = {"message": {"token": row["fcm_token"],
                                "notification": {"title": title, "body": body}}}
        resp = _requests.post(
            url, json=payload,
            headers={"Authorization": f"Bearer {credentials.token}",
                     "Content-Type": "application/json; charset=UTF-8"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True

        # v2.73 — stale-token cleanup. FCM's own signal that this token's
        # app was uninstalled/reinstalled and will never succeed again is
        # either a 404 status or an "UNREGISTERED" errorCode in the response
        # body's error.details[] — check both since the body doesn't always
        # parse as expected. This ONLY ever deletes the token; a premature
        # delete is harmless since the app re-registers on its next launch
        # and set_fcm_token()'s INSERT OR REPLACE just overwrites it.
        is_unregistered = resp.status_code == 404
        try:
            for detail in resp.json().get("error", {}).get("details", []):
                if detail.get("errorCode") == "UNREGISTERED":
                    is_unregistered = True
        except Exception:
            pass

        if is_unregistered:
            try:
                conn2 = _connect()
                try:
                    conn2.execute("DELETE FROM user_fcm_tokens WHERE user_id=?", (user_id,))
                    conn2.commit()
                finally:
                    conn2.close()
                if sys.stdout is not None:
                    print(f"[send_fcm_push] Stale/unregistered token cleared for user_id={user_id}.")
            except Exception as e:
                if sys.stdout is not None:
                    print(f"[send_fcm_push] Failed to clear stale token for user_id={user_id}: {e}")
            return False

        if sys.stdout is not None:
            print(f"[send_fcm_push] FCM rejected push for user_id={user_id}: "
                  f"{resp.status_code} {resp.text[:300]}")
        return False
    except ImportError as e:
        if sys.stdout is not None:
            print(f"[send_fcm_push] Missing package for FCM send ({e}) — "
                  f"run: python -m pip install google-auth requests. Skipped.")
        return False
    except Exception as e:
        if sys.stdout is not None:
            print(f"[send_fcm_push] Unexpected error sending FCM push to user_id={user_id}: {e}")
        return False


def notify_admins(event_type, message, cls_id=None):
    """
    (v2.87) Fan-out an in-app + FCM notification to every active admin —
    for events not about a specific lead (late/early punch alerts).
    Opens its own connection/transaction.

    cls_id: insert_notification()'s idempotency key is
    event_id = md5(cls_id + event_type + today), which is GLOBALLY
    unique across the whole notifications table — NOT scoped per
    recipient or per employee. Passing cls_id=None (or the same literal
    cls_id) for every call of a given event_type on a given day would
    collapse every employee's late/early-punch event that day onto one
    row: only the first one inserted would actually notify anyone.
    Callers of this function MUST therefore pass a per-employee-unique
    cls_id-like key (e.g. f"attn:{employee_user_id}") for attendance
    events, so each employee's daily event stays distinct — see the two
    call sites in api_attendance_punch_in()/api_attendance_punch_out().
    (This still fans out only ONE admin per event_type per employee per
    day if there are multiple admins — same pre-existing limitation as
    the new_enquiry hook's own admin fan-out, not something new here.)
    """
    conn = _connect()
    try:
        for admin_id in _get_admin_user_ids(conn):
            inserted = insert_notification(admin_id, cls_id, event_type, message, conn=conn)
            if inserted:
                send_fcm_push(admin_id, "CLS Attendance Alert", message)
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# SELF-TEST  —  run this file directly to verify everything works
# ─────────────────────────────────────────────────────────────
# Usage:  python cls_db.py
# It creates the DB, runs a tiny end-to-end scenario, prints results,
# then leaves a clean real DB behind (the test rows are isolated).

if __name__ == "__main__":
    # v2.78 — one-off admin invocation for backfill_capi_event_snapshots(),
    # gated behind an explicit flag so plain `python cls_db.py` with no
    # arguments still runs the unconditional self-test below, unchanged.
    # No prior convention for a callable one-off function existed inside
    # this file itself, so this mirrors the --dry-run flag convention
    # already used by other one-off admin scripts in this codebase (e.g.
    # cls_call_recording_audit.py).
    import argparse
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument("--backfill-capi-snapshots", action="store_true",
                          help="Run backfill_capi_event_snapshots() and exit (dry-run unless --live is also passed).")
    _parser.add_argument("--live", action="store_true",
                          help="With --backfill-capi-snapshots: actually write, instead of the default dry-run.")
    _parser.add_argument("--verbose", action="store_true",
                          help="With --backfill-capi-snapshots: print one line per row, not just the summary.")
    _args, _ = _parser.parse_known_args()

    if _args.backfill_capi_snapshots:
        backfill_capi_event_snapshots(dry_run=not _args.live, verbose=_args.verbose)
        sys.exit(0)

    print("=" * 55)
    print(" CLS DATABASE LAYER — SELF TEST (v1.1)")
    print("=" * 55)

    init_db()
    print(f"[OK] Database initialised: {DB_FILE}")

    # ── Normalization checks ──
    print("\n--- Normalization ---")
    tests_phone = [
        ("+91 98765 43210", "9876543210"),
        ("098765 43210",    "9876543210"),
        ("919876543210.0",  "9876543210"),
        ("12345",           ""),
    ]
    for raw, expected in tests_phone:
        got = norm_phone(raw)
        flag = "OK" if got == expected else "FAIL"
        print(f"  [{flag}] norm_phone({raw!r}) = {got!r}")

    tests_email = [
        ("  Srikanth@Gmail.COM ", "srikanth@gmail.com"),
        ("nan",                   ""),
        ("notanemail",            ""),
    ]
    for raw, expected in tests_email:
        got = norm_email(raw)
        flag = "OK" if got == expected else "FAIL"
        print(f"  [{flag}] norm_email({raw!r}) = {got!r}")

    # ── End-to-end scenario ──
    print("\n--- Upsert scenario ---")

    # 1. Meta lead arrives first
    c1, c1_is_new = upsert_meta_lead(
        leadgen_id="TEST_LG_1001", form_id="933648612881057",
        project="Naishka", full_name="Test Buyer",
        phone_raw="+919876500001", email_raw="testbuyer@gmail.com",
        meta_created_time="2026-05-21 10:00:00")
    print(f"  [{'OK' if c1_is_new else 'FAIL'}] Meta lead upserted -> cls_id={c1[:8]}... (is_new={c1_is_new})")

    # 2. Same person shows up in Sell.do at stage Prospect -> should MATCH
    c2, changed = upsert_selldo_lead(
        selldo_lead_id="SD_555", project="Naishka Prism",
        full_name="Test Buyer", phone_raw="9876500001",
        email_raw="testbuyer@gmail.com", current_stage="Prospect")
    match_ok = "OK" if c2 == c1 else "FAIL"
    print(f"  [{match_ok}] Sell.do lead matched same row (changed={changed})")

    # 3. Job C should now see this lead as needing a fire
    unfired = get_unfired_leads()
    pend = [u for u in unfired if u["cls_id"] == c1]
    print(f"  [{'OK' if pend else 'FAIL'}] get_unfired_leads() sees the lead")

    # 4. Fire it, then confirm it disappears from the unfired list
    if pend:
        mark_as_fired(c1, "Prospect")
        still = [u for u in get_unfired_leads() if u["cls_id"] == c1]
        print(f"  [{'OK' if not still else 'FAIL'}] after mark_as_fired, no longer pending")

    # 5. Sell.do-only lead (no Meta match) -> should INSERT, not discard
    c3, _ = upsert_selldo_lead(
        selldo_lead_id="SD_999", project="Grace Classic",
        full_name="Walkin Person", phone_raw="9000000099",
        email_raw="", current_stage="Opportunity")
    isolated = "OK" if c3 != c1 else "FAIL"
    print(f"  [{isolated}] unmatched Sell.do lead inserted as new row")

    # ── Drip enrollment (v1.1) ──
    print("\n--- Drip enrollment ---")

    # 6. Enroll the test lead individually
    ok = enroll_in_drip(c1)
    print(f"  [{'OK' if ok else 'FAIL'}] enroll_in_drip({c1[:8]}) — newly enrolled")

    # 7. Enrolling again should return False (idempotent)
    ok2 = enroll_in_drip(c1)
    print(f"  [{'OK' if not ok2 else 'FAIL'}] enroll_in_drip again -> False (idempotent)")

    # 8. Bulk enroll — c3 has no email so should NOT be enrolled
    count = bulk_enroll_drip()
    print(f"  [OK] bulk_enroll_drip enrolled {count} additional lead(s)")

    # ── Comms log (v1.1) ──
    print("\n--- Comms log ---")

    # 9. Record a sent email
    record_comms(cls_id=c1, project="Naishka", drip_stage="Prospect",
                 day_number=1, template_key="naishka_prospect_d1",
                 sender_email="sales2@asianbuild.in",
                 brevo_message_id="brevo_test_001", status="sent")
    ok = was_email_sent(c1, "Prospect", 1)
    print(f"  [{'OK' if ok else 'FAIL'}] record_comms -> was_email_sent confirms it")

    # 10. Same email not yet sent for Day 4
    ok = not was_email_sent(c1, "Prospect", 4)
    print(f"  [{'OK' if ok else 'FAIL'}] Day 4 not yet sent -> was_email_sent = False")

    # ── Pause / unpause (v1.1) ──
    print("\n--- Drip pause/unpause ---")

    # 11. Pause the drip (simulating Re Assigned)
    pause_drip(c1)
    conn_check = _connect()
    paused = conn_check.execute(
        "SELECT drip_paused FROM leads WHERE cls_id=?", (c1,)
    ).fetchone()["drip_paused"]
    conn_check.close()
    print(f"  [{'OK' if paused == 1 else 'FAIL'}] pause_drip -> drip_paused=1")

    # 12. Unpause the drip (simulating transition to a real stage)
    unpause_drip(c1)
    conn_check = _connect()
    paused = conn_check.execute(
        "SELECT drip_paused FROM leads WHERE cls_id=?", (c1,)
    ).fetchone()["drip_paused"]
    conn_check.close()
    print(f"  [{'OK' if paused == 0 else 'FAIL'}] unpause_drip -> drip_paused=0")

    # ── Opt-out / hard bounce (v1.1) ──
    print("\n--- Hard stops ---")

    # 13. Create a test lead to opt out
    c4, _ = upsert_meta_lead(
        leadgen_id="TEST_LG_OPTOUT", form_id="933648612881057",
        project="Naishka", full_name="Opted Out Person",
        phone_raw="+919876500099", email_raw="optout@test.com",
        meta_created_time="2026-06-01 10:00:00")
    mark_opt_out(c4)
    conn_check = _connect()
    oo = conn_check.execute(
        "SELECT email_opt_out FROM leads WHERE cls_id=?", (c4,)
    ).fetchone()["email_opt_out"]
    conn_check.close()
    print(f"  [{'OK' if oo == 1 else 'FAIL'}] mark_opt_out -> email_opt_out=1")

    # 14. Hard bounce
    mark_hard_bounce(c4)
    conn_check = _connect()
    hb = conn_check.execute(
        "SELECT email_hard_bounce FROM leads WHERE cls_id=?", (c4,)
    ).fetchone()["email_hard_bounce"]
    conn_check.close()
    print(f"  [{'OK' if hb == 1 else 'FAIL'}] mark_hard_bounce -> email_hard_bounce=1")

    # ── Flags ──
    print("\n--- Completion flags ---")
    set_flag("test_job")
    print(f"  [{'OK' if is_flag_fresh('test_job') else 'FAIL'}] flag set and reads as fresh")
    print(f"  [{'OK' if not is_flag_fresh('test_job', 0) else 'FAIL'}] flag reads as stale at 0-min tolerance")

    # ── Drip stats (v1.1) ──
    print("\n--- Drip stats ---")
    ds = drip_stats()
    for k, v in ds.items():
        print(f"  {k:18s}: {v}")

    print("\n--- CLS stats ---")
    for k, v in stats().items():
        print(f"  {k:18s}: {v}")

    print("\n" + "=" * 55)
    print(" SELF TEST COMPLETE (v1.1)")
    print("=" * 55)
    print("\nNOTE: test rows (TEST_LG_1001, SD_555, SD_999, TEST_LG_OPTOUT)")
    print("are now in cls.db. Delete cls.db before going live, or ignore —")
    print("the real jobs will simply add real leads alongside them.")
