# CLS/APX CRM — Changelog

## 2026-08-11
- settings hub (settings.html v0.42) — new admin-only "Bulk job history"
  tile, links to the existing settings_bulk_jobs route/page. Additive only
  — the existing "Past Bulk Jobs" link inside Bulk Reassign is untouched.
  No route/logic change. Phase 2 of the 6-phase feature batch.
- attendance nav (app.py v0.43, attendance.html v0.33) — admin "Attendance"
  nav-drawer link now redirects straight to Who's Present Today
  (settings_attendance_today()) instead of the intermediate admin card;
  "Who's Present Today" button removed from that card (Settings &
  Attendance button stays). Phase 1 of the 6-phase feature batch.
