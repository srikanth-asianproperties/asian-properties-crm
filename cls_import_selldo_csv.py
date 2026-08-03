"""
=============================================================
cls_import_selldo_csv.py  —  CLS Sell.do Historical CSV Bulk Import
=============================================================
Version : 1.6
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.6  (2026-08) — BASE_DIR updated from C:\CLS to D:\CLS — drive migration, 2026-08.

v1.5  (July 2026) — per-insert guardrail logging for --commit runs.
  For every row whose action is "insert" AND commit=True, run() now
  logs one "[insert] cls_id=... crm_lead_no=... last_fired_stage=...
  drip_paused=..." line, read back from the actual just-written row
  via the existing cls_db.get_lead_by_id() (no new cls_db function,
  no direct sqlite3 access — this is a genuine post-write confirmation
  of what was persisted, not a restatement of the input). Dry runs are
  unaffected (cls_id is None for an insert-preview, and there's no row
  to read back yet) — this only fires under --commit. --selftest
  gained a regression that runs a real commit=True import against a
  throwaway DB and confirms the expected [insert] line appears with
  the correct last_fired_stage/drip_paused values.

v1.4  (July 2026) — fix a dry-run undercount in the CSV-internal
  duplicate logic: run()'s "Duplicates within CSV" count (and the
  total-rows arithmetic built on it) silently dropped a duplicate
  group's older rows whenever the group's PRIMARY row's action was
  "insert" rather than a match — because the old code used
  primary_result["cls_id"] as its "is this primary OK?" check, and a
  dry-run (commit=False) insert-preview correctly has cls_id=None (no
  lead has actually been created yet). That's a normal, expected state
  during a dry run — not the same thing as the primary being invalid —
  but the code treated them identically and "continue"d past the
  group's older rows without counting or logging them anywhere,
  producing a real CSV run where Total(7670) != Insert(3911) +
  Update(3753) + Duplicates(1) + Skipped(0) — 5 rows vanished from the
  summary with no indication anything was skipped. Root cause found by
  reproducing against the real export: dedupe_by_phone() actually finds
  6 duplicate groups (6 older rows total), but only 1 group's primary
  was a MATCH (real cls_id available even under dry-run) — the other 5
  groups' primaries were fresh inserts, so their cls_id was None and
  their older rows were silently uncounted.

  FIX: the count (dup_logged += len(older_rows)) now happens whenever
  the primary's own action is valid (i.e. NOT skip_invalid_row),
  regardless of commit mode. The actual activity_log write is still
  gated on commit=True, at which point cls_id is guaranteed to be
  populated (real for both insert and update actions). No change to
  insert/update/skip counts — those were always correct, this only
  affected the "Duplicates within CSV" number and the rows the dry-run
  summary appeared to lose track of.

v1.3  (July 2026) — fix the REAL root cause of every "Created At" row
  being skipped: the CSV's actual column header is
  "Created At(System Date)", not "Created At". load_csv_rows() was
  reading the value via a plain lookup keyed on "Created At", which
  doesn't exist in the real export — every row silently got "" instead
  of raising an error, so v1.2's AM/PM fix was correct but never ran
  (there was nothing to parse). NEW CREATED_AT_CSV_HEADER =
  "Created At(System Date)" — load_csv_rows() renames that column to
  the canonical "Created At" key immediately after reading (only if
  "Created At" isn't already present, so an export that genuinely uses
  the plain name still works unchanged), before any other lookup in
  this script (or cls_db.import_selldo_csv_row()'s csv_row contract,
  which still expects the plain "Created At" key and was NOT touched)
  ever sees the row. No assumption is made about any other differently
  -named date column (e.g. a "Custom Date" variant) — this fixes only
  the one confirmed string mismatch. --selftest gained a regression
  test that builds a real CSV with the actual
  "Created At(System Date)" header and confirms load_csv_rows() reads
  and parses it correctly.

v1.2  (July 2026) — fix "Created At" parsing for Sell.do's real export
  format. The field is a 12-hour timestamp with a mixed-case AM/PM
  marker — capital first letter, lowercase second ("Pm"/"Am", e.g.
  "13/02/2026 06:03:56 Pm"), not the standard "PM"/"AM" every
  CREATED_AT_FORMATS entry expected (none had a 12-hour %I/%p format
  at all, so every real row failed as unparseable). parse_created_at()
  now normalizes a trailing am/pm marker (any case) to standard
  uppercase before trying the formats, and a new 12-hour
  "%d/%m/%Y %I:%M:%S %p" entry was added to CREATED_AT_FORMATS —
  together these handle "Pm"/"Am"/"PM"/"AM"/"pm"/"am" all the same
  way. --selftest gained both a mixed-case and a standard-case check.

v1.1  (July 2026) — fix "Lead's Id" parsing for Sell.do's real export
  format. The column does not arrive as a plain integer — it's an
  Excel HYPERLINK formula:
    =HYPERLINK("https://app.sell.do/client/0/xxxx/yyyy/f/AddNote", 7899)
  NEW extract_selldo_lead_id(raw) pulls the trailing number out of
  that shape (same trailing-number-before-the-closing-paren idea as
  Job B's own selldo_url extraction, reimplemented independently here
  — selldo_to_cls.py was not opened to build this, per the standing
  "never touch Job B" rule). Falls back to using the raw value as-is
  if it doesn't match the HYPERLINK shape (e.g. an already-cleaned
  CSV), so this is backward compatible with a plain-integer column
  too. Applied in load_csv_rows() right after the CSV is read, before
  any matching/dedup logic sees "Lead's Id" — cls_db.import_selldo_
  csv_row() itself is unchanged and still expects a plain numeric
  string.

v1.0  (July 2026) — initial version, per Srikanth's locked design.

PURPOSE
-------
One-time historical backfill of Sell.do leads into cls.db, from a CSV
export the operator has already downloaded. Roughly 7,000 rows
expected; ~4,000 as brand-new inserts, the remainder matching existing
CLS leads by phone/email (or by an already-known selldo_lead_id).

This script is NOT part of the A->B->C->D pipeline, is NOT scheduled,
and does NOT set or check any cls_db completion flag. It runs
independently, whenever the operator runs it by hand. selldo_to_cls.py
(Job B) was NOT read, referenced, or modified to build this — Job B
stays exactly as it is.

Option B (Srikanth's decision): the CSV's own "Lead's Id" becomes the
CLS crm_lead_no (shown in the UI as "APX-<id>") for every row this
script touches, matched or new — so CLS's friendly IDs line up with
Sell.do's own numbering across the whole imported history.

All matching, insert, and update logic lives in cls_db.py v2.17's
import_selldo_csv_row() — this script's job is CSV-specific mechanics
only: reading the file, cleaning pandas NaN artefacts, parsing
"Created At", deduping rows that share a phone number, and reporting a
summary. No sqlite3 access happens directly in this file.

CSV COLUMNS USED (per Srikanth's spec)
---------------------------------------
  "Lead's Id", "First Name", "Last Name", "Lead Stage", "Phone",
  "Email", "Projects", "First-Campaign", "Attended By", "Created At"
Read but ignored: "Lead Status", "First-Sub Source",
"Attended By Sales Id", "Secondary Phones", "Secondary Emails".

DEDUPE (per phone_norm group)
------------------------------
Within each group of CSV rows sharing the same phone_norm, the row
with the LATEST "Created At" is treated as the primary (the one
actually passed to cls_db.import_selldo_csv_row). Every older
Sell.do ID in that group is logged onto the PRIMARY lead's
activity_log as 'duplicate_selldo_id_from_import' once the primary
row has been imported/matched (so a cls_id exists to attach it to).
Rows with an empty phone_norm AND an empty email_norm go to
skip_invalid_row (never grouped — there is no key to group them by).

RUN
---
  python cls_import_selldo_csv.py "C:\\path\\to\\export.csv"           # dry-run (default)
  python cls_import_selldo_csv.py "C:\\path\\to\\export.csv" --commit  # writes
  python cls_import_selldo_csv.py --selftest                        # offline, no CSV, no DB writes
=============================================================
"""

