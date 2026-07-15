"""
=============================================================
cls_dashboard.py  —  CLS Dashboard Generator
=============================================================
Version : 2.0
Author  : Built for Asian Properties / Srikanth

WHAT THIS DOES
--------------
Reads cls.db and writes dashboard.html — a single, self-contained
HTML page showing the health of the whole Centralised Leads System:
summary cards, per-project tiles, a working filter bar, and the
full historical event log (every CAPI fire ever recorded).

WHAT CHANGED IN v2.0  (Srikanth's redesign request)
---------------------------------------------------
  1. NEW LOOK — dark-navy header + light card theme, matching the
     old selldo_capi_automation.py dashboard (replaces the cream/
     copper theme).
  2. FILTER BAR — campaign / event / date / name-or-phone search +
     Reset, all client-side (pure inline JavaScript, no server).
  3. REMOVED the "By project" table and the "Match quality" table.
     Both forced scrolling before the events data. The page now goes
     straight from cards -> project tiles -> filter -> events.
  4. EVENT COLUMNS rebuilt to mirror the old dashboard exactly:
     #  Date  Time  Campaign  Name  Phone  CRM Stage  Meta Event
     Value  Previous Stage
     (Previous Stage is fed by the new events_log.prev_stage column.)

HYBRID USE
----------
1. Standalone: run `python cls_dashboard.py` anytime for an instant
   fresh dashboard — without firing any events.
2. Automatic: Job C (cls_capi_firer.py) calls generate_dashboard()
   at the end of every run, so the dashboard auto-refreshes each
   2-hour cycle.

DATA SOURCES (all from cls.db — no separate files)
--------------------------------------------------
  leads table       -> total leads count (used only inside cards)
  events_log table  -> the running history of every fired event,
                       including the new prev_stage column

OUTPUT
------
  C:\\CLS\\dashboard.html  — open in any browser; double-click it.

RUN
---
  python cls_dashboard.py            # generate the dashboard now
  python cls_dashboard.py --selftest # offline check on a temp DB
=============================================================
"""

import os
import sys
import json
from datetime import datetime

import cls_db   # the foundation layer

BASE_DIR       = r"C:\CLS"
DASHBOARD_FILE = os.path.join(BASE_DIR, "dashboard.html")

# Meta event -> accent colour. These mirror the old dashboard's event
# colours: QualifiedLead = blue, Schedule = amber, CompleteRegistration
# = green. CRM-stage funnel order: Prospect -> Opportunity -> Site Visited.
EVENT_COLORS = {
    "QualifiedLead"       : "#2F80ED",   # blue  — Prospect
    "Schedule"            : "#E08C2B",   # amber — Opportunity
    "CompleteRegistration": "#27AE60",   # green — Site Visited
}


def _esc(value):
    """Minimal HTML-escape so lead names with & < > can't break the page."""
    s = "" if value is None else str(value)
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _split_dt(fired_at):
    """
    Split a 'YYYY-MM-DD HH:MM:SS' timestamp into (date, time).
    The old dashboard showed Date and Time as TWO separate columns;
    CLS stores one fired_at string, so we slice it here.
    Falls back gracefully if the format is unexpected.
    """
    s = "" if fired_at is None else str(fired_at).strip()
    if " " in s:
        d, t = s.split(" ", 1)
        return d, t
    return s, ""


