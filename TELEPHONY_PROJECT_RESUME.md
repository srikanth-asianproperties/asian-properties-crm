# Asian Properties CRM — Telephony Feature: Project Resume
*Generated end-of-session, for continuing in a new claude.ai chat + new Claude Code session*

## STATUS UPDATE 2026-08-09: ARCHITECTURE CLOSED

All 9 originally-open Telephony architecture decisions are now locked.
Native call recording (Architecture B — READ_CALL_LOG + server-side
matching) is confirmed production-proven across the full team, 10+
days, zero gaps. No further architecture decisions pending on Telephony.
See CLS_to_CRM_Handoff_Brief.md Sections 9-10 (updated same date) for
the full locked record. This resume doc's remaining content below is
now historical/background only, kept for context on how Phase A/B
were built.

## How to use this document
1. Upload this file to this Project's Knowledge (Project settings → add file).
2. In your next new chat in this Project, just say: "Read TELEPHONY_PROJECT_RESUME.md and let's continue" — Claude will pull full context from it plus the existing userMemories.
3. In Claude Code (separate context, 91% full), start a **fresh session** and paste the "Claude Code fresh-session primer" block near the bottom of this doc as your first message — it re-grounds Claude Code on file versions and standing rules without needing your old, nearly-full context window.

---

