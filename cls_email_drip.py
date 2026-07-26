"""
=============================================================
cls_email_drip.py  —  CLS Job D  |  Automated Email Drip
=============================================================
Version : 1.3
Author  : Built for Asian Properties / Srikanth

WHAT CHANGED IN v1.3
--------------------
- CLS1/CLS2 database split support. ADDITIONS ONLY. Added
  cls_db.write_job_result() calls at run()'s two existing return
  points (missing Brevo key, and the final success path) — one line
  to C:\\CLS\\job_results.txt per run, reusing the total_sent/
  total_failed/total_skipped counters already computed. No new
  counting logic. Per Srikanth's explicit call, Job D continues
  reading from CLS2.db (the Sell.do-trusted mirror) during
  parallel-run — a Task Scheduler CLS_DB_PATH env var setting, not a
  code change (see cls_db.py v2.23).

WHAT CHANGED IN v1.2
--------------------
- sync_bounces_from_brevo() added: called at the top of every run().
  Fetches hard + soft bounced email addresses from Brevo Transactional
  API and marks them in cls.db (email_bounced=1, email_bounced_type).
  Requires migrate_db.py to have been run once first.
- Send query now skips leads where email_bounced=1 OR opted_out=1.
  These filters are applied inside get_drip_due() via cls_db, AND as
  an explicit guard in run() before every send attempt.
- Brevo {unsubscribeLink} tag added to the footer of _wrap_email().
  Brevo replaces this with a unique per-recipient one-click unsubscribe
  URL. When clicked, Brevo marks the contact as emailBlacklisted=true
  and blocks all future sends automatically.
- STOP reply text in footer updated to match the unsubscribe link CTA.
- Self-test updated to verify unsubscribeLink present in all templates.

WHAT CHANGED IN v1.1
--------------------
- "Asian Properties" removed from all sender names, headers, and footers.
  Emails now present as "Naishka Homes" / "Grace Classic" / "Prima Paradiso"
  directly — not as a brokerage.
- Elevation photo added at the top of every email body.
- Incoming Day 1 redesigned as a full project-description email with 6
  images (elevation, 4 interiors, floor plan) + map link.
- Website CTA added to every template.
- Bullet-point lists and coloured highlight boxes removed from templates
  2-8 to reduce Gmail Promotions-tab classification. Content rewritten as
  conversational prose.
- Image URLs are served from naishka.asianbuild.in/images/ — see the
  NAISHKA_IMAGE_BASE constant below. Upload the files from email_images/
  to your Cloudflare Pages project before going live.

GMAIL INBOX PLACEMENT NOTES
----------------------------
Incoming Day 1 contains images and project details — it will land in
Promotions or Updates. That is acceptable: it is the first email and
leads are most motivated to open it.

All other templates are written in conversational prose with no pricing
boxes or feature lists, to improve Primary inbox placement over time.
The decisive factor long-term is engagement: once leads reply or click,
Gmail learns to trust the sender.

IMAGE HOSTING
-------------
All 7 images are hosted on Brevo CDN (img.mailinblue.com) — permanent,
email-safe URLs that load correctly in Gmail and all email clients.
These are set in NAISHKA_IMAGE_URLS below. No further uploads needed.

RUN
---
  python cls_email_drip.py               # normal run
  python cls_email_drip.py --dry-run     # log what would send; no emails
  python cls_email_drip.py --selftest    # offline checks
=============================================================
"""

import os
import sys
import time
import sqlite3
import requests
from datetime import datetime

import cls_db

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR = r"C:\CLS"
ENV_FILE = os.path.join(BASE_DIR, ".env")
LOG_FILE = os.path.join(BASE_DIR, "cls_drip_log.txt")

# ── Naishka image base URL ──
# Used as fallback if NAISHKA_IMAGE_URLS is empty.
NAISHKA_IMAGE_BASE = "https://naishka.asianbuild.in/images"