import os
import re
import sys
import shutil
import tempfile
from datetime import datetime
from collections import defaultdict

import pandas as pd

import cls_db   # the foundation layer — the ONLY way this script touches cls.db

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR = r"D:\CLS"
LOG_FILE = os.path.join(BASE_DIR, "cls_import_selldo_log.txt")

CSV_COLUMNS_USED = [
    "Lead's Id", "First Name", "Last Name", "Lead Stage", "Phone",
    "Email", "Projects", "First-Campaign", "Attended By", "Created At",
]
CSV_COLUMNS_IGNORED = [
    "Lead Status", "First-Sub Source", "Attended By Sales Id",
    "Secondary Phones", "Secondary Emails",
]

# Sell.do's real CSV header for this column — confirmed directly
# against a live export — is "Created At(System Date)", not the plain
# "Created At" every lookup in this script (and cls_db.import_selldo_
# csv_row()'s csv_row contract) uses. load_csv_rows() renames it to
# the canonical "Created At" key right after reading, so this is the
# ONLY place that needs to know about the real header name.
CREATED_AT_CSV_HEADER = "Created At(System Date)"

# Sell.do's own export formats tried first; pandas.to_datetime as a
# last-resort fallback for anything these miss. The %I/%p entry is
# Sell.do's real export shape (12-hour + AM/PM marker, e.g.
# "13/02/2026 06:03:56 Pm") — parse_created_at() normalizes the
# marker's case before this is tried, so mixed-case "Pm"/"Am" match
# just as well as standard "PM"/"AM".
CREATED_AT_FORMATS = [
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %I:%M:%S %p",
]
CLS_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"   # what cls_db._now() produces


