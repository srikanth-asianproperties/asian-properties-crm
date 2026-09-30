"""
setup_task_scheduler.py  —  Register CLS Job D in Windows Task Scheduler
=========================================================================
Creates 5 daily triggers: 10:00, 12:00, 14:00, 16:00, 18:00
Matches the exact schedule of Jobs A, B, C.

v4 (2026-09-30) — NEW `--meta-spend` mode: registers the Finance F1 "CLS Meta
Spend Sync" task (hourly 07:00-19:00 daily via Repetition Interval PT1H +
explicit Duration PT12H, Job C's pattern; runs run_cls_meta_spend_sync.bat).
`python setup_task_scheduler.py --meta-spend` (run as Admin, ONCE — standing
OS-level change, so NOT run automatically). Other modes untouched.

v3 (2026-09-29) — NEW `--daily-brief` mode: registers the AI-2 "CLS Daily AI
Brief" task (07:00 daily, runs run_cls_ai_daily_brief.bat from D:/CLS, single
run-and-exit, StartWhenAvailable so a missed 07:00 fires on next wake).
`python setup_task_scheduler.py --daily-brief` (run as Admin, ONCE — it is a
standing OS-level change, so it is NOT run automatically). With no flag the
script still registers Job D exactly as before (untouched, still on the old
C:/CLS paths — Job D is paused).

WHAT CHANGED FROM v1
--------------------
- Schedule changed from "daily at 10:30" to 5 triggers per day:
  10:00, 12:00, 14:00, 16:00, 18:00 — matching Jobs A, B, C exactly.
- Working directory (C:\CLS) now set via XML task definition.
  The old schtasks /create command has no /workingdir flag — this was
  causing "import cls_db" to fail when run by Task Scheduler because
  Python's cwd defaulted to C:\Windows\System32.
- Task registered via XML (schtasks /create /xml) instead of inline
  flags, which is the only reliable method for multi-trigger tasks
  with a working directory in Windows Task Scheduler.

Run ONCE from C:\CLS as Administrator:
  python setup_task_scheduler.py
=========================================================================
"""

import subprocess
import sys
import os
import tempfile
from datetime import date

TASK_NAME   = "CLS_Job_D_EmailDrip"
SCRIPT_PATH = r"C:\CLS\cls_email_drip.py"
START_DIR   = r"C:\CLS"
RUN_TIMES   = ["10:00", "12:00", "14:00", "16:00", "18:00"]


def find_python():
    return sys.executable


