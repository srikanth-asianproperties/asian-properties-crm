"""
=============================================================
cls_reports.py — Asian Properties CRM (APX) | v0.6.1 Reports Enhancements
=============================================================
Version : 1.1
Author  : Built for Asian Properties / Srikanth

WHAT THIS IS
------------
v1.0 shipped 12 reports as a flat card grid, all point-in-time or fixed-
window, plain HTML tables. v1.1 (this version) adds: a date-range picker
on every non-live report (Requirement 1), a categorized landing page
(Requirement 2), 3 new per-salesperson Weekly Reports (Requirement 3), a
new "Lead Stage Analysis" chart report with 4 views (Requirement 4), a
renamed + extended Salesperson Scorecard (Requirement 5, was "Salesperson
Daily Scorecard"), and a new Campaign Insights category with 6 reports
(Requirement 6). 10 new report entries total (22 vs the original 12).

Still owns report metadata, table/column/chart shaping, role-scoping, and
Excel export — still calls into cls_db.py for every database read and
never opens sqlite3 itself.

CAMPAIGN DATA — READ BEFORE TRUSTING THOSE NUMBERS
----------------------------------------------------
leads.campaign is blank/NULL on 99.97% of leads as of 2026-07-17 (see
cls_db.py v2.13's changelog for the exact count) — it's a manual, optional
field, never auto-populated by the Meta/Sell.do pipeline jobs. Srikanth's
explicit call (2026-07): build the Campaign Insights category now anyway,
because he intends to backfill campaign on existing leads. Every campaign-
grouped report therefore buckets blank/NULL under the literal label
"Unknown/Manual" via cls_db._campaign_bucket() rather than dropping those
leads, and right now that one bucket will hold almost everything. This is
expected, not a bug — it'll fill in as campaign gets backfilled/captured
going forward.

CHARTING
--------
Chart.js via CDN (Srikanth's confirmed call, 2026-07) — loaded only by
report_view_charts.html (report_view.html, used by every plain-table
report, gains no new dependency). A report's builder attaches an optional
"chart" key (single-view reports: Campaign Insights C1/C2/C3/C5/C6) or
"views" key (multi-view reports: Lead Stage Analysis's 4 sub-views) to
its returned table dict; build_report() below passes these straight
through. The underlying {columns, rows} table is ALWAYS still produced
alongside every chart — charts are a visual layer on top of the same
accessible/exportable tabular data, never a replacement for it, so Excel
export needs no chart-specific code path (see export_to_excel() / the new
_report_sheets() helper: multi-view reports export one worksheet per
view, everything else exports its one table as before).

DATE RANGE
----------
Every report except the 3 explicitly live/point-in-time ones (Pipeline
Funnel Snapshot, Lead Score Distribution, Owner-wise Workload — "date_
default": "live" in REPORTS below) now takes an optional date range via
?from=YYYY-MM-DD&to=YYYY-MM-DD. Each report carries its own sensible
default ("today" / "this_week" / "this_month" / "last_30_days") in its
REPORTS entry — config-not-code, not inferred from cadence — resolved by
resolve_date_range() below, which app.py's routes call once and thread
into build_report()/export_to_excel() identically, so Excel export always
honors whatever range is currently showing on screen.

Week-start convention: Monday-Sunday (Srikanth's confirmed call, 2026-07)
— see _this_week_range().

ROLE SCOPING (unchanged from v1.0 — same predicate app.py already uses
everywhere else):
  cls_db.can_view_all_leads(role) True  -> admin/manager, sees company-wide
                                            numbers on every owner-filterable
                                            report, and may open admin_only
                                            reports.
  cls_db.can_view_all_leads(role) False -> salesperson, every owner-
                                            filterable report is silently
                                            scoped to their own
                                            owner_match_name, and admin_only
                                            reports 404 for them (app.py
                                            enforces this) rather than just
                                            being hidden from the landing page.

PDF export is still NOT implemented here — browser print-to-PDF, per
Srikanth's v0.6 call (see report_view.html's <style media="print"> block).
The new report_view_charts.html gets the same print treatment, with
canvases hidden and each view's table shown instead — Chart.js canvases
don't print reliably, and the underlying table is the honest fallback.

CHANGELOG
---------
v1.1 (July 2026) — APX v0.6.1 Reports Enhancements. All 10 requirements
  from Srikanth's build prompt, confirmed decisions: Chart.js via CDN,
  build Campaign Insights now (with "Unknown/Manual" fallback bucket) not
  deferred, Monday-Sunday week start, new Scorecard slug
  "salesperson-scorecard" (old "daily-scorecard" 301-redirects, see
  app.py), and all of C1-C6 built including C6 as its own standalone
  report alongside Lead Stage Analysis view D (same underlying
  cls_db.get_site_visits_by_campaign() data, not queried twice).

  NEW date-range helpers: _today_range(), _this_week_range(),
  _this_month_range(), _last_30_days_range(), QUICK_RANGES,
  default_range_for(), resolve_date_range(), quick_select_links().

  NEW STAGE_COLORS + _stage_breakdown_view() — shared by Lead Stage
  Analysis views A/B/C and Campaign Insights C2, reusing the SAME
  cls_db.get_stage_breakdown() call shaped into a {columns, rows, chart}
  dict, so the grouping logic exists in exactly one place.

  NEW _per_salesperson_activity() — shared by the renamed Salesperson
  Scorecard and Weekly Site Visits Conducted/Scheduled (W2/W3), all three
  reading cls_db.get_activity_counts_range() per active salesperson, the
  SAME actor-attributed pattern the v1.0 Daily Scorecard already used
  (see cls_db.py v2.13's changelog on why this is correct instead of a
  raw site_visits/follow_ups.created_by query — that column only ever
  records who SCHEDULED a row, never who conducted/completed it).

  RENAMED "daily-scorecard" -> "salesperson-scorecard", _build_daily_
  scorecard -> _build_salesperson_scorecard, gained 2 columns (Follow-ups
  Created, Site Visits Created) and is now date-range-driven (default
  "today") instead of hardcoded to today. app.py 301-redirects the old
  slug — see that file's changelog.

  NEW report entries (10): weekly-leads-received, weekly-site-visits-
  conducted, weekly-site-visits-scheduled (Weekly Reports category),
  lead-stage-analysis (Pipeline Analysis), campaign-lead-volume,
  campaign-stage-distribution, campaign-conversion-rate, campaign-lost-
  reasons, campaign-response-time, campaign-site-visits (Campaign
  Insights, new Marketing Performance sub-group).

  NEW CATEGORIES + visible_categories() — replaces v1.0's flat
  visible_reports() (single caller, in app.py's reports_home(), updated
  together with this file).

  MODIFIED build_report() — now threads date_from/date_to into every
  builder call and surfaces the new optional "chart"/"views" keys.
  MODIFIED export_to_excel() — generalized to export one worksheet per
  view for multi-view reports via new _report_sheets() helper; single-
  table reports export exactly as v1.0 did.
  MODIFIED 8 existing builders (_build_source_performance, _build_
  project_pipeline, _build_conversion_funnel, _build_hit_rate, _build_
  lost_reason, _build_reengagement, _build_first_response, _build_call_
  activity) — each now accepts date_from/date_to and threads them into
  the cls_db.py v2.13 functions it already called. _build_call_activity
  additionally drops the old daily/weekly period toggle (has_period_
  toggle) in favor of the universal date-range picker — Today is its
  new default, replacing the old toggle's default of weekly.
  UNCHANGED builders (still take **kwargs, ignore date_from/date_to since
  there's no time dimension to apply it to): _build_pipeline_funnel,
  _build_score_distribution, _build_owner_workload.

v1.0 (July 2026) — initial build. All 12 reports from Srikanth's spec.
  Two data-honesty notes surfaced explicitly to the user in the relevant
  reports' `caveat` field (not hidden):
    - Report #5 (Conversion Funnel Over Time): activity_log stage_change
      rows only exist for stage moves made THROUGH the CRM app, not
      Sell.do-driven syncs — see cls_db.py's HONESTY NOTE.
    - Report #3 (Lead Source Performance): built on leads.source
      ('meta'/'selldo_only'/'manual_crm'), not the richer but mostly-NULL
      lead_source_detail — see cls_db.py's HONESTY NOTE.
"""

