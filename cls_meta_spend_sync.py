"""
=============================================================
cls_meta_spend_sync.py  —  Meta ad-spend sync (Finance F1)
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.0 (2026-09-30) — Initial version, Finance F1.
  Pulls per-ad, per-day spend from Meta's Insights API (level=ad,
  time_increment=1) for every account in cls_db.META_AD_ACCOUNTS and upserts
  it into ad_spend_daily via cls_db.upsert_ad_spend_rows() (idempotent, keyed
  spend_date + ad_id). Ops-only script outside the Job A-D naming — logs to
  job_results.txt as "Meta Spend Sync".

MODES
-----
  (default)              re-pull the last 3 days (Meta revises recent numbers).
  --backfill YYYY-MM-DD  load from that date to today in MONTHLY chunks. Safe to
                         re-run / resume: every chunk is an idempotent upsert.
  --dry-run              fetch and print counts only; writes nothing.
  --selftest             config sanity only; no network, no DB.

Never raises to the scheduler: every failure is logged, reported to
job_results.txt as FAILED, and the script exits 0. Token comes from .env
(META_SYSTEM_USER_TOKEN, same variable Job A uses); the DB target comes from
CLS_DB_PATH, set by run_cls_meta_spend_sync.bat (CLS1.db). Spend is in the
ad account's own currency (INR for act_825098213089084) and is stored as
Meta reports it — see the F1 hand-over note on GST.
"""

import os
import sys
import time
from datetime import datetime, timedelta

BASE_DIR = r"D:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db
import cls_capi_core
import requests
from dotenv import dotenv_values

LOG_FILE = os.path.join(BASE_DIR, "cls_meta_spend_sync_log.txt")
JOB_NAME = "Meta Spend Sync"
DEFAULT_LOOKBACK_DAYS = 3
REQUEST_TIMEOUT = 45
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 5
MAX_PAGES = 200   # hard stop against a runaway paging loop
INSIGHT_FIELDS = ("spend,impressions,clicks,account_currency,"
                  "campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name")
# Meta error codes worth retrying (rate limit / transient).
RETRYABLE_ERROR_CODES = {1, 2, 4, 17, 32, 341, 613}

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(message, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] {message}"
    try:
        if sys.stdout is not None:
            print(entry)
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(entry + "\n")
    except Exception:
        pass


class MetaRefused(Exception):
    """Meta returned an error we should not retry (bad token, no permission...)."""


def _get_json(url, params):
    """GET with timeout + exponential backoff. Returns parsed JSON or raises MetaRefused/RuntimeError."""
    last = "unknown error"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            try:
                body = resp.json()
            except ValueError:
                body = {}
            err = body.get("error") if isinstance(body, dict) else None
            if resp.status_code == 200 and not err:
                return body
            msg = (err or {}).get("message") or f"HTTP {resp.status_code}"
            retryable = resp.status_code >= 500 or resp.status_code == 429 \
                or (err or {}).get("code") in RETRYABLE_ERROR_CODES
            if not retryable:
                raise MetaRefused(msg)
            last = msg
        except MetaRefused:
            raise
        except requests.RequestException as e:
            last = str(e)
        if attempt < MAX_RETRIES:
            wait = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            log(f"Retry {attempt}/{MAX_RETRIES - 1} in {wait}s: {last}", "WARN")
            time.sleep(wait)
    raise RuntimeError(f"gave up after {MAX_RETRIES} attempts: {last}")


def fetch_range(account_id, token, since, until):
    """All per-ad daily rows for [since, until] (YYYY-MM-DD), following paging.next."""
    url = f"https://graph.facebook.com/{cls_capi_core.GRAPH_API_VERSION}/{account_id}/insights"
    params = {
        "level": "ad", "time_increment": 1, "fields": INSIGHT_FIELDS, "limit": 500,
        "time_range": '{"since":"%s","until":"%s"}' % (since, until),
        "access_token": token,
    }
    rows = []
    pages = 0
    while url and pages < MAX_PAGES:
        body = _get_json(url, params)
        for d in body.get("data", []):
            rows.append({
                "spend_date": d.get("date_start"), "account_id": account_id,
                "campaign_id": d.get("campaign_id"), "campaign_name": d.get("campaign_name"),
                "adset_id": d.get("adset_id"), "adset_name": d.get("adset_name"),
                "ad_id": d.get("ad_id"), "ad_name": d.get("ad_name"),
                "spend": d.get("spend"), "impressions": d.get("impressions"),
                "clicks": d.get("clicks"), "currency": d.get("account_currency"),
            })
        url = (body.get("paging") or {}).get("next")   # next URL already carries every param
        params = None
        pages += 1
    if url:
        log(f"Stopped paging at {MAX_PAGES} pages for {account_id} {since}..{until}", "WARN")
    return rows


