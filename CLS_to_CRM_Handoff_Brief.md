# CLS → CRM Handoff Brief
### Seed document for the new dedicated CRM project (Asian Properties)
**Prepared for:** Srikanth, Asian Properties (Hyderabad, India)
**Date:** 30 June 2026
**Purpose:** This single document gives the new "Asian Properties CRM" Claude project everything it needs to know about the existing CLS system, so it starts fully informed rather than blind. Drop this into the new project's knowledge base together with the CLS scripts listed in Section 12.
 
> **How to read this:** Sections 1–6 = the existing system (the spine). Sections 7–11 = the CRM decisions already made. Sections 12–14 = environment, working style, and the immediate next action.
 
---
 
## 1. Business context
 
- **Company:** Asian Properties — a residential real estate brokerage in Hyderabad, India. Domain: `asianbuild.in`.
- **Projects (4 active):**
  - **Naishka Homes** — 3 BHK flats, Bandlaguda Jagir.
  - **Grace Classic** — 2 & 3 BHK flats, Kokapet/Narsingi.
  - **Prima Paradiso** — duplex/triplex villas, Mallampet (partner-shared Meta Page from a separate Business Manager).
  - **Praga Enclave.**
- **Team:** ~4 sales executives. Example: **Elohar** handles Naishka / Bandlaguda Jagir leads.
- **Current CRM:** Sell.do — costs **₹85,000/year** (renews Nov→Nov), slow sync, app lag, occasional recordings not syncing. The CRM project exists to **replace Sell.do with an in-house system**, retired gradually in parallel.
---
 
## 2. What CLS is (the spine the CRM extends)
 