# ── Naishka Brevo CDN URLs (permanent, email-safe) ──
# Run upload_images_to_brevo.py once to populate these.
# Once populated, these take priority over NAISHKA_IMAGE_BASE.
# Leave empty strings until you have run the upload script.
NAISHKA_IMAGE_URLS = {
    "elevation"      : "https://img.mailinblue.com/11406527/images/rnb/original/6a2a4d377af11bd70994696f.jpeg",
    "living_room"    : "https://img.mailinblue.com/11406527/images/rnb/original/6a2a3cb324fef51aaff91139.jpg",
    "bedroom"        : "https://img.mailinblue.com/11406527/images/rnb/original/6a2a3cb42a983c60eb1ac9bf.jpg",
    "kitchen"        : "https://img.mailinblue.com/11406527/images/rnb/original/6a2a3cb62a983c60eb1ac9c0.jpg",
    "balcony"        : "https://img.mailinblue.com/11406527/images/rnb/original/6a2a3cb76c007c094d936a0e.jpg",
    "floorplan_1500" : "https://img.mailinblue.com/11406527/images/rnb/original/6a2a3cb86c007c094d936a0f.jpg",
    "floorplan_1700" : "https://img.mailinblue.com/11406527/images/rnb/original/6a2a3cb924fef51aaff9113a.jpg",
}

# ── Sender mapping — project name -> Brevo sender ──
# No "Asian Properties" here. Each project presents as its own brand.
SENDER_CONFIG = {
    "Naishka": {
        "email": "sales2@asianbuild.in",
        "name" : "Naishka Homes",
    },
    "Grace Classic": {
        "email": "sales3@asianbuild.in",
        "name" : "Grace Classic",
    },
    "Prima Paradiso": {
        "email": "sales4@asianbuild.in",
        "name" : "Prima Paradiso",
    },
}

DEFAULT_SENDER = {
    "email": "sales1@asianbuild.in",
    "name" : "Naishka Homes",
}

API_PAUSE_SEC  = 0.3
DAILY_SEND_CAP = 250


# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry     = f"[{timestamp}] [{level}] {message}"
    print(entry)
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# .env LOADER
# ─────────────────────────────────────────────────────────────

def load_env():
    env = {}
    try:
        from dotenv import dotenv_values
        env = dict(dotenv_values(ENV_FILE))
    except ImportError:
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def project_to_key(project_name):
    if not project_name:
        return "unknown"
    return project_name.strip().lower().replace(" ", "_")


def _lead_first_name(full_name):
    if not full_name or not full_name.strip():
        return "there"
    return full_name.strip().split()[0].title()


def _img(src, alt="", max_width=560):
    """Return a responsive <img> tag safe for all email clients."""
    return (f'<img src="{src}" alt="{alt}" width="{max_width}" '
            f'style="width:100%;max-width:{max_width}px;height:auto;'
            f'display:block;border-radius:6px;margin:0 0 18px;" />')


def _build_img_context(project, override_srcs=None):
    """
    Build the {img_*} format-string values for a project's templates.
    override_srcs : dict of {key: src_string} — used by the preview
                   script to inject base64 data URIs instead of hosted URLs.
    """
    srcs = override_srcs or {}
    if project == "Naishka":
        base = NAISHKA_IMAGE_BASE
        cdn  = NAISHKA_IMAGE_URLS   # Brevo CDN URLs — takes priority when set

        def s(key, fname):
            # Priority: override (preview) > Brevo CDN > Cloudflare Pages base URL
            if srcs.get(key):
                return srcs[key]
            if cdn.get(key):
                return cdn[key]
            return f"{base}/{fname}"

        return {
            # All 8 templates use elevation
            "img_elevation"      : _img(s("elevation",     "elevation.jpeg"),     "Naishka Homes",       560),
            # Incoming Day 1 interior photos
            "img_living"         : _img(s("living_room",   "interior-02.jpg"),    "Living room",         400),
            "img_bedroom"        : _img(s("bedroom",       "interior-04.jpg"),    "Bedroom",             400),
            "img_kitchen"        : _img(s("kitchen",       "interior-06.jpg"),    "Kitchen",             400),
            "img_balcony"        : _img(s("balcony",       "interior-08.jpg"),    "Balcony view",        400),
            # Both floor plans shown in Incoming Day 1
            "img_floor_plan_1500": _img(s("floorplan_1500","floorplan-1500.jpg"), "1500 sft Floor Plan", 520),
            "img_floor_plan_1700": _img(s("floorplan_1700","floorplan-1700.jpg"), "1700 sft Floor Plan", 520),
        }
    # Placeholder for other projects — add their images when building templates
    return {
        "img_elevation"      : "",
        "img_living"         : "",
        "img_bedroom"        : "",
        "img_kitchen"        : "",
        "img_balcony"        : "",
        "img_floor_plan_1500": "",
        "img_floor_plan_1700": "",
    }


