"""
cls_pk_bundle.py  -- v1.4
Consolidates the CLS/CRM source tree into ONE markdown file for manual
upload to the Claude.ai Project Knowledge base. Solves three problems:
  1. Manual multi-file upload fatigue -> upload exactly one file.
  2. Filename collisions (manifest.json, build.gradle appearing twice)
     -> disambiguated by full relative-path headers.
  3. Accidental inclusion of secrets/DBs/logs -> explicit allow-list,
     nothing is swept in by default.

USAGE
    python cls_pk_bundle.py                 # writes PK_BUNDLE.md
    python cls_pk_bundle.py --dry-run        # lists what WOULD be included, writes nothing
    python cls_pk_bundle.py --out my.md      # custom output path
    python cls_pk_bundle.py --lock-in        # also permanently adds any newly
                                              # discovered .py files into
                                              # INCLUDE_FILES below (see v1.2 notes)

WHERE TO RUN
    From D:\\CLS itself (i.e. ROOT below should point at D:\\CLS).
    Run via Claude Code or a plain `python` call -- no dependencies beyond
    the standard library.

MAINTENANCE
    This file is config-not-code: to add/remove a file from the bundle,
    edit INCLUDE_FILES / INCLUDE_DIRS below. Do not add logic branches.

    v1.2: new .py files ANYWHERE under D:\\CLS (including android_pilot/
    and every subfolder) are auto-discovered on every run, warned about,
    and still included in that run's PK_BUNDLE.md output in a clearly
    separate "AUTO-DISCOVERED" section. They are NOT permanently added
    to INCLUDE_FILES unless --lock-in is explicitly passed.

    v1.3: each auto-discovered file now also gets HEURISTIC usage
    signals (last-modified age, git last-commit date, whether any .bat
    wrapper references it, whether any other .py file imports it) and
    a resulting label (LIKELY ACTIVE / POSSIBLY STALE / UNKNOWN).
    IMPORTANT: this is deliberately signal-only, never a verdict. It
    NEVER decides inclusion, NEVER deletes or excludes anything, and
    is not a substitute for actually reading the file. Whether a script
    is "important" is a judgment call -- the signals just give you (or
    Claude, when reviewing the bundle with you) something concrete to
    judge with, instead of guessing from a bare filename.

CHANGELOG
    v1.4 - FIX: the "N Python file(s) found on disk but NOT in
           INCLUDE_FILES" warning printed a literal warning-sign
           character (⚠). On a Windows console using the cp1252
           codepage that raised UnicodeEncodeError and crashed the
           whole run before PK_BUNDLE.md was written, leaving a stale
           bundle on disk with no error surfaced except a traceback.
           Fixed with the same UTF-8-safe print-guard pattern already
           used in cls_capi_firer.py/cls_backup.py/etc.: a small
           safe_print() helper that falls back to an ASCII-only
           rendering (errors="replace") if the console can't display
           the original string. Only the crashing print call is
           affected -- no other output changed.
    v1.3 - Srikanth's requirement: auto-discovered files aren't just
           listed -- each one is now checked against a few cheap,
           objective signals (mtime age, git history, .bat references,
           cross-file imports) and given a heuristic
           LIKELY ACTIVE / POSSIBLY STALE / UNKNOWN label, shown in
           both the console output and the PK_BUNDLE.md AUTO-DISCOVERED
           section. All checks are best-effort and fail safe to
           "unknown" rather than erroring. Nothing about --lock-in or
           inclusion behavior changed -- signals are informational only.
    v1.2 - Auto-discover new .py files anywhere under D:\\CLS (recursive,
           includes android_pilot/) that aren't yet in INCLUDE_FILES.
           Warn-only by default -- still included in THIS run's bundle
           (separate, clearly flagged section) but not remembered for
           next time unless --lock-in is passed. --lock-in edits
           INCLUDE_FILES in this script's own source at a fixed marker
           line, backing up the previous version of the script first.
           Never auto-includes hard-excluded files, and never bundles
           itself.
    v1.1 - PK_BUNDLE.md's first line is now an "Updated: <date/time>"
           stamp (plus a best-effort short git commit hash, fully
           fail-safe if git/repo is unavailable).
    v1.0 - initial version, reflects the Bucket 1 (REFRESH) + Bucket 2 (ADD)
           audit from the 2026-08-03 Project Knowledge review.
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\CLS")


def safe_print(text):
    """Console-encoding-safe print. Windows consoles often use a
    system codepage (e.g. cp1252) that can't represent every Unicode
    character (e.g. \u26a0). Falls back to an ASCII-only rendering
    rather than crashing the run. Same pattern as the log() helpers
    in cls_capi_firer.py / cls_backup.py / cls_import_selldo_csv.py."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