CLS (Centralised Leads System) is a deterministic Python automation pipeline running on a **Windows office desktop at `C:\CLS\`** via Task Scheduler. It ingests Meta Lead Ads, syncs Sell.do CRM stages, fires Meta Conversions API (CAPI) events, runs email drips, and reports health.
 
**Single source of truth:** a SQLite database `C:\CLS\cls.db` (WAL mode), managed through `cls_db.py`. Every other script imports `cls_db`.
 
### Core pipeline jobs
 
| Job | Script | Role | Gating |
|---|---|---|---|
| **A** | `meta_leads_fetcher.py` | Pulls Meta leads (with `leadgen_id`) into `cls.db`; sets flag `meta_fetch` | — |
| **B** | `selldo_to_cls.py` | Playwright login to Sell.do → CSV export → Gmail IMAP fetch → writes each lead's `current_stage`; sets `selldo_sync` | gated on Job A flag |
| **C** | `cls_capi_firer.py` | Finds leads whose stage changed, fires CAPI events to Meta; records events; refreshes dashboard | gated on Job B flag |
| **D** | `cls_email_drip.py` | Email drip engine (Brevo) across CRM stages | reads `cls.db` |
| — | `cls_dashboard.py` | Generates `dashboard.html` from `cls.db` | read-only |
 
**Support scripts:** `cls_watchdog.py` (per-cycle Telegram health report + EOD summary), `cls_telegram_listener.py` (bot: `/help /stats /today /health /pending`), `cls_backup.py` (daily rclone → Google Drive), `cls_snapshot.py` (pushes JSON to Cloudflare Workers KV → powers the PWA Command Center), `cls_telecaller_report.py` (weekend Brevo email of Opportunity-stage leads).
 
**Schedule (current):** Jobs A/B/C every 2 hours, 7 days/week, 10:00–18:00 IST (cycles at 10, 12, 14, 16, 18). *Note: memory of a denser 9-cycle/1-hour cadence also exists; treat the live Task Scheduler as authoritative.*
 
---
 
## 3. The "you already built ~60% of a CRM" map
 
This is the central insight. The CRM is **finishing a system whose data spine already runs**, not founding one.
 
| CRM capability | Already built in CLS? | Where |
|---|---|---|
| Lead capture | ✅ | Job A (Meta), landing-page `/api/contact` |
| Dedup / matching | ✅ | `cls_db.py` matcher (phone/email normalization) |
| Pipeline stage tracking | ✅ | `cls.db` `current_stage` + `events_log` |
| Lead owner / assignment data | ✅ (data) / ❌ (UI) | `lead_owner` column exists; no UI to set it |
| Automation (email) | ✅ | Job D / Brevo |
| Ad-platform feedback | ✅ | Job C / CAPI |
| Reporting | ✅ | `cls_dashboard.py`, PWA Command Center |
| **Multi-user UI for salespeople** | ❌ | **to build** |
| **Salesperson stage editing** | ❌ | **to build** |
| **Notes / activity log** | ❌ | **to build** |
| **Telephony + call recording** | ❌ | **to build (v1.0)** |
| **Follow-up reminders** | ❌ | **to build** |
 
**Strategic payoff of building:** when stages live in the in-house CRM, **Job B (the Playwright scraper — the pipeline's most fragile link) is retired**, and Job C can fire CAPI **in near-real-time** instead of on a batch cycle → fresher conversion signals → better Meta optimisation. That ad-performance gain is the deepest reason to build, beyond the licence saving.
 
---
 
## 4. Key design principles (carry these into the CRM)
 
These are non-negotiable; they are CLS's moat and must survive into the CRM.
 
- **Risk 1 — completion-flag gating:** jobs chain by completion signal (`cls_flags.json`), not fixed clock timing.
- **Risk 3 — never discard:** `cls.db` is a COMPLETE lead registry (walk-ins, 99acres, referrals all stored), not a rolling snapshot.
- **Risk 4 — per-row fire state:** a lead fires only when `current_stage != last_fired_stage`; recorded only after Meta confirms. No double-fires.
- **Deterministic `event_id` = md5(identifier + stage):** re-runs and parallel runs are safe — Meta deduplicates.
- **Idempotent & self-healing:** a missed run is recovered by the next; running twice does no harm.
- **Config-not-code:** form IDs, drip schedules, project buckets, target stages live in editable dicts/tables, not scattered logic.
- **Self-healing migrations:** every schema change uses `ALTER TABLE ... IF NOT EXISTS` / try-except blocks so the live DB upgrades on first run — never manual SQL.
- **Determinism over probabilistic; auditable over clever.** AI/LLM belongs only at the **edges** (lead scoring, analytics, WhatsApp agent), **never in the firing core.**
---
 
## 5. `cls.db` essentials the CRM will read & write
 
- **Tables:** `leads`, `events_log`, `comms_log` (+ Job D drip columns). The CRM will add `users`, `activity_log`, `assignments` (Section 8).
- **Key lead columns:** `current_stage`, `last_fired_stage`, `lead_owner`, `selldo_url`, `selldo_lead_id`, `leadgen_id`, plus 4 drip columns and timestamps.
- **`TARGET_STAGES`** (tracked stages, defined in `cls_db.py`): `["Incoming", "Prospect", "Opportunity", "Site Visited"]`.
- **CAPI firing stages (3 transitions only):**
  - Prospect → `QualifiedLead` (₹200)
  - Opportunity → `Schedule` (₹1000)
  - Site Visited → `CompleteRegistration` (₹3000)
- ⚠️ **`TARGET_STAGES` is defined in BOTH `cls_capi_firer.py` and `cls_db.py`** — adding a stage to only one causes silent failures. Update both.
- **`PROJECT_BUCKETS`:** collapses 39 Sell.do project-name variants into 4 clean buckets for display/attribution; raw `events_log.project` is left untouched (real history).
- **Drip control dicts in `cls_db.py`:** `DRIP_SCHEDULE`, `DRIP_PAUSE_STAGES` (`["Re Assigned"]`), `DRIP_TERMINAL_STAGES` (`["Booked","Lost","Unqualified"]`).
---
 
## 6. Known constraints & hard-won learnings
 
- **Windows Task Scheduler quirks:** `pythonw.exe` sets `sys.stdout = None` → all log/print needs guards. Working directory must be explicitly `C:\CLS\` (use XML task registration, not `schtasks` flags) or `import cls_db` fails. System codepage cp1252 can't encode Telugu/Arabic → all `log()` functions encode UTF-8 with `errors="replace"`.
- **Job B is the most fragile component** — Playwright vs Sell.do login UI + Gmail polling. Self-healing mitigates but doesn't eliminate. **Retiring Job B is a primary CRM goal.**
- **Cloudflare Pages zip upload does NOT compile Pages Functions** — always deploy via Wrangler CLI.
- **Cloudflare Access intercepts `fetch()` differently from browser navigation** — `/api` paths need a separate Bypass Access Application.
- **SQLite WAL handles 4–5 concurrent users comfortably.** Don't pre-optimise to Postgres; the schema ports cleanly later if concurrency ever bites.
- **Version drift between interdependent files causes silent per-lead failures** — version assertions at startup are the guard.
---
 
## 7. The CRM decisions already made (locked)
 
| Decision | Choice | Rationale |
|---|---|---|
| Build vs fork | **Extend CLS** (not fork Frappe/EspoCRM) | Reuses the 60% already owned; keeps determinism/control; Job B dies cleanly |
| Project structure | **New dedicated, seeded project** (this doc + scripts) | Clean focused memory; coupling to `cls.db` handled via seeding |
| Migration style | **Parallel-run, fade old slowly** | Srikanth's standing doctrine; the non-negotiable safeguard |
| App appearance | **PWA (app-shell UI)** | Native feel, no app store, no Android call-app policy issues, instant updates |
| Database | **Keep `cls.db` (SQLite + WAL)** | Already the source of truth |
| Backend | **Flask or FastAPI (Python)** | Same language; imports `cls_db.py` directly |
| Remote access | **Cloudflare Tunnel** | Secure, zero open ports; Cloudflare already in use |
| Telephony | **Deferred until Sell.do expires** | No telephony cost during early versions |
| Call recording | **Script-first (read native OEM recordings via Drive/rclone bridge)**; cloud telephony (Exotel/MyOperator) as documented fallback | See Section 10 |
 
---
 
## 8. The versioned roadmap (the "pyramid")
 
Working name: **APX** (Asian Properties eXchange) — rename freely.
 
| Version | Scope | Effort (part-time) | Sell.do status | Risk |
|---|---|---|---|---|
| **v0.1 — Viewer** | Read-only lead list/detail from `cls.db`, login, Cloudflare Tunnel | 1–2 wks | ✅ runs everything | Very low |
| **v0.5 — Writer** | Stage change, notes (`activity_log`), assignment (`assignments`), follow-up reminders. **Parallel run — team updates BOTH** | 2–3 wks | ✅ verify nothing lost | Low |
| **v1.0 — Telephony + cutover-ready** | Call-recording capture (Section 10); click-to-call; Job B becomes optional | 1–2 wks | ⚠️ begin weaning | Medium |
| **v1.0 Cutover** | Retire Job B; Job C reads stages directly; **cancel Sell.do** | 1 wk | ❌ off | Medium |
| **v1.5+ — Strategic** | Lead scoring (AI at edge), portal email parser, site-visit scheduler, WhatsApp/Job E, NL analytics over `cls.db` | ongoing | — | Low, incremental |
 
**New schema for v0.5:** `users` (id, name, email, role, password_hash), `activity_log` (lead_id, user_id, type, note, ts), `assignments` (lead_id, user_id, assigned_ts). All added via self-healing migrations.
 
**Realistic total to cutover: 2–4 months of part-time evenings.**
 
**The one sacred rule:** in v0.5, run in parallel **≥ 3–4 weeks** before cancelling Sell.do. Do not demolish the rented flat until the team has lived in the new one.
 
---
 
## 9. App appearance — Native Android app (LOCKED, supersedes original PWA plan)

**Decision (locked, 2026-08-09):** The team's only interface is a
native Android APK, distributed by direct download (no Play Store).
The PWA plan from the original brief is retired — left dormant in the
codebase, not deleted, per standing "paused not deleted" doctrine.

**Actual architecture:** The native app's main screen is a WebView
loading crm.asianbuild.in full-screen on launch. Every CRM page (leads
list, dashboard, stage changes, reports, settings) is the same
Jinja2/HTML the Flask backend already serves — unchanged by this
decision. The WebView's own cookie jar means session-cookie login
works inside it exactly as it does in a browser — no auth change was
needed for these pages.

Two small native-only additions sit on top of the WebView: a gear icon
(Settings) and a sync icon (manual recording sync), plus background
Attendance punch/location-ping logic — these are the only parts of the
app that are true native Kotlin, not WebView content.

**Auth model (locked):** Token-based auth (already built:
user_api_tokens, generate_api_token()/verify_api_token()) stays scoped
ONLY to the native bridge API calls that a WebView cannot make itself
— Telephony's report-calls/upload-recording and Attendance's
punch-in/out/location-ping. All CRM page access remains session-cookie
based. This is deliberate, not partial — extending tokens further was
evaluated and found unnecessary, since the WebView already handles the
rest correctly.
---
 
## 10. Call recording — LOCKED architecture (supersedes original rclone/Drive plan)

**Decision (locked, 2026-08-09):** Native call-recording capture via
Android's READ_CALL_LOG permission and direct recording-folder access,
NOT the originally-planned rclone + Google Drive bridge. The rclone/Drive
bridge described in the original Section 10 was never built — Phase A
(feasibility) proved direct native folder access works reliably on real
devices, making the bridge unnecessary.

**Actual architecture ("dumb app, smart server"):** The native app
reports call-log metadata to /api/telephony/report-calls (token-auth'd).
The server (cls_db.py) matches phone numbers against existing leads
using the existing norm_phone()/find_match() logic — no duplicated
matching logic. Only calls matching an existing lead get their recording
file uploaded via /api/telephony/upload-recording. See
TELEPHONY_RECORDING_POLICY.md for the locked privacy scope rule this
enforces.

**Status: proven in production.** Recordings have worked reliably across
the full team's devices for 10+ consecutive days with no gaps —
considered fully trusted, no further per-OEM reliability work needed
unless something regresses.

**Fallback (Exotel/MyOperator cloud telephony): DROPPED.** No reason to
adopt — native capture works reliably as-is.

**rclone + Google Drive infra:** Still in use, but ONLY for the
unrelated general daily backup of C:\CLS\ (cls_backup.py) — database,
scripts, .env, logs. It explicitly EXCLUDES call_recordings/ (see
cls_backup.py v1.2) and has no role in the telephony pipeline. Do not
confuse this with the old planned recording-specific bridge, which
doesn't exist.

**Compliance footnote (DPDP Act):** unchanged — Srikanth is handling
consent-notice mechanics himself; do not raise this topic in future
sessions.
---
 
## 11. Telephony timing
 
No telephony spend until Sell.do's paid term ends. The early versions (v0.1, v0.5) require zero telephony — Sell.do's dialer keeps running during parallel-run. Telephony/recording is a v1.0 concern.

**Architecture status (2026-08-09):** All 9 originally-open Telephony architecture decisions (native app scope, auth model, distribution, per-device reliability, fallback trigger, rclone/Drive fate, DPDP surface, ASR integration point, Job B/cutover dependency) are CLOSED as of 2026-08-09, with call-recording capture specifically confirmed production-proven and counting toward v1.0 cutover readiness. See Sections 9–10 for the locked record.
 
---
 
## 12. Files to add to the new project knowledge base
 
Add these CLS scripts alongside this brief so the CRM project can read the exact spine it extends:
- `cls_db.py` (the foundation — schema, matcher, helpers, config dicts)
- `cls_capi_firer.py` (Job C — what consumes stage changes)
- `selldo_to_cls.py` (Job B — the script being retired; understand what it produces)
- `cls_dashboard.py` (reporting reference)
- `cls_email_drip.py` (Job D — automation reference)
- *(optional)* `meta_leads_fetcher.py`, `cls_watchdog.py`, `cls_snapshot.py`, `cls_telecaller_report.py`
---
 
## 13. Environment & tools
 
- **Runtime:** Python on Windows; Windows Task Scheduler; SQLite (WAL) via `C:\CLS\cls.db`.
- **Credentials:** `C:\CLS\.env` (Meta tokens, Brevo API key, Telegram bot token, Cloudflare KV creds). Never hard-code.
- **APIs:** Meta Graph API v23.0 (CAPI + Lead Ads; next upgrade ~v25.0), Sell.do (Playwright + Gmail IMAP + CSV), Brevo (`sib-api-v3-sdk` v7.6.0), Telegram Bot API.
- **Infra:** Cloudflare Pages / Workers KV / Access / DNS; account ID `16f11cb357f34023b2dc26007263c7f2`; KV namespace `CLS_SNAPSHOT`. Node v24.17.0, Wrangler 4.103.0.
- **Backup:** rclone → Google Drive (also the call-recording bridge in Section 10).
- **Email:** Zoho Mail (sales1–4@, role-named), Brevo (transactional + drip), domain authenticated (SPF/DKIM/DMARC live).
---
 
## 14. How Srikanth works (apply by default)
 
- Precise, point-by-point, collaborative. In-depth responses that "leave no stone unturned." Tables wherever they clarify. Real estate / marketing / business-growth analogies. India-specific context. Resource links per response. **An explicitly labeled opinion at the end of every response.** Address him as **Srikanth**.
- **Lock architecture fully before writing code.** Complete one scoped phase/version before the next.
- **Prefers risk tables and comparison tables before code changes.**
- **During incidents:** wants working code + concise steps, not diagnosis.
- **Direct edits over descriptions:** deliver complete updated files, not "change line X."
- **Smart-and-simple over complicated:** pushes back on over-engineering; prefers solutions touching the fewest files using data already available.
- **Iterative deployment:** ships to Cloudflare, checks laptop + mobile, returns with specific visual feedback.
- **Content-in-docs, logic-in-code:** project-detail docs feed content (e.g., email templates) without touching code.
- Works evening sessions, often within token-reset windows.
---
 
## 15. Immediate next action
 
The new project's first build task is **v0.1 — the read-only Viewer**:
1. Self-healing migration to add `users` (+ later `activity_log`, `assignments`).
2. Flask/FastAPI skeleton importing `cls_db.py`.
3. Login + role (admin vs salesperson).
4. Lead list + lead detail, read-only from `cls.db`.
5. Expose via Cloudflare Tunnel; test on laptop + mobile (PWA install).
Sell.do keeps running the entire time. Zero risk to the live pipeline.
 
---
*End of brief. Seed the new project with this file + the Section 12 scripts, set the custom instructions per Section 14, and v0.1 can begin.*
 