# ─────────────────────────────────────────────────────────────
# LOGGING  —  same format/pattern as every other CLS job.
# Guarded + UTF-8-safe: this script is normally run interactively via
# python.exe (which has a console), but the guard is kept for
# consistency with the rest of CLS per CLAUDE.md's "guard every
# print()" rule.
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    timestamp = datetime.now().strftime(CLS_TIMESTAMP_FORMAT)
    entry = f"[{timestamp}] [{level}] {message}"
    if sys.stdout is not None:
        safe_entry = entry.encode("utf-8", errors="replace").decode("utf-8")
        try:
            print(safe_entry)
        except UnicodeEncodeError:
            print(safe_entry.encode("ascii", errors="replace").decode("ascii"))
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# "Created At" PARSING
# ─────────────────────────────────────────────────────────────

def parse_created_at(raw):
    """
    Try Sell.do's known export formats first, then fall back to
    pandas.to_datetime (errors='coerce'). Returns a CLS-format
    "%Y-%m-%d %H:%M:%S" string, or None if truly unparseable.

    Sell.do's real export uses a mixed-case AM/PM marker — capital
    first letter, lowercase second ("Pm"/"Am", e.g.
    "13/02/2026 06:03:56 Pm") — rather than standard "PM"/"AM". A
    trailing am/pm marker of any case is normalized to standard
    uppercase before the formats below are tried, so "Pm"/"Am"/"PM"/
    "AM"/"pm"/"am" are all treated identically.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s.lower() in ("nan", "none", "nat"):
        return None

    s = re.sub(r"\b(am|pm)\b$", lambda m: m.group(1).upper(), s, flags=re.IGNORECASE)

    for fmt in CREATED_AT_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime(CLS_TIMESTAMP_FORMAT)
        except ValueError:
            continue

    coerced = pd.to_datetime(s, errors="coerce")
    if pd.isna(coerced):
        return None
    return coerced.strftime(CLS_TIMESTAMP_FORMAT)


# ─────────────────────────────────────────────────────────────
# "Lead's Id" PARSING  —  Sell.do exports it as an Excel HYPERLINK
# ─────────────────────────────────────────────────────────────

def extract_selldo_lead_id(raw):
    """
    Sell.do's "Lead's Id" column arrives as an Excel HYPERLINK formula,
    not a plain integer:
      =HYPERLINK("https://app.sell.do/client/0/xxxx/yyyy/f/AddNote", 7899)
    Extracts the trailing number just before the closing parenthesis —
    same trailing-number-before-the-closing-paren idea as Job B's own
    selldo_url extraction, reimplemented independently here
    (selldo_to_cls.py was not opened to build this).

    Falls back to the raw value, stripped, if it doesn't match the
    HYPERLINK shape at all — so a CSV that's already plain integers
    (e.g. re-saved/cleaned by hand) still works unchanged.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    match = re.search(r',\s*"?(\d+)"?\s*\)\s*$', s)
    if match:
        return match.group(1)
    return s


# ─────────────────────────────────────────────────────────────
# CSV LOADING + CLEANING
# ─────────────────────────────────────────────────────────────

