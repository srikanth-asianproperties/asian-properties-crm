"""
=============================================================
app.py — Asian Properties CRM (APX) | v0.1 Viewer
=============================================================
Version : 0.53
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
v0.53 (2026-08-16) — Task 3 Part B: Today's Agenda subsection + tab
  rename (cls_db.py v2.58 — see that file's changelog for
  get_todays_agenda()). dashboard_today() route gains a second, SEPARATE
  scope variable, scope_owner (owner_match_name-based, same as
  dashboard()'s Stats-tab cards) alongside the existing actor-email-
  based scope_email — Today's Agenda is lead-scoped, not actor-scoped,
  so it can't reuse scope_email. New todays_agenda context var passed
  into the existing dashboard_today.html render. ADDITIVE ONLY —
  nothing existing removed or modified.
v0.52 (2026-08-16) — Task 3 Part A: dashboard metrics, lead_reengaged
  logging, New Enquiries bug fix (cls_db.py v2.57 — see that file's
  changelog for the get_new_enquiries_count()/leads() bug-fix detail
  and the new lead_reengaged activity logging). NEW: dashboard() route
  gains 2 context vars, no_future_activity_count/missed_calls_count,
  computed with the SAME scope_owner already resolved for the
  existing 4 cards. NEW routes GET /dashboard/no-future-activity
  (no_future_activity_list()) and GET /dashboard/missed-calls
  (missed_calls_list()), same @login_required + scope_owner pattern as
  due_list()/new_enquiries_list(); render new templates
  no_future_activity_list.html and missed_calls_list.html. ADDITIVE
  ONLY — nothing existing removed or modified.
v0.51 (2026-08-15) — Meta App Review screencast support — ads_read demo
  (Ads Insights Preview), read-only Graph API call, no cls_db changes.
  NEW META_SYSTEM_USER_TOKEN constant (.env-sourced, same convention as
  META_WEBHOOK_VERIFY_TOKEN/META_LEADGEN_APP_SECRET). NEW route GET
  /admin/ads-insights-preview (admin_ads_insights_preview(), same
  @login_required + @admin_required pattern as
  admin_webhook_test_leads()) — calls Meta's Insights API directly
  (fields=impressions,spend,clicks,ctr,campaign_name,
  date_preset=last_7d) against act_825098213089084, wrapped in
  try/except so it can never 500; renders new template
  ads_insights_preview.html with either the campaign rows or a plain
  error message. Reuses cls_capi_core.GRAPH_API_VERSION (v23.0) rather
  than a hardcoded version number. NEW top-level `import requests`.
v0.50 (2026-08-15) — Meta App Review screencast support: isolated
  test-lead viewer, no writes to production `leads` table, no
  interaction with Job A/B/C. meta_leadgen_webhook()'s POST branch gains
  ONE new line (wrapped in its own try/except, never blocks the 200 OK
  back to Meta): cls_db.log_webhook_test_lead(payload). GET verification
  logic untouched. NEW route GET /admin/webhook-test-leads
  (admin_webhook_test_leads(), @login_required + @admin_required, same
  pattern as settings_bulk_jobs()) renders new template
  webhook_test_leads.html from cls_db.get_webhook_test_leads(). This is
  v1.5+ scope (ahead of active v1.0 work), explicitly approved to build
  now because it unblocks App Review's screencast requirement.
v0.49 (2026-08-14) — inline CAPI firing redesign. change_lead_stage()'s
  existing body is UNCHANGED; added one block after flash() and before
  the return redirect(...): on a successful stage change into one of
  cls_capi_core.TARGET_STAGES, fires that lead's CAPI event synchronously
  via cls_capi_core.fire_single_lead_event() (using this file's own
  already-loaded _env dict, not a fresh load_env() call — same .env,
  avoids re-reading the file from disk on every stage-change POST). On
  any failure (fire returns False, or any exception), queues it via
  cls_db.queue_failed_fire() instead of blocking the request — a
  salesperson's stage change must never fail because Meta was slow or
  down. NEW import cls_capi_core near the existing import cls_db.
  Requires cls_db.py v2.55 (capi_fire_queue table + queue functions)
  and cls_capi_core.py v1.0 (fire_single_lead_event()).
  PATCH (same v0.49, 2026-08-14): the CAPI-firing block above was
  silent on both outcomes — found during live testing when a fire
  neither succeeded nor queued, with nothing in crm_app_log.txt to show
  why. Added _log() calls (this file's existing helper, same convention
  as the webhook routes above) on both paths: a successful fire logs at
  INFO, a queued failure (or exception) logs at WARNING with the error
  text. No logic changed — same fire/queue behavior as before, now visible.
v0.48 (2026-08-14) — added Facebook Login for Business required routes:
  OAuth redirect placeholder, deauthorize callback, data deletion callback
  (with signature verification), and deletion status stub page. No cls_db
  writes; data deletion route logs requests only, does not yet perform
  actual deletion — that requires separate design work.
  NEW GET /oauth/meta-callback — static landing page, no params processed,
  no auth. Exists only because Meta's Tech Provider setup requires at
  least one Valid OAuth Redirect URI on file.
  NEW POST /webhooks/meta-deauthorize and NEW POST /webhooks/
  meta-data-deletion — both verify Meta's signed_request via a new shared
  helper, _verify_meta_signed_request() (base64url-decode + HMAC-SHA256
  over the payload segment using META_LEADGEN_APP_SECRET, hmac.compare_
  digest for the comparison — Meta's documented algorithm, factored once
  rather than duplicated across the two routes). META_LEADGEN_APP_SECRET
  read via the same _env dict/.env convention as v0.47's
  META_WEBHOOK_VERIFY_TOKEN. Deauthorize just logs user_id on a valid
  signature; data-deletion additionally generates a confirmation_code
  (secrets.token_hex(8) — cryptographic, not random) and returns Meta's
  required {"url", "confirmation_code"} JSON shape. Both return 400 on an
  invalid/unverifiable signature.
  NEW GET /data-deletion-status — reads the ?id= query param and shows a
  stub "being processed" message with a contact address (reuses
  sales1@asianbuild.in, the existing internal-mail address already used
  elsewhere in this file — see v0.5's export-email changelog entry —
  rather than inventing a new placeholder). The ?id= value is
  html.escape()'d before being placed in the response: it's Flask string
  output (no Jinja auto-escaping), so an unescaped reflected query param
  here would be a straightforward reflected-XSS opening — added even
  though the task spec didn't call it out explicitly, per this file's own
  "prioritize safe/secure code" convention. Genuinely a stub: this route
  does NOT look up or act on any real deletion record (none exists yet
  in cls_db) — it exists only so the URL data-deletion webhook returns
  resolves to something instead of a 404, ahead of real deletion-tracking
  design.
  All four routes deliberately have no @login_required — Meta's own
  servers call these, not a browser session with a CRM login.
v0.47 (2026-08-14) — added Meta leadgen webhook verification endpoint
  (GET challenge-response + POST logging only, no cls.db writes).
  NEW /webhooks/meta-leadgen (meta_leadgen_webhook(), GET+POST, no
  @login_required — Meta's own servers call this, not a browser
  session). GET performs the hub.mode/hub.verify_token/hub.challenge
  handshake Meta App Review requires, comparing against
  META_WEBHOOK_VERIFY_TOKEN (read via this file's _env dict, same
  dotenv-loaded-not-os.environ convention as CRM_SECRET_KEY/CRM_HOST
  above — NOT the CLS_APK_UPLOAD_SECRET-style real-OS-env-var
  convention, since this token is meant to live in .env). POST just
  logs the payload via _log() (this file's existing pythonw-safe
  logging helper) and returns 200 — no cls_db writes yet; that's a
  separate later task once routing design (this endpoint's eventual
  role replacing Job A's polling) is finalized.
v0.46 (2026-08-11) — Phase 5 of the 6-phase feature batch (requires
  cls_db.py v2.53): settings_bulk_reassign_commit() now passes
  cls_ids=matched_ids to create_bulk_job(), snapshotting the reassigned
  leads into the new bulk_job_leads table atomically with the job row.
  NEW GET /settings/bulk-jobs/<job_id>/export.xlsx
  (settings_bulk_job_export_excel(), @admin_required) — per-bulk-job
  Excel download, same shape as settings_export_leads_excel(), rows from
  the bulk_job_leads snapshot via cls_db.get_bulk_job_lead_rows().
v0.45 (2026-08-11) — Phase 4 of the 6-phase feature batch (requires
  cls_db.py v2.52): NEW GET /dashboard/today/<metric> (dashboard_today_
  drilldown()) — one route/template for all 5 Today's Performance tiles,
  dispatched via the new cls_db.TODAY_PERFORMANCE_METRICS config dict.
  Same company_wide/actor-email scoping as dashboard_today() itself.
  Pipeline Analysis's stage tiles (dashboard_pipeline.html) are now
  clickable too, linking to the existing leads_list route's "stages"
  filter param — no route/context change needed there, template-only.
v0.44 (2026-08-11) — Phase 3 of the 6-phase feature batch: dashboard()
  now also computes today_attendance (cls_db.get_today_attendance_overview(),
  the SAME function settings_attendance_today() already calls — no new
  query) when the logged-in user is admin (literal role=='admin' check),
  None otherwise, for a new admin-only "Today's Attendance" card on
  dashboard.html. No new route, no schema/cls_db.py change.
v0.43 (2026-08-11) — Phase 1 of the 6-phase feature batch: attendance_home()
  now redirects an admin session straight to settings_attendance_today()
  ("Who's Present Today") instead of rendering attendance.html's admin card,
  so the nav drawer's "Attendance" link lands an admin directly on that view.
  Checked via the literal role=='admin' string, matching attendance.html's
  own gate. attendance.html's admin card had its "Who's Present Today"
  button removed (Settings & Attendance button only) — see that template's
  own changelog. No schema change, no cls_db.py change.
v0.42 (2026-08-09) — Nine-item batch (requires cls_db.py v2.51):
  - settings_attendance_dashboard()'s `employees` list (the oversight
    filter dropdown) now excludes role='admin', matching cls_db.py
    v2.51's same exclusion in the two functions this route calls.
  - settings.html: "My Attendance" tile in the role-agnostic second
    block now hidden for current_user.role == 'admin'. manager/
    salesperson unaffected.
  - lead_detail.html: activity-log branches now bold their static
    label fragment (e.g. "Stage changed:", "Reassigned:") — template-
    only, no route/schema change.
  - leads_search.html: caption text updated to match cls_db.py v2.51's
    rewritten search classification (# / apx- = exact lead-ID match;
    an all-digits term = phone-only; otherwise unchanged combined
    search).
  - NEW GET /attendance/today-summary (login_required, self-scoped
    only — actor is always session["user_id"], no company-wide
    option): renders attendance_today_summary.html from
    cls_db.get_todays_achievements(), reusing dashboard_today.html's
    existing .stat-card/.stat-card-grid classes, no new CSS.
  - /logout is now an INTERSTITIAL (confirmed with Srikanth): with an
    active session it shows the Daily Achievements screen above
    (show_logout_button=True) instead of clearing the session
    immediately. NEW /logout/confirm carries the exact clear-session-
    and-redirect body /logout used to run directly — reached only via
    the interstitial's "Continue to logout" button. A /logout hit with
    no active session skips straight to login, unchanged from before.
  - dashboard.html: removed the "View all leads →" button (was
    directly above the bottom tab bar). Confirmed with Srikanth this
    is the element item 2 meant — NOT the nav-drawer "Leads" link
    (base.html), which stays untouched as the only way to reach
    /leads.
v0.41 (2026-08-07) — Manager view-mode toggle (requires cls_db.py
  v2.50). Mounika is a player-coach (manager role, carries her own
  leads too) — this lets her flip her OWN default leads/dashboard view
  between "team-wide" (unchanged manager behavior) and "own-leads-only"
  (see her own pipeline like a salesperson would), with zero change to
  her role, WRITE access, or report ACCESS.
  NEW route POST /toggle-view-mode (@login_required, 403 if
  current_user.role != 'manager'): reads the user's current view_mode
  via cls_db.get_view_mode(), flips it, saves via cls_db.set_view_mode()
  (which itself re-validates role=='manager' — belt and suspenders with
  the route's own 403), redirects to request.referrer if present and
  same-origin-relative, else dashboard().
  SWAPPED cls_db.can_view_all_leads(user["role"]) -> cls_db.
  effective_company_wide(user) at every call site that was computing a
  company-wide-vs-own-leads SCOPE variable for a leads/dashboard VIEW:
  dashboard(), dashboard_booking_summary(), dashboard_today(),
  due_list(), reengaged_list(), new_enquiries_list(),
  settings_telephony_recordings(), and leads_list() (which didn't have
  a named `company_wide` variable before — introduced one there, same
  pattern as the others, replacing its 3 inline can_view_all_leads()
  calls).
  DELIBERATELY NOT changed — flagged, not an oversight:
    - _check_report_access()'s admin_only gate and reports_home()'s
      is_oversight flag — that's report ACCESS (which categories/
      reports a role may open at all), not a view SCOPE, and Srikanth's
      instruction was explicit that this stays role-based.
    - _is_lead_owner_or_admin() / can_write_any_lead() and every WRITE
      route built on them — write access stays role-based, unaffected
      by view_mode, also explicit.
    - lead_detail()'s `restricted` gate and serve_recording()'s
      `can_read` gate — both OR in can_write, which is already True for
      every manager via WRITE_ANYWHERE_ROLES regardless of view_mode,
      so swapping the can_view_all_leads() half of either OR would be a
      no-op in practice; left as can_view_all_leads() for clarity.
    - settings_telephony()'s company_wide (recording-FOLDER-PATH config
      rows, not leads) and settings_telephony_revoke_token()'s gate —
      user-config/action screens, not a leads view; and the Attendance
      Dashboard's is_oversight (a different domain entirely). None of
      these were in the requested list; flagging here since they use
      the identical can_view_all_leads() pattern, in case Srikanth wants
      any of them folded into the toggle later.
    - leads_filter_screen()'s owner_options/can_view_all_owners — these
      populate the FILTER PANEL's available choices, not leads_list()'s
      own default scope; leads_list() itself (the page actually shown)
      is covered above.
v0.40 (2026-08-07) — Two small fixes, bundled:
  (1) NEW APP_VERSION constant (config-not-code, defined near
  RECORDINGS_DIR below), surfaced via inject_current_user() as
  `app_version` in every template. base.html's drawer-footer and
  settings.html now show it ("APX v0.40"). MUST be bumped in lockstep
  with this docstring's own "Version :" line above on every future
  version bump — nothing reads the docstring programmatically, so
  keeping the two equal is a manual convention, not enforced by code.
  (2) api_telephony_upload_recording() now looks up the call's
  direction (INCOMING/OUTGOING, already staged in call_log_staging by
  report-calls) via the NEW cls_db.get_call_direction(lead_id,
  call_timestamp) (requires cls_db.py v2.49) and passes it into
  log_call_recording() so lead_detail.html can render it. No match
  found -> direction=None, same as any historical row; never blocks
  the upload. Only wired into the fresh-upload branch, not the
  recovering-missing-file branch (update_call_recording_file() is
  unchanged, out of scope for this fix).
v0.39 (2026-08-07) — token_required now logs WHY a bearer-token 401
  happens (crm_app_log.txt), via cls_db.diagnose_api_token_failure()
  (requires cls_db.py v2.48). Found while investigating Elohar/
  Devender's morning 401s: rejections left zero trace before this.
  Additive only, no auth behavior change — every existing accept/
  reject decision in token_required is unchanged, this only adds a
  log line on each of the two reject paths.
v0.38 (2026-08-07) — Telephony token architecture change (Option C,
  self-service "Sync my token"; requires cls_db.py v2.47). Replaces
  manual admin token generation + voice-relay, which failed twice in
  one morning (a re-regenerated token silently invalidated the one an
  employee had just been given; a token accidentally pasted into the
  wrong settings field). NEW POST /api/my-token (api_my_token(),
  @login_required — session-cookie auth, NOT @token_required): returns
  ONLY the calling session's own user_id's token, never accepts a
  user_id param. Raw tokens are never stored anywhere (cls_db.
  verify_api_token() only ever sees a SHA-256 hash) so there is no
  "return the existing token" — every call mints a FRESH one via the
  existing, unmodified cls_db.generate_api_token(), deliberately POST
  (not GET) so no prefetch/proxy/cache layer can trigger it without a
  real user tap behind it. Intended to be called by the app's new
  "Sync my token" button (android_pilot SettingsActivity.kt) only,
  never automatically/on a timer — each call invalidates whatever
  token is currently active for that user on any other device, same
  pre-existing limitation the old admin-regenerate flow already had.
  settings_telephony_generate_token() RENAMED to
  settings_telephony_revoke_token(), route changed from POST
  /settings/telephony/token/<user_id> to POST /settings/telephony/
  token/<user_id>/revoke, and its body changed from generating a new
  token to calling the new cls_db.revoke_api_token(user_id) — an admin
  kill-switch (lost phone / departing employee) that deactivates
  without minting a replacement, so there's no new raw value to relay
  by hand; the employee's own next "Sync my token" tap mints their
  own. Same permission check as before (unchanged). settings_telephony.
  html updated to match (button relabeled "Revoke Token", confirm()
  text reworded, "View Synced Recordings" link restyled as a button).
  user_recording_paths.recording_folder_path is UNCHANGED — confirmed
  load-bearing (MainActivity.kt's findRecordingFileNear() uses it to
  scope MediaStore candidate search), left in place, not touched.
v0.37 (2026-08-06) — APX Attendance Chunk C: admin "who's present
  today" view + proactive exemption (requires cls_db.py v2.46). NEW
  settings_attendance_today() (/settings/attendance/today, GET,
  @admin_required — deliberately NOT the looser can_view_all_leads()
  gate the Dashboard/Export pair uses) renders a new template listing
  every active employee's actual status for today. NEW
  settings_attendance_exempt() (/settings/attendance/exempt, POST,
  @admin_required) backs a new form section added to the BOTTOM of
  settings_attendance_corrections.html — the existing pending-queue/
  history sections there are unchanged. settings_attendance_
  corrections() now also passes employees/correction_fields/
  attendance_statuses into that template for the new form's dropdowns
  (additive context only, existing template variables untouched).
  Also: attendance.html now hides Punch In/Out, the Weekoff/Leave
  button, and the "Today" status badge for role=='admin' specifically
  (checked literally, NOT via OVERSIGHT_ROLES/can_view_all_leads, so
  manager is completely unaffected and still punches normally) —
  admin instead sees a link to the new Who's-Present-Today page plus
  a pointer into Settings > Attendance. Holidays, Dashboard, Export,
  and the existing reactive Correction Request approve/reject flow
  are all UNCHANGED — only added to, never modified.

v0.36 (2026-08-06) — APX Attendance Chunk B: Weekoff/Leave rebuilt as
  range-capable, duplicate-protected self-service (requires cls_db.py
  v2.45 — see its changelog for the validate-then-write design). NEW
  attendance_weekoff_submit() / attendance_leave_submit() JSON routes
  (/attendance/weekoff/submit, /attendance/leave/submit) back a new
  button+modal in attendance.html; both @login_required, user_id
  always pulled from session, never from request input. The OLD
  attendance_weekoff/attendance_leave form-POST routes are PAUSED
  (commented out, not deleted) — left live they'd let a submission
  bypass the new duplicate-protection. attendance.html also: removed
  the old inline Weekoff/Leave card and the employee-facing Correction
  Request card (front-end only — attendance_correction_request() route
  and the admin-side Corrections queue are untouched), and restyled
  the login submit button + logout link to a new scoped
  .btn-pill-green class (base.html/login.html) — existing .btn/
  .btn-primary/.drawer-link defaults used everywhere else in the app
  are unchanged.

v0.35 (2026-08-06) — APX Attendance Chunk A: photo compression + map
  overlay. PunchActivity.kt (client) no longer draws its own text
  watermark — it now only resizes/compresses the raw selfie before
  upload. api_attendance_punch_in()/api_attendance_punch_out() no
  longer call `uploaded.save(path)` directly; both now read the raw
  bytes and pass them through the new cls_attendance_photo.
  render_punch_photo(bytes, lat, lng, ts) before writing to disk. That
  function tries a Google Static Maps pin thumbnail + coordinates/
  date-time text composite, falls back to the old plain-text overlay
  style on any failure, and falls back to the untouched original photo
  if even that fails — a punch can never fail over an image problem.
  New OS env var CLS_MAPS_API_KEY (same "real env var, never .env"
  convention as CLS_DB_PATH), new dependency Pillow (requirements.txt).
  No schema change — cls_db.record_punch() already only ever stored
  the photo filename, never bytes.

v0.34 (2026-08-04) — PWA WhatsApp deep-link bug fix. "Open WhatsApp"
  buttons worked in browser but failed in the installed PWA with
  net::ERR_UNKNOWN_URL_SCHEME on whatsapp://send/.... Root cause: the
  buttons were <form method=post> submits that got server-redirected
  (302) to https://wa.me/..., which itself redirects to whatsapp://...
  — that redirect chain loses user-gesture status in standalone PWA
  mode, so the OS blocked the custom URL scheme. Fix moves the actual
  navigation to a plain <a href="https://wa.me/..."> in the templates
  (a direct, un-intercepted top-level user gesture); this route pair
  now only logs the send.
  - whatsapp_send(): same ownership gate and wa_url validation as
    before (now abort(400) instead of flash+redirect on invalid
    wa_url, since the caller is a background fetch, not a page nav);
    still calls cls_db.log_whatsapp_sent(); dropped `return
    redirect(wa_url)` in favor of `return "", 204`.
  - reminder_mark_sent(): same change, same reasoning; still calls
    cls_db.log_reminder_sent().
  - Confirmed via grep: whatsapp_picker.html and reminders_tomorrow.html
    are the only callers of url_for('whatsapp_send'/'reminder_mark_sent')
    in live code (crm/templates/) — both updated in this same change to
    call these routes via fetch() and navigate independently via <a
    href>, so no caller is left depending on the old redirect. No
    schema change, no migration.

v0.33 (2026-08-04) — Leads List Pipeline Stage filter, radio -> checkbox
  multi-select. Requires cls_db.py v2.44. Reuses the SAME stages= list
  infrastructure _build_lead_filter_where() already supports for Bulk
  Reassign/Export (cls_db.py v2.30) — no duplicated filter logic.
  - _parse_lead_filters() gained "stages": request.args.getlist("stages")
    alongside the existing single-value "stage" key (kept, unchanged —
    still back-filled for any other reader, though leads_list() itself
    now reads f["stages"] for the actual query).
  - leads_list() now passes stages=f["stages"] or None to cls_db.
    get_leads_page(), instead of stage=f["stage"].
  - leads_filter.html: Pipeline Stage section changed from radio
    name="stage" to checkbox name="stages" — mirrors bulk_reassign_
    filter.html's existing Pipeline Stage checkbox block exactly.
  - leads_search.html: the single hidden carry-forward
    <input name="stage"> replaced with a loop over filters.stages, same
    pattern already used for configuration/property_type/facing; its
    "Clear search" link's stage=filters.stage query param likewise
    swapped to stages=filters.stages.
  - _leads_list_actionbar.html: the Filter/Search breadcrumb links'
    stage=filters.stage query param swapped to stages=filters.stages
    (2 call sites) — carries the now-list filter forward correctly
    instead of silently dropping it.
  - leads_list.html: the "Filters active" banner condition now checks
    filters.stages instead of filters.stage.
  Purely additive at the query layer — no schema migration. filters.stage
  (singular) is left in the dict for backward compatibility with any old
  bookmarked URL still carrying ?stage=Prospect, but the actual filtering
  now happens via filters.stages.

v0.32 (2026-08) — BASE_DIR updated from C:\CLS to D:\CLS — drive migration, 2026-08.

v0.31 (2026-08-02) — Pre-Step-6 fix: ATTENDANCE_PHOTOS_DIR parameterized
  via CLS_ATTENDANCE_PHOTOS_DIR (a real OS env var, same convention as
  cls_db.py's CLS_DB_PATH), defaulting to the same C:\\CLS\\
  attendance_photos path as before if unset. Closes a real test-
  isolation gap: last session's Step 4 test script had no way to
  redirect photo writes the way CLS_DB_PATH already redirects the
  database, and leaked 6 fake test photos into the live directory
  (caught and cleaned up, not left in place). Also corrected
  RECORDINGS_DIR's now-stale comment (said "excluded from cls_backup.py
  sync" — that exclusion was reversed in cls_backup.py v1.3). No route
  or behavior change — same default path, same directory structure.

v0.30 (2026-08-02) — APX Attendance v0.9 pilot: two items.

  1. Geofence-breach color backport (template-only, no schema/route
     change): attendance.html's personal mini-calendar (Step 2) used a
     RED border for a geofence breach; the Step 3 Dashboard specified
     ORANGE (#FF8C00). Backported so both calendar views match — same
     color, same 2px border width, in both the cell style and the
     legend swatch.

  2. Build Order Step 4 — token-auth /api/attendance/* endpoints,
     against cls_db.py v2.42. NEW ATTENDANCE_PHOTOS_DIR (C:\\CLS\\
     attendance_photos), same reasoning/DPDP flag as RECORDINGS_DIR.
     @token_required / g.telephony_user REUSED EXACTLY — one bearer
     token per user already gates Telephony, now also gates these 4
     (see cls_db.py v2.42's corrected user_api_tokens comment) — no
     second auth scheme.
     - POST /api/attendance/punch-in: multipart photo+lat+lng+
       client_ts. Computes geofence breach (flagged, NEVER blocks —
       see cls_db.check_geofence_breach()) and late/present status +
       minutes (cls_db.compute_punch_in_timing()), saves the photo,
       upserts the attendance row (cls_db.record_punch()).
     - POST /api/attendance/punch-out: same request shape, writes only
       logout_* columns.
     - POST /api/attendance/location-ping: JSON {lat,lng,ts}. Silently
       no-ops unless the user has an OPEN attendance row today
       (cls_db.record_location_ping()).
     - POST /api/attendance/register-fcm-token: JSON {fcm_token},
       stores via cls_db.set_fcm_token(). Does NOT send any push —
       that's the separate, later FCM-wiring step.
     No native Android code yet (PunchActivity.kt/AttendanceWorker.kt
     are Steps 5/6) — verified with a Flask-test-client script standing
     in for curl/Postman, against a throwaway copy of CLS1.db.

v0.29 (2026-08-02) — APX Attendance v0.9 pilot: admin Dashboard (Build
  Order Step 3 of the v0.9 spec), against cls_db.py v2.40 (audit
  column)/v2.41 (dashboard data function).
  - NEW GET /settings/attendance/dashboard: monthly calendar (green=
    present, amber=late, red=absent, grey=weekoff, blue=leave, ORANGE
    border=geofence breach) + totals row, month/year picker, employee
    filter. NOT @admin_required — gated the same way every other
    dashboard/report in this app is (cls_db.can_view_all_leads), since
    a salesperson needs their own-scoped view here too; their ?user_id
    is always ignored server-side and force-replaced with their own id
    (_resolve_attendance_dashboard_scope()), never trusted from the
    query string.
  - NEW GET /settings/attendance/dashboard/export.xlsx: reuses
    cls_reports.export_to_excel() (the EXISTING Reports export engine)
    against a report-shaped dict built by the new
    _attendance_dashboard_report() helper — no new export engine
    written. PDF is the same browser-print-to-PDF convention
    report_view.html already uses (a <style media="print"> block +
    window.print()) — no PDF library, matching cls_reports.py's own
    documented "PDF export is still NOT implemented here" call.
  - View and export share _parse_dashboard_month_args()/
    _resolve_attendance_dashboard_scope() so the exported file can
    never drift from what's on screen.
  - Linked from settings_attendance.html (admin hub tile) and from
    attendance.html (a new "View My Calendar & Export" link, so a
    salesperson can actually reach their own-scoped dashboard — it
    isn't @admin_required, but there was previously no navigable link
    to it for a non-admin).
  - Verified via a Flask-test-client script against a throwaway copy
    of CLS1.db with several fake users and multiple weeks of varied
    attendance data (present/late/absent/weekoff/leave, some with
    geofence breaches) — never CLS1.db/CLS2.db directly.

v0.28 (2026-08-02) — APX Attendance v0.9 pilot: Flask/Jinja2 routes only
  (Build Order Step 2 of the v0.9 spec), against cls_db.py v2.38/2.39's
  schema + data-access functions. SIBLING module — no leads/activity_log/
  assignments route touched. No /api/attendance/* token-auth endpoints
  yet (Step 4); no dashboard/calendar-with-colors/export screen yet
  (Step 3).
  - NEW GET /attendance: employee page — today's status, a
    calendar.monthcalendar mini calendar for the current month (?year=/
    ?month= to navigate), Login/Logout/Weekoff/Leave/Correction Request.
    Login/Logout are feature-detected calls to window.AndroidBridge.
    punchIn()/punchOut() (same onclick-feature-detect pattern as
    settings.html v0.20's openDeviceSyncSettings()) — falls back to a
    "use the mobile app" message since no native camera code exists yet.
    NOTE: android_pilot's CURRENT AndroidBridge (v9) doesn't have
    punchIn/punchOut either, so the fallback message is what shows even
    inside the native app's WebView today — expected until a later
    Android build-order step ships those two bridge methods.
  - NEW POST /attendance/weekoff, /attendance/leave: plain form submits
    to cls_db.set_self_service_attendance_status().
  - NEW POST /attendance/correction-request: plain form submit to
    cls_db.create_correction_request().
  - NEW GET /settings/attendance: admin hub, same card-grid pattern as
    settings.html.
  - NEW GET/POST /settings/attendance/holidays (+ its /delete route),
    /settings/attendance/corrections (approve/reject queue, one route
    handling both actions via a hidden 'action' field, same idiom as
    settings_users()'s toggle-active), /settings/attendance/projects
    (lat/long/radius per project bucket, sourced from
    cls_db.get_all_bucket_names()) — all @admin_required.
  - NEW POST /settings/users/<id>/assign-project: sets
    users.assigned_project from a small per-row addition to the
    EXISTING settings_users.html (Team) screen, rather than a new "edit
    user" screen — touches one existing template instead of adding one,
    per the spec's explicit "fewer templates" call. settings_users()
    now also passes projects=cls_db.get_all_bucket_names() for that
    dropdown.
  - Verified via a Flask-test-client script against a throwaway temp
    SQLite DB with fake users/attendance rows (never CLS1.db/CLS2.db),
    covering employee routes, all 3 admin sub-screens, admin-vs-
    salesperson role gating, and the correction approve/reject flow.

v0.27 (2026-08-01) — Five-item batch: Pipeline date-range tile, self-scoped
  Telephony access, Synced Recordings filter/UI polish.

  1. dashboard_pipeline(): NEW date-range parsing (reuses this file's own
     DATE_PRESETS/DATE_PRESET_ORDER/DATE_PRESET_LABELS, same 4-branch
     resolution style as _parse_recordings_filters()), feeding NEW
     cls_db.get_leads_created_in_range() for the "Total Leads" tile only.
     Default preset is "today" ONLY when the route has no query string at
     all, preserving the old default. Stage tiles (get_stage_snapshot_counts)
     are UNTOUCHED — still a live snapshot regardless of the picker.

  2. Self-scoped Telephony access for all logged-in users, same
     cls_db.can_view_all_leads(role) gate used everywhere else (leads_list()
     etc.) — oversight roles (admin, manager) unchanged/company-wide; a
     salesperson now reaches these routes too but scoped to themselves only:
       - settings_telephony(): @admin_required REMOVED (now @login_required
         only). Non-oversight logins get `users` filtered to their own row;
         POST only ever writes their own path_<user_id> field regardless of
         what else is in the submitted form.
       - settings_telephony_generate_token(): @admin_required REMOVED (now
         @login_required only). NEW explicit guard: a non-oversight login
         gets abort(403) if the URL's user_id isn't their own — they may
         only ever regenerate their own token.
       - settings_telephony_recordings(): @admin_required REMOVED (now
         @login_required only). Non-oversight logins are force-scoped to
         their own owner_match_name server-side — same fails-closed
         convention as leads_list()'s owner gate, a salesperson's own
         ?lead_owner= query param is never trusted. NEW company_wide flag
         passed to the template so it can hide the now-redundant Lead
         owner/Activity owner filter dropdowns for that role.
       - settings_telephony_recording_delete(): UNCHANGED, still
         @admin_required — defense in depth, the Delete button is now also
         hidden client-side in the template for non-admins (settings.html
         v0.21 also adds a role-agnostic "My Telephony Settings" tile
         pointing at the same settings_telephony route).

  3/4/5. No app.py change needed — settings_telephony_recordings.html v3
     handles the filter-row grid layout, admin-only Delete button, and the
     clickable Lead #/wider audio player entirely at the template level.

  Verified via a Flask-test-client script against a throwaway temp SQLite
  DB (never CLS1.db) — 32/32 checks passed, covering: date-range default/
  maximum/custom Total Leads counts; admin vs. salesperson scoping on all
  three telephony routes; the query-string lead_owner override being
  ignored for a salesperson; the token-generation 403 guard; and the
  delete endpoint still 403ing a salesperson directly.

v0.26 (2026-08-01) — /settings gate loosened + user-facing "APX" removed.

  /settings: @admin_required REMOVED from the route (still @login_required)
  — the page itself is reachable by any logged-in user now. Every EXISTING
  tile is still admin-only, just gated at the template level instead of
  the route level (see settings.html v0.20's own changelog) — verified
  against a plain salesperson-role test login: sees Settings, sees ONLY
  the new Device Sync section, none of the 10 existing admin tiles.
  Every settings/* SUB-route (settings_projects, settings_users,
  settings_telephony, etc.) is UNCHANGED — still @admin_required at the
  route level, so direct-URL access by a non-admin is still blocked
  exactly as before; only the hub page's own gate and tile visibility
  changed.

  login.html: heading changed from literal "APX" to "Asian Properties
  CRM" — the only genuine user-facing "APX" occurrence found in a
  repo-wide search of crm/ (every other hit was inside a Python/Jinja/JS
  comment, e.g. this file's own top banner two lines above, left
  untouched as internal project terminology, not a rename).

v0.25 (2026-08-01) — android_pilot APK distribution. Additive only, no
  cls_db.py change (pure file I/O, no SQLite involved).

  New POST /api/apk/upload (CI-only, X-Upload-Secret header checked via
  hmac.compare_digest against CLS_APK_UPLOAD_SECRET — a real OS env var,
  same never-hardcoded/never-in-.env convention as cls_db.py's
  CLS_DB_PATH, NOT this file's own _env/dotenv dict). Always overwrites
  apk_releases/clspilot-latest.apk so the public link never changes.
  Logs one line per upload to apk_upload_log.txt (its own file, not
  job_results.txt — that one's for the A-D pipeline only) so Srikanth
  can confirm a new build landed without opening GitHub.

  New GET /download/clspilot.apk (public, no @login_required — has to
  work for a team member who isn't a CRM user yet on that phone).
  Flagged and confirmed with Srikanth before building: gated by a
  DIFFERENT secret (?key=..., CLS_APK_DOWNLOAD_SECRET) than the upload
  endpoint uses — sharing one secret for both would have meant a leaked
  download link also grants the ability to push a malicious build, not
  just read the APK. Both secrets fail closed if unset (empty string
  never matches). Serves with the correct APK mimetype
  (application/vnd.android.package-archive) and a friendly plain-text
  message instead of a raw 404 if nothing's been uploaded yet.

  New import: hmac (stdlib, no new dependency).

v0.24 (2026-08-01) — New admin Settings > Telephony > Synced Recordings
  page. Requires cls_db.py v2.36. Additive only.

  New /settings/telephony/recordings (@login_required + @admin_required,
  same gate as /settings/telephony): filtered/paginated table of every
  call_recording activity_log row. Date-preset filter reuses app.py's
  own DATE_PRESETS dict (same convention _parse_bulk_filters() already
  established: copy the 4-branch resolution logic, don't share a helper,
  don't pull in cls_reports.py's separate copy). Call Status/Lead Owner/
  Activity Owner/search filters call the new cls_db.list_call_recordings().
  actor->display-name resolution done in the route via cls_db.
  get_all_users() (email->full_name dict), matching how lead_detail.html's
  timeline already resolves activity_log.actor — no SQL JOIN for this,
  by established convention. Each row also gets a file_exists flag (same
  os.path.exists() check cls_call_recording_audit.py already does) so an
  admin can see at a glance whether a recording actually plays, given the
  2026-07-31 file-loss incident.

  New /settings/telephony/recordings/<id>/delete (POST, same gate): calls
  cls_db.delete_call_recording_activity() UNCHANGED (the same function
  cls_call_recording_audit.py already uses — nothing duplicated/moved),
  and additionally removes the underlying file if the row had one. A web
  "Delete" click is a single deliberate action after visually reviewing
  the row on-screen, so — unlike the CLI audit tool's careful separate
  --delete-file flag for incident-response review — this always removes
  both together, with the confirm() text saying so explicitly.

  settings_telephony.html gets one new "View Synced Recordings ->" link.

  Row actions are plain inline buttons (View Lead + Delete), not a new
  dropdown/kebab component — confirmed with Srikanth: nothing like that
  exists anywhere in this codebase, and every existing per-row action
  here (settings_users.html's Deactivate, settings_projects.html's
  delete) is 1-3 small buttons. "View Activity Detail" as a separate
  action was dropped — the table row already shows every field a detail
  view would.

v0.23 (2026-07-31) — Bug 2 fix CORRECTED: recover missing recording files
  instead of permanently blocking re-sync. Requires cls_db.py v2.35.

  Separately, unrelated ops mistake this same day: the call_recordings/
  folder was accidentally deleted from disk while testing (files only —
  no activity_log rows were touched). v0.22's row-exists-only duplicate
  check would have permanently blocked recovering those legitimate
  recordings via re-sync, since an existing row always looks like
  "already logged" regardless of whether its file still exists.

  api_telephony_upload_recording() now calls cls_db.get_call_recording_
  file_path(lead_id, call_timestamp) instead of the old call_recording_
  exists() boolean, and checks os.path.exists() on that path under
  RECORDINGS_DIR: row+file both present -> genuine duplicate, skip as
  before; row present but file missing -> recovery — falls through to
  save the new file and calls cls_db.update_call_recording_file()
  (UPDATE in place) instead of cls_db.log_call_recording() (INSERT), so
  a recovered file never creates a second row for the same real call.
  No row present at all -> normal first-time path, unchanged.

v0.22 (2026-07-31) — Bug 2 fix: duplicate call recordings on repeat sync.
  Requires cls_db.py v2.34. api_telephony_upload_recording() now calls
  cls_db.call_recording_exists(lead_id, call_timestamp) immediately after
  validating the lead, BEFORE any file write — a duplicate returns
  {"success": true, "message": "...duplicate upload skipped."} without
  touching disk or activity_log a second time. Confirmed real: seen
  during Srikanth's own repeat-sync test. No other route logic changed.
  SUPERSEDED by v0.23 above the same day — see that entry.

v0.21 (2026-07-31) — Phase B Telephony: server-side call-recording
  matching backend. Requires cls_db.py v2.33. Additions only.

  Admin Settings > Telephony (new): per-user recording-folder path
  config (settings_telephony, one form/one Save button, following
  settings_lead_scoring.html's pattern) + per-user bearer-token
  generation (settings_telephony_generate_token, a deliberately
  separate small form so saving paths can never accidentally
  regenerate a token). Gated @login_required + @admin_required, same
  as every other Settings route — NOT can_write_any_lead, which is a
  different lead-scoped gate.

  New token_required decorator + 2 new /api/telephony/* endpoints
  (report-calls, upload-recording) — the FIRST token-based auth and
  FIRST /api/* JSON routes in this file, entirely independent of the
  session-cookie login (no `session` access at all in token_required).
  jsonify/g added to the flask import; secure_filename added from
  werkzeug.utils (first file-upload handling in this file).
  RECORDINGS_DIR = C:\\CLS\\call_recordings — new, intentionally
  excluded from cls_backup.py's rclone sync (see that file's v1.2
  changelog) pending DPDP consent-notice design.

  New /recordings/<lead_id>/<filename> route for the <audio> player in
  lead_detail.html's timeline — @login_required (not @token_required,
  this is for browser/WebView playback by a logged-in human), gated by
  the same READ condition lead_detail() itself uses to decide whether
  the timeline is shown (can_write OR can_view_all_leads) — NOT
  _check_lead_ownership, which is the stricter WRITE-only gate and
  would incorrectly 403 an oversight viewer.

  Does not touch android_pilot/ — the app-side code that calls these
  new endpoints is a follow-up, out of scope for this change.

v0.20 (2026-07-29) — Dashboard owner-scoping fix + "Leads to Booking
  Summary" tab. Requires cls_db.py v2.31.

  Part A bug fix — dashboard()'s 4 stat cards (New Enquiries, Reengaged,
  Missed Followups, Missed Site Visits) were showing company-wide
  numbers to every login, salesperson included; only dashboard_today()
  and dashboard_pipeline() were already correctly owner-scoped. Root
  cause: cls_db.get_new_enquiries_count()/get_reengaged_count()/
  get_due_by_kind() had no owner param at all (see cls_db.py v2.31).
  Fixed by computing scope_owner the SAME way dashboard_today() already
  does (company_wide = cls_db.can_view_all_leads(user["role"]);
  scope_owner = None if company_wide else user["owner_match_name"]) and
  passing owner=scope_owner into all 4 calls. Uses owner_match_name, NOT
  email — lead_owner is matched against owner_match_name everywhere else
  in this file (leads_list(), dashboard_today() is the one exception,
  because activity_log.actor stores email, a different column).

  Also fixed the 3 drill-down routes behind those cards — due_list(),
  reengaged_list(), new_enquiries_list() — which showed ALL leads to
  ALL logins regardless of the (now-fixed) card count above them. Same
  scope_owner gate applied. This closes the same class of visibility
  gap /leads and /leads/<id> were already closed against in v0.1.4;
  these 3 routes were missed at the time.

  pending_reminder_count verified unchanged — inject_current_user()
  already scopes it correctly via get_pending_reminder_count(owner_
  match_name) when role=='salesperson'.

  Part B/C — NEW top tab bar on /dashboard ("Stats Overview" / "Leads to
  Booking Summary"), replacing the old plain <h2>Stats</h2>. Existing
  bottom tab bar (Stats/Today/Pipeline, _dashboard_tabbar.html)
  UNCHANGED. NEW route dashboard_booking_summary() (GET /dashboard/
  booking-summary) — read-only report page, filter bar (Project/Source/
  Sales Person/Date range) + Quick Summary cards + Leads/Site Visits/
  Bookings sub-tabs, built on the new cls_db.py v2.31 period-scoped
  query functions. Sales Person filter is force-locked to the logged-in
  salesperson's own owner_match_name (dropdown hidden), same enforcement
  as /leads — cls_db is the only place that can be trusted to apply
  this, so the route computes scope_owner the same way as Part A above
  and a salesperson's ?owner= query param is ignored, never trusted.
  Date range reuses cls_reports.REPORT_DATE_PRESETS/ORDER/LABELS (11-
  option quick-select, same Mon-Sun convention as cls_reports.py),
  resolved locally in _resolve_booking_summary_date_range() rather than
  cls_reports.resolve_date_range() (that one is keyed to a report_id in
  REPORTS_BY_ID — this page isn't one of the 12 reports). Default range:
  this_month.

  "Value (INR)" ships as "—" (Decision 1, deferred) — no schema change
  this round; leads.booking_value does not exist yet. "Bookings" is
  EVENT-based (Decision 3): activity_log rows where activity_type=
  'stage_change' AND new_value='Booked', within the date range — not
  current_stage='Booked' — consistent with every other card here being
  period-bound by created/scheduled/event date, and avoiding double/
  zero-counting a lead that unwinds and rebooks. Site-visit status
  breakdown (Decision 4) maps our 4-value status enum (scheduled/
  conducted/cancelled/no_show) to Conducted/Cancelled/Didn't Visit/
  Scheduled/Missed — no "Pending"/"Dropped" rows (we have no equivalent
  state). Project/Source breakdowns (Decision 2) are labeled "Lead By
  Project"/"Lead By Source" (not "Interested Project(s)/Source(s)") —
  ours are single-value columns, not Sell.do's multi-select.

v0.19 (2026-07) — Bulk Reassign Filter UX Rework, same treatment as
  v0.18's Export rework. NO cls_db.py change — confirmed the stages=/
  owners= list params get_leads_matching() needs already existed from
  the Export session; this is pure reuse.

  Verified live state before editing, per standing rule: Campaign was
  ALREADY a checkbox multi-select (approved in Task 3's original
  design). Project was a radio (unchanged — not asked to convert).
  Stage and the FILTER-by-owner field ("Current Owner", inside the
  filter accordion) were both radios. The REASSIGN-TO-OWNER field
  ("Reassign matched leads to", a plain <select name="to_owner"> in
  its own card OUTSIDE the accordion) is unambiguously a different
  field — confirmed, not touched, still single-select (you cannot bulk-
  reassign to multiple destinations in one job).

  Task 1 — search box added above Campaign, Project, and (now-checkbox)
  Current Owner in bulk_reassign_filter.html. Reuses the EXACT
  filterOptRows() Export already had rather than a second copy — pulled
  up into base.html v0.15 (loaded on every page) and removed from
  export_leads.html/export_site_visits.html's own <script> blocks.

  Task 2 — Pipeline Stage and Current Owner (the FILTER) changed from
  radio to checkbox: bulk_reassign_filter.html now submits stages=/
  owners= (lists) instead of stage=/owner= (single). _bulk_reassign_
  matched() updated to pass stages=/owners= to cls_db.get_leads_
  matching(). _parse_bulk_filters() already returned both the old
  single-value and new list-style keys (from the Export session) — no
  change needed there, confirmed it still serves both Bulk Reassign and
  Export correctly (Export continues submitting stages=/owners=, Bulk
  Reassign now does too; neither ever submits the other's now-unused
  single-value stage=/owner=, but both keys stay in the dict for any
  future caller).

  Task 3 — _bulk_filters_summary() reworked to join multi-select
  categories with " | " (was ", ", which would run "Stage: A, B" and
  "Campaign: C, D" together unreadably once both can hold multiple
  values) and gained a to_owner param so it FIXES a real gap: the
  destination owner was never actually appended to the stored string
  before (despite this function's own original docstring describing
  that format) — bulk_jobs.to_owner is a separate column that
  settings_bulk_jobs.html never displays, so the destination was
  silently invisible in the history table until now.

  Task 4 — no route logic change needed: settings_bulk_reassign_preview()
  and _commit() already call the same _bulk_reassign_matched(f), so
  both automatically reflect Task 2's stages=/owners= once that
  function was updated. bulk_reassign_preview.html's confirm form
  updated to resubmit stages=/owners= as per-value hidden fields (same
  loop pattern as campaigns=) instead of single stage=/owner= fields —
  to_owner's single hidden field is untouched.

v0.18 (2026-07) — Export rework. Requires cls_db.py v2.30. SCOPE
  REVERSAL, confirmed explicitly by Srikanth: Bulk Export was built
  (v0.17) role-agnostic/self-scoped like Reports — now admin-only,
  nested under Settings. Salespeople lose access to Export entirely;
  intentional, not a regression.

  Task A — moved from /export/... + export_* function names to
  /settings/export/... + settings_export_* (my call, for consistency
  with every other admin-only Settings feature — settings_bulk_reassign,
  settings_projects, settings_campaign_routing, settings_users, all
  under the settings_ prefix; not explicitly specified, flagged). All
  10 routes (hub + 3 types x view/excel/email) gained @admin_required
  (same decorator as Bulk Reassign — narrower than can_view_all_leads()/
  WRITE_ANYWHERE_ROLES, which are a different, broader gate). Dropped
  the can_view_all_leads()-based "force to own leads" branching from
  every report-builder helper — no non-admin caller left to scope for.
  base.html's standalone "Export" drawer link REMOVED; settings.html
  gained an "Export" tile instead.

  Task B — Campaign, Project (Export Leads only — the only screen with
  those fields) and Owner (Leads + Site Visits — Activity has no Owner
  filter) checkbox/radio lists gained a plain-text search box above
  them. Vanilla JS (filterOptRows()): filters visible .opt-row labels
  by textContent match, live, per-section-scoped so multiple search
  boxes on one page never cross-filter each other. Never touches
  checked/selected state — search only changes visibility. No new JS
  library.

  Task C — Stage and Owner (Export Leads + Site Visits — Activity has
  neither field, untouched) changed from radio (single-value) to
  checkbox (multi-select), reading NEW filters.stages/filters.owners
  (lists) instead of filters.stage/filters.owner. Backed by cls_db.py
  v2.30's new stages=/owners= list params on _build_lead_filter_where()/
  get_leads_matching()/get_site_visits_conducted() — purely additive,
  Export-only; Bulk Reassign's own filter form is untouched (still
  single-value stage/owner radios). _parse_bulk_filters() (shared by
  both features) gained stages/owners keys alongside the existing
  stage/owner keys.

  Task D — each export type is now TWO GET routes sharing ONE template
  via a new show_results flag: _view (filter form only, NO query run,
  no row count) and _results (reached by submitting that form — the
  report is computed, Excel/PDF/Email actions appear). Mirrors Bulk
  Reassign's filter -> preview split: nothing renders until an explicit
  Apply. Export mechanics (Excel/PDF/email) themselves are unchanged —
  only when they become visible/reachable changed.

  FLAGGED, not built: export_activity.html has no Campaign/Project/
  Stage/Owner filter today (just date range + an optional single
  cls_id) — Tasks B and C have nothing to touch there. Not adding those
  fields since it wasn't asked for.

v0.17 (July 2026) — APX v0.7 batch: Newest-First Default (Task 1) +
  Complete Activity History (Task 2) + Bulk Reassign (Task 3) + Bulk
  Export (Task 4) + Lead Age (Task 5). Requires cls_db.py v2.28.
  ADDITIONS ONLY except the one default-value change in Task 1.

  Task 1 — _parse_lead_filters()'s sort_by fallback changed from
  "recent" to "created_desc" (one line). leads_filter.html needed NO
  change — its Sort By radios already key off filters.sort_by, so the
  new default just flows through.

  Task 2.2 — WhatsApp send logging. whatsapp_picker.html's Send button
  was client-side-only (window.open, no server round-trip, nothing
  logged) — now a real <form method="post"> to NEW
  /leads/<cls_id>/whatsapp/send (whatsapp_send()), same ownership gate
  and same wa_url-must-start-with-https://wa.me/ validation as the
  existing reminder_mark_sent() pattern it mirrors. Logs via NEW
  cls_db.log_whatsapp_sent(), then 302-redirects into WhatsApp exactly
  as before.

  Task 3 — Bulk Reassign (Settings > Bulk Reassign, admin_required
  only — NOT WRITE_ANYWHERE_ROLES/managers, deliberately stricter than
  normal lead-write access since this is destructive at scale). Three
  steps: NEW settings_bulk_reassign() (GET filter form) ->
  settings_bulk_reassign_preview() (GET, shows matched count + target
  owner, writes nothing) -> settings_bulk_reassign_commit() (POST, the
  only step that writes, via cls_db.bulk_reassign_leads()'s one
  transaction). NEW settings_bulk_jobs() (history page). NEW
  bulk_reassign_filter.html / bulk_reassign_preview.html /
  settings_bulk_jobs.html. settings.html gained a "Bulk Reassign" tile.
  NEW _parse_bulk_filters() / _bulk_filters_summary() helpers (shared
  with Task 4 below) — a smaller, separate filter parser from
  _parse_lead_filters(), since Bulk Reassign/Export only ever offer
  date range, campaign (multi-select), project, stage, source, current
  owner — not the full leads-list filter set.

  Task 4 — Bulk Export (NEW top-level "Export" nav link in base.html,
  visible to everyone — same role-agnostic-in-template pattern as
  "Reports", scoped internally via cls_db.can_view_all_leads() exactly
  like Reports: salesperson exports only their own leads/visits/
  activity, admin/manager export everything). Three export types, each
  view+excel+email route trio: export_leads_view/_excel/_email,
  export_site_visits_view/_excel/_email, export_activity_view/_excel/
  _email, plus NEW export_home() hub. Reuses cls_reports.
  export_to_excel() unchanged (same {title,columns,rows,date_from,
  date_to} shape Reports already builds) — no new export mechanism.
  PDF is browser print-to-PDF, same <style media="print"> + "Print /
  Save as PDF" pattern as report_view.html — no server-side PDF
  library. Email is NEW _send_export_email() — same Brevo
  (sib_api_v3_sdk) transactional client cls_email_drip.py/
  cls_watchdog.py already use, same BREVO_API_KEY from .env; sender
  reuses sales1@asianbuild.in (cls_watchdog.py's own precedent for
  internal/system mail) under a new "Asian Properties CRM" display
  name rather than a customer-facing project brand. Sends only to the
  REQUESTING user's own login email. Date range reuses this file's
  EXISTING DATE_PRESETS/DATE_PRESET_LABELS/DATE_PRESET_ORDER (same
  dict leads_filter.html already uses) rather than cls_reports.py's
  separate REPORT_DATE_PRESETS — Srikanth's approved call, avoids a
  third near-identical date-preset dict.

  Task 5 — no app.py change; get_leads_page() already returns age_days
  per lead (cls_db.py v2.28), leads_list.html reads it directly.

v0.16 (July 2026) — Settings > Lead Scoring (Task 4 of the settings-GUI
  batch, final task). Requires cls_db.py v2.26. NEW combined GET/POST
  route settings_lead_scoring() + settings_lead_scoring.html. Only
  changes WHERE the scoring rules come from (DB via cls_db.
  get_lead_score_config()/set_lead_score_config() instead of a
  hardcoded dict) — compute_lead_scores() itself, and its existing call
  sites in leads_list()/lead_detail(), are untouched. settings.html
  gained a "Lead Scoring" tile.

v0.15 (July 2026) — Settings > Campaign Routing (Task 3 of the
  settings-GUI batch). Requires cls_db.py v2.25. NEW routes:
  settings_campaign_routing() (GET), settings_campaign_routing_fallback()
  (POST — fallback owner), settings_campaign_routing_save() (POST —
  add/edit a rule), settings_campaign_routing_toggle() (POST — active
  flip), settings_campaign_routing_delete() (POST). NEW
  settings_campaign_routing.html. settings.html gained a "Campaign
  Routing" tile. meta_leads_fetcher.py bumped to v1.3 separately
  (campaign_name passthrough at its cls_db.upsert_meta_lead() call site).

v0.14 (July 2026) — Settings > Projects (Task 2 of the settings-GUI
  batch). Requires cls_db.py v2.24. NEW /settings/projects route +
  settings_projects.html (admin-only): list every bucket with its
  aliases, add a new alias to an existing bucket OR create a brand-new
  bucket, delete (x) an alias. settings.html gained a "Projects" tile.

  MODIFIED (data-source only, output unchanged): the 5 call sites that
  built projects=sorted(set(cls_db.PROJECT_BUCKETS.values())) — 1 more
  than this task's originally-scoped 4, found by reading the live file
  rather than assuming the count — now call cls_db.get_all_bucket_names()
  instead. Same output shape at every site (leads_filter, lead_detail,
  lead_new, both WhatsApp template admin screens); no template changes
  needed.

v0.13 (July 2026) — Settings > Team > Add User. NEW combined GET/POST
  route settings_user_new() at /settings/users/new (admin-only, same
  gate pattern as settings_users()), NEW settings_user_new.html. Zero
  cls_db.py changes — this is a GUI wrapper around the already-existing
  cls_db.create_user(), which already hashes passwords and already
  raises ValueError on invalid/duplicate email. settings_users.html
  gained a "+ Add User" link. Mirrors create_admin.py v1.3's
  owner_match_name gating exactly (required for salesperson/manager,
  omitted for admin).

  SECURITY NOTE (flagged, not changed): this route lets an admin create
  another admin account through the browser for the first time —
  previously only possible via terminal access to the office PC running
  create_admin.py. No new privilege is introduced (an existing admin
  could already do this from a terminal), but the exposure surface
  widens: any admin session reachable via the Cloudflare Tunnel can now
  mint a new admin login without physical/terminal access to the
  laptop. No code change requested for this — flagging per Srikanth's
  standing rule to surface auth/role exposure changes explicitly.

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

import base64
import calendar
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_from_directory, send_file, abort, flash,
    jsonify, g
)
from werkzeug.utils import secure_filename
import requests  # v0.51 — Ads Insights Preview demo page's direct Graph API call

# ── Import cls_db.py the same way every other CLS job does ──
BASE_DIR = r"D:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db  # noqa: E402  (must follow the sys.path insert above)
import cls_capi_core  # v0.49 — inline CAPI firing (fire_single_lead_event) for change_lead_stage()
import cls_reports  # v0.6 — Reports section; lives in crm/ alongside app.py, no sys.path change needed
import cls_attendance_photo  # v0.35 — APX Attendance Chunk A: map-thumbnail photo watermarking

# v0.21 — Phase B Telephony: where uploaded call recordings land.
# Deliberately outside cls_db.py's DB file (this is plain files, not
# rows) but still under C:\CLS\ for a single-drive backup story.
# v0.31 — comment corrected: this WAS "intentionally excluded from
# cls_backup.py's rclone sync pending DPDP consent-notice design," but
# that exclusion was reversed in cls_backup.py v1.3 (Srikanth's explicit
# confirmation the consent-notice design is resolved) — RECORDINGS_DIR
# is backed up like everything else now.
# v0.40 — single source-of-truth app version, config-not-code. Keep in
# lockstep with this file's own docstring "Version :" line above (see
# CHANGELOG v0.40) — surfaced into every template via
# inject_current_user() as `app_version`.
APP_VERSION = "0.41"

RECORDINGS_DIR = os.path.join(BASE_DIR, "call_recordings")

# v0.30 — APX Attendance Build Order Step 4: where punch-in/out selfies
# land. Same reasoning as RECORDINGS_DIR above — plain files, not DB
# rows, still under C:\CLS\ for single-drive backup. Same DPDP
# consent-notice question RECORDINGS_DIR had — resolved per Srikanth's
# confirmation (cls_backup.py v1.3), so this is backed up too.
#
# v0.31 — parameterized via CLS_ATTENDANCE_PHOTOS_DIR (a real OS
# environment variable, same "never hardcoded, never in .env" convention
# as cls_db.py's CLS_DB_PATH and this file's own CLS_APK_UPLOAD_SECRET/
# CLS_APK_DOWNLOAD_SECRET above), defaulting to the same path as before
# if unset. Closes a real gap from last session: a test script had no
# way to redirect photo writes away from the live directory the way
# CLS_DB_PATH already lets every test redirect the database — it
# leaked 6 fake test photos into C:\CLS\attendance_photos\ before this
# was caught and cleaned up. A throwaway-DB test from now on should ALSO
# set CLS_ATTENDANCE_PHOTOS_DIR before importing this module (env vars
# are read at import time, same caveat as CLS_DB_PATH).
ATTENDANCE_PHOTOS_DIR = os.environ.get(
    "CLS_ATTENDANCE_PHOTOS_DIR", os.path.join(BASE_DIR, "attendance_photos")
)

# v0.25 — android_pilot APK distribution. GitHub Actions pushes each new
# build here (POST /api/apk/upload) instead of relying on GitHub's
# private-repo Releases, which require a GitHub login and don't work for
# team-wide phone installs. Always overwrites the same filename so the
# public download link never changes across builds.
APK_RELEASES_DIR = os.path.join(BASE_DIR, "apk_releases")
APK_FILENAME = "clspilot-latest.apk"
APK_UPLOAD_LOG = os.path.join(BASE_DIR, "apk_upload_log.txt")

# Two SEPARATE secrets, deliberately not shared — same "config-driven,
# never hardcoded, never in .env" convention as cls_db.py's CLS_DB_PATH
# (real OS environment variables, read via os.environ directly, NOT via
# this file's own _env/dotenv-loaded dict below).
#   CLS_APK_UPLOAD_SECRET   — CI-only (X-Upload-Secret header), never
#                             shared with a human or the Android app.
#   CLS_APK_DOWNLOAD_SECRET — embedded in the shareable download URL
#                             Srikanth gives the team. Separate on
#                             purpose: if the download link ever leaks,
#                             an attacker gets read access to the APK
#                             only — NOT the ability to push a malicious
#                             build, which is what sharing one secret
#                             for both would have allowed.
# Left "" if unset — every check below treats an empty secret as "reject
# everything" (fail closed), never as "no protection needed."
APK_UPLOAD_SECRET = os.environ.get("CLS_APK_UPLOAD_SECRET", "")
APK_DOWNLOAD_SECRET = os.environ.get("CLS_APK_DOWNLOAD_SECRET", "")


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

# v0.47 — Meta leadgen webhook verification token. Read from .env via
# this file's own _env dict (same convention as CRM_SECRET_KEY/CRM_HOST
# above), NOT os.environ directly — that pattern is reserved elsewhere
# in this file for secrets deliberately kept OUT of .env (see
# APK_UPLOAD_SECRET/APK_DOWNLOAD_SECRET above). This token belongs in
# .env, so it follows the .env-sourced convention instead. Empty string
# if unset — the route below fails closed (rejects verification) rather
# than matching an unset token against an unset value.
META_WEBHOOK_VERIFY_TOKEN = _env.get("META_WEBHOOK_VERIFY_TOKEN", "")

# v0.48 — Meta app secret used to verify signed_request payloads on the
# deauthorize/data-deletion callbacks below. Same "read from .env via
# _env dict" convention as META_WEBHOOK_VERIFY_TOKEN above, for the same
# reason (this is meant to live in .env, not as a real OS env var).
META_LEADGEN_APP_SECRET = _env.get("META_LEADGEN_APP_SECRET", "")

# v0.51 — Meta System User token for the ads_read Insights Preview demo
# page (App Review screencast support). Same .env-sourced convention as
# META_WEBHOOK_VERIFY_TOKEN/META_LEADGEN_APP_SECRET above. Empty string
# if unset — the route below fails closed (renders an error message
# instead of sending a blank access_token to Meta).
META_SYSTEM_USER_TOKEN = _env.get("META_SYSTEM_USER_TOKEN", "")


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


def token_required(view):
    """
    v0.21 — Phase B Telephony. Auth for the 2 telephony API endpoints
    ONLY, entirely independent of the session-cookie login every other
    route in this file uses — no `session` read or write happens here
    at all. Reads 'Authorization: Bearer <token>', resolves it via
    cls_db.verify_api_token(), and stashes the resolved user on
    flask.g for the view. 401s on anything missing/invalid, same
    fail-closed posture as login_required/admin_required.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            _log(f"Token rejected: missing/malformed Authorization header (path={request.path})", "WARN")
            abort(401, description="Missing or malformed Authorization header.")
        raw_token = auth_header[len("Bearer "):].strip()
        user = cls_db.verify_api_token(raw_token)
        if not user:
            reason = cls_db.diagnose_api_token_failure(raw_token)
            _log(f"Token rejected: {reason} (path={request.path})", "WARN")
            abort(401, description="Invalid or expired token.")
        g.telephony_user = user
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
    # v0.40 — also injects `app_version` (the APP_VERSION constant
    # above), role-agnostic and available even when logged out, so
    # base.html can show it in the footer on every page.
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
        "app_version": APP_VERSION,
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
    """
    v0.42 — Item 7: /logout is now an interstitial, not an immediate
    session clear. With an active session, shows today's Daily
    Achievements (cls_db.get_todays_achievements) with a "Continue to
    logout" action — the actual clear now happens at logout_confirm()
    below, reached only from that button. A hit with no active session
    (already logged out, or a stray GET) skips straight to login —
    nothing to show. Not native attendance punch-out — that's still
    unwired (android_pilot has no app source yet) — this is purely the
    CRM web session's own /logout link (base.html's nav-drawer).
    """
    if not session.get("user_id"):
        return redirect(url_for("login"))
    achievements = cls_db.get_todays_achievements(session["user_id"])
    return render_template(
        "attendance_today_summary.html",
        achievements=achievements,
        show_logout_button=True,
    )


