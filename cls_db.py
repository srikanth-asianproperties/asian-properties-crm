"""
=============================================================
cls_db.py  —  Centralised Leads System (CLS) | Database Layer
=============================================================
Version : 2.16
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
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

import os
import re
import uuid
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
# All CLS files live in the same folder as the existing automation,
# so paths stay consistent with selldo_capi_automation.py (C:\automation).

BASE_DIR  = r"C:\CLS"
DB_FILE   = os.path.join(BASE_DIR, "cls.db")          # the Centralised Leads System
FLAG_FILE = os.path.join(BASE_DIR, "cls_flags.json")  # completion flags between jobs

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

# Allowed INITIAL stages for a manually-entered lead (v1.9). Never
# "Incoming" — a manual entry is definitionally not a fresh digital
# inquiry; it's a walk-in, a reference, or an offline call, so it
# starts wherever it genuinely is in the funnel already.
MANUAL_ENTRY_STAGES = ["Prospect", "Opportunity", "Site Visited"]

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
# Config-not-code, same pattern as STAGE_TRANSITIONS/DRIP_SCHEDULE above.
# To retune scoring, edit ONLY this dict and LEAD_SCORE_BANDS below —
# compute_lead_scores() reads them at call time, no code changes needed.
# Deliberately excludes a "reengaged" bonus — see the v2.2 changelog
# note for why (the only reengagement signal today is an approximate
# time-elapsed heuristic, not the precise "this person re-submitted"
# signal Srikanth's design notes require before it drives anything).
LEAD_SCORE_RULES = {
    # Points for the lead's CURRENT stage. Unqualified/Lost/Re Assigned
    # deliberately score 0 here — they aren't "worth nothing," they're
    # excluded from the stage component entirely; a Lost lead's score
    # is whatever residual activity points it accumulated, not a
    # negative judgement encoded into the stage table itself.
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
    # Only applied when current_stage == 'Opportunity' (same rule Sell.do
    # itself uses for opportunity_temperature's meaning).
    "temperature_points": {"Warm": 15, "Hot": 30},
    "site_visit_conducted": 25,
    "site_visit_no_show"  : -15,
    "follow_up_completed" : 10,
    # Notes/calls are capped ONCE PER CALENDAR DAY regardless of how many
    # are logged that day — stops someone gaming the score by spamming
    # notes rather than genuinely progressing the lead.
    "note_points_per_day"     : 2,
    "call_tap_points_per_day" : 5,
    # Staleness decay — mirrors get_stale_stage_count()'s spirit, but
    # scoped to scoring rather than a health metric. Exempted stages are
    # ones where sitting unchanged for a while is normal/expected, not
    # a sign of neglect (e.g. Site Visited awaiting a loan approval).
    "decay_after_days"      : 14,
    "decay_points_per_period": -10,
    "decay_exempt_stages"    : ["Site Visited", "Opportunity", "Booked"],
}

# Score bands for display next to the lead's name. Checked in order —
# MUST stay sorted by threshold, descending — first match wins.
LEAD_SCORE_BANDS = [
    (70, "Hot"),
    (30, "Warm"),
    (0,  "Cold"),
]

# ── Project name → display bucket ──
# Sell.do CSV exports store project names with variation (spacing, dashes,
# old sub-project names) and sometimes comma-join MULTIPLE project names
# into one field — executives add nearby projects to a lead's record as
# the lead's interest expands after a site visit. The raw events_log.project
# value is left untouched (it's real CRM history); this map is ONLY used
# to decide which single bucket a lead/event displays/attributes under,
# for dashboards, the phone snapshot, and cost-per-site-visit analysis.
#
# To add a new alias, add ONE line below — no other code changes needed.
PROJECT_BUCKETS = {
    # ── Naishka Homes umbrella (Bandlaguda Jagir cluster — adjacent
    #    projects bucketed together per Srikanth's call, 2026-06-21) ──
    "Naishka"                          : "Naishka Homes",
    "Naishka Prism"                    : "Naishka Homes",
    "Naishka Pavilion"                 : "Naishka Homes",
    "Naishka Prestige"                 : "Naishka Homes",
    "Naishka Pristine"                 : "Naishka Homes",
    "Pavan Classic"                    : "Naishka Homes",
    "Sri Marvel"                       : "Naishka Homes",
    "Madhavi Residency"                : "Naishka Homes",
    "Saanvi Elite Bandlaguda Jagir"    : "Naishka Homes",

    # ── Grace Classic (spacing/dash export variants only) ──
    "Grace Classic"                    : "Grace Classic",
    "Grace Classic - Kokapet"          : "Grace Classic",
    "Grace Classic   Kokapet"          : "Grace Classic",   # double-space, no dash

    # ── Prima Paradiso (already clean, listed for completeness) ──
    "Prima Paradiso"                   : "Prima Paradiso",

    # ── Praga Enclave — separate old project, still active, NOT merged
    #    into Naishka Homes despite being nearby ──
    "Praga Enclave"                    : "Praga Enclave",
}


def get_project_bucket(raw_project):
    """
    Collapse a raw events_log/leads `project` value into its display
    bucket using PROJECT_BUCKETS.

    Handles three real-world shapes seen in Sell.do exports:
      1. A clean single name              -> looked up directly
      2. A known spacing/naming variant   -> looked up directly
      3. A comma-joined multi-project string (executives add projects
         to a lead's CRM record as interest expands after a site visit)
         -> the FIRST project listed is used (it's almost always the
            lead's original enquiry, before others were added)

    Unknown names fall through unchanged (so a brand-new project
    just works without needing a code change — it shows under its
    own raw name until someone adds it to PROJECT_BUCKETS).

    Returns "(unknown)" for None/blank input.
    """
    if not raw_project:
        return "(unknown)"

    first = raw_project.split(",")[0].strip()
    return PROJECT_BUCKETS.get(first, first)


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
    ]
    for col_name, col_type in drip_migrations:
        if col_name not in lead_cols:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type};")

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
    followups_cols = [r["name"] for r in conn.execute("PRAGMA table_info(follow_ups)").fetchall()]
    if "outcome_reason" not in followups_cols:
        conn.execute("ALTER TABLE follow_ups ADD COLUMN outcome_reason TEXT;")

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

    IMPORTANT — this is a VISIBILITY capability, not a write capability.
    A manager can VIEW any lead in full but can only change stage / add
    notes / reassign / schedule visits on leads they personally own. The
    write gate is app.py's _check_lead_ownership() (owner-or-admin), with
    admin as the only write-anywhere role. app.py's lead_detail() combines
    this read predicate with the ownership write-gate to render a manager
    a full-but-read-only view of leads that aren't theirs.
    """
    return role in OVERSIGHT_ROLES


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


def get_leads_page(stage=None, project=None, search=None, owner=None,
                   page=1, per_page=CRM_PAGE_SIZE, date_from=None, date_to=None,
                   sort_by="recent", stage_reason=None, campaign=None,
                   source=None, sub_source=None, budget=None,
                   configuration=None, property_type=None, facing=None,
                   search_all_owners=False):
    """
    Paginated, filterable lead list for the CRM's /leads screen.

    stage       : exact current_stage match (e.g. "Prospect"), or None for all
    project     : matches the BUCKETED project (get_project_bucket), or None for all
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
             "total_pages": int}.

    Note: project filtering happens in Python after fetching, because
    the bucket name is DERIVED (get_project_bucket), not a stored column.
    At CLS's current scale (~3k leads) this is simple and fast; if the
    table grows an order of magnitude, this is the first place to revisit.
    """
    conn = _connect()
    try:
        where = ["1=1"]
        params = []

        if stage:
            where.append("current_stage = ?")
            params.append(stage)

        # v2.7 — an active search with search_all_owners drops the owner
        # scope for THIS query, so a salesperson can find (but only
        # view, restricted) a lead that isn't theirs. A blank search
        # keeps the owner scope even with the flag on.
        has_active_search = bool(search and search.strip())
        apply_owner_scope = owner and not (search_all_owners and has_active_search)

        if apply_owner_scope:
            where.append("LOWER(lead_owner) = LOWER(?)")
            params.append(owner)

        if has_active_search:
            search_term = search.strip().lower()
            # v2.16 — accept "APX-183" or just "183" for lead ID search.
            # The prefix is a UI convention only; crm_lead_no is stored as
            # a bare INTEGER, so strip the prefix before matching.
            if search_term.startswith("apx-"):
                search_term = search_term[4:].strip()
            like = f"%{search_term}%"
            where.append(
                "(LOWER(full_name) LIKE ? OR phone_norm LIKE ? "
                "OR email_norm LIKE ? OR CAST(crm_lead_no AS TEXT) LIKE ?)"
            )
            params.extend([like, like, like, like])

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

        if source:
            where.append("source = ?")
            params.append(source)

        if sub_source:
            where.append("lead_source_detail = ?")
            params.append(sub_source)

        if budget:
            where.append("budget = ?")
            params.append(budget)

        for col_name, selected in (
            ("configuration", configuration),
            ("property_type", property_type),
            ("facing", facing),
        ):
            if selected:
                ors = " OR ".join(f"{col_name} LIKE ?" for _ in selected)
                where.append(f"({ors})")
                params.extend(f"%{val}%" for val in selected)

        where_sql = " AND ".join(where)
        order_sql = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["recent"])

        all_rows = conn.execute(f"""
            SELECT cls_id, full_name, phone_raw, phone_norm, email_raw,
                   project, current_stage, lead_owner, source,
                   stage_updated_at, cls_updated_at, cls_created_at, crm_lead_no
            FROM leads
            WHERE {where_sql}
            ORDER BY {order_sql}
        """, params).fetchall()

        rows = [dict(r) for r in all_rows]
        for r in rows:
            r["project_bucket"] = get_project_bucket(r["project"])

        if project:
            rows = [r for r in rows if r["project_bucket"] == project]

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


def get_lead_by_id(cls_id):
    """Full lead row for the /leads/<cls_id> detail screen, or None."""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return None
        lead = dict(row)
        lead["project_bucket"] = get_project_bucket(lead["project"])
        return lead
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


def get_new_enquiries_count(days=7):
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
    no human action has EVER been taken on it. Integration ingestion
    (Job A/B upserts) writes no activity_log rows, so "zero activity_
    log rows" reliably means "untouched since it arrived." The moment
    ANY activity is logged against it (log_call_tap's 'call_attempted'
    is the most common first touch, but a note/stage-change/site-visit
    would too), it drops off this count — even though it may still be
    sitting at current_stage='Incoming' (nobody has moved the stage
    yet, just looked at it). `days` is kept as an unused parameter so
    existing call sites don't need updating.
    """
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT COUNT(*) c FROM leads l
            WHERE l.current_stage='Incoming'
              AND NOT EXISTS (SELECT 1 FROM activity_log a WHERE a.cls_id = l.cls_id)
        """).fetchone()
        return row["c"]
    finally:
        conn.close()