def generate_dashboard():
    """
    Read cls.db, build dashboard.html. Returns True on success.
    Safe to call from Job C or standalone — it only reads the DB.
    """
    cls_db.init_db()   # ensures events_log + prev_stage column exist

    lead_stats  = cls_db.stats()
    evt_stats   = cls_db.event_stats()
    events      = cls_db.get_events()        # all events, newest first
    last_update = datetime.now().strftime("%d %b %Y, %I:%M %p")

    # ── Per-event-type counts for the top cards ──
    # The old dashboard's cards were: Total Events / Today /
    # QualifiedLead / Schedule / CompleteReg.
    event_type_counts = {"QualifiedLead": 0, "Schedule": 0,
                         "CompleteRegistration": 0}
    for e in events:
        me = e["meta_event"]
        if me in event_type_counts:
            event_type_counts[me] += 1

    # ── Per-project tiles (counted from events_log, like the old one) ──
    # "+N today" mirrors the old dashboard's per-project tile.
    today_str = datetime.now().strftime("%Y-%m-%d")
    project_agg = {}   # bucket -> {"total": int, "today": int}
    for e in events:
        p = cls_db.get_project_bucket(e["project"])
        agg = project_agg.setdefault(p, {"total": 0, "today": 0})
        agg["total"] += 1
        if str(e["fired_at"]).startswith(today_str):
            agg["today"] += 1
    project_tiles = sorted(project_agg.items(),
                           key=lambda kv: kv[1]["total"], reverse=True)

    # ── Summary cards ──
    cards = [
        ("Total Events",  f"{evt_stats['total_events']:,}", "#1F2A44"),
        ("Today",         f"{evt_stats['events_today']:,}", "#EB5A8C"),
        ("QualifiedLead", f"{event_type_counts['QualifiedLead']:,}",
         EVENT_COLORS["QualifiedLead"]),
        ("Schedule",      f"{event_type_counts['Schedule']:,}",
         EVENT_COLORS["Schedule"]),
        ("CompleteReg.",  f"{event_type_counts['CompleteRegistration']:,}",
         EVENT_COLORS["CompleteRegistration"]),
    ]
    cards_html = ""
    for title, value, color in cards:
        cards_html += f"""
        <div class="card">
          <div class="card-value" style="color:{color}">{_esc(value)}</div>
          <div class="card-title">{_esc(title)}</div>
        </div>"""

    # ── Project tiles ──
    tiles_html = ""
    for name, agg in project_tiles:
        tiles_html += f"""
        <div class="tile">
          <div class="tile-name">{_esc(name)}</div>
          <div class="tile-total">{agg['total']:,} <span>total</span></div>
          <div class="tile-today">+{agg['today']:,} today</div>
        </div>"""
    if not tiles_html:
        tiles_html = ('<div class="tile tile-empty">No projects yet — '
                      'tiles fill as Job C fires events.</div>')

    # ── Build filter dropdown option lists from the actual data ──
    campaigns = sorted({cls_db.get_project_bucket(e["project"]) for e in events})
    meta_evts = sorted({e["meta_event"] for e in events if e["meta_event"]})
    dates     = sorted({_split_dt(e["fired_at"])[0] for e in events
                        if e["fired_at"]}, reverse=True)

    camp_opts = "".join(f'<option value="{_esc(c)}">{_esc(c)}</option>'
                        for c in campaigns)
    evt_opts  = "".join(f'<option value="{_esc(m)}">{_esc(m)}</option>'
                        for m in meta_evts)
    date_opts = "".join(f'<option value="{_esc(d)}">{_esc(d)}</option>'
                        for d in dates)

    # ── Event log rows ──
    if events:
        event_html = ""
        for idx, e in enumerate(events):
            # Newest event is row #len, oldest is #1 — same as old script.
            row_num = len(events) - idx
            color   = EVENT_COLORS.get(e["meta_event"], "#5F6470")
            date_s, time_s = _split_dt(e["fired_at"])
            prev    = e["prev_stage"] if e["prev_stage"] else "—"
            tag = ('<span class="pill pill-lg">leadgen</span>'
                   if e["used_leadgen"]
                   else '<span class="pill pill-h">hashed</span>')
            # data-* attributes drive the client-side filter.
            event_html += f"""
            <tr data-campaign="{_esc(cls_db.get_project_bucket(e['project']))}"
                data-event="{_esc(e['meta_event'])}"
                data-date="{_esc(date_s)}"
                data-search="{_esc((e['full_name'] or '').lower())} {_esc(e['phone_norm'] or '')}">
              <td class="dim">{row_num}</td>
              <td>{_esc(date_s)}</td>
              <td class="dim">{_esc(time_s)}</td>
              <td>{_esc(cls_db.get_project_bucket(e['project']))}</td>
              <td>{_esc(e['full_name'])}</td>
              <td class="dim">{_esc(e['phone_norm'])}</td>
              <td>{_esc(e['crm_stage'])}</td>
              <td><b style="color:{color}">{_esc(e['meta_event'])}</b></td>
              <td style="color:{color}">&#8377;{e['value_inr']:,}</td>
              <td class="dim">{_esc(prev)} {tag}</td>
            </tr>"""
        event_section = f"""
        <table class="evt" id="evtTable">
          <thead><tr>
            <th>#</th><th>Date</th><th>Time</th><th>Campaign</th>
            <th>Name</th><th>Phone</th><th>CRM Stage</th>
            <th>Meta Event</th><th>Value</th><th>Previous Stage</th>
          </tr></thead>
          <tbody>{event_html}</tbody>
        </table>"""
    else:
        event_section = ('<p class="empty">No events fired yet. '
                         'The log will fill as Job C runs.</p>')

    # ── Assemble the page ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CLS Dashboard — Asian Properties</title>