import io
import re
from datetime import datetime, timedelta

import cls_db

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


def _scope_owner(current_user):
    """
    The one place that decides "does this login see everyone's numbers
    or just their own" for every owner-filterable report — reuses
    cls_db.can_view_all_leads() exactly as app.py does everywhere else,
    not a new predicate.
    """
    if cls_db.can_view_all_leads(current_user["role"]):
        return None
    return current_user.get("owner_match_name") or "__none__"
    # "__none__" (v1.0): a salesperson login with no owner_match_name set
    # yet (admin hasn't linked their login to a lead_owner value) must
    # see ZERO leads, not everyone's — a value that matches nothing in
    # leads.lead_owner is the deliberate, honest way to enforce that
    # with the existing owner=? scoping, rather than silently falling
    # through to owner=None (which would leak company-wide data to an
    # unlinked login).


# ─────────────────────────────────────────────────────────────
# DATE RANGE — quick-select defaults + query-param resolution
# ─────────────────────────────────────────────────────────────

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _today_range():
    d = datetime.now().strftime("%Y-%m-%d")
    return d, d


def _this_week_range():
    """Monday-Sunday (Srikanth's confirmed call, 2026-07)."""
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def _this_month_range():
    """1st of the current month through TODAY (month-to-date) — not
    through the end of the calendar month, so the range never extends
    into the future."""
    now = datetime.now()
    first = now.replace(day=1)
    return first.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")


def _last_30_days_range():
    now = datetime.now()
    start = now - timedelta(days=29)  # inclusive of today = 30 days total
    return start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")


# Config-not-code: every report's "date_default" value (in REPORTS below)
# is a key into this dict. "live" is handled separately (no range at all)
# — see default_range_for().
QUICK_RANGES = {
    "today": _today_range,
    "this_week": _this_week_range,
    "this_month": _this_month_range,
    "last_30_days": _last_30_days_range,
}


def default_range_for(report_id):
    """
    (v1.1) Returns (from_str, to_str) for a report's default range, or
    (None, None) for a "live" (point-in-time, no picker) report.
    """
    meta = REPORTS_BY_ID[report_id]
    kind = meta.get("date_default", "this_month")
    if kind == "live":
        return None, None
    return QUICK_RANGES[kind]()


