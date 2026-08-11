# CLS/APX CRM — Changelog

## 2026-08-11
- CLS_CHANGELOG.md — created this session (Phase 1's commit); each
  phase below was appended as its own session completed, not batched
  at the end. Phase 6 of the 6-phase feature batch — this closes out
  the batch; see the "after all 6 phases" summary in that session for
  final version numbers and open items.
- bulk job history export (cls_db.py v2.53, app.py v0.46,
  settings_bulk_jobs.html v1.1) — new bulk_job_leads snapshot table:
  every bulk-reassign job now records the exact cls_ids it touched,
  atomically with its bulk_jobs row (create_bulk_job() now opens the
  transaction both inserts share and returns job_id — the only non-
  additive cls_db.py change this phase, confirmed with Srikanth before
  writing it). NEW per-job "Download" link on Past Bulk Jobs
  (/settings/bulk-jobs/<job_id>/export.xlsx), hidden for jobs that
  predate this migration ("Not available for jobs before this date").
  Phase 5 of the 6-phase feature batch.
- dashboard_today / dashboard_pipeline (app.py v0.45, cls_db.py v2.52,
  dashboard_today.html v0.8, dashboard_pipeline.html v0.9, NEW
  dashboard_today_drilldown.html) — every tile on both tabs is now
  clickable. Pipeline Analysis stage tiles reuse the existing leads_list
  "stages" filter (no new code). Today's Performance tiles drill into a
  new actor-scoped list per tile (5 new cls_db.py functions — Calls Made,
  Site Visits Scheduled/Conducted, Follow-ups Scheduled/Completed — all
  matching their tile's own actor-email scoping, deliberately NOT the
  owner-scoped get_site_visits_conducted() used by Export). Confirmed
  with Srikanth to build the fully-correct 5-function version rather
  than reuse a mismatched existing function. Phase 4 of the 6-phase
  feature batch.
- dashboard (app.py v0.44, dashboard.html v0.15) — new admin-only "Today's
  Attendance" card on the Stats Overview tab, borderless 2-column table
  (name, status), reusing cls_db.get_today_attendance_overview() — the
  same function settings_attendance_today() already calls, no new query.
  Phase 3 of the 6-phase feature batch.
- settings hub (settings.html v0.42) — new admin-only "Bulk job history"
  tile, links to the existing settings_bulk_jobs route/page. Additive only
  — the existing "Past Bulk Jobs" link inside Bulk Reassign is untouched.
  No route/logic change. Phase 2 of the 6-phase feature batch.
- attendance nav (app.py v0.43, attendance.html v0.33) — admin "Attendance"
  nav-drawer link now redirects straight to Who's Present Today
  (settings_attendance_today()) instead of the intermediate admin card;
  "Who's Present Today" button removed from that card (Settings &
  Attendance button stays). Phase 1 of the 6-phase feature batch.
