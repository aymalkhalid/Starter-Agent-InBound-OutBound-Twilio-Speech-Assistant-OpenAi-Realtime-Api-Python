"""
Dynamic settings: load runtime-safe overrides from Supabase and apply to Config.

Dashboard Settings can change transcription, voice, tone, VAD, booking, transfer,
and similar knobs without editing .env. Main prompt content and industry behavior
stay prompt-as-code in prompts/main_system_instructions.md. See docs/CONFIGURATION.md.
"""
from __future__ import annotations

import json
import os
from typing import Any

from config import (
    Config,
    _normalize_accent_strength,
    _normalize_expressiveness,
    _normalize_language_switch_policy,
    _normalize_pacing,
    _normalize_realtime_voice,
    _normalize_warmth,
    _sanitize_prompt_control,
)
from voice_realtime.models import normalize_reasoning_effort, validate_realtime_model
from voice_realtime.settings import normalize_vad_eagerness, normalize_vad_mode, normalize_voice_profile
from services.log_utils import Log
from services.timezone_utils import normalize_timezone_name

GROUPED_REALTIME_SETTINGS_KEY = "REALTIME_VOICE_SETTINGS"
GROUPED_REALTIME_SETTING_KEYS = frozenset(
    {
        "OPENAI_REALTIME_MODEL",
        "VOICE",
        "VOICE_PROFILE",
        "REALTIME_REASONING_EFFORT",
        "VAD_MODE",
        "VAD_EAGERNESS",
        "VAD_THRESHOLD",
        "VAD_SILENCE_DURATION_MS",
        "VAD_PREFIX_PADDING_MS",
        "ASSISTANT_TONE",
        "ASSISTANT_WARMTH",
        "ASSISTANT_EXPRESSIVENESS",
        "ASSISTANT_PACING",
        "ASSISTANT_LANGUAGE",
        "ASSISTANT_ACCENT",
        "ASSISTANT_ACCENT_STRENGTH",
        "LANGUAGE_SWITCH_POLICY",
    }
)

# Runtime-safe keys the dashboard can override. Value type: "str" | "bool" | "int" | "float"
# Do not add full prompt bodies, prompt-profile ids, or industry templates here.
# Only used when CALL_RECORD_BACKEND=supabase and SUPABASE_URL/SUPABASE_KEY are set.
OVERRIDABLE_KEYS: dict[str, str] = {
    "TRANSCRIPTION_MODEL": "str",
    "TRANSCRIPT_ENHANCEMENT_ENABLED": "bool",
    "CALL_RECORDING_ENABLED": "bool",
    "VOICE": "str",
    "VOICE_PROFILE": "str",
    "ASSISTANT_TONE": "str",
    "ASSISTANT_WARMTH": "str",
    "ASSISTANT_EXPRESSIVENESS": "str",
    "ASSISTANT_PACING": "str",
    "ASSISTANT_LANGUAGE": "str",
    "ASSISTANT_ACCENT": "str",
    "ASSISTANT_ACCENT_STRENGTH": "str",
    "LANGUAGE_SWITCH_POLICY": "str",
    "TEMPERATURE": "float",
    "COMPANY_NAME": "str",
    "AGENT_NAME": "str",
    "BOOKING_ENABLED": "bool",
    "BOOKING_SLOT_DURATION_MINUTES": "int",
    "BUSINESS_APPOINTMENT_OPENING_TIME": "str",
    "BUSINESS_APPOINTMENT_CLOSING_TIME": "str",
    "AVAILABILITY_MAX_SLOTS_PER_BUCKET_PER_DAY": "int",
    "BOOKING_DAYS_ENABLED": "str",
    "VAD_THRESHOLD": "float",
    "VAD_SILENCE_DURATION_MS": "int",
    "VAD_PREFIX_PADDING_MS": "int",
    "VAD_DEBOUNCE_AFTER_OUTGOING_MS": "int",
    "VAD_INTERRUPTION_CONFIRM_MS": "int",
    "VAD_MODE": "str",
    "VAD_EAGERNESS": "str",
    "HUMAN_TRANSFER_ENABLED": "bool",
    "HUMAN_TRANSFER_DIAL_NUMBER": "str",
    # Realtime / transcript models. OPENAI_REALTIME_MODEL must be registered unless explicitly allowed.
    "OPENAI_REALTIME_MODEL": "str",
    "REALTIME_REASONING_EFFORT": "str",
    "TRANSCRIPT_ENHANCEMENT_MODEL": "str",
    # Google Calendar booking (e.g. primary or @group.calendar.google.com)
    "GOOGLE_CALENDAR_ID": "str",
    "TIMEZONE": "str",
}


