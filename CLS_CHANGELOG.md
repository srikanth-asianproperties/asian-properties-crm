# CLS/APX CRM — Changelog

## 2026-08-11
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