@app.route("/logout/confirm")
def logout_confirm():
    """
    v0.42 — Item 7: the actual session clear, unchanged in behavior
    from what /logout itself used to do directly — moved here so
    /logout can show the achievements interstitial first. Reached only
    via the "Continue to logout" button on that screen.
    """
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


@app.route("/toggle-view-mode", methods=["POST"])
@login_required
def toggle_view_mode():
    """
    v0.41 — flips the CURRENT LOGIN's own manager view_mode between
    'manager' (company-wide, the default) and 'individual' (own-leads-
    only) — see cls_db.py v2.50's changelog. 403 for anyone whose role
    isn't 'manager'; cls_db.set_view_mode() itself re-checks this too
    (belt and suspenders), so this can never take effect for an admin
    or salesperson account even if reached some other way.

    Redirects back to wherever the toggle control was clicked
    (request.referrer), so the same nav-drawer control works from every
    page; falls back to dashboard() when there's no referrer, or it
    points somewhere off this app (same-origin check against
    request.host_url — an open-redirect guard, since a Referer header is
    technically client-supplied).
    """
    user = cls_db.get_user_by_id(session["user_id"])
    if user["role"] != "manager":
        abort(403, description="Only managers have a view-mode toggle.")

    new_mode = "individual" if cls_db.get_view_mode(user) == "manager" else "manager"
    cls_db.set_view_mode(user["user_id"], new_mode)

    dest = request.referrer
    if dest and dest.startswith(request.host_url):
        return redirect(dest)
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
    #
    # v0.20 — owner-scoping bug fix: these 4 cards previously showed
    # company-wide numbers to every login. Same pattern dashboard_today()
    # already used correctly (see that route's docstring for why
    # owner_match_name, not email, is the right scoping key here).
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)
    scope_owner = None if company_wide else user.get("owner_match_name")
    new_enquiries_count = cls_db.get_new_enquiries_count(owner=scope_owner)  # v1.9 — stage-based now
    reengaged_count = cls_db.get_reengaged_count(days=7, owner=scope_owner)
    follow_up_due_count = len(cls_db.get_due_by_kind("follow_up", owner=scope_owner))
    site_visit_due_count = len(cls_db.get_due_by_kind("site_visit", owner=scope_owner))
    # v0.52 — Task 3 Part A, Change 2/3: 2 new stat-cards, same
    # scope_owner gate already resolved above for the other 4 cards.
    no_future_activity_count = cls_db.get_no_future_activity_count(owner=scope_owner)
    missed_calls_count = cls_db.get_missed_calls_count(owner=scope_owner)
    # v0.44 — Phase 3: admin-only "Today's Attendance" card. Same literal
    # role=='admin' check used throughout the attendance UI (not the looser
    # can_view_all_leads()/OVERSIGHT_ROLES gate), and the SAME function
    # settings_attendance_today() already calls — no second query for the
    # same data. Only computed for admin so non-admin dashboard loads don't
    # pay for a query they'll never render.
    today_attendance = (
        cls_db.get_today_attendance_overview(datetime.now().strftime("%Y-%m-%d"))
        if user["role"] == "admin" else None
    )
    return render_template(
        "dashboard.html",
        active_tab="stats",
        active_view="stats_overview",
        new_enquiries_count=new_enquiries_count,
        reengaged_count=reengaged_count,
        follow_up_due_count=follow_up_due_count,
        site_visit_due_count=site_visit_due_count,
        no_future_activity_count=no_future_activity_count,
        missed_calls_count=missed_calls_count,
        today_attendance=today_attendance,
    )