def _parse_value(key: str, raw: str) -> Any:
    t = OVERRIDABLE_KEYS.get(key, "str")
    s = (raw or "").strip()
    if t == "bool":
        return s.lower() in ("1", "true", "yes")
    if t == "int":
        try:
            return int(s) if s else 0
        except ValueError:
            return 0
    if t == "float":
        try:
            return float(s) if s else 0.0
        except ValueError:
            return 0.0
    return s


def _normalize_override_for_storage(key: str, value: Any) -> Any:
    """Normalize settings before persistence so app_settings never stores invalid voice/model controls."""
    if key == "OPENAI_REALTIME_MODEL":
        return validate_realtime_model(
            str(value or "").strip(),
            allow_unregistered=bool(getattr(Config, "ALLOW_UNREGISTERED_REALTIME_MODELS", False)),
        )
    if key == "REALTIME_REASONING_EFFORT":
        return normalize_reasoning_effort(str(value or "low"))
    if key == "VOICE":
        return _normalize_realtime_voice(str(value or ""))
    if key == "VOICE_PROFILE":
        return normalize_voice_profile(str(value or "custom"))
    if key == "VAD_MODE":
        return normalize_vad_mode(str(value or "server_vad"))
    if key == "VAD_EAGERNESS":
        return normalize_vad_eagerness(str(value or "auto"))
    return value


def _stringify_setting_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_grouped_realtime_settings(raw: Any) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError):
        Log.error(f"Dynamic settings: invalid {GROUPED_REALTIME_SETTINGS_KEY} JSON")
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in parsed.items():
        if key in GROUPED_REALTIME_SETTING_KEYS and key in OVERRIDABLE_KEYS:
            out[key] = _stringify_setting_value(value)
    return out