def get_new_enquiries_leads():
    """
    (v2.11) List-returning counterpart to get_new_enquiries_count()
    above — SAME criteria (current_stage='Incoming' AND zero activity_
    log rows), just returning rows instead of a count, so the dashboard
    card can link through to an actual filtered list. Mirrors
    get_reengaged_leads()'s shape.
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT * FROM leads l
            WHERE l.current_stage='Incoming'
              AND NOT EXISTS (SELECT 1 FROM activity_log a WHERE a.cls_id = l.cls_id)
            ORDER BY l.cls_created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_reengaged_count(days=7):
    """
    APPROXIMATE reengagement signal — labelled as such in the UI on
    purpose. Counts leads that already existed BEFORE the window
    (cls_created_at older than `days`) but were touched INSIDE the
    window (cls_updated_at within `days`).

    The caveat (deliberately not hidden): this can't yet distinguish
    "a genuine new inbound inquiry from a returning customer" from "a
    routine stage re-sync on an old lead" — both bump cls_updated_at
    identically. A precise version means adding a marker at the exact
    moment find_match() succeeds inside upsert_meta_lead/
    upsert_selldo_lead, which is a production write-path change —
    deliberately deferred rather than rushed into a read-only polish
    pass. Until then, treat this number as directional, not exact.
    """
    conn = _connect()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        row = conn.execute("""
            SELECT COUNT(*) c FROM leads
            WHERE cls_created_at < ? AND cls_updated_at >= ?
        """, (cutoff, cutoff)).fetchone()
        return row["c"]
    finally:
        conn.close()


def get_reengaged_leads(days=7, owner=None, date_from=None, date_to=None):
    """
    List-returning counterpart to get_reengaged_count() above — SAME
    approximate criteria (see that function's docstring for the full
    caveat), just returning rows instead of a count, so the dashboard
    card can link through to an actual filtered list.

    owner (v2.12): optional, default None (existing behavior,
    unchanged — reengaged_list() keeps calling this with no owner
    arg). Pass a lead_owner to scope to one salesperson's own leads,
    for Report #9's owner-filtered view.

    date_from/date_to (v2.13): optional 'YYYY-MM-DD' strings, default
    None (existing behavior unchanged — `days` trailing window from
    right now). When both given, the cutoff becomes date_from's start
    of day (leads created before the selected period, reengaged AT OR
    AFTER it starts) and matches are additionally capped at date_to's
    end of day — "which existing leads came back DURING this period,"
    not "...since N days ago."
    """
    conn = _connect()
    try:
        if date_from and date_to:
            cutoff = f"{date_from} 00:00:00"
            upper = f"{date_to} 23:59:59"
            query = """
                SELECT * FROM leads
                WHERE cls_created_at < ? AND cls_updated_at >= ? AND cls_updated_at <= ?
            """
            params = [cutoff, cutoff, upper]
        else:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            query = """
                SELECT * FROM leads
                WHERE cls_created_at < ? AND cls_updated_at >= ?
            """
            params = [cutoff, cutoff]
        if owner:
            query += " AND lead_owner = ?"
            params.append(owner)
        query += " ORDER BY cls_updated_at DESC"
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
    """
    METRIC_MAP = {
        "call_attempted":        "calls_attempted",
        "site_visit_scheduled":  "site_visits_created",
        "site_visit_conducted":  "site_visits_conducted",
        "follow_up_scheduled":   "follow_ups_created",
        "follow_up_completed":   "follow_ups_completed",
        "note":                  "notes_added",
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
                  new_value=None, description=None):
    """
    Internal helper — appends one row to activity_log. Takes an OPEN
    connection (not a fresh one) so callers can log the activity in
    the SAME transaction as the actual write, keeping them atomic:
    either both the write and its audit row land, or neither does.
    """
    conn.execute("""
        INSERT INTO activity_log (
            cls_id, activity_type, actor, prev_value, new_value,
            description, created_at
        ) VALUES (?,?,?,?,?,?,?)
    """, (cls_id, activity_type, actor, prev_value, new_value,
          description, _now()))


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

        conn.commit()
        return True, f"Stage changed: {live_stage} → {new_stage}.{cancelled_note}"
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


