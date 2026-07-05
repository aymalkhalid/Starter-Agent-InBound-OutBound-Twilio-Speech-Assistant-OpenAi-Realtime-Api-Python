"""
Outbound campaign service: Supabase CRUD for campaigns and contacts,
campaign type config loading, and system message builder for outbound calls.

Mirrors the patterns in webhook_service.py — sync Supabase functions
called via asyncio.to_thread() from async route handlers.
"""
import os
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from config import Config, _build_accent_instruction, _build_delivery_instruction, _build_language_instruction
from services.log_utils import Log

from services.outbound_campaign_types import DEFAULT_CAMPAIGN_TYPES

# ---------------------------------------------------------------------------
# Campaign type config
# ---------------------------------------------------------------------------

_campaign_types_cache: dict[str, Any] | None = None


def get_campaign_types() -> dict[str, Any]:
    """Return built-in campaign type definitions. Cached after first load."""
    global _campaign_types_cache
    if _campaign_types_cache is None:
        _campaign_types_cache = dict(DEFAULT_CAMPAIGN_TYPES)
    return _campaign_types_cache



def get_campaign_type_config(campaign_type: str) -> dict[str, Any]:
    """Return config dict for a specific campaign type, or empty dict if not found."""
    return get_campaign_types().get(campaign_type, {})


def resolve_campaign_type_default_script(campaign_type: str) -> str:
    """Return the script the dashboard should prefill for a campaign type.

    Mirrors the runtime fallback used when message_template is blank:
    inline default_script, then system_instructions_path, then Config.SYSTEM_MESSAGE.
    """
    type_cfg = get_campaign_type_config(campaign_type)
    template = (type_cfg.get("default_script") or "").strip()
    if not template and (type_cfg.get("system_instructions_path") or "").strip():
        template = _render_campaign_system_instructions(type_cfg["system_instructions_path"]).strip()
    if not template:
        template = (getattr(Config, "SYSTEM_MESSAGE", "") or "").strip()
    return template


def get_campaign_types_for_dashboard() -> dict[str, Any]:
    """Campaign type presets with resolved default_script text for dashboard prefill."""
    types = get_campaign_types()
    enriched: dict[str, Any] = {}
    for key, cfg in types.items():
        item = dict(cfg)
        item["default_script"] = resolve_campaign_type_default_script(key)
        enriched[key] = item
    return enriched


def _append_language_and_accent_policy(prompt: str) -> str:
    """Append global Realtime delivery/language/accent policy to outbound prompts."""
    sections = [prompt.rstrip()]
    if "# Delivery Style" not in prompt:
        sections.append(
            _build_delivery_instruction(
                getattr(Config, "ASSISTANT_TONE", "warm professional"),
                getattr(Config, "ASSISTANT_WARMTH", "warm"),
                getattr(Config, "ASSISTANT_EXPRESSIVENESS", "balanced"),
                getattr(Config, "ASSISTANT_PACING", "moderate"),
            ).strip()
        )
    if "# Language" not in prompt:
        sections.append(
            _build_language_instruction(
                getattr(Config, "ASSISTANT_LANGUAGE", "English"),
                getattr(Config, "LANGUAGE_SWITCH_POLICY", "explicit_or_substantive"),
            ).strip()
        )
    if "# Accent" not in prompt:
        sections.append(
            _build_accent_instruction(
                getattr(Config, "ASSISTANT_LANGUAGE", "English"),
                getattr(Config, "ASSISTANT_ACCENT", "neutral American"),
                getattr(Config, "ASSISTANT_ACCENT_STRENGTH", "light"),
            ).strip()
        )
    return "\n\n".join(section for section in sections if section)


def _clean_prompt_value(value: Any, *, max_length: int = 500) -> str:
    """Return a compact one-line value suitable for prompt context."""
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (str, int, float)):
        text = str(value)
    else:
        return ""
    text = " ".join(text.split()).strip()
    if len(text) > max_length:
        return text[: max_length - 3].rstrip() + "..."
    return text


def _normalized_field_key(value: Any) -> str:
    """Normalize custom-field keys from CSVs/forms for alias matching."""
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _first_custom_field(custom_fields: dict[str, Any], aliases: tuple[str, ...]) -> str:
    alias_keys = {_normalized_field_key(alias) for alias in aliases}
    for key, value in custom_fields.items():
        if _normalized_field_key(key) in alias_keys:
            cleaned = _clean_prompt_value(value)
            if cleaned:
                return cleaned
    return ""