# ---------------------------------------------------------------------------
# CONFIG -- edit this section only. No logic changes needed for new files.
# ---------------------------------------------------------------------------

# Explicit individual files, relative to ROOT. One line per file = one
# clear audit trail of what's exposed to Project Knowledge.
#
# New entries can be added here by hand as always, OR by running
# `python cls_pk_bundle.py --lock-in`, which inserts newly discovered
# .py files directly above the AUTO_DISCOVER_INSERT_MARKER line below.
# Do not remove or move that marker line -- --lock-in depends on it.
INCLUDE_FILES = [
    # --- docs ---
    "CLAUDE.md",
    "CLS_to_CRM_Handoff_Brief.md",
    "TELEPHONY_RECORDING_POLICY.md",
    "TELEPHONY_PROJECT_RESUME.md",

    # --- core app ---
    "crm/app.py",
    "crm/cls_reports.py",
    "crm/create_admin.py",
    "crm/schema_check.py",
    "crm/requirements.txt",
    "cls_db.py",

    # --- jobs A-D + support scripts ---
    "meta_leads_fetcher.py",
    "selldo_to_cls.py",
    "cls_capi_firer.py",
    "cls_email_drip.py",
    "cls_telegram_listener.py",
    "cls_watchdog.py",
    "cls_backup.py",
    "cls_parallel_diff.py",
    "cls_parallel_export.py",
    "cls_db_fork.py",
    "cls_import_selldo_csv.py",
    "cls_call_recording_audit.py",
    "cls_snapshot.py",
    "cls_dashboard.py",
    "cls_telecaller_report.py",
    "migrate_db.py",
    "setup_task_scheduler.py",

    # --- config/flags (small, non-secret runtime config) ---
    "cls_flags.json",

    # --- PWA app-shell + Pages Functions ---
    "pwa/index.html",
    "pwa/_routes.json",
    "pwa/functions/_middleware.js",
    "pwa/functions/api/snapshot.js",
    "crm/static/sw.js",
    "crm/static/manifest.json",   # renamed on output: crm_static_manifest.json
    "pwa/manifest.json",           # renamed on output: pwa_manifest.json

    # --- Android (Kotlin/XML/Gradle) ---
    "android_pilot/build.gradle",              # renamed: android_project_build.gradle
    "android_pilot/app/build.gradle",          # renamed: android_app_build.gradle
    "android_pilot/app/src/main/AndroidManifest.xml",
    "android_pilot/app/src/main/java/com/asianproperties/clspilot/MainActivity.kt",
    "android_pilot/app/src/main/java/com/asianproperties/clspilot/SettingsActivity.kt",
    "android_pilot/app/src/main/java/com/asianproperties/clspilot/PunchActivity.kt",
    "android_pilot/app/src/main/java/com/asianproperties/clspilot/AttendanceWorker.kt",
    "android_pilot/app/src/main/java/com/asianproperties/clspilot/Shared.kt",
    "android_pilot/app/src/main/res/layout/activity_main.xml",
    "android_pilot/app/src/main/res/layout/activity_punch.xml",
    "android_pilot/app/src/main/res/layout/activity_settings.xml",
    "android_pilot/app/src/main/res/drawable/circle_button_bg.xml",

    "cls_attendance_photo.py",
    # --- AUTO_DISCOVER_INSERT_MARKER: do not remove or move this line ---
]

# Whole directories to include entirely (every file inside, non-recursive
# into further subfolders unless EXTRA_DIR_RECURSE lists them).
# Used for the 46 HTML templates -- adding a new template later means
# nothing to edit here, it's picked up automatically.
INCLUDE_DIRS = [
    "crm/templates",   # all *.html
]