def resolve_date_range(report_id, args):
    """
    (v1.1) The one place app.py's report routes call to turn a request's
    ?from=&to= query params into the (date_from, date_to) pair every
    builder/export call uses. Falls back to the report's own configured
    default when either param is missing or not a well-formed
    'YYYY-MM-DD' string — a malformed/tampered query string degrades to
    the sensible default rather than erroring.

    args : request.args (or any dict-like with .get())

    Returns (None, None) for a "live" report — callers should treat that
    as "don't show a date picker" (report_view.html/report_view_charts.html
    branch on report.is_live for this).
    """
    meta = REPORTS_BY_ID.get(report_id)
    if meta is None:
        return None, None
    if meta.get("date_default", "this_month") == "live":
        return None, None
    from_arg = args.get("from")
    to_arg = args.get("to")
    if from_arg and to_arg and _DATE_RE.match(from_arg) and _DATE_RE.match(to_arg) and from_arg <= to_arg:
        return from_arg, to_arg
    return default_range_for(report_id)


def quick_select_links():
    """
    (v1.1) The 4 quick-select buttons every date-range picker shows,
    computed once per request (server-side, so there's no client/server
    timezone math to keep in sync) — [(label, key, from, to), ...].
    "Custom" isn't in this list; it's just the two always-visible
    <input type="date"> fields in the picker partial, pre-filled with
    whatever range is currently showing.
    """
    return [
        ("Today", "today") + _today_range(),
        ("This Week", "this_week") + _this_week_range(),
        ("This Month", "this_month") + _this_month_range(),
        ("Last 30 Days", "last_30_days") + _last_30_days_range(),
    ]


# ─────────────────────────────────────────────────────────────
# SHARED CHART/GROUPING HELPERS
# ─────────────────────────────────────────────────────────────

# Reuses the exact stage colors base.html's .stage-* badge classes
# already use, so a chart bar and a stage badge elsewhere in the app
# read as the same color for the same stage. Lost gets a distinct
# darker red from Unqualified for chart legibility — base.html's CSS
# intentionally combines them into one badge color, but a bar-chart
# legend needs the two stages visually distinguishable.
STAGE_COLORS = {
    "Incoming": "#8A93A3", "Prospect": "#2F80ED", "Opportunity": "#E08C2B",
    "Site Visited": "#27AE60", "Unqualified": "#D64545", "Lost": "#A93226",
    "Re Assigned": "#7E57C2", "Booked": "#1E8449",
}


def _stage_breakdown_view(data, group_label):
    """
    (v1.1) Shapes cls_db.get_stage_breakdown()'s {group: {stage: count,
    total}} return into a {columns, rows, chart} view dict — one stacked-
    bar dataset per stage, groups sorted by total desc. Shared by Lead
    Stage Analysis views A/B/C and Campaign Insights C2 (Campaign Stage
    Distribution is exactly view C, reused rather than re-queried).
    """
    groups = sorted(data.items(), key=lambda kv: -kv[1]["total"])
    labels = [g for g, _ in groups]
    datasets = [
        {"label": stage, "color": STAGE_COLORS[stage], "data": [data[g][stage] for g in labels]}
        for stage in cls_db.ALL_STAGES
    ]
    columns = [("group", group_label)] + [(s, s) for s in cls_db.ALL_STAGES] + [("total", "Total")]
    rows = [{"group": g, **data[g]} for g in labels]
    return {"columns": columns, "rows": rows, "chart": {"type": "stacked_bar", "labels": labels, "datasets": datasets}}


def _per_salesperson_activity(current_user, date_from, date_to):
    """
    (v1.1) One row per salesperson in scope — every active user for an
    oversight login (admin/manager), just the current login for a
    salesperson — each paired with their cls_db.get_activity_counts_range()
    dict for [date_from, date_to]. Shared by the Salesperson Scorecard and
    Weekly Site Visits Conducted/Scheduled (W2/W3): same per-user loop the
    v1.0 Daily Scorecard already used, just reading the range-aware
    function instead of the today-only one.

    Returns a list of (display_name, activity_counts_dict) tuples.
    """
    rows = []
    if cls_db.can_view_all_leads(current_user["role"]):
        users = [u for u in cls_db.get_all_users_detailed() if u["active"]]
        for u in users:
            perf = cls_db.get_activity_counts_range(actor_email=u["email"], date_from=date_from, date_to=date_to)
            rows.append((u["full_name"] or u["email"], perf))
    else:
        perf = cls_db.get_activity_counts_range(actor_email=current_user["email"], date_from=date_from, date_to=date_to)
        rows.append((current_user["full_name"] or current_user["email"], perf))
    return rows


# ─────────────────────────────────────────────────────────────
# PER-REPORT BUILDERS — each returns {"columns", "rows"} plus an
# optional "chart" (single view) or "views" (multi-view) key.
# ─────────────────────────────────────────────────────────────

def _build_salesperson_scorecard(current_user, date_from=None, date_to=None, **kwargs):
    columns = [
        ("name", "Salesperson"), ("calls_attempted", "Calls Tapped"),
        ("notes_added", "Notes Added"),
        ("follow_ups_created", "Follow-ups Created"),
        ("follow_ups_completed", "Follow-ups Conducted"),
        ("site_visits_created", "Site Visits Created"),
        ("site_visits_conducted", "Site Visits Conducted"),
    ]
    rows = [{"name": name, **perf} for name, perf in _per_salesperson_activity(current_user, date_from, date_to)]
    if cls_db.can_view_all_leads(current_user["role"]):
        company = cls_db.get_activity_counts_range(actor_email=None, date_from=date_from, date_to=date_to)
        rows.append({"name": "— Company Wide —", **company})
    return {"columns": columns, "rows": rows}