# ─────────────────────────────────────────────────────────────
# EMAIL SHELL
# ─────────────────────────────────────────────────────────────

def _wrap_email(body_content, sender_name):
    """
    Consistent email shell. Header shows only the project name — no
    "Asian Properties" branding anywhere.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;color:#2A2F3A;
       line-height:1.65;margin:0;padding:0;background:#F4F5F7;}}
  .w{{max-width:600px;margin:0 auto;background:#fff;
      border:1px solid #E4E6EB;border-radius:8px;overflow:hidden;}}
  .hd{{background:#141C2F;color:#fff;padding:18px 26px;}}
  .hd h2{{margin:0;font-size:17px;font-weight:600;}}
  .bd{{padding:24px 26px;font-size:15px;}}
  .bd p{{margin:0 0 13px;}}
  .ft{{background:#F4F5F7;padding:16px 26px;font-size:12px;
       color:#8A8F9C;border-top:1px solid #E4E6EB;}}
  a.cta{{color:#2F80ED;font-weight:600;text-decoration:none;}}
  a.map-link{{display:inline-block;margin:4px 0 14px;
              color:#2F80ED;font-weight:600;text-decoration:none;}}
</style>
</head>
<body>
<div class="w">
  <div class="hd"><h2>{sender_name}</h2></div>
  <div class="bd">{body_content}</div>
  <div class="ft">
    <p>{sender_name} &nbsp;&middot;&nbsp; Hyderabad, Telangana</p>
    <p style="margin:6px 0 0;">
      Don't want to receive these emails?
      <a href="{{unsubscribeLink}}" style="color:#8A8F9C;">
        Click here to unsubscribe</a>
      &nbsp;or reply with <strong>STOP</strong>.
    </p>
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# TEMPLATE REGISTRY
# ─────────────────────────────────────────────────────────────
# key format: {project_key}_{stage_lower_underscored}_d{day}
#
# Placeholders filled at send time:
#   {lead_name}     — first name
#   {project_name}  — project name from cls.db
#   {img_elevation} — elevation <img> tag
#   {img_living}    — living room <img> tag      (Incoming D1 only)
#   {img_bedroom}   — bedroom <img> tag          (Incoming D1 only)
#   {img_kitchen}   — kitchen <img> tag          (Incoming D1 only)
#   {img_balcony}   — balcony <img> tag          (Incoming D1 only)
#   {img_floor_plan}— floor plan <img> tag       (Incoming D1 only)
# ─────────────────────────────────────────────────────────────

TEMPLATES = {

    # ──────────────────────────────────────────────────────
    # INCOMING  |  2 emails
    # ──────────────────────────────────────────────────────

    # Day 1 — Full project introduction with all images
    "naishka_incoming_d1": {
        "subject": "Thank you for your interest — here is everything about Naishka Homes",
        "body": """
{img_elevation}

<p>Hi {lead_name},</p>

<p>Thank you for reaching out. We are delighted to share everything
about <strong>Naishka Homes</strong> — ready-to-move 3&nbsp;BHK flats
in Padmasri Layout, Bandlaguda Jagir, Hyderabad.</p>

<p><strong>About the project</strong><br>
Naishka Homes is HMDA approved and 100% Vastu compliant. All flats
are 3&nbsp;BHK with sizes ranging from 1,500 to 1,700 sqft, with
East and West facings available. There are no common walls between
flats — each unit has fully independent walls on all sides, giving
you complete privacy.</p>