def _resolve_booking_summary_date_range(args):
    """
    (v0.20) Turns the Booking Summary page's ?preset=&from=&to= into a
    (date_from, date_to, active_preset) triple. Mirrors cls_reports.
    resolve_date_range()'s logic but decoupled from a report_id (this
    page isn't one of the 12 REPORTS_BY_ID reports, so that function
    can't be reused directly). Reuses cls_reports.REPORT_DATE_PRESETS
    (the same 11-option quick-select set as leads_filter.html /
    _report_date_picker.html) rather than duplicating the date-math.
    Falls back to "this_month" when nothing usable is in the query
    string, matching most reports' own date_default.
    """
    preset_arg = args.get("preset")
    if preset_arg and preset_arg != "custom" and preset_arg in cls_reports.REPORT_DATE_PRESETS:
        date_from, date_to = cls_reports.REPORT_DATE_PRESETS[preset_arg]()
        return date_from, date_to, preset_arg
    from_arg = args.get("from")
    to_arg = args.get("to")
    date_re = r"^\d{4}-\d{2}-\d{2}$"
    if (from_arg and to_arg and re.match(date_re, from_arg)
            and re.match(date_re, to_arg) and from_arg <= to_arg):
        return from_arg, to_arg, "custom"
    date_from, date_to = cls_reports.REPORT_DATE_PRESETS["this_month"]()
    return date_from, date_to, "this_month"