def load_csv_rows(csv_path):
    """
    Reads the CSV with pandas, keeps only the columns this import
    uses, replaces NaN/blank cells with "" (so cls_db.import_selldo_
    csv_row() never has to guard against pandas float-NaN artefacts),
    parses "Created At" into CLS's own timestamp format up front
    (needed for the dedupe-by-latest step below and by cls_db.import_
    selldo_csv_row(), which does not parse dates itself), and extracts
    the plain numeric id out of "Lead's Id"'s HYPERLINK-formula shape
    (see extract_selldo_lead_id()) — cls_db.import_selldo_csv_row()
    expects a plain numeric string there, not the formula.

    Returns a list of dicts, one per CSV row. "Created At" is replaced
    with the parsed CLS-format string, or "" if unparseable (rows with
    an unparseable Created At are rejected downstream by
    cls_db.import_selldo_csv_row()'s own validation, same as any other
    invalid row).
    """
    df = pd.read_csv(csv_path, dtype=str)

    # Sell.do's real header for this column is "Created At(System
    # Date)" — rename it to the canonical "Created At" key everything
    # else expects. Only renames if "Created At" isn't already present,
    # so an export that genuinely has the plain column name is unaffected.
    if "Created At" not in df.columns and CREATED_AT_CSV_HEADER in df.columns:
        df = df.rename(columns={CREATED_AT_CSV_HEADER: "Created At"})

    for col in CSV_COLUMNS_USED:
        if col not in df.columns:
            df[col] = ""

    keep_cols = [c for c in CSV_COLUMNS_USED if c in df.columns]
    df = df[keep_cols]
    df = df.where(pd.notnull(df), "")   # NaN -> "" everywhere

    rows = []
    for record in df.to_dict(orient="records"):
        record["Lead's Id"] = extract_selldo_lead_id(record.get("Lead's Id"))
        record["Created At"] = parse_created_at(record.get("Created At")) or ""
        rows.append(record)
    return rows


# ─────────────────────────────────────────────────────────────
# DEDUPE BY PHONE  —  keep latest Created At as primary per group
# ─────────────────────────────────────────────────────────────

def dedupe_by_phone(rows):
    """
    Groups rows by phone_norm. Rows with empty phone_norm AND empty
    email_norm are routed straight to skip_invalid_row (never grouped
    — there is no key to group them by, and import_selldo_csv_row()
    would reject them anyway).

    Returns (primary_rows, invalid_rows, duplicate_groups) where:
      primary_rows      : one row per phone_norm group (or standalone
                           email-only rows), the one to actually import
      invalid_rows       : rows with neither phone_norm nor email_norm
      duplicate_groups   : list of (primary_row, [older_row, ...]) for
                           groups that had more than one row
    """
    groups = defaultdict(list)
    email_only = []
    invalid_rows = []

    for row in rows:
        phone_norm = cls_db.norm_phone(row.get("Phone"))
        email_norm = cls_db.norm_email(row.get("Email"))
        if not phone_norm and not email_norm:
            invalid_rows.append(row)
        elif phone_norm:
            groups[phone_norm].append(row)
        else:
            email_only.append(row)   # no phone to key on, but has an email

    primary_rows = []
    duplicate_groups = []

    for phone_norm, group_rows in groups.items():
        if len(group_rows) == 1:
            primary_rows.append(group_rows[0])
            continue
        group_rows_sorted = sorted(
            group_rows, key=lambda r: r.get("Created At") or "", reverse=True
        )
        primary = group_rows_sorted[0]
        older = group_rows_sorted[1:]
        primary_rows.append(primary)
        duplicate_groups.append((primary, older))

    primary_rows.extend(email_only)

    return primary_rows, invalid_rows, duplicate_groups


# ─────────────────────────────────────────────────────────────
# "Attended By" NAME CHECK  —  read-only, via existing cls_db lookup
# ─────────────────────────────────────────────────────────────

def get_known_owner_names():
    """
    Known salesperson names = users.owner_match_name for every CRM
    login (case-insensitive). Read-only, via the existing
    cls_db.get_all_users_detailed() — no new cls_db function needed.
    """
    names = set()
    for u in cls_db.get_all_users_detailed():
        match_name = (u.get("owner_match_name") or "").strip()
        if match_name:
            names.add(match_name.lower())
    return names