def _settings_rows_to_overrides(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Convert Supabase app_settings rows into flat overrides.

    Realtime voice/model settings are accepted only from the grouped JSON row.
    Other operational settings remain simple per-key rows.
    """
    flat: dict[str, str] = {}
    grouped_raw: Any = None
    for row in rows:
        key = row.get("key")
        value = row.get("value") or ""
        if key == GROUPED_REALTIME_SETTINGS_KEY:
            grouped_raw = value
        elif key in OVERRIDABLE_KEYS and key not in GROUPED_REALTIME_SETTING_KEYS:
            flat[key] = _stringify_setting_value(value)
    flat.update(_parse_grouped_realtime_settings(grouped_raw))
    return flat


def load_overrides_sync() -> dict[str, str]:
    """Load key-value overrides from Supabase app_settings table. Returns {} if not configured or on error."""
    if (Config.CALL_RECORD_BACKEND or "").strip().lower() != "supabase":
        return {}
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        return {}
    try:
        from supabase import create_client
        client = create_client(Config.SUPABASE_URL.strip(), Config.SUPABASE_KEY.strip())
        # Use a small table name; typically in the same DB as call records
        r = client.table("app_settings").select("key, value").execute()
        rows = getattr(r, "data", None) or []
        return _settings_rows_to_overrides(rows)
    except Exception as e:
        Log.error(f"Dynamic settings load error: {e}")
        return {}


def _load_existing_grouped_realtime_settings(client: Any) -> dict[str, Any]:
    try:
        r = client.table("app_settings").select("key, value").execute()
        rows = getattr(r, "data", None) or []
        for row in rows:
            if row.get("key") == GROUPED_REALTIME_SETTINGS_KEY:
                parsed = _parse_grouped_realtime_settings(row.get("value") or "")
                return {key: _parse_value(key, value) for key, value in parsed.items()}
    except Exception as e:
        Log.error(f"Dynamic settings grouped load error: {e}")
    return {}


def save_overrides_sync(updates: dict[str, Any]) -> bool:
    """Upsert overrides into Supabase app_settings. Only keys in OVERRIDABLE_KEYS are written. Returns True on success."""
    if (Config.CALL_RECORD_BACKEND or "").strip().lower() != "supabase":
        return False
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        return False
    try:
        allowed = {
            k: _normalize_override_for_storage(k, v)
            for k, v in updates.items()
            if k in OVERRIDABLE_KEYS
        }
        if not allowed:
            return True
        from supabase import create_client
        client = create_client(Config.SUPABASE_URL.strip(), Config.SUPABASE_KEY.strip())
        grouped_updates = {
            key: val
            for key, val in allowed.items()
            if key in GROUPED_REALTIME_SETTING_KEYS
        }
        if grouped_updates:
            grouped_payload = _load_existing_grouped_realtime_settings(client)
            grouped_payload.update(grouped_updates)
            client.table("app_settings").upsert(
                {
                    "key": GROUPED_REALTIME_SETTINGS_KEY,
                    "value": json.dumps(grouped_payload, sort_keys=True),
                },
                on_conflict="key",
            ).execute()
        for key, val in allowed.items():
            if key in GROUPED_REALTIME_SETTING_KEYS:
                continue
            client.table("app_settings").upsert({"key": key, "value": str(val)}, on_conflict="key").execute()
        return True
    except Exception as e:
        Log.error(f"Dynamic settings save error: {e}")
        return False


def apply_overrides_to_config(overrides: dict[str, str]) -> None:
    """Apply loaded overrides to Config and rebuild system message if company/agent profile changed."""
    if not overrides:
        return
    prompt_needs_rebuild = False
    for key, raw in overrides.items():
        if key not in OVERRIDABLE_KEYS:
            continue
        try:
            val = _parse_value(key, raw)
            if key == "TRANSCRIPTION_MODEL":
                Config.TRANSCRIPTION_MODEL = (val or "tiny").strip().lower() if isinstance(val, str) else getattr(Config, "TRANSCRIPTION_MODEL", "tiny")
            elif key == "TRANSCRIPT_ENHANCEMENT_ENABLED":
                Config.TRANSCRIPT_ENHANCEMENT_ENABLED = bool(val)
            elif key == "CALL_RECORDING_ENABLED":
                Config.CALL_RECORDING_ENABLED = bool(val)
            elif key == "VOICE":
                Config.VOICE = _normalize_realtime_voice(val if isinstance(val, str) else None)
            elif key == "VOICE_PROFILE":
                Config.VOICE_PROFILE = normalize_voice_profile(val if isinstance(val, str) else None)
            elif key == "ASSISTANT_TONE":
                Config.ASSISTANT_TONE = _sanitize_prompt_control(val if isinstance(val, str) else None, "warm professional", 80)
                prompt_needs_rebuild = True
            elif key == "ASSISTANT_WARMTH":
                Config.ASSISTANT_WARMTH = _normalize_warmth(val if isinstance(val, str) else None)
                prompt_needs_rebuild = True
            elif key == "ASSISTANT_EXPRESSIVENESS":
                Config.ASSISTANT_EXPRESSIVENESS = _normalize_expressiveness(val if isinstance(val, str) else None)
                prompt_needs_rebuild = True
            elif key == "ASSISTANT_PACING":
                Config.ASSISTANT_PACING = _normalize_pacing(val if isinstance(val, str) else None)
                prompt_needs_rebuild = True
            elif key == "ASSISTANT_LANGUAGE":
                Config.ASSISTANT_LANGUAGE = _sanitize_prompt_control(val if isinstance(val, str) else None, "English", 48)
                prompt_needs_rebuild = True
            elif key == "ASSISTANT_ACCENT":
                Config.ASSISTANT_ACCENT = _sanitize_prompt_control(val if isinstance(val, str) else None, "neutral American", 64)
                prompt_needs_rebuild = True
            elif key == "ASSISTANT_ACCENT_STRENGTH":
                Config.ASSISTANT_ACCENT_STRENGTH = _normalize_accent_strength(val if isinstance(val, str) else None)
                prompt_needs_rebuild = True
            elif key == "LANGUAGE_SWITCH_POLICY":
                Config.LANGUAGE_SWITCH_POLICY = _normalize_language_switch_policy(val if isinstance(val, str) else None)
                prompt_needs_rebuild = True
            elif key == "TEMPERATURE":
                Config.TEMPERATURE = float(val) if isinstance(val, (int, float)) else Config.TEMPERATURE
            elif key == "COMPANY_NAME":
                Config.COMPANY_NAME = (val or "").strip() or Config.COMPANY_NAME
                prompt_needs_rebuild = True
            elif key == "AGENT_NAME":
                Config.AGENT_NAME = (val or "").strip()
                prompt_needs_rebuild = True
            elif key == "BOOKING_ENABLED":
                Config.BOOKING_ENABLED = bool(val)
                prompt_needs_rebuild = True
            elif key == "TIMEZONE":
                tz_name = normalize_timezone_name(val if isinstance(val, str) else None)
                if tz_name:
                    Config.TIMEZONE = tz_name
            elif key == "BOOKING_SLOT_DURATION_MINUTES":
                setattr(Config, "BOOKING_SLOT_DURATION_MINUTES", max(1, int(val)) if isinstance(val, (int, float)) else 60)
            elif key == "BUSINESS_APPOINTMENT_OPENING_TIME":
                setattr(Config, "BUSINESS_APPOINTMENT_OPENING_TIME", (val or "08:00").strip() if isinstance(val, str) else "08:00")
            elif key == "BUSINESS_APPOINTMENT_CLOSING_TIME":
                setattr(Config, "BUSINESS_APPOINTMENT_CLOSING_TIME", (val or "18:00").strip() if isinstance(val, str) else "18:00")
            elif key == "AVAILABILITY_MAX_SLOTS_PER_BUCKET_PER_DAY":
                setattr(Config, "AVAILABILITY_MAX_SLOTS_PER_BUCKET_PER_DAY", int(val) if isinstance(val, (int, float)) else 4)
            elif key == "BOOKING_DAYS_ENABLED":
                setattr(Config, "BOOKING_DAYS_ENABLED", (val or "").strip() if isinstance(val, str) else "")
            elif key == "VAD_THRESHOLD":
                Config.VAD_THRESHOLD = float(val) if isinstance(val, (int, float)) else Config.VAD_THRESHOLD
            elif key == "VAD_SILENCE_DURATION_MS":
                Config.VAD_SILENCE_DURATION_MS = int(val) if isinstance(val, (int, float)) else Config.VAD_SILENCE_DURATION_MS
            elif key == "VAD_PREFIX_PADDING_MS":
                Config.VAD_PREFIX_PADDING_MS = int(val) if isinstance(val, (int, float)) else Config.VAD_PREFIX_PADDING_MS
            elif key == "VAD_DEBOUNCE_AFTER_OUTGOING_MS":
                Config.VAD_DEBOUNCE_AFTER_OUTGOING_MS = int(val) if isinstance(val, (int, float)) else Config.VAD_DEBOUNCE_AFTER_OUTGOING_MS
            elif key == "VAD_INTERRUPTION_CONFIRM_MS":
                Config.VAD_INTERRUPTION_CONFIRM_MS = int(val) if isinstance(val, (int, float)) else Config.VAD_INTERRUPTION_CONFIRM_MS
            elif key == "VAD_MODE":
                Config.VAD_MODE = normalize_vad_mode(val if isinstance(val, str) else None)
            elif key == "VAD_EAGERNESS":
                Config.VAD_EAGERNESS = normalize_vad_eagerness(val if isinstance(val, str) else None)
            elif key == "HUMAN_TRANSFER_ENABLED":
                Config.HUMAN_TRANSFER_ENABLED = bool(val)
            elif key == "HUMAN_TRANSFER_DIAL_NUMBER":
                Config.HUMAN_TRANSFER_DIAL_NUMBER = (val or "").strip() or getattr(Config, "HUMAN_TRANSFER_DIAL_NUMBER", "+15551234567")
            elif key == "OPENAI_REALTIME_MODEL":
                Config.OPENAI_REALTIME_MODEL = validate_realtime_model(
                    val if isinstance(val, str) else Config.OPENAI_REALTIME_MODEL,
                    allow_unregistered=bool(getattr(Config, "ALLOW_UNREGISTERED_REALTIME_MODELS", False)),
                )
                prompt_needs_rebuild = True
            elif key == "REALTIME_REASONING_EFFORT":
                Config.REALTIME_REASONING_EFFORT = normalize_reasoning_effort(val if isinstance(val, str) else "low")
                prompt_needs_rebuild = True
            elif key == "TRANSCRIPT_ENHANCEMENT_MODEL":
                Config.TRANSCRIPT_ENHANCEMENT_MODEL = (val or "gpt-4o-mini").strip() if isinstance(val, str) else Config.TRANSCRIPT_ENHANCEMENT_MODEL
            elif key == "GOOGLE_CALENDAR_ID":
                os.environ["GOOGLE_CALENDAR_ID"] = (val or "").strip() if isinstance(val, str) else os.environ.get("GOOGLE_CALENDAR_ID", "")
        except Exception as e:
            Log.error(f"Dynamic settings apply {key}: {e}")
    if prompt_needs_rebuild:
        _rebuild_system_message()
    # Sync to os.environ so prompt and booking helpers see overrides
    for key in (
        "AGENT_NAME",
        "COMPANY_NAME",
        "BOOKING_ENABLED",
        "ASSISTANT_TONE",
        "ASSISTANT_WARMTH",
        "ASSISTANT_EXPRESSIVENESS",
        "ASSISTANT_PACING",
        "ASSISTANT_LANGUAGE",
        "ASSISTANT_ACCENT",
        "ASSISTANT_ACCENT_STRENGTH",
        "LANGUAGE_SWITCH_POLICY",
        "TIMEZONE",
        "BOOKING_SLOT_DURATION_MINUTES",
        "BUSINESS_APPOINTMENT_OPENING_TIME",
        "BUSINESS_APPOINTMENT_CLOSING_TIME",
        "AVAILABILITY_MAX_SLOTS_PER_BUCKET_PER_DAY",
        "BOOKING_DAYS_ENABLED",
        "OPENAI_REALTIME_MODEL",
        "REALTIME_REASONING_EFFORT",
        "VOICE",
        "VOICE_PROFILE",
        "VAD_MODE",
        "VAD_EAGERNESS",
    ):
        if key in overrides:
            val = getattr(Config, key, None)
            if val is not None:
                os.environ[key] = str(val)


def _rebuild_system_message() -> None:
    """Rebuild Config.SYSTEM_MESSAGE from the main system-instructions file."""
    try:
        from config import rebuild_system_message
        rebuild_system_message()
    except Exception as e:
        Log.error(f"Rebuild system message: {e}")


def get_effective_settings() -> dict[str, Any]:
    """Return current effective value for each overridable key (from Config / os.environ). For GET /settings."""
    out: dict[str, Any] = {}
    for key in OVERRIDABLE_KEYS:
        if key == "BOOKING_SLOT_DURATION_MINUTES":
            out[key] = getattr(Config, "BOOKING_SLOT_DURATION_MINUTES", 60)
        elif key == "BUSINESS_APPOINTMENT_OPENING_TIME":
            out[key] = getattr(Config, "BUSINESS_APPOINTMENT_OPENING_TIME", "08:00")
        elif key == "BUSINESS_APPOINTMENT_CLOSING_TIME":
            out[key] = getattr(Config, "BUSINESS_APPOINTMENT_CLOSING_TIME", "18:00")
        elif key == "AVAILABILITY_MAX_SLOTS_PER_BUCKET_PER_DAY":
            out[key] = getattr(Config, "AVAILABILITY_MAX_SLOTS_PER_BUCKET_PER_DAY", 4)
        elif key == "BOOKING_DAYS_ENABLED":
            out[key] = getattr(Config, "BOOKING_DAYS_ENABLED", "") or ""
        elif key == "GOOGLE_CALENDAR_ID":
            out[key] = os.environ.get("GOOGLE_CALENDAR_ID", "") or ""
        elif key == "TIMEZONE":
            out[key] = getattr(Config, "TIMEZONE", "America/Los_Angeles") or "America/Los_Angeles"
        else:
            out[key] = getattr(Config, key, None)
    return out


def get_effective_settings_with_sources(overrides: dict[str, str] | None = None) -> dict[str, Any]:
    """Return effective settings with source metadata for dashboard diagnostics."""
    active_overrides = overrides if overrides is not None else load_overrides_sync()
    values = get_effective_settings()
    settings: dict[str, dict[str, Any]] = {}
    for key in OVERRIDABLE_KEYS:
        if key in active_overrides:
            source = "supabase"
        elif os.environ.get(key) not in (None, ""):
            source = "env"
        else:
            source = "default"
        settings[key] = {
            "value": values.get(key),
            "source": source,
        }
    return {
        "precedence": ["temporary_session_overrides", "supabase_app_settings", "env", "defaults"],
        "settings": settings,
        "grouped_realtime_settings_key": GROUPED_REALTIME_SETTINGS_KEY,
        "grouped_realtime_setting_keys": sorted(GROUPED_REALTIME_SETTING_KEYS),
    }