@app.route("/dashboard/booking-summary")
@login_required
def dashboard_booking_summary():
    """
    v0.20 — Part B/C: "Leads to Booking Summary" top tab on the Stats
    dashboard (see _dashboard_view_tabbar.html). READ-ONLY report page —
    nothing here writes to leads/activity_log/site_visits/follow_ups.

    Filter bar: Project, Source, Sales Person, Date range. Sales Person
    is force-locked to the logged-in salesperson's own owner_match_name
    (dropdown hidden in the template) — same enforcement, same fails-
    closed posture, as leads_list()'s owner gate: a salesperson's
    ?owner= query param is parsed but never trusted for non-oversight
    roles. Admin/manager get the full dropdown + "All" (owner=None).
    """
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)

    if company_wide:
        owner = request.args.get("owner") or None
        owner_options = cls_db.get_distinct_owners()
    else:
        owner = user.get("owner_match_name") or None
        owner_options = []

    project = request.args.get("project") or None
    source = request.args.get("source") or None
    date_from, date_to, active_preset = _resolve_booking_summary_date_range(request.args)

    filters = {
        "project": project or "", "source": source or "", "owner": owner or "",
        "date_preset": active_preset, "date_from": date_from, "date_to": date_to,
    }

    return render_template(
        "dashboard_booking_summary.html",
        active_tab="stats",
        active_view="booking_summary",
        filters=filters,
        project_options=cls_db.get_all_bucket_names(),
        source_options=cls_db.SOURCE_OPTIONS,
        source_labels=cls_db.SOURCE_DISPLAY_LABELS,
        owner_options=owner_options,
        company_wide=company_wide,
        date_preset_order=cls_reports.REPORT_DATE_PRESET_ORDER,
        date_preset_labels=cls_reports.REPORT_DATE_PRESET_LABELS,
        totals=cls_db.get_booking_summary_totals(date_from, date_to, project, source, owner),
        # v0.20 — stage_counts/visits_by_status come back from cls_db as
        # dicts (useful for any future non-template caller, same shape
        # as get_stage_snapshot_counts()); reshaped to label/count lists
        # here so dashboard_booking_summary.html can render every
        # breakdown table through one shared Jinja macro.
        stage_counts=[{"label": s, "count": c} for s, c in
                      cls_db.get_stage_counts_for_period(date_from, date_to, project, source, owner).items()],
        leads_by_owner=cls_db.get_leads_by_owner_for_period(date_from, date_to, project, source, owner),
        leads_by_project=cls_db.get_leads_by_project_for_period(date_from, date_to, project, source, owner),
        leads_by_source=cls_db.get_leads_by_source_for_period(date_from, date_to, project, source, owner),
        visits_by_owner=cls_db.get_site_visits_by_owner_for_period(date_from, date_to, project, source, owner),
        visits_by_status=[{"label": s, "count": c} for s, c in
                          cls_db.get_site_visits_by_status_for_period(date_from, date_to, project, source, owner).items()],
        visits_by_project=cls_db.get_site_visits_by_project_for_period(date_from, date_to, project, source, owner),
        visits_by_source=cls_db.get_site_visits_by_source_for_period(date_from, date_to, project, source, owner),
        bookings_by_owner=cls_db.get_bookings_by_owner_for_period(date_from, date_to, project, source, owner),
        bookings_by_project=cls_db.get_bookings_by_project_for_period(date_from, date_to, project, source, owner),
        booked_leads=cls_db.get_booked_leads_for_period(date_from, date_to, project, source, owner),
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
    # v0.41 — unless they've toggled their own view_mode to 'individual'
    # (cls_db.effective_company_wide()), in which case they see their
    # own actions only, same as a salesperson.
    company_wide = cls_db.effective_company_wide(user)
    scope_email = None if company_wide else user["email"]
    perf = cls_db.get_todays_activity_counts(actor_email=scope_email)
    # v0.53 — Task 3 Part B: Today's Agenda is LEAD-scoped (which
    # leads a salesperson currently owns), not actor-scoped like perf
    # above (which activity_log rows they personally logged) — a
    # separate scope_owner variable, same owner_match_name pattern
    # dashboard() uses for its Stats-tab cards. Deliberately not
    # reusing/repurposing scope_email for this.
    scope_owner = None if company_wide else user.get("owner_match_name")
    todays_agenda = cls_db.get_todays_agenda(owner=scope_owner)
    return render_template(
        "dashboard_today.html",
        active_tab="today",
        perf=perf,
        company_wide=company_wide,
        todays_agenda=todays_agenda,
    )


@app.route("/dashboard/today/<metric>")
@login_required
def dashboard_today_drilldown(metric):
    """
    v0.45 — Phase 4: drill-down list behind each of Today's Performance's
    5 tiles. One route/template for all 5 (config-driven via cls_db.
    TODAY_PERFORMANCE_METRICS) rather than 5 near-identical routes,
    same "config not code" pattern as due_list()'s <kind> param. Same
    company_wide/actor-email scoping as dashboard_today() itself, so a
    tile's number and its drill-down list are always counting the exact
    same activity_log rows.
    """
    if metric not in cls_db.TODAY_PERFORMANCE_METRICS:
        abort(404)
    config = cls_db.TODAY_PERFORMANCE_METRICS[metric]
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)
    scope_email = None if company_wide else user["email"]
    items = config["fetch"](actor_email=scope_email)
    return render_template(
        "dashboard_today_drilldown.html",
        active_tab="today",
        items=items,
        label=config["label"],
        metric=metric,
    )


@app.route("/attendance/today-summary")
@login_required
def attendance_today_summary():
    """
    v0.42 — Item 7: Daily Achievements. ALWAYS self-scoped — actor is
    session["user_id"], no company-wide option, regardless of role.
    Renders cls_db.get_todays_achievements(), reusing dashboard_today.
    html's existing .stat-card/.stat-card-grid classes (no new CSS).

    Independently reachable on its own (no logout button rendered
    here — that only appears when /logout itself renders this same
    template with show_logout_button=True, see logout() above).
    """
    achievements = cls_db.get_todays_achievements(session["user_id"])
    return render_template(
        "attendance_today_summary.html",
        achievements=achievements,
    )


@app.route("/dashboard/pipeline")
@login_required
def dashboard_pipeline():
    """
    v0.7 — Pipeline Analysis tab. Stage tiles are UNCHANGED: always a
    live snapshot of where every lead sits right now regardless of the
    date picker below (see cls_db.get_stage_snapshot_counts()
    docstring for why this is a snapshot, not a historical-as-of-date
    figure) — only "Total Leads" responds to the date-range picker.

    Date-range parsing reuses this file's own DATE_PRESETS /
    DATE_PRESET_ORDER / DATE_PRESET_LABELS dict (NOT
    cls_reports.REPORT_DATE_PRESETS — established convention, see
    _parse_recordings_filters()'s docstring), same 4-branch resolution
    style. Default preset is "today" ONLY when the route is hit with
    no query string at all, preserving the pre-v0.7 "Total Leads" =
    today's new intake default; an explicit ?date_preset=... (any
    value, including "maximum" for all-time) is always respected as-is.
    cls_db.get_leads_created_today_count() is no longer called here —
    replaced by the new date-range-aware get_leads_created_in_range() —
    but is left untouched since nothing else uses it.
    """
    stage_counts = cls_db.get_stage_snapshot_counts()

    date_preset_param = request.args.get("date_preset") or ""
    date_from = request.args.get("date_from") or ""
    date_to = request.args.get("date_to") or ""

    if not date_preset_param and not date_from and not date_to:
        date_preset_param = "today"  # first-load default, unchanged behavior

    if date_preset_param and date_preset_param != "custom" and date_preset_param in DATE_PRESETS:
        date_from, date_to = DATE_PRESETS[date_preset_param]()
        active_preset = date_preset_param
    elif date_preset_param == "custom":
        active_preset = "custom"
    elif date_from or date_to:
        active_preset = _detect_active_date_preset(date_from, date_to)
    else:
        active_preset = ""

    leads_total = cls_db.get_leads_created_in_range(date_from or None, date_to or None)

    return render_template(
        "dashboard_pipeline.html",
        active_tab="pipeline",
        stage_counts=stage_counts,
        leads_total=leads_total,
        all_stages=cls_db.ALL_STAGES,
        filters={"date_preset": active_preset, "date_from": date_from, "date_to": date_to},
        date_preset_order=DATE_PRESET_ORDER,
        date_preset_labels=DATE_PRESET_LABELS,
    )


@app.route("/due/<kind>")
@login_required
def due_list(kind):
    """
    v0.3 — filtered list behind the dashboard's two split due-today
    cards. kind must be 'site_visit' or 'follow_up'.

    v0.20 — owner-scoping bug fix: previously showed ALL leads to every
    login regardless of who was signed in, even after the dashboard
    CARD count above it was scoped. Same scope_owner gate as dashboard().
    """
    if kind not in ("site_visit", "follow_up"):
        abort(404)
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)
    scope_owner = None if company_wide else user.get("owner_match_name")
    items = cls_db.get_due_by_kind(kind, owner=scope_owner)
    return render_template("due_list.html", items=items, kind=kind)


@app.route("/reengaged")
@login_required
def reengaged_list():
    """
    v0.3 — filtered list behind the dashboard's Reengaged card. Same
    approximate criteria as the count on the dashboard — labeled as
    such in the template, not hidden.

    v0.20 — owner-scoping bug fix: same scope_owner gate as dashboard().
    """
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)
    scope_owner = None if company_wide else user.get("owner_match_name")
    leads = cls_db.get_reengaged_leads(days=7, owner=scope_owner)
    return render_template("reengaged_list.html", leads=leads)


@app.route("/new-enquiries")
@login_required
def new_enquiries_list():
    """
    v0.9.6 — filtered list behind the dashboard's redefined New
    Enquiries card (cls_db.py v2.11 decision 1). Same criteria as
    get_new_enquiries_count(): current_stage='Incoming' AND zero
    activity_log rows — genuinely untouched since arrival.

    v0.20 — owner-scoping bug fix: same scope_owner gate as dashboard().
    """
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)
    scope_owner = None if company_wide else user.get("owner_match_name")
    leads = cls_db.get_new_enquiries_leads(owner=scope_owner)
    return render_template("new_enquiries_list.html", leads=leads)


@app.route("/dashboard/no-future-activity")
@login_required
def no_future_activity_list():
    """
    v0.52 — Task 3 Part A, Change 2: filtered list behind the
    dashboard's new "No Future Activity" card. Same criteria as
    cls_db.get_no_future_activity_count(): open-pipeline leads (not
    Unqualified/Lost/Booked) with no scheduled site visit or follow-up.

    Same scope_owner gate as every other dashboard drill-down route.
    """
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)
    scope_owner = None if company_wide else user.get("owner_match_name")
    leads = cls_db.get_no_future_activity_leads(owner=scope_owner)
    return render_template("no_future_activity_list.html", leads=leads)


@app.route("/dashboard/missed-calls")
@login_required
def missed_calls_list():
    """
    v0.52 — Task 3 Part A, Change 3: filtered list behind the
    dashboard's new "Missed Calls" card. Same criteria as
    cls_db.get_missed_calls_count(): a missed call with no later
    outgoing call back to the same matched lead.

    Same scope_owner gate as every other dashboard drill-down route.
    """
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)
    scope_owner = None if company_wide else user.get("owner_match_name")
    calls = cls_db.get_missed_calls_list(owner=scope_owner)
    return render_template("missed_calls_list.html", calls=calls)


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
# SETTINGS > EXPORT  (v0.18, Task 4 reworked) — admin-only, nested
# under Settings. Was role-agnostic (visible to everyone, self-scoped
# like Reports) — REVERSED per Srikanth's explicit instruction:
# salespeople lose access entirely, this is intentional, not a
# regression. Gated @admin_required, same decorator as Bulk Reassign —
# deliberately narrower than can_view_all_leads()/WRITE_ANYWHERE_ROLES
# (a different, broader gate for lead-level read/write access).
#
# URL path + function names moved from /export/... + export_* to
# /settings/export/... + settings_export_* — my call, for consistency
# with every other admin-only Settings feature (settings_bulk_reassign,
# settings_projects, settings_campaign_routing, settings_users, ...),
# all under the settings_ prefix. Not explicitly specified — flagged.
#
# Filter -> results split (Task D): each export type is now TWO GET
# routes sharing ONE template (view vs results, via show_results) —
# _view renders the filter form only, no query run, no row count;
# _results (reached by submitting that form) computes and shows the
# report. Mirrors Bulk Reassign's filter -> preview split: nothing
# renders until an explicit Apply. Excel/PDF/Email actions live only in
# the results state, same mechanics as before this rework.
#
# Task C (stage/owner checkbox multi-select) is Export-only — the
# report-builder helpers below now read f["stages"]/f["owners"] (lists)
# instead of f["stage"]/f["owner"] (single). _parse_bulk_filters() still
# returns both; Bulk Reassign's own filter form (unchanged) keeps using
# the single-value keys.
# ─────────────────────────────────────────────────────────────

LEADS_EXPORT_COLUMNS = [
    ("crm_lead_no", "Lead #"), ("full_name", "Name"), ("phone_raw", "Phone"),
    ("project_bucket", "Project"), ("current_stage", "Stage"),
    ("lead_owner", "Owner"), ("source", "Source"), ("cls_created_at", "Created"),
]
SITE_VISITS_EXPORT_COLUMNS = [
    ("crm_lead_no", "Lead #"), ("full_name", "Name"), ("phone_raw", "Phone"),
    ("project", "Project"), ("lead_owner", "Owner"),
    ("scheduled_at", "Scheduled"), ("conducted_at", "Conducted"),
    ("outcome_reason", "Outcome"),
]
ACTIVITY_EXPORT_COLUMNS = [
    ("crm_lead_no", "Lead #"), ("full_name", "Name"), ("activity_type", "Type"),
    ("actor", "By"), ("description", "Description"), ("created_at", "When"),
]


def _send_export_email(user, report, filename):
    """
    v0.17 — emails a generated Excel export to the REQUESTING user's
    own login email, via the SAME Brevo (sib_api_v3_sdk) transactional
    API cls_email_drip.py/cls_watchdog.py already use, same
    BREVO_API_KEY from .env — no new SMTP path. Sender address reuses
    sales1@asianbuild.in (cls_watchdog.py's own precedent for internal/
    system emails, cls_email_drip.py's DEFAULT_SENDER mailbox — the
    only Brevo-verified sender already in use for non-customer-facing
    mail) under its own display name rather than a customer-facing
    project brand (Naishka Homes etc.), since this is an internal CRM
    tool, not a lead-facing communication.

    Returns (ok: bool, message: str).
    """
    brevo_key = _env.get("BREVO_API_KEY", "")
    if not brevo_key:
        return False, "BREVO_API_KEY is missing from C:\\CLS\\.env."

    try:
        buf = cls_reports.export_to_excel(report)
    except RuntimeError as e:
        return False, str(e)

    import sib_api_v3_sdk
    cfg = sib_api_v3_sdk.Configuration()
    cfg.api_key["api-key"] = brevo_key
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(cfg))
    send_smtp = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": user["email"], "name": user["full_name"]}],
        sender={"email": "sales1@asianbuild.in", "name": "Asian Properties CRM"},
        subject=report["title"],
        html_content=(
            f"<p>Attached: <strong>{report['title']}</strong>, generated "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}.</p>"
        ),
        attachment=[{
            "content": base64.b64encode(buf.getvalue()).decode("ascii"),
            "name": filename,
        }],
    )
    try:
        api_instance.send_transac_email(send_smtp)
        return True, f"Emailed to {user['email']}."
    except Exception as e:
        return False, str(e)