def reassign_lead_owner(cls_id, new_owner, actor):
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

    Returns (ok: bool, message: str).
    """
    new_owner = (new_owner or "").strip()
    if not new_owner:
        return False, "Owner name can't be empty."

    conn = _connect()
    try:
        row = conn.execute("SELECT lead_owner FROM leads WHERE cls_id=?", (cls_id,)).fetchone()
        if not row:
            return False, "Lead not found."

        prev_owner = row["lead_owner"]
        now = _now()
        conn.execute(
            "UPDATE leads SET lead_owner=?, cls_updated_at=?, owner_notified=0 WHERE cls_id=?",
            (new_owner, now, cls_id)
        )
        _log_activity(conn, cls_id, "assignment_change", actor,
                      prev_value=prev_owner, new_value=new_owner)
        conn.commit()
        return True, f"Reassigned: {prev_owner or '(unassigned)'} → {new_owner}."
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

    initial_stage MUST be one of MANUAL_ENTRY_STAGES (Prospect /
    Opportunity / Site Visited) — never "Incoming", since a manually-
    entered lead is definitionally not a fresh digital inquiry; it's
    already somewhere further along in the funnel by the time someone
    is typing it in by hand.

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
        crm_lead_no = _next_crm_lead_no(conn)
        conn.execute("""
            INSERT INTO leads (
                cls_id, project, full_name, phone_raw, phone_norm,
                email_raw, email_norm, current_stage, stage_updated_at,
                match_tier, source, lead_owner, crm_lead_no,
                lead_source_detail, cls_created_at, cls_updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cls_id, project, full_name, phone_raw, phone_norm,
              email_raw, email_norm, initial_stage, now,
              "manual", "manual_crm", lead_owner, crm_lead_no,
              source_detail or None, now, now))
        _log_activity(conn, cls_id, "lead_created_manual", actor,
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
    leads.project), scheduled_at, notes, reminder_sent_at (the most
    recent whatsapp_reminder_sent activity_log entry for this visit,
    else None). Sorted by scheduled_at ascending.
    """
    conn = _connect()
    try:
        query = """
            SELECT v.visit_id, v.cls_id, l.full_name, l.phone_raw, l.phone_norm,
                   l.project, v.scheduled_at, v.notes,
                   (SELECT MAX(a.created_at) FROM activity_log a
                    WHERE a.activity_type = 'whatsapp_reminder_sent'
                      AND a.description LIKE 'visit_id:' || v.visit_id || '%') AS reminder_sent_at
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
    description is EXACTLY f"visit_id:{visit_id}" —
    get_site_visits_for_tomorrow()'s LIKE lookup depends on this format.
    """
    conn = _connect()
    try:
        _log_activity(conn, cls_id, "whatsapp_reminder_sent", actor,
                      description=f"visit_id:{visit_id}")
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


def get_due_today():
    """
    Site visits and follow-ups due today or overdue, across ALL leads —
    feeds the dashboard's "Due Today" card. This is the agreed
    substitute for exact-time push notifications (a separate iOS
    16.4+ PWA push project) — gets most of the value at a fraction
    of the effort.

    "Missed" is computed here, live, never stored: a row counts as
    missed if scheduled_at has passed and status is still 'scheduled'.
    Cancelled/completed items are excluded entirely.

    Returns a list of dicts: {kind, id, cls_id, full_name, scheduled_at,
    missed, notes}, sorted by scheduled_at ascending (most overdue /
    soonest first).
    """
    conn = _connect()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        results = []

        visits = conn.execute("""
            SELECT v.visit_id, v.cls_id, v.scheduled_at, v.notes, l.full_name, l.crm_lead_no
            FROM site_visits v JOIN leads l ON l.cls_id = v.cls_id
            WHERE v.status = 'scheduled' AND DATE(v.scheduled_at) <= DATE(?)
        """, (today,)).fetchall()
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

        follow_ups = conn.execute("""
            SELECT f.followup_id, f.cls_id, f.scheduled_at, f.notes, l.full_name, l.crm_lead_no
            FROM follow_ups f JOIN leads l ON l.cls_id = f.cls_id
            WHERE f.status = 'scheduled' AND DATE(f.scheduled_at) <= DATE(?)
        """, (today,)).fetchall()
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


def get_due_by_kind(kind):
    """
    Same due/overdue logic as get_due_today() above, filtered to just
    one kind (v1.9) — feeds the two split dashboard cards (Follow-ups
    Due, Site Visits Due) instead of one combined list. kind must be
    'site_visit' or 'follow_up'.
    """
    return [item for item in get_due_today() if item["kind"] == kind]


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
    """
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT user_id, full_name, email, role, active, created_at, last_login_at
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
    LEAD_SCORE_RULES/LEAD_SCORE_BANDS above — edit those, not this
    function, to retune.
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

        rules = LEAD_SCORE_RULES
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
            band = "Cold"
            for threshold, label in LEAD_SCORE_BANDS:
                if score >= threshold:
                    band = label
                    break

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