# Extensions allowed when sweeping INCLUDE_DIRS (safety net against
# accidentally including a stray .db or .log dropped into that folder).
DIR_SWEEP_EXTENSIONS = {".html"}

# Files that would match the above by name/location but must NEVER be
# included, no matter what. Belt-and-suspenders against secrets/DBs/logs.
HARD_EXCLUDE_NAMES = {
    ".env", "cls.db", "CLS1.db", "CLS2.db",
}
HARD_EXCLUDE_SUFFIXES = {".log", ".db", ".msi", ".exe", ".pyc"}
HARD_EXCLUDE_SUBSTRINGS = ["_log", "log_", "snapshot.json", "offset.json"]

# Directory NAMES to skip entirely during the recursive .py auto-
# discovery scan (collect_files()/INCLUDE_DIRS are unaffected by this
# list -- it only governs discover_new_python_files() below). Any
# directory whose name matches one of these, anywhere in the tree, is
# skipped along with everything inside it. Also skips any directory
# starting with "." (covers .git, .venv, .idea, etc. without listing
# every dotfolder by hand).
AUTO_DISCOVER_EXCLUDE_DIR_NAMES = {
    "__pycache__", "venv", "env", "node_modules", "build", "dist",
    ".gradle", "site-packages",
    # binary-asset / operational-output folders -- never contain source
    "call_recordings", "attendance_photos", "apk_releases",
}

# v1.3 -- a file untouched longer than this (by mtime) is labeled
# POSSIBLY STALE if no other reference to it is found either. Purely a
# label threshold, not a deletion trigger. Config-not-code, tune freely.
STALE_DAYS_THRESHOLD = 60

# ---------------------------------------------------------------------------
# Language hints for fenced code blocks, purely cosmetic.
# ---------------------------------------------------------------------------
LANG_BY_SUFFIX = {
    ".py": "python", ".html": "html", ".js": "javascript", ".json": "json",
    ".kt": "kotlin", ".xml": "xml", ".gradle": "groovy", ".md": "markdown",
    ".txt": "text",
}