@app.route("/settings/export")
@login_required
@admin_required
def settings_export_home():
    return render_template("export_home.html")


# ── Export Leads ──

def _export_leads_rows(f):
    return cls_db.get_leads_matching(
        stages=f["stages"] or None, project=f["project"] or None,
        date_from=f["date_from"] or None, date_to=f["date_to"] or None,
        campaigns=f["campaigns"] or None, source=f["source"] or None,
        owners=f["owners"] or None,
    )


def _export_leads_report(f):
    return {
        "title": "Export Leads", "columns": LEADS_EXPORT_COLUMNS,
        "rows": _export_leads_rows(f),
        "date_from": f["date_from"], "date_to": f["date_to"],
    }


def _export_leads_context(f):
    return dict(
        filters=f, stages=cls_db.ALL_STAGES, projects=cls_db.get_all_bucket_names(),
        source_options=cls_db.SOURCE_OPTIONS, campaign_options=cls_db.get_distinct_campaigns(),
        owner_options=cls_db.get_distinct_owners(),
        date_preset_order=DATE_PRESET_ORDER, date_preset_labels=DATE_PRESET_LABELS,
    )


@app.route("/settings/export/leads")
@login_required
@admin_required
def settings_export_leads_view():
    f = _parse_bulk_filters()
    return render_template("export_leads.html", show_results=False, report=None, **_export_leads_context(f))


@app.route("/settings/export/leads/results")
@login_required
@admin_required
def settings_export_leads_results():
    f = _parse_bulk_filters()
    return render_template("export_leads.html", show_results=True, report=_export_leads_report(f), **_export_leads_context(f))


@app.route("/settings/export/leads/excel")
@login_required
@admin_required
def settings_export_leads_excel():
    f = _parse_bulk_filters()
    try:
        buf = cls_reports.export_to_excel(_export_leads_report(f))
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("settings_export_leads_results", **f))
    return send_file(buf, as_attachment=True, download_name="export-leads.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/settings/export/leads/email", methods=["POST"])
@login_required
@admin_required
def settings_export_leads_email():
    user = cls_db.get_user_by_id(session["user_id"])
    f = _parse_bulk_filters()
    ok, message = _send_export_email(user, _export_leads_report(f), "export-leads.xlsx")
    flash(message, "success" if ok else "error")
    return redirect(url_for("settings_export_leads_results", **f))


# ── Export Site Visits Conducted ──

def _export_site_visits_report(f):
    rows = cls_db.get_site_visits_conducted(
        date_from=f["date_from"] or None, date_to=f["date_to"] or None, owners=f["owners"] or None,
    )
    return {
        "title": "Export Site Visits Conducted", "columns": SITE_VISITS_EXPORT_COLUMNS,
        "rows": rows, "date_from": f["date_from"], "date_to": f["date_to"],
    }


def _export_site_visits_context(f):
    return dict(
        filters=f, owner_options=cls_db.get_distinct_owners(),
        date_preset_order=DATE_PRESET_ORDER, date_preset_labels=DATE_PRESET_LABELS,
    )


@app.route("/settings/export/site-visits")
@login_required
@admin_required
def settings_export_site_visits_view():
    f = _parse_bulk_filters()
    return render_template("export_site_visits.html", show_results=False, report=None, **_export_site_visits_context(f))


@app.route("/settings/export/site-visits/results")
@login_required
@admin_required
def settings_export_site_visits_results():
    f = _parse_bulk_filters()
    return render_template("export_site_visits.html", show_results=True, report=_export_site_visits_report(f), **_export_site_visits_context(f))


@app.route("/settings/export/site-visits/excel")
@login_required
@admin_required
def settings_export_site_visits_excel():
    f = _parse_bulk_filters()
    try:
        buf = cls_reports.export_to_excel(_export_site_visits_report(f))
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("settings_export_site_visits_results", **f))
    return send_file(buf, as_attachment=True, download_name="export-site-visits.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/settings/export/site-visits/email", methods=["POST"])
@login_required
@admin_required
def settings_export_site_visits_email():
    user = cls_db.get_user_by_id(session["user_id"])
    f = _parse_bulk_filters()
    ok, message = _send_export_email(user, _export_site_visits_report(f), "export-site-visits.xlsx")
    flash(message, "success" if ok else "error")
    return redirect(url_for("settings_export_site_visits_results", **f))


# ── Export Activity History ──
# No Task B/C changes here — this screen has no Campaign/Project/Stage/
# Owner filter today (just date range + an optional single cls_id), so
# neither task has anything to touch. Flagged rather than silently
# adding fields that weren't asked for.

def _export_activity_report(f, lead_filter_cls_id):
    rows = cls_db.get_activity_log_export(
        date_from=f["date_from"] or None, date_to=f["date_to"] or None,
        cls_id=lead_filter_cls_id or None,
    )
    return {
        "title": "Export Activity History", "columns": ACTIVITY_EXPORT_COLUMNS,
        "rows": rows, "date_from": f["date_from"], "date_to": f["date_to"],
    }


@app.route("/settings/export/activity")
@login_required
@admin_required
def settings_export_activity_view():
    f = _parse_bulk_filters()
    lead_filter_cls_id = (request.args.get("cls_id") or "").strip()
    return render_template(
        "export_activity.html", filters=f, cls_id=lead_filter_cls_id, show_results=False, report=None,
        date_preset_order=DATE_PRESET_ORDER, date_preset_labels=DATE_PRESET_LABELS,
    )


@app.route("/settings/export/activity/results")
@login_required
@admin_required
def settings_export_activity_results():
    f = _parse_bulk_filters()
    lead_filter_cls_id = (request.args.get("cls_id") or "").strip()
    return render_template(
        "export_activity.html", filters=f, cls_id=lead_filter_cls_id, show_results=True,
        export_args=dict(f, cls_id=lead_filter_cls_id),
        report=_export_activity_report(f, lead_filter_cls_id),
        date_preset_order=DATE_PRESET_ORDER, date_preset_labels=DATE_PRESET_LABELS,
    )


@app.route("/settings/export/activity/excel")
@login_required
@admin_required
def settings_export_activity_excel():
    f = _parse_bulk_filters()
    lead_filter_cls_id = (request.args.get("cls_id") or "").strip()
    try:
        buf = cls_reports.export_to_excel(_export_activity_report(f, lead_filter_cls_id))
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("settings_export_activity_results", **f, cls_id=lead_filter_cls_id))
    return send_file(buf, as_attachment=True, download_name="export-activity.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/settings/export/activity/email", methods=["POST"])
@login_required
@admin_required
def settings_export_activity_email():
    user = cls_db.get_user_by_id(session["user_id"])
    f = _parse_bulk_filters()
    lead_filter_cls_id = (request.form.get("cls_id") or "").strip()
    ok, message = _send_export_email(user, _export_activity_report(f, lead_filter_cls_id), "export-activity.xlsx")
    flash(message, "success" if ok else "error")
    return redirect(url_for("settings_export_activity_results", **f, cls_id=lead_filter_cls_id))


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

    v0.33 — NEW "stages" (list, via getlist("stages")) — Pipeline Stage
    is now a checkbox multi-select on the Leads List filter screen, same
    pattern as configuration/property_type/facing below. The existing
    single-value "stage" key is left in place unchanged (still populated
    from request.args.get("stage")) for backward compatibility with any
    caller/bookmark that only ever set the old single-value param; the
    actual query in leads_list() now reads f["stages"], not f["stage"].
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
        "stages":        request.args.getlist("stages"),
        "project":       request.args.get("project") or "",
        "owner":         request.args.get("owner") or "",
        "date_from":     date_from,
        "date_to":       date_to,
        "date_preset":   active_preset,
        "sort_by":       request.args.get("sort_by") or "created_desc",
        "stage_reason":  request.args.get("stage_reason") or "",
        "campaign":      request.args.get("campaign") or "",
        "source":        request.args.get("source") or "",
        "sub_source":    request.args.get("sub_source") or "",
        "budget":        request.args.get("budget") or "",
        "configuration": request.args.getlist("configuration"),
        "property_type": request.args.getlist("property_type"),
        "facing":        request.args.getlist("facing"),
    }


def _parse_bulk_filters():
    """
    v0.17 — Task 3 (Bulk Reassign) / Task 4 (Bulk Export) shared filter
    parser. Deliberately a SEPARATE, smaller helper from
    _parse_lead_filters() above — these two features only ever offer
    date range, campaign (multi-select), project, stage, source, and
    current owner, not the full leads-list filter set (no search,
    sort, stage_reason, budget, configuration/property_type/facing).

    Date-preset resolution is copied from _parse_lead_filters() rather
    than shared as a sub-helper — same 4-branch logic, reusing the SAME
    DATE_PRESETS dict leads_filter.html already uses (Srikanth's
    approved call: reuse app.py's existing dict rather than pulling in
    cls_reports.py's separate REPORT_DATE_PRESETS copy).

    v0.18 — gained stages/owners (lists, Task C's checkbox multi-select,
    Export-only). Bulk Reassign's own filter form never submits these
    (still single-value stage/owner radios) so they're just empty lists
    for that caller — additive, no existing behavior changed.
    """
    date_preset_param = request.values.get("date_preset") or ""
    date_from = request.values.get("date_from") or ""
    date_to = request.values.get("date_to") or ""

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
        "date_from":   date_from,
        "date_to":     date_to,
        "date_preset": active_preset,
        "campaigns":   request.values.getlist("campaigns"),
        "project":     request.values.get("project") or "",
        "stage":       request.values.get("stage") or "",
        "source":      request.values.get("source") or "",
        "owner":       request.values.get("owner") or "",
        "stages":      request.values.getlist("stages"),
        "owners":      request.values.getlist("owners"),
    }


def _bulk_filters_summary(f, to_owner):
    """
    v0.17 — builds the short human-readable string stored in
    bulk_jobs.filters_summary — deliberately plain text, not JSON, so
    settings_bulk_jobs.html can print it directly with no second
    renderer. Only lists filters that were actually set; "All leads"
    if none were.

    v0.19 — FIX: now actually appends "→ reassigned to {to_owner}",
    matching the format this function's own original design doc (and
    cls_db.create_bulk_job()'s docstring) always described — e.g.
    "Project: Naishka, Stage: Prospect → reassigned to Devender Goud".
    This was silently missing before (the caller never appended it
    either), so bulk_jobs.to_owner — stored as its own column — never
    actually showed up anywhere, since settings_bulk_jobs.html only
    ever displays the filters_summary column. Found while reworking
    this function for multi-select; fixed as part of the same change.

    Also: Stage/Owner (now checkbox multi-select — Bulk Reassign
    Filter UX Rework) and Campaign (already multi-select) each join
    their own selected values with ", "; the filter CATEGORIES
    themselves now join with " | " instead of ", " — needed once a
    single category can itself contain commas (e.g. "Stage: Prospect,
    Site Visit Scheduled"), so the string stays unambiguous rather than
    running every value together indistinguishably.
    """
    parts = []
    if f["project"]:
        parts.append(f"Project: {f['project']}")
    if f["stages"]:
        parts.append(f"Stage: {', '.join(f['stages'])}")
    if f["campaigns"]:
        parts.append(f"Campaign: {', '.join(f['campaigns'])}")
    if f["source"]:
        parts.append(f"Source: {f['source']}")
    if f["owners"]:
        parts.append(f"Current Owner: {', '.join(f['owners'])}")
    if f["date_preset"]:
        parts.append(f"Date: {DATE_PRESET_LABELS.get(f['date_preset'], f['date_preset'])}")
    filters_part = " | ".join(parts) if parts else "All leads"
    return f"{filters_part} → reassigned to {to_owner}"