def upsert_meta_lead(leadgen_id, form_id, project, full_name,
                     phone_raw, email_raw, meta_created_time):
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
                    form_id=?, project=?, full_name=?,
                    phone_raw=?, phone_norm=?, email_raw=?, email_norm=?,
                    meta_created_time=?, cls_updated_at=?
                WHERE cls_id=?
            """, (form_id, project, full_name,
                  phone_raw, phone_norm, email_raw, email_norm,
                  meta_created_time, now, cls_id))
            conn.commit()
            return cls_id

        # ── 2. No leadgen_id row — does a contact match exist? (enrich it) ──
        cls_id, tier = find_match(conn, phone_norm, email_norm)
        if cls_id:
            # An existing row (likely selldo_only) is the same person.
            # Stamp the leadgen_id onto it — this is the back-fill case.
            conn.execute("""
                UPDATE leads SET
                    leadgen_id=?, form_id=?, project=COALESCE(project,?),
                    full_name=COALESCE(NULLIF(full_name,''),?),
                    meta_created_time=?, cls_updated_at=?
                WHERE cls_id=?
            """, (leadgen_id, form_id, project, full_name,
                  meta_created_time, now, cls_id))
            conn.commit()
            return cls_id

        # ── 3. Genuinely new lead — insert. ──
        cls_id = str(uuid.uuid4())
        crm_lead_no = _next_crm_lead_no(conn)
        conn.execute("""
            INSERT INTO leads (
                cls_id, leadgen_id, form_id, project, full_name,
                phone_raw, phone_norm, email_raw, email_norm,
                meta_created_time, source, crm_lead_no,
                cls_created_at, cls_updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cls_id, leadgen_id, form_id, project, full_name,
              phone_raw, phone_norm, email_raw, email_norm,
              meta_created_time, "meta", crm_lead_no, now, now))
        conn.commit()
        return cls_id
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
        existing = conn.execute(
            "SELECT cls_id, current_stage FROM leads WHERE selldo_lead_id=? LIMIT 1",
            (selldo_lead_id,)
        ).fetchone()
        match_tier = "selldo_id"

        if not existing:
            # Fall back to phone/email matching against Meta-sourced rows.
            cls_id, match_tier = find_match(conn, phone_norm, email_norm)
            if cls_id:
                existing = conn.execute(
                    "SELECT cls_id, current_stage FROM leads WHERE cls_id=?",
                    (cls_id,)
                ).fetchone()

        # ── Existing row -> update CRM stage ──
        if existing:
            cls_id        = existing["cls_id"]
            prev_stage    = existing["current_stage"]
            stage_changed = (prev_stage != current_stage)
            conn.execute("""
                UPDATE leads SET
                    selldo_lead_id=?, current_stage=?, match_tier=?,
                    project=COALESCE(project,?),
                    full_name=COALESCE(NULLIF(full_name,''),?),
                    phone_raw=COALESCE(NULLIF(phone_raw,''),?),
                    phone_norm=COALESCE(NULLIF(phone_norm,''),?),
                    email_raw=COALESCE(NULLIF(email_raw,''),?),
                    email_norm=COALESCE(NULLIF(email_norm,''),?),
                    stage_updated_at=CASE WHEN ? THEN ? ELSE stage_updated_at END,
                    lead_owner=COALESCE(NULLIF(?,  ''), lead_owner),
                    selldo_url=COALESCE(NULLIF(?,  ''), selldo_url),
                    opportunity_temperature=?,
                    cls_updated_at=?
                WHERE cls_id=?
            """, (selldo_lead_id, current_stage, match_tier,
                  project, full_name,
                  phone_raw, phone_norm, email_raw, email_norm,
                  stage_changed, now,
                  lead_owner, selldo_url,
                  opportunity_temperature or None,
                  now, cls_id))
            conn.commit()
            return cls_id, stage_changed

        # ── No match anywhere -> INSERT selldo_only row (Risk 3) ──
        cls_id = str(uuid.uuid4())
        crm_lead_no = _next_crm_lead_no(conn)
        conn.execute("""
            INSERT INTO leads (
                cls_id, leadgen_id, project, full_name,
                phone_raw, phone_norm, email_raw, email_norm,
                selldo_lead_id, current_stage, stage_updated_at,
                match_tier, source, lead_owner, selldo_url,
                opportunity_temperature, crm_lead_no,
                cls_created_at, cls_updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cls_id, None, project, full_name,
              phone_raw, phone_norm, email_raw, email_norm,
              selldo_lead_id, current_stage, now,
              "unmatched", "selldo_only", lead_owner, selldo_url,
              opportunity_temperature or None, crm_lead_no,
              now, now))
        conn.commit()
        return cls_id, True   # brand-new row counts as a change
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


def record_event(cls_id, leadgen_id, full_name, phone_norm, project,
                 crm_stage, meta_event, value_inr, used_leadgen, dataset_id,
                 prev_stage=None, lead_owner=None):
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
    """
    now = _now()
    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO events_log (
                fired_at, cls_id, leadgen_id, full_name, phone_norm,
                project, crm_stage, prev_stage, meta_event, value_inr,
                used_leadgen, dataset_id, lead_owner
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (now, cls_id, leadgen_id, full_name, phone_norm,
              project, crm_stage, prev_stage, meta_event, value_inr,
              1 if used_leadgen else 0, dataset_id, lead_owner))
        conn.commit()
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
    (bucketed through the existing get_project_bucket() so Sell.do's
    spacing/dash variants and comma-joined multi-project strings
    collapse into one row per real project, same as every other
    project-facing view in this file) x current_stage, optionally
    scoped to one salesperson's owned leads.

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
        query = "SELECT project, current_stage FROM leads"
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
        bucket = get_project_bucket(r["project"])
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
    "project": "project",
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

    "project" grouping runs raw project values through the existing
    get_project_bucket() collapse; "campaign" grouping runs raw
    campaign values through _campaign_bucket() (blank/NULL ->
    "Unknown/Manual" — see this module's v2.13 HONESTY NOTE on why
    that bucket currently holds almost everything).

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
            key = get_project_bucket(raw)
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
        return {
            "total_leads"      : total,
            "with_leadgen_id"  : with_lg,
            "selldo_only"      : selldo_only,
            "pending_fire"     : unfired,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# SELF-TEST  —  run this file directly to verify everything works
# ─────────────────────────────────────────────────────────────
# Usage:  python cls_db.py
# It creates the DB, runs a tiny end-to-end scenario, prints results,
# then leaves a clean real DB behind (the test rows are isolated).

if __name__ == "__main__":
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
    c1 = upsert_meta_lead(
        leadgen_id="TEST_LG_1001", form_id="933648612881057",
        project="Naishka", full_name="Test Buyer",
        phone_raw="+919876500001", email_raw="testbuyer@gmail.com",
        meta_created_time="2026-05-21 10:00:00")
    print(f"  [OK] Meta lead upserted -> cls_id={c1[:8]}...")

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
    c4 = upsert_meta_lead(
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