def _build_pipeline_funnel(current_user, **kwargs):
    owner = _scope_owner(current_user)
    counts = cls_db.get_stage_snapshot_counts(owner=owner)
    columns = [("stage", "Stage"), ("count", "Leads")]
    rows = [{"stage": stage, "count": counts[stage]} for stage in cls_db.ALL_STAGES]
    return {"columns": columns, "rows": rows}


def _build_source_performance(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_source_performance(date_from=date_from, date_to=date_to)
    columns = [
        ("source", "Source"), ("total", "Total Leads"),
        ("prospect_plus", "Reached Prospect+"), ("opportunity_plus", "Reached Opportunity+"),
        ("site_visited_plus", "Reached Site Visited+"), ("booked", "Booked"),
        ("lost_unqualified", "Lost/Unqualified"), ("quality_rate", "Opportunity+ Rate"),
    ]
    rows = []
    for r in data:
        row = dict(r)
        row["quality_rate"] = f'{round(r["opportunity_plus"] / r["total"] * 100, 1)}%' if r["total"] else "—"
        rows.append(row)
    return {"columns": columns, "rows": rows}


def _build_project_pipeline(current_user, date_from=None, date_to=None, **kwargs):
    owner = _scope_owner(current_user)
    data = cls_db.get_project_pipeline(owner=owner, date_from=date_from, date_to=date_to)
    columns = [("project", "Project")] + [(s, s) for s in cls_db.ALL_STAGES] + [("total", "Total")]
    rows = []
    for project, stage_counts in sorted(data.items(), key=lambda kv: -kv[1]["total"]):
        rows.append({"project": project, **stage_counts})
    return {"columns": columns, "rows": rows}


def _build_conversion_funnel(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_conversion_funnel_trend(date_from=date_from, date_to=date_to)
    columns = [
        ("month", "Month"), ("entered_prospect", "Entered Prospect"),
        ("reached_opportunity", "Reached Opportunity"), ("opportunity_rate", "Opportunity Rate"),
        ("reached_site_visited", "Reached Site Visited"), ("site_visited_rate", "Site Visit Rate"),
    ]
    rows = []
    for r in data:
        row = dict(r)
        row["opportunity_rate"] = f'{r["opportunity_rate"]}%'
        row["site_visited_rate"] = f'{r["site_visited_rate"]}%'
        rows.append(row)
    return {"columns": columns, "rows": rows}


def _build_hit_rate(current_user, date_from=None, date_to=None, **kwargs):
    owner = _scope_owner(current_user)
    data = cls_db.get_followup_hit_rate(owner=owner, date_from=date_from, date_to=date_to)
    columns = [
        ("kind", "Type"), ("completed", "Completed"), ("missed", "Missed"),
        ("upcoming", "Upcoming"), ("cancelled", "Cancelled"), ("no_show", "No-Show"),
        ("total", "Total"),
    ]
    rows = [
        {"kind": "Site Visits", **data["site_visits"]},
        {"kind": "Follow-ups", "no_show": "—", **data["follow_ups"]},
    ]
    return {"columns": columns, "rows": rows}


def _build_lost_reason(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_lost_reason_breakdown(date_from=date_from, date_to=date_to)
    columns = [("stage", "Stage"), ("reason", "Reason"), ("count", "Count")]
    return {"columns": columns, "rows": data}


def _build_score_distribution(current_user, **kwargs):
    owner = _scope_owner(current_user)
    data = cls_db.get_score_distribution(owner=owner)
    columns = [("owner", "Salesperson"), ("Hot", "Hot"), ("Warm", "Warm"), ("Cold", "Cold"), ("total", "Total")]
    return {"columns": columns, "rows": data}


def _build_reengagement(current_user, date_from=None, date_to=None, **kwargs):
    owner = _scope_owner(current_user)
    leads = cls_db.get_reengaged_leads(owner=owner, date_from=date_from, date_to=date_to)
    columns = [
        ("crm_lead_no", "Lead #"), ("full_name", "Name"), ("current_stage", "Stage"),
        ("lead_owner", "Owner"), ("cls_created_at", "First Created"), ("cls_updated_at", "Reengaged At"),
    ]
    rows = [{k: lead.get(k) for k, _ in columns} for lead in leads]
    return {"columns": columns, "rows": rows}


def _build_first_response(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_first_response_time(date_from=date_from, date_to=date_to)
    columns = [
        ("month", "Month"), ("leads", "Leads"), ("responded", "Responded"),
        ("no_response_yet", "No Response Yet"), ("avg_hours", "Avg Response (hrs)"),
        ("median_hours", "Median Response (hrs)"),
    ]
    rows = []
    for r in data:
        row = dict(r)
        row["avg_hours"] = row["avg_hours"] if row["avg_hours"] is not None else "—"
        row["median_hours"] = row["median_hours"] if row["median_hours"] is not None else "—"
        rows.append(row)
    return {"columns": columns, "rows": rows}


def _build_owner_workload(current_user, **kwargs):
    owner = _scope_owner(current_user)
    data = cls_db.get_owner_workload(owner=owner)
    columns = [
        ("owner", "Salesperson"), ("open_leads", "Open Leads"),
        ("open_follow_ups", "Open Follow-ups"), ("open_site_visits", "Open Site Visits"),
    ]
    return {"columns": columns, "rows": data}


def _build_call_activity(current_user, date_from=None, date_to=None, **kwargs):
    owner = _scope_owner(current_user)
    data = cls_db.get_call_activity(owner=owner, date_from=date_from, date_to=date_to)
    columns = [
        ("crm_lead_no", "Lead #"), ("full_name", "Name"), ("lead_owner", "Owner"),
        ("call_count", "Calls"), ("last_call_at", "Last Call"),
    ]
    return {"columns": columns, "rows": data}


# ── Weekly Reports (Requirement 3) ──

def _build_weekly_leads_received(current_user, date_from=None, date_to=None, **kwargs):
    owner = _scope_owner(current_user)
    data = cls_db.get_leads_received_by_owner(date_from, date_to, owner=owner)
    columns = [("owner", "Salesperson"), ("count", "Leads Received")]
    return {"columns": columns, "rows": data}


def _build_weekly_site_visits_conducted(current_user, date_from=None, date_to=None, **kwargs):
    columns = [("name", "Salesperson"), ("count", "Site Visits Conducted")]
    rows = [{"name": name, "count": perf["site_visits_conducted"]}
            for name, perf in _per_salesperson_activity(current_user, date_from, date_to)]
    return {"columns": columns, "rows": rows}


def _build_weekly_site_visits_scheduled(current_user, date_from=None, date_to=None, **kwargs):
    columns = [("name", "Salesperson"), ("count", "Site Visits Scheduled")]
    rows = [{"name": name, "count": perf["site_visits_created"]}
            for name, perf in _per_salesperson_activity(current_user, date_from, date_to)]
    return {"columns": columns, "rows": rows}


# ── Lead Stage Analysis (Requirement 4) ──

def _build_lead_stage_analysis(current_user, date_from=None, date_to=None, **kwargs):
    owner = _scope_owner(current_user)
    by_owner = _stage_breakdown_view(
        cls_db.get_stage_breakdown("owner", date_from=date_from, date_to=date_to, owner=owner), "Owner")
    by_project = _stage_breakdown_view(
        cls_db.get_stage_breakdown("project", date_from=date_from, date_to=date_to, owner=owner), "Project")
    by_campaign = _stage_breakdown_view(
        cls_db.get_stage_breakdown("campaign", date_from=date_from, date_to=date_to, owner=owner), "Campaign")

    visits = cls_db.get_site_visits_by_campaign(date_from=date_from, date_to=date_to, owner=owner)
    visits_view = {
        "columns": [("campaign", "Campaign"), ("count", "Site Visits")], "rows": visits,
        "chart": {"type": "bar", "labels": [r["campaign"] for r in visits],
                  "datasets": [{"label": "Site Visits", "color": "#2F80ED", "data": [r["count"] for r in visits]}]},
    }

    views = [
        {"title": "By Owner", **by_owner},
        {"title": "By Project", **by_project},
        {"title": "By Campaign", **by_campaign},
        {"title": "Site Visits by Campaign", **visits_view},
    ]
    return {"columns": [], "rows": [], "views": views}


# ── Campaign Insights (Requirement 6) ──

def _build_campaign_lead_volume(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_campaign_lead_volume(date_from=date_from, date_to=date_to)
    columns = [("campaign", "Campaign"), ("count", "Leads")]
    chart = {"type": "horizontal_bar", "labels": [r["campaign"] for r in data],
             "datasets": [{"label": "Leads", "color": "#2F80ED", "data": [r["count"] for r in data]}]}
    return {"columns": columns, "rows": data, "chart": chart}


def _build_campaign_stage_distribution(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_stage_breakdown("campaign", date_from=date_from, date_to=date_to)
    return _stage_breakdown_view(data, "Campaign")


def _build_campaign_conversion_rate(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_campaign_performance(date_from=date_from, date_to=date_to)
    columns = [
        ("campaign", "Campaign"), ("total", "Total Leads"),
        ("prospect_plus", "Reached Prospect+"), ("opportunity_plus", "Reached Opportunity+"),
        ("site_visited_plus", "Reached Site Visited+"), ("booked", "Booked"),
        ("lost_unqualified", "Lost/Unqualified"), ("conversion_rate", "Site Visited+ Rate"),
    ]
    rows = []
    for r in data:
        row = dict(r)
        row["conversion_rate"] = round(r["site_visited_plus"] / r["total"] * 100, 1) if r["total"] else 0.0
        rows.append(row)
    chart = {"type": "bar", "labels": [r["campaign"] for r in rows],
             "datasets": [{"label": "Site Visited+ Rate (%)", "color": "#27AE60",
                           "data": [r["conversion_rate"] for r in rows]}]}
    for row in rows:
        row["conversion_rate"] = f'{row["conversion_rate"]}%'
    return {"columns": columns, "rows": rows, "chart": chart}


def _build_campaign_lost_reasons(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_campaign_lost_reasons(date_from=date_from, date_to=date_to)
    columns = [("campaign", "Campaign"), ("reason", "Reason"), ("count", "Count")]
    return {"columns": columns, "rows": data}


def _build_campaign_response_time(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_campaign_response_time(date_from=date_from, date_to=date_to)
    columns = [
        ("campaign", "Campaign"), ("leads", "Leads"), ("responded", "Responded"),
        ("no_response_yet", "No Response Yet"), ("avg_hours", "Avg Response (hrs)"),
        ("median_hours", "Median Response (hrs)"),
    ]
    chart = {"type": "bar", "labels": [r["campaign"] for r in data],
             "datasets": [{"label": "Median Response (hrs)", "color": "#E08C2B",
                           "data": [r["median_hours"] or 0 for r in data]}]}
    rows = []
    for r in data:
        row = dict(r)
        row["avg_hours"] = row["avg_hours"] if row["avg_hours"] is not None else "—"
        row["median_hours"] = row["median_hours"] if row["median_hours"] is not None else "—"
        rows.append(row)
    return {"columns": columns, "rows": rows, "chart": chart}


def _build_campaign_site_visits(current_user, date_from=None, date_to=None, **kwargs):
    data = cls_db.get_site_visits_by_campaign(date_from=date_from, date_to=date_to)
    columns = [("campaign", "Campaign"), ("count", "Site Visits")]
    chart = {"type": "bar", "labels": [r["campaign"] for r in data],
             "datasets": [{"label": "Site Visits", "color": "#2F80ED", "data": [r["count"] for r in data]}]}
    return {"columns": columns, "rows": data, "chart": chart}


# ─────────────────────────────────────────────────────────────
# REGISTRY — config-not-code. Add a report by adding ONE entry here;
# every route, the landing page, and the Excel exporter all read from
# this single list, nothing else needs to change. Add it to a category
# in CATEGORIES below too, or it simply won't appear on the landing page
# (build_report()/the route still work by direct URL either way).
#
# date_default: "today" | "this_week" | "this_month" | "last_30_days" |
#               "live" (no date picker — see Requirement 1's 3 exempt
#               reports: pipeline-funnel, score-distribution, owner-workload)
# template: report_view.html (default, omitted) | report_view_charts.html
#           (chart-bearing reports)
# ─────────────────────────────────────────────────────────────

REPORTS = [
    {
        "id": "salesperson-scorecard", "title": "Salesperson Scorecard",
        "description": "Calls tapped, notes added, follow-ups and site visits created/conducted, for the selected period.",
        "cadence": "Daily", "admin_only": False, "owner_filterable": True,
        "caveat": None, "build": _build_salesperson_scorecard, "date_default": "today",
    },
    {
        "id": "pipeline-funnel", "title": "Pipeline Funnel Snapshot",
        "description": "Count of leads in each of the 8 stages, right now.",
        "cadence": "Live", "admin_only": False, "owner_filterable": True,
        "caveat": "A live snapshot of where leads sit right now, not a historical figure for today specifically.",
        "build": _build_pipeline_funnel, "date_default": "live",
    },
    {
        "id": "source-performance", "title": "Lead Source Performance",
        "description": "Which capture channel (Meta / Sell.do-only / manually entered) produces the best-quality leads.",
        "cadence": "Weekly", "admin_only": True, "owner_filterable": False,
        "caveat": (
            "Based on leads.source (meta / selldo_only / manual_crm) — the system-level capture channel, "
            "not a marketing sub-source like \"99acres\". The richer lead_source_detail field is set only "
            "for manually-entered leads and is NULL for the large majority of leads, so it isn't usable "
            "here yet."
        ),
        "build": _build_source_performance, "date_default": "last_30_days",
    },
    {
        "id": "project-pipeline", "title": "Project-wise Pipeline",
        "description": "Stage breakdown per project (Naishka Homes / Grace Classic / Prima Paradiso / Praga Enclave), for leads created in the selected period.",
        "cadence": "Weekly", "admin_only": False, "owner_filterable": True,
        "caveat": None, "build": _build_project_pipeline, "date_default": "this_month",
    },
    {
        "id": "conversion-funnel", "title": "Conversion Funnel Over Time",
        "description": "Prospect → Opportunity → Site Visit conversion rate trend, month over month.",
        "cadence": "Monthly", "admin_only": True, "owner_filterable": False,
        "caveat": (
            "Only counts stage moves made THROUGH the CRM app (activity_log 'stage_change' rows) — Sell.do-"
            "driven syncs during parallel-run leave no such trail, so months before the team's CRM adoption "
            "matured will undercount. This is a real data gap, not a bug; it fills in as parallel-run continues."
        ),
        "build": _build_conversion_funnel, "date_default": "this_month",
    },
    {
        "id": "hit-rate", "title": "Follow-up / Site-Visit Hit Rate",
        "description": "Of follow-ups and site visits scheduled in the selected period: completed vs missed vs cancelled.",
        "cadence": "Weekly", "admin_only": False, "owner_filterable": True,
        "caveat": "\"Missed\" is computed live (still scheduled and past due), never a stored status.",
        "build": _build_hit_rate, "date_default": "this_week",
    },
    {
        "id": "lost-reason", "title": "Lost/Unqualified Reason Breakdown",
        "description": "Why leads are dying — price, location, budget, no response.",
        "cadence": "Monthly", "admin_only": True, "owner_filterable": False,
        "caveat": "Reflects each lead's CURRENT reason only — cleared the moment a lead moves out of Lost/Unqualified.",
        "build": _build_lost_reason, "date_default": "this_month",
    },
    {
        "id": "score-distribution", "title": "Lead Score Distribution",
        "description": "Hot / Warm / Cold count, by salesperson.",
        "cadence": "Live", "admin_only": False, "owner_filterable": True,
        "caveat": None, "build": _build_score_distribution, "date_default": "live",
    },
    {
        "id": "reengagement", "title": "Reengagement Report",
        "description": "Which existing leads came back during the selected period.",
        "cadence": "Weekly", "admin_only": False, "owner_filterable": True,
        "caveat": (
            "Approximate signal — leads that existed before the selected period but were touched again within it. "
            "Can't yet distinguish a genuine new inquiry from a routine stage sync."
        ),
        "build": _build_reengagement, "date_default": "this_week",
    },
    {
        "id": "first-response", "title": "First-Response Time",
        "description": "Time from lead creation to first activity_log entry.",
        "cadence": "Monthly", "admin_only": True, "owner_filterable": False,
        "caveat": None, "build": _build_first_response, "date_default": "this_month",
    },
    {
        "id": "owner-workload", "title": "Owner-wise Workload",
        "description": "Open leads and open follow-ups/site-visits per salesperson, right now.",
        "cadence": "Live", "admin_only": False, "owner_filterable": True,
        "caveat": None, "build": _build_owner_workload, "date_default": "live",
    },
    {
        "id": "call-activity", "title": "Call Activity Report",
        "description": "Calls tapped per lead per salesperson, for the selected period (best-effort — no duration; that's v1.0 Telephony).",
        "cadence": "Daily", "admin_only": False, "owner_filterable": True,
        "caveat": None, "build": _build_call_activity, "date_default": "today",
    },
    {
        "id": "weekly-leads-received", "title": "Weekly Leads Received",
        "description": "New leads assigned to each salesperson during the selected week.",
        "cadence": "Weekly", "admin_only": False, "owner_filterable": True,
        "caveat": (
            "Grouped by each lead's CURRENT owner, not who it was assigned to at creation time — a lead "
            "reassigned since shows under its new owner."
        ),
        "build": _build_weekly_leads_received, "date_default": "this_week",
    },
    {
        "id": "weekly-site-visits-conducted", "title": "Weekly Site Visits Conducted",
        "description": "Site visits marked completed by each salesperson during the selected week.",
        "cadence": "Weekly", "admin_only": False, "owner_filterable": True,
        "caveat": None, "build": _build_weekly_site_visits_conducted, "date_default": "this_week",
    },
    {
        "id": "weekly-site-visits-scheduled", "title": "Weekly Site Visits Scheduled",
        "description": "Site visits created (scheduled) by each salesperson during the selected week.",
        "cadence": "Weekly", "admin_only": False, "owner_filterable": True,
        "caveat": None, "build": _build_weekly_site_visits_scheduled, "date_default": "this_week",
    },
    {
        "id": "lead-stage-analysis", "title": "Lead Stage Analysis",
        "description": "Lead counts by stage — broken down by owner, project, and campaign — plus site visits by campaign, for the selected period.",
        "cadence": "Monthly", "admin_only": False, "owner_filterable": True,
        "caveat": (
            "By-campaign and site-visits-by-campaign views are dominated by \"Unknown/Manual\" until campaign "
            "data is backfilled — see this report's Campaign data note."
        ),
        "build": _build_lead_stage_analysis, "date_default": "this_month",
        "template": "report_view_charts.html",
    },
    {
        "id": "campaign-lead-volume", "title": "Campaign Lead Volume",
        "description": "Which campaigns brought in the most leads during the selected period.",
        "cadence": "Marketing", "admin_only": True, "owner_filterable": False,
        "caveat": "leads.campaign is blank/NULL on the large majority of leads today — see this report's Campaign data note.",
        "build": _build_campaign_lead_volume, "date_default": "last_30_days",
        "template": "report_view_charts.html",
    },
    {
        "id": "campaign-stage-distribution", "title": "Campaign Stage Distribution",
        "description": "Where each campaign's leads end up in the pipeline, for the selected period.",
        "cadence": "Marketing", "admin_only": True, "owner_filterable": False,
        "caveat": "leads.campaign is blank/NULL on the large majority of leads today — see this report's Campaign data note.",
        "build": _build_campaign_stage_distribution, "date_default": "last_30_days",
        "template": "report_view_charts.html",
    },
    {
        "id": "campaign-conversion-rate", "title": "Campaign Conversion Rate",
        "description": "% of each campaign's leads reaching Site Visited+, for the selected period.",
        "cadence": "Marketing", "admin_only": True, "owner_filterable": False,
        "caveat": "leads.campaign is blank/NULL on the large majority of leads today — see this report's Campaign data note.",
        "build": _build_campaign_conversion_rate, "date_default": "last_30_days",
        "template": "report_view_charts.html",
    },
    {
        "id": "campaign-lost-reasons", "title": "Campaign Lost Reason Breakdown",
        "description": "Why leads from each campaign died, for the selected period.",
        "cadence": "Marketing", "admin_only": True, "owner_filterable": False,
        "caveat": "leads.campaign is blank/NULL on the large majority of leads today — see this report's Campaign data note.",
        "build": _build_campaign_lost_reasons, "date_default": "last_30_days",
    },
    {
        "id": "campaign-response-time", "title": "Campaign First-Response Time",
        "description": "Median time to first response, per campaign, for the selected period.",
        "cadence": "Marketing", "admin_only": True, "owner_filterable": False,
        "caveat": "leads.campaign is blank/NULL on the large majority of leads today — see this report's Campaign data note.",
        "build": _build_campaign_response_time, "date_default": "last_30_days",
        "template": "report_view_charts.html",
    },
    {
        "id": "campaign-site-visits", "title": "Site Visits by Campaign",
        "description": "Site visits per campaign, for the selected period. Standalone version of Lead Stage Analysis's view D.",
        "cadence": "Marketing", "admin_only": True, "owner_filterable": False,
        "caveat": "leads.campaign is blank/NULL on the large majority of leads today — see this report's Campaign data note.",
        "build": _build_campaign_site_visits, "date_default": "last_30_days",
        "template": "report_view_charts.html",
    },
]

REPORTS_BY_ID = {r["id"]: r for r in REPORTS}

# ─────────────────────────────────────────────────────────────
# CATEGORIES — config-not-code (Requirement 2). Landing page renders
# from this, in this order; a report id not listed here still works by
# direct URL, it just won't appear on /reports.
# ─────────────────────────────────────────────────────────────

CATEGORIES = [
    {"name": "Daily Operations", "report_ids": [
        "salesperson-scorecard", "pipeline-funnel", "owner-workload", "score-distribution",
    ]},
    {"name": "Weekly Reports", "report_ids": [
        "weekly-leads-received", "weekly-site-visits-conducted", "weekly-site-visits-scheduled",
    ]},
    {"name": "Pipeline Analysis", "report_ids": [
        "conversion-funnel", "project-pipeline", "lead-stage-analysis", "hit-rate", "first-response",
    ]},
    {"name": "Lead Quality & Retention", "report_ids": [
        "lost-reason", "reengagement",
    ]},
    {"name": "Marketing Performance", "report_ids": [
        "source-performance", "campaign-lead-volume", "campaign-stage-distribution",
        "campaign-conversion-rate", "campaign-lost-reasons", "campaign-response-time", "campaign-site-visits",
    ]},
    {"name": "Activity Log", "report_ids": [
        "call-activity",
    ]},
]


def visible_categories(current_user):
    """
    (v1.1) Landing-page structure — replaces v1.0's flat visible_reports().
    Same "admin_only reports simply absent, not greyed-out" rule as
    before, applied per-category; a category with zero visible reports
    for this login is omitted entirely rather than shown empty.
    """
    oversight = cls_db.can_view_all_leads(current_user["role"])
    result = []
    for cat in CATEGORIES:
        reports = [REPORTS_BY_ID[rid] for rid in cat["report_ids"] if oversight or not REPORTS_BY_ID[rid]["admin_only"]]
        if reports:
            result.append({"name": cat["name"], "reports": reports})
    return result


def build_report(report_id, current_user, date_from=None, date_to=None, **kwargs):
    """
    Runs one report's builder and returns the full renderable dict:
    {id, title, description, cadence, caveat, date_default, is_live,
    template, date_from, date_to, columns, rows, chart, views}.
    Raises KeyError for an unknown report_id — the route treats that
    as a 404, never a 500.
    """
    meta = REPORTS_BY_ID[report_id]
    table = meta["build"](current_user, date_from=date_from, date_to=date_to, **kwargs)
    return {
        "id": meta["id"], "title": meta["title"], "description": meta["description"],
        "cadence": meta["cadence"], "caveat": meta["caveat"],
        "date_default": meta.get("date_default", "this_month"),
        "is_live": meta.get("date_default") == "live",
        "template": meta.get("template", "report_view.html"),
        "date_from": date_from, "date_to": date_to,
        "columns": table.get("columns", []), "rows": table.get("rows", []),
        "chart": table.get("chart"), "views": table.get("views"),
    }


# ─────────────────────────────────────────────────────────────
# EXCEL EXPORT
# ─────────────────────────────────────────────────────────────

def _report_sheets(report):
    """
    (v1.1) Normalizes a built report into a list of {title, columns,
    rows} — one sheet per view for multi-view reports (Lead Stage
    Analysis), or a single sheet for every other report, unchanged from
    v1.0's shape.
    """
    if report.get("views"):
        return [{"title": v["title"], "columns": v["columns"], "rows": v["rows"]} for v in report["views"]]
    return [{"title": report["title"], "columns": report["columns"], "rows": report["rows"]}]


def export_to_excel(report):
    """
    report : the dict build_report() returns. Writes one worksheet per
    _report_sheets() entry, header row bolded, column widths auto-sized
    to content (capped so one long free-text cell can't blow up the
    whole sheet). Every sheet's second row states the report's title and
    the exact date range it was generated for (or omits the range for a
    "live" report), so an exported file is self-describing even once
    detached from the app.

    Returns a BytesIO positioned at 0, ready for Flask's send_file().
    Raises RuntimeError if openpyxl isn't installed — the route
    catches this and shows a clear message rather than a raw 500.
    """
    if not OPENPYXL_AVAILABLE:
        raise RuntimeError(
            "openpyxl is not installed. Run: python -m pip install openpyxl"
        )

    wb = Workbook()
    first = True
    range_note = f"{report['date_from']} to {report['date_to']}" if report.get("date_from") else None

    for sheet_data in _report_sheets(report):
        ws = wb.active if first else wb.create_sheet()
        first = False
        # Excel sheet titles: max 31 chars, and none of \ / ? * [ ] allowed —
        # several report/view titles ("Lost/Unqualified...") contain a slash.
        safe_title = sheet_data["title"]
        for ch in r'\/?*[]':
            safe_title = safe_title.replace(ch, "-")
        ws.title = safe_title[:31]

        ws.append([report["title"]])
        ws["A1"].font = Font(bold=True, size=13)
        generated_line = f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        if range_note:
            generated_line += f" — {range_note}"
        ws.append([generated_line])
        if report.get("caveat"):
            ws.append([report["caveat"]])
        ws.append([])

        header_row_idx = ws.max_row + 1
        labels = [label for _, label in sheet_data["columns"]]
        ws.append(labels)
        for cell in ws[header_row_idx]:
            cell.font = Font(bold=True)

        for row in sheet_data["rows"]:
            ws.append([row.get(key, "") for key, _ in sheet_data["columns"]])

        for i, (key, label) in enumerate(sheet_data["columns"], start=1):
            col_letter = ws.cell(row=header_row_idx, column=i).column_letter
            max_len = max(
                [len(label)] + [len(str(row.get(key, ""))) for row in sheet_data["rows"]]
            )
            ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