def get_contact_timezone_from_contact(contact: dict[str, Any] | None) -> str:
    """Return lead-provided contact timezone without falling back to business timezone."""
    if not isinstance(contact, dict):
        return ""
    top_level = _first_custom_field(contact, ("contact_timezone", "timezone", "time_zone", "tz"))
    if top_level:
        return top_level
    custom_fields = contact.get("custom_fields") or {}
    if not isinstance(custom_fields, dict):
        custom_fields = {}
    return _first_custom_field(custom_fields, ("contact_timezone", "timezone", "time_zone", "tz"))


def _split_contact_name(name: str) -> tuple[str, str]:
    parts = [part for part in (name or "").split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


_LEAD_NAME_ALIASES = ("name", "contact_name", "full_name", "fullname", "lead_name")
_LEAD_FIRST_NAME_ALIASES = ("first_name", "firstname", "contact_first_name", "first")
_LEAD_LAST_NAME_ALIASES = ("last_name", "lastname", "contact_last_name", "last")
_LEAD_PHONE_ALIASES = (
    "phone",
    "contact_phone",
    "phone_number",
    "phonenumber",
    "mobile",
    "mobile_phone",
    "cell",
    "user_number",
)
_LEAD_EMAIL_ALIASES = ("email", "contact_email", "email_address", "emailaddress")
_LEAD_OFFER_ALIASES = (
    "lead_offer",
    "latest_optin",
    "latest_opt_in",
    "contact_latest_optin",
    "contact_latest_opt_in",
    "offer",
    "optin",
    "opt_in",
    "facebook_offer",
    "fb_offer",
    "requested_offer",
    "latest offer",
    "latest opt-in",
)
_LEAD_TIMEZONE_ALIASES = ("contact_timezone", "timezone", "time_zone", "tz")
_LEAD_CALLBACK_ALIASES = (
    "callback_number",
    "clinic_phone",
    "front_desk_phone",
    "frontdesk_phone",
    "office_phone",
    "business_phone",
)
_LEAD_SOURCE_ALIASES = ("source_campaign", "campaign", "campaign_name", "source")
_LEAD_ENTITY_CONTAINER_ALIASES = ("contact", "lead", "data", "payload")
_LEAD_CUSTOM_FIELD_CONTAINER_ALIASES = (
    "custom_fields",
    "customfields",
    "custom_data",
    "customdata",
    "custom",
    "fields",
    "extra",
)
_LEAD_AUTH_FIELD_ALIASES = ("key", "dashboard_key", "dashboardkey", "x_dashboard_key", "authorization")


def _coerce_mapping(value: Any) -> dict[str, Any]:
    """Return a plain dict from a JSON object or JSON-object string."""
    if isinstance(value, dict):
        return {str(k).strip(): v for k, v in value.items() if str(k).strip()}
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return {str(k).strip(): v for k, v in parsed.items() if str(k).strip()}
    return {}


def _lead_payload_entity_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return top-level and common nested lead/contact objects from an API payload."""
    root = _coerce_mapping(payload)
    if not root:
        return []

    entity_keys = {_normalized_field_key(alias) for alias in _LEAD_ENTITY_CONTAINER_ALIASES}
    sources = [root]
    for source in list(sources):
        for key, value in source.items():
            if _normalized_field_key(key) in entity_keys:
                nested = _coerce_mapping(value)
                if nested:
                    sources.append(nested)
    return sources


def _lead_payload_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return entity sources plus explicit custom-field maps for alias matching."""
    entity_sources = _lead_payload_entity_sources(payload)
    custom_container_keys = {
        _normalized_field_key(alias) for alias in _LEAD_CUSTOM_FIELD_CONTAINER_ALIASES
    }
    sources = list(entity_sources)
    for source in entity_sources:
        for key, value in source.items():
            if _normalized_field_key(key) in custom_container_keys:
                custom = _coerce_mapping(value)
                if custom:
                    sources.append(custom)
    return sources


def _first_lead_payload_field(payload: dict[str, Any], aliases: tuple[str, ...]) -> str:
    """Find the first non-empty lead field across top-level, nested, and custom maps."""
    alias_keys = {_normalized_field_key(alias) for alias in aliases}
    for source in _lead_payload_sources(payload):
        for key, value in source.items():
            if _normalized_field_key(key) in alias_keys:
                cleaned = _clean_prompt_value(value)
                if cleaned:
                    return cleaned
    return ""


def build_contact_from_lead_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize one external lead webhook payload into an outbound contact row.

    This accepts direct JSON from tools such as GHL, n8n, Zapier, or Insomnia.
    Common aliases are converted into the starter's canonical contact fields and
    appointment-setter custom fields.
    """
    if not isinstance(payload, dict):
        return {"name": "", "phone": "", "email": "", "custom_fields": {}}

    name = _first_lead_payload_field(payload, _LEAD_NAME_ALIASES)
    first_name = _first_lead_payload_field(payload, _LEAD_FIRST_NAME_ALIASES)
    last_name = _first_lead_payload_field(payload, _LEAD_LAST_NAME_ALIASES)
    if not name:
        name = " ".join(part for part in (first_name, last_name) if part).strip()
    if name and (not first_name or not last_name):
        split_first, split_last = _split_contact_name(name)
        first_name = first_name or split_first
        last_name = last_name or split_last

    phone = _first_lead_payload_field(payload, _LEAD_PHONE_ALIASES)
    email = _first_lead_payload_field(payload, _LEAD_EMAIL_ALIASES)
    lead_offer = _first_lead_payload_field(payload, _LEAD_OFFER_ALIASES)
    contact_timezone = _first_lead_payload_field(payload, _LEAD_TIMEZONE_ALIASES)
    callback_number = _first_lead_payload_field(payload, _LEAD_CALLBACK_ALIASES)
    source_campaign = _first_lead_payload_field(payload, _LEAD_SOURCE_ALIASES)

    custom_fields: dict[str, Any] = {}
    entity_sources = _lead_payload_entity_sources(payload)
    custom_container_keys = {
        _normalized_field_key(alias) for alias in _LEAD_CUSTOM_FIELD_CONTAINER_ALIASES
    }
    for source in entity_sources:
        for key, value in source.items():
            if _normalized_field_key(key) in custom_container_keys:
                custom_fields.update(_coerce_mapping(value))

    reserved_keys = {
        _normalized_field_key(alias)
        for alias in (
            _LEAD_NAME_ALIASES
            + _LEAD_FIRST_NAME_ALIASES
            + _LEAD_LAST_NAME_ALIASES
            + _LEAD_PHONE_ALIASES
            + _LEAD_EMAIL_ALIASES
            + _LEAD_OFFER_ALIASES
            + _LEAD_TIMEZONE_ALIASES
            + _LEAD_CALLBACK_ALIASES
            + _LEAD_SOURCE_ALIASES
            + _LEAD_ENTITY_CONTAINER_ALIASES
            + _LEAD_CUSTOM_FIELD_CONTAINER_ALIASES
            + _LEAD_AUTH_FIELD_ALIASES
        )
    }
    for source in entity_sources:
        for key, value in source.items():
            normalized_key = _normalized_field_key(key)
            if normalized_key in reserved_keys or isinstance(value, (dict, list, tuple, set)):
                continue
            if _clean_prompt_value(value):
                custom_fields.setdefault(str(key).strip(), value)

    if first_name:
        custom_fields["contact_first_name"] = first_name
    if last_name:
        custom_fields["contact_last_name"] = last_name
    if lead_offer:
        custom_fields["lead_offer"] = lead_offer
        custom_fields.setdefault("contact_latest_optin", lead_offer)
    if contact_timezone:
        custom_fields["contact_timezone"] = contact_timezone
    if callback_number:
        custom_fields["callback_number"] = callback_number
    if source_campaign:
        custom_fields["source_campaign"] = source_campaign
        custom_fields.setdefault("source", source_campaign)

    return {
        "name": name,
        "phone": phone,
        "email": email,
        "custom_fields": custom_fields,
    }


def _build_outbound_lead_context(
    *,
    campaign: dict[str, Any],
    contact: dict[str, Any],
    custom_fields: dict[str, Any],
) -> dict[str, str]:
    """Normalize outbound lead fields used by reusable prompts and templates."""
    raw_name = _clean_prompt_value(contact.get("name"))
    custom_name = _first_custom_field(
        custom_fields,
        ("contact_name", "full_name", "name", "lead_name"),
    )
    contact_name = raw_name or custom_name
    first_name = _first_custom_field(
        custom_fields,
        ("contact_first_name", "first_name", "firstname", "first"),
    )
    last_name = _first_custom_field(
        custom_fields,
        ("contact_last_name", "last_name", "lastname", "last"),
    )
    if contact_name and (not first_name or not last_name):
        split_first, split_last = _split_contact_name(contact_name)
        first_name = first_name or split_first
        last_name = last_name or split_last

    lead_offer = _first_custom_field(
        custom_fields,
        (
            "lead_offer",
            "latest_optin",
            "latest_opt_in",
            "contact_latest_optin",
            "contact_latest_opt_in",
            "offer",
            "optin",
            "opt_in",
            "facebook_offer",
            "fb_offer",
            "requested_offer",
            "latest offer",
            "latest opt-in",
        ),
    )
    contact_timezone = _first_custom_field(
        custom_fields,
        ("contact_timezone", "timezone", "time_zone", "tz"),
    )
    callback_number = _first_custom_field(
        custom_fields,
        (
            "callback_number",
            "clinic_phone",
            "front_desk_phone",
            "frontdesk_phone",
            "office_phone",
            "business_phone",
        ),
    ) or _clean_prompt_value(os.getenv("HUMAN_TRANSFER_DIAL_NUMBER", ""))
    source_campaign = _first_custom_field(
        custom_fields,
        ("source_campaign", "campaign", "campaign_name", "source"),
    ) or _clean_prompt_value(campaign.get("name"))

    return {
        "contact_name": contact_name,
        "contact_first_name": first_name,
        "contact_last_name": last_name,
        "contact_phone": _clean_prompt_value(contact.get("phone")),
        "contact_email": _clean_prompt_value(contact.get("email")),
        "lead_offer": lead_offer,
        "contact_latest_optin": lead_offer,
        "contact_timezone": contact_timezone,
        "contact_id": _clean_prompt_value(contact.get("id")),
        "call_id": _clean_prompt_value(contact.get("call_sid")),
        "callback_number": callback_number,
        "source_campaign": source_campaign,
    }


def _format_outbound_lead_context(context: dict[str, str]) -> str:
    """Render normalized lead context as a compact system-prompt block."""
    ordered_keys = (
        "contact_name",
        "contact_first_name",
        "contact_last_name",
        "contact_phone",
        "contact_email",
        "lead_offer",
        "contact_timezone",
        "contact_id",
        "call_id",
        "callback_number",
        "source_campaign",
    )
    lines = [
        "# Outbound Lead Context",
        "Use this context silently. Do not read field names aloud.",
    ]
    for key in ordered_keys:
        value = context.get(key, "")
        if value:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _render_campaign_system_instructions(instructions_path: str) -> str:
    """Render a campaign-specific prompt with the same config builders as the main prompt."""
    from config import (
        _build_accent_instruction,
        _build_booking_instruction,
        _build_call_record_instruction,
        _build_delivery_instruction,
        _build_language_instruction,
        _build_reasoning_effort_instruction,
        _build_tools_availability_instruction,
        _build_tools_text,
        _build_transfer_instruction,
    )
    from system_instructions import render_system_instructions

    return render_system_instructions(
        company_name=Config.COMPANY_NAME,
        agent_name=Config.AGENT_NAME,
        delivery_instruction=_build_delivery_instruction(
            Config.ASSISTANT_TONE,
            Config.ASSISTANT_WARMTH,
            Config.ASSISTANT_EXPRESSIVENESS,
            Config.ASSISTANT_PACING,
        ),
        language_instruction=_build_language_instruction(
            Config.ASSISTANT_LANGUAGE,
            Config.LANGUAGE_SWITCH_POLICY,
        ),
        accent_instruction=_build_accent_instruction(
            Config.ASSISTANT_LANGUAGE,
            Config.ASSISTANT_ACCENT,
            Config.ASSISTANT_ACCENT_STRENGTH,
        ),
        call_record_instruction=_build_call_record_instruction(),
        booking_instruction=_build_booking_instruction(),
        transfer_instruction=_build_transfer_instruction(),
        reasoning_effort_instruction=_build_reasoning_effort_instruction(
            Config.OPENAI_REALTIME_MODEL,
            Config.REALTIME_REASONING_EFFORT,
        ),
        tools_availability_instruction=_build_tools_availability_instruction(),
        tools_text=_build_tools_text(),
        instructions_path=instructions_path,
    )


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client():
    """Create and return a Supabase client. Returns None if not configured."""
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        Log.info("SUPABASE_URL/SUPABASE_KEY not set; outbound service unavailable")
        return None
    try:
        from supabase import create_client
    except ImportError:
        Log.error("supabase package not installed; pip install supabase")
        return None
    return create_client(Config.SUPABASE_URL.strip(), Config.SUPABASE_KEY.strip())


def _campaigns_table() -> str:
    return Config.SUPABASE_OUTBOUND_CAMPAIGNS_TABLE or "outbound_campaigns"


def _contacts_table() -> str:
    return Config.SUPABASE_OUTBOUND_CONTACTS_TABLE or "outbound_contacts"


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------

def create_campaign_sync(
    name: str,
    campaign_type: str = "general",
    message_template: str = "",
    concurrency: int = 1,
) -> dict[str, Any] | None:
    """Insert a new campaign row. Returns the inserted row dict or None on failure."""
    client = _get_supabase_client()
    if not client:
        return None
    concurrency = max(1, min(concurrency, Config.OUTBOUND_MAX_CONCURRENCY))
    row = {
        "name": name,
        "campaign_type": campaign_type,
        "message_template": message_template,
        "concurrency": concurrency,
        "status": "draft",
    }
    try:
        r = client.table(_campaigns_table()).insert(row).execute()
        data = (r.data or []) if hasattr(r, "data") else []
        if data:
            Log.info(f"Outbound campaign created: {data[0].get('id')}")
            return data[0]
        return None
    except Exception as e:
        Log.error(f"Outbound campaign create error: {e}")
        return None


def _aggregate_contact_progress(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Group contact status rows by campaign_id into progress count dicts."""
    progress_by_campaign: dict[str, dict[str, int]] = {}
    for row in rows:
        campaign_id = row.get("campaign_id")
        if not campaign_id:
            continue
        counts = progress_by_campaign.setdefault(str(campaign_id), {})
        status = row.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        counts["total"] = counts.get("total", 0) + 1
    return progress_by_campaign


def _fetch_contact_progress_for_campaigns_sync(
    client: Any,
    campaign_ids: list[str],
) -> dict[str, dict[str, int]]:
    """Return per-campaign contact status counts for the given campaign ids."""
    if not campaign_ids:
        return {}
    try:
        r = (
            client.table(_contacts_table())
            .select("campaign_id, status")
            .in_("campaign_id", campaign_ids)
            .execute()
        )
        rows = (r.data or []) if hasattr(r, "data") else []
        return _aggregate_contact_progress(rows)
    except Exception as e:
        Log.error(f"Outbound campaign list progress error: {e}")
        return {}


def list_campaigns_sync(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """List campaigns ordered by created_at DESC. Returns (rows, total_count)."""
    client = _get_supabase_client()
    if not client:
        return [], 0
    try:
        query = (
            client.table(_campaigns_table())
            .select("*", count="exact")
            .order("created_at", desc=True)
        )
        if status and str(status).strip():
            query = query.eq("status", str(status).strip())
        query = query.range(offset, offset + limit - 1)
        r = query.execute()
        data = (r.data or []) if hasattr(r, "data") else []
        total = r.count if hasattr(r, "count") and r.count is not None else len(data)
        campaign_ids = [str(c["id"]) for c in data if c.get("id")]
        progress_by_id = _fetch_contact_progress_for_campaigns_sync(client, campaign_ids)
        for campaign in data:
            campaign_id = str(campaign.get("id") or "")
            campaign["progress"] = progress_by_id.get(campaign_id, {"total": 0})
        return data, total
    except Exception as e:
        Log.error(f"Outbound campaigns list error: {e}")
        return [], 0


def get_campaign_sync(campaign_id: str) -> dict[str, Any] | None:
    """Fetch a single campaign by id, including its contacts."""
    client = _get_supabase_client()
    if not client or not campaign_id:
        return None
    try:
        r = client.table(_campaigns_table()).select("*").eq("id", campaign_id).limit(1).execute()
        data = (r.data or []) if hasattr(r, "data") else []
        if not data:
            return None
        campaign = data[0]
        cr = (
            client.table(_contacts_table())
            .select("*")
            .eq("campaign_id", campaign_id)
            .order("id", desc=False)
            .execute()
        )
        campaign["contacts"] = (cr.data or []) if hasattr(cr, "data") else []
        return campaign
    except Exception as e:
        Log.error(f"Outbound campaign get error: {e}")
        return None


def update_campaign_sync(campaign_id: str, updates: dict[str, Any]) -> bool:
    """Update campaign row by id. Returns True on success."""
    client = _get_supabase_client()
    if not client or not campaign_id or not updates:
        return False
    allowed = {"name", "campaign_type", "message_template", "concurrency", "status", "started_at", "completed_at", "metadata"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return False
    if "concurrency" in filtered:
        filtered["concurrency"] = max(1, min(int(filtered["concurrency"]), Config.OUTBOUND_MAX_CONCURRENCY))
    try:
        client.table(_campaigns_table()).update(filtered).eq("id", campaign_id).execute()
        Log.info(f"Outbound campaign updated: {campaign_id}")
        return True
    except Exception as e:
        Log.error(f"Outbound campaign update error: {e}")
        return False


def delete_campaign_sync(campaign_id: str) -> bool:
    """Delete campaign by id (cascade deletes contacts). Returns True on success."""
    client = _get_supabase_client()
    if not client or not campaign_id:
        return False
    try:
        client.table(_campaigns_table()).delete().eq("id", campaign_id).execute()
        Log.info(f"Outbound campaign deleted: {campaign_id}")
        return True
    except Exception as e:
        Log.error(f"Outbound campaign delete error: {e}")
        return False


# ---------------------------------------------------------------------------
# Contact CRUD
# ---------------------------------------------------------------------------

def add_contacts_sync(campaign_id: str, contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bulk-insert contacts for a campaign. Returns list of inserted rows."""
    client = _get_supabase_client()
    if not client or not campaign_id or not contacts:
        return []
    rows = []
    for c in contacts:
        phone = (c.get("phone") or "").strip()
        if not phone:
            continue
        rows.append({
            "campaign_id": campaign_id,
            "name": (c.get("name") or "").strip(),
            "phone": phone,
            "email": (c.get("email") or "").strip(),
            "custom_fields": c.get("custom_fields") or {},
            "status": "pending",
        })
    if not rows:
        return []
    try:
        r = client.table(_contacts_table()).insert(rows).execute()
        data = (r.data or []) if hasattr(r, "data") else []
        Log.info(f"Outbound contacts added: {len(data)} for campaign {campaign_id}")
        return data
    except Exception as e:
        Log.error(f"Outbound contacts insert error: {e}")
        return []


def delete_contact_sync(contact_id: str) -> bool:
    """Delete a single contact by id. Returns True on success."""
    client = _get_supabase_client()
    if not client or not contact_id:
        return False
    try:
        client.table(_contacts_table()).delete().eq("id", contact_id).execute()
        return True
    except Exception as e:
        Log.error(f"Outbound contact delete error: {e}")
        return False


def update_contact_status_sync(
    contact_id: str,
    status: str,
    call_sid: str | None = None,
    error: str | None = None,
) -> bool:
    """
    Update a contact's call status. Used by the campaign runner and status callbacks.
    Looks up by contact_id when provided, or by call_sid as fallback (Twilio callbacks
    only know the call_sid, not our internal contact_id).
    """
    client = _get_supabase_client()
    if not client:
        return False
    if not contact_id and not call_sid:
        return False
    updates: dict[str, Any] = {"status": status}
    if call_sid is not None:
        updates["call_sid"] = call_sid
    if error is not None:
        updates["error"] = error
    now_iso = datetime.now(timezone.utc).isoformat()
    if status == "calling":
        updates["called_at"] = now_iso
    elif status in ("completed", "failed", "skipped"):
        updates["completed_at"] = now_iso
    try:
        query = client.table(_contacts_table()).update(updates)
        if contact_id:
            query = query.eq("id", contact_id)
        else:
            query = query.eq("call_sid", call_sid)
        query.execute()
        return True
    except Exception as e:
        Log.error(f"Outbound contact status update error: {e}")
        return False


def get_contact_sync(contact_id: str) -> dict[str, Any] | None:
    """Fetch a single contact by id."""
    client = _get_supabase_client()
    if not client or not contact_id:
        return None
    try:
        r = client.table(_contacts_table()).select("*").eq("id", contact_id).limit(1).execute()
        data = (r.data or []) if hasattr(r, "data") else []
        return data[0] if data else None
    except Exception as e:
        Log.error(f"Outbound contact get error: {e}")
        return None


# ---------------------------------------------------------------------------
# Campaign progress
# ---------------------------------------------------------------------------

def get_campaign_progress_sync(campaign_id: str) -> dict[str, int]:
    """Return contact counts grouped by status for a campaign. Used for dashboard progress display."""
    client = _get_supabase_client()
    if not client or not campaign_id:
        return {}
    try:
        r = (
            client.table(_contacts_table())
            .select("status")
            .eq("campaign_id", campaign_id)
            .execute()
        )
        rows = (r.data or []) if hasattr(r, "data") else []
        counts: dict[str, int] = {}
        for row in rows:
            s = row.get("status", "pending")
            counts[s] = counts.get(s, 0) + 1
        counts["total"] = len(rows)
        return counts
    except Exception as e:
        Log.error(f"Outbound campaign progress error: {e}")
        return {}


def reset_failed_to_pending_sync(campaign_id: str) -> int:
    """
    Set all contacts with status 'failed' to 'pending' and clear call_sid, error, completed_at.
    Used when re-running a completed campaign so failed contacts can be redialed.
    Returns the number of contacts reset.
    """
    client = _get_supabase_client()
    if not client or not campaign_id:
        return 0
    try:
        r = (
            client.table(_contacts_table())
            .update({"status": "pending", "call_sid": None, "error": None, "completed_at": None})
            .eq("campaign_id", campaign_id)
            .eq("status", "failed")
            .execute()
        )
        data = (r.data or []) if hasattr(r, "data") else []
        count = len(data)
        if count:
            Log.info(f"Outbound campaign {campaign_id}: reset {count} failed contact(s) to pending")
        return count
    except Exception as e:
        Log.error(f"Outbound reset failed to pending error: {e}")
        return 0


def reset_contact_to_pending_sync(contact_id: str) -> bool:
    """
    Set a single contact to 'pending' and clear call_sid, error, completed_at.
    Use when a contact is stuck in 'calling' (e.g. call failed before Twilio status callback) so the user can retry.
    Only updates when current status is 'calling' or 'failed'. Returns True if updated.
    """
    contact = get_contact_sync(contact_id)
    if not contact or contact.get("status") not in ("calling", "failed"):
        return False
    client = _get_supabase_client()
    if not client:
        return False
    try:
        client.table(_contacts_table()).update(
            {"status": "pending", "call_sid": None, "error": None, "completed_at": None}
        ).eq("id", contact_id).execute()
        Log.info(f"Outbound contact {contact_id} reset to pending")
        return True
    except Exception as e:
        Log.error(f"Outbound contact reset error: {e}")
        return False


# ---------------------------------------------------------------------------
# System message builder for outbound calls
# ---------------------------------------------------------------------------

def build_outbound_system_message(campaign_id: str, contact_id: str) -> str | None:
    """
    Fetch campaign + contact from Supabase and render the system message with
    normalized lead context. Returns None only when campaign/contact data cannot
    be loaded.
    """
    client = _get_supabase_client()
    if not client:
        return None
    try:
        cr = client.table(_campaigns_table()).select("*").eq("id", campaign_id).limit(1).execute()
        campaign_rows = (cr.data or []) if hasattr(cr, "data") else []
        if not campaign_rows:
            Log.info(f"Outbound system message: campaign {campaign_id} not found")
            return None
        campaign = campaign_rows[0]

        ctr = client.table(_contacts_table()).select("*").eq("id", contact_id).limit(1).execute()
        contact_rows = (ctr.data or []) if hasattr(ctr, "data") else []
        if not contact_rows:
            Log.info(f"Outbound system message: contact {contact_id} not found")
            return None
        contact = contact_rows[0]
    except Exception as e:
        Log.error(f"Outbound system message fetch error: {e}")
        return None

    template = (campaign.get("message_template") or "").strip()
    if not template:
        template = resolve_campaign_type_default_script(campaign.get("campaign_type", "general"))
    if not template:
        return None

    from system_instructions import get_agent_name
    agent_name = get_agent_name() or "the voice agent"
    custom_fields = contact.get("custom_fields") or {}
    if not isinstance(custom_fields, dict):
        custom_fields = {}
    lead_context = _build_outbound_lead_context(
        campaign=campaign,
        contact=contact,
        custom_fields=custom_fields,
    )
    replacements = {
        "contact_name": lead_context.get("contact_name") or "there",
        "company_name": os.getenv("COMPANY_NAME") or getattr(Config, "COMPANY_NAME", "our company"),
        "agent_name": agent_name,
        "receptionist_name": agent_name,
    }
    replacements.update(custom_fields)
    replacements.update({key: value for key, value in lead_context.items() if value})

    result = template
    for key, value in replacements.items():
        result = result.replace("{" + key + "}", str(value))

    result = result.rstrip() + "\n\n" + _format_outbound_lead_context(lead_context)

    return _append_language_and_accent_policy(result)


# ---------------------------------------------------------------------------
# Campaign runner (async orchestrator)
# ---------------------------------------------------------------------------

async def run_campaign(campaign_id: str, base_url: str) -> None:
    """
    Dial all pending contacts in a campaign with concurrency control.
    Launched as a background task from the /start endpoint.
    Checks campaign status before each dial — if paused, stops picking up new contacts.
    """
    import asyncio
    from services.twilio_service import TwilioService

    campaign = await asyncio.to_thread(get_campaign_sync, campaign_id)
    if not campaign:
        Log.error(f"run_campaign: campaign {campaign_id} not found")
        return

    concurrency = max(1, min(campaign.get("concurrency", 1), Config.OUTBOUND_MAX_CONCURRENCY))
    contacts = campaign.get("contacts") or []
    pending = [c for c in contacts if c.get("status") == "pending"]
    if not pending:
        await asyncio.to_thread(update_campaign_sync, campaign_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        return

    Log.info(f"Outbound campaign {campaign_id}: dialing {len(pending)} contacts (concurrency={concurrency})")
    sem = asyncio.Semaphore(concurrency)

    async def _dial_one(contact: dict) -> None:
        async with sem:
            fresh = await asyncio.to_thread(get_campaign_sync, campaign_id)
            if not fresh or fresh.get("status") != "running":
                Log.info(f"Campaign {campaign_id} no longer running; skipping contact {contact.get('id')}")
                return

            contact_id = contact["id"]
            phone = (contact.get("phone") or "").strip()
            if not phone:
                await asyncio.to_thread(update_contact_status_sync, contact_id, "skipped", error="No phone number")
                return

            await asyncio.to_thread(update_contact_status_sync, contact_id, "calling")
            twiml_url = f"{base_url}/outbound-call-twiml/{campaign_id}?contact_id={quote(contact_id, safe='')}"
            status_callback = f"{base_url}/outbound-call-status"

            try:
                call = await TwilioService.create_outbound_call(
                    to=phone,
                    twiml_url=twiml_url,
                    status_callback=status_callback,
                )
                TwilioService.register_outbound_context(call.sid, campaign_id, contact_id)
                await asyncio.to_thread(
                    update_contact_status_sync, contact_id, "calling", call_sid=call.sid
                )
            except Exception as e:
                Log.error(f"Outbound dial failed for {phone}: {e}")
                await asyncio.to_thread(
                    update_contact_status_sync, contact_id, "failed", error=str(e)[:500]
                )

    tasks = [_dial_one(c) for c in pending]
    await asyncio.gather(*tasks, return_exceptions=True)

    final = await asyncio.to_thread(get_campaign_sync, campaign_id)
    if final and final.get("status") == "running":
        await asyncio.to_thread(update_campaign_sync, campaign_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        Log.info(f"Outbound campaign {campaign_id} completed")
