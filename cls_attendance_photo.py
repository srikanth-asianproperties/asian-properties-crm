"""
=============================================================
cls_attendance_photo.py — APX Attendance photo watermarking
=============================================================
Version : 1.0
Author  : Built for Asian Properties / Srikanth

WHAT THIS IS
------------
APX Attendance Chunk A (2026-08-06): server-side compositing of the
punch-in/punch-out selfie. crm/app.py's api_attendance_punch_in/out
routes now call render_punch_photo() instead of saving the uploaded
photo straight to disk.

The client (PunchActivity.kt v3) no longer draws any text watermark
itself — it only resizes/compresses the raw selfie. ALL overlay
drawing (map thumbnail + text, or the plain-text fallback) happens
here, once, so the two never stack on top of each other.

THREE-LAYER FALLBACK ("attendance must never fail over an image
problem" — Srikanth's explicit instruction for this task):
  1. Best case: Google Static Maps pin thumbnail + coordinates/date-
     time text block composited onto the photo.
  2. If ANYTHING in step 1 fails (missing/invalid CLS_MAPS_API_KEY,
     network error, quota, bad response, Pillow decode error) — fall
     back to the OLD plain-text style (numeric Lat/Lng + timestamp,
     no map thumbnail), drawn directly onto the photo via Pillow.
  3. If even step 2 fails (e.g. Pillow itself can't decode the
     upload) — return the original photo bytes completely untouched.
Every layer is wrapped so this module's public function cannot raise.

CLS_MAPS_API_KEY
-----------------
Read from a real OS environment variable at import time — same
"never hardcoded, never in .env" convention as cls_db.py's
CLS_DB_PATH and crm/app.py's CLS_ATTENDANCE_PHOTOS_DIR. No default:
if it's unset, that's logged once at import time and every call
short-circuits straight to the step-2 fallback (no point attempting
a Static Maps request that can only 403).

SCOPE NOTE — coordinates only, not a real street address
----------------------------------------------------------
Srikanth confirmed (2026-08-06) this renders formatted Lat/Lng, not a
reverse-geocoded street address. A real address needs a second,
separate Google Geocoding API call — PunchActivity.kt's own v1
docstring already flagged that as a deferred v1.5 add-on; Chunk A
does not pull it in.

NEW DEPENDENCY: Pillow (not previously installed anywhere in this
codebase) — added to crm/requirements.txt alongside this file.
`requests` was already a project dependency (see CLAUDE.md), no new
dependency there.

WHY THIS ISN'T IN cls_db.py
-----------------------------
This module does no SQLite access at all (record_punch() only ever
stored the photo *filename*, never bytes) — it's image/HTTP work, so
per CLAUDE.md's "All SQLite access stays centralized in cls_db.py"
rule, it belongs in its own small module rather than bloating that
file with non-DB logic.
"""

import io
import logging
import os

import requests

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

log = logging.getLogger("cls_attendance_photo")

CLS_MAPS_API_KEY = os.environ.get("CLS_MAPS_API_KEY")
if not CLS_MAPS_API_KEY:
    log.warning(
        "CLS_MAPS_API_KEY not set — map thumbnail overlay disabled for this "
        "process; every punch photo will use the plain-text fallback style."
    )

STATIC_MAPS_URL = "https://maps.googleapis.com/maps/api/staticmap"
STATIC_MAPS_TIMEOUT_S = 5          # bounded worst-case delay added to a punch
MAP_THUMB_SIZE_PX = 160            # square thumbnail, bottom-left corner
MAP_ZOOM = 16

TEXT_MARGIN_PX = 14
TEXT_BG_COLOR = (0, 0, 0, 150)     # translucent black band behind text
TEXT_COLOR = (255, 255, 255, 255)

JPEG_SAVE_QUALITY = 85             # composite is drawn on an already-small
                                   # client-resized photo — this is a final
                                   # re-encode pass, not the primary size
                                   # control (that's PunchActivity.kt's job)


def _guarded(label, fn):
    """Runs fn(), logs+returns None on ANY exception instead of raising —
    every step of the map-composite path is wrapped with this so a single
    bad response/timeout/decode error can never propagate up into the
    Flask route and block a punch."""
    try:
        return fn()
    except Exception as e:
        log.warning("cls_attendance_photo: %s failed: %s", label, e)
        return None


def _fetch_map_thumbnail(lat, lng):
    """Static Maps pin-marker thumbnail as PNG bytes, or None on any
    failure. Short, bounded timeout — this must never be the reason a
    punch-in spinner hangs."""
    if not CLS_MAPS_API_KEY:
        return None
    params = {
        "center": f"{lat},{lng}",
        "zoom": MAP_ZOOM,
        "size": f"{MAP_THUMB_SIZE_PX}x{MAP_THUMB_SIZE_PX}",
        "markers": f"color:red|{lat},{lng}",
        "key": CLS_MAPS_API_KEY,
    }
    resp = requests.get(STATIC_MAPS_URL, params=params, timeout=STATIC_MAPS_TIMEOUT_S)
    resp.raise_for_status()
    if not resp.headers.get("Content-Type", "").startswith("image/"):
        # Google returns a 200 with an error image (or JSON, depending on
        # the failure) for some bad-key/quota cases — a non-image
        # Content-Type means treat it as a failure, not a thumbnail.
        raise ValueError(f"Static Maps returned non-image content-type: {resp.headers.get('Content-Type')}")
    return resp.content


