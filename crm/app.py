"""
=============================================================
app.py — Asian Properties CRM (APX) | v0.1 Viewer
=============================================================
Version : 0.12.1
Author  : Built for Asian Properties / Srikanth

WHAT THIS IS
------------
v0.1 was a READ-ONLY lead viewer. v0.2 (this version) is the v0.5
"Writer" roadmap phase: stage changes, notes, assignment, site-visit
and follow-up scheduling — the CRM's first WRITE path into cls.db's
leads table (current_stage, lead_owner) beyond the login-only `users`
table.

THIS IS A PARALLEL-RUN VERSION, NOT A CUTOVER. Sell.do keeps running
exactly as before, and your team updates BOTH systems during this
phase — that's the whole point of parallel-run (per your own
non-negotiable rule: never cut over until the team has lived in the
new system for 3-4 weeks). A forgotten Sell.do update simply reverts
on Job B's next sync (<=2hrs) — an intentional, code-free enforcement
signal for double-entry discipline, not a bug. See cls_db.py v1.8's
changelog for the full reasoning.

Stage changes follow the SAME one-way transition rules as Sell.do's
own rule-based engine (STAGE_TRANSITIONS in cls_db.py) — free-form
stage changes are not possible from this app.

FOLDER LAYOUT (this file lives in C:\\CLS\\crm\\)
------------------------------------------------
  C:\\CLS\\cls_db.py          <- shared with Jobs A-D, imported via sys.path
  C:\\CLS\\cls.db             <- the single source of truth
  C:\\CLS\\.env               <- same .env the automation jobs use
  C:\\CLS\\crm_app_log.txt    <- NEW (v0.1.5) — production run log, same
                                 folder as the other CLS *_log.txt files
  C:\\CLS\\crm\\app.py         <- this file
  C:\\CLS\\crm\\templates\\     <- Jinja2 templates
  C:\\CLS\\crm\\static\\        <- manifest.json, sw.js, icons

FIRST-TIME SETUP
-----------------
  1. Add CRM_SECRET_KEY to C:\\CLS\\.env:
       python -c "import secrets; print(secrets.token_hex(32))"
     then add the printed value as:
       CRM_SECRET_KEY=<paste it here>
  2. pip install -r requirements.txt
  3. python create_admin.py     <- creates YOUR login (users table starts empty)
  4. python app.py              <- open http://127.0.0.1:5000

GOING LIVE VIA CLOUDFLARE TUNNEL  (v0.1.5 — now via Waitress)
--------------------------------------------------------------
  Add to C:\\CLS\\.env:  CRM_ENV=production
  Two things change when CRM_ENV=production:
    1. The session cookie flips to Secure (HTTPS-only) — correct once
       the public URL is https:// via the Tunnel.
    2. app.py stops using Flask's own dev server (which explicitly
       warns it isn't meant for this) and instead serves via Waitress,
       a production-grade pure-Python WSGI server, wrapped in a
       self-healing loop — see run_production() below and the
       DEPLOYMENT section at the bottom of this docstring.
  Do NOT set CRM_HOST=0.0.0.0 in production. Cloudflare Tunnel's
  cloudflared process connects to this app over localhost — the app
  never needs to be reachable on the LAN itself. Leave CRM_HOST unset
  (defaults to 127.0.0.1) once you're done with phone/LAN testing.

TESTING ON YOUR PHONE (same WiFi, before the Tunnel exists)
--------------------------------------------------------------
  1. Find your laptop's local IP:  ipconfig  ->  IPv4 Address (e.g. 192.168.1.42)
  2. Add to C:\\CLS\\.env:  CRM_HOST=0.0.0.0
  3. Restart: Ctrl+C, then  python app.py
     (Windows Firewall will prompt the first time — allow it for
     PRIVATE networks only, not Public.)
  4. On your phone, same WiFi, open  http://192.168.1.42:5000
     (use your own IP from step 1, not this example)
  5. When done testing, remove CRM_HOST from .env (or set it back to
     127.0.0.1) — 0.0.0.0 means anyone on that WiFi can reach the
     login page for as long as app.py is running with it set.

DEPLOYMENT — run APX as an unattended service (v0.1.5)
--------------------------------------------------------------
  Same pattern as cls_telegram_listener.py: launch at Windows startup,
  loop forever internally, restart on failure.

  1. Confirm your Python path:  where python
  2. In an Admin Command Prompt, run (adjust the python.exe path to
     what step 1 printed):

       schtasks /Create /TN "APX CRM Server" ^
         /TR "\\"C:\\Users\\Srikanth\\AppData\\Local\\Programs\\Python\\Python314\\python.exe\\" C:\\CLS\\crm\\app.py" ^
         /SC ONSTART /DELAY 0001:00 /RL HIGHEST /F

  3. In Task Scheduler (GUI) -> find "APX CRM Server" -> Properties ->
     Settings tab -> check "If the task fails, restart every: 1 minute"
     and "Attempt to restart up to: 3 times". (schtasks.exe's /Create
     switches don't expose this option — it's a GUI/XML-only setting,
     which is why this step is manual, same as it was for the listener.)
  4. Right-click the task -> Run, to test it once without rebooting.
     Confirm crm.asianbuild.in loads, then check
     C:\\CLS\\crm_app_log.txt for the "APX CRM starting" line.
  5. Reboot the laptop once, fully, to confirm the ONSTART trigger
     actually brings the CRM back up on its own — don't just trust
     the manual "Run" test above for that part.

  Why both Task Scheduler's restart AND an internal retry loop:
  Task Scheduler's restart-on-failure only helps if the *process*
  dies (crashes, is killed, or the machine reboots). It does nothing
  if the process is alive but waitress.serve() itself throws an
  exception internally without the process exiting — that's what the
  while-loop in run_production() below catches and logs, matching the
  "never fail silently" rule your other CLS scripts already follow.

CHANGELOG
---------
v0.12.1 (July 2026) — User Activity Log, 2 fixes from first real-world
  testing behind the Cloudflare Tunnel. app.py-only, no schema change.

  FIX 1 — login()'s call to cls_db.start_user_session() was capturing
  request.remote_addr, which is always 127.0.0.1 in production since
  traffic arrives via cloudflared (Cloudflare Tunnel) rather than a
  direct connection. Now reads request.headers.get('CF-Connecting-IP',
  request.remote_addr) instead — Cloudflare's own header carrying the
  real visitor IP, falling back to remote_addr for local/dev testing
  where that header is absent.

  FIX 2 — _log_user_action() before_request hook's skip list now also
  excludes the 'service_worker' endpoint (the @app.route("/sw.js")
  route, confirmed at its def service_worker() — served from the root
  path rather than under /static/, which is why the existing 'static'
  skip didn't already cover it). The browser fetches sw.js on its own
  in the background; it was showing up as a fake "action" after every
  real page view.

v0.12 (July 2026) — admin "User Activity Log" (Settings > User Activity).
  Requires cls_db.py v2.21. NEW settings_user_activity.html, settings.html
  gained one tile. ADDITIONS ONLY — no existing route, function signature,
  or call site changed.

  NEW ENDPOINT_LABELS config dict + NEW @app.before_request hook
  (_log_user_action) — logs every logged-in request via cls_db.
  log_user_action(), against the current login's session_row_id. Skips
  static/login/logout endpoints and any request with no logged-in
  user_id; wrapped in try/except so a logging failure can never break a
  real request (same "never fail silently, but never let logging kill
  a request either" posture as cls_snapshot.py's swallowed errors).

  MODIFIED login() — on successful verify_login(), now also calls
  cls_db.start_user_session() and stashes the returned id as
  session["session_row_id"] (set fresh AFTER session.clear(), same as
  session["user_id"] already was — ordering unchanged, just one more
  key set at the same point).

  MODIFIED logout() — now calls cls_db.end_user_session() (guarded by
  session.get("session_row_id") existing) BEFORE session.clear() wipes
  it.

  NEW GET /settings/user-activity (settings_user_activity) — admin-only,
  optional user_id/date_from/date_to query params, calls cls_db.
  get_user_timeline() + cls_db.get_all_users_detailed() (existing
  function, reused for the filter dropdown).

v0.11.1 (July 2026) — APX bug-fix + scoped-enhancement batch (items 2 and
  4 of Srikanth's 4-item batch; item 1 is cls_db.py-only, item 3 Option A
  is leads_list.html-only — see those files' own changelogs). Requires
  cls_db.py v2.19.

  ITEM 2 — _is_lead_owner_or_admin() now also returns True when
  cls_db.can_write_any_lead(user["role"]) is True, alongside the existing
  owner-or-admin check. REVERSES v0.9.5's deliberate manager write
  restriction: a manager can now write to ANY lead (stage, notes, assign,
  site visit/follow-up, property/contact edits, call tap), not just their
  own — flagged to Srikanth as security-relevant, proceeding on his
  explicit call. Every write route already funnels through
  _check_lead_ownership -> _is_lead_owner_or_admin, so this ONE function
  change covers all of them; no route-level changes needed.
  lead_detail()'s can_write/restricted split (v0.9.5) confirmed to fall
  out of this naturally — a manager now gets can_write=True on every
  lead without a separate patch (its explanatory comment updated to say
  so). Settings, the Team page, lead deletion, and source-editing are
  UNCHANGED — still admin_required / role=="admin" only, not touched by
  this constant. activity_log continues to record the ACTUAL acting
  user, never the lead's owner — unaffected, confirmed still true.

  ITEM 4 — NEW date-range quick-select dropdown on /leads/filter.
  NEW DATE_PRESETS (+ _dr_* helpers, DATE_PRESET_ORDER, DATE_PRESET_
  LABELS, _detect_active_date_preset()) near _parse_lead_filters() —
  mirrors cls_reports.py's QUICK_RANGES/resolve_date_range() naming and
  structure and the SAME Monday-Sunday week-start convention, but is its
  own dict here (not imported from cls_reports.py) since the Leads
  filter needs 11 presets vs Reports' 4 and the two screens are
  otherwise unrelated — touches fewer files than extending cls_reports.py
  for a screen it doesn't otherwise serve. cls_db.py needed ZERO changes
  for this item — it already just takes date_from/date_to strings.
  _parse_lead_filters() now resolves an incoming date_preset param into
  concrete dates BEFORE calling cls_db.get_leads_page(), and back-fills
  filters["date_preset"] (by detection) even for old bookmarked URLs
  that only carry raw date_from/date_to — full backward compatibility,
  date_preset is additive, not a replacement. leads_filter_screen() now
  passes date_preset_order/date_preset_labels to the template.

v0.11  (July 2026) — APX v0.11 Admin "View as" (impersonation), with
  dual-attribution on every write. Requires cls_db.py v2.15.
  settings_users.html extended, base.html extended (impersonation
  banner — its second v0.10/v0.11 edit).

  NEW _actor() helper — the ONE place that decides what string a
  write's `actor` argument is: the current user's email normally, or
  "target@x (via admin@x)" during a View-as session. EVERY existing
  write route's actor=user["email"] call site was swapped to
  actor=_actor() — a grep-and-replace across the whole file, not a
  signature change to any cls_db.py writer. This is the entire
  mechanism: existing write paths inherit dual-attribution with zero
  additional code at each call site.

  NEW POST /admin/impersonate/<user_id> (impersonate_start) — admin-
  only. Session swap: session["impersonator_id"] = the admin's own
  user_id, then session["user_id"] = the target's. Rejects self,
  another admin, or an unknown/deactivated target (cls_db.
  get_user_by_id() already excludes deactivated accounts, so that
  case surfaces as "not found" rather than a separate check). Logs a
  'start' row via cls_db.log_impersonation().

  NEW POST /admin/impersonate/exit (impersonate_exit) — login_required
  ONLY (not admin_required — mid-impersonation, session["user_id"] IS
  the target, who may not be an admin). Swaps the session keys back,
  logs an 'exit' row, redirects to dashboard.

  MODIFIED login_required() — NEW safety check: if
  session["impersonator_id"] is set but that admin's own account no
  longer resolves via get_user_by_id() (deactivated by another admin
  mid-session), the whole session is cleared rather than leaving a
  stuck "viewing as" state with no way back to a valid admin login.

  MODIFIED inject_current_user() — NEW `impersonator` key: the real
  admin's user dict when mid-impersonation, else None. base.html uses
  this (not current_user, which is the TARGET during impersonation) to
  decide whether to render the banner.

v0.10  (July 2026) — APX v0.10 Tomorrow's Site-Visit WhatsApp Reminders.
  Requires cls_db.py v2.14. NEW templates/reminders_tomorrow.html, NEW
  templates/settings_whatsapp_reminders.html, settings.html/base.html/
  dashboard.html all extended.

  NEW /reminders/site-visits-tomorrow (reminders_tomorrow route) —
  salespeople see only their own leads' tomorrow visits
  (owner_match_name-scoped, same convention as everywhere else in this
  file); admins/managers see all of them. Renders each visit's message
  pre-filled from that project's reminder template (matched via
  cls_db.get_project_bucket(), same bucketing the rest of the app
  already uses) — a visit whose project has no template gets a warning
  card and no send button instead.

  NEW POST /reminders/site-visits-tomorrow/mark-sent/<visit_id> —
  ownership-gated like every other write route, validates wa_url is a
  genuine https://wa.me/ link before redirecting to it (never redirects
  to an arbitrary caller-supplied URL), then logs the send via
  cls_db.log_reminder_sent() and 302s into WhatsApp.

  NEW admin CRUD routes /settings/whatsapp-reminder-templates(/save,
  /<id>/delete) — mirror the existing WhatsApp Templates admin routes
  exactly, against the new (separate) whatsapp_reminder_templates
  table.

  MODIFIED inject_current_user() — now also injects
  pending_reminder_count (cls_db.get_pending_reminder_count(), scoped
  the same way as unread_assignment_count) so base.html can show a
  drawer badge on every page without each route computing it.

v0.9.8  (July 2026) — APX v0.6.1 Reports Enhancements. Requires cls_db.py
  v2.13, cls_reports.py v1.1, NEW report_view_charts.html, NEW
  templates/_report_date_picker.html partial, reports.html/
  report_view.html both extended (categorized landing page, date-range
  picker).

  MODIFIED /reports — now renders categories (cls_reports.
  visible_categories()) instead of a flat card list.

  MODIFIED /reports/<report_id> and /reports/<report_id>/export.xlsx —
  the old daily/weekly `period` query param + has_period_toggle branch
  is GONE, replaced by the universal date-range picker: both routes now
  call cls_reports.resolve_date_range(report_id, request.args) to get
  (date_from, date_to) — either the caller's ?from=&to=, or the report's
  own configured default — and thread it into build_report()/
  export_to_excel() identically, so Excel always matches what's on
  screen. report_view() picks report_view.html or report_view_charts.html
  per the report's "template" key.

  NEW /reports/daily-scorecard 301-redirect to /reports/salesperson-
  scorecard (the renamed report's new slug — see cls_reports.py's
  changelog) — same treatment for the old export.xlsx path — so any
  bookmark from before this version keeps working.

v0.9.7  (July 2026) — APX v0.6 Reports section. Requires cls_db.py v2.12,
  NEW crm/cls_reports.py, NEW reports.html + report_view.html, base.html
  gained one nav-drawer link.

  NEW "ROUTES — REPORTS" section (3 routes): /reports (landing, cards
  from cls_reports.visible_reports() — admin_only reports are simply
  absent from a salesperson's list, not shown greyed-out), /reports/
  <report_id> (one generic table view for all 12 reports, admin_only
  reports 404 for a non-oversight login — enforced here, not just hidden
  on the landing page), /reports/<report_id>/export.xlsx (openpyxl
  download, same 403 gate). PDF export is browser print-to-PDF
  (report_view.html's own <style media="print">) — no server-side PDF
  library, per Srikanth's confirmed call.

  All three routes reuse cls_db.can_view_all_leads(role) for the
  admin_only gate — the SAME predicate every other oversight check in
  this file already uses, not a new auth pattern.

v0.9.6  (July 2026) — APX v0.5 polish pass, 5 independent changes
  (Srikanth's decisions 1-5). Requires cls_db.py v2.11, lead_detail.html
  v7, dashboard.html v0.7, due_list.html v0.4, NEW new_enquiries_list.html.

  - decision 1: NEW /new-enquiries route (new_enquiries_list()) — calls
    cls_db.get_new_enquiries_leads() (v2.11's redefined criteria:
    current_stage='Incoming' AND zero activity_log rows) and renders a
    NEW new_enquiries_list.html (mirrors reengaged_list.html). dashboard()
    itself is UNCHANGED — it already called get_new_enquiries_count(),
    which cls_db.py v2.11 redefined; only the template's card link moved
    from a generic leads_list filter to this new route so the tap-through
    list matches the count.

  - decision 2: label-only, no route/app.py change — dashboard.html and
    due_list.html rename their own headers.

  - decision 3: leads_filter_screen()'s stage_reasons is now a DEDUPED
    union (dict.fromkeys()) of LOST_REASONS + UNQUALIFIED_REASONS, so
    leads already marked Lost under an old code stay filterable.
    lead_detail()'s lost_reasons kwarg now passes cls_db.STAGE_REASON_
    LISTS["Lost"] (== UNQUALIFIED_REASONS) instead of cls_db.LOST_
    REASONS — the ONLY behavior change; unqualified_reasons is untouched.

  - decision 4: template-only fix (lead_detail.html) — no app.py change.
    update_lead_stage() already wrote the reason into the stage_change
    activity_log row's description; confirmed during Step 0 verification,
    so no cls_db.py write-path change was needed either.

  - decision 5: update_contact_info_route() now also passes alt_phone_raw
    from the form to cls_db.update_lead_contact_info() (new optional
    kwarg, cls_db.py v2.11). new_lead() OPTIONALLY sets alt_phone_raw via
    a second update_lead_contact_info() call after creation succeeds,
    same pattern already used there for property details — create_
    manual_lead()'s own signature is untouched.

v0.9.5  (July 2026) — NEW 'manager' role (oversight tier). Requires
  cls_db.py v2.9, lead_detail.html v6, dashboard_today.html + leads_
  filter.html (renamed template flags), settings_users.html (badge),
  create_admin.py v1.3. NO database migration (role is free-text TEXT).

  Hierarchy: admin (top) > manager (middle) > salesperson (bottom).
  A manager is an OVERSIGHT role: sees EVERY lead in full and the
  company-wide dashboards, but — per Srikanth's Option 1 (least
  privilege) — can only WRITE (change stage, add notes, reassign,
  schedule visits/follow-ups, call-log) on leads they personally own,
  exactly like a salesperson. Managers carry their own leads too (an
  owner_match_name is set at creation), so a manager is a "player-coach":
  sees all, works their own pipeline.

  - Every place that used `role == "admin"` purely for VISIBILITY now
    calls cls_db.can_view_all_leads(role) instead: dashboard_today()
    (company-wide scope), leads_list() (see-all branch + owner dropdown
    + search_all_owners), leads_filter_screen() (owner dropdown), and
    lead_detail() (full vs restricted view). One config-not-code helper,
    no scattered role literals — add a future oversight role in cls_db's
    OVERSIGHT_ROLES and every site follows.

  - lead_detail() now passes TWO booleans, splitting what used to be the
    single `restricted` flag:
      * restricted  = not (owns-it OR can_view_all_leads) → contact-only
                      view. Managers are NOT restricted → they see the
                      full lead.
      * can_write   = _is_lead_owner_or_admin (owner or admin) → whether
                      write controls render at all. Managers viewing a
                      lead they don't own get can_write=False → full read,
                      no write UI (so nothing 403s on submit).
    For every user/lead combination that existed before this version,
    can_write == not restricted (they move together) — so gating write
    controls on can_write instead of not-restricted is a NO-OP for
    existing admins and salespeople. Only the new manager-viewing-a-non-
    owned-lead case differs.

  - The WRITE gate itself (_check_lead_ownership / _is_lead_owner_or_admin)
    is UNCHANGED: owner-or-admin. Manager was deliberately NOT added
    there — that's what keeps writes attributable to exactly one owner
    (clean parallel-run attribution) and managers out of other reps'
    pipelines.

  - admin_required and every admin-only route (Settings, Team page, lead
    delete, source change) are UNTOUCHED — a manager is a logged-in
    non-admin and stays 403'd from all of them. Manager is additive on
    oversight only; no admin power leaks to it. FLAGGED per the auth-
    change rule: this adds a role that can READ every lead — an
    intentional visibility widening, scoped to oversight, no write or
    admin expansion.

v0.9.3  (July 2026) — testing-feedback batch (3 items from Srikanth,
  raised by his team during parallel-run):
  - NEW Settings > Team (/settings/users): admin can activate/
    deactivate any login. Reuses users.active — already enforced by
    verify_login()/get_user_by_id() since v0.1 — so this is new UI on
    an existing flag, not a new access-control mechanism. Guards
    against an admin deactivating their own account.
  - NEW "ACTIONS" button on the lead-detail page, next to the stage
    dropdown. Opens a modal with 4 items: Edit name/phone, Edit
    property details, Reassign owner (all 3 MOVED here out of the
    Contact info card, unchanged otherwise — same routes, same forms)
    and a NEW 4th item, Site Visit Conducted.
  - NEW add_walkin_site_visit (/leads/<id>/site-visit-conducted) +
    cls_db.log_walkin_site_visit() — logs a site visit for an existing,
    in-touch lead who visited a project WITHOUT prior scheduling.
    Collects project (dropdown), conducted-on date+time, and notes;
    written straight to site_visits as status='conducted' and logged
    to activity_log as 'site_visit_conducted' — the SAME activity_type
    the normal scheduled-visit "Conducted" outcome uses, so it's
    already counted everywhere that reads it (Today's Performance,
    lead scoring) with no new counter.
  - "Change source (admin only)" was deliberately LEFT in the Contact
    info card, not moved — Srikanth's list named only 3 items to move;
    flagging this as a scope call rather than silently including it.
  - Requires cls_db.py v2.8, lead_detail.html v5, NEW settings_users.html.

v0.9.2  (July 2026) — lead-detail admin cleanup (3 items from Srikanth):
  - Danger zone: dropped the card/heading/description wrapper around
    delete — just the button remains, still gated by a JS confirm()
    reconfirmation (unchanged; it already asked for confirmation).
  - CAPI fire history + Email history are now accordion cards (same
    toggleCard() pattern as Contact info / Activity History), closed
    by default instead of always-expanded tables.
  - NEW fmt_phone template filter — every phone DISPLAY now renders
    from phone_norm consistently ("+91 83090 32020"), instead of the
    inconsistent phone_raw (which varies with '+91'/no-code/'.0'
    pandas-float artefacts depending on source). phone_raw is
    untouched in the DB and in the editable "Edit name / phone" field.
  - Requires lead_detail.html v4, leads_list.html, whatsapp_picker.html
    (all updated to use the new filter). No cls_db.py change.

v0.9.1  (July 2026) — bottom-bar fix, non-owner search, admin lead
  delete, WhatsApp templates (under a new admin Settings hub).
  - FIX: leads-list bottom bar scrolled with content instead of
    staying fixed. Root cause was an inline style="position:relative"
    on that one action-bar (added for the Fields popover anchor),
    which overrode base.html's .action-bar{position:fixed}. Removed —
    the popover positions itself via fixed-coordinate JS anyway.
  - NEW admin_required decorator — stacks on login_required, the single
    gate for Settings + lead deletion.
  - leads_list(): salespeople now pass search_all_owners=True so an
    ACTIVE search finds leads they don't own (landing on the v0.9
    restricted view); blank list stays scoped to their own. No-op for
    admins (who already see all).
  - NEW delete_lead_route (/leads/<id>/delete, POST, admin-only) —
    hard-deletes a lead + all children via cls_db.delete_lead().
  - NEW whatsapp_picker (/leads/<id>/whatsapp) — ownership-gated
    template picker; builds wa.me deep links pre-filled with the
    project message for this lead's number.
  - NEW Settings hub (admin-only): /settings landing, plus WhatsApp
    Templates CRUD at /settings/whatsapp-templates (+ save/delete).
  - Requires cls_db.py v2.7 (whatsapp_templates table, delete_lead,
    search_all_owners, template CRUD).

v0.9  (July 2026) — Restricted view for non-owned leads + new-lead
  form fields (item 12).
  - lead_detail() no longer hard-403s a non-owner. Closes a real gap:
    the company-wide Reengaged list (get_reengaged_leads() has never
    been owner-filtered) let anyone click through to any lead, which
    then 403'd — jarring, and the actual reason Srikanth asked for
    this. Now renders Contact-info-only; every OTHER section's data
    isn't even fetched, not just hidden. Every WRITE route (stage,
    note, assign, site-visit, follow-up, property/contact edits, call
    tap) is UNCHANGED — still hard-blocks via _check_lead_ownership.
    _is_lead_owner_or_admin() is the new non-aborting check this uses;
    _check_lead_ownership() is now a thin wrapper around it that still
    aborts, for every write route.
  - new_lead() extended with budget/configuration/property_type/facing
    — set via a second update_property_details() call right after
    create_manual_lead() succeeds, not a wider create_manual_lead()
    signature. Campaign deliberately NOT on this form (auto-fill only,
    Job A's job, not manual entry's).
  - Requires cls_db.py v2.6 (no cls_db changes needed for this version
    itself — both changes above reuse existing v2.3+ functions as-is).

v0.8  (July 2026) — Lead detail page rebuild (items 9–16 of Srikanth's
  spec) + the fixed-bottom-bar CSS fix (base.html, applies retroactively
  to every page using .action-bar, not just this one).
  - NEW ampm template filter — 12-hour AM/PM display for Activity
    History and site-visit/follow-up timestamps (item 9).
  - NEW /leads/<cls_id>/contact route + cls_db.update_lead_contact_info()
    — edit name/phone on an existing lead (item 10).
  - assign_lead() RELAXED from admin-only to ownership-based (item 11)
    — flagged inline as a security-relevant change.
  - update_property_details_route() fixed to read configuration/
    property_type/facing as checkbox groups (getlist), and wired to
    the budget field — both were schema-ready since v2.3/v2.5 but this
    route hadn't caught up yet.
  - change_lead_stage() now passes reason_code/reason_notes through
    to cls_db.update_lead_stage() (v2.3) — required by that function
    whenever new_stage is Lost/Unqualified.
  - lead_detail() now clears the reassignment badge (cls_db.
    mark_lead_notification_read()) the moment a lead's current owner
    opens it, and passes owner_options to EVERYONE (not admin-only),
    powering the new universal reassign-to-anyone dropdown.
  - inject_current_user() context processor now also injects
    unread_assignment_count globally, for base.html's new drawer badge.
  - Requires cls_db.py v2.6 or later.

v0.7  (July 2026) — Leads list restructure: top filter bar removed,
  replaced by a bottom icon bar (Filter / Search / Fields) opening
  dedicated full-screen panels, per Srikanth's mobile-first spec.
  - NEW _parse_lead_filters() — single source of truth for every
    filter query-param name, shared by all 3 routes below so they
    can't drift out of sync with each other.
  - leads_list() extended to pass the full v2.5 filter set through to
    cls_db.get_leads_page() (date range, sort, stage reason, campaign,
    source, sub-source, budget, configuration/property_type/facing).
    Still the SAME route/URL — every existing link/bookmark works.
  - NEW leads_search_screen() at /leads/search — dedicated search box,
    carries every other active filter forward as hidden inputs.
  - NEW leads_filter_screen() at /leads/filter — dedicated filter
    panel (accordion of categories, mobile-first — see leads_filter.html's
    own header comment for why this isn't a literal two-pane layout).
    Pre-fills from whatever's currently active. Pipeline stage options
    are now ALL_STAGES, not TARGET_STAGES (bug fix, see cls_db.py v2.5).
  - Requires cls_db.py v2.5 or later.

v0.6  (July 2026) — Dashboard restructure: 3 tabs (Stats / Today's
  Performance / Pipeline Analysis), navigated via a bottom icon bar.
  - dashboard() UNCHANGED at the /dashboard URL (now the "Stats" tab —
    same 4 cards as before), so every existing url_for('dashboard')
    link elsewhere needs no change.
  - NEW dashboard_today() at /dashboard/today — salesperson logins see
    only their own actions today; admin logins see the company-wide
    total. Reads cls_db.get_todays_activity_counts(). No "talk time"
    card — needs telephony data that doesn't exist yet (v1.0).
  - NEW dashboard_pipeline() at /dashboard/pipeline — live snapshot
    tiles per stage (cls_db.get_stage_snapshot_counts()) plus a
    "Total Leads" tile that's specifically today's new intake
    (cls_db.get_leads_created_today_count()), clearly labelled as
    different from the snapshot tiles around it.
  - Requires cls_db.py v2.4 or later (get_stage_snapshot_counts,
    get_leads_created_today_count, get_todays_activity_counts).

v0.5  (July 2026) — lead scoring + card-based lead detail page:
  - leads_list() and lead_detail() now call cls_db.compute_lead_scores()
    for whatever leads they're about to render (only the current page
    of results for leads_list — never the full unfiltered set), and
    attach lead_score/lead_score_band onto each row dict. Pure display
    addition — no new routes, no new writes.
  - lead_detail.html restructured into four clickable accordion cards
    (Contact / Activity History / Site Visits & Follow-ups / Notes),
    with a filter-icon row inside Activity History. No new routes were
    needed — every existing write route still posts to the same
    endpoint and redirects back to lead_detail exactly as before; this
    is a template/JS-only restructure.

v0.4  (July 2026) — richer lead data model:
  - /leads/new now accepts source_detail (Walk-In/Meta/Channel
    Partner/Youtube/Referral/Website), validated against
    cls_db.MANUAL_SOURCE_OPTIONS.
  - NEW POST /leads/<id>/source — ADMIN-ONLY, changes lead_source_
    detail after creation (see cls_db.py v2.0's update_lead_source_
    detail() for why this is locked to admin).
  - NEW POST /leads/<id>/property-details — updates funding_source/
    property_type/configuration/campaign, ownership-scoped like every
    other write route (not admin-only — any assigned salesperson can
    fill these in as they learn them from conversation).
  - Site-visit/follow-up scheduling forms switched from a single
    datetime-local input to separate native date + time inputs
    (calendar picker + clock picker), combined into one value via JS
    before submit — better mobile UX than the combined widget.

v0.3  (July 2026) — refinements from first real mobile usage:
  - NEW GET/POST /leads/new — manual lead entry (walk-ins, references,
    offline inquiries). Initial stage restricted to Prospect/
    Opportunity/Site Visited, matching cls_db.MANUAL_ENTRY_STAGES.
  - /leads/<id>/site-visit/<vid>/conducted REPLACED with
    /leads/<id>/site-visit/<vid>/update — one route, 4 outcomes
    (conducted/rescheduled/cancelled/no_show), mandatory reason.
  - /leads/<id>/follow-up/<fid>/completed REPLACED with
    /leads/<id>/follow-up/<fid>/update — 3 outcomes (completed/
    postponed/cancelled), mandatory reason.
  - NEW POST /leads/<id>/call-tap — fire-and-forget call-attempt
    logging (see cls_db.py v1.9's log_call_tap() for the honest
    explanation of what this can and can't capture).
  - NEW GET /due/<kind> — filtered list for the dashboard's two new
    split due-today cards (kind = 'site_visit' or 'follow_up').
  - NEW GET /reengaged — filtered list for the Reengaged dashboard
    card, using cls_db.get_reengaged_leads() (same approximate
    criteria as the existing count, clearly labeled).
  - dashboard() now passes new_enquiries_count (redefined — see
    cls_db.py v1.9), reengaged_count, and the two due-by-kind counts,
    ALL as clickable cards linking to filtered lists — replacing the
    v0.2 dashboard's inline combined Due Today table.
  - lead_detail() now resolves activity_log actor emails to display
    names via cls_db.get_all_users() before rendering — Activity
    History shows "Elohar Peddi," not
    "elohar.asianproperties@gmail.com."
  - leads_list.html redesigned (dense multi-field-per-line cards
    instead of one-field-per-line stacked table rows) and now shows
    crm_lead_no.

v0.2  (July 2026) — v0.5 "Writer": stage changes, notes, assignment,
  site visits, follow-ups.
  - NEW POST /leads/<id>/stage — change stage, validated against
    cls_db.STAGE_TRANSITIONS (Sell.do's own rule engine, matched
    exactly). Rejects invalid/stale transitions with a clear flash
    message rather than a silent failure.
  - NEW POST /leads/<id>/note — add a free-text note.
  - NEW POST /leads/<id>/assign — reassign lead_owner. ADMIN-ONLY —
    reassigning ownership is a manager-level action, unlike stage
    changes and notes which any salesperson can do on their own leads.
  - NEW POST /leads/<id>/site-visit + /site-visit/<id>/conducted —
    schedule and mark-conducted for site visits.
  - NEW POST /leads/<id>/follow-up + /follow-up/<id>/completed —
    same pattern for follow-ups.
  - NEW _check_lead_ownership() — the exact same ownership gate
    lead_detail already used, now factored out and reused by every
    write route above, so a salesperson can write to their own leads
    only, exactly as they can already only READ their own leads.
  - /dashboard gained due_today (site visits/follow-ups due or
    overdue) — feeds the new Due Today card.
  - Flask's flash() is now used for success/error messages after
    every write action (imported from flask; SECRET_KEY was already
    configured for sessions, so this needed no new setup).
  - Templates updated to match: lead_detail.html gets a stage-change
    form, note form, activity history timeline, and live site-visit/
    follow-up scheduling (replacing the v0.1.2 greyed-out
    placeholders); dashboard.html gets the Due Today card.

v0.1.5  (July 2026) — production hardening:
  - Swapped Flask's development server for Waitress (pure-Python WSGI
    server, Windows-native, no C compiler needed) whenever
    CRM_ENV=production. Local dev (CRM_ENV unset) is UNCHANGED — still
    Flask's own dev server via `python app.py`, same as v0.1-v0.1.4.
  - NEW run_production(): wraps waitress.serve() in a retry loop with
    file-based logging to C:\\CLS\\crm_app_log.txt (guarded print(),
    same pythonw.exe-safe pattern as every other CLS script) — if
    Waitress ever crashes, it's logged and restarted after 10s rather
    than silently taking the whole team's access down.
  - Thread count configurable via WAITRESS_THREADS in .env (defaults
    to 4) — config-not-code, no file edit needed to tune it.
  - requirements.txt gained one new dependency: waitress.
  - No schema changes, no route changes, no template changes. This is
    purely a "how it's served" change — behavior for every existing
    user is identical.

v0.1.4  (July 2026) — lead-ownership scoping:
  - Salespeople now only see leads where leads.lead_owner matches their
    account's owner_match_name (set via create_admin.py). If unset,
    they see zero leads plus a clear warning, rather than everyone's —
    fails closed, not open.
  - Enforced on BOTH /leads (list) and /leads/<id> (detail) — a
    salesperson can't bypass the list filter by guessing/typing another
    lead's URL directly; that now returns 403.
  - Admins are unaffected — see everyone, plus a new optional "View
    owner" dropdown to inspect any one person's pipeline.

v0.1.3  (July 2026) — Fields picker + role-based lead detail:
  - /leads gained a "Fields" picker (Phone/Project/Owner/Source/Updated
    columns, toggle any on/off) — travels via URL params, same pattern
    as the existing Stage/Project filters, so it's bookmarkable and
    survives pagination. No schema change, no new dependency.
  - Lead detail page: CAPI fire history and Email history are now
    admin-only. Salesperson logins see a placeholder for the future
    Activity History (v0.5) instead of data that isn't relevant to
    their role.

v0.1.2  (July 2026) — polish pass after first mobile test:
  - Hamburger nav drawer (Dashboard / Leads / Log out) replacing the
    plain top nav — matches the Sell.do navigation pattern requested.
  - New /dashboard route + 2 mini-dashboard cards on login: "New
    Enquiries This Week" (exact) and "Reengaged Leads" (approximate,
    clearly labeled — see cls_db.get_reengaged_count() docstring for
    the caveat). Login now lands on /dashboard instead of /leads.
  - Denser /leads list — fewer fields per row, more leads per screen.
  - Click-to-call: phone numbers are now tel: links (list + detail),
    opening the native dialer prefilled, same as the Sell.do phone icon.
  - Lead detail page gained a Sell.do-style action bar. Only the call
    button is live. Site-visit and follow-up buttons are shown but
    disabled/greyed — they're wired up in v0.5, once site_visits/
    follow_ups tables exist. Email and WhatsApp buttons are greyed
    placeholders per your explicit instruction to defer both.

v0.1.1  (July 2026) — CRM_HOST made configurable via .env, defaulting
  to 127.0.0.1 (unchanged behavior unless you opt in), so phone/LAN
  testing doesn't require editing this file.

v0.1  (July 2026) — first working version:
  Login (against cls_db.verify_login), lead list with stage/project/
  search filters + pagination, lead detail with CAPI fire history and
  email history. PWA app-shell (manifest + minimal service worker so
  it's installable on a phone). No write routes exist yet — v0.5 adds
  stage changes, notes, and assignment.
=============================================================
"""