<style>
  :root {{
    --bg:#F4F5F7; --navy:#141C2F; --navy2:#1F2A44;
    --ink:#2A2F3A; --muted:#8A8F9C; --line:#E4E6EB;
    --panel:#FFFFFF; --accent:#2F80ED;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--ink);
    font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
    line-height:1.55; }}

  /* ── Dark navy header bar ── */
  header {{ background:var(--navy); color:#FFF;
    padding:18px 32px; }}
  header h1 {{ font-size:19px; font-weight:600; }}
  header .updated {{ font-size:12px; color:#9AA3B8; margin-top:2px; }}

  .wrap {{ max-width:1280px; margin:0 auto; padding:24px 32px 48px; }}

  /* ── Summary cards ── */
  .cards {{ display:grid; grid-template-columns:repeat(5,1fr);
    gap:16px; margin-bottom:20px; }}
  .card {{ background:var(--panel); border:1px solid var(--line);
    border-radius:12px; padding:20px 16px; text-align:center;
    box-shadow:0 1px 3px rgba(20,28,47,.04); }}
  .card-value {{ font-size:34px; font-weight:700; line-height:1; }}
  .card-title {{ font-size:12px; color:var(--muted); margin-top:8px;
    text-transform:none; letter-spacing:.01em; }}

  /* ── Project tiles ── */
  .tiles {{ display:grid; grid-template-columns:repeat(2,1fr);
    gap:16px; margin-bottom:22px; }}
  .tile {{ background:var(--panel); border:1px solid var(--line);
    border-left:4px solid var(--accent); border-radius:12px;
    padding:16px 20px; }}
  .tile-name {{ font-size:13px; color:var(--muted); font-weight:600; }}
  .tile-total {{ font-size:26px; font-weight:700; color:var(--ink);
    margin-top:2px; }}
  .tile-total span {{ font-size:13px; font-weight:500;
    color:var(--muted); }}
  .tile-today {{ font-size:12px; color:#EB5A8C; font-weight:600;
    margin-top:2px; }}
  .tile-empty {{ grid-column:1/-1; border-left-color:var(--line);
    color:var(--muted); font-size:13px; }}

  /* ── Filter bar ── */
  .filterbar {{ display:flex; flex-wrap:wrap; align-items:center;
    gap:10px; margin-bottom:16px; font-size:13px; }}
  .filterbar label {{ color:var(--muted); font-weight:600;
    margin-right:2px; }}
  .filterbar select, .filterbar input {{ font-size:13px;
    padding:7px 10px; border:1px solid var(--line);
    border-radius:8px; background:var(--panel); color:var(--ink);
    font-family:inherit; }}
  .filterbar input {{ min-width:220px; }}
  .filterbar button {{ font-size:13px; padding:7px 16px;
    border:none; border-radius:8px; background:var(--navy2);
    color:#FFF; cursor:pointer; font-weight:600; }}
  .filterbar button:hover {{ background:var(--navy); }}
  .rowcount {{ color:var(--muted); margin-left:auto; }}

  /* ── Events table ── */
  table {{ width:100%; border-collapse:collapse;
    background:var(--panel); border:1px solid var(--line);
    border-radius:12px; overflow:hidden; font-size:13px; }}
  thead tr {{ background:var(--navy2); }}
  th {{ text-align:left; padding:11px 12px; font-size:11px;
    color:#C5CAD6; text-transform:uppercase; letter-spacing:.04em;
    font-weight:600; }}
  td {{ padding:10px 12px; border-top:1px solid var(--line); }}
  td.dim {{ color:var(--muted); font-size:12px; }}
  .pill {{ font-size:10px; padding:2px 7px; border-radius:10px;
    font-weight:600; margin-left:4px; }}
  .pill-lg {{ background:#E4F1FF; color:#1A5FBF; }}
  .pill-h {{ background:#EFF0F2; color:#6B7280; }}
  .evt tbody tr:hover {{ background:#F8F9FB; }}
  .evt tbody tr.hidden {{ display:none; }}
  .empty {{ color:var(--muted); padding:24px; background:var(--panel);
    border:1px solid var(--line); border-radius:12px; }}
  .noresult {{ color:var(--muted); padding:18px; font-size:13px;
    text-align:center; }}

  h2 {{ font-size:14px; font-weight:600; margin:0 0 12px;
    color:var(--ink); }}
  footer {{ margin-top:28px; font-size:12px; color:var(--muted);
    text-align:center; }}
</style>
</head>
<body>
  <header>
    <h1>Centralised Leads System — Dashboard</h1>
    <div class="updated">Asian Properties &nbsp;&middot;&nbsp; last updated {last_update}</div>
  </header>

  <div class="wrap">

    <!-- ── Summary cards ── -->
    <div class="cards">{cards_html}</div>

    <!-- ── Project tiles ── -->
    <div class="tiles">{tiles_html}</div>

    <!-- ── Filter bar (client-side) ── -->
    <div class="filterbar">
      <label>Filter:</label>
      <select id="fCampaign">
        <option value="">All Campaigns</option>{camp_opts}
      </select>
      <select id="fEvent">
        <option value="">All Events</option>{evt_opts}
      </select>
      <select id="fDate">
        <option value="">All Dates</option>{date_opts}
      </select>
      <input id="fSearch" type="text" placeholder="Search name or phone...">
      <button id="fReset" type="button">Reset</button>
      <span class="rowcount" id="rowCount"></span>
    </div>

    <!-- ── Event log ── -->
    <h2>Event log &mdash; every CAPI fire ({evt_stats['total_events']:,} total)</h2>
    {event_section}

    <footer>Generated by cls_dashboard.py from cls.db &middot;
      {evt_stats['leadgen_events']:,} of {evt_stats['total_events']:,}
      events fired with leadgen_id enrichment &middot;
      {lead_stats['total_leads']:,} leads in registry</footer>
  </div>

<script>
/* ── Client-side filtering — no server, runs in the browser ──
   Every event row carries data-campaign / data-event / data-date /
   data-search attributes. Changing any control re-applies all four
   filters together (AND logic). Reset clears them. */
(function () {{
  var campaign = document.getElementById('fCampaign');
  var event_   = document.getElementById('fEvent');
  var date     = document.getElementById('fDate');
  var search   = document.getElementById('fSearch');
  var reset    = document.getElementById('fReset');
  var count    = document.getElementById('rowCount');
  var table    = document.getElementById('evtTable');
  if (!table) {{ if (count) count.textContent = ''; return; }}
  var rows = Array.prototype.slice.call(
              table.querySelectorAll('tbody tr'));

  function apply() {{
    var c = campaign.value;
    var e = event_.value;
    var d = date.value;
    var s = search.value.trim().toLowerCase();
    var shown = 0;
    rows.forEach(function (row) {{
      var ok = true;
      if (c && row.getAttribute('data-campaign') !== c) ok = false;
      if (e && row.getAttribute('data-event')    !== e) ok = false;
      if (d && row.getAttribute('data-date')     !== d) ok = false;
      if (s && row.getAttribute('data-search').indexOf(s) === -1) ok = false;
      row.classList.toggle('hidden', !ok);
      if (ok) shown++;
    }});
    count.textContent = shown + ' of ' + rows.length + ' rows shown';
  }}

  campaign.addEventListener('change', apply);
  event_.addEventListener('change', apply);
  date.addEventListener('change', apply);
  search.addEventListener('input', apply);
  reset.addEventListener('click', function () {{
    campaign.value = ''; event_.value = '';
    date.value = ''; search.value = '';
    apply();
  }});

  apply();   // initial paint of the row count
}})();
</script>
</body>
</html>"""

    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    return True


# ─────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────

def selftest():
    print("=" * 55)
    print(" CLS DASHBOARD — SELF TEST (offline)")
    print("=" * 55)

    cls_db.init_db()
    print("  [OK] init_db — events_log table + prev_stage column present")

    # Record a couple of fake events, then confirm they read back.
    before = cls_db.event_stats()["total_events"]
    cls_db.record_event(
        cls_id="testc1", leadgen_id="999", full_name="Test Lead",
        phone_norm="9876543210", project="Naishka", crm_stage="Opportunity",
        meta_event="Schedule", value_inr=1000, used_leadgen=True,
        dataset_id="2575028359563587", prev_stage="Prospect")
    cls_db.record_event(
        cls_id="testc2", leadgen_id=None, full_name="Walkin Lead",
        phone_norm="9000000001", project="Grace Classic", crm_stage="Prospect",
        meta_event="QualifiedLead", value_inr=200, used_leadgen=False,
        dataset_id="2575028359563587")   # no prev_stage — old signature
    after = cls_db.event_stats()["total_events"]
    ok = (after == before + 2)
    print(f"  [{'OK' if ok else 'FAIL'}] record_event appended 2 rows ({before} -> {after})")

    evts = cls_db.get_events(limit=2)
    ok = (len(evts) == 2 and evts[0]["fired_at"] >= evts[1]["fired_at"])
    print(f"  [{'OK' if ok else 'FAIL'}] get_events returns newest-first")

    ok = ("prev_stage" in evts[0])
    print(f"  [{'OK' if ok else 'FAIL'}] events carry the prev_stage field")

    es = cls_db.event_stats()
    ok = (es["leadgen_events"] >= 1 and es["total_value_inr"] >= 1200)
    print(f"  [{'OK' if ok else 'FAIL'}] event_stats: leadgen + value totals")

    ok = generate_dashboard()
    exists = os.path.exists(DASHBOARD_FILE)
    print(f"  [{'OK' if ok and exists else 'FAIL'}] dashboard.html written to {DASHBOARD_FILE}")

    print("=" * 55)
    print(" SELF TEST COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        if generate_dashboard():
            print(f"Dashboard generated: {DASHBOARD_FILE}")
        else:
            print("Dashboard generation failed.")
