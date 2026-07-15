"""
send_template_preview.py  v3  --  One-time preview sender
Sends all 8 Naishka templates to mandhapatims@gmail.com.
Uses Brevo CDN image URLs from cls_email_drip.py — no base64.

Copy to C:\CLS\ and run:
  python send_template_preview.py
"""

import os, sys, time
BASE_DIR = "C:\\CLS"
sys.path.insert(0, BASE_DIR)

PREVIEW_EMAIL = "mandhapatims@gmail.com"
PREVIEW_NAME  = "Srikanth (Preview)"
PAUSE_SEC     = 1.5

def load_brevo_key():
    env_file = os.path.join(BASE_DIR, ".env")
    env = {}
    try:
        from dotenv import dotenv_values
        env = dict(dotenv_values(env_file))
    except ImportError:
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env.get("BREVO_API_KEY", "")

from cls_email_drip import (TEMPLATES, SENDER_CONFIG, _wrap_email,
                             _build_img_context, NAISHKA_IMAGE_URLS)

SEND_ORDER = [
    ("naishka_incoming_d1",     "Naishka", "Incoming",     1),
    ("naishka_incoming_d3",     "Naishka", "Incoming",     3),
    ("naishka_prospect_d1",     "Naishka", "Prospect",     1),
    ("naishka_prospect_d4",     "Naishka", "Prospect",     4),
    ("naishka_prospect_d10",    "Naishka", "Prospect",    10),
    ("naishka_opportunity_d1",  "Naishka", "Opportunity",  1),
    ("naishka_opportunity_d5",  "Naishka", "Opportunity",  5),
    ("naishka_site_visited_d1", "Naishka", "Site Visited", 1),
]

def verify_urls():
    print("Verifying Brevo CDN URLs in cls_email_drip.py...")
    empty = [k for k, v in NAISHKA_IMAGE_URLS.items() if not v]
    if empty:
        print("  WARNING: These image keys are empty: " + str(empty))
        print("  Images will fall back to Cloudflare and may not load.")
    else:
        print("  All 7 Brevo CDN URLs populated. Good to go.")
    print()

def main():
    print("=" * 55)
    print(" Naishka Homes -- Template Preview v3")
    print(" Sending to: " + PREVIEW_EMAIL)
    print("=" * 55)
    print()

    brevo_key = load_brevo_key()
    if not brevo_key:
        print("[ERROR] BREVO_API_KEY not found in .env")
        sys.exit(1)

    verify_urls()

    import sib_api_v3_sdk
    config = sib_api_v3_sdk.Configuration()
    config.api_key["api-key"] = brevo_key
    api = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(config))

    sent = failed = 0
    n = len(SEND_ORDER)

    for idx, (tmpl_key, project, stage, day) in enumerate(SEND_ORDER, 1):
        tmpl   = TEMPLATES[tmpl_key]
        sender = SENDER_CONFIG[project]

        # Use Brevo CDN URLs — no overrides, no base64
        img_ctx = _build_img_context(project)
        context = {
            "lead_name"   : "Srikanth",
            "project_name": project,
            **img_ctx,
        }
        subject    = tmpl["subject"].format(**context)
        body_inner = tmpl["body"].format(**context)
        html       = _wrap_email(body_inner, sender["name"])

        # Small preview banner
        banner = (
            '<div style="background:#FEF9C3;border:1px solid #FCD34D;'
            'border-radius:6px;padding:9px 14px;margin-bottom:18px;'
            'font-family:monospace;font-size:12px;color:#92400E;">'
            '<strong>PREVIEW ' + str(idx) + '/' + str(n) + '</strong>'
            ' &nbsp; ' + stage + ' Day ' + str(day) +
            ' &nbsp;|&nbsp; key: ' + tmpl_key + '</div>'
        )
        html = html.replace('<div class="bd">', '<div class="bd">' + banner)

        email_obj = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": PREVIEW_EMAIL, "name": PREVIEW_NAME}],
            sender={"email": sender["email"], "name": sender["name"]},
            subject="[PREVIEW " + str(idx) + "/" + str(n) + " | " + stage + " Day " + str(day) + "] " + subject,
            html_content=html,
            headers={
                "List-Unsubscribe": "<mailto:" + sender["email"] + "?subject=unsubscribe>",
            },
        )
        try:
            api.send_transac_email(email_obj)
            print("  [" + str(idx) + "/" + str(n) + "] SENT   " + stage + " Day " + str(day))
            sent += 1
        except Exception as e:
            print("  [" + str(idx) + "/" + str(n) + "] FAILED " + stage + " Day " + str(day) + ": " + str(e)[:80])
            failed += 1

        if idx < n:
            time.sleep(PAUSE_SEC)

    print("-" * 55)
    print("Done -- " + str(sent) + " sent, " + str(failed) + " failed")
    print("Check your inbox at " + PREVIEW_EMAIL)
    print("=" * 55)

if __name__ == "__main__":
    main()
