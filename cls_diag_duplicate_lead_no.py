"""
cls_diag_duplicate_lead_no.py
v1.0 (2026-09-02)

READ-ONLY. Finds every crm_lead_no that appears on more than one
row in leads. Makes zero writes. See cls_db.py's _next_crm_lead_no()
docstring (v2.81) for why this can happen.

USAGE: python cls_diag_duplicate_lead_no.py

CHANGELOG:
  v1.0 (2026-09-02) — initial version, written after Srikanth found
  lead #8447 duplicated.
"""
import sys
import cls_db

def safe_print(*a, **k):
    if sys.stdout is not None:
        print(*a, **k)

def main():
    conn = cls_db._connect()
    try:
        dupes = conn.execute("""
            SELECT crm_lead_no, COUNT(*) cnt
            FROM leads
            WHERE crm_lead_no IS NOT NULL
            GROUP BY crm_lead_no
            HAVING COUNT(*) > 1
            ORDER BY crm_lead_no
        """).fetchall()

        if not dupes:
            safe_print("No duplicate crm_lead_no values found. Clean.")
            return

        safe_print(f"Found {len(dupes)} duplicated crm_lead_no value(s):\n")
        for d in dupes:
            lead_no = d["crm_lead_no"]
            safe_print("=" * 60)
            safe_print(f"crm_lead_no = {lead_no}  ({d['cnt']} rows)")
            safe_print("=" * 60)
            rows = conn.execute("""
                SELECT cls_id, full_name, phone_norm, email_norm,
                       project, source, current_stage,
                       cls_created_at, cls_updated_at
                FROM leads WHERE crm_lead_no = ?
                ORDER BY cls_created_at ASC
            """, (lead_no,)).fetchall()
            for i, r in enumerate(rows):
                tag = "ORIGINAL (earliest)" if i == 0 else "NEWER DUPLICATE"
                safe_print(f"  [{tag}]")
                safe_print(f"    cls_id         : {r['cls_id']}")
                safe_print(f"    full_name      : {r['full_name']}")
                safe_print(f"    phone_norm     : {r['phone_norm']}")
                safe_print(f"    email_norm     : {r['email_norm']}")
                safe_print(f"    project        : {r['project']}")
                safe_print(f"    source         : {r['source']}")
                safe_print(f"    current_stage  : {r['current_stage']}")
                safe_print(f"    cls_created_at : {r['cls_created_at']}")
                safe_print(f"    cls_updated_at : {r['cls_updated_at']}")
                safe_print("")
        safe_print(f"\nTotal duplicated crm_lead_no values: {len(dupes)}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