def _draw_text_block(draw, xy, lines, font, anchor_right=False, canvas_size=None):
    """Draws `lines` inside a translucent background band, anchored at xy
    (top-left of the block) or right-aligned against canvas_size[0] if
    anchor_right. Shared by both the map-composite text block and the
    plain-text fallback so the two styles share one implementation."""
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    line_widths = [draw.textbbox((0, 0), line, font=font)[2] for line in lines]
    block_w = max(line_widths) + 2 * TEXT_MARGIN_PX
    block_h = sum(line_heights) + 2 * TEXT_MARGIN_PX + (len(lines) - 1) * 4

    x0, y0 = xy
    if anchor_right and canvas_size:
        x0 = canvas_size[0] - block_w - TEXT_MARGIN_PX
    draw.rectangle([x0, y0, x0 + block_w, y0 + block_h], fill=TEXT_BG_COLOR)

    cursor_y = y0 + TEXT_MARGIN_PX
    for line, lh in zip(lines, line_heights):
        draw.text((x0 + TEXT_MARGIN_PX, cursor_y), line, font=font, fill=TEXT_COLOR)
        cursor_y += lh + 4


def _load_font():
    """Best-effort truetype font for a slightly nicer look; falls back to
    Pillow's built-in bitmap font (always available, no file dependency)
    if no truetype font can be found on this machine."""
    for candidate in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, 18)
        except Exception:
            continue
    return ImageFont.load_default()


def _composite_with_map(photo_bytes, lat, lng, ts_str):
    """Layer 1 (best case): map thumbnail bottom-left, coordinates/date-
    time text block bottom-right. Returns JPEG bytes, or None if any step
    fails (caller falls back to _plain_text_overlay)."""
    thumb_bytes = _guarded("_fetch_map_thumbnail", lambda: _fetch_map_thumbnail(lat, lng))
    if thumb_bytes is None:
        return None

    base = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    thumb = Image.open(io.BytesIO(thumb_bytes)).convert("RGBA")

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font()

    # Map thumbnail, bottom-left, with a small margin, plus a thin white
    # border so it stays visible against a dark photo background.
    thumb_x = TEXT_MARGIN_PX
    thumb_y = base.size[1] - thumb.size[1] - TEXT_MARGIN_PX
    border = Image.new(
        "RGBA", (thumb.size[0] + 4, thumb.size[1] + 4), (255, 255, 255, 220)
    )
    overlay.paste(border, (thumb_x - 2, thumb_y - 2), border)
    overlay.paste(thumb, (thumb_x, thumb_y), thumb)

    lines = [
        "Lat: {:.6f}  Lng: {:.6f}".format(lat, lng),
        ts_str,
    ]
    text_y = base.size[1] - TEXT_MARGIN_PX - 70
    _draw_text_block(draw, (0, text_y), lines, font, anchor_right=True, canvas_size=base.size)

    composited = Image.alpha_composite(base, overlay).convert("RGB")
    out = io.BytesIO()
    composited.save(out, format="JPEG", quality=JPEG_SAVE_QUALITY)
    return out.getvalue()


def _plain_text_overlay(photo_bytes, lat, lng, ts_str):
    """Layer 2 fallback: the OLD client-side watermark style (numeric
    Lat/Lng + timestamp, bottom-left, no map thumbnail) — now drawn
    server-side instead of on the phone. Returns JPEG bytes, or None if
    even this fails (caller falls back to the untouched original)."""
    base = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font()

    lines = [
        "Lat: {:.6f}  Lng: {:.6f}".format(lat, lng),
        ts_str,
    ]
    text_y = base.size[1] - TEXT_MARGIN_PX - 70
    _draw_text_block(draw, (TEXT_MARGIN_PX, text_y), lines, font)

    composited = Image.alpha_composite(base, overlay).convert("RGB")
    out = io.BytesIO()
    composited.save(out, format="JPEG", quality=JPEG_SAVE_QUALITY)
    return out.getvalue()


def render_punch_photo(photo_bytes, lat, lng, ts_str):
    """
    Public entry point — called by crm/app.py's punch-in/punch-out routes
    in place of the old `uploaded.save(path)`.

    photo_bytes : raw JPEG bytes as uploaded by PunchActivity.kt (already
                  resized/compressed client-side — this function does not
                  resize, only overlays).
    lat, lng    : floats, already validated by _parse_punch_request().
    ts_str      : the same 'YYYY-MM-DD HH:MM:SS' string app.py computed
                  for this punch.

    Returns JPEG bytes to write to disk. NEVER raises — worst case
    (Pillow missing, or every layer fails) returns photo_bytes unchanged,
    so a photo/map problem can never fail the punch itself.
    """
    if not _PIL_AVAILABLE:
        log.warning("cls_attendance_photo: Pillow not installed — saving photo unmodified.")
        return photo_bytes

    result = _guarded("_composite_with_map", lambda: _composite_with_map(photo_bytes, lat, lng, ts_str))
    if result is not None:
        return result

    result = _guarded("_plain_text_overlay", lambda: _plain_text_overlay(photo_bytes, lat, lng, ts_str))
    if result is not None:
        return result

    log.warning("cls_attendance_photo: all overlay layers failed — saving original photo unmodified.")
    return photo_bytes
