"""
upload_images_to_brevo.py  --  One-time setup script
Uploads all Naishka email images to Brevo CDN and prints
permanent URLs to paste into cls_email_drip.py.

Run ONCE from C:\\CLS after setting BREVO_API_KEY in .env.
Usage:  python upload_images_to_brevo.py
"""

import os, sys, time
BASE_DIR = "C:\\CLS"
sys.path.insert(0, BASE_DIR)

# name field MUST include .jpg extension so Brevo knows the image format
IMAGES = [
    ("elevation",      "https://naishka.asianbuild.in/images/elevation.jpeg",     "naishka_elevation.jpg"),
    ("living_room",    "https://naishka.asianbuild.in/images/interior-02.jpg",    "naishka_living_room.jpg"),
    ("bedroom",        "https://naishka.asianbuild.in/images/interior-04.jpg",    "naishka_bedroom.jpg"),
    ("kitchen",        "https://naishka.asianbuild.in/images/interior-06.jpg",    "naishka_kitchen.jpg"),
    ("balcony",        "https://naishka.asianbuild.in/images/interior-08.jpg",    "naishka_balcony.jpg"),
    ("floorplan_1500", "https://naishka.asianbuild.in/images/floorplan-1500.jpg", "naishka_floorplan1500.jpg"),
    ("floorplan_1700", "https://naishka.asianbuild.in/images/floorplan-1700.jpg", "naishka_floorplan1700.jpg"),
]

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

def main():
    print("=" * 60)
    print(" Naishka Images -- Upload to Brevo CDN")
    print("=" * 60)

    brevo_key = load_brevo_key()
    if not brevo_key:
        print("[ERROR] BREVO_API_KEY not found in .env")
        sys.exit(1)

    import sib_api_v3_sdk
    config = sib_api_v3_sdk.Configuration()
    config.api_key["api-key"] = brevo_key
    api = sib_api_v3_sdk.EmailCampaignsApi(sib_api_v3_sdk.ApiClient(config))

    results = {}
    print("\nUploading " + str(len(IMAGES)) + " images...\n")

    for key, source_url, brevo_name in IMAGES:
        fname = source_url.split("/")[-1]
        try:
            upload_obj = sib_api_v3_sdk.UploadImageToGallery(
                image_url=source_url,
                name=brevo_name
            )
            resp = api.upload_image_to_gallery(upload_obj)
            brevo_url = resp.url
            results[key] = brevo_url
            print("  OK   " + fname.ljust(25) + " -> " + brevo_url)
        except Exception as e:
            results[key] = None
            err = str(e)
            # Extract just the response body for clarity
            if "HTTP response body:" in err:
                body = err.split("HTTP response body:")[-1].strip()
                print("  FAIL " + fname.ljust(25) + " -> " + body[:120])
            else:
                print("  FAIL " + fname.ljust(25) + " -> " + err[:120])
        time.sleep(0.5)

    print()
    print("=" * 60)
    print(" PASTE THIS BLOCK INTO cls_email_drip.py")
    print(" Find NAISHKA_IMAGE_URLS and replace the whole dict")
    print("=" * 60)
    print()
    print("NAISHKA_IMAGE_URLS = {")
    for key, url in results.items():
        if url:
            print('    "' + key + '": "' + url + '",')
        else:
            print('    "' + key + '": "",  # UPLOAD FAILED')
    print("}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print("\nWARNING: " + str(len(failed)) + " upload(s) failed: " + str(failed))
    else:
        print("\nAll 7 images uploaded successfully.")
        print("Paste the block above into cls_email_drip.py")
        print("then run: python send_template_preview.py")

if __name__ == "__main__":
    main()