# ─────────────────────────────────────────────────────────────
# BACKUP  —  always taken before any --commit write
# ─────────────────────────────────────────────────────────────

def backup_db():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BASE_DIR, f"cls.db.pre_import_{ts}")
    shutil.copy2(cls_db.DB_FILE, backup_path)
    return backup_path


# ─────────────────────────────────────────────────────────────
# MAIN IMPORT RUN
# ─────────────────────────────────────────────────────────────

def run(csv_path, commit=False):
    log("=" * 60)
    log(f"CLS Sell.do CSV import starting — csv={csv_path} commit={commit}")

    backup_path = None
    if commit:
        try:
            backup_path = backup_db()
            log(f"Pre-import backup written: {backup_path}")
        except Exception as e:
            log(f"FATAL — could not back up cls.db before --commit: {e}", level="ERROR")
            log("Aborting. No rows were touched.", level="ERROR")
            return

    rows = load_csv_rows(csv_path)
    log(f"CSV rows read: {len(rows)}")

    primary_rows, dedupe_invalid_rows, duplicate_groups = dedupe_by_phone(rows)

    known_owners = get_known_owner_names()
    unknown_owner_names = set()

    results = []
    invalid_count = len(dedupe_invalid_rows)

    for row in primary_rows:
        result = cls_db.import_selldo_csv_row(row, commit=commit)
        results.append(result)

        attended_by = str(row.get("Attended By") or "").strip()
        if attended_by and attended_by.lower() not in known_owners:
            unknown_owner_names.add(attended_by)

        row_sid = row.get("Lead's Id")
        for warning in result.get("warnings", []):
            log(f"  [warn] Lead's Id={row_sid!r}: {warning}")

        if commit and result["action"] == "insert":
            lead = cls_db.get_lead_by_id(result["cls_id"])
            if lead:
                log(f"  [insert] cls_id={lead['cls_id']} crm_lead_no={lead['crm_lead_no']} "
                    f"last_fired_stage={lead['last_fired_stage']!r} drip_paused={lead['drip_paused']!r}")

    # ── Log the CSV-internal duplicates onto the primary lead ──
    # NOTE (fixed — see v1.4 changelog): counting must NOT depend on
    # primary_result["cls_id"] being populated. During a DRY RUN
    # (commit=False), a primary whose action is "insert" correctly has
    # cls_id=None — no lead has actually been created yet — but that's
    # NOT the same thing as the primary being invalid. The old code
    # used cls_id as its "was the primary OK?" check, which silently
    # dropped every duplicate-group's older rows from BOTH the count
    # and the dry-run summary whenever the primary was a fresh insert
    # (as opposed to a match onto an existing lead) — undercounting
    # "Duplicates within CSV" and making the total-rows arithmetic not
    # add up, with no indication anything was skipped. The count now
    # depends only on whether the primary's own action was valid
    # (i.e. not skip_invalid_row); the actual write is still gated on
    # commit (at which point cls_id is guaranteed to exist, whether
    # the primary was inserted or matched).
    dup_logged = 0
    for primary_row, older_rows in duplicate_groups:
        primary_result = next(
            (r for r in results if r.get("new_crm_lead_no") == _safe_int(primary_row.get("Lead's Id"))
             and r["action"] != "skip_invalid_row"),
            None,
        )
        if primary_result is None:
            continue   # primary itself was invalid/skipped — nothing to attach history to
        dup_logged += len(older_rows)
        if commit:
            cls_id = primary_result["cls_id"]
            primary_sid = str(primary_row.get("Lead's Id") or "").strip()
            for older in older_rows:
                old_id = str(older.get("Lead's Id") or "").strip()
                ts = older.get("Created At") or "(unknown time)"
                description = (
                    f"CSV import found an older Sell.do ID {old_id} (created_at {ts}) "
                    f"for this phone. Kept latest ({primary_sid}) "
                    f"as primary; logging the earlier one for history."
                )
                _log_duplicate_activity(cls_id, old_id, description)

    insert_count = sum(1 for r in results if r["action"] == "insert")
    update_id_only_count = sum(1 for r in results if r["action"] == "update_id_only")
    update_backfill_count = sum(1 for r in results if r["action"] == "update_id_and_backfill")
    skip_invalid_count = invalid_count + sum(1 for r in results if r["action"] == "skip_invalid_row")

    label = "WROTE" if commit else "WOULD"
    log("")
    log("=" * 60)
    log(f" IMPORT SUMMARY ({label})")
    log("=" * 60)
    log(f"  Total CSV rows read     : {len(rows)}")
    log(f"  Rows to INSERT (new)    : {insert_count}")
    log(f"  Rows to UPDATE (match)  : {update_id_only_count + update_backfill_count} of which:")
    log(f"     - id-only changes     : {update_id_only_count}")
    log(f"     - id + backfill       : {update_backfill_count}")
    log(f"  Duplicates within CSV   : {dup_logged} (older Sell.do IDs logged)")
    log(f"  Skipped (invalid rows)  : {skip_invalid_count}")
    log(f"  Unknown 'Attended By'   : {len(unknown_owner_names)} names"
        + (f" -> {sorted(unknown_owner_names)}" if unknown_owner_names else ""))

    if commit:
        log(f"  Pre-import backup       : {backup_path}")
        log(f"  activity_log rows written (approx):")
        log(f"     imported_from_selldo         : {insert_count}")
        log(f"     lead_id_changed_from_import  : "
            f"{sum(1 for r in results if r['action'] in ('update_id_only', 'update_id_and_backfill') and r['prev_crm_lead_no'] != r['new_crm_lead_no'])}")
        log(f"     backfilled_from_selldo_import: "
            f"{sum(len(r['backfilled']) for r in results)}")
        log(f"     duplicate_selldo_id_from_import: {dup_logged}")
    else:
        log("")
        log("Dry run only — nothing was written. To commit these changes, run:")
        log(f'  python cls_import_selldo_csv.py "{csv_path}" --commit')

    log("=" * 60)