@app.route("/leads")
@login_required
def leads_list():
    f = _parse_lead_filters()
    page = request.args.get("page", 1, type=int)

    user = cls_db.get_user_by_id(session["user_id"])
    owner_unlinked_warning = False

    # v0.41 — company_wide now goes through cls_db.effective_company_wide()
    # rather than can_view_all_leads(user["role"]) directly, so a manager
    # who has toggled their own view_mode to 'individual' is force-scoped
    # to their own owner_match_name below exactly like a salesperson. An
    # admin, or a manager who hasn't toggled, sees no behavior change.
    company_wide = cls_db.effective_company_wide(user)

    if company_wide:
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
    if not company_wide and not owner:
        result = {"rows": [], "total": 0, "page": 1, "per_page": cls_db.CRM_PAGE_SIZE, "total_pages": 1}
    else:
        # v0.9.1 — a salesperson's ACTIVE SEARCH looks across all owners
        # (they land on the restricted read-only view for anything not
        # theirs); their blank list stays scoped to their own leads.
        # Oversight roles (admin/manager, v0.9.5) already see everything,
        # so the flag is a no-op for them.
        result = cls_db.get_leads_page(
            project=f["project"] or None,
            search=f["q"] or None, owner=owner, page=page,
            date_from=f["date_from"] or None, date_to=f["date_to"] or None,
            sort_by=f["sort_by"], stage_reason=f["stage_reason"] or None,
            campaign=f["campaign"] or None, source=f["source"] or None,
            sub_source=f["sub_source"] or None, budget=f["budget"] or None,
            configuration=f["configuration"] or None,
            property_type=f["property_type"] or None,
            facing=f["facing"] or None,
            search_all_owners=(not company_wide),
            stages=f["stages"] or None,
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
        projects=cls_db.get_all_bucket_names(),
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
        project_buckets=cls_db.get_all_bucket_names() if can_write else [],
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

    # v0.49 — inline CAPI firing. On a successful stage change into a
    # target stage, fire it to Meta synchronously; queue on any failure
    # rather than let a Meta hiccup block the salesperson's request.
    if ok and new_stage in cls_capi_core.TARGET_STAGES:
        try:
            fresh_lead = cls_db.get_lead_by_id(cls_id)
            fired, err = cls_capi_core.fire_single_lead_event(fresh_lead, _env)
            if fired:
                _log(f"CAPI fire OK: cls_id={cls_id} | {new_stage}")
            else:
                cls_db.queue_failed_fire(cls_id, new_stage, err)
                _log(f"CAPI fire FAILED (queued): cls_id={cls_id} | {new_stage} | {err}", "WARNING")
        except Exception as e:
            cls_db.queue_failed_fire(cls_id, new_stage, str(e))
            _log(f"CAPI fire EXCEPTION (queued): cls_id={cls_id} | {new_stage} | {e}", "WARNING")

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
        projects=cls_db.get_all_bucket_names(),
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


@app.route("/leads/<cls_id>/whatsapp/send", methods=["POST"])
@login_required
def whatsapp_send(cls_id):
    """
    v0.17 — Task 2.2. whatsapp_picker's Send button used to be a plain
    client-side wa.me deep link (window.open, no server round-trip, so
    nothing ever got logged). Now a real POST so the send gets an
    activity_log row — mirrors reminder_mark_sent() below exactly: same
    ownership gate, same "wa_url must start with https://wa.me/"
    validation.

    v0.34 — PWA deep-link fix. This route used to 302-redirect the
    browser into wa_url itself; that redirect chain (this route's 302 ->
    https://wa.me/... -> whatsapp://...) loses user-gesture status in an
    installed/standalone PWA, so the OS blocked the whatsapp:// custom
    scheme (net::ERR_UNKNOWN_URL_SCHEME). The browser now navigates via
    whatsapp_picker.html's own <a href="https://wa.me/..."> directly —
    this route only logs the send, via a fetch(..., {keepalive:true})
    fired alongside that navigation, so it returns a plain 204 instead.
    Validation and logging logic are otherwise unchanged.
    """
    lead = cls_db.get_lead_by_id(cls_id)
    if not lead:
        abort(404, description="No lead found with that id.")
    user = cls_db.get_user_by_id(session["user_id"])
    _check_lead_ownership(lead, user)

    wa_url = request.form.get("wa_url", "")
    if not wa_url.startswith("https://wa.me/"):
        abort(400, description="Invalid WhatsApp link.")

    project = (request.form.get("project") or "").strip() or "Unknown project"
    message = (request.form.get("message") or "").strip()
    description = f"{project} template"
    if message:
        description += f" — {message}"

    cls_db.log_whatsapp_sent(cls_id, _actor(), description)
    return "", 204


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
    """
    v0.34 — PWA deep-link fix. This route used to 302-redirect the
    browser into wa_url itself; that redirect chain (this route's 302 ->
    https://wa.me/... -> whatsapp://...) loses user-gesture status in an
    installed/standalone PWA, so the OS blocked the whatsapp:// custom
    scheme (net::ERR_UNKNOWN_URL_SCHEME). The browser now navigates via
    reminders_tomorrow.html's own <a href="https://wa.me/..."> directly
    — this route only logs the send, via a fetch(..., {keepalive:true})
    fired alongside that navigation, so it returns a plain 204 instead.
    Validation and logging logic are otherwise unchanged.
    """
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
        abort(400, description="Invalid WhatsApp link.")

    cls_db.log_reminder_sent(visit_id, visit["cls_id"], actor=_actor())
    return "", 204


# ─────────────────────────────────────────────────────────────
# SETTINGS  (admin-only hub — v0.9.1)
# ─────────────────────────────────────────────────────────────

@app.route("/settings")
@login_required
def settings_home():
    """
    v0.9.1 — the admin Settings landing page. A hub of tiles;
    WhatsApp Templates is the first tenant, with room for more (user
    management, list config, etc.) without touching the hamburger menu
    each time.

    v0.26 — gate loosened from @admin_required to @login_required: the
    page itself is now reachable by any logged-in user, but every
    EXISTING tile is wrapped in {% if current_user.role == 'admin' %} in
    settings.html itself, so a non-admin still sees none of them — this
    route change is additive/gating only, no existing admin functionality
    was removed, just moved from a route-level gate to a template-level
    one for the specific sections that still need it. The one new
    section that's genuinely role-agnostic (Device Sync, a native-bridge
    entry point with no server-side data of its own) is what actually
    needed this loosened gate.
    """
    return render_template("settings.html")


@app.route("/settings/projects", methods=["GET", "POST"])
@login_required
@admin_required
def settings_projects():
    """
    v0.14 — admin Settings > Projects. GUI CRUD for the project_aliases
    table (cls_db.py v2.24), which replaced the hardcoded PROJECT_BUCKETS
    dict. One form handles both "add an alias to an existing bucket" and
    "create a brand-new bucket" — a brand-new bucket is just an alias
    whose project_bucket equals itself (see cls_db.add_project_alias()
    docstring), so no separate route/branch is needed for that case.
    """
    if request.method == "POST":
        alias = request.form.get("alias", "").strip()
        project_bucket = request.form.get("project_bucket", "").strip()
        try:
            cls_db.add_project_alias(alias, project_bucket)
            flash(f"'{alias}' -> '{project_bucket}' saved.", "success")
        except ValueError as e:
            flash(str(e), "error")
        return redirect(url_for("settings_projects"))

    buckets = cls_db.list_project_buckets()
    return render_template("settings_projects.html", buckets=buckets)


@app.route("/settings/projects/<path:alias>/delete", methods=["POST"])
@login_required
@admin_required
def settings_project_alias_delete(alias):
    """v0.14 — deletes one alias row. No blocking logic — see
    cls_db.delete_project_alias() docstring for why that's safe."""
    cls_db.delete_project_alias(alias)
    flash(f"'{alias}' removed.", "success")
    return redirect(url_for("settings_projects"))


@app.route("/settings/campaign-routing")
@login_required
@admin_required
def settings_campaign_routing():
    """
    v0.15 — admin Settings > Campaign Routing. Lists all rules plus the
    global fallback owner. ?edit=<campaign_name> prefills the add/edit
    form with that rule's current values (campaign_name itself is not
    editable once created — it's the table's unique key; "editing" means
    changing rule_type/owners/active for that same campaign).

    Owner dropdown is sourced from cls_db.get_all_users_detailed(),
    filtered to active salespeople/managers WITH an owner_match_name set
    — the value actually written as leads.lead_owner must be that exact
    string, not a full_name/email that would silently fail to match.
    """
    edit_campaign = request.args.get("edit", "").strip()
    edit_rule = None
    if edit_campaign:
        edit_rule = next(
            (r for r in cls_db.list_campaign_routing_rules()
             if r["campaign_name"].lower() == edit_campaign.lower()),
            None
        )

    owner_choices = [
        u for u in cls_db.get_all_users_detailed()
        if u["active"] and u["role"] in ("manager", "salesperson") and u["owner_match_name"]
    ]

    return render_template(
        "settings_campaign_routing.html",
        rules=cls_db.list_campaign_routing_rules(),
        fallback_owner=cls_db.get_fallback_owner(),
        owner_choices=owner_choices,
        edit_rule=edit_rule,
    )


@app.route("/settings/campaign-routing/fallback", methods=["POST"])
@login_required
@admin_required
def settings_campaign_routing_fallback():
    try:
        cls_db.set_fallback_owner(request.form.get("fallback_owner", ""))
        flash("Fallback owner updated.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("settings_campaign_routing"))


@app.route("/settings/campaign-routing/save", methods=["POST"])
@login_required
@admin_required
def settings_campaign_routing_save():
    campaign_name = request.form.get("campaign_name", "").strip()
    rule_type = request.form.get("rule_type", "").strip()
    owners_list = [o.strip() for o in request.form.getlist("owners") if o.strip()]
    try:
        cls_db.upsert_campaign_routing_rule(campaign_name, rule_type, owners_list)
        flash(f"Routing rule for '{campaign_name}' saved.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("settings_campaign_routing"))


@app.route("/settings/campaign-routing/<path:campaign_name>/toggle", methods=["POST"])
@login_required
@admin_required
def settings_campaign_routing_toggle(campaign_name):
    active = request.form.get("active") == "1"
    cls_db.set_campaign_routing_rule_active(campaign_name, active)
    flash(f"'{campaign_name}' {'activated' if active else 'deactivated'}.", "success")
    return redirect(url_for("settings_campaign_routing"))


@app.route("/settings/campaign-routing/<path:campaign_name>/delete", methods=["POST"])
@login_required
@admin_required
def settings_campaign_routing_delete(campaign_name):
    cls_db.delete_campaign_routing_rule(campaign_name)
    flash(f"'{campaign_name}' deleted.", "success")
    return redirect(url_for("settings_campaign_routing"))


@app.route("/settings/lead-scoring", methods=["GET", "POST"])
@login_required
@admin_required
def settings_lead_scoring():
    """
    v0.16 — admin Settings > Lead Scoring. Only changes WHERE
    compute_lead_scores()'s rules come from (DB, via cls_db.py's new
    get_lead_score_config()/set_lead_score_config()) — the scoring
    mechanism and its display (score-badge on leads_list/lead_detail)
    are untouched. A saved change takes effect immediately, no restart.
    """
    if request.method == "POST":
        try:
            config = {
                "stage_points": {
                    stage: float(request.form.get(f"stage_{stage}", "").strip())
                    for stage in cls_db.ALL_STAGES
                },
                "temperature_points": {
                    "Warm": float(request.form.get("temp_warm", "").strip()),
                    "Hot": float(request.form.get("temp_hot", "").strip()),
                },
                "site_visit_conducted": float(request.form.get("site_visit_conducted", "").strip()),
                "site_visit_no_show": float(request.form.get("site_visit_no_show", "").strip()),
                "follow_up_completed": float(request.form.get("follow_up_completed", "").strip()),
                "note_points_per_day": float(request.form.get("note_points_per_day", "").strip()),
                "call_tap_points_per_day": float(request.form.get("call_tap_points_per_day", "").strip()),
                "decay_after_days": float(request.form.get("decay_after_days", "").strip()),
                "decay_points_per_period": float(request.form.get("decay_points_per_period", "").strip()),
                "decay_exempt_stages": request.form.getlist("decay_exempt_stages"),
                "hot_threshold": float(request.form.get("hot_threshold", "").strip()),
                "warm_threshold": float(request.form.get("warm_threshold", "").strip()),
            }
            cls_db.set_lead_score_config(config)
            flash("Lead scoring config saved.", "success")
        except ValueError as e:
            flash(f"Could not save: {e}", "error")
        return redirect(url_for("settings_lead_scoring"))

    config = cls_db.get_lead_score_config()
    return render_template("settings_lead_scoring.html", config=config, all_stages=cls_db.ALL_STAGES)


# ─────────────────────────────────────────────────────────────
# SETTINGS > BULK REASSIGN  (v0.17, Task 3 — admin-only)
# ─────────────────────────────────────────────────────────────
# Three steps, deliberately (Srikanth's call — this is the one
# irreversible bulk action in this batch): filter form (GET) -> preview
# (GET, shows matched count + target owner, nothing written yet) ->
# commit (POST, the only step that actually writes). admin_required
# only, NOT cls_db.can_write_any_lead()/WRITE_ANYWHERE_ROLES — a
# manager can write to any SINGLE lead (v0.11.1) but bulk reassignment
# at scale is stricter than that, per Srikanth's explicit instruction.

def _bulk_reassign_matched(f):
    """
    Shared lookup — filter form + preview + commit all need the SAME
    matched set for the SAME filters.

    v0.19 — Stage and (filter-)Owner now read f["stages"]/f["owners"]
    (lists, checkbox multi-select) instead of the single-value
    f["stage"]/f["owner"] — reuses cls_db.py v2.30's stages=/owners=
    params (already built for Export, no cls_db.py change needed here).
    """
    return cls_db.get_leads_matching(
        stages=f["stages"] or None, project=f["project"] or None,
        date_from=f["date_from"] or None, date_to=f["date_to"] or None,
        campaigns=f["campaigns"] or None, source=f["source"] or None,
        owners=f["owners"] or None,
    )


@app.route("/settings/bulk-reassign")
@login_required
@admin_required
def settings_bulk_reassign():
    f = _parse_bulk_filters()
    target_owners = [u for u in cls_db.get_all_users_detailed()
                     if u["active"] and (u["owner_match_name"] or "").strip()]
    return render_template(
        "bulk_reassign_filter.html",
        filters=f,
        stages=cls_db.ALL_STAGES,
        projects=cls_db.get_all_bucket_names(),
        source_options=cls_db.SOURCE_OPTIONS,
        campaign_options=cls_db.get_distinct_campaigns(),
        owner_options=cls_db.get_distinct_owners(),
        target_owners=target_owners,
        date_preset_order=DATE_PRESET_ORDER,
        date_preset_labels=DATE_PRESET_LABELS,
    )


@app.route("/settings/bulk-reassign/preview")
@login_required
@admin_required
def settings_bulk_reassign_preview():
    f = _parse_bulk_filters()
    to_owner = (request.args.get("to_owner") or "").strip()
    if not to_owner:
        flash("Select a target owner before previewing.", "error")
        return redirect(url_for("settings_bulk_reassign", **request.args))

    matched = _bulk_reassign_matched(f)
    return render_template(
        "bulk_reassign_preview.html",
        filters=f, to_owner=to_owner, matched=matched,
        date_preset_labels=DATE_PRESET_LABELS,
    )


@app.route("/settings/bulk-reassign/commit", methods=["POST"])
@login_required
@admin_required
def settings_bulk_reassign_commit():
    f = _parse_bulk_filters()
    to_owner = (request.form.get("to_owner") or "").strip()
    if not to_owner:
        flash("Select a target owner before confirming.", "error")
        return redirect(url_for("settings_bulk_reassign"))

    matched = _bulk_reassign_matched(f)
    matched_ids = [lead["cls_id"] for lead in matched]

    actor = _actor()
    reassigned_count = cls_db.bulk_reassign_leads(matched_ids, to_owner, actor)
    # v0.46 — Phase 5: cls_ids=matched_ids snapshots exactly which leads
    # this job touched into bulk_job_leads, atomically with the bulk_jobs
    # row itself (see cls_db.py v2.53's create_bulk_job() changelog).
    cls_db.create_bulk_job("bulk_reassign", actor, _bulk_filters_summary(f, to_owner), to_owner,
                           reassigned_count, cls_ids=matched_ids)

    flash(f"Reassigned {reassigned_count} lead(s) to {to_owner}.", "success")
    return redirect(url_for("settings_bulk_jobs"))


@app.route("/settings/bulk-jobs")
@login_required
@admin_required
def settings_bulk_jobs():
    return render_template("settings_bulk_jobs.html", jobs=cls_db.get_bulk_jobs())


@app.route("/settings/bulk-jobs/<int:job_id>/export.xlsx")
@login_required
@admin_required
def settings_bulk_job_export_excel(job_id):
    """
    v0.46 — Phase 5: per-bulk-job Excel export, same shape as
    settings_export_leads_excel() (reuses LEADS_EXPORT_COLUMNS and
    cls_reports.export_to_excel()). Rows come from the bulk_job_leads
    SNAPSHOT (cls_db.get_bulk_job_lead_rows()), not the leads' current
    owner/stage, so the download always reflects exactly what this job
    touched at the time it ran. settings_bulk_jobs.html only shows this
    link when leads_snapshot_count > 0 (jobs from before this migration
    have none) — this route doesn't re-check that itself, since an
    admin hitting the URL directly for an old job just gets a
    near-empty workbook (header row only), not an error.
    """
    report = {
        "title": f"Bulk Job #{job_id} — Leads",
        "columns": LEADS_EXPORT_COLUMNS,
        "rows": cls_db.get_bulk_job_lead_rows(job_id),
    }
    try:
        buf = cls_reports.export_to_excel(report)
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("settings_bulk_jobs"))
    return send_file(buf, as_attachment=True, download_name=f"bulk-job-{job_id}-leads.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/settings/users")
@login_required
@admin_required
def settings_users():
    """v0.9.3 — admin Settings > Team: list every CRM login with an
    activate/deactivate toggle. Item 1 of Srikanth's testing-feedback
    batch. Reuses users.active, already enforced by verify_login()/
    get_user_by_id() since v0.1 — this is the first admin-facing UI
    for a flag that already worked, not a new permission concept.

    v0.28 — also passes projects (cls_db.get_all_bucket_names()) for a
    new per-row "assigned project" dropdown (APX Attendance geofencing,
    cls_db.py v2.38's users.assigned_project column) rendered in
    settings_users.html alongside the existing activate/deactivate form.
    """
    users = cls_db.get_all_users_detailed()
    return render_template("settings_users.html", users=users, projects=cls_db.get_all_bucket_names())


@app.route("/settings/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def settings_user_new():
    """
    v0.13 — admin Settings > Team > Add User. GUI wrapper around
    cls_db.create_user() (unchanged) — the first in-app way to create a
    CRM login; previously only possible via terminal access to the
    office PC running create_admin.py. Mirrors create_admin.py v1.3's
    owner_match_name gating exactly: admins get nothing extra, managers
    and salespeople both require it (a manager is a "player-coach" who
    carries their own leads too, same reasoning as the terminal script).
    """
    form = {"full_name": "", "email": "", "role": "salesperson", "owner_match_name": ""}

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()
        owner_match_name = request.form.get("owner_match_name", "").strip()

        form = {"full_name": full_name, "email": email, "role": role, "owner_match_name": owner_match_name}

        if role not in cls_db.CRM_ROLES:
            flash("Please choose a valid role.", "error")
        elif role in ("salesperson", "manager") and not owner_match_name:
            flash("Owner name (Sell.do 'Attended By' text) is required for salesperson and manager logins.", "error")
        elif not password or len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            try:
                cls_db.create_user(
                    full_name, email, password, role,
                    owner_match_name if role != "admin" else None,
                )
                flash(f"Created login for {full_name or email}.", "success")
                return redirect(url_for("settings_users"))
            except ValueError as e:
                flash(str(e), "error")

    return render_template("settings_user_new.html", roles=cls_db.CRM_ROLES, form=form)


@app.route("/settings/telephony", methods=["GET", "POST"])
@login_required
def settings_telephony():
    """
    v0.22 — Settings > Telephony. Phase B: per-salesperson OEM
    recording-folder path config (cls_db.user_recording_paths), one text
    input per user saved together in a single form — same shape as
    settings_lead_scoring.html's "one input per item, one Save button"
    pattern, not settings_users.html's per-row-own-form pattern.
    Token generation (per-user bearer token for the 2 telephony API
    endpoints) is a SEPARATE small form per row below, deliberately not
    bundled into this save form so saving paths can never accidentally
    regenerate someone's token.

    v0.22 — self-scoped access: was @admin_required, now @login_required
    only, same can_view_all_leads(role) gate used everywhere else in
    this file (e.g. leads_list()). Oversight roles (admin, manager) keep
    today's unchanged company-wide view of every user's row. A
    salesperson instead sees ONLY their own row, and on POST may only
    ever write their own path_<user_id> field — any other path_<id> key
    present in the submitted form is ignored (defense in depth; the
    template they're served only ever renders an input for their own
    user_id, so this should be unreachable via the UI itself).
    """
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.can_view_all_leads(user["role"])

    if request.method == "POST":
        users = cls_db.get_all_users_detailed()
        if not company_wide:
            users = [u for u in users if u["user_id"] == user["user_id"]]
        for u in users:
            field = f"path_{u['user_id']}"
            if field in request.form:
                cls_db.set_recording_path(u["user_id"], request.form.get(field, "").strip())
        flash("Recording folder paths saved.", "success")
        return redirect(url_for("settings_telephony"))

    users = cls_db.get_all_users_detailed()
    if not company_wide:
        users = [u for u in users if u["user_id"] == user["user_id"]]
    for u in users:
        u["recording_folder_path"] = cls_db.get_recording_path(u["user_id"]) or ""
    return render_template("settings_telephony.html", users=users, company_wide=company_wide)


@app.route("/settings/telephony/token/<int:user_id>/revoke", methods=["POST"])
@login_required
def settings_telephony_revoke_token(user_id):
    """
    v0.38 — was settings_telephony_generate_token() (v0.22); renamed
    and repurposed as part of the Option C self-service token-sync
    redesign. Manual admin generation + voice-relay is retired — this
    is now purely an admin KILL-SWITCH (lost phone / departing
    employee): deactivates the user's current active token via the
    new cls_db.revoke_api_token(user_id) and mints NOTHING in its
    place, so there is no raw value to show or relay by hand. The
    employee gets a working token again by tapping "Sync my token" in
    the app themselves (POST /api/my-token below), which mints their
    own via the unchanged cls_db.generate_api_token().

    Permission check is UNCHANGED from v0.22: self-scoped access.
    Oversight roles (admin, manager) may revoke anyone's token; a
    non-oversight (salesperson) login may only ever revoke their OWN
    — 403s regardless of what the URL's user_id says, never trusting
    the request to self-report.
    """
    requester = cls_db.get_user_by_id(session["user_id"])
    if not cls_db.can_view_all_leads(requester["role"]) and user_id != requester["user_id"]:
        abort(403, description="You may only revoke your own telephony token.")

    user = cls_db.get_user_by_id(user_id)
    if not user:
        flash("Unknown user.", "error")
        return redirect(url_for("settings_telephony"))
    cls_db.revoke_api_token(user_id)
    flash(
        f"Token revoked for {user['full_name'] or user['email']} — they'll need to "
        f"tap \"Sync my token\" in the app to get a new one.",
        "success"
    )
    return redirect(url_for("settings_telephony"))


@app.route("/api/my-token", methods=["POST"])
@login_required
def api_my_token():
    """
    v0.38 — Option C self-service token sync. Session-cookie authed
    ONLY (@login_required, not @token_required) — always acts on
    session["user_id"], NEVER accepts a user_id parameter, so this can
    never be used to fetch anyone else's token.

    Raw tokens are never stored anywhere (cls_db.verify_api_token()
    only ever sees a SHA-256 hash), so there is no "return the
    existing token" path — every call mints a FRESH one via the
    existing, unmodified cls_db.generate_api_token(), deactivating
    whatever was active before. Deliberately POST, not GET, so no
    prefetch/proxy/cache layer can trigger this without a real user
    action behind it. Meant to be called ONLY by the app's explicit
    "Sync my token" button (android_pilot SettingsActivity.kt), never
    automatically/on a timer — each call invalidates whatever token
    is currently active for this user on any other device, same
    pre-existing limitation the old admin-regenerate flow already had.

    The raw token is returned in the JSON body and NEVER logged —
    same "never logged" posture as the flash-message path this
    replaces.
    """
    raw_token = cls_db.generate_api_token(session["user_id"])
    return jsonify({"token": raw_token})


def _parse_recordings_filters():
    """
    v0.24 — filter parser for /settings/telephony/recordings. Date-preset
    resolution is COPIED from _parse_lead_filters()/_parse_bulk_filters()
    rather than shared as a sub-helper — same established convention
    those two already follow (see _parse_bulk_filters()'s own docstring):
    same 4-branch logic, reusing app.py's own DATE_PRESETS dict rather
    than cls_reports.py's separate REPORT_DATE_PRESETS copy.
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
        "date_from":       date_from,
        "date_to":         date_to,
        "date_preset":     active_preset,
        "call_status":     request.args.get("call_status") or "",
        "lead_owner":      request.args.get("lead_owner") or "",
        "activity_owner":  request.args.get("activity_owner") or "",
        "search":          request.args.get("search") or "",
    }


@app.route("/settings/telephony/recordings")
@login_required
def settings_telephony_recordings():
    """
    v0.25 — Settings > Telephony > Synced Recordings. Filtered,
    paginated table of every call_recording activity_log row, with
    inline playback (reuses serve_recording() as-is) and per-row delete.
    Gated @login_required only now (was + @admin_required) — NOT
    can_write_any_lead, a separate lead-scoped gate.

    v0.25 — self-scoped access, same can_view_all_leads(role) gate used
    everywhere else in this file. Oversight roles (admin, manager) keep
    today's unchanged company-wide view. A salesperson is force-scoped
    to their own owner_match_name — same fails-closed convention as
    leads_list()'s owner gate: any ?lead_owner= they pass on the query
    string is never trusted, always overwritten server-side. The
    Lead-owner/Activity-owner filter dropdowns are also omitted from
    what's passed to the template for this role (see company_wide below)
    since every row shown is already theirs.
    """
    user = cls_db.get_user_by_id(session["user_id"])
    company_wide = cls_db.effective_company_wide(user)

    f = _parse_recordings_filters()
    if not company_wide:
        f["lead_owner"] = user.get("owner_match_name") or ""
    page = request.args.get("page", 1, type=int)

    result = cls_db.list_call_recordings(
        date_from=f["date_from"] or None, date_to=f["date_to"] or None,
        call_status=f["call_status"] or None, lead_owner=f["lead_owner"] or None,
        activity_owner=f["activity_owner"] or None, search=f["search"] or None,
        page=page,
    )

    # v0.24 — actor/lead_owner display-name resolution happens here, in
    # the route, matching the established convention: activity_log.actor
    # is always resolved to a display name in Python via get_all_users()
    # (an email->full_name dict), never via a SQL JOIN — every existing
    # consumer of activity_log.actor (lead_detail.html's timeline) does
    # this the same way.
    user_names = cls_db.get_all_users()
    for r in result["rows"]:
        r["actor_name"] = user_names.get(r["actor"], r["actor"])
        # File-existence check — same os.path.exists() logic
        # cls_call_recording_audit.py already uses, surfaced here so an
        # admin can see at a glance whether a recording is actually
        # playable, given the recent file-loss incident.
        if r["recording_file_path"]:
            full_path = os.path.join(RECORDINGS_DIR, secure_filename(r["cls_id"]), r["recording_file_path"])
            r["file_exists"] = os.path.exists(full_path)
        else:
            r["file_exists"] = False

    return render_template(
        "settings_telephony_recordings.html",
        result=result, filters=f, company_wide=company_wide,
        date_preset_order=DATE_PRESET_ORDER, date_preset_labels=DATE_PRESET_LABELS,
        lead_owner_options=cls_db.get_distinct_owners(),
        activity_owner_options=cls_db.get_all_users_detailed(),
    )


@app.route("/settings/telephony/recordings/<int:activity_id>/delete", methods=["POST"])
@login_required
@admin_required
def settings_telephony_recording_delete(activity_id):
    """
    v0.24 — deletes ONE call_recording row AND its underlying file
    together. Unlike cls_call_recording_audit.py's CLI tool (which
    deliberately separates row-deletion from file-deletion for careful
    incident-response review), a web admin clicking "Delete" here has
    already reviewed the row on-screen (lead, status, duration, played
    the audio) — one deliberate, confirmed action removes both. Calls
    cls_db.delete_call_recording_activity() UNCHANGED — the same
    function the CLI audit script uses, not a duplicate.
    """
    activities = cls_db.list_call_recording_activities()
    match = next((a for a in activities if a["activity_id"] == activity_id), None)

    ok, msg = cls_db.delete_call_recording_activity(activity_id)
    if ok and match and match.get("recording_file_path"):
        file_path = os.path.join(
            RECORDINGS_DIR, secure_filename(match["cls_id"]), match["recording_file_path"]
        )
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                _log(f"settings_telephony_recording_delete: could not remove {file_path}: {e}", "WARNING")

    flash(msg, "success" if ok else "error")
    return redirect(url_for("settings_telephony_recordings"))


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
        projects=cls_db.get_all_bucket_names(),
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
        projects=cls_db.get_all_bucket_names(),
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
# PHASE B TELEPHONY API  (v0.21) — token auth, NOT session-cookie auth
# ─────────────────────────────────────────────────────────────
# The Android app's job is dumb and simple: report call-log metadata
# (never files) to report-calls below, then upload ONLY the specific
# recordings the server said matched a lead. See
# C:\CLS\TELEPHONY_RECORDING_POLICY.md for the locked scope rule these
# two endpoints enforce, and cls_db.py v2.33's changelog for the schema.

@app.route("/api/telephony/report-calls", methods=["POST"])
@token_required
def api_telephony_report_calls():
    """
    Body: {"calls": [{"number": "...", "timestamp": "YYYY-MM-DD HH:MM:SS",
    "duration": <seconds>, "direction": "INCOMING"/"OUTGOING"/...}, ...]}

    Every entry is normalized + matched via cls_db.record_call_log_entry()
    (reuses norm_phone()/find_match() — no new matching logic) and logged
    to call_log_staging regardless of outcome. The response contains
    ONLY matched entries plus this user's configured recording folder —
    unmatched numbers are never returned to the app and are never
    persisted anywhere but call_log_staging.
    """
    user = g.telephony_user
    body = request.get_json(silent=True) or {}
    calls = body.get("calls", [])
    if not isinstance(calls, list):
        return jsonify({"error": "'calls' must be a list."}), 400

    matched = []
    for entry in calls:
        if not isinstance(entry, dict):
            continue
        number = str(entry.get("number", "")).strip()
        timestamp = str(entry.get("timestamp", "")).strip()
        duration = entry.get("duration", 0)
        direction = str(entry.get("direction", "")).strip()
        if not number or not timestamp:
            continue
        result = cls_db.record_call_log_entry(user["user_id"], number, timestamp, duration, direction)
        if result["matched"]:
            matched.append({
                "lead_id": result["cls_id"],
                "call_timestamp": result["call_timestamp"],
                "duration_seconds": result["duration_seconds"],
            })

    return jsonify({
        "recording_folder_path": cls_db.get_recording_path(user["user_id"]),
        "matched": matched,
    })


@app.route("/api/telephony/upload-recording", methods=["POST"])
@token_required
def api_telephony_upload_recording():
    """
    Multipart form: file field 'recording', plus 'lead_id',
    'call_timestamp', 'duration' fields. Only called by the app for
    entries this user's own prior report-calls response marked matched.

    Validates lead_id is a real lead, saves the file under
    RECORDINGS_DIR/<lead_id>/<safe filename>, and logs it to that
    lead's activity timeline via cls_db.log_call_recording() with
    created_at backdated to the real call time (not upload time).
    matched_phone is taken from the lead's OWN stored phone_norm, not
    from client input — that's the number that actually matched.

    recording_file_path is stored as JUST the filename (not lead_id/
    filename) — the lead_id half of the path is already the row's own
    cls_id, and lead_detail.html's <audio> src builds the URL from both
    separately (url_for('serve_recording', lead_id=a.cls_id,
    filename=a.recording_file_path)), so there's no path-separator
    (Windows "\\" vs URL "/") ambiguity to resolve in the template.
    """
    user = g.telephony_user
    lead_id = request.form.get("lead_id", "").strip()
    call_timestamp = request.form.get("call_timestamp", "").strip()
    duration_raw = request.form.get("duration", "0").strip()
    uploaded = request.files.get("recording")

    if not lead_id or not call_timestamp or not uploaded:
        return jsonify({
            "success": False,
            "message": "lead_id, call_timestamp, and recording file are all required."
        }), 400

    lead = cls_db.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "message": "Unknown lead_id."}), 404

    safe_lead_id = secure_filename(lead_id)

    # v0.23 — Bug 2 fix, corrected: a retried upload for a call already
    # logged (e.g. the app crashes after a successful upload but before it
    # saves its own sync watermark) must not create a second identical
    # activity_log row — confirmed real via a repeat-sync duplicate during
    # testing. v0.22's first cut checked ROW existence only, which turned
    # out to be wrong on its own: recordings were accidentally deleted
    # from disk on 2026-07-31 (unrelated ops mistake, files only, no DB
    # rows touched) while their activity_log rows survived — a
    # row-exists-only check would have permanently blocked ever recovering
    # them via re-sync, since the row "existing" would always look like a
    # duplicate. Now checks whether the row's recorded file is ACTUALLY
    # still on disk: row+file both present -> genuine duplicate, skip:
    # row present but file missing -> recovery, fall through and UPDATE
    # that same row instead of inserting a second one.
    existing_file_path = cls_db.get_call_recording_file_path(lead_id, call_timestamp)
    recovering_missing_file = False
    if existing_file_path:
        existing_full_path = os.path.join(RECORDINGS_DIR, safe_lead_id, existing_file_path)
        if os.path.exists(existing_full_path):
            return jsonify({
                "success": True,
                "message": "Already logged for this call — duplicate upload skipped."
            })
        recovering_missing_file = True

    try:
        duration_seconds = int(float(duration_raw))
    except ValueError:
        duration_seconds = 0

    safe_name = secure_filename(uploaded.filename) or f"{call_timestamp.replace(':', '-').replace(' ', '_')}.mp3"
    lead_dir = os.path.join(RECORDINGS_DIR, safe_lead_id)
    os.makedirs(lead_dir, exist_ok=True)
    uploaded.save(os.path.join(lead_dir, safe_name))

    if recovering_missing_file:
        ok, msg = cls_db.update_call_recording_file(
            lead_id, call_timestamp, safe_name, duration_seconds, lead.get("phone_norm"),
        )
    else:
        # v0.40 — direction (INCOMING/OUTGOING) was already staged in
        # call_log_staging by report-calls; look it up by the same
        # (lead_id, call_timestamp) match key and carry it through onto
        # the activity_log row. No match -> None, never blocks the upload.
        direction = cls_db.get_call_direction(lead_id, call_timestamp)
        ok, msg = cls_db.log_call_recording(
            lead_id, user["email"], safe_name,
            duration_seconds, lead.get("phone_norm"), call_timestamp,
            direction=direction,
        )
    return jsonify({"success": ok, "message": msg})


@app.route("/recordings/<lead_id>/<path:filename>")
@login_required
def serve_recording(lead_id, filename):
    """
    v0.21 — authenticated playback for the <audio> player in
    lead_detail.html's timeline. Deliberately @login_required, NOT
    @token_required — this is for a logged-in human viewing the CRM in
    a browser/WebView, not the app's own upload flow.

    Gated by the same READ condition lead_detail() itself uses to decide
    whether this lead's activity timeline (and therefore any
    call_recording entry) is shown at all — can_write OR
    can_view_all_leads — NOT _check_lead_ownership, which is the
    stricter WRITE-only gate. Conflating the two would 403 a manager/
    oversight viewer who can already see this exact recording referenced
    on the lead's page. See _is_lead_owner_or_admin()'s docstring on why
    read and write are deliberately separate checks in this file.
    """
    lead = cls_db.get_lead_by_id(lead_id)
    if not lead:
        abort(404)
    user = cls_db.get_user_by_id(session["user_id"])
    can_read = _is_lead_owner_or_admin(lead, user) or cls_db.can_view_all_leads(user["role"])
    if not can_read:
        abort(403, description="This lead isn't assigned to you.")
    return send_from_directory(
        os.path.join(RECORDINGS_DIR, secure_filename(lead_id)),
        filename
    )


# ─────────────────────────────────────────────────────────────
# APX ATTENDANCE  —  v0.9 pilot, Build Order Step 2 (v0.28)
# ─────────────────────────────────────────────────────────────
# SIBLING module to the lead-management routes above — own prefix
# (/attendance, /settings/attendance), own data (cls_db.py v2.38/2.39).
# Nothing here reads or writes leads/activity_log/assignments.
#
# Login/Logout have NO native camera code yet (that's a later build-
# order step) — both buttons feature-detect window.AndroidBridge and
# call .punchIn()/.punchOut() if present, else show a "use the mobile
# app" message. IMPORTANT: android_pilot's CURRENT AndroidBridge (v9,
# openDeviceSyncSettings only) does NOT have punchIn/punchOut yet
# either, so today this correctly falls back to the message even
# inside the native app's WebView — that's expected until the Android
# build-order step ships those two bridge methods, not a bug here.
#
# No /api/attendance/* token-auth endpoints in this step (Build Order
# Step 4) — Weekoff/Leave/Correction Request below are plain
# session-cookie form POSTs, same auth as every other route in this file.

def _month_nav(year, month):
    """Prev/next (year, month) pairs for the mini-calendar's < > links."""
    first_of_month = datetime(year, month, 1)
    prev_month_date = first_of_month - timedelta(days=1)
    next_month_date = (first_of_month + timedelta(days=32)).replace(day=1)
    return (prev_month_date.year, prev_month_date.month,
            next_month_date.year, next_month_date.month)


@app.route("/attendance")
@login_required
def attendance_home():
    """
    v0.28 — Employee-facing Attendance page: today's status, this
    month's mini calendar (calendar.monthcalendar — Monday-start weeks,
    0 = day outside the month), and the Login/Logout/Weekoff/Leave/
    Correction Request buttons. ?year=&month= pick the calendar month
    (defaults to the current month); invalid/missing values silently
    fall back to today rather than erroring.

    v0.38 — Phase 1: an admin session hitting this route (i.e. the nav
    drawer's "Attendance" link) now redirects straight to
    settings_attendance_today() ("Who's Present Today") instead of
    rendering this page's admin card. Checked as the LITERAL
    role=='admin' string, matching attendance.html's own gate (not
    OVERSIGHT_ROLES/can_view_all_leads) — manager is unaffected and
    still gets the normal employee view below. The admin card in
    attendance.html is left in place (Settings & Attendance button
    only, per that template's own changelog) as a harmless fallback;
    with this redirect in place it is not actually reachable via the
    nav link.
    """
    user = cls_db.get_user_by_id(session["user_id"])
    if user["role"] == "admin":
        return redirect(url_for("settings_attendance_today"))
    today_dt = datetime.now()
    today = today_dt.strftime("%Y-%m-%d")
    try:
        year = int(request.args.get("year", today_dt.year))
        month = int(request.args.get("month", today_dt.month))
        if not (1 <= month <= 12):
            raise ValueError
    except ValueError:
        year, month = today_dt.year, today_dt.month

    today_status = cls_db.get_attendance_for_date(user["user_id"], today)
    month_data = cls_db.get_attendance_month(user["user_id"], year, month)
    weeks = calendar.monthcalendar(year, month)
    holidays = {
        h["holiday_date"] for h in cls_db.list_attendance_holidays()
        if h["holiday_date"].startswith(f"{year:04d}-{month:02d}")
    }
    prev_year, prev_month, next_year, next_month = _month_nav(year, month)

    return render_template(
        "attendance.html",
        today=today,
        today_status=today_status,
        year=year, month=month,
        month_name=calendar.month_name[month],
        weeks=weeks,
        month_data=month_data,
        holidays=holidays,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        correction_fields=cls_db.ATTENDANCE_CORRECTION_FIELDS,
        attendance_statuses=cls_db.ATTENDANCE_STATUSES,
    )


# ── v0.36 Chunk B: Weekoff/Leave rebuilt as range-capable, duplicate- ──
# protected self-service (see cls_db.py v2.45 changelog for the full
# design). PAUSED, not deleted, per this repo's convention — the two
# OLD single-day form-POST routes below are superseded by the two NEW
# JSON routes further down (attendance_weekoff_submit / attendance_
# leave_submit). Left live, these would let a submission bypass the
# new weekoff_log/leave_requests duplicate-protection entirely, since
# they call cls_db.set_self_service_attendance_status() directly with
# no knowledge of the new tables.
#
# @app.route("/attendance/weekoff", methods=["POST"])
# @login_required
# def attendance_weekoff():
#     user = cls_db.get_user_by_id(session["user_id"])
#     date_str = (request.form.get("attendance_date") or "").strip() or datetime.now().strftime("%Y-%m-%d")
#     ok, message = cls_db.set_self_service_attendance_status(user["user_id"], date_str, "weekoff", _actor())
#     flash(message, "success" if ok else "error")
#     return redirect(url_for("attendance_home"))
#
#
# @app.route("/attendance/leave", methods=["POST"])
# @login_required
# def attendance_leave():
#     user = cls_db.get_user_by_id(session["user_id"])
#     date_str = (request.form.get("attendance_date") or "").strip() or datetime.now().strftime("%Y-%m-%d")
#     ok, message = cls_db.set_self_service_attendance_status(user["user_id"], date_str, "leave", _actor())
#     flash(message, "success" if ok else "error")
#     return redirect(url_for("attendance_home"))


@app.route("/attendance/weekoff/submit", methods=["POST"])
@login_required
def attendance_weekoff_submit():
    """
    (v0.36) Chunk B — NEW JSON endpoint backing attendance.html's
    Weekoff/Leave button+modal (replaces the PAUSED attendance_weekoff
    form-POST above). Always today's date, computed server-side — the
    UI sends no date field by design (spec: "no picker"). user_id comes
    ONLY from session — self-service, a user can only submit for
    themselves, never for anyone else. Returns JSON {success, message}.
    """
    user_id = session["user_id"]
    date_str = datetime.now().strftime("%Y-%m-%d")
    ok, message = cls_db.submit_weekoff(user_id, date_str, _actor())
    return jsonify({"success": ok, "message": message})


@app.route("/attendance/leave/submit", methods=["POST"])
@login_required
def attendance_leave_submit():
    """
    (v0.36) Chunk B — NEW JSON endpoint backing attendance.html's
    Weekoff/Leave button+modal (replaces the PAUSED attendance_leave
    form-POST above). Expects JSON body {"dates": [...]} ('YYYY-MM-DD'
    strings) from the multi-select calendar. Rejects anything that
    isn't a well-formed date string here (never trusts the client)
    before handing off to cls_db.submit_leave(), which does the
    today-or-future + overlap/duplicate validation. user_id comes ONLY
    from session. Returns JSON {success, message}.
    """
    user_id = session["user_id"]
    payload = request.get_json(silent=True) or {}
    raw_dates = payload.get("dates") or []
    dates = []
    for d in raw_dates:
        try:
            datetime.strptime(d, "%Y-%m-%d")
            dates.append(d)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid date in selection."}), 400
    ok, message = cls_db.submit_leave(user_id, dates, _actor())
    return jsonify({"success": ok, "message": message})


@app.route("/attendance/correction-request", methods=["POST"])
@login_required
def attendance_correction_request():
    user = cls_db.get_user_by_id(session["user_id"])
    date_str = (request.form.get("attendance_date") or "").strip()
    field_changed = (request.form.get("field_changed") or "").strip()
    new_value = (request.form.get("new_value") or "").strip()
    note = (request.form.get("request_note") or "").strip()

    if not date_str or not new_value:
        flash("Date and new value are both required.", "error")
        return redirect(url_for("attendance_home"))

    ok, message = cls_db.create_correction_request(
        user["user_id"], date_str, field_changed, new_value, note, _actor()
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("attendance_home"))


@app.route("/settings/attendance")
@login_required
@admin_required
def settings_attendance():
    """v0.28 — Attendance admin hub. Same card-grid pattern as
    settings.html. Dashboard/calendar-with-colors/export tile is
    deliberately NOT here yet — that's Build Order Step 3."""
    return render_template("settings_attendance.html")


@app.route("/settings/attendance/holidays", methods=["GET", "POST"])
@login_required
@admin_required
def settings_attendance_holidays():
    if request.method == "POST":
        holiday_date = (request.form.get("holiday_date") or "").strip()
        label = (request.form.get("label") or "").strip()
        if not holiday_date:
            flash("Date is required.", "error")
        else:
            cls_db.add_attendance_holiday(holiday_date, label)
            flash(f"Holiday saved for {holiday_date}.", "success")
        return redirect(url_for("settings_attendance_holidays"))

    return render_template(
        "settings_attendance_holidays.html",
        holidays=cls_db.list_attendance_holidays(),
    )


@app.route("/settings/attendance/holidays/<holiday_date>/delete", methods=["POST"])
@login_required
@admin_required
def settings_attendance_holiday_delete(holiday_date):
    cls_db.delete_attendance_holiday(holiday_date)
    flash(f"Holiday removed for {holiday_date}.", "success")
    return redirect(url_for("settings_attendance_holidays"))


@app.route("/settings/attendance/today")
@login_required
@admin_required
def settings_attendance_today():
    """
    (v0.37) Chunk C — admin-only "who's present today" view. Deliberately
    @admin_required, NOT the looser can_view_all_leads()/OVERSIGHT_ROLES
    gate the Dashboard/Export pair uses — matches the Holidays/
    Corrections/Projects convention, per Srikanth's explicit choice.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "settings_attendance_today.html",
        today=today,
        overview=cls_db.get_today_attendance_overview(today),
    )


@app.route("/settings/attendance/corrections", methods=["GET", "POST"])
@login_required
@admin_required
def settings_attendance_corrections():
    """v0.28 — Approve/reject queue. POST handles both actions via a
    single 'action' field ('approve'/'reject') on the same route,
    mirroring settings_users()'s toggle-active pattern (one hidden
    field deciding which of two outcomes a shared handler applies)."""
    if request.method == "POST":
        try:
            correction_id = int(request.form.get("correction_id", ""))
        except ValueError:
            flash("Invalid request.", "error")
            return redirect(url_for("settings_attendance_corrections"))

        approve = request.form.get("action") == "approve"
        ok, message = cls_db.resolve_attendance_correction(correction_id, approve, _actor())
        flash(message, "success" if ok else "error")
        return redirect(url_for("settings_attendance_corrections"))

    all_corrections = cls_db.list_attendance_corrections()
    return render_template(
        "settings_attendance_corrections.html",
        pending=[c for c in all_corrections if c["status"] == "pending"],
        resolved=[c for c in all_corrections if c["status"] != "pending"],
        # v0.37 Chunk C — employee dropdown for the new proactive-
        # exemption form section at the bottom of this template. Same
        # get_all_users_detailed() source as the Dashboard's employee
        # filter.
        employees=cls_db.get_all_users_detailed(),
        correction_fields=cls_db.ATTENDANCE_CORRECTION_FIELDS,
        attendance_statuses=cls_db.ATTENDANCE_STATUSES,
    )


@app.route("/settings/attendance/exempt", methods=["POST"])
@login_required
@admin_required
def settings_attendance_exempt():
    """
    (v0.37) Chunk C — proactive admin exemption form POST, submitted
    from the new section at the bottom of settings_attendance_
    corrections.html. Thin wrapper over cls_db.apply_admin_attendance_
    exemption() — see that function's docstring for exactly how it
    reuses create_correction_request()/resolve_attendance_correction()
    unmodified, back-to-back, with neither existing function changed.
    """
    try:
        user_id = int(request.form.get("user_id", ""))
    except ValueError:
        flash("Select an employee.", "error")
        return redirect(url_for("settings_attendance_corrections"))

    date_str = (request.form.get("attendance_date") or "").strip()
    field_changed = (request.form.get("field_changed") or "").strip()
    new_value = (request.form.get("new_value") or "").strip()
    note = (request.form.get("request_note") or "").strip()

    if not date_str or not new_value:
        flash("Date and new value are required.", "error")
        return redirect(url_for("settings_attendance_corrections"))

    ok, message = cls_db.apply_admin_attendance_exemption(
        user_id, date_str, field_changed, new_value, note, _actor()
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("settings_attendance_corrections"))


@app.route("/settings/attendance/projects", methods=["GET", "POST"])
@login_required
@admin_required
def settings_attendance_projects():
    if request.method == "POST":
        project_bucket = (request.form.get("project_bucket") or "").strip()
        latitude = (request.form.get("latitude") or "").strip()
        longitude = (request.form.get("longitude") or "").strip()
        radius_meters = (request.form.get("radius_meters") or "").strip()

        if not project_bucket:
            flash("Choose a project.", "error")
            return redirect(url_for("settings_attendance_projects"))
        try:
            lat_f = float(latitude) if latitude else None
            lng_f = float(longitude) if longitude else None
            radius_i = int(radius_meters) if radius_meters else 1500
        except ValueError:
            flash("Latitude/longitude must be numbers, radius must be a whole number of meters.", "error")
            return redirect(url_for("settings_attendance_projects"))

        cls_db.set_attendance_project_location(project_bucket, lat_f, lng_f, radius_i)
        flash(f"Location saved for {project_bucket}.", "success")
        return redirect(url_for("settings_attendance_projects"))

    locations = {l["project_bucket"]: l for l in cls_db.list_attendance_project_locations()}
    return render_template(
        "settings_attendance_projects.html",
        projects=cls_db.get_all_bucket_names(),
        locations=locations,
    )


@app.route("/settings/users/<int:user_id>/assign-project", methods=["POST"])
@login_required
@admin_required
def settings_user_assign_project(user_id):
    """v0.28 — sets users.assigned_project (cls_db.py v2.38) from a
    small per-row form on settings_users.html, rather than a separate
    "edit user" screen — touches one existing template instead of
    adding a new one, per the v0.9 spec's explicit "pick whichever
    touches fewer templates" call."""
    project_bucket = (request.form.get("assigned_project") or "").strip() or None
    cls_db.set_user_assigned_project(user_id, project_bucket)
    flash("Project assignment saved.", "success")
    return redirect(url_for("settings_users"))


