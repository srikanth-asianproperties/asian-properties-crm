"""
=============================================================
cls_ai.py — Asian Properties CRM (APX) | AI provider layer
=============================================================
Version : 0.2
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v0.2 (2026-09-29) — DEFAULT_DAILY_CAPS gains "daily_brief": 5 (AI-2 Daily AI Brief;
  one call/day expected, cap leaves room for manual re-runs).
v0.1 (2026-09-29) — initial. AI phase Step 1.
  - PROVIDER_REGISTRY (config-not-code): one entry per provider. Adding
    Gemini later = one registry entry + one _call_<provider>() function
    + one line in _PROVIDER_CALLERS. Nothing else changes.
  - get_available_providers(): only providers whose API-key env var is
    set and non-empty — a provider with no key never appears in the
    Settings dropdown.
  - get/set_ai_provider_config(): app_settings['ai_provider_config']
    (JSON). set_ validates provider+model before writing.
  - call_llm(): the ONLY place in the codebase that talks to an LLM API.
    Hard 12s timeout, NEVER raises, never puts the API key in any
    returned error/log text, daily per-purpose call cap.
  - PROMPT_VERSION: bump to invalidate every cached AI output at once.

WHY THE KEY IS AN OS ENV VAR (not .env): same reason as CLS_DB_PATH /
FCM_SERVICE_ACCOUNT_KEY_PATH — see CLAUDE.md. Restart the app after
setting it.

PRIVACY: prompts are built by the CALLER and must never contain lead
name/phone/email (DPDP). This module does not inspect prompts.
"""

import hashlib
import json
import os
import sys

import requests

import cls_db

PROMPT_VERSION = "score_explain_v1"      # bump -> every cached explanation goes stale
LLM_TIMEOUT_SECONDS = 12
AI_CONFIG_KEY = "ai_provider_config"
DEFAULT_DAILY_CAPS = {"score_explanation": 100, "daily_brief": 5}
FALLBACK_DAILY_CAP = 100                 # purposes with no explicit cap

PROVIDER_REGISTRY = {
    "anthropic": {
        "label": "Claude (Anthropic)",
        "env_var": "CLS_AI_ANTHROPIC_KEY",
        "default_model": "claude-haiku-4-5-20251001",
        "models": ["claude-haiku-4-5-20251001"],   # extend later
    },
    # "gemini": {...}  # added in a future task
}


def _log(msg):
    """Guarded — pythonw.exe sets stdout to None."""
    try:
        if sys.stdout is not None:
            print(f"[cls_ai] {msg}")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

def get_available_providers():
    """Providers whose env_var is set and non-empty: [{key, label, models}]."""
    out = []
    for key, p in PROVIDER_REGISTRY.items():
        if (os.environ.get(p["env_var"]) or "").strip():
            out.append({"key": key, "label": p["label"],
                        "models": list(p["models"]),
                        "default_model": p["default_model"]})
    return out


def _stored_config(conn):
    raw = cls_db.get_app_setting(conn, AI_CONFIG_KEY)
    if not raw:
        return {}
    try:
        cfg = json.loads(raw)
        return cfg if isinstance(cfg, dict) else {}
    except ValueError:
        return {}


def get_ai_provider_config(conn):
    """
    {"provider": key|None, "model": str|None, "daily_caps": {...},
     "configured": bool}. Falls back to the first available provider if
    nothing is stored (or the stored provider lost its key); provider is
    None with configured=False when no provider has a key at all.
    """
    stored = _stored_config(conn)
    caps = dict(DEFAULT_DAILY_CAPS)
    if isinstance(stored.get("daily_caps"), dict):
        caps.update(stored["daily_caps"])

    available = {p["key"]: p for p in get_available_providers()}
    provider = stored.get("provider")
    model = stored.get("model")
    if provider not in available:
        if not available:
            return {"provider": None, "model": None,
                    "daily_caps": caps, "configured": False}
        provider = next(iter(available))
        model = None
    if model not in available[provider]["models"]:
        model = available[provider]["default_model"]
    return {"provider": provider, "model": model,
            "daily_caps": caps, "configured": True}


def set_ai_provider_config(conn, provider_key, model):
    """Validate-before-write; preserves any stored daily_caps."""
    available = {p["key"]: p for p in get_available_providers()}
    if provider_key not in available:
        raise ValueError("That provider is not available (no API key set).")
    if model not in available[provider_key]["models"]:
        raise ValueError("That model is not offered by the chosen provider.")
    stored = _stored_config(conn)
    stored["provider"] = provider_key
    stored["model"] = model
    cls_db.set_app_setting(conn, AI_CONFIG_KEY, json.dumps(stored))


def build_suggestion_key(cls_id, latest_activity_id, stage, total_score):
    """Deterministic cache fingerprint (event_id doctrine)."""
    raw = f"{cls_id}:{latest_activity_id}:{stage}:{total_score}:{PROMPT_VERSION}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────
# PROVIDERS
# ─────────────────────────────────────────────────────────────

def _call_anthropic(prompt, model, api_key):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key,
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": 400,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=LLM_TIMEOUT_SECONDS,
    )
    if r.status_code != 200:
        # status code only — never echo headers/body that could carry the key
        return {"ok": False, "text": None, "error": f"Provider returned HTTP {r.status_code}",
                "tokens_in": None, "tokens_out": None}
    data = r.json()
    text = "".join(b.get("text", "") for b in data.get("content", [])
                   if b.get("type") == "text").strip()
    usage = data.get("usage") or {}
    if not text:
        return {"ok": False, "text": None, "error": "Empty response from provider",
                "tokens_in": usage.get("input_tokens"), "tokens_out": usage.get("output_tokens")}
    return {"ok": True, "text": text, "error": None,
            "tokens_in": usage.get("input_tokens"), "tokens_out": usage.get("output_tokens")}


_PROVIDER_CALLERS = {"anthropic": _call_anthropic}


def call_llm(prompt, purpose, conn):
    """
    Always returns {"ok", "text", "error", "tokens_in", "tokens_out"} —
    never raises. Also adds "provider"/"model" (None if not resolved).
    """
    result = {"ok": False, "text": None, "error": None,
              "tokens_in": None, "tokens_out": None,
              "provider": None, "model": None}
    try:
        cfg = get_ai_provider_config(conn)
        if not cfg["configured"]:
            result["error"] = "No AI provider configured"
            return result
        provider, model = cfg["provider"], cfg["model"]
        result["provider"], result["model"] = provider, model

        cap = cfg["daily_caps"].get(purpose, FALLBACK_DAILY_CAP)
        if cls_db.count_ai_suggestions_today(conn, purpose) >= cap:
            result["error"] = "Daily AI call limit reached"
            return result

        api_key = (os.environ.get(PROVIDER_REGISTRY[provider]["env_var"]) or "").strip()
        caller = _PROVIDER_CALLERS.get(provider)
        if not api_key or caller is None:
            result["error"] = "AI provider not available"
            return result

        out = caller(prompt, model, api_key)
        result.update(out)
        return result
    except requests.exceptions.Timeout:
        result["error"] = "AI provider timed out"
    except Exception as e:
        # Type name only: exception text from HTTP libs can embed request details.
        result["error"] = f"AI call failed ({type(e).__name__})"
        _log(result["error"])
    return result