## 1. What this feature is
A native Android hybrid pilot app (`android_pilot` repo) + CRM backend additions (main `C:\CLS\` repo) that let salespeople sync real call recordings from their phones into the CRM, matched automatically to the correct lead — replacing a manual/Sell.do-based process, with strict privacy guarantees (only real leads' calls are ever touched).

## 2. Journey so far (chronological)

**Phase A — feasibility pilot (android_pilot repo, created fresh)**
- Built a throwaway Android app via GitHub Actions cloud build (no local Android Studio needed) to test one question: does Android's scoped storage allow reading the OEM call-recording folder?
- Answer: **yes, confirmed on real device.** Call-log access also confirmed working.
- Several build/CI bugs fixed along the way (missing `gradle.properties`, ANR from main-thread scanning, SQL `LIMIT` syntax bug) — all resolved.

**Phase B — backend (main CLS repo)**
- Architecture locked: "dumb app, smart server" — Android app only reports call-log metadata + uploads matched files; all lead-matching happens server-side in `cls_db.py`, reusing existing `norm_phone()`/`find_match()`, never duplicated.
- New schema (additive only): 3 new `activity_log` columns (`recording_file_path`, `duration_seconds`, `matched_phone`), 3 new tables (`user_recording_paths`, `user_api_tokens`, `call_log_staging`).
- New admin Settings → Telephony page: per-user recording-folder path config, per-user hashed bearer token generation.
- Two new token-authenticated API endpoints: `/api/telephony/report-calls`, `/api/telephony/upload-recording`.
- New authenticated recording-playback route + inline `<audio>` player on the lead timeline.
- `TELEPHONY_RECORDING_POLICY.md` created — locked company policy: only recordings for calls matching existing leads/clients are ever fetched; no personal-call scanning, ever.
- `cls_backup.py` updated to exclude `call_recordings/` from the daily Google Drive rclone sync (pending DPDP consent design — **do not raise this topic with Srikanth, he's handling it himself**).

**Real-world testing — bugs found and fixed**
1. **Folder-path prefix bug**: app compared the full `/storage/emulated/0/...` path against MediaStore's prefix-free `RELATIVE_PATH` — always 0 matches. Fixed by normalizing the configured path before comparing.
2. **Wrong-recording incident (serious)**: a missed/unanswered call (duration=0) got matched to an unrelated real recording (a personal call to Srikanth's father) purely by timestamp proximity, and it landed on a real lead's timeline. **Root cause understood precisely**: duration=0 calls can never have a legitimate recording, but the matcher didn't know that.
   - **Fix**: hard rule — never attempt file-matching for duration=0 calls. Also added: ambiguous-candidate detection (skip if two candidate files are both within tolerance), and a **duration-mismatch hard gate** (call duration vs. file duration must be within ~35% or the match is skipped) — this second gate is a Srikanth-confirmed decision, threshold not yet validated against real data.
3. **Duplicate uploads on every re-sync**: fixed server-side — before logging a new `call_recording` row, check if one already exists for that exact `(cls_id, call_timestamp)`; if the file is missing (see incident below) but the row exists, **update** the row with the recovered file rather than inserting a duplicate.

**Data-loss incident (fully disclosed, recovered)**
- During testing, Claude Code accidentally ran a blanket directory-delete (`rm -rf`) on `C:\CLS\call_recordings\`, assuming it only contained its own test debris — it actually also contained real synced recordings from Srikanth's live device testing.
- **Database rows were never touched** — only the underlying `.mp3` files were deleted. All legitimate recordings still exist on Srikanth's phone (the app only ever uploads a copy) and are recoverable via re-sync.
- The one file that mattered most — the wrongly-matched personal recording — was also deleted, which is actually a fortunate side effect.
- **Standing rule now in force**: no test/cleanup script may ever run a directory-wide delete against any path shared with production (`RECORDINGS_DIR`, `call_recordings/`, etc.). Any test needing to exercise file-save logic must monkey-patch the directory to a throwaway temp path first. This has been followed correctly in all sessions since.
- **Not yet done**: Srikanth deliberately deprioritized recovering the 4 legitimate lost recordings (would require clearing the Android app's storage to reset its "last synced" watermark, then re-syncing). Open item, low priority, his call whenever.
- The 6 orphaned duration=0 `activity_log` rows caused by this incident were reviewed via `cls_call_recording_audit.py` (dry-run) and deleted with Srikanth's explicit confirmation.

**Admin visibility — Synced Recordings page**
- New admin-only page (`/settings/telephony/recordings`): filterable/paginated table of every synced recording — Lead ID/Name, Call Status (Answered/Missed), Duration, Activity Owner (who synced it — `activity_log.actor`, already captured, no schema change needed), Lead Owner, Date/Time, inline audio playback, and per-row "View Lead" / "Delete" actions.
- Delete requires **double confirmation** (Srikanth's explicit request, given the recent incident) and removes both the DB row and the file together.
- Built entirely by reusing existing patterns (date-range presets, `get_leads_page()`'s pagination shape, `.report-table` styling) — no new UI conventions invented.

**GUI/UX overhaul (most recent work)**
- Removed "APX" branding everywhere user-facing (only `login.html`'s `<h2>` was actually rendered text; all other 18 occurrences were internal comments/changelogs, correctly left alone). Now reads "Asian Properties CRM" throughout.
- Added a "Show password" toggle on the login page.
- **Settings page access restructured**: `/settings` route opened to all logged-in users, but all existing admin sections (users, projects, campaign routing, lead scoring, telephony config, user activity log, etc.) are now wrapped to show **admin-only**. A new "Device Sync (this phone)" section is visible to **everyone**, containing a button that calls a native JavaScript bridge (`AndroidBridge.openDeviceSyncSettings()`) to open the native token/call-log-check screen — with a graceful fallback message if opened in a plain browser instead of the app.
  - Caught along the way: the Settings link in the nav drawer (`base.html`) was *also* separately admin-gated and needed unlocking, or non-admins would have no way to navigate there even though the route itself was open.
  - Verified with real test logins (salesperson vs admin), not just visual inspection — including catching and fixing a false-alarm in Claude Code's own test tooling (a stray character corrupting a regex) before trusting the final "access control confirmed correct" result.
- **Android app UI redesign**: the app now opens directly into the CRM (WebView), full-screen, no intermediate native button screen. A small sync icon sits inside the purple header band (top-right); the old "Open CRM" button and top-left settings icon are both removed from the main screen. The native token/call-log screen still exists but is now reached only via the JS bridge from inside the CRM's Settings page (see above), or will be once that particular version of the CRM is deployed and tested together with this APK version.
- **App icon**: real Asian Properties logo now wired in as the launcher icon (legacy + adaptive-icon variants, all densities).
- **APK distribution**: attempted a "public download link via GitHub Releases," hit a private-repo login wall, redesigned as CRM-server-hosted download endpoints (`/api/apk/upload` + `/download/clspilot.apk`, dual-secret protected) — **but this was explicitly paused by Srikanth** ("let's stop this apk accessing public or private thing for now, I'll download it manually like before"). The two routes are built, committed, and inert (no secrets configured, nothing calls them yet). Not a priority to resume unless Srikanth raises it again.

## 3. Current file/version state (as of this doc)

**Main CLS repo** (`C:\CLS\`, no remote configured, local git only):
- `cls_db.py` — v2.36
- `crm/app.py` — v0.26
- `crm/templates/base.html` — v0.16
- `crm/templates/login.html` — v1 (rewritten this session)
- `crm/templates/settings.html` — v0.20
- `crm/templates/settings_telephony.html` — v1 (new)
- `crm/templates/settings_telephony_recordings.html` — v2 (double-confirm delete)
- `crm/templates/lead_detail.html` — v10
- `cls_backup.py` — v1.2
- `cls_call_recording_audit.py` — v1.0 (new, CLI dry-run-by-default review/delete tool)
- `TELEPHONY_RECORDING_POLICY.md` — new
- Last commit: `43b0760`

**android_pilot repo** (`github.com/srikanth-asianproperties/cls-android-pilot`, has a remote, pushes trigger CI):
- `MainActivity.kt` — v9 (WebView-first, sync icon repositioned into header band, JS bridge added, settings icon removed from main screen)
- `SettingsActivity.kt` — new (native token entry + Check Call-Log Access, reached via JS bridge from CRM Settings page)
- `Shared.kt` — new (shared prefs helper, call-type-to-string)
- `build.gradle` — versionCode 9 / "0.9-pilot"
- App icon fully wired (real Asian Properties logo, legacy + adaptive variants)
- Last pushed commit: `291014f`
- **CRM-side counterpart to the JS bridge (the "Device Sync" Settings section) is built and committed in the main CLS repo at `43b0760` — needs the CRM restarted to go live, then both halves should be tested together.**

## 4. Standing rules established this project (keep applying in new sessions)
- Version-verify every file live before editing; never regenerate from memory.
- Complete runnable files only, never diffs.
- Self-healing/additive-only schema migrations.
- `CLS_DB_PATH` via OS env var / `.bat` wrapper, never `.env`.
- Config-not-code; guard all `print()`/stdout for `pythonw.exe`.
- **Never run a directory-wide delete against any path shared with production** (established after the recording-files incident) — tests must redirect to a throwaway temp path.
- Diagnostics-before-fixes discipline for any "should work but doesn't" bug, especially anywhere near the recording-matching pipeline, given the privacy stakes.
- Do not raise or remind Srikanth about DPDP consent-notice mechanics — he is handling this himself.
- Double-confirmation required for any delete action in the Synced Recordings admin page (already built).
- Split workflow: architecture/planning happens in claude.ai chat; file changes happen in Claude Code, which reads live files from disk directly.

## 5. Open items awaiting Srikanth (not urgent, in no particular order)
1. **Duration-mismatch threshold (35%)** — shipped as a guess, never calibrated against real diagnostic data (the v0.6 diagnostic output was only ever seen on-screen on Srikanth's phone, never captured). Watch real sync results; if legitimate recordings start getting wrongly skipped, or wrong ones still slip through, revisit this number.
2. **Watermark-reset for the 4 lost legitimate recordings** — deliberately deprioritized by Srikanth, low stakes, his call whenever.
3. **APK distribution mechanism** — paused by Srikanth's explicit request. The CRM-hosted upload/download endpoints exist but are inert. Resume only if he raises it again.
4. **Token revocation** — Settings → Telephony currently only supports *generating* a per-user token, not revoking one. Worth adding before wider team rollout (lost phone / departing employee scenario) — not yet built, not yet requested by Srikanth either.
5. **Wider team rollout mechanics** — so far only tested on Srikanth's own phone/account. Elohar, Devender, Priya haven't been onboarded (their own tokens, their own recording-folder paths, APK installed on their phones) — a real next step whenever Srikanth is ready to expand beyond himself.
6. **Login page subtitle** — the old redundant "Asian Properties CRM" subtitle line was removed (since the heading says the same thing now); confirm this is fine or supply different subtitle copy if wanted.

## 6. Immediate next step once a new session starts
Test the two most recent halves **together**, since they were built in separate sessions and haven't been verified end-to-end as a pair yet:
1. Restart the CRM server (picks up `43b0760`'s Settings/branding/login changes).
2. On the phone (already has APK v9 / `291014f` installed — no reinstall needed): open the app, confirm it loads straight into the CRM, sync icon sits in the header band correctly, no leftover settings icon on the main screen.
3. Log in as a **salesperson test account** → open Settings from the drawer → confirm only "Device Sync (this phone)" appears → tap "Open Device Sync Settings" → confirm the native token/Check-Call-Log-Access screen opens correctly via the JS bridge.
4. Log in as **admin** → confirm all existing admin sections still appear, plus Device Sync at the bottom.
5. If all of that works, this UX overhaul is fully closed out and verified — worth a commit checkpoint if anything needed a fix along the way.

---

## Claude Code fresh-session primer (paste as your first message in a new Claude Code session)

```
Resuming work on the Asian Properties CRM Telephony feature (Phase A/B complete,
now in GUI-overhaul + real-world testing phase). Read
C:\CLS\TELEPHONY_PROJECT_RESUME.md (or wherever this file lives if moved) for
full context before doing anything. Key things to know immediately:

- Main CLS repo is at commit 43b0760, android_pilot repo is at 291014f (has a
  GitHub remote, main CLS repo does not).
- NEVER run a directory-wide delete against any path shared with production
  (especially C:\CLS\call_recordings\) — a past session accidentally deleted
  real files this way. Any test needing file-save logic must redirect to a
  throwaway temp path first.
- Always verify live file versions before editing — do not regenerate from
  memory, even if this resume doc states a version number, re-check the
  actual file header first, since more work may have happened after this
  doc was written.
- Do not raise DPDP consent-notice topics with Srikanth — he's handling that
  himself.
- Immediate first task once you've read the resume doc: help verify the
  Settings-page JS-bridge + Android app changes work correctly together
  end-to-end (see "Immediate next step" section of the resume doc).
```