import os
import re
import sys
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_from_directory, send_file, abort, flash
)

# ── Import cls_db.py the same way every other CLS job does ──
BASE_DIR = r"C:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db  # noqa: E402  (must follow the sys.path insert above)
import cls_reports  # v0.6 — Reports section; lives in crm/ alongside app.py, no sys.path change needed


# ─────────────────────────────────────────────────────────────
# ENV LOADER  —  same C:\CLS\.env the automation jobs read
# ─────────────────────────────────────────────────────────────

def load_env():
    env = {}
    env_file = os.path.join(BASE_DIR, ".env")
    try:
        from dotenv import dotenv_values
        env = dict(dotenv_values(env_file))
    except ImportError:
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


_env = load_env()

SECRET_KEY = _env.get("CRM_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "CRM_SECRET_KEY is missing from C:\\CLS\\.env. Generate one with:\n"
        '  python -c "import secrets; print(secrets.token_hex(32))"\n'
        "then add it as CRM_SECRET_KEY=<value> to C:\\CLS\\.env and restart."
    )

IS_PRODUCTION = _env.get("CRM_ENV", "development").strip().lower() == "production"

# Defaults to localhost-only (safest). Set CRM_HOST=0.0.0.0 in .env temporarily
# to test from your phone over the same WiFi — see TESTING ON YOUR PHONE below.
# In production, leave this unset — Cloudflare Tunnel connects over localhost.
HOST = _env.get("CRM_HOST", "127.0.0.1").strip()