# ── Attendance Dashboard (v0.29, Build Order Step 3) ──
# NOT @admin_required — visibility follows the SAME OVERSIGHT_ROLES
# convention as every other dashboard/report in this app
# (cls_db.can_view_all_leads), because a salesperson must reach their
# own scoped view here too (linked from attendance.html, not just from
# the admin-only Settings > Attendance hub). The view route and its
# Excel export share these two helpers so the exported file can never
# drift from what's on screen.

def _parse_dashboard_month_args():
    today_dt = datetime.now()
    try:
        year = int(request.args.get("year", today_dt.year))
        month = int(request.args.get("month", today_dt.month))
        if not (1 <= month <= 12):
            raise ValueError
    except ValueError:
        year, month = today_dt.year, today_dt.month
    return year, month


def _resolve_attendance_dashboard_scope(user, is_oversight):
    """A salesperson's ?user_id is ALWAYS ignored and force-replaced
    with their own id — never trust the query string for scope, same
    fails-closed posture as every other owner-scoped route in this
    file. Only an oversight role (admin/manager) may pick a specific
    employee, or leave it blank for the company-wide "All employees"
    totals table."""
    if not is_oversight:
        return user["user_id"]
    raw = (request.args.get("user_id") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@app.route("/settings/attendance/dashboard")
@login_required
def settings_attendance_dashboard():
    """
    v0.29 — Build Order Step 3. Monthly calendar (color-coded: green=
    present, amber=late, red=absent, grey=weekoff, blue=leave, ORANGE
    border=geofence breach — Srikanth's specified palette) + totals
    row, month/year picker, an employee filter (oversight roles only),
    and Export Excel / Print-Save-as-PDF buttons. The calendar only
    renders when exactly one employee is in scope (a company-wide
    "All employees" calendar grid doesn't make sense) — the totals
    table always renders, scoped to that one employee's row or every
    active employee.
    """
    user = cls_db.get_user_by_id(session["user_id"])
    is_oversight = cls_db.can_view_all_leads(user["role"])
    year, month = _parse_dashboard_month_args()
    selected_user_id = _resolve_attendance_dashboard_scope(user, is_oversight)

    totals = cls_db.get_attendance_totals_for_month(year, month, owner_scope=selected_user_id)

    calendar_weeks = None
    calendar_month_data = {}
    calendar_user_name = None
    holidays = set()
    if selected_user_id is not None:
        calendar_weeks = calendar.monthcalendar(year, month)
        calendar_month_data = cls_db.get_attendance_month(selected_user_id, year, month)
        target_user = cls_db.get_user_by_id(selected_user_id)
        calendar_user_name = target_user["full_name"] if target_user else "(unknown)"
        holidays = {
            h["holiday_date"] for h in cls_db.list_attendance_holidays()
            if h["holiday_date"].startswith(f"{year:04d}-{month:02d}")
        }

    employees = [u for u in cls_db.get_all_users_detailed() if u["active"] and u["role"] != "admin"] if is_oversight else []
    current_year = datetime.now().year

    return render_template(
        "settings_attendance_dashboard.html",
        year=year, month=month,
        month_names=calendar.month_name,
        year_options=list(range(current_year - 2, current_year + 1)),
        is_oversight=is_oversight,
        employees=employees,
        selected_user_id=selected_user_id,
        totals=totals,
        attendance_statuses=cls_db.ATTENDANCE_STATUSES,
        calendar_weeks=calendar_weeks,
        calendar_month_data=calendar_month_data,
        calendar_user_name=calendar_user_name,
        holidays=holidays,
    )


def _attendance_dashboard_report(year, month, selected_user_id):
    """Shared by settings_attendance_dashboard() and its Excel export
    below — builds the exact cls_reports.build_report()-shaped dict
    export_to_excel() expects (title, date_from/date_to, caveat,
    columns, rows), reusing that EXISTING export engine rather than
    writing a new one, per the spec's explicit instruction."""
    totals = cls_db.get_attendance_totals_for_month(year, month, owner_scope=selected_user_id)
    columns = (
        [("full_name", "Name")]
        + [(s, s.replace("_", " ").title()) for s in cls_db.ATTENDANCE_STATUSES]
        + [("geofence_breaches", "Geofence Breaches")]
    )
    last_day = calendar.monthrange(year, month)[1]
    return {
        "title": f"Attendance — {calendar.month_name[month]} {year}",
        "date_from": f"{year:04d}-{month:02d}-01",
        "date_to": f"{year:04d}-{month:02d}-{last_day:02d}",
        "caveat": None,
        "columns": columns,
        "rows": totals,
    }


@app.route("/settings/attendance/dashboard/export.xlsx")
@login_required
def settings_attendance_dashboard_export():
    user = cls_db.get_user_by_id(session["user_id"])
    is_oversight = cls_db.can_view_all_leads(user["role"])
    year, month = _parse_dashboard_month_args()
    selected_user_id = _resolve_attendance_dashboard_scope(user, is_oversight)

    report = _attendance_dashboard_report(year, month, selected_user_id)
    try:
        buf = cls_reports.export_to_excel(report)
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("settings_attendance_dashboard", year=year, month=month,
                                 user_id=selected_user_id or ""))

    filename = report["title"].lower().replace(" ", "-").replace("/", "-") + ".xlsx"
    return send_file(
        buf, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Token-auth API endpoints (v0.30, Build Order Step 4) ──
# @token_required / g.telephony_user REUSED EXACTLY, same mechanism as
# the 2 existing Telephony endpoints below — one bearer token per user,
# not a second auth scheme for Attendance. No PunchActivity.kt/
# AttendanceWorker.kt exist yet (Steps 5/6) — these 4 endpoints are
# tested here with curl/Postman-equivalent requests only.

def _parse_punch_request():
    """Shared by punch-in/punch-out: validates the multipart body and
    resolves the punch timestamp. Returns (uploaded_file, lat, lng, ts,
    date_str, error_response_or_None)."""
    uploaded = request.files.get("photo")
    lat_raw = request.form.get("lat", "")
    lng_raw = request.form.get("lng", "")
    client_ts = (request.form.get("client_ts") or "").strip()

    if not uploaded or not lat_raw or not lng_raw:
        return None, None, None, None, None, (
            jsonify({"success": False, "message": "photo, lat, and lng are all required."}), 400
        )
    try:
        lat, lng = float(lat_raw), float(lng_raw)
    except ValueError:
        return None, None, None, None, None, (
            jsonify({"success": False, "message": "lat/lng must be numbers."}), 400
        )

    # client_ts is the phone's own capture time (matches the reference
    # spec's "never silently submit without coordinates" spirit applied
    # to time too) — falls back to server time if missing/unparseable,
    # since a punch must never fail over a timestamp glitch.
    try:
        punch_dt = datetime.strptime(client_ts, "%Y-%m-%d %H:%M:%S") if client_ts else datetime.now()
    except ValueError:
        punch_dt = datetime.now()
    ts = punch_dt.strftime("%Y-%m-%d %H:%M:%S")

    return uploaded, lat, lng, punch_dt, ts, None


@app.route("/api/attendance/punch-in", methods=["POST"])
@token_required
def api_attendance_punch_in():
    """
    v0.30 — Multipart form: 'photo' file, 'lat', 'lng' (required),
    optional 'client_ts' ('YYYY-MM-DD HH:MM:SS'). Geofence breach is
    computed and FLAGGED in the response — see cls_db.check_geofence_
    breach()'s docstring on why it never blocks. Photo is saved to disk
    (never a DB blob) at ATTENDANCE_PHOTOS_DIR/<user_id>/<date>_in.jpg,
    overwriting any earlier same-day punch-in photo — consistent with
    the attendance row itself being an UPDATE, not a new row, on a
    same-day re-punch (cls_db.record_punch()).

    v0.35 — the raw upload is passed through cls_attendance_photo.
    render_punch_photo() before being written to disk (map-thumbnail
    watermark, self-healing fallback chain — see that module's
    docstring). render_punch_photo() never raises, so this route's
    behavior on a map/image failure is unchanged from before: the punch
    still saves, just with a plainer photo.

    FCM push-on-punch is NOT implemented here — that's the separate,
    later FCM-wiring build-order step (needs Srikanth's one-time
    Firebase project setup first); register-fcm-token below only
    stores tokens, nothing sends to them yet.
    """
    user = g.telephony_user
    uploaded, lat, lng, punch_dt, ts, error = _parse_punch_request()
    if error:
        return error
    date_str = ts[:10]

    geofence_breach = cls_db.check_geofence_breach(user.get("assigned_project"), lat, lng)
    status, late_minutes = cls_db.compute_punch_in_timing(punch_dt)

    user_dir = os.path.join(ATTENDANCE_PHOTOS_DIR, secure_filename(str(user["user_id"])))
    os.makedirs(user_dir, exist_ok=True)
    photo_filename = f"{date_str}_in.jpg"
    rendered_photo = cls_attendance_photo.render_punch_photo(uploaded.read(), lat, lng, ts)
    with open(os.path.join(user_dir, photo_filename), "wb") as f:
        f.write(rendered_photo)

    cls_db.record_punch(
        user["user_id"], "in", date_str, ts, lat, lng, geofence_breach, photo_filename,
        status=status, late_minutes=late_minutes,
    )

    return jsonify({
        "success": True, "status": status, "late_minutes": late_minutes,
        "geofence_breach": geofence_breach,
    })


@app.route("/api/attendance/punch-out", methods=["POST"])
@token_required
def api_attendance_punch_out():
    """v0.30 — same request shape as punch-in, writing only the
    logout_* columns — status/late_minutes are computed once, at
    login, and are never touched by a logout (cls_db.record_punch()).

    v0.35 — same cls_attendance_photo.render_punch_photo() pass-through
    as punch-in above."""
    user = g.telephony_user
    uploaded, lat, lng, punch_dt, ts, error = _parse_punch_request()
    if error:
        return error
    date_str = ts[:10]

    geofence_breach = cls_db.check_geofence_breach(user.get("assigned_project"), lat, lng)

    user_dir = os.path.join(ATTENDANCE_PHOTOS_DIR, secure_filename(str(user["user_id"])))
    os.makedirs(user_dir, exist_ok=True)
    photo_filename = f"{date_str}_out.jpg"
    rendered_photo = cls_attendance_photo.render_punch_photo(uploaded.read(), lat, lng, ts)
    with open(os.path.join(user_dir, photo_filename), "wb") as f:
        f.write(rendered_photo)

    cls_db.record_punch(user["user_id"], "out", date_str, ts, lat, lng, geofence_breach, photo_filename)

    return jsonify({"success": True, "geofence_breach": geofence_breach})


@app.route("/api/attendance/location-ping", methods=["POST"])
@token_required
def api_attendance_location_ping():
    """v0.30 — JSON body {lat, lng, ts}. Silently no-ops (200,
    success:false) if this user has no OPEN attendance row today
    (cls_db.record_location_ping()) — a stray ping after logout or a
    killed WorkManager job (Step 6, not built yet) can never corrupt
    data. Not an error status: the app has no useful recovery action to
    take on this response either way."""
    user = g.telephony_user
    body = request.get_json(silent=True) or {}
    ts = str(body.get("ts", "")).strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        lat, lng = float(body.get("lat")), float(body.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "lat and lng are required and must be numbers."}), 400

    accepted = cls_db.record_location_ping(user["user_id"], lat, lng, ts)
    return jsonify({"success": accepted})