<p><strong>Pricing</strong><br>
3&nbsp;BHK flats are priced between &#8377;88 Lakhs and &#8377;1 Crore
(basic cost &#8377;5,700/sqft plus &#8377;3,00,000 for amenities).
GST and registration charges apply separately. Prices are negotiable
— our team is happy to work with your budget.</p>

<p><strong>Inside the flat</strong></p>
<table width="100%" cellpadding="4" cellspacing="0" border="0">
<tr>
  <td width="50%" style="padding-right:8px;">{img_living}</td>
  <td width="50%">{img_bedroom}</td>
</tr>
<tr>
  <td width="50%" style="padding-right:8px;">{img_kitchen}</td>
  <td width="50%">{img_balcony}</td>
</tr>
</table>

<p><strong>Amenities</strong><br>
Generator power backup, CCTV surveillance in common areas,
dedicated car parking for each flat, one lift, borewell with
drinking water provision, and 24/7 water supply. Excellent
ventilation from all sides.</p>

<p><strong>Floor plans</strong></p>
<p style="margin:0 0 4px;font-size:13px;color:#666;">1,500 sqft unit</p>
{img_floor_plan_1500}
<p style="margin:0 0 4px;font-size:13px;color:#666;">1,700 sqft unit</p>
{img_floor_plan_1700}

<p><strong>Location</strong><br>
ORR Exit in 7 minutes, Gachibowli in 20 minutes, Hitech City in
25 minutes. Schools nearby include Kangaroo Kids, Glendale Academy,
Pallavi International, and Pristine Public Schools. Shadan Hospitals
is 15 minutes away; Human Touch Hospitals is 10 minutes away.</p>

<p><strong>View on Google Maps</strong><br>
<a class="map-link" href="https://maps.app.goo.gl/cdjehvUA6D5gkSTe7">
&#128205; Open location in Google Maps</a></p>

<p>For more details about our project, visit our website:
<a class="cta" href="https://naishka.asianbuild.in">Click here</a></p>

<p>Our team will reach out to you shortly to answer any questions
and schedule a site visit at your convenience.</p>

<p>Warm regards,<br><strong>Naishka Homes</strong></p>
""",
    },

    # Day 3 — Gentle nudge (still at Incoming = not yet contacted)
    "naishka_incoming_d3": {
        "subject": "Still exploring options? A note from Naishka Homes",
        "body": """
{img_elevation}

<p>Hi {lead_name},</p>

<p>We wanted to follow up in case you are still looking for the
right home in Hyderabad.</p>

<p>Naishka Homes is located in Bandlaguda Jagir — just 7 minutes
from the ORR and 20 minutes from Gachibowli. The flats are ready
to move in, HMDA approved, and priced from &#8377;88 Lakhs for a
spacious 3&nbsp;BHK. Our team is available to answer questions
and arrange a visit at whatever time suits you.</p>

<p>For more details, visit our website:
<a class="cta" href="https://naishka.asianbuild.in">Click here</a></p>

<p>Just reply to this email or call us — we will take it from there.</p>

<p>Best regards,<br><strong>Naishka Homes</strong></p>
""",
    },

    # ──────────────────────────────────────────────────────
    # PROSPECT  |  3 emails
    # ──────────────────────────────────────────────────────

    # Day 1 — Detailed overview
    "naishka_prospect_d1": {
        "subject": "Your overview of Naishka Homes, {lead_name}",
        "body": """
{img_elevation}

<p>Hi {lead_name},</p>

<p>Thank you for your interest in Naishka Homes. Here is a
complete overview to help you evaluate the project.</p>

<p>The flats are 3&nbsp;BHK, ranging from 1,500 to 1,700 sqft,
with East and West facings. They are ready to move — you visit
the actual flat, not a model unit, and can move in as soon as
the paperwork is complete. Every flat is HMDA approved, 100%
Vastu compliant, and has no common walls with neighbouring units.</p>

<p>Pricing starts at &#8377;88 Lakhs and goes up to &#8377;1 Crore,
depending on size and floor. Our team is open to discussion on
pricing — please do not hesitate to ask.</p>

<p>The project comes with dedicated car parking, a lift, generator
backup, CCTV surveillance, and 24/7 water supply. It is 7 minutes
from the ORR and 20 minutes from Gachibowli, with several good
schools within a short drive.</p>

<p>For more details, visit our website:
<a class="cta" href="https://naishka.asianbuild.in">Click here</a></p>

<p>Reply to schedule a visit or ask any questions — we are happy
to help.</p>

<p>Warm regards,<br><strong>Naishka Homes</strong></p>
""",
    },

    # Day 4 — Differentiation (why Naishka)
    "naishka_prospect_d4": {
        "subject": "What makes Naishka Homes different, {lead_name}",
        "body": """
{img_elevation}

<p>Hi {lead_name},</p>

<p>When families compare projects in the Bandlaguda Jagir area,
a couple of things about Naishka Homes consistently come up.</p>

<p>First, there are no common walls. Every flat has fully
independent walls on all four sides — no shared boundary with
a neighbour. This means better privacy, less noise, and no future
disputes over wall ownership. It is a rarer feature than most
people realise in this price range.</p>

<p>Second, the project is genuinely 100% Vastu compliant —
designed from the foundation up, not adjusted after the fact.
For families that consider Vastu when choosing a home, this
matters a great deal.</p>

<p>Schools like Glendale Academy and Pallavi International are
within a few minutes' drive. Shadan Hospitals and Human Touch
Hospitals are 10 to 15 minutes away.</p>

<p>For more details, visit our website:
<a class="cta" href="https://naishka.asianbuild.in">Click here</a></p>

<p>Would you like to visit this week? Reply with a convenient
day and time and we will arrange everything.</p>

<p>Best regards,<br><strong>Naishka Homes</strong></p>
""",
    },

    # Day 10 — Site visit invitation
    "naishka_prospect_d10": {
        "subject": "Have you had a chance to visit Naishka Homes?",
        "body": """
{img_elevation}

<p>Hi {lead_name},</p>

<p>We wanted to check in — if you have not yet had the chance
to visit Naishka Homes, this is a good time.</p>

<p>The flats are ready to move in, so you will see the actual
unit — the real size, the finish, the natural light — not a
brochure. Several families have already made their decision
after a single visit.</p>

<p>Our team can arrange a visit on any day that works for you,
including evenings and weekends. Pricing is open to discussion.</p>

<p>For more details, visit our website:
<a class="cta" href="https://naishka.asianbuild.in">Click here</a></p>

<p>Just reply or call us to set it up.</p>

<p>Warm regards,<br><strong>Naishka Homes</strong></p>
""",
    },

    # ──────────────────────────────────────────────────────
    # OPPORTUNITY  |  2 emails
    # ──────────────────────────────────────────────────────

    # Day 1 — Investment angle, personalised
    "naishka_opportunity_d1": {
        "subject": "A note on your Naishka Homes decision, {lead_name}",
        "body": """
{img_elevation}

<p>Hi {lead_name},</p>

<p>Thank you for seriously considering Naishka Homes. We
appreciate the time you have taken, and we want to make sure
you have everything you need to decide confidently.</p>

<p>A few things worth keeping in mind: the flats are HMDA
approved with a clean title, which makes bank loans
straightforward. They are ready to move, so there is no
construction risk — what you see is exactly what you get.
And Bandlaguda Jagir is one of the fastest-growing
residential corridors near the Financial District, which
supports long-term value whether you plan to live here or
rent it out.</p>

<p>If you have any questions about a specific unit, the
payment structure, or the registration process, please
write back. We are happy to walk you through everything.</p>

<p>For more details, visit our website:
<a class="cta" href="https://naishka.asianbuild.in">Click here</a></p>

<p>Warm regards,<br><strong>Naishka Homes</strong></p>
""",
    },

    # Day 5 — Soft close, negotiation
    "naishka_opportunity_d5": {
        "subject": "Ready to take the next step, {lead_name}?",
        "body": """
{img_elevation}

<p>Hi {lead_name},</p>

<p>We hope your evaluation of Naishka Homes is going well. If
there is anything holding you back — a question about the price,
a concern about the process, or a comparison with another project
— please share it with us. We would rather address it honestly
than leave you uncertain.</p>

<p>Our team has some flexibility on pricing and is ready to
discuss a number that works for you. Once you decide, the
process is simple: choose your unit, agree on the price, pay
a token to hold it, and complete registration at your
convenience.</p>

<p>For more details, visit our website:
<a class="cta" href="https://naishka.asianbuild.in">Click here</a></p>

<p>Reply or call us anytime — we are here.</p>

<p>Best regards,<br><strong>Naishka Homes</strong></p>
""",
    },

    # ──────────────────────────────────────────────────────
    # SITE VISITED  |  1 email
    # ──────────────────────────────────────────────────────

    # Day 1 — Thank you + next steps
    "naishka_site_visited_d1": {
        "subject": "Thank you for visiting Naishka Homes, {lead_name}",
        "body": """
{img_elevation}

<p>Hi {lead_name},</p>

<p>Thank you for visiting Naishka Homes. We hope you came away
with a clear picture of the space, the construction quality,
and the neighbourhood.</p>

<p>When you are ready to move forward, the process is
straightforward: choose your preferred unit, we discuss and
agree on the final price, you pay a token amount to hold it,
and registration is completed at a time that suits you.
Our team will be with you at every step.</p>

<p>If you would like to bring a family member for a second
look, we are happy to arrange another visit anytime.</p>

<p>For more details, visit our website:
<a class="cta" href="https://naishka.asianbuild.in">Click here</a></p>

<p>We look forward to welcoming you as a Naishka Homes resident.</p>

<p>Warm regards,<br><strong>Naishka Homes</strong></p>
""",
    },
}


# ─────────────────────────────────────────────────────────────
# BREVO SEND
# ─────────────────────────────────────────────────────────────

def send_email(api_instance, to_email, to_name, sender_email,
               sender_name, subject, html_content):
    import sib_api_v3_sdk
    send_smtp = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email, "name": to_name}],
        sender={"email": sender_email, "name": sender_name},
        subject=subject,
        html_content=html_content,
        # List-Unsubscribe header tells Brevo the email handles its own
        # unsubscribe, suppressing their injected footer. Without this,
        # Brevo injects ~100KB of footer HTML on the free plan, pushing
        # every email past Gmail's 102KB clip limit.
        headers={
            "List-Unsubscribe": "<mailto:" + sender_email + "?subject=unsubscribe>",
        },
    )
    try:
        resp = api_instance.send_transac_email(send_smtp)
        msg_id = getattr(resp, "message_id", str(resp))
        return True, msg_id
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────
# BOUNCE SYNC  (Brevo → cls.db)
# ─────────────────────────────────────────────────────────────

def sync_bounces_from_brevo(brevo_key):
    """
    Fetch hard + soft bounced email addresses from Brevo's Transactional
    Events API and mark them in cls.db so Job D never attempts to send
    to them again.

    Columns written (added by migrate_db.py):
      email_bounced      INTEGER  1 = bounced
      email_bounced_type TEXT     'hard' | 'soft'

    Hard bounces  = permanent bad address  → always suppress
    Soft bounces  = temporary failure      → suppress for now; Brevo will
                                             retry automatically on its side
    """
    if not brevo_key:
        log("sync_bounces_from_brevo: no API key — skipping.", "WARNING")
        return 0

    log("Syncing bounces from Brevo...")

    headers = {
        "accept"  : "application/json",
        "api-key" : brevo_key,
    }

    suppressed = {"hard": [], "soft": []}
    event_map  = {"hardBounces": "hard", "softBounces": "soft"}

    for event_type, bounce_key in event_map.items():
        url = (f"https://api.brevo.com/v3/smtp/statistics/events"
               f"?event={event_type}&limit=100")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                log(f"  Brevo API error ({event_type}): "
                    f"HTTP {resp.status_code} — {resp.text[:120]}", "WARNING")
                continue
            events = resp.json().get("events", [])
            for e in events:
                email = (e.get("email") or "").strip().lower()
                if email:
                    suppressed[bounce_key].append(email)
            log(f"  Brevo returned {len(suppressed[bounce_key])} {bounce_key} bounce(s).")
        except Exception as exc:
            log(f"  sync_bounces_from_brevo request failed ({event_type}): {exc}",
                "WARNING")

    db_path = os.path.join(BASE_DIR, "cls.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    total_marked = 0

    for bounce_type, emails in suppressed.items():
        for email in emails:
            cur.execute("""
                UPDATE leads
                SET    email_bounced      = 1,
                       email_bounced_type = ?
                WHERE  LOWER(TRIM(COALESCE(email_norm, ''))) = ?
                  AND  COALESCE(email_bounced, 0)            = 0
            """, (bounce_type, email))
            if cur.rowcount > 0:
                total_marked += 1

    conn.commit()
    conn.close()

    log(f"  Bounce sync complete — {total_marked} lead(s) newly suppressed "
        f"({len(suppressed['hard'])} hard, {len(suppressed['soft'])} soft).")
    return total_marked


# ─────────────────────────────────────────────────────────────
# MAINTENANCE PASS
# ─────────────────────────────────────────────────────────────

def maintenance_pass():
    conn = cls_db._connect()
    try:
        ph = ",".join("?" for _ in cls_db.DRIP_PAUSE_STAGES)
        to_pause = conn.execute(
            f"SELECT cls_id FROM leads WHERE drip_enrolled_at IS NOT NULL"
            f" AND current_stage IN ({ph}) AND COALESCE(drip_paused,0)!=1",
            cls_db.DRIP_PAUSE_STAGES).fetchall()
        paused = 0
        for r in to_pause:
            cls_db.pause_drip(r["cls_id"]); paused += 1

        to_unpause = conn.execute(
            f"SELECT cls_id,current_stage FROM leads"
            f" WHERE drip_enrolled_at IS NOT NULL AND drip_paused=1"
            f" AND current_stage NOT IN ({ph})",
            cls_db.DRIP_PAUSE_STAGES).fetchall()
        unpaused = 0
        for r in to_unpause:
            if r["current_stage"] not in cls_db.DRIP_TERMINAL_STAGES:
                cls_db.unpause_drip(r["cls_id"]); unpaused += 1

        return paused, unpaused
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run(dry_run=False, img_overrides=None):
    """
    img_overrides : dict of {img_key: src_string} passed by the preview
                    script to inject base64 images instead of hosted URLs.
    """
    log("=" * 55)
    log("CLS JOB D — Email Drip — START")
    if dry_run:
        log("MODE: --dry-run (no emails will actually be sent)")
    log("=" * 55)

    cls_db.init_db()

    env = load_env()
    brevo_key = env.get("BREVO_API_KEY", "")
    if not brevo_key and not dry_run:
        log("BREVO_API_KEY missing in .env — aborting.", "ERROR")
        cls_db.write_job_result("Job D (Email Drip)", False,
                                 "BREVO_API_KEY missing in .env")
        return False

    api_instance = None
    if not dry_run:
        import sib_api_v3_sdk
        cfg = sib_api_v3_sdk.Configuration()
        cfg.api_key["api-key"] = brevo_key
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(cfg))

    newly_enrolled = cls_db.bulk_enroll_drip()
    if newly_enrolled:
        log(f"Enrolled {newly_enrolled} new lead(s) into drip.")

    # ── Bounce sync: pull latest Brevo bounce list → suppress in cls.db ──
    # Must run AFTER brevo_key is validated and BEFORE send loop.
    sync_bounces_from_brevo(brevo_key)

    paused, unpaused = maintenance_pass()
    if paused or unpaused:
        log(f"Maintenance: paused {paused}, unpaused {unpaused} lead(s).")

    total_sent = total_failed = total_skipped = no_template = 0
    per_stage_report = []

    for stage, days in cls_db.DRIP_SCHEDULE.items():
        stage_sent = 0
        for day_num in days:
            leads = cls_db.get_drip_due(stage, day_num)
            if not leads:
                continue
            log(f"  {stage} Day {day_num}: {len(leads)} lead(s) due")

            for lead in leads:
                if total_sent >= DAILY_SEND_CAP:
                    log(f"Daily cap ({DAILY_SEND_CAP}) reached.", "WARNING")
                    break

                project   = lead.get("project") or ""
                proj_key  = project_to_key(project)
                tmpl_key  = f"{proj_key}_{stage.lower().replace(' ','_')}_d{day_num}"
                lead_name = _lead_first_name(lead.get("full_name"))
                to_email  = lead.get("email_norm", "")
                to_name   = lead.get("full_name") or ""

                # ── Skip bounced or opted-out leads ──────────────────
                if lead.get("email_bounced"):
                    total_skipped += 1
                    log(f"    SKIP (bounced/{lead.get('email_bounced_type','?')})"
                        f" cls_id={lead['cls_id']} {to_email}")
                    continue
                if lead.get("opted_out"):
                    total_skipped += 1
                    log(f"    SKIP (opted_out) cls_id={lead['cls_id']} {to_email}")
                    continue

                template = TEMPLATES.get(tmpl_key)
                if not template:
                    no_template += 1
                    continue

                sender = SENDER_CONFIG.get(project, DEFAULT_SENDER)
                img_ctx = _build_img_context(project, img_overrides)

                context = {
                    "lead_name"   : lead_name,
                    "project_name": project,
                    **img_ctx,
                }
                subject    = template["subject"].format(**context)
                body_inner = template["body"].format(**context)
                html       = _wrap_email(body_inner, sender["name"])

                if cls_db.was_email_sent(lead["cls_id"], stage, day_num):
                    total_skipped += 1
                    continue

                if dry_run:
                    log(f"    DRY-RUN: {tmpl_key} -> {to_email}")
                    cls_db.record_comms(
                        cls_id=lead["cls_id"], project=project,
                        drip_stage=stage, day_number=day_num,
                        template_key=tmpl_key, sender_email=sender["email"],
                        brevo_message_id="dry_run", status="sent")
                    total_sent += 1; stage_sent += 1
                else:
                    ok, msg_id = send_email(
                        api_instance, to_email, to_name,
                        sender["email"], sender["name"], subject, html)
                    status = "sent" if ok else "failed"
                    cls_db.record_comms(
                        cls_id=lead["cls_id"], project=project,
                        drip_stage=stage, day_number=day_num,
                        template_key=tmpl_key, sender_email=sender["email"],
                        brevo_message_id=msg_id, status=status)
                    if ok:
                        total_sent += 1; stage_sent += 1
                        log(f"    SENT {tmpl_key} -> {to_email}")
                    else:
                        total_failed += 1
                        log(f"    FAILED {tmpl_key}: {msg_id}", "ERROR")
                    time.sleep(API_PAUSE_SEC)

            if total_sent >= DAILY_SEND_CAP:
                break
        if stage_sent:
            per_stage_report.append((stage, stage_sent))
        if total_sent >= DAILY_SEND_CAP:
            break

    log("-" * 55)
    log("SEND SUMMARY")
    for stage, count in per_stage_report:
        log(f"  {stage:16s}: {count} sent")
    log(f"TOTAL: {total_sent} sent, {total_failed} failed, "
        f"{total_skipped} skipped")
    if no_template:
        log(f"  {no_template} lead(s) skipped — no template for their project yet.")

    ds = cls_db.drip_stats()
    log(f"Enrolled: {ds['drip_enrolled']} | Paused: {ds['drip_paused']} | "
        f"Opt-out: {ds['email_opt_out']} | Bounced: {ds['hard_bounced']}")
    log(f"Emails sent all-time: {ds['emails_sent']} | Today: {ds['emails_today']}")

    cls_db.set_flag("email_drip")
    log("Completion flag 'email_drip' set.")
    log("=" * 55)
    log("CLS JOB D — Email Drip — DONE")
    log("=" * 55)
    cls_db.write_job_result("Job D (Email Drip)", True,
                             f"{total_sent} sent, {total_failed} failed, {total_skipped} skipped")
    return True


# ─────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────

def selftest():
    print("=" * 55)
    print(" CLS EMAIL DRIP v1.2 — SELF TEST (offline)")
    print("=" * 55)

    tests = [("Naishka","naishka"),("Grace Classic","grace_classic"),
             ("Prima Paradiso","prima_paradiso"),(None,"unknown")]
    for raw, exp in tests:
        got = project_to_key(raw)
        print(f"  [{'OK' if got==exp else 'FAIL'}] project_to_key({raw!r}) = {got!r}")

    print("\n--- Template coverage (Naishka) ---")
    for stage, days in cls_db.DRIP_SCHEDULE.items():
        sk = stage.lower().replace(" ","_")
        for d in days:
            k = f"naishka_{sk}_d{d}"
            print(f"  [{'OK' if k in TEMPLATES else 'MISS'}] {k}")

    print("\n--- Rendering with images ---")
    cls_db.init_db()
    img_ctx = _build_img_context("Naishka")
    all_ok = True
    for key in [k for k in TEMPLATES if k.startswith("naishka_")]:
        tmpl = TEMPLATES[key]
        ctx  = {"lead_name":"Srikanth","project_name":"Naishka",**img_ctx}
        try:
            subj = tmpl["subject"].format(**ctx)
            body = tmpl["body"].format(**ctx)
            html = _wrap_email(body, "Naishka Homes")
            ok   = ("Naishka Homes" in html and "Asian Properties" not in html
                    and "STOP" in html and "naishka.asianbuild.in" in html
                    and "unsubscribeLink" in html)
            print(f"  [{'OK' if ok else 'FAIL'}] {key}  ({len(html)} chars)"
                  + ("" if ok else " — MISSING brand/link check"))
            if not ok: all_ok = False
        except KeyError as e:
            print(f"  [FAIL] {key} — missing placeholder {e}")
            all_ok = False

    print(f"\n  {'All templates pass.' if all_ok else 'FIX NEEDED.'}")
    print("\n--- Sender names (no Asian Properties) ---")
    for proj, cfg in SENDER_CONFIG.items():
        ok = "Asian Properties" not in cfg["name"]
        print(f"  [{'OK' if ok else 'FAIL'}] {proj}: '{cfg['name']}'")

    print("\n--- Drip stats ---")
    ds = cls_db.drip_stats()
    for k,v in ds.items():
        print(f"  {k:18s}: {v}")

    print("=" * 55)
    print(" SELF TEST COMPLETE (v1.3)")
    print("=" * 55)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
    elif "--dry-run" in args:
        run(dry_run=True)
    else:
        run()
