"""
=============================================================
cls_diag_new_lead_capi.py — CLS Diagnostic — New Lead CAPI Fire Check
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

PURPOSE
-------
READ-ONLY. Checks the most recently created leads to see whether each
one has fired a CAPI event, is waiting in the retry queue, or has
fallen through both — the "zero CAPI history" symptom flagged from the
Export CAPI Events list.

Makes NO writes to cls.db. Makes NO API calls. Safe to run anytime.

RUN
---
  python cls_diag_new_lead_capi.py                # last 7 days, all projects
  python cls_diag_new_lead_capi.py --days 3
  python cls_diag_new_lead_capi.py --project "Naishka Homes"
=============================================================
"""

import argparse
from datetime import datetime, timedelta

import cls_db
import cls_capi_core


def classify(lead, fired_row, queue_row):
    stage = lead["current_stage"]
    in_target = stage in cls_capi_core.TARGET_STAGES

    if not in_target:
        return f"OK - stage '{stage}' is not a CAPI target stage, nothing should have fired"

    if fired_row:
        return f"FIRED - event logged {fired_row['fired_at']} ({fired_row['meta_event']})"

    if queue_row:
        if queue_row["status"] == "pending":
            return f"WAITING IN QUEUE - {queue_row['attempts']} attempt(s) so far, last error: {queue_row['last_error']}"
        elif queue_row["status"] == "failed_permanent":
            return f"STUCK - gave up after {queue_row['attempts']} attempts, last error: {queue_row['last_error']}"
        else:
            return f"IN QUEUE - status={queue_row['status']}"

    return "NEVER FIRED, NEVER QUEUED - the fire hook was never triggered for this lead (this is the bug)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--project", type=str, default=None)
    args = parser.parse_args()

    cutoff = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    conn = cls_db._connect()
    try:
        query = ("SELECT cls_id, full_name, project, current_stage, last_fired_stage, "
                  "cls_created_at, source FROM leads WHERE cls_created_at >= ?")
        params = [cutoff]
        if args.project:
            query += " AND project = ?"
            params.append(args.project)
        query += " ORDER BY cls_created_at ASC"
        leads = [dict(r) for r in conn.execute(query, params).fetchall()]

        events = {}
        for r in conn.execute("SELECT cls_id, fired_at, meta_event FROM events_log ORDER BY fired_at ASC"):
            row = dict(r)
            events.setdefault(row["cls_id"], row)

        queue = {}
        for r in conn.execute("SELECT cls_id, target_stage, attempts, status, last_error FROM capi_fire_queue"):
            row = dict(r)
            queue[row["cls_id"]] = row
    finally:
        conn.close()

    print("=" * 70)
    print(" CLS DIAGNOSTIC - New Lead CAPI Fire Check")
    print(f" Leads created since {cutoff}" + (f" | project={args.project}" if args.project else " | all projects"))
    print("=" * 70)

    if not leads:
        print("No leads found in this window.")
        return

    counts = {"FIRED": 0, "WAITING": 0, "STUCK": 0, "NEVER": 0, "OK": 0}
    for lead in leads:
        fired_row = events.get(lead["cls_id"])
        queue_row = queue.get(lead["cls_id"])
        result = classify(lead, fired_row, queue_row)

        if result.startswith("FIRED"):
            counts["FIRED"] += 1
        elif result.startswith("WAITING"):
            counts["WAITING"] += 1
        elif result.startswith("STUCK"):
            counts["STUCK"] += 1
        elif result.startswith("NEVER"):
            counts["NEVER"] += 1
        else:
            counts["OK"] += 1

        print(f"\n{lead['full_name']} | {lead['project']} | stage={lead['current_stage']} "
              f"| created={lead['cls_created_at']} | source={lead['source']}")
        print(f"  -> {result}")

    print("\n" + "=" * 70)
    print(f" SUMMARY - {len(leads)} lead(s) checked")
    print(f"   Fired OK:              {counts['FIRED']}")
    print(f"   Waiting in queue:      {counts['WAITING']}")
    print(f"   Stuck (gave up):       {counts['STUCK']}")
    print(f"   Never fired/queued:    {counts['NEVER']}   <-- this is the number that matters")
    print(f"   Not a target stage:    {counts['OK']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