def month_chunks(start, end):
    """Split [start, end] (date objects) into calendar-month (since, until) string pairs."""
    chunks = []
    cur = start
    while cur <= end:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)   # first of next month
        chunk_end = min(nxt - timedelta(days=1), end)
        chunks.append((cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cur = nxt
    return chunks


def selftest():
    assert cls_db.META_AD_ACCOUNTS, "META_AD_ACCOUNTS empty"
    c = month_chunks(datetime(2026, 6, 1).date(), datetime(2026, 9, 30).date())
    assert c[0] == ("2026-06-01", "2026-06-30") and c[-1] == ("2026-09-01", "2026-09-30") and len(c) == 4, c
    c = month_chunks(datetime(2026, 9, 29).date(), datetime(2026, 9, 30).date())
    assert c == [("2026-09-29", "2026-09-30")], c
    log("SELFTEST OK")
    return True


def main(backfill_from=None, dry_run=False):
    log("=" * 55)
    log(f"META SPEND SYNC — START{' (DRY RUN)' if dry_run else ''}"
        f"{' backfill from ' + backfill_from if backfill_from else ''}")
    log("=" * 55)
    try:
        token = (dotenv_values(os.path.join(BASE_DIR, ".env")).get("META_SYSTEM_USER_TOKEN") or "").strip()
        if not token:
            raise RuntimeError("META_SYSTEM_USER_TOKEN missing in .env")
        today = datetime.now().date()
        if backfill_from:
            start = datetime.strptime(backfill_from, "%Y-%m-%d").date()
            windows = month_chunks(start, today)
        else:
            windows = [((today - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1)).strftime("%Y-%m-%d"),
                        today.strftime("%Y-%m-%d"))]

        if not dry_run:
            cls_db.init_db()   # self-healing; makes sure ad_spend_daily exists
        total_fetched = total_written = 0
        currencies = set()
        for account_id in cls_db.META_AD_ACCOUNTS:
            for since, until in windows:
                rows = fetch_range(account_id, token, since, until)
                currencies.update(r["currency"] for r in rows if r["currency"])
                written = 0 if dry_run else cls_db.upsert_ad_spend_rows(rows)
                total_fetched += len(rows)
                total_written += written
                log(f"{account_id} {since}..{until}: fetched {len(rows)}, "
                    f"{'would write' if dry_run else 'wrote'} {len(rows) if dry_run else written}")
        summary = (f"{'DRY RUN — ' if dry_run else ''}fetched {total_fetched} ad-day rows, "
                   f"{'wrote 0 (dry run)' if dry_run else f'wrote {total_written}'}"
                   f" (currency: {', '.join(sorted(currencies)) or 'n/a'})")
        log(summary)
        if not dry_run:
            cls_db.write_job_result(JOB_NAME, True, summary)
        return True
    except Exception as e:   # never raise to the scheduler
        log(f"FAILED: {e}", "ERROR")
        if not dry_run:
            try:
                cls_db.write_job_result(JOB_NAME, False, str(e))
            except Exception:
                pass
        return False


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        try:
            selftest()
        except Exception as e:
            log(f"SELFTEST FAILED: {e}", "ERROR")
        sys.exit(0)
    bf = None
    if "--backfill" in args:
        i = args.index("--backfill")
        bf = args[i + 1] if i + 1 < len(args) else None
        try:
            datetime.strptime(bf or "", "%Y-%m-%d")
        except ValueError:
            log("--backfill needs a date like 2026-06-01", "ERROR")
            sys.exit(0)
    main(backfill_from=bf, dry_run="--dry-run" in args)
    sys.exit(0)