@app.route("/api/attendance/register-fcm-token", methods=["POST"])
@token_required
def api_attendance_register_fcm_token():
    """v0.30 — JSON body {fcm_token}. Called on app start and on
    Firebase's token-refresh callback (FCM-wiring build-order step, not
    built yet — this endpoint just stores whatever it's given so that
    later step has something to send to)."""
    user = g.telephony_user
    body = request.get_json(silent=True) or {}
    fcm_token = str(body.get("fcm_token", "")).strip()
    if not fcm_token:
        return jsonify({"success": False, "message": "fcm_token is required."}), 400
    cls_db.set_fcm_token(user["user_id"], fcm_token)
    return jsonify({"success": True})


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
# APK DISTRIBUTION  (v0.25) — android_pilot's CI push + team download
# ─────────────────────────────────────────────────────────────
# Both routes are intentionally OUTSIDE the session-cookie login system —
# upload is CI-only (a build machine, never a browser), download must
# work for a team member who isn't a CRM user yet on that phone. Neither
# uses @login_required/@admin_required; each has its OWN secret check
# instead (see APK_UPLOAD_SECRET/APK_DOWNLOAD_SECRET above).

@app.route("/api/apk/upload", methods=["POST"])
def api_apk_upload():
    """
    v0.25 — CI-only. Multipart form field 'file'. Auth via
    'X-Upload-Secret' header, compared with hmac.compare_digest (not
    Python's '==') to avoid a timing side-channel on the secret —
    cheap and correct even though the actual sensitivity here is low
    (this endpoint can only overwrite the APK file, nothing else).
    Always overwrites APK_RELEASES_DIR/APK_FILENAME — no versioned
    filenames, so the public download link never changes.
    """
    provided = request.headers.get("X-Upload-Secret", "")
    if not APK_UPLOAD_SECRET or not provided or not hmac.compare_digest(provided, APK_UPLOAD_SECRET):
        abort(403, description="Invalid or missing upload secret.")

    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"success": False, "message": "No file provided (expected form field 'file')."}), 400

    os.makedirs(APK_RELEASES_DIR, exist_ok=True)
    dest_path = os.path.join(APK_RELEASES_DIR, APK_FILENAME)
    uploaded.save(dest_path)
    size_bytes = os.path.getsize(dest_path)

    # v0.25 — small rolling log, same one-line-per-event plain-append
    # style as cls_db.write_job_result(), but its OWN file rather than
    # job_results.txt (that file is specifically for the A-D pipeline
    # jobs per this project's convention — this isn't part of that
    # pipeline). Lets Srikanth sanity-check "was a new build actually
    # received" without opening GitHub at all.
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(APK_UPLOAD_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] APK Upload: SUCCESS — {size_bytes} bytes\n")
    except Exception:
        pass  # logging failure must never fail the upload itself

    return jsonify({"success": True, "size_bytes": size_bytes})


@app.route("/download/clspilot.apk")
def download_apk():
    """
    v0.25 — public, no login (see section note above). Gated by a
    query-string secret ('?key=...') instead — Srikanth's confirmed
    call: closes off the "URL leaks and is downloadable by anyone
    forever" exposure a fully predictable public path would have, while
    keeping the one-tap-on-a-phone install flow (no password prompt).
    A DIFFERENT secret from the upload endpoint's — see
    APK_DOWNLOAD_SECRET's comment above on why sharing one would be
    unsafe. If no build has been uploaded yet, returns a plain friendly
    message instead of a raw 404.
    """
    provided = request.args.get("key", "")
    if not APK_DOWNLOAD_SECRET or not provided or not hmac.compare_digest(provided, APK_DOWNLOAD_SECRET):
        abort(403, description="Invalid or missing download key.")

    dest_path = os.path.join(APK_RELEASES_DIR, APK_FILENAME)
    if not os.path.exists(dest_path):
        return "No build has been uploaded yet — check back after the next CI run.", 200

    return send_from_directory(
        APK_RELEASES_DIR, APK_FILENAME,
        mimetype="application/vnd.android.package-archive",
        as_attachment=True, download_name="clspilot.apk"
    )


# ─────────────────────────────────────────────────────────────
# META LEADGEN WEBHOOK  (v0.47)
# ─────────────────────────────────────────────────────────────
# Prerequisite for Meta App Review's webhook verification step, and a
# future replacement path for Job A's (meta_leads_fetcher.py) polling.
# GET is Meta's one-time (and re-run-on-demand) challenge-response
# handshake; POST is what Meta calls going forward whenever a lead
# comes in. Deliberately NOT @login_required — Meta's own servers call
# this, not a browser session. Verification/logging ONLY: no cls_db
# writes yet, on purpose — that's a separate, later task once routing
# design (how a webhook-delivered lead maps onto cls_db's existing
# Meta-lead upsert path) is finalized.

@app.route("/webhooks/meta-leadgen", methods=["GET", "POST"])
def meta_leadgen_webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == META_WEBHOOK_VERIFY_TOKEN:
            _log("Meta webhook verification succeeded")
            return challenge, 200
        else:
            _log("Meta webhook verification FAILED - token mismatch", "WARNING")
            return "Verification failed", 403

    # POST — logging, plus (v0.50) a best-effort write to the isolated
    # webhook_test_leads table for App Review's screencast requirement.
    # Never touches the real leads table / Job A/B/C.
    payload = request.get_json(silent=True) or {}
    _log(f"Meta leadgen webhook received: {payload}")
    try:
        cls_db.log_webhook_test_lead(payload)
    except Exception as e:
        _log(f"log_webhook_test_lead failed (non-fatal, webhook still returns 200): {e}", "WARNING")
    return "OK", 200


@app.route("/admin/webhook-test-leads")
@login_required
@admin_required
def admin_webhook_test_leads():
    """
    v0.50 — Meta App Review screencast support. Admin-only viewer for
    webhook_test_leads (isolated table, see cls_db.py v2.56) so a
    reviewer's test payload can be visually confirmed on screen. Read-only,
    no interaction with the real leads table or Job A/B/C.
    """
    return render_template("webhook_test_leads.html", rows=cls_db.get_webhook_test_leads())


@app.route("/admin/ads-insights-preview")
@login_required
@admin_required
def admin_ads_insights_preview():
    """
    v0.51 — Meta App Review screencast support: ads_read demo page.
    Read-only direct call to Meta's Graph API Insights endpoint — no
    cls_db interaction, no caching/storage, fetched live on every load
    (this is a demo page, not a production dashboard). Reuses
    cls_capi_core.GRAPH_API_VERSION rather than hardcoding a version
    number, since this codebase already hit one Graph API version
    deprecation (v19.0) and upgraded past it. Never raises — any
    failure (network, auth, rate limit, missing token) renders the
    template with an error message instead of a 500.
    """
    campaigns = []
    error = None
    if not META_SYSTEM_USER_TOKEN:
        error = "META_SYSTEM_USER_TOKEN is not set in .env"
    else:
        try:
            resp = requests.get(
                f"https://graph.facebook.com/{cls_capi_core.GRAPH_API_VERSION}/act_825098213089084/insights",
                params={
                    "fields": "impressions,spend,clicks,ctr,campaign_name",
                    "date_preset": "last_7d",
                    "access_token": META_SYSTEM_USER_TOKEN,
                },
                timeout=10,
            )
            result = resp.json()
            if resp.status_code == 200 and "data" in result:
                campaigns = result["data"]
            else:
                error = (result.get("error") or {}).get("message") or f"Unexpected response (HTTP {resp.status_code})"
        except Exception as e:
            error = str(e)

    return render_template("ads_insights_preview.html", campaigns=campaigns, error=error)


# ─────────────────────────────────────────────────────────────
# FACEBOOK LOGIN FOR BUSINESS  (v0.48)
# ─────────────────────────────────────────────────────────────
# Four routes required to satisfy Meta's Tech Provider / App Review
# checklist for "Facebook Login for Business": a Valid OAuth Redirect
# URI, a deauthorize callback, a data deletion callback, and (since the
# data deletion callback must point somewhere) a status page for it.
# None of these touch real lead data or cls_db — see module changelog
# above for the full reasoning on each.

def _verify_meta_signed_request(signed_request, app_secret):
    """
    Verifies a Meta signed_request per Meta's documented algorithm:
    "<base64url-sig>.<base64url-json-payload>", HMAC-SHA256 over the
    raw payload segment using the app secret. Returns the decoded
    payload dict if the signature checks out, else None. Shared by
    both the deauthorize and data-deletion routes below so the
    verification logic exists in exactly one place.
    """
    if not signed_request or not app_secret:
        return None
    try:
        encoded_sig, payload = signed_request.split(".", 1)
    except ValueError:
        return None

    def _b64url_decode(s):
        padding = "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s + padding)

    try:
        sig = _b64url_decode(encoded_sig)
        data = json.loads(_b64url_decode(payload))
    except Exception:
        return None

    expected_sig = hmac.new(
        app_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).digest()

    if not hmac.compare_digest(sig, expected_sig):
        return None

    return data


@app.route("/oauth/meta-callback", methods=["GET"])
def meta_oauth_callback():
    # No params processed, no auth — exists only because Meta's Tech
    # Provider setup requires at least one Valid OAuth Redirect URI on
    # file. Real OAuth logic, if ever needed, is a separate later task.
    return "Login complete. You may close this window.", 200


@app.route("/webhooks/meta-deauthorize", methods=["POST"])
def meta_deauthorize_webhook():
    signed_request = request.form.get("signed_request", "")
    data = _verify_meta_signed_request(signed_request, META_LEADGEN_APP_SECRET)

    if data is None:
        _log("Meta deauthorize callback FAILED - invalid signed_request", "WARNING")
        return "Invalid signed_request", 400

    user_id = data.get("user_id", "")
    _log(f"Meta deauthorize callback received for user_id={user_id}")
    return "OK", 200


@app.route("/webhooks/meta-data-deletion", methods=["POST"])
def meta_data_deletion_webhook():
    signed_request = request.form.get("signed_request", "")
    data = _verify_meta_signed_request(signed_request, META_LEADGEN_APP_SECRET)

    if data is None:
        _log("Meta data-deletion callback FAILED - invalid signed_request", "WARNING")
        return "Invalid signed_request", 400

    user_id = data.get("user_id", "")
    # secrets.token_hex(), not random — this code stands in for a real
    # deletion record, so it needs to be unguessable, not just unique.
    confirmation_code = secrets.token_hex(8)
    _log(f"Meta data-deletion request received for user_id={user_id}, "
         f"confirmation_code={confirmation_code}")

    return jsonify({
        "url": f"https://crm.asianbuild.in/data-deletion-status?id={confirmation_code}",
        "confirmation_code": confirmation_code,
    }), 200


@app.route("/data-deletion-status", methods=["GET"])
def data_deletion_status():
    """
    STUB — does not look up or act on any real deletion record (no such
    tracking exists in cls_db yet). Exists only so the URL the
    data-deletion callback hands back resolves to a real page instead
    of a 404, ahead of actual deletion-tracking design (separate task).
    """
    deletion_id = html.escape(request.args.get("id", ""))
    return (
        f"Deletion request {deletion_id} is being processed. "
        f"Contact us at sales1@asianbuild.in for status updates."
    ), 200


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