# Waitress thread count — config-not-code, no file edit needed to tune it.
# 4 is comfortable for a small sales team's request volume.
WAITRESS_THREADS = int(_env.get("WAITRESS_THREADS", "4"))


# ─────────────────────────────────────────────────────────────
# PRODUCTION LOGGING  (v0.1.5) — same pythonw.exe-safe pattern as
# cls_watchdog.py / cls_telegram_listener.py: guard print(), always
# write to file, never let a logging failure crash the app itself.
# ─────────────────────────────────────────────────────────────

CRM_LOG_FILE = os.path.join(BASE_DIR, "crm_app_log.txt")


def _log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] {msg}"
    try:
        if sys.stdout is not None:
            print(entry)
    except Exception:
        pass
    try:
        with open(CRM_LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Secure requires HTTPS. Only enable once this is reached via the
# Cloudflare Tunnel (CRM_ENV=production in .env) — see module docstring.
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION

cls_db.init_db()  # safe/idempotent — creates any missing tables (incl. users)


@app.template_filter("fmt_phone")
def fmt_phone_filter(value):
    """
    (v0.9.2) Consistent phone DISPLAY everywhere a number is shown.
    Fixes item 3 of Srikanth's Aug-2026 admin-page request: phone_raw
    was being shown as-is, so numbers rendered inconsistently across
    leads depending on their source system — some with '+91', some
    without, some with a trailing '.0' pandas-float artefact (e.g.
    '8309032020.0'), some with spaces.

    Always formats from phone_norm (cls_db.norm_phone()'s clean, last-
    10-digits join key) rather than phone_raw, so every lead's number
    displays the same way: '+91 83090 32020'. phone_raw is left
    UNTOUCHED in the DB and in the "Edit name / phone" input — this is
    a display-only filter, not a data migration.
    """
    if not value:
        return "—"
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 10:
        return str(value)   # never hide/crash on unexpected input
    return f"+91 {digits[:5]} {digits[5:]}"


@app.template_filter("ampm")
def ampm_filter(value):
    """
    (v0.8) Formats a cls_db timestamp string into 12-hour AM/PM display
    — item 9 of Srikanth's rebuild spec (Activity History was showing
    raw 24-hour timestamps). Handles both formats cls_db actually
    writes: "YYYY-MM-DD HH:MM:SS" (_now(), used for activity_log/
    stage_updated_at/cls_updated_at) and "YYYY-MM-DD HH:MM" (site
    visit/follow-up scheduled_at). Returns the value UNCHANGED if it
    doesn't match either format — a display nicety should never be
    able to crash a page or hide a value it can't parse.
    """
    if not value:
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%b %d, %Y %I:%M %p")
        except ValueError:
            continue
    return value


# ─────────────────────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────────────────────

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        # v0.11 — if this session is mid-impersonation, confirm the
        # REAL admin behind it still has an active account. Prevents a
        # stuck "viewing as" state if another admin deactivates that
        # admin mid-session: without this check, get_user_by_id() below
        # would only ever re-validate the TARGET account, and the
        # impersonator could keep operating under someone else's
        # identity after their own login was revoked.
        if session.get("impersonator_id"):
            admin = cls_db.get_user_by_id(session["impersonator_id"])
            if not admin:
                session.clear()
                return redirect(url_for("login"))
        # Re-check the account is still active on every request — an
        # admin disabling someone takes effect immediately, not at
        # their next login.
        user = cls_db.get_user_by_id(session["user_id"])
        if not user:
            session.clear()
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """
    v0.9.1 — stacks ON TOP of login_required (apply login_required
    first, then this): 403s any logged-in non-admin. The single gate
    for every Settings tool and lead deletion, so each new admin
    feature inherits the check instead of re-implementing a role test.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = cls_db.get_user_by_id(session["user_id"])
        if not user or user["role"] != "admin":
            abort(403, description="This area is for admins only.")
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_current_user():
    # Makes `current_user` available in every template automatically.
    # v0.8 — also injects unread_assignment_count (cls_db v2.3's
    # reassignment badge), so base.html can show it next to the
    # "Leads" drawer link on every page without every single route
    # having to compute and pass it explicitly.
    # v0.10 — also injects pending_reminder_count (cls_db.
    # get_pending_reminder_count()), same scoping rule, for the new
    # "Reminders" drawer link's badge.
    # v0.11 — also injects `impersonator`: the REAL admin's user dict
    # when this session is mid "View as", else None. base.html uses
    # this (not current_user) to decide whether to render the
    # impersonation banner, since current_user is the TARGET during
    # impersonation.
    user = None
    unread_assignment_count = 0
    pending_reminder_count = 0
    impersonator = None
    if session.get("user_id"):
        user = cls_db.get_user_by_id(session["user_id"])
        if user:
            unread_assignment_count = cls_db.get_unread_assignment_count(user.get("owner_match_name"))
            owner_scope = user.get("owner_match_name") if user["role"] == "salesperson" else None
            pending_reminder_count = cls_db.get_pending_reminder_count(owner_scope)
        if session.get("impersonator_id"):
            impersonator = cls_db.get_user_by_id(session["impersonator_id"])
    return {
        "current_user": user,
        "unread_assignment_count": unread_assignment_count,
        "pending_reminder_count": pending_reminder_count,
        "impersonator": impersonator,
    }


def _actor():
    """
    (v0.11) Returns the string to pass as `actor` on every cls_db
    write. Normal: current user's email. During impersonation:
    dual-attributed as 'target@x (via admin@x)' so activity_log records
    BOTH parties on every write made while an admin is viewing as
    someone else. This is the ONE place that decision lives — every
    write route below calls this instead of user["email"] directly, so
    dual-attribution applies automatically with no per-route change.
    """
    user = cls_db.get_user_by_id(session["user_id"])
    if session.get("impersonator_id"):
        admin = cls_db.get_user_by_id(session["impersonator_id"])
        if admin:
            return f"{user['email']} (via {admin['email']})"
    return user["email"]


# ─────────────────────────────────────────────────────────────
# USER ACTIVITY LOG  —  v0.12, request-level audit hook
# ─────────────────────────────────────────────────────────────
# config-not-code: an endpoint not listed here just logs under its raw
# endpoint name instead of a friendly label — nothing is ever silently
# unlogged, this dict only controls display text.
ENDPOINT_LABELS = {
    "dashboard": "Viewed Dashboard",
    "dashboard_today": "Viewed Today's Performance",
    "dashboard_pipeline": "Viewed Pipeline Analysis",
    "leads_search_screen": "Searched Leads",
    "lead_detail": "Viewed Lead",
    "settings_home": "Opened Settings",
}


@app.before_request
def _log_user_action():
    """
    (v0.12) Records every logged-in request against the current login's
    session (cls_db.log_user_action()), for the admin User Activity Log.
    Skipped entirely for static assets, the login/logout routes
    themselves (nothing to attach the action to yet, or the session is
    about to be torn down), the service worker (sw.js — the browser
    fetches this on its own in the background, not a user action; it's
    a separate skip from 'static' since it's served from the root path,
    not /static/), and any request with no logged-in user_id. Wrapped
    in try/except that swallows and logs any failure — same "never let
    logging break a real request" posture as cls_snapshot.py's
    swallowed errors elsewhere in this codebase.
    """
    try:
        if request.endpoint in (None, "static", "login", "logout", "service_worker"):
            return
        if not session.get("user_id"):
            return
        label = ENDPOINT_LABELS.get(request.endpoint, request.endpoint)
        cls_id = request.view_args.get("cls_id") if request.view_args else None
        cls_db.log_user_action(
            session.get("session_row_id"), _actor(), request.method, label, cls_id=cls_id
        )
    except Exception as e:
        _log(f"_log_user_action failed: {e}", level="ERROR")


# ─────────────────────────────────────────────────────────────
# ROUTES — AUTH
# ─────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        user = cls_db.verify_login(email, password)
        if user:
            # Cloudflare Tunnel (cloudflared) proxies every request, so
            # request.remote_addr is always 127.0.0.1 in production —
            # the real visitor IP only survives in Cloudflare's own
            # CF-Connecting-IP header. Falls back to remote_addr for
            # local/dev testing where that header is never set.
            ip = request.headers.get("CF-Connecting-IP", request.remote_addr)
            session_row_id = cls_db.start_user_session(
                user["user_id"], user["email"], ip
            )
            session.clear()
            session["user_id"] = user["user_id"]
            session["session_row_id"] = session_row_id
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        error = "Incorrect email or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    if session.get("session_row_id"):
        cls_db.end_user_session(session["session_row_id"], reason="manual")
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────
# ROUTES — DASHBOARD
# ─────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def home():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    # v0.6 — Dashboard restructure: this is now the "Stats" tab of a
    # 3-tab dashboard (Stats / Today's Performance / Pipeline Analysis),
    # navigated via the bottom icon bar in dashboard.html. Kept at the
    # SAME route name/URL as before (v0.3) so every existing
    # url_for('dashboard') link elsewhere (due_list.html,
    # reengaged_list.html, "Back to Dashboard" buttons) needs no change.
    new_enquiries_count = cls_db.get_new_enquiries_count()  # v1.9 — stage-based now
    reengaged_count = cls_db.get_reengaged_count(days=7)
    follow_up_due_count = len(cls_db.get_due_by_kind("follow_up"))
    site_visit_due_count = len(cls_db.get_due_by_kind("site_visit"))
    return render_template(
        "dashboard.html",
        active_tab="stats",
        new_enquiries_count=new_enquiries_count,
        reengaged_count=reengaged_count,
        follow_up_due_count=follow_up_due_count,
        site_visit_due_count=site_visit_due_count,
    )


@app.route("/dashboard/today")
@login_required
def dashboard_today():
    """
    v0.6 — Today's Performance tab. Salesperson logins see ONLY their
    own actions today (scoped by their login email, which is what
    activity_log.actor always stores); oversight logins (admin OR
    manager, v0.9.5) see the company-wide total. No "talk time" card —
    that needs telephony data (v1.0) that doesn't exist yet; see
    cls_db.get_todays_activity_counts()'s docstring.
    """
    user = cls_db.get_user_by_id(session["user_id"])
    # v0.9.5 — managers, like admins, supervise the whole team, so they
    # see the company-wide total, not just their own actions.
    company_wide = cls_db.can_view_all_leads(user["role"])
    scope_email = None if company_wide else user["email"]
    perf = cls_db.get_todays_activity_counts(actor_email=scope_email)
    return render_template(
        "dashboard_today.html",
        active_tab="today",
        perf=perf,
        company_wide=company_wide,
    )


@app.route("/dashboard/pipeline")
@login_required
def dashboard_pipeline():
    """
    v0.6 — Pipeline Analysis tab. Tiles are a live snapshot of where
    every lead sits right now (see cls_db.get_stage_snapshot_counts()
    docstring for why this is a snapshot, not a historical-as-of-today
    figure), except "Total Leads" which is specifically today's new
    intake — flagged inline on the page itself so it isn't mistaken
    for another snapshot tile.
    """
    stage_counts = cls_db.get_stage_snapshot_counts()
    leads_today = cls_db.get_leads_created_today_count()
    return render_template(
        "dashboard_pipeline.html",
        active_tab="pipeline",
        stage_counts=stage_counts,
        leads_today=leads_today,
        all_stages=cls_db.ALL_STAGES,
    )


@app.route("/due/<kind>")
@login_required
def due_list(kind):
    """
    v0.3 — filtered list behind the dashboard's two split due-today
    cards. kind must be 'site_visit' or 'follow_up'.
    """
    if kind not in ("site_visit", "follow_up"):
        abort(404)
    items = cls_db.get_due_by_kind(kind)
    return render_template("due_list.html", items=items, kind=kind)


@app.route("/reengaged")
@login_required
def reengaged_list():
    """
    v0.3 — filtered list behind the dashboard's Reengaged card. Same
    approximate criteria as the count on the dashboard — labeled as
    such in the template, not hidden.
    """
    leads = cls_db.get_reengaged_leads(days=7)
    return render_template("reengaged_list.html", leads=leads)


@app.route("/new-enquiries")
@login_required
def new_enquiries_list():
    """
    v0.9.6 — filtered list behind the dashboard's redefined New
    Enquiries card (cls_db.py v2.11 decision 1). Same criteria as
    get_new_enquiries_count(): current_stage='Incoming' AND zero
    activity_log rows — genuinely untouched since arrival.
    """
    leads = cls_db.get_new_enquiries_leads()
    return render_template("new_enquiries_list.html", leads=leads)


# ─────────────────────────────────────────────────────────────
# ROUTES — REPORTS (v0.6)
# ─────────────────────────────────────────────────────────────
# All 12 reports share these 3 routes — report-specific behavior lives
# entirely in cls_reports.py's REPORTS config, not here. The admin_only
# gate is enforced HERE (403, not just a hidden landing-page card) so a
# salesperson can't reach a Team report by typing/bookmarking its URL.

def _report_or_404(report_id):
    if report_id not in cls_reports.REPORTS_BY_ID:
        abort(404)
    return cls_reports.REPORTS_BY_ID[report_id]


def _check_report_access(meta, user):
    if meta["admin_only"] and not cls_db.can_view_all_leads(user["role"]):
        abort(403, description="This report is for admins/managers only.")


@app.route("/reports")
@login_required
def reports_home():
    user = cls_db.get_user_by_id(session["user_id"])
    return render_template(
        "reports.html",
        categories=cls_reports.visible_categories(user),
        is_oversight=cls_db.can_view_all_leads(user["role"]),
    )


@app.route("/reports/daily-scorecard")
@login_required
def report_view_old_scorecard_redirect():
    return redirect(url_for("report_view", report_id="salesperson-scorecard", **request.args), code=301)


@app.route("/reports/daily-scorecard/export.xlsx")
@login_required
def report_export_old_scorecard_redirect():
    return redirect(url_for("report_export_excel", report_id="salesperson-scorecard", **request.args), code=301)


@app.route("/reports/<report_id>")
@login_required
def report_view(report_id):
    user = cls_db.get_user_by_id(session["user_id"])
    meta = _report_or_404(report_id)
    _check_report_access(meta, user)

    date_from, date_to = cls_reports.resolve_date_range(report_id, request.args)
    report = cls_reports.build_report(report_id, user, date_from=date_from, date_to=date_to)
    return render_template(
        meta.get("template", "report_view.html"),
        report=report,
        quick_select_links=cls_reports.quick_select_links(),
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/reports/<report_id>/export.xlsx")
@login_required
def report_export_excel(report_id):
    user = cls_db.get_user_by_id(session["user_id"])
    meta = _report_or_404(report_id)
    _check_report_access(meta, user)

    date_from, date_to = cls_reports.resolve_date_range(report_id, request.args)
    report = cls_reports.build_report(report_id, user, date_from=date_from, date_to=date_to)
    try:
        buf = cls_reports.export_to_excel(report)
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("report_view", report_id=report_id, **request.args))

    filename = report["title"].lower().replace(" ", "-").replace("/", "-") + ".xlsx"
    return send_file(
        buf, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ─────────────────────────────────────────────────────────────
# ROUTES — LEADS (read-only)
# ─────────────────────────────────────────────────────────────


# All optional columns the "Fields" picker can toggle. "Name" isn't
# here — it's the mandatory anchor, always shown, always the link into
# the lead's detail page.
ALL_LIST_FIELDS = ["phone", "project", "owner", "source", "updated"]
DEFAULT_LIST_FIELDS = ["phone", "project", "updated"]  # today's existing look


# ─────────────────────────────────────────────────────────────
# LEADS FILTER — DATE RANGE PRESETS  (v0.11.1, item 4 of Srikanth's
# bug-fix batch)
# ─────────────────────────────────────────────────────────────
# Mirrors cls_reports.py's QUICK_RANGES/resolve_date_range() naming and
# structure (same Monday-Sunday week-start convention, Srikanth's
# confirmed 2026-07 decision — see cls_reports.py v1.1's changelog) but
# is its OWN small dict here rather than importing cls_reports' helpers:
# the Leads filter needs a longer preset list (11 vs Reports' 4 — adds
# Yesterday/Last 7/Last 14/Last week/Last month/Maximum, none of which
# Reports currently has), and this screen is otherwise unrelated to the
# Reports module. Duplicating ~10 lines of date math here avoids coupling
# the Leads filter's lifecycle to Reports' — touches fewer files than
# extending cls_reports.py's dict to serve a screen it doesn't otherwise
# know about, while keeping the exact same convention.
#
# All computed server-side (no client-side date math, no timezone drift).

def _dr_today():
    d = datetime.now().strftime("%Y-%m-%d")
    return d, d


def _dr_yesterday():
    d = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return d, d


def _dr_last_n_days(n):
    now = datetime.now()
    start = now - timedelta(days=n - 1)  # inclusive of today
    return start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")


def _dr_this_week():
    """Monday of current week through TODAY (month-to-date style, never
    extends into the future) — same convention as
    cls_reports._this_week_range()."""
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    return monday.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")


def _dr_last_week():
    """Full previous Monday-Sunday (7 days), not to-date."""
    now = datetime.now()
    this_monday = now - timedelta(days=now.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d")


def _dr_this_month():
    """1st of the current month through TODAY (month-to-date) — same
    convention as cls_reports._this_month_range()."""
    now = datetime.now()
    first = now.replace(day=1)
    return first.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")


def _dr_last_month():
    """Full previous calendar month, 1st through last day."""
    now = datetime.now()
    first_this_month = now.replace(day=1)
    last_day_prev_month = first_this_month - timedelta(days=1)
    first_prev_month = last_day_prev_month.replace(day=1)
    return first_prev_month.strftime("%Y-%m-%d"), last_day_prev_month.strftime("%Y-%m-%d")


def _dr_maximum():
    """"Maximum" clears date_from/date_to entirely (no date filter at
    all — all-time), NOT a huge literal date range. Returned as ("", "")
    so it round-trips through the same "" == no-filter convention every
    other filter in this dict already uses."""
    return "", ""


# Config-not-code: the dropdown's option order AND the resolver share
# this one dict — add a preset here and both follow automatically.
DATE_PRESETS = {
    "today":        _dr_today,
    "yesterday":    _dr_yesterday,
    "last_7_days":  lambda: _dr_last_n_days(7),
    "last_14_days": lambda: _dr_last_n_days(14),
    "last_30_days": lambda: _dr_last_n_days(30),
    "this_week":    _dr_this_week,
    "last_week":    _dr_last_week,
    "this_month":   _dr_this_month,
    "last_month":   _dr_last_month,
    "maximum":      _dr_maximum,
}

# Display order for the dropdown (dict insertion order above already
# matches this, but spelled out explicitly since template iteration
# order mattering silently is the kind of thing that's easy to break
# later by reordering DATE_PRESETS for an unrelated reason).
DATE_PRESET_ORDER = list(DATE_PRESETS.keys()) + ["custom"]

DATE_PRESET_LABELS = {
    "today": "Today", "yesterday": "Yesterday",
    "last_7_days": "Last 7 days", "last_14_days": "Last 14 days",
    "last_30_days": "Last 30 days",
    "this_week": "This week", "last_week": "Last week",
    "this_month": "This month", "last_month": "Last month",
    "maximum": "Maximum", "custom": "Custom",
}


def _detect_active_date_preset(date_from, date_to):
    """
    Given the currently-resolved date_from/date_to ("" meaning unset),
    figure out which preset (if any) produced them — used to show the
    right label when a bookmarked URL carries raw date_from/date_to with
    no date_preset param (backward compatibility, see _parse_lead_filters).
    Returns "" if neither is set (no filter, nothing to label), or
    "custom" if they're set but don't match any known preset.
    """
    if not date_from and not date_to:
        return ""
    for key, fn in DATE_PRESETS.items():
        if key == "maximum":
            continue  # maximum's own output is ("",""), already handled above
        f, t = fn()
        if f == date_from and t == date_to:
            return key
    return "custom"


def _parse_lead_filters():
    """
    v0.7 — reads every leads-list filter param from the query string
    into one dict. Shared by leads_list(), leads_filter_screen(), and
    leads_search_screen() so all three agree on param names and none
    of them drift out of sync with each other over time. Checkbox
    multi-selects (configuration/property_type/facing) come back as
    lists via getlist(); everything else is a single value or "".

    Deliberately returns "" (not None) for anything absent — every
    caller either feeds this straight into a template's hidden-input
    re-population (wants strings) or passes it to get_leads_page()
    (which treats "" the same as None, since `if x:` is falsy either way).

    v0.11.1 — NEW date_preset resolution (item 4). A `date_preset` query
    param (one of DATE_PRESETS' keys, or "custom") is resolved into
    concrete date_from/date_to server-side BEFORE this dict is used —
    get_leads_page() itself needs zero changes, it already just takes
    date_from/date_to strings. Backward compatible: any existing
    bookmarked URL with date_from/date_to and NO date_preset keeps
    working exactly as before (date_preset is additive); this function
    additionally back-fills filters["date_preset"] by DETECTING which
    preset those raw dates match (or "custom" if none), purely so the
    filter screen can show the right "· <preset>" summary label.
    """
    date_preset_param = request.args.get("date_preset") or ""
    date_from = request.args.get("date_from") or ""
    date_to = request.args.get("date_to") or ""

    if date_preset_param and date_preset_param != "custom" and date_preset_param in DATE_PRESETS:
        date_from, date_to = DATE_PRESETS[date_preset_param]()
        active_preset = date_preset_param
    elif date_preset_param == "custom":
        active_preset = "custom"
    elif date_from or date_to:
        active_preset = _detect_active_date_preset(date_from, date_to)
    else:
        active_preset = ""

    return {
        "q":             request.args.get("q") or "",
        "stage":         request.args.get("stage") or "",
        "project":       request.args.get("project") or "",
        "owner":         request.args.get("owner") or "",
        "date_from":     date_from,
        "date_to":       date_to,
        "date_preset":   active_preset,
        "sort_by":       request.args.get("sort_by") or "recent",
        "stage_reason":  request.args.get("stage_reason") or "",
        "campaign":      request.args.get("campaign") or "",
        "source":        request.args.get("source") or "",
        "sub_source":    request.args.get("sub_source") or "",
        "budget":        request.args.get("budget") or "",
        "configuration": request.args.getlist("configuration"),
        "property_type": request.args.getlist("property_type"),
        "facing":        request.args.getlist("facing"),
    }


@app.route("/leads")
@login_required
def leads_list():
    f = _parse_lead_filters()
    page = request.args.get("page", 1, type=int)

    user = cls_db.get_user_by_id(session["user_id"])
    owner_unlinked_warning = False

    if cls_db.can_view_all_leads(user["role"]):
        # v0.9.5 — oversight roles (admin OR manager) can optionally view
        # one person's pipeline via a dropdown; leaving it blank shows
        # everyone's leads. (A manager with their own owner_match_name
        # still sees EVERYONE here — the dropdown is how they narrow to
        # one rep, including themselves.)
        owner = request.args.get("owner") or None
        owner_options = cls_db.get_distinct_owners()
    else:
        # Salespeople are force-scoped to their own owner_match_name —
        # the request can't override this via query params.
        owner = user.get("owner_match_name") or None
        owner_options = []
        if not owner:
            owner_unlinked_warning = True
    f["owner"] = owner or ""

    # If a salesperson's account isn't linked yet, show zero leads
    # rather than silently falling through to "everyone's leads" —
    # fails closed, not open. (Oversight roles never hit this — they're
    # allowed the unfiltered view by design.)
    if not cls_db.can_view_all_leads(user["role"]) and not owner:
        result = {"rows": [], "total": 0, "page": 1, "per_page": cls_db.CRM_PAGE_SIZE, "total_pages": 1}
    else:
        # v0.9.1 — a salesperson's ACTIVE SEARCH looks across all owners
        # (they land on the restricted read-only view for anything not
        # theirs); their blank list stays scoped to their own leads.
        # Oversight roles (admin/manager, v0.9.5) already see everything,
        # so the flag is a no-op for them.
        result = cls_db.get_leads_page(
            stage=f["stage"] or None, project=f["project"] or None,
            search=f["q"] or None, owner=owner, page=page,
            date_from=f["date_from"] or None, date_to=f["date_to"] or None,
            sort_by=f["sort_by"], stage_reason=f["stage_reason"] or None,
            campaign=f["campaign"] or None, source=f["source"] or None,
            sub_source=f["sub_source"] or None, budget=f["budget"] or None,
            configuration=f["configuration"] or None,
            property_type=f["property_type"] or None,
            facing=f["facing"] or None,
            search_all_owners=(not cls_db.can_view_all_leads(user["role"])),
        )

    # v0.5 — lead scoring. Only the CURRENT PAGE of rows gets scored
    # (not the full filtered set) — cheap, bounded by per_page, and the
    # only rows actually rendered anyway.
    scores = cls_db.compute_lead_scores([r["cls_id"] for r in result["rows"]])
    for r in result["rows"]:
        s = scores.get(r["cls_id"], {"score": 0, "band": "Cold"})
        r["lead_score"] = s["score"]
        r["lead_score_band"] = s["band"]

    # Fields picker: only trust an explicit submission (marked by the
    # hidden fields_submitted=1 input in the form) — otherwise a bare
    # /leads visit (first time, or a bookmark) falls back to the
    # sensible default rather than showing zero optional columns.
    if request.args.get("fields_submitted"):
        active_fields = [f2 for f2 in request.args.getlist("fields") if f2 in ALL_LIST_FIELDS]
    else:
        active_fields = DEFAULT_LIST_FIELDS

    return render_template(
        "leads_list.html",
        result=result,
        owner_options=owner_options,
        owner_unlinked_warning=owner_unlinked_warning,
        filters=f,
        all_fields=ALL_LIST_FIELDS,
        active_fields=active_fields,
    )


@app.route("/leads/search")
@login_required
def leads_search_screen():
    """
    v0.7 — dedicated full-screen search box (replaces the old inline
    top-bar search input). Carries every OTHER currently-active filter
    forward as hidden inputs, so searching doesn't silently clear a
    filter someone already set — only submits back to leads_list()
    with `q` added/changed.
    """
    f = _parse_lead_filters()
    return render_template("leads_search.html", filters=f)


@app.route("/leads/filter")
@login_required
def leads_filter_screen():
    """
    v0.7 — dedicated full-screen filter panel (replaces the old inline
    top-bar dropdowns). Pre-fills every control from whatever's
    currently active, so reopening this screen shows your existing
    selections rather than resetting them. Carries `q` forward as a
    hidden input so an active search term survives applying filters.

    Pipeline stage options are ALL_STAGES (all 8), not TARGET_STAGES —
    see cls_db.py v2.5's changelog for why that's a deliberate fix,
    not scope creep.
    """
    f = _parse_lead_filters()
    user = cls_db.get_user_by_id(session["user_id"])
    # Presentation-layer labels only — cls_db.SORT_OPTIONS itself holds
    # raw SQL ORDER BY clauses, which have no business leaking into a
    # template. Kept here (app.py), not cls_db.py, since it's purely a
    # display concern.
    sort_labels = {
        "recent":       "Most Recently Updated",
        "created_desc": "Newest Inquiries First",
        "created_asc":  "Oldest Inquiries First",
        "name_asc":     "Name (A–Z)",
    }
    return render_template(
        "leads_filter.html",
        filters=f,
        stages=cls_db.ALL_STAGES,
        projects=sorted(set(cls_db.PROJECT_BUCKETS.values())),
        sort_labels=sort_labels,
        # v0.9.6 — DEDUPED union (Srikanth's decision 3): the Lost picker
        # now shows UNQUALIFIED_REASONS (see lead_detail() below), but
        # leads already marked Lost under an OLD LOST_REASONS code must
        # stay filterable here, so this filter list still covers both.
        # dict.fromkeys() dedupes while preserving first-seen order.
        stage_reasons=list(dict.fromkeys(cls_db.LOST_REASONS + cls_db.UNQUALIFIED_REASONS)),
        source_options=cls_db.SOURCE_OPTIONS,
        sub_source_options=cls_db.MANUAL_SOURCE_OPTIONS,
        budget_options=cls_db.BUDGET_BRACKETS,
        configuration_options=cls_db.CONFIGURATIONS,
        property_type_options=cls_db.PROPERTY_TYPES,
        facing_options=cls_db.FACING_OPTIONS,
        owner_options=cls_db.get_distinct_owners() if cls_db.can_view_all_leads(user["role"]) else [],
        can_view_all_owners=cls_db.can_view_all_leads(user["role"]),
        # v0.11.1 — item 4: date-range quick-select dropdown.
        date_preset_order=DATE_PRESET_ORDER,
        date_preset_labels=DATE_PRESET_LABELS,
    )


def _is_lead_owner_or_admin(lead, user):
    """
    v0.9 — non-aborting ownership check, factored out of
    _check_lead_ownership below.

    v0.9.5 — this was the WRITE gate: True only for the lead's own owner
    or an admin, INTENTIONALLY not widened to managers — a manager saw
    every lead (cls_db.can_view_all_leads, the READ side) but wrote only
    to their own, so every write stayed attributable to one owner.

    v0.11.1 (July 2026) — REVERSES that split for managers. Srikanth's
    explicit call, flagged as security-relevant before building: a
    manager may now write to ANY lead, exactly as if they owned it, not
    just their own pipeline. Implemented as an added OR against
    cls_db.can_write_any_lead(user["role"]) — the existing owner-or-admin
    check is untouched, this just widens who else satisfies it. A FUTURE
    READER MUST NOT ASSUME THE OLD v0.9.5 READ/WRITE SPLIT STILL HOLDS —
    see cls_db.py v2.19's changelog and can_view_all_leads()'s docstring
    for the same note on the read side. activity_log still records the
    ACTUAL acting user (never the lead's owner) on every write — that
    behavior is untouched and is the whole reason this grant is safe.

    Scope: this function (and _check_lead_ownership below) governs ONLY
    lead-level write routes (stage, notes, assign, site visit/follow-up,
    property/contact edits, call tap). Settings, the Team page, lead
    deletion, and source-editing are gated separately by admin_required /
    role=="admin" and are NOT affected by this change.

    lead_detail() combines this (write side) with can_view_all_leads()
    (read side) to render a manager a full, writable view of leads that
    aren't theirs (previously: full but read-only). Every write route
    still calls _check_lead_ownership (which aborts) — this predicate
    only decides whether write CONTROLS render on a plain GET.
    """
    if user["role"] == "admin":
        return True
    if cls_db.can_write_any_lead(user["role"]):
        return True
    owner = (user.get("owner_match_name") or "").strip().lower()
    lead_owner = (lead.get("lead_owner") or "").strip().lower()
    return bool(owner) and owner == lead_owner


def _check_lead_ownership(lead, user):
    """
    Shared ownership gate — used by EVERY v0.5+ write route (stage
    change, notes, assign, site visit/follow-up, property edits,
    contact edits, call tap), so a salesperson can't write to someone
    else's lead. Aborts with 403 on failure. NOT used by lead_detail()
    itself anymore (v0.9) — that route renders a restricted, read-only
    view instead of blocking entirely; see _is_lead_owner_or_admin().
    """
    if not _is_lead_owner_or_admin(lead, user):
        abort(403, description="This lead isn't assigned to you.")


@app.route("/leads/<cls_id>")
@login_required
def lead_detail(cls_id):
    """
    v0.9 — a non-owner (e.g. a salesperson who found this lead via the
    company-wide Reengaged list, not their own scoped Leads list) no
    longer gets a hard 403 here. They get Contact info only, in a
    read-only "restricted" view — Activity History, Site Visits &
    Follow-ups, and Notes render grayed out and non-expandable, and
    the stage dropdown / edit toggles / action bar don't render at
    all. Every WRITE route (stage, note, assign, site-visit, follow-
    up, property/contact edits, call tap) still hard-blocks via
    _check_lead_ownership regardless of what this page shows — the
    restricted view is a rendering choice, not the actual security
    boundary.
    """
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")

    user = cls_db.get_user_by_id(session["user_id"])

    # v0.9.5 — two separate booleans, splitting what used to be one flag:
    #   can_write   : may this user WRITE to this lead? (owner, admin, or
    #                 — v0.11.1 — any oversight-write role per
    #                 cls_db.can_write_any_lead()). Drives whether write
    #                 controls render at all.
    #   restricted  : is this a contact-info-ONLY view? True only when the
    #                 user can neither write to NOR oversee this lead.
    # v0.11.1 — a manager is never `restricted` (can_view_all_leads) AND now
    # naturally gets can_write=True on every lead too (falls out of
    # _is_lead_owner_or_admin()'s new can_write_any_lead() OR — no separate
    # patch needed here). A salesperson is unaffected: can_write stays
    # owner-only, restricted stays True for anything not theirs.
    can_write = _is_lead_owner_or_admin(lead, user)
    restricted = not (can_write or cls_db.can_view_all_leads(user["role"]))

    # v0.8 — clear this lead's reassignment badge the moment its
    # CURRENT owner opens it. Only fires for the owner themselves —
    # an admin, a manager, or a restricted non-owner viewing it doesn't
    # clear it on the owner's behalf.
    if can_write:
        owner_name = (user.get("owner_match_name") or "").strip().lower()
        lead_owner_name = (lead.get("lead_owner") or "").strip().lower()
        if owner_name and owner_name == lead_owner_name:
            cls_db.mark_lead_notification_read(cls_id)

    if restricted:
        # Deliberately don't even FETCH the other sections' data for a
        # restricted viewer — not just hide it in the template. A
        # competing salesperson's notes/activity on a lead that isn't
        # yours shouldn't reach the browser at all, grayed out or not.
        events, comms, activity_log = [], [], []
        site_visits, follow_ups, allowed_next_stages = [], [], []
    else:
        events = cls_db.get_events_for_lead(cls_id)
        comms = cls_db.get_comms_for_lead(cls_id)
        activity_log = cls_db.get_activity_log_for_lead(cls_id)
        site_visits = cls_db.get_site_visits_for_lead(cls_id)
        follow_ups = cls_db.get_follow_ups_for_lead(cls_id)
        allowed_next_stages = cls_db.STAGE_TRANSITIONS.get(lead["current_stage"], [])

        # v0.3 — resolve each activity's actor email to a display name.
        user_names = cls_db.get_all_users()
        for entry in activity_log:
            entry["actor_name"] = user_names.get(entry["actor"], entry["actor"])

    # v0.5 — lead scoring, same function as leads_list, single-item call.
    score = cls_db.compute_lead_scores([cls_id]).get(cls_id, {"score": 0, "band": "Cold"})
    lead["lead_score"] = score["score"]
    lead["lead_score_band"] = score["band"]

    return render_template(
        "lead_detail.html",
        lead=lead, events=events, comms=comms,
        activity_log=activity_log,
        site_visits=site_visits,
        follow_ups=follow_ups,
        allowed_next_stages=allowed_next_stages,
        restricted=restricted,
        can_write=can_write,
        source_options=cls_db.MANUAL_SOURCE_OPTIONS,
        funding_sources=cls_db.FUNDING_SOURCES,
        property_types=cls_db.PROPERTY_TYPES,
        configurations=cls_db.CONFIGURATIONS,
        budget_options=cls_db.BUDGET_BRACKETS,
        facing_options=cls_db.FACING_OPTIONS,
        # v0.9.6 — Srikanth's decision 3: the Lost picker now shows the
        # SAME list as Unqualified (cls_db.STAGE_REASON_LISTS["Lost"] is
        # UNQUALIFIED_REASONS), not cls_db.LOST_REASONS. LOST_REASONS
        # stays defined/PAUSED in cls_db.py for historical filtering only
        # (see leads_filter_screen() above) — it's just no longer what
        # renders here.
        lost_reasons=cls_db.STAGE_REASON_LISTS["Lost"],
        unqualified_reasons=cls_db.UNQUALIFIED_REASONS,
        # These feed WRITE controls (reassign dropdown, property-detail
        # editor), so gate on can_write — a manager viewing a non-owned
        # lead (restricted=False, can_write=False) gets the full read view
        # but no reassign/edit options. For pre-v0.9.5 users can_write ==
        # (not restricted), so this is unchanged for them.
        owner_options=cls_db.get_distinct_owners() if can_write else [],
        project_buckets=sorted(set(cls_db.PROJECT_BUCKETS.values())) if can_write else [],
    )


# ─────────────────────────────────────────────────────────────
# ROUTES — WRITER (v0.5)
# ─────────────────────────────────────────────────────────────
# Every route below re-runs the same ownership check lead_detail does
# above — a salesperson can write to their own leads only. /assign is
# further restricted to admin, since reassigning ownership is a
# manager-level action.

@app.route("/leads/<cls_id>/stage", methods=["POST"])
@login_required
def change_lead_stage(cls_id):
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    new_stage = request.form.get("new_stage", "")
    # v0.8 — only present when new_stage is Lost/Unqualified (the
    # template's JS reveals this panel only for those two); cls_db.
    # update_lead_stage() itself is the actual enforcement point for
    # "these are required for Lost/Unqualified," not this route.
    reason_code = request.form.get("reason_code") or None
    reason_notes = request.form.get("reason_notes") or None
    ok, message = cls_db.update_lead_stage(
        cls_id, new_stage, actor=_actor(),
        reason_code=reason_code, reason_notes=reason_notes
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/note", methods=["POST"])
@login_required
def add_lead_note(cls_id):
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    text = request.form.get("note_text", "")
    ok, message = cls_db.add_note(cls_id, actor=_actor(), text=text)
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/assign", methods=["POST"])
@login_required
def assign_lead(cls_id):
    """
    v0.8 — SECURITY-RELEVANT CHANGE, flagging explicitly: this route
    was admin-only through v0.7. Item 11 of Srikanth's rebuild spec
    ("my people assign to other project") explicitly asks for
    salespeople to reassign a lead that isn't a fit for their project,
    not just admins. Restriction relaxed to the SAME ownership check
    every other write route already uses (_check_lead_ownership) — a
    salesperson can only reassign a lead that's currently theirs,
    exactly like every other write action on this page. Admins remain
    unrestricted, as before.
    """
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    new_owner = request.form.get("new_owner", "")
    ok, message = cls_db.reassign_lead_owner(cls_id, new_owner, actor=_actor())
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/site-visit", methods=["POST"])
@login_required
def add_site_visit(cls_id):
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    scheduled_at = request.form.get("scheduled_at", "")
    notes = request.form.get("notes", "")
    ok, message = cls_db.schedule_site_visit(cls_id, scheduled_at, actor=_actor(), notes=notes)
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/site-visit-conducted", methods=["POST"])
@login_required
def add_walkin_site_visit(cls_id):
    """
    v0.9.3 — "Site Visit Conducted" (ACTIONS button, item 4). For an
    existing, in-touch lead who showed up at a project WITHOUT a prior
    scheduled visit. Deliberately a separate route from add_site_visit
    /update_site_visit_route — there's no open 'scheduled' row to
    close here, see cls_db.log_walkin_site_visit()'s docstring.
    """
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    project = request.form.get("project", "")
    conducted_at = request.form.get("conducted_at", "")
    notes = request.form.get("notes", "")
    ok, message = cls_db.log_walkin_site_visit(
        cls_id, project, conducted_at, actor=_actor(), notes=notes
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/site-visit/<int:visit_id>/update", methods=["POST"])
@login_required
def update_site_visit_route(cls_id, visit_id):
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    action = request.form.get("action", "")
    reason = request.form.get("reason", "")
    new_scheduled_at = request.form.get("new_scheduled_at") or None
    ok, message = cls_db.update_site_visit(
        visit_id, action, actor=_actor(), reason=reason,
        new_scheduled_at=new_scheduled_at
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/follow-up", methods=["POST"])
@login_required
def add_follow_up(cls_id):
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    scheduled_at = request.form.get("scheduled_at", "")
    notes = request.form.get("notes", "")
    ok, message = cls_db.schedule_follow_up(cls_id, scheduled_at, actor=_actor(), notes=notes)
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/follow-up/<int:followup_id>/update", methods=["POST"])
@login_required
def update_follow_up_route(cls_id, followup_id):
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    action = request.form.get("action", "")
    reason = request.form.get("reason", "")
    new_scheduled_at = request.form.get("new_scheduled_at") or None
    ok, message = cls_db.update_follow_up(
        followup_id, action, actor=_actor(), reason=reason,
        new_scheduled_at=new_scheduled_at
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/call-tap", methods=["POST"])
@login_required
def call_tap(cls_id):
    """
    Fire-and-forget — the frontend calls this via fetch() right
    alongside the tel: link, doesn't wait for or care about the
    response. See cls_db.py v1.9's log_call_tap() for what this can
    and can't actually capture.
    """
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        return ("", 404)
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)
    cls_db.log_call_tap(cls_id, actor=_actor())
    return ("", 204)


@app.route("/leads/new", methods=["GET", "POST"])
@login_required
def new_lead():
    """
    v0.9 — item 12: added budget, configuration, property_type, facing
    to the manual entry form. No cls_db changes needed for this —
    create_manual_lead() stays focused on identity/dedup fields only;
    these extra qualification fields are set via a SECOND call to the
    already-existing update_property_details() right after creation
    succeeds, reusing that function's validation exactly as the "Edit
    property details" toggle on lead_detail does. Two DB calls, not a
    wider create_manual_lead() signature — simpler to reason about and
    keeps that function's one job (create + dedup-check) unchanged.

    Campaign is deliberately NOT on this form — item 12 only wants it
    auto-filled for Meta/Google leads (Job A's job, not this route's),
    and a manual entry is by definition not one of those.
    """
    user = cls_db.get_user_by_id(session["user_id"])

    if request.method == "POST":
        full_name = request.form.get("full_name", "")
        phone_raw = request.form.get("phone_raw", "")
        initial_stage = request.form.get("initial_stage", "")
        project = request.form.get("project", "")
        email_raw = request.form.get("email_raw", "")
        source_detail = request.form.get("source_detail", "")
        # Salespeople default to their own owner_match_name; admins can
        # optionally override via a free-text field on the form.
        lead_owner = request.form.get("lead_owner", "") or user.get("owner_match_name", "")

        ok, result = cls_db.create_manual_lead(
            full_name=full_name, phone_raw=phone_raw, initial_stage=initial_stage,
            actor=_actor(), project=project, email_raw=email_raw,
            lead_owner=lead_owner, source_detail=source_detail
        )
        if ok:
            cls_id = result
            budget = request.form.get("budget") or None
            configuration_list = request.form.getlist("configuration")
            property_type_list = request.form.getlist("property_type")
            facing_list = request.form.getlist("facing")
            if budget or configuration_list or property_type_list or facing_list:
                cls_db.update_property_details(
                    cls_id, actor=_actor(), budget=budget,
                    configuration=", ".join(configuration_list) if configuration_list else None,
                    property_type=", ".join(property_type_list) if property_type_list else None,
                    facing=", ".join(facing_list) if facing_list else None,
                )
            # v0.9.6 — optional alternate phone (decision 5, OPTIONAL part).
            # Same "second call, existing function" pattern as the property
            # details block above — create_manual_lead() itself stays
            # focused on identity/dedup fields only.
            alt_phone_raw = request.form.get("alt_phone_raw") or None
            if alt_phone_raw:
                cls_db.update_lead_contact_info(
                    cls_id, actor=_actor(), alt_phone_raw=alt_phone_raw
                )
            flash("Lead created.", "success")
            return redirect(url_for("lead_detail", cls_id=cls_id))
        flash(result, "error")

    return render_template(
        "lead_new.html",
        manual_entry_stages=cls_db.MANUAL_ENTRY_STAGES,
        projects=sorted(set(cls_db.PROJECT_BUCKETS.values())),
        source_options=cls_db.MANUAL_SOURCE_OPTIONS,
        budget_options=cls_db.BUDGET_BRACKETS,
        configuration_options=cls_db.CONFIGURATIONS,
        property_type_options=cls_db.PROPERTY_TYPES,
        facing_options=cls_db.FACING_OPTIONS,
    )


@app.route("/leads/<cls_id>/source", methods=["POST"])
@login_required
def update_lead_source(cls_id):
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    if user["role"] != "admin":
        abort(403, description="Only admins can change a lead's source after creation.")

    new_source_detail = request.form.get("source_detail", "")
    ok, message = cls_db.update_lead_source_detail(cls_id, new_source_detail, actor=_actor())
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/property-details", methods=["POST"])
@login_required
def update_property_details_route(cls_id):
    """
    v0.8 — updated for the v2.3/v2.5 multi-select change: configuration,
    property_type, and facing are now checkbox groups (getlist), not
    single dropdowns, joined into the comma-separated string cls_db
    expects. budget is new here too (schema existed since v2.3, this
    route just hadn't been wired to it yet).
    """
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    configuration_list = request.form.getlist("configuration")
    property_type_list = request.form.getlist("property_type")
    facing_list = request.form.getlist("facing")

    ok, message = cls_db.update_property_details(
        cls_id, actor=_actor(),
        funding_source=request.form.get("funding_source") or None,
        property_type=", ".join(property_type_list) if property_type_list else None,
        configuration=", ".join(configuration_list) if configuration_list else None,
        campaign=request.form.get("campaign") or None,
        budget=request.form.get("budget") or None,
        facing=", ".join(facing_list) if facing_list else None,
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/contact", methods=["POST"])
@login_required
def update_contact_info_route(cls_id):
    """
    v0.8 — item 10 of Srikanth's rebuild spec: edit a lead's name/
    phone after creation. See cls_db.update_lead_contact_info()'s
    docstring for the flagged matcher-risk this carries.
    """
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    ok, message = cls_db.update_lead_contact_info(
        cls_id, actor=_actor(),
        full_name=request.form.get("full_name") or None,
        phone_raw=request.form.get("phone_raw") or None,
        alt_phone_raw=request.form.get("alt_phone_raw") or None,
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", cls_id=cls_id))


@app.route("/leads/<cls_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_lead_route(cls_id):
    """
    v0.9.1 — ADMIN-ONLY hard delete (item 3). admin_required gates it;
    a salesperson can't reach this even by crafting the POST. The
    template also gates the button behind current_user.role=='admin',
    but this decorator is the real boundary.

    FLAGGED (also in cls_db.delete_lead + v2.7 changelog): if this
    person still exists in Sell.do, Job B re-imports them on its next
    sync. Accepted parallel-run reality — a suppression list is v1.0+.
    """
    ok, message = cls_db.delete_lead(cls_id, actor=_actor())
    flash(message, "success" if ok else "error")
    # Deleted lead's own page no longer exists — go back to the list.
    return redirect(url_for("leads_list"))


@app.route("/leads/<cls_id>/whatsapp")
@login_required
def whatsapp_picker(cls_id):
    """
    v0.9.1 — item 4. The lead-page WhatsApp button opens this template
    picker. Ownership-gated exactly like the write actions: a non-owner
    on the restricted view never sees the button (template hides it),
    and this route hard-blocks them too.

    Picking a template here builds a wa.me deep link (in the template)
    that opens the user's own WhatsApp to this lead's number with the
    project message pre-filled. It CANNOT auto-send — WhatsApp blocks
    that — so the user reviews and taps send, which is exactly the
    described flow.
    """
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    if not lead.get("phone_norm"):
        flash("This lead has no valid phone number to message.", "error")
        return redirect(url_for("lead_detail", cls_id=cls_id))

    templates = cls_db.get_whatsapp_templates()
    # Pre-render each template's message against THIS lead, so the
    # picker can build ready-to-use wa.me links with no further work.
    rendered = []
    for t in templates:
        body = cls_db.render_whatsapp_template(t["message_body"], lead)
        rendered.append({
            "template_id": t["template_id"],
            "project": t["project"],
            "message": body,
        })

    return render_template(
        "whatsapp_picker.html",
        lead=lead,
        templates=rendered,
        phone_e164="91" + lead["phone_norm"],  # India country code + normalized 10-digit
    )


# ─────────────────────────────────────────────────────────────
# ROUTES — SITE-VISIT REMINDERS  (v0.10)
# ─────────────────────────────────────────────────────────────
# Tomorrow's scheduled site visits, one WhatsApp reminder deep-link per
# visit. Same "cannot auto-send, user reviews and taps Send inside
# WhatsApp" flow as whatsapp_picker() above — this route only ever
# builds a wa.me link and records that it was opened.

@app.route("/reminders/site-visits-tomorrow")
@login_required
def reminders_tomorrow():
    user = cls_db.get_user_by_id(session["user_id"])
    owner_scope = user.get("owner_match_name") if user["role"] == "salesperson" else None
    visits = cls_db.get_site_visits_for_tomorrow(owner_match_name=owner_scope)

    # {project bucket -> reminder message body}, so each visit can be
    # matched to its project's template the same way the rest of the
    # app buckets projects (cls_db.get_project_bucket()).
    templates_by_bucket = {t["project"]: t["message_body"] for t in cls_db.get_whatsapp_reminder_templates()}
    for v in visits:
        bucket = cls_db.get_project_bucket(v["project"])
        body = templates_by_bucket.get(bucket)
        if body:
            v["rendered_body"] = cls_db.render_whatsapp_reminder_template(
                body, {"full_name": v["full_name"], "project": bucket}, v["scheduled_at"]
            )
        else:
            v["rendered_body"] = None

    return render_template("reminders_tomorrow.html", visits=visits)


@app.route("/reminders/site-visits-tomorrow/mark-sent/<int:visit_id>", methods=["POST"])
@login_required
def reminder_mark_sent(visit_id):
    visit = cls_db.get_site_visit_by_id(visit_id)
    if not visit:
        abort(404, description="No site visit found with that id.")
    lead = cls_db.get_lead_by_id(visit["cls_id"])
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    wa_url = request.form.get("wa_url", "")
    if not wa_url.startswith("https://wa.me/"):
        flash("Couldn't open WhatsApp — invalid link.", "error")
        return redirect(url_for("reminders_tomorrow"))

    cls_db.log_reminder_sent(visit_id, visit["cls_id"], actor=_actor())
    return redirect(wa_url)


# ─────────────────────────────────────────────────────────────
# SETTINGS  (admin-only hub — v0.9.1)
# ─────────────────────────────────────────────────────────────

@app.route("/settings")
@login_required
@admin_required
def settings_home():
    """v0.9.1 — the admin Settings landing page. A hub of tiles;
    WhatsApp Templates is the first tenant, with room for more (user
    management, list config, etc.) without touching the hamburger menu
    each time."""
    return render_template("settings.html")


@app.route("/settings/users")
@login_required
@admin_required
def settings_users():
    """v0.9.3 — admin Settings > Team: list every CRM login with an
    activate/deactivate toggle. Item 1 of Srikanth's testing-feedback
    batch. Reuses users.active, already enforced by verify_login()/
    get_user_by_id() since v0.1 — this is the first admin-facing UI
    for a flag that already worked, not a new permission concept."""
    users = cls_db.get_all_users_detailed()
    return render_template("settings_users.html", users=users)


@app.route("/settings/user-activity")
@login_required
@admin_required
def settings_user_activity():
    """
    (v0.12) Admin Settings > User Activity Log — full session-level
    audit trail (cls_db.get_user_timeline()). Optional query params:
    user_id (filter to one login), date_from/date_to ('YYYY-MM-DD').
    With no params at all this defaults to today — resolved here (not
    left to get_user_timeline()'s own internal default) so the date
    inputs on the page can show the actual range being displayed.
    """
    user_id = request.args.get("user_id", type=int)
    date_from = request.args.get("date_from") or None
    date_to = request.args.get("date_to") or None
    if not date_from and not date_to:
        today = datetime.now().strftime("%Y-%m-%d")
        date_from = date_to = today
    elif not date_from:
        date_from = date_to
    elif not date_to:
        date_to = date_from

    timeline = cls_db.get_user_timeline(user_id=user_id, date_from=date_from, date_to=date_to)
    users = cls_db.get_all_users_detailed()
    return render_template(
        "settings_user_activity.html",
        timeline=timeline, users=users,
        selected_user_id=user_id, date_from=date_from, date_to=date_to,
    )


@app.route("/settings/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def settings_user_toggle(user_id):
    new_active = request.form.get("active") == "1"
    ok, message = cls_db.set_user_active(
        user_id, new_active, actor_user_id=session["user_id"]
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("settings_users"))


@app.route("/admin/impersonate/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def impersonate_start(user_id):
    """
    v0.11 — admin "View as": full session swap into a target
    salesperson/manager's account, for diagnosing what they see without
    asking them to screen-share. Every write made from here on is
    dual-attributed via _actor() until Exit to admin is tapped.
    """
    admin = cls_db.get_user_by_id(session["user_id"])
    # get_user_by_id() only ever returns an ACTIVE account (WHERE
    # active=1 — see its docstring) — so a deactivated target already
    # comes back None here and is rejected by the "not found" branch
    # below, same as a genuinely unknown user_id. No separate active
    # check needed.
    target = cls_db.get_user_by_id(user_id)

    if not target:
        flash("That user couldn't be found or is deactivated.", "error")
        return redirect(url_for("settings_users"))
    if target["user_id"] == admin["user_id"]:
        flash("You can't view as yourself.", "error")
        return redirect(url_for("settings_users"))
    if target["role"] == "admin":
        flash("Can't view as another admin.", "error")
        return redirect(url_for("settings_users"))

    session["impersonator_id"] = session["user_id"]
    session["user_id"] = target["user_id"]
    cls_db.log_impersonation(admin["email"], target["email"], event="start")
    flash(f"Now viewing as {target['full_name'] or target['email']}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/impersonate/exit", methods=["POST"])
@login_required
def impersonate_exit():
    """v0.11 — ends a "View as" session and returns to the real admin
    login. Available to anyone mid-impersonation, not admin_required —
    at this point session["user_id"] IS the target, who may not be an
    admin themselves."""
    if not session.get("impersonator_id"):
        flash("You're not currently viewing as someone else.", "error")
        return redirect(url_for("dashboard"))

    target = cls_db.get_user_by_id(session["user_id"])
    admin = cls_db.get_user_by_id(session["impersonator_id"])

    session["user_id"] = session["impersonator_id"]
    session.pop("impersonator_id", None)

    if target and admin:
        cls_db.log_impersonation(admin["email"], target["email"], event="exit")
    flash("Returned to admin view.", "success")
    return redirect(url_for("dashboard"))


@app.route("/settings/whatsapp-templates")
@login_required
@admin_required
def whatsapp_templates_admin():
    """v0.9.1 — admin CRUD list for WhatsApp templates."""
    templates = cls_db.get_whatsapp_templates()
    return render_template(
        "settings_whatsapp.html",
        templates=templates,
        projects=sorted(set(cls_db.PROJECT_BUCKETS.values())),
    )


@app.route("/settings/whatsapp-templates/save", methods=["POST"])
@login_required
@admin_required
def whatsapp_template_save():
    ok, message = cls_db.upsert_whatsapp_template(
        project=request.form.get("project", ""),
        message_body=request.form.get("message_body", ""),
        actor=_actor(),
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("whatsapp_templates_admin"))


@app.route("/settings/whatsapp-templates/<int:template_id>/delete", methods=["POST"])
@login_required
@admin_required
def whatsapp_template_delete(template_id):
    ok, message = cls_db.delete_whatsapp_template(template_id)
    flash(message, "success" if ok else "error")
    return redirect(url_for("whatsapp_templates_admin"))


@app.route("/settings/whatsapp-reminder-templates")
@login_required
@admin_required
def whatsapp_reminder_templates_admin():
    """v0.10 — admin CRUD list for site-visit reminder templates.
    Mirrors whatsapp_templates_admin() exactly, against the separate
    whatsapp_reminder_templates table."""
    templates = cls_db.get_whatsapp_reminder_templates()
    return render_template(
        "settings_whatsapp_reminders.html",
        templates=templates,
        projects=sorted(set(cls_db.PROJECT_BUCKETS.values())),
    )


@app.route("/settings/whatsapp-reminder-templates/save", methods=["POST"])
@login_required
@admin_required
def whatsapp_reminder_template_save():
    ok, message = cls_db.upsert_whatsapp_reminder_template(
        project=request.form.get("project", ""),
        message_body=request.form.get("message_body", ""),
        actor=_actor(),
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("whatsapp_reminder_templates_admin"))


@app.route("/settings/whatsapp-reminder-templates/<int:template_id>/delete", methods=["POST"])
@login_required
@admin_required
def whatsapp_reminder_template_delete(template_id):
    ok, message = cls_db.delete_whatsapp_reminder_template(template_id)
    flash(message, "success" if ok else "error")
    return redirect(url_for("whatsapp_reminder_templates_admin"))


# ─────────────────────────────────────────────────────────────
# PWA PLUMBING
# ─────────────────────────────────────────────────────────────

@app.route("/sw.js")
def service_worker():
    # Served from the ROOT path (not /static/sw.js) so its default scope
    # covers the whole app, not just /static/*. Needed for "Add to Home
    # Screen" installability.
    return send_from_directory(
        os.path.join(app.root_path, "static"), "sw.js",
        mimetype="application/javascript"
    )


# ─────────────────────────────────────────────────────────────
# PRODUCTION SERVER  (v0.1.5)
# ─────────────────────────────────────────────────────────────

def run_production():
    """
    Serves via Waitress instead of Flask's dev server — the swap this
    whole hardening pass is about. Wrapped in a self-healing retry
    loop: Task Scheduler's "At startup" trigger + restart-on-failure
    setting (see the DEPLOYMENT section of this file's docstring)
    covers the process dying outright or the machine rebooting; this
    loop covers the narrower case where waitress.serve() raises
    without the process itself exiting. Either way, this must never
    go down without a trace — same rule cls_watchdog.py and
    cls_telegram_listener.py already follow.
    """
    from waitress import serve

    retry_delay_sec = 10
    attempt = 0

    _log(f"APX CRM starting (Waitress, {WAITRESS_THREADS} threads, "
         f"host={HOST}:5000).")

    while True:
        attempt += 1
        try:
            serve(app, host=HOST, port=5000, threads=WAITRESS_THREADS)
            # serve() blocks forever under normal operation. Reaching
            # this line means it returned without raising, which
            # shouldn't happen in practice — log it rather than
            # silently exiting the whole task.
            _log("Waitress serve() returned unexpectedly (no exception). "
                 "Restarting.", "WARNING")
        except Exception as e:
            _log(f"CRASH on attempt {attempt}: {e}", "ERROR")
        time.sleep(retry_delay_sec)


if __name__ == "__main__":
    if IS_PRODUCTION:
        run_production()
    else:
        # Local dev — unchanged from v0.1. Flask's own dev server,
        # debug=True, no Waitress, no retry loop. Only CRM_ENV=production
        # in .env switches this over to run_production() above.
        app.run(host=HOST, port=5000, debug=True)