def _safe_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _log_duplicate_activity(cls_id, old_selldo_id, description):
    """
    Thin wrapper so the one activity_log write this script does NOT
    route through cls_db.import_selldo_csv_row() (the CSV-internal
    duplicate note, attached to the PRIMARY lead, not the row being
    imported) still goes through cls_db — never direct sqlite3 here.
    """
    cls_db.log_duplicate_selldo_import(cls_id, old_selldo_id, description)


# ─────────────────────────────────────────────────────────────
# SELF-TEST  —  offline, no CSV, no DB writes
# ─────────────────────────────────────────────────────────────

def selftest():
    global BASE_DIR, LOG_FILE

    print("=" * 55)
    print(" cls_import_selldo_csv.py — SELF TEST (v1.5)")
    print("=" * 55)

    ok = hasattr(cls_db, "import_selldo_csv_row")
    print(f"  [{'OK' if ok else 'FAIL'}] cls_db.import_selldo_csv_row exists")

    ok = cls_db.norm_phone("+91 98765 43210") == "9876543210"
    print(f"  [{'OK' if ok else 'FAIL'}] cls_db.norm_phone works")

    ok = cls_db.norm_email("  Test@Example.COM ") == "test@example.com"
    print(f"  [{'OK' if ok else 'FAIL'}] cls_db.norm_email works")

    ok = callable(cls_db.find_match)
    print(f"  [{'OK' if ok else 'FAIL'}] cls_db.find_match callable")

    parsed = parse_created_at("21/07/2026 10:30:00")
    ok = parsed == "2026-07-21 10:30:00"
    print(f"  [{'OK' if ok else 'FAIL'}] parse_created_at handles dd/mm/yyyy — got {parsed!r}")

    parsed_mixed_case = parse_created_at("13/02/2026 06:03:56 Pm")
    ok = parsed_mixed_case == "2026-02-13 18:03:56"
    print(f"  [{'OK' if ok else 'FAIL'}] parse_created_at handles Sell.do's mixed-case 'Pm' — got {parsed_mixed_case!r}")

    parsed_standard_case = parse_created_at("13/02/2026 06:03:56 PM")
    ok = parsed_standard_case == "2026-02-13 18:03:56"
    print(f"  [{'OK' if ok else 'FAIL'}] parse_created_at handles standard-case 'PM' — got {parsed_standard_case!r}")

    parsed_bad = parse_created_at("not a date")
    ok = parsed_bad is None
    print(f"  [{'OK' if ok else 'FAIL'}] parse_created_at rejects garbage")

    # ── Regression: Sell.do's real header is "Created At(System Date)",
    # not "Created At" — build an actual CSV with that real header and
    # confirm load_csv_rows() reads and correctly parses the value,
    # instead of silently defaulting it to "" (the bug this catches).
    import csv as _csv
    real_header_dir = tempfile.mkdtemp(prefix="cls_import_selftest_csv_")
    try:
        real_header_csv = os.path.join(real_header_dir, "real_header_sample.csv")
        with open(real_header_csv, "w", newline="", encoding="utf-8") as f:
            writer = _csv.writer(f)
            writer.writerow([
                "Lead's Id", "First Name", "Last Name", "Lead Stage", "Lead Status",
                "Phone", "Secondary Phones", "Email", "Secondary Emails", "Projects",
                "First-Campaign", "First-Source Of Enquiry", "First-Sub Source",
                "Attended By", "Created At(System Date)", "Attended By Sales Id",
            ])
            writer.writerow([
                "8001", "Header", "Test", "Prospect", "Open", "9444444444", "",
                "headertest@example.com", "", "Naishka", "FB_1", "Facebook", "",
                "Priya Sales", "13/02/2026 06:03:56 Pm", "1",
            ])
        loaded_rows = load_csv_rows(real_header_csv)
        got_created_at = loaded_rows[0].get("Created At") if loaded_rows else None
        ok = len(loaded_rows) == 1 and got_created_at == "2026-02-13 18:03:56"
        print(f"  [{'OK' if ok else 'FAIL'}] load_csv_rows reads the real 'Created At(System Date)' header — got {got_created_at!r}")
    finally:
        shutil.rmtree(real_header_dir, ignore_errors=True)

    # ── Isolated, throwaway DB for the row-shape check below ──
    # import_selldo_csv_row() does a real (read-only, commit=False)
    # lookup against whatever cls.db it's pointed at. Redirecting
    # cls_db.DB_FILE to a fresh temp file here means this self-test
    # never reads OR writes the real C:\CLS\cls.db, and its result is
    # deterministic regardless of what's already in production (a
    # synthetic phone number could otherwise coincidentally match a
    # real lead and turn this into an "update" instead of "insert").
    real_db_file = cls_db.DB_FILE
    real_base_dir = cls_db.BASE_DIR
    tmp_dir = tempfile.mkdtemp(prefix="cls_import_selftest_")
    try:
        cls_db.DB_FILE = os.path.join(tmp_dir, "selftest_cls.db")
        cls_db.BASE_DIR = tmp_dir
        cls_db.init_db()

        synthetic_row = {
            "Lead's Id": "999999",
            "First Name": "Selftest",
            "Last Name": "Row",
            "Lead Stage": "Prospect",
            "Phone": "9999999999",
            "Email": "selftest_row_that_should_not_exist@example.invalid",
            "Projects": "Test Project",
            "First-Campaign": "",
            "Attended By": "Nobody",
            "Created At": "2026-01-01 10:00:00",
        }
        result = cls_db.import_selldo_csv_row(synthetic_row, commit=False)
        expected_keys = {"action", "cls_id", "prev_crm_lead_no", "new_crm_lead_no", "backfilled", "warnings"}
        ok = set(result.keys()) == expected_keys and result["action"] == "insert"
        print(f"  [{'OK' if ok else 'FAIL'}] import_selldo_csv_row returns expected shape — got {result}")

        invalid_row = dict(synthetic_row)
        invalid_row["Phone"] = ""
        invalid_row["Email"] = ""
        result2 = cls_db.import_selldo_csv_row(invalid_row, commit=False)
        ok = result2["action"] == "skip_invalid_row"
        print(f"  [{'OK' if ok else 'FAIL'}] row with no phone/email -> skip_invalid_row")

        # ── Regression: dry-run duplicate-group undercount (v1.4 fix) ──
        # Two rows share a phone with NO existing match in this fresh
        # DB, so the latest-Created-At row becomes the primary and its
        # action is "insert" — under dry-run (commit=False) that means
        # cls_id=None, which is the exact shape that used to make the
        # older row silently vanish from "Duplicates within CSV"
        # (see v1.4 changelog). Runs run() itself in dry-run mode and
        # checks the printed summary line, since that's the actual
        # code path the bug lived in.
        import io
        import contextlib
        import csv as _csv2

        dup_csv_dir = tempfile.mkdtemp(prefix="cls_import_selftest_dupcsv_")
        real_local_base_dir = BASE_DIR
        real_local_log_file = LOG_FILE
        try:
            BASE_DIR = dup_csv_dir
            LOG_FILE = os.path.join(dup_csv_dir, "selftest_import_log.txt")

            dup_csv_path = os.path.join(dup_csv_dir, "dup_sample.csv")
            with open(dup_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = _csv2.writer(f)
                writer.writerow([
                    "Lead's Id", "First Name", "Last Name", "Lead Stage",
                    "Phone", "Email", "Projects", "First-Campaign",
                    "Attended By", "Created At",
                ])
                writer.writerow([
                    "8101", "Older", "Duplicate", "Incoming", "9666666666",
                    "", "Naishka", "", "Nobody", "2026-01-01 10:00:00",
                ])
                writer.writerow([
                    "8102", "Newer", "Primary", "Incoming", "9666666666",
                    "", "Naishka", "", "Nobody", "2026-03-01 10:00:00",
                ])
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                run(dup_csv_path, commit=False)
            match = re.search(r"Duplicates within CSV\s*:\s*(\d+)", captured.getvalue())
            got_dup_count = int(match.group(1)) if match else None
            ok = got_dup_count == 1
            print(f"  [{'OK' if ok else 'FAIL'}] dry-run counts a duplicate group whose primary is a fresh insert — got Duplicates within CSV={got_dup_count!r} (expected 1)")
        finally:
            BASE_DIR = real_local_base_dir
            LOG_FILE = real_local_log_file
            shutil.rmtree(dup_csv_dir, ignore_errors=True)

        # ── Regression: per-insert guardrail logging (v1.5) ──
        # A real --commit run should log one "[insert] cls_id=...
        # last_fired_stage=... drip_paused=..." line per inserted row,
        # read back from the actual written row (not just restating
        # the input). Runs run() with commit=True against the same
        # throwaway DB and checks the captured log output directly.
        guardrail_csv_dir = tempfile.mkdtemp(prefix="cls_import_selftest_guardrail_")
        real_local_base_dir = BASE_DIR
        real_local_log_file = LOG_FILE
        try:
            BASE_DIR = guardrail_csv_dir
            LOG_FILE = os.path.join(guardrail_csv_dir, "selftest_import_log.txt")

            guardrail_csv_path = os.path.join(guardrail_csv_dir, "guardrail_sample.csv")
            with open(guardrail_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = _csv2.writer(f)
                writer.writerow([
                    "Lead's Id", "First Name", "Last Name", "Lead Stage",
                    "Phone", "Email", "Projects", "First-Campaign",
                    "Attended By", "Created At",
                ])
                writer.writerow([
                    "8201", "Guardrail", "Check", "Prospect", "9777777777",
                    "", "Naishka", "", "Nobody", "2026-04-01 09:00:00",
                ])
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                run(guardrail_csv_path, commit=True)
            log_text = captured.getvalue()
            match = re.search(
                r"\[insert\] cls_id=(\S+) crm_lead_no=8201 last_fired_stage='Prospect' drip_paused=1",
                log_text,
            )
            ok = match is not None
            print(f"  [{'OK' if ok else 'FAIL'}] --commit logs a per-insert guardrail line — {'found' if ok else 'MISSING'}: "
                  + (match.group(0) if match else "(no matching line in output)"))
        finally:
            BASE_DIR = real_local_base_dir
            LOG_FILE = real_local_log_file
            shutil.rmtree(guardrail_csv_dir, ignore_errors=True)
    finally:
        cls_db.DB_FILE = real_db_file
        cls_db.BASE_DIR = real_base_dir
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("=" * 55)
    print(" SELF TEST COMPLETE — offline logic verified, cls.db untouched.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--selftest" in args:
        selftest()
        sys.exit(0)

    csv_args = [a for a in args if not a.startswith("--")]
    if not csv_args:
        log("Usage: python cls_import_selldo_csv.py \"C:\\path\\to\\export.csv\" [--commit]", level="ERROR")
        log("       python cls_import_selldo_csv.py --selftest", level="ERROR")
        sys.exit(1)

    csv_path = csv_args[0]
    if not os.path.exists(csv_path):
        log(f"FATAL — CSV file not found: {csv_path}", level="ERROR")
        sys.exit(1)

    run(csv_path, commit=("--commit" in args))