def is_hard_excluded(path: Path) -> bool:
    name = path.name
    if name in HARD_EXCLUDE_NAMES:
        return True
    if path.suffix in HARD_EXCLUDE_SUFFIXES:
        return True
    low = str(path).lower()
    if any(s in low for s in HARD_EXCLUDE_SUBSTRINGS):
        return True
    return False


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def get_git_short_hash():
    """
    Best-effort short git commit hash for ROOT, for the "Updated:"
    stamp. Returns None on ANY failure -- git not installed, ROOT not a
    git repo, git not on PATH, timeout, etc. Never raises, never blocks
    a bundle run. Purely informational.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def collect_files():
    """Returns list of (relative_path_str, absolute_Path, output_name)
    for everything in INCLUDE_FILES / INCLUDE_DIRS -- the allow-listed
    set, unchanged in behavior from v1.0/v1.1."""
    seen = set()
    result = []

    def add(rel_str, output_name=None):
        abs_path = ROOT / rel_str
        if not abs_path.exists():
            print(f"  [MISSING] {rel_str}  -- skipped (not found on disk)")
            return
        if is_hard_excluded(abs_path):
            print(f"  [BLOCKED] {rel_str}  -- matched hard-exclude rule, skipped")
            return
        key = str(abs_path.resolve())
        if key in seen:
            return
        seen.add(key)
        result.append((rel_str, abs_path, output_name or rel_str.replace("/", "_")))

    for rel in INCLUDE_FILES:
        # honor the // renamed comment convention by just using path-safe name
        add(rel)

    for rel_dir in INCLUDE_DIRS:
        dir_path = ROOT / rel_dir
        if not dir_path.exists():
            print(f"  [MISSING DIR] {rel_dir}  -- skipped (not found)")
            continue
        for f in sorted(dir_path.iterdir()):
            if f.is_file() and f.suffix in DIR_SWEEP_EXTENSIONS:
                add(f"{rel_dir}/{f.name}")

    return result


def _all_python_files_for_scanning():
    """
    (v1.3) All .py files anywhere under ROOT, outside noise dirs -- used
    ONLY as a text corpus to check whether other files import a given
    discovered file. Has nothing to do with INCLUDE_FILES / bundling
    decisions.
    """
    out = []
    for f in ROOT.rglob("*.py"):
        if not f.is_file():
            continue
        try:
            parts = f.relative_to(ROOT).parts[:-1]
        except ValueError:
            continue
        if any(p in AUTO_DISCOVER_EXCLUDE_DIR_NAMES or p.startswith(".") for p in parts):
            continue
        out.append(f)
    return out


def _all_bat_files():
    """(v1.3) Every .bat file under ROOT -- Task Scheduler wrappers live here."""
    return [f for f in ROOT.rglob("*.bat") if f.is_file()]


def gather_usage_signals(rel_path, all_py_files, all_bat_files):
    """
    (v1.3) Best-effort, HEURISTIC-ONLY signals for whether a discovered
    .py file looks currently active or possibly stale/unused. Never
    used to auto-decide inclusion or deletion -- purely informational,
    for a human (or Claude, when reviewing the bundle) to judge with
    actual context. Every check fails safe to "unknown"/False rather
    than raising.
    """
    abs_path = ROOT / rel_path
    stem = abs_path.stem

    try:
        days_old = (datetime.now() - datetime.fromtimestamp(abs_path.stat().st_mtime)).days
    except Exception:
        days_old = None

    git_last_commit = None
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel_path],
            cwd=str(ROOT), capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            git_last_commit = result.stdout.strip()
    except Exception:
        pass

    referenced_in_bat = False
    for bat in all_bat_files:
        if abs_path.name in _read_text_safe(bat):
            referenced_in_bat = True
            break

    referenced_in_py = False
    for other in all_py_files:
        try:
            if other.resolve() == abs_path.resolve():
                continue
        except Exception:
            continue
        content = _read_text_safe(other)
        if f"import {stem}" in content or f"from {stem} import" in content:
            referenced_in_py = True
            break

    return {
        "days_old": days_old,
        "git_last_commit": git_last_commit,
        "referenced_in_bat": referenced_in_bat,
        "referenced_in_py": referenced_in_py,
    }


def _heuristic_verdict(signals):
    """(v1.3) A LABEL, not a decision. Always phrased as heuristic."""
    if signals["referenced_in_bat"] or signals["referenced_in_py"]:
        return "LIKELY ACTIVE (referenced elsewhere)"
    if signals["days_old"] is not None and signals["days_old"] > STALE_DAYS_THRESHOLD:
        return f"POSSIBLY STALE (no reference found, unmodified {signals['days_old']}d)"
    return "UNKNOWN (no reference found, but recently modified -- verify manually)"


def discover_new_python_files():
    """
    Recursively scans the ENTIRE D:\\CLS tree -- including android_pilot/
    and every subfolder -- for *.py files that are NOT already in
    INCLUDE_FILES and are not hard-excluded. Skips noise directories per
    AUTO_DISCOVER_EXCLUDE_DIR_NAMES and any "."-prefixed directory.
    Never flags this script itself, and never flags its own --lock-in
    backup copies (non-.py suffix, see lock_in_discovered()).

    Returns a sorted list of dicts:
        {"rel_path": str, "signals": {...}, "verdict": str}

    Warn-only: this function only discovers, gathers signals, and
    RETURNS. It never writes anything and never excludes a file based
    on its verdict -- see lock_in_discovered() for the only code path
    that modifies INCLUDE_FILES, which is always human-triggered.
    """
    already_included = set()
    for rel in INCLUDE_FILES:
        p = ROOT / rel
        if p.exists():
            already_included.add(str(p.resolve()))

    self_path = Path(__file__).resolve()
    candidate_rel_paths = []

    for f in ROOT.rglob("*.py"):
        if not f.is_file():
            continue
        try:
            rel_parts = f.relative_to(ROOT).parts
        except ValueError:
            continue
        parent_parts = rel_parts[:-1]
        if any(part in AUTO_DISCOVER_EXCLUDE_DIR_NAMES or part.startswith(".") for part in parent_parts):
            continue
        if f.resolve() == self_path:
            continue
        if str(f.resolve()) in already_included:
            continue
        if is_hard_excluded(f):
            continue
        candidate_rel_paths.append(f.relative_to(ROOT).as_posix())

    candidate_rel_paths.sort()
    if not candidate_rel_paths:
        return []

    # Build the reference corpus ONCE, not per-candidate.
    all_py_files = _all_python_files_for_scanning()
    all_bat_files = _all_bat_files()

    discovered = []
    for rel_path in candidate_rel_paths:
        signals = gather_usage_signals(rel_path, all_py_files, all_bat_files)
        discovered.append({
            "rel_path": rel_path,
            "signals": signals,
            "verdict": _heuristic_verdict(signals),
        })

    return discovered


def lock_in_discovered(discovered):
    """
    Permanently adds discovered files' rel_paths into THIS script's own
    INCLUDE_FILES list, so future runs stop flagging them. Only ever
    called when --lock-in is explicitly passed -- never automatic, and
    NEVER filtered by verdict (a POSSIBLY STALE file is still your call,
    not this function's -- if it's in `discovered`, it gets locked in
    exactly like a LIKELY ACTIVE one; review the verdicts BEFORE running
    --lock-in, not after).

    Safety, since this is self-modifying code:
      1. Backs up the current script to
         cls_pk_bundle.py.bak_<YYYYMMDD_HHMMSS> BEFORE any write. The
         backup filename deliberately does NOT end in .py, so it can
         never be picked up by discover_new_python_files() later.
      2. Only ever inserts new lines at ONE fixed point -- immediately
         above the "AUTO_DISCOVER_INSERT_MARKER" comment line. If that
         marker is missing, this function refuses to touch the file.
      3. Never touches anything else in the file.
    """
    script_path = Path(__file__).resolve()
    source = script_path.read_text(encoding="utf-8")
    marker = "    # --- AUTO_DISCOVER_INSERT_MARKER: do not remove or move this line ---"

    if marker not in source:
        print("ERROR: AUTO_DISCOVER_INSERT_MARKER not found in this script's own source.")
        print("Refusing to auto-edit. Add the following lines into INCLUDE_FILES by hand instead:")
        for d in discovered:
            print(f'    "{d["rel_path"]}",')
        return False

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = script_path.with_name(f"{script_path.name}.bak_{ts}")
    backup_path.write_text(source, encoding="utf-8")

    new_lines = "".join(f'    "{d["rel_path"]}",\n' for d in discovered)
    updated_source = source.replace(marker, new_lines + marker, 1)
    script_path.write_text(updated_source, encoding="utf-8")

    print(f"Backed up previous version to: {backup_path.name}")
    print(f"Locked in {len(discovered)} file(s) into INCLUDE_FILES:")
    for d in discovered:
        print(f"  + {d['rel_path']}  [{d['verdict']}]")
    print("Review the diff (git diff cls_pk_bundle.py) and commit it per your normal commit discipline.")
    return True


def _format_signals_line(signals):
    days = f"{signals['days_old']}d ago" if signals["days_old"] is not None else "unknown"
    git_d = signals["git_last_commit"] or "unknown"
    bat = "yes" if signals["referenced_in_bat"] else "no"
    pyref = "yes" if signals["referenced_in_py"] else "no"
    return f"modified: {days} | last git commit: {git_d} | in a .bat wrapper: {bat} | imported elsewhere: {pyref}"


def build_bundle(files, discovered, dry_run: bool):
    total_bytes = 0
    lines = []

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M") + " IST"
    git_hash = get_git_short_hash()
    git_suffix = f" (git {git_hash})" if git_hash else " (git: unavailable)"
    lines.append(f"Updated: {timestamp_str}{git_suffix}\n\n")

    lines.append("# CLS / CRM Project Knowledge Bundle\n")
    lines.append(f"Auto-generated by cls_pk_bundle.py from {ROOT}\n")
    total_count = len(files) + len(discovered)
    if discovered:
        lines.append(f"Files included: {total_count} ({len(files)} allow-listed + {len(discovered)} auto-discovered)\n\n")
    else:
        lines.append(f"Files included: {total_count}\n\n")

    lines.append("## File index (allow-listed)\n")
    for rel_str, abs_path, out_name in files:
        size = abs_path.stat().st_size
        total_bytes += size
        lines.append(f"- `{rel_str}` ({size:,} bytes)\n")

    if discovered:
        lines.append("\n## \u26a0 File index (AUTO-DISCOVERED -- not yet in INCLUDE_FILES)\n")
        lines.append("These .py files were found on disk but are not yet permanently listed. ")
        lines.append("Signals are heuristic ONLY -- read the file before deciding anything. ")
        lines.append("Run `python cls_pk_bundle.py --lock-in` to make selected ones permanent.\n\n")
        for d in discovered:
            size = (ROOT / d["rel_path"]).stat().st_size
            total_bytes += size
            lines.append(f"- `{d['rel_path']}` ({size:,} bytes) -- **{d['verdict']}**\n")
            lines.append(f"  - {_format_signals_line(d['signals'])}\n")

    lines.append(f"\n**Total: {total_count} files, {total_bytes:,} bytes**\n\n---\n")

    if dry_run:
        print("\n--- DRY RUN: no output file written ---")
        print(f"Would include {total_count} files, {total_bytes:,} bytes total.")
        print(f"Would stamp: Updated: {timestamp_str}{git_suffix}\n")
        return None

    for rel_str, abs_path, out_name in files:
        lang = LANG_BY_SUFFIX.get(abs_path.suffix, "")
        content = _read_text_safe(abs_path) or f"[ERROR READING FILE]"
        lines.append(f"\n\n## FILE: {rel_str}\n")
        lines.append(f"```{lang}\n{content}\n```\n")

    for d in discovered:
        rel_str = d["rel_path"]
        abs_path = ROOT / rel_str
        lang = LANG_BY_SUFFIX.get(abs_path.suffix, "")
        content = _read_text_safe(abs_path) or f"[ERROR READING FILE]"
        lines.append(f"\n\n## FILE (\u26a0 AUTO-DISCOVERED -- {d['verdict']}): {rel_str}\n")
        lines.append(f"<!-- {_format_signals_line(d['signals'])} -->\n")
        lines.append(f"```{lang}\n{content}\n```\n")

    return "".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Bundle CLS source into one PK-upload file.")
    parser.add_argument("--dry-run", action="store_true", help="List files only, write nothing.")
    parser.add_argument("--out", default=str(ROOT / "PK_BUNDLE.md"), help="Output file path.")
    parser.add_argument(
        "--lock-in", action="store_true",
        help="Permanently add ALL of this run's auto-discovered .py files into INCLUDE_FILES "
             "(backs up this script first), regardless of their heuristic verdict. Review the "
             "verdicts printed below BEFORE using this flag."
    )
    args = parser.parse_args()

    if not ROOT.exists():
        print(f"ERROR: ROOT path {ROOT} does not exist on this machine. "
              f"Edit ROOT at the top of this script if D:\\CLS is not correct.")
        sys.exit(1)

    print(f"Scanning {ROOT} ...\n")
    files = collect_files()
    discovered = discover_new_python_files()

    if discovered:
        safe_print(f"\n\u26a0 {len(discovered)} Python file(s) found on disk but NOT in INCLUDE_FILES:\n")
        for d in discovered:
            print(f'  "{d["rel_path"]}"')
            print(f"      verdict : {d['verdict']}")
            print(f"      signals : {_format_signals_line(d['signals'])}\n")
        print("Heuristic labels only -- always read a file before deciding to lock it in or drop it.")
        if args.lock_in:
            print()
            lock_in_discovered(discovered)
        else:
            print("These ARE included in THIS run's PK_BUNDLE.md (see the AUTO-DISCOVERED section),")
            print("but will be flagged again on every future run until you either:")
            print("  (a) add specific paths into INCLUDE_FILES yourself, or")
            print("  (b) re-run with --lock-in to add ALL of them at once.\n")
    else:
        print("No new (un-listed) .py files found.\n")

    output = build_bundle(files, discovered, dry_run=args.dry_run)
    if output is None:
        return

    out_path = Path(args.out)
    out_path.write_text(output, encoding="utf-8")
    print(f"\nWrote {out_path}  ({len(files) + len(discovered)} files, {out_path.stat().st_size:,} bytes)")
    print("Next step: delete all files in Project Knowledge, then upload this ONE file.")


if __name__ == "__main__":
    main()
