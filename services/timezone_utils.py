"""Timezone helpers for booking display and validation."""
from __future__ import annotations

from datetime import datetime
from typing import Any


COMMON_TIMEZONE_LABELS = {
    "America/Los_Angeles": "Pacific Time",
    "America/Denver": "Mountain Time",
    "America/Phoenix": "Mountain Time",
    "America/Chicago": "Central Time",
    "America/New_York": "Eastern Time",
    "America/Anchorage": "Alaska Time",
    "Pacific/Honolulu": "Hawaii Time",
    "UTC": "UTC",
    "Etc/UTC": "UTC",
}


def normalize_timezone_name(value: Any) -> str | None:
    """Return a valid IANA timezone name, or None when invalid/empty."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(text)
        return text
    except Exception:
        return None


def timezone_label(tz_name: str | None) -> str:
    """Human label for a timezone, preferring stable business-friendly names."""
    normalized = normalize_timezone_name(tz_name)
    if not normalized:
        return ""
    if normalized in COMMON_TIMEZONE_LABELS:
        return COMMON_TIMEZONE_LABELS[normalized]
    return normalized.replace("_", " ")


def same_timezone(left: str | None, right: str | None) -> bool:
    """True when both values validate to the same IANA timezone name."""
    left_normalized = normalize_timezone_name(left)
    right_normalized = normalize_timezone_name(right)
    return bool(left_normalized and right_normalized and left_normalized == right_normalized)


def format_local_time(
    dt: datetime,
    tz_name: str,
    *,
    include_timezone: bool = True,
    long: bool = False,
) -> str:
    """Format an aware datetime in the requested timezone for caller-facing use."""
    normalized = normalize_timezone_name(tz_name) or "UTC"
    try:
        from zoneinfo import ZoneInfo

        local_dt = dt.astimezone(ZoneInfo(normalized))
    except Exception:
        local_dt = dt
    fmt = "%A, %B %d at %I:%M %p" if long else "%a %b %d at %I:%M %p"
    text = local_dt.strftime(fmt)
    if include_timezone:
        label = timezone_label(normalized)
        if label:
            text = f"{text} {label}"
    return text


def infer_timezone_from_phone(phone: Any) -> str | None:
    """
    Best-effort caller timezone from phone number.

    Requires optional phonenumbers package. Returns a value only when it yields a
    single valid timezone; ambiguous/mobile/unknown numbers intentionally return None.
    """
    raw = str(phone or "").strip()
    if not raw:
        return None
    try:
        import phonenumbers
        from phonenumbers import timezone as phone_timezone
    except Exception:
        return None

    try:
        region = None if raw.startswith("+") else "US"
        parsed = phonenumbers.parse(raw, region)
        if not phonenumbers.is_possible_number(parsed):
            return None
        zones = [
            zone
            for zone in phone_timezone.time_zones_for_number(parsed)
            if normalize_timezone_name(zone)
        ]
    except Exception:
        return None

    unique = sorted(set(zones))
    if len(unique) == 1:
        return unique[0]
    return None
