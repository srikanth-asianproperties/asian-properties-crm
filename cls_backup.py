"""
=============================================================
cls_backup.py  —  CLS Daily Backup to Google Drive
=============================================================
Version : 1.6
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.6  (2026-08-19) — Exclude .git/ and __pycache__/ from backup per
  Srikanth's explicit decision (2026-08-19), following the same-day
  investigation session into Step 2's dated-archive timeout.
  Investigation found gdrive:CLS_Backup/latest held 1,798 objects
  total, of which .git/ (621 objects, 34.5%) and __pycache__/ (17
  objects) together were ~90% of the object count when combined with
  android_pilot/ — and Step 2's server-side copy is billed roughly
  per-object by Google Drive's API, not per-byte, so a folder full of
  many small objects (like .git/'s internal object store) drives the
  same kind of throttling/timeout behavior documented in v1.3, even
  though .git/ is only 9.9 MiB. .git/ is fully redundant with GitHub
  (confirmed even with origin/master, 0 ahead/0 behind, at the time of
  this decision) — the real commit history lives there; this Drive
  backup only ever needed the working files. __pycache__/ is
  auto-regenerated compiled bytecode with zero unique content and is
  already gitignored by convention — a minor contributor (17 files)
  but no reason to carry it along either.
  Added RCLONE_EXCLUDE_GIT and RCLONE_EXCLUDE_PYCACHE (same rclone
  filter syntax as the existing excludes) alongside the existing
  --exclude flags on all three rclone calls that already excluded
  call_recordings/attendance_photos (Step 1 sync, and both fallback
  local-copy paths). Not added to Step 2 (server-side copy) — same
  reasoning as v1.5: that step copies from "latest", and "latest" no
  longer contains .git/ or __pycache__ once Step 1 stops adding them,
  so nothing further is needed there.
  EXPLICITLY NOT EXCLUDED: android_pilot/ (1,001 objects, the single
  largest contributor found by the investigation) — this was a
  confirmed decision, not an oversight. Unlike .git/, android_pilot/
  has no backup elsewhere (it isn't tracked in the GitHub repo), so it
  stays in the Drive backup as-is. Do not add it to the excludes in a
  future session without re-confirming with Srikanth first.

v1.5  (2026-08-18) — Exclude attendance_photos/ from backup per Srikanth's
  explicit decision (2026-08-18), reversing the earlier v0.30/v0.31 design
  call to include it after DPDP review. He does not want these photos
  stored on Google Drive. Added RCLONE_EXCLUDE_ATTENDANCE (same rclone
  filter syntax as RCLONE_EXCLUDE_CALL_RECORDINGS) and added it alongside
  the existing --exclude call_recordings flag on all three rclone calls
  that already excluded call_recordings (Step 1 sync, and both fallback
  local-copy paths). Not added to Step 2 (server-side copy) — that step
  copies from "latest" to a dated folder, and "latest" no longer contains
  attendance_photos once Step 1 stops adding it, so nothing further is
  needed there. Nothing else changed.

v1.4  (2026-08) — BASE_DIR updated from C:\CLS to D:\CLS — drive migration, 2026-08.

v1.3  (2026-08-03) — Fixed timeout failure from 2026-08-02.
  ROOT CAUSE: Step 1 (daily dated copy) did a full local->Drive
  upload of the entire C:\\CLS\\ folder (269 MB) into a brand-new
  empty dated folder every single day. On 2026-08-02, Google Drive's
  API throttled the upload (visible in the log as transfer speed
  decaying from ~4 MiB/s down to single-digit bytes/sec and back,
  repeatedly — classic rclone exponential backoff against a Drive
  rate limit). Step 2 (sync to "latest") only had 39.8 MB of actual
  changes to push and still took ~4 minutes fighting the same
  throttle; Step 1 had to push the full 269 MB fresh and ran out of
  the 1800s timeout window. cls.db and everything else DID reach
  Drive successfully via Step 2 — only the dated archive copy for
  that day was missing.

  FIX — Reordered + changed Step 1's transport:
    1. Step 1 is now "sync to latest" (runs FIRST). This is exactly
       what old Step 2 did — pushes only the delta since last run.
    2. Step 2 is now "server-side copy" of gdrive:CLS_Backup/latest
       -> gdrive:CLS_Backup/daily/YYYY-MM-DD. Because both sides of
       this copy are already on Google Drive, rclone performs it
       server-side — no bytes move through this PC's upload link at
       all, so it's fast and immune to local/upload-side throttling.
    3. Safety net: if the server-side copy fails for any reason, the
       script automatically falls back to the old behavior (a full
       local->Drive copy straight into the dated folder) so the
       daily archive still gets created, just slower that one day.
  Nothing else changed — retention, pruning, exclude filters,
  Telegram reporting, and selftest are all unchanged.

v1.2  (2026-07-31) — Exclude call_recordings/ (Phase B Telephony) from
  both backup steps via a new --exclude "call_recordings/**" flag on
  each rclone call. Nothing else changed — every other file/folder
  under C:\\CLS\\ is still backed up exactly as before. See
  RCLONE_EXCLUDE_CALL_RECORDINGS below for why.

v1.1  (June 2026) — Three fixes after first live run:
  FIX 1 — RCLONE_TIMEOUT increased from 300s to 1800s (30 min).
    C:\\CLS\\ is 262 MB, not the estimated 15 MB. At typical Indian
    broadband upload speeds (1-4 MB/s), the first daily copy takes
    4-10 minutes. The 300s timeout caused Step 1 (daily copy) to
    abort every run. Step 2 (latest sync) has no per-step timeout
    and completed successfully — meaning Google Drive DID receive
    a full backup, but the script incorrectly reported failure.
    Root cause: folder size was underestimated at design time.
    30 minutes gives 6x headroom for any realistic connection speed.

  FIX 2 — Removed invalid --format flag from prune_old_backups().
    rclone lsd does not accept a --format flag. This caused the prune
    step to fail with "unknown flag: --format" on every run. The flag
    was unnecessary — plain lsd output already contains the folder name
    as the last token on each line, which is what the parser reads.

  FIX 3 — SyntaxWarning on Windows paths in docstring.
    Two docstring lines contained bare C:\\CLS\\ sequences which Python
    interpreted as invalid escape sequences (\\C, \\C). Escaped to C:\\\\CLS\\\\
    in docstrings. No functional impact — warnings suppressed cleanly.

WHAT THIS DOES
--------------
Backs up the entire C:\\CLS\\ folder to Google Drive once daily.
Keeps 7 dated copies (one per day, last 7 days).
Sends a Telegram message confirming success or failure.

No imports beyond Python stdlib + requests (already installed).
No dependency on cls_db.py — this script runs standalone so it
works even if the database itself is the thing being recovered.

WHAT GETS BACKED UP
--------------------
Everything in C:\\CLS\\ :
  - cls.db                  (the lead database — most critical)
  - *.py scripts            (all automation logic)
  - .env                    (all API keys and credentials)
  - cls_flags.json          (completion flags)
  - *_log.txt               (audit trail of all fired events)
  - cls_watchdog_snapshot.json
  - rclone.exe              (the backup tool itself)

Google Drive destination:
  gdrive:CLS_Backup/latest/             (always the most recent copy)
  gdrive:CLS_Backup/daily/YYYY-MM-DD/   (7 copies retained, server-side
                                          copy of "latest" — see v1.3)

REAL ESTATE ANALOGY
--------------------
Think of this like keeping certified copies of your sale deeds
in both your office drawer AND a bank locker. The daily backup
is the bank locker — if the office burns down, the originals
(deeds / cls.db) are safe and you can restart from where you
left off. "latest/" is the locker you check first; "daily/" is
the 7-day archive in case today's copy is itself corrupted. As of
v1.3, the bank makes the dated archive copy internally from what's
already in the locker, instead of you re-driving the originals
over from the office every single day.

SCHEDULE (Task Scheduler)
--------------------------
Run once daily at 09:30 — before the main CLS cycle starts at 10:00.
This ensures the backup captures yesterday's end-of-day state cleanly,
before any new data arrives in the 10:00 cycle.

  Program : C:\\Python312\\python.exe   (adjust to your Python path)
  Args    : C:\\CLS\\cls_backup.py
  Start in: C:\\CLS\\

ONE-TIME SETUP
--------------
  1. Install rclone:
       - Download rclone.exe from https://rclone.org/downloads/
         (Windows AMD64, single .exe file)
       - Place rclone.exe in C:\\CLS\\

  2. Connect rclone to Google Drive (run once in Command Prompt):
       C:\\CLS\\rclone.exe config
       Follow the prompts — choose "n" (new remote), name it "gdrive",
       storage type "drive", leave client_id/secret blank, scope 1,
       auto config "y" (opens browser to log in with your Google account).

  3. Test the connection:
       C:\\CLS\\rclone.exe lsd gdrive:
       You should see your Google Drive folders listed.

  4. No new pip installs needed — uses requests (already installed)
     and subprocess (stdlib).

  5. Run a manual test before scheduling:
       python C:\\CLS\\cls_backup.py --selftest   (checks rclone + Telegram)
       python C:\\CLS\\cls_backup.py              (does a real backup now)

CREDENTIALS
-----------
Reads from C:\\CLS\\.env (same file as all other CLS scripts):
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
  (No new credentials needed — reuses existing Telegram bot)

FAILURE PHILOSOPHY
------------------
This script must never crash silently. Every failure is:
  1. Written to cls_backup_log.txt
  2. Sent as a Telegram alert
If Telegram itself fails, the error is still in the log file.
The script always exits with a clear success/failure message.
=============================================================
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime, timedelta

import requests

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR    = r"D:\CLS"
LOG_FILE    = os.path.join(BASE_DIR, "cls_backup_log.txt")
RCLONE_EXE  = os.path.join(BASE_DIR, "rclone.exe")
ENV_FILE    = os.path.join(BASE_DIR, ".env")

# Google Drive remote name (must match what you chose in rclone config)
GDRIVE_REMOTE = "gdrive"

# Destination folder structure on Google Drive
GDRIVE_BASE   = f"{GDRIVE_REMOTE}:CLS_Backup"
GDRIVE_LATEST = f"{GDRIVE_BASE}/latest"          # always the most recent copy
GDRIVE_DAILY  = f"{GDRIVE_BASE}/daily"           # dated archives

# How many daily copies to keep before deleting the oldest
RETAIN_DAYS = 7

# Timeout for the local->Drive sync (seconds). This is the one step that
# actually uploads bytes from this PC, so it needs the generous window.
# C:\CLS\ is ~262 MB. At 1 MB/s upload (conservative Indian broadband),
# a full transfer takes ~4-5 min; a delta-only sync is normally much
# faster. 30 minutes gives ample headroom even if Drive throttles.
RCLONE_TIMEOUT = 1800

# v1.3 — Timeout for the Drive-to-Drive server-side copy (Step 2). No
# data leaves this PC for this step, so it should be quick — but it's
# still one API call per file, so give it real headroom rather than
# assuming instant.
SERVERSIDE_COPY_TIMEOUT = 600

# v1.2 — call_recordings/ (Phase B Telephony, app.py v0.21) is
# deliberately excluded from this backup. Call-recording audio is more
# sensitive than the rest of C:\CLS and the DPDP consent-notice
# mechanics for this feature are still a separate open item (see
# TELEPHONY_RECORDING_POLICY.md) — don't widen where this data lives
# (i.e. syncing it to Google Drive) before that's resolved. rclone
# filter syntax: a trailing /** excludes the folder's full contents.
RCLONE_EXCLUDE_CALL_RECORDINGS = "call_recordings/**"

# v1.5 — attendance_photos/ is now excluded from backup per Srikanth's
# explicit decision (2026-08-18), reversing the earlier v0.30/v0.31
# design call to include it after DPDP review. He does not want these
# photos stored on Google Drive. Same rclone filter syntax as
# RCLONE_EXCLUDE_CALL_RECORDINGS.
RCLONE_EXCLUDE_ATTENDANCE = "attendance_photos/**"

# v1.6 — .git/ excluded from backup per Srikanth's decision
# (2026-08-19). Fully redundant with GitHub (confirmed even,
# 0 ahead/0 behind, at the time of this decision) — the actual
# per-commit history lives there, this Drive backup only ever needed
# the working files. Was the leading contributor (621 objects, 34.5%
# of latest/'s total object count) to Step 2's dated-archive timeout.
RCLONE_EXCLUDE_GIT = ".git/**"

# v1.6 — __pycache__/ excluded from backup per Srikanth's decision
# (2026-08-19). Auto-regenerated compiled bytecode, zero unique
# content, already gitignored by convention. Minor contributor (17
# files) but no reason to carry it along.
RCLONE_EXCLUDE_PYCACHE = "__pycache__/**"


# ─────────────────────────────────────────────────────────────
# LOGGING  —  Unicode-safe, append-only
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    safe_entry = entry.encode("utf-8", errors="replace").decode("utf-8")
    try:
        print(safe_entry)
    except UnicodeEncodeError:
        print(safe_entry.encode("ascii", errors="replace").decode("ascii"))
    try:
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# .env LOADER  —  same pattern as cls_capi_firer.py
# ─────────────────────────────────────────────────────────────

def load_env():
    env = {}
    if not os.path.exists(ENV_FILE):
        return env
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


# ─────────────────────────────────────────────────────────────
# TELEGRAM  —  same pattern as cls_watchdog.py
# ─────────────────────────────────────────────────────────────

def send_telegram(message, env):
    token   = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log("Telegram credentials missing in .env — skipping notification.", "WARNING")
        return False
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=data, timeout=15)
        if r.status_code == 200:
            log("Telegram notification sent.")
            return True
        else:
            log(f"Telegram returned HTTP {r.status_code}: {r.text}", "WARNING")
            return False
    except Exception as e:
        sanitized = str(e).replace(token, "***REDACTED***")
        log(f"Telegram send failed: {sanitized}", "WARNING")
        return False


# ─────────────────────────────────────────────────────────────
# RCLONE RUNNER
# ─────────────────────────────────────────────────────────────

def run_rclone(args, description, timeout=None):
    """
    Run rclone with the given argument list.
    Returns (success: bool, output: str).
    v1.3: accepts an optional per-call timeout override (falls back to
    RCLONE_TIMEOUT) so the fast server-side copy doesn't have to share
    the same 30-minute window as the full local upload.
    """
    cmd = [RCLONE_EXE] + args
    effective_timeout = timeout if timeout is not None else RCLONE_TIMEOUT
    log(f"Running: {description}")
    log(f"Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            encoding="utf-8",
            errors="replace"
        )
        if result.stdout.strip():
            log(f"rclone stdout: {result.stdout.strip()}")
        if result.stderr.strip():
            log(f"rclone stderr: {result.stderr.strip()}")
        if result.returncode == 0:
            log(f"{description} — SUCCESS")
            return True, result.stdout + result.stderr
        else:
            log(f"{description} — FAILED (exit code {result.returncode})", "ERROR")
            return False, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        log(f"{description} — TIMED OUT after {effective_timeout}s", "ERROR")
        return False, "TIMEOUT"
    except FileNotFoundError:
        log(f"rclone.exe not found at {RCLONE_EXE}", "ERROR")
        return False, "rclone.exe not found"
    except Exception as e:
        log(f"{description} — Exception: {e}", "ERROR")
        return False, str(e)


# ─────────────────────────────────────────────────────────────
# FOLDER SIZE HELPER
# ─────────────────────────────────────────────────────────────

def get_folder_size_mb(folder):
    """Return total size of folder in MB (for logging)."""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except Exception:
                    pass
    except Exception:
        pass
    return round(total / (1024 * 1024), 2)


# ─────────────────────────────────────────────────────────────
# OLD DAILY BACKUP PRUNER
# ─────────────────────────────────────────────────────────────

def prune_old_backups():
    """
    Delete daily backup folders older than RETAIN_DAYS from Google Drive.
    Lists gdrive:CLS_Backup/daily/, identifies folders by date name,
    deletes any older than 7 days.
    """
    log(f"Pruning daily backups older than {RETAIN_DAYS} days...")

    # List directories in gdrive:CLS_Backup/daily/
    ok, output = run_rclone(
        ["lsd", GDRIVE_DAILY],
        "List daily backup folders"
    )
    if not ok:
        log("Could not list daily backup folders — skipping prune.", "WARNING")
        return

    cutoff = datetime.now() - timedelta(days=RETAIN_DAYS)
    pruned = 0

    for line in output.splitlines():
        # rclone lsd output: "          -1 2026-06-16 09:30:00        -1 2026-06-16"
        # The folder name is the last token on the line
        parts = line.strip().split()
        if not parts:
            continue
        folder_name = parts[-1]   # e.g. "2026-06-16"
        try:
            folder_date = datetime.strptime(folder_name, "%Y-%m-%d")
        except ValueError:
            continue   # not a date-named folder, skip

        if folder_date < cutoff:
            old_path = f"{GDRIVE_DAILY}/{folder_name}"
            ok2, _ = run_rclone(
                ["purge", old_path],
                f"Delete old backup {folder_name}"
            )
            if ok2:
                pruned += 1

    log(f"Prune complete — {pruned} old backup(s) removed.")


# ─────────────────────────────────────────────────────────────
# MAIN BACKUP
# ─────────────────────────────────────────────────────────────

def run_backup():
    """
    Full backup sequence (reordered in v1.3):
      1. Sync C:\\CLS\\ -> gdrive:CLS_Backup/latest/  (the only step
         that uploads bytes from this PC — delta-only, so it's the
         fastest and least throttling-exposed way to get a full
         current snapshot onto Drive)
      2. Server-side copy gdrive:CLS_Backup/latest/ ->
         gdrive:CLS_Backup/daily/YYYY-MM-DD/  (Drive-to-Drive, no
         local upload at all). Falls back to a full local copy into
         the dated folder if the server-side copy fails for any reason.
      3. Prune backups older than 7 days
      4. Send Telegram report
    """
    env       = load_env()
    today_str = datetime.now().strftime("%Y-%m-%d")
    start_ts  = datetime.now()

    log("=" * 55)
    log(f"CLS BACKUP STARTED — {today_str}")
    log("=" * 55)

    # ── Pre-flight checks ──
    if not os.path.exists(RCLONE_EXE):
        msg = (
            f"🚨 <b>CLS Backup FAILED</b>\n"
            f"Date: {today_str}\n"
            f"Reason: rclone.exe not found at {RCLONE_EXE}\n"
            f"Action: Download from https://rclone.org/downloads/ "
            f"and place in C:\\CLS\\"
        )
        log("rclone.exe not found — aborting.", "ERROR")
        send_telegram(msg, env)
        return False

    if not os.path.exists(BASE_DIR):
        msg = (
            f"🚨 <b>CLS Backup FAILED</b>\n"
            f"Date: {today_str}\n"
            f"Reason: C:\\CLS\\ folder not found."
        )
        log("C:\\CLS\\ not found — aborting.", "ERROR")
        send_telegram(msg, env)
        return False

    folder_size = get_folder_size_mb(BASE_DIR)
    log(f"C:\\CLS\\ folder size: {folder_size} MB")

    # ── Step 1: Sync to "latest" (the only step that uploads from this PC) ──
    log(f"Step 1: Syncing to {GDRIVE_LATEST} (latest) ...")

    ok1, output1 = run_rclone(
        [
            "sync",          # sync (not copy) so deleted files don't accumulate
            BASE_DIR,
            GDRIVE_LATEST,
            "--progress",
            "--stats-one-line",
            "--exclude", RCLONE_EXCLUDE_CALL_RECORDINGS,
            "--exclude", RCLONE_EXCLUDE_ATTENDANCE,
            "--exclude", RCLONE_EXCLUDE_GIT,
            "--exclude", RCLONE_EXCLUDE_PYCACHE,
        ],
        f"Latest backup → {GDRIVE_LATEST}"
    )

    # ── Step 2: Dated daily archive — server-side copy from "latest" ──
    daily_dest = f"{GDRIVE_DAILY}/{today_str}"

    if ok1:
        log(f"Step 2: Server-side copy {GDRIVE_LATEST} -> {daily_dest} ...")
        ok2, output2 = run_rclone(
            [
                "copy",
                GDRIVE_LATEST,
                daily_dest,
                "--progress",
                "--stats-one-line",
            ],
            f"Daily archive (server-side copy) → {daily_dest}",
            timeout=SERVERSIDE_COPY_TIMEOUT
        )

        # v1.3 fallback: if the Drive-to-Drive copy itself fails, don't
        # give up on the dated archive — fall back to the old full
        # local upload straight into the dated folder. Slower, but the
        # existing safety net is preserved rather than silently dropped.
        if not ok2:
            log("Server-side copy failed — falling back to full local copy for daily archive.", "WARNING")
            ok2, output2 = run_rclone(
                [
                    "copy",
                    BASE_DIR,
                    daily_dest,
                    "--progress",
                    "--stats-one-line",
                    "--exclude", RCLONE_EXCLUDE_CALL_RECORDINGS,
                    "--exclude", RCLONE_EXCLUDE_ATTENDANCE,
                    "--exclude", RCLONE_EXCLUDE_GIT,
                    "--exclude", RCLONE_EXCLUDE_PYCACHE,
                ],
                f"Daily backup fallback (local copy) → {daily_dest}"
            )
    else:
        # If Step 1 itself failed, "latest" may be stale/incomplete —
        # don't server-side copy a possibly-broken snapshot. Fall back
        # straight to a full local copy so the dated archive still has
        # a shot at succeeding independently.
        log("Step 1 (sync to latest) failed — skipping server-side copy, "
            "attempting daily archive via direct local copy instead.", "WARNING")
        ok2, output2 = run_rclone(
            [
                "copy",
                BASE_DIR,
                daily_dest,
                "--progress",
                "--stats-one-line",
                "--exclude", RCLONE_EXCLUDE_CALL_RECORDINGS,
                "--exclude", RCLONE_EXCLUDE_ATTENDANCE,
                "--exclude", RCLONE_EXCLUDE_GIT,
                "--exclude", RCLONE_EXCLUDE_PYCACHE,
            ],
            f"Daily backup fallback (local copy) → {daily_dest}"
        )

    # ── Step 3: Prune old daily backups ──
    prune_old_backups()

    # ── Step 4: Report ──
    duration  = round((datetime.now() - start_ts).total_seconds(), 1)
    success   = ok1 and ok2

    if success:
        msg = (
            f"✅ <b>CLS Backup Complete</b>\n"
            f"📅 Date: {today_str}\n"
            f"📁 Size: {folder_size} MB\n"
            f"⏱ Duration: {duration}s\n\n"
            f"<b>Destinations:</b>\n"
            f"• <code>CLS_Backup/latest/</code> ✅\n"
            f"• <code>CLS_Backup/daily/{today_str}/</code> ✅\n\n"
            f"🗂 Keeping last {RETAIN_DAYS} daily copies.\n"
            f"Restore command:\n"
            f"<code>rclone copy gdrive:CLS_Backup/latest C:\\CLS\\</code>"
        )
        log("BACKUP SUCCESSFUL.")
    else:
        failed_steps = []
        if not ok1:
            failed_steps.append(f"Latest sync → {GDRIVE_LATEST}")
        if not ok2:
            failed_steps.append(f"Daily archive → {daily_dest}")

        msg = (
            f"🚨 <b>CLS Backup FAILED</b>\n"
            f"📅 Date: {today_str}\n"
            f"📁 Size: {folder_size} MB\n"
            f"⏱ Duration: {duration}s\n\n"
            f"<b>Failed steps:</b>\n"
            + "\n".join(f"• {s}" for s in failed_steps)
            + f"\n\n⚠️ Check <code>C:\\CLS\\cls_backup_log.txt</code> for details."
        )
        log("BACKUP FAILED — check log.", "ERROR")

    send_telegram(msg, env)
    log("=" * 55)
    return success


# ─────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────

def selftest():
    """
    Checks rclone connectivity and Telegram, without doing a real backup.
    Run this before scheduling: python cls_backup.py --selftest
    """
    print("=" * 55)
    print(" CLS BACKUP — SELF TEST")
    print("=" * 55)

    env = load_env()

    # Check 1: rclone.exe present
    if os.path.exists(RCLONE_EXE):
        print(f"  [OK]  rclone.exe found at {RCLONE_EXE}")
    else:
        print(f"  [FAIL] rclone.exe NOT found at {RCLONE_EXE}")
        print(f"         Download from https://rclone.org/downloads/")
        print(f"         (Windows AMD64 .zip → extract rclone.exe → place in C:\\CLS\\)")
        return

    # Check 2: rclone can reach Google Drive
    print(f"  Testing Google Drive connection (gdrive: remote)...")
    ok, output = run_rclone(["lsd", f"{GDRIVE_REMOTE}:"], "Google Drive connectivity check")
    if ok:
        print(f"  [OK]  Google Drive connected. rclone can see your Drive.")
    else:
        print(f"  [FAIL] Cannot reach Google Drive.")
        print(f"         Run: C:\\CLS\\rclone.exe config")
        print(f"         And follow the setup steps in this script's docstring.")
        return

    # Check 3: C:\CLS\ folder exists and has files
    if os.path.exists(BASE_DIR):
        size = get_folder_size_mb(BASE_DIR)
        file_count = sum(len(files) for _, _, files in os.walk(BASE_DIR))
        print(f"  [OK]  C:\\CLS\\ found — {file_count} files, {size} MB")
    else:
        print(f"  [FAIL] C:\\CLS\\ folder not found.")
        return

    # Check 4: Telegram
    token   = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        print(f"  Testing Telegram...")
        ok_tg = send_telegram(
            "✅ <b>CLS Backup self-test</b>\nTelegram connection confirmed. "
            "Backup script is ready.",
            env
        )
        if ok_tg:
            print(f"  [OK]  Telegram message sent — check your phone.")
        else:
            print(f"  [WARN] Telegram send failed — check token/chat_id in .env")
    else:
        print(f"  [WARN] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not in .env — "
              f"notifications will be skipped.")

    print("")
    print("  All checks passed. Ready to run:")
    print("    python C:\\CLS\\cls_backup.py")
    print("")
    print("  Or schedule it in Task Scheduler at 09:30 daily.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        success = run_backup()
        sys.exit(0 if success else 1)