def build_task_xml(python_exe):
    """
    Build a Task Scheduler XML definition.

    WHY XML INSTEAD OF schtasks /create FLAGS:
    - schtasks /create supports only ONE trigger per command.
      To get 5 run times you would need 5 separate commands and
      they would overwrite each other — only the last would survive.
    - schtasks /create has no flag for WorkingDirectory (StartIn).
      Without this, Task Scheduler launches the script with cwd =
      C:\Windows\System32, which breaks 'import cls_db' unless
      C:\CLS is explicitly on sys.path.
    - XML registration (schtasks /create /xml) solves both problems
      cleanly in one step.
    """
    today = date.today().strftime("%Y-%m-%d")

    # Build one <CalendarTrigger> block per run time
    triggers = ""
    for t in RUN_TIMES:
        triggers += f"""
        <CalendarTrigger>
          <StartBoundary>{today}T{t}:00</StartBoundary>
          <Enabled>true</Enabled>
          <ScheduleByDay>
            <DaysInterval>1</DaysInterval>
          </ScheduleByDay>
        </CalendarTrigger>"""

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>CLS Job D — Automated Email Drip for Asian Properties</Description>
  </RegistrationInfo>
  <Triggers>{triggers}
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>{SCRIPT_PATH}</Arguments>
      <WorkingDirectory>{START_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""
    return xml


def main():
    python_exe = find_python()

    print("=" * 60)
    print(" CLS Job D — Task Scheduler Setup")
    print("=" * 60)
    print(f"  Task name  : {TASK_NAME}")
    print(f"  Script     : {SCRIPT_PATH}")
    print(f"  Python     : {python_exe}")
    print(f"  Schedule   : Daily at {', '.join(RUN_TIMES)}")
    print(f"  Working dir: {START_DIR}")
    print()

    # ── Step 1: Delete existing task (clean slate) ──────────────
    print("Step 1: Removing old task if it exists...")
    subprocess.run(
        f'schtasks /delete /tn "{TASK_NAME}" /f',
        capture_output=True, shell=True)
    print("  OK (safe to ignore if task did not previously exist)")
    print()

    # ── Step 2: Write XML to temp file ──────────────────────────
    print("Step 2: Writing task XML definition...")
    xml_content = build_task_xml(python_exe)
    xml_path = os.path.join(tempfile.gettempdir(), "cls_job_d_task.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(xml_content)
    print(f"  Written to: {xml_path}")
    print()

    # ── Step 3: Register task from XML ──────────────────────────
    print("Step 3: Registering task from XML...")
    result = subprocess.run(
        f'schtasks /create /tn "{TASK_NAME}" /xml "{xml_path}" /f',
        capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print("  FAILED.")
        print(f"  stdout : {result.stdout.strip()}")
        print(f"  stderr : {result.stderr.strip()}")
        print()
        print("  FIX: Run this script as Administrator.")
        print("  Right-click Command Prompt -> Run as administrator")
        print("  Then: python setup_task_scheduler.py")
        return
    print("  OK — task registered successfully.")
    print()

    # ── Step 4: Verify registration ─────────────────────────────
    print("Step 4: Verifying task registration...")
    result = subprocess.run(
        f'schtasks /query /tn "{TASK_NAME}" /fo LIST /v',
        capture_output=True, text=True, shell=True)
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if any(k in line for k in
                   ["TaskName", "Status", "Next Run", "Task To Run",
                    "Start In", "Scheduled Task State"]):
                print(f"  {line}")
    print()

    # ── Step 5: Show existing CLS jobs for comparison ───────────
    print("Step 5: Existing CLS job schedule (for reference)...")
    for job in ["CLS_Job_A", "CLS_Job_B", "CLS_Job_C"]:
        result = subprocess.run(
            f'schtasks /query /tn "{job}" /fo LIST',
            capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "Next Run" in line or "Schedule" in line:
                    print(f"  {job}: {line.strip()}")
        else:
            print(f"  {job}: not found in Task Scheduler")
    print()

    print("=" * 60)
    print(f" DONE. Job D will now run at {', '.join(RUN_TIMES)} every day.")
    print()
    print(" To trigger a manual run RIGHT NOW:")
    print(f'   schtasks /run /tn "{TASK_NAME}"')
    print()
    print(" To confirm it ran (check the log):")
    print("   type C:\\CLS\\cls_drip_log.txt")
    print("=" * 60)


# ─────────────────────────────────────────────────────────────
# v3 — Daily AI Brief (AI-2): single daily run-and-exit task
# ─────────────────────────────────────────────────────────────
BRIEF_TASK_NAME = "CLS Daily AI Brief"
BRIEF_WRAPPER   = r"D:\CLS\run_cls_ai_daily_brief.bat"   # sets CLS_DB_PATH=CLS1.db, then pythonw
BRIEF_START_DIR = r"D:\CLS"
BRIEF_RUN_TIME  = "07:00"


def build_daily_brief_xml():
    """One daily trigger; Program = the .bat wrapper (NOT python.exe directly —
    bypassing the wrapper silently falls back to the default DB, see CLAUDE.md
    'Documented gotcha'). Short-lived script, so PT1H limit — not Job C's
    keep-alive pattern."""
    today = date.today().strftime("%Y-%m-%d")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>CLS Daily AI Brief — 7 AM admin summary of the previous day</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{today}T{BRIEF_RUN_TIME}:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{BRIEF_WRAPPER}</Command>
      <WorkingDirectory>{BRIEF_START_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""


def register_daily_brief():
    print("=" * 60)
    print(" CLS Daily AI Brief — Task Scheduler Setup")
    print("=" * 60)
    print(f"  Task name : {BRIEF_TASK_NAME}")
    print(f"  Runs      : {BRIEF_WRAPPER}  daily at {BRIEF_RUN_TIME}")
    xml_path = os.path.join(tempfile.gettempdir(), "cls_daily_ai_brief_task.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(build_daily_brief_xml())
    result = subprocess.run(
        f'schtasks /create /tn "{BRIEF_TASK_NAME}" /xml "{xml_path}" /f',
        capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print("  FAILED:", result.stdout.strip(), result.stderr.strip())
        print("  FIX: run this from an elevated (Administrator) prompt.")
        return
    print("  OK — task registered.")
    q = subprocess.run(f'schtasks /query /tn "{BRIEF_TASK_NAME}" /fo LIST /v',
                       capture_output=True, text=True, shell=True)
    for line in q.stdout.splitlines():
        if any(k in line for k in ("TaskName", "Next Run", "Task To Run", "Start In", "Scheduled Task State")):
            print("  " + line.strip())
    print(f'  Manual test: schtasks /run /tn "{BRIEF_TASK_NAME}"  (log: D:/CLS/cls_ai_daily_brief_log.txt)')


# ─────────────────────────────────────────────────────────────
# v4 — Meta Spend Sync (Finance F1): hourly, Job C-style repetition
# ─────────────────────────────────────────────────────────────
SPEND_TASK_NAME = "CLS Meta Spend Sync"
SPEND_WRAPPER   = r"D:\CLS\run_cls_meta_spend_sync.bat"   # sets CLS_DB_PATH=CLS1.db, then pythonw
SPEND_START_DIR = r"D:\CLS"
SPEND_START_TIME = "07:00"     # first run each day; repeats hourly for PT12H (07:00-19:00)


def build_meta_spend_xml():
    """Daily trigger at 07:00 with an hourly Repetition and an EXPLICIT Duration
    (Job C's pattern: Interval + Duration PT12H — a Repetition without a Duration
    can silently stop repeating). Program = the .bat wrapper, never python.exe."""
    today = date.today().strftime("%Y-%m-%d")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>CLS Meta Spend Sync — hourly pull of Meta ad spend into ad_spend_daily (Finance F1)</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{today}T{SPEND_START_TIME}:00</StartBoundary>
      <Enabled>true</Enabled>
      <Repetition>
        <Interval>PT1H</Interval>
        <Duration>PT12H</Duration>
      </Repetition>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{SPEND_WRAPPER}</Command>
      <WorkingDirectory>{SPEND_START_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""


def register_meta_spend():
    print("=" * 60)
    print(" CLS Meta Spend Sync — Task Scheduler Setup")
    print("=" * 60)
    print(f"  Task name : {SPEND_TASK_NAME}")
    print(f"  Runs      : {SPEND_WRAPPER}  hourly from {SPEND_START_TIME} for 12h, daily")
    xml_path = os.path.join(tempfile.gettempdir(), "cls_meta_spend_sync_task.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(build_meta_spend_xml())
    result = subprocess.run(
        f'schtasks /create /tn "{SPEND_TASK_NAME}" /xml "{xml_path}" /f',
        capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print("  FAILED:", result.stdout.strip(), result.stderr.strip())
        print("  FIX: run this from an elevated (Administrator) prompt.")
        return
    print("  OK — task registered.")
    q = subprocess.run(f'schtasks /query /tn "{SPEND_TASK_NAME}" /fo LIST /v',
                       capture_output=True, text=True, shell=True)
    for line in q.stdout.splitlines():
        if any(k in line for k in ("TaskName", "Next Run", "Task To Run", "Start In", "Scheduled Task State")):
            print("  " + line.strip())
    print(f'  Manual test: schtasks /run /tn "{SPEND_TASK_NAME}"  (log: D:/CLS/cls_meta_spend_sync_log.txt)')


if __name__ == "__main__":
    if "--meta-spend" in sys.argv:
        register_meta_spend()
    elif "--daily-brief" in sys.argv:
        register_daily_brief()
    else:
        main()
