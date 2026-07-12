"""Browser Realtime WebRTC session support.

This module keeps browser voice-lab sessions separate from the Twilio media
stream path. The standard OpenAI API key is used only server-side to mint a
short-lived Realtime client secret for the browser.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Mapping

import httpx

from config import Config, build_system_message_for_settings
from voice_realtime.session_builder import TRANSPORT_BROWSER, build_realtime_session
from voice_realtime.settings import EffectiveRealtimeSettings


OPENAI_REALTIME_CLIENT_SECRETS_URL = "https://api.openai.com/v1/realtime/client_secrets"
OPENAI_REALTIME_WEBRTC_URL = "https://api.openai.com/v1/realtime/calls"
SUPPORTED_BROWSER_TRANSCRIPTION_DELAYS = frozenset({"minimal", "low", "medium", "high", "xhigh"})


class BrowserRealtimeError(ValueError):
    """Raised for invalid browser Realtime session operations."""


@dataclass
class BrowserToolResult:
    call_id: str
    item: dict[str, Any]
    trigger_response: bool = True
    duplicate: bool = False


@dataclass
class BrowserRealtimeSession:
    browser_session_id: str
    created_at: float
    expires_at: float
    metadata: dict[str, Any]
    openai_session_id: str | None = None
    tool_results: dict[str, BrowserToolResult] = field(default_factory=dict)


class BrowserRealtimeSessionStore:
    """In-memory browser session registry and coarse throttling.

    This is intentionally process-local for Milestone 2. It prevents accidental
    duplicate tool execution and gives the backend a session boundary for the
    browser fallback tool endpoint.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserRealtimeSession] = {}
        self._recent_starts: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check_throttle(
        self,
        throttle_key: str,
        *,
        max_per_minute: int,
        max_active: int,
        now: float | None = None,
    ) -> None:
        now = now or time.time()
        async with self._lock:
            self._cleanup_locked(now)
            active_for_key = sum(
                1
                for session in self._sessions.values()
                if session.metadata.get("throttle_key") == throttle_key
            )
            if active_for_key >= max_active:
                raise BrowserRealtimeError("Too many active browser voice sessions.")
            window = [
                ts for ts in self._recent_starts.get(throttle_key, [])
                if now - ts < 60
            ]
            if len(window) >= max_per_minute:
                self._recent_starts[throttle_key] = window
                raise BrowserRealtimeError("Browser voice session rate limit exceeded.")
            window.append(now)
            self._recent_starts[throttle_key] = window

    async def register(
        self,
        *,
        metadata: Mapping[str, Any],
        expires_at: float,
        openai_session_id: str | None = None,
    ) -> BrowserRealtimeSession:
        now = time.time()
        async with self._lock:
            self._cleanup_locked(now)
            browser_session_id = f"brs_{uuid.uuid4().hex}"
            session = BrowserRealtimeSession(
                browser_session_id=browser_session_id,
                created_at=now,
                expires_at=expires_at,
                metadata=dict(metadata),
                openai_session_id=openai_session_id,
            )
            self._sessions[browser_session_id] = session
            return session

    async def get_valid(self, browser_session_id: str) -> BrowserRealtimeSession:
        async with self._lock:
            now = time.time()
            self._cleanup_locked(now)
            session = self._sessions.get((browser_session_id or "").strip())
            if not session:
                raise BrowserRealtimeError("Invalid or expired browser session.")
            if session.expires_at <= now:
                self._sessions.pop(session.browser_session_id, None)
                raise BrowserRealtimeError("Invalid or expired browser session.")
            return session

    async def get_tool_result(
        self,
        browser_session_id: str,
        call_id: str,
    ) -> BrowserToolResult | None:
        session = await self.get_valid(browser_session_id)
        return session.tool_results.get(call_id)

    async def remember_tool_result(
        self,
        browser_session_id: str,
        result: BrowserToolResult,
    ) -> None:
        async with self._lock:
            session = self._sessions.get(browser_session_id)
            if session:
                session.tool_results[result.call_id] = result

    def _cleanup_locked(self, now: float) -> None:
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for session_id in expired_ids:
            self._sessions.pop(session_id, None)
        for key, starts in list(self._recent_starts.items()):
            kept = [ts for ts in starts if now - ts < 60]
            if kept:
                self._recent_starts[key] = kept
            else:
                self._recent_starts.pop(key, None)


browser_realtime_session_store = BrowserRealtimeSessionStore()


def _client_secret_expires_at(response_payload: Mapping[str, Any]) -> float:
    secret = response_payload.get("client_secret")
    if isinstance(secret, Mapping):
        raw_expires = secret.get("expires_at") or secret.get("expires")
        try:
            if raw_expires:
                return float(raw_expires)
        except (TypeError, ValueError):
            pass
    raw_expires = response_payload.get("expires_at") or response_payload.get("expires")
    try:
        if raw_expires:
            return float(raw_expires)
    except (TypeError, ValueError):
        pass
    return time.time() + int(getattr(Config, "BROWSER_VOICE_LAB_SESSION_TTL_SECONDS", 600))


def _setting_metadata(settings: EffectiveRealtimeSettings, *, preset: str | None = None) -> dict[str, Any]:
    return {
        "model": settings.model,
        "voice": settings.voice,
        "voice_profile": settings.voice_profile,
        "preset": preset or settings.preset,
        "vad_mode": settings.vad_mode,
        "vad_eagerness": settings.vad_eagerness,
        "reasoning_effort": settings.reasoning_effort,
    }


def _browser_input_transcription_config() -> dict[str, Any] | None:
    model = (getattr(Config, "BROWSER_VOICE_LAB_TRANSCRIPTION_MODEL", "") or "").strip()
    if not model:
        return None
    transcription: dict[str, Any] = {"model": model}
    language = getattr(Config, "REALTIME_INPUT_TRANSCRIPTION_LANGUAGE", None)
    if isinstance(language, str) and language.strip():
        transcription["language"] = language.strip()
    delay = (getattr(Config, "BROWSER_VOICE_LAB_TRANSCRIPTION_DELAY", "") or "").strip().lower()
    if model == "gpt-realtime-whisper" and delay in SUPPORTED_BROWSER_TRANSCRIPTION_DELAYS:
        transcription["delay"] = delay
    return transcription


def build_browser_client_secret_payload(
    settings: EffectiveRealtimeSettings,
    *,
    instructions: str | None = None,
    tools: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the official Realtime client-secret request body."""
    if tools is None:
        from services.openai_service import OpenAISessionManager

        tools = OpenAISessionManager._realtime_tools()
    session_instructions = instructions or build_system_message_for_settings(settings)
    session = build_realtime_session(
        TRANSPORT_BROWSER,
        settings,
        session_instructions,
        tools,
        input_transcription=_browser_input_transcription_config(),
    )
    return {"session": session}


def browser_session_public_response(
    *,
    browser_session: BrowserRealtimeSession,
    openai_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Return only browser-safe session metadata and the ephemeral client secret."""
    client_secret = openai_payload.get("client_secret")
    safe_secret: dict[str, Any] = {}
    if isinstance(client_secret, Mapping):
        safe_secret = {
            "value": client_secret.get("value"),
            "expires_at": client_secret.get("expires_at") or client_secret.get("expires"),
        }
    elif openai_payload.get("value"):
        safe_secret = {
            "value": openai_payload.get("value"),
            "expires_at": openai_payload.get("expires_at") or openai_payload.get("expires"),
        }
    return {
        "browser_session_id": browser_session.browser_session_id,
        "openai_session_id": browser_session.openai_session_id,
        "client_secret": safe_secret,
        "webrtc_url": OPENAI_REALTIME_WEBRTC_URL,
        "expires_at": browser_session.expires_at,
        "metadata": dict(browser_session.metadata),
    }


def safety_identifier(raw: str | None) -> str:
    value = (raw or "dashboard").strip() or "dashboard"
    seed = f"{getattr(Config, 'AGENT_LABEL', 'voice-agent')}:{value}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


async def mint_browser_realtime_session(
    *,
    settings: EffectiveRealtimeSettings,
    throttle_key: str,
    safety_id: str,
    preset: str | None = None,
) -> dict[str, Any]:
    """Create a browser Realtime client secret and register the local session."""
    if not getattr(Config, "BROWSER_VOICE_LAB_ENABLED", True):
        raise BrowserRealtimeError("Browser Voice Lab is disabled.")
    if not getattr(Config, "OPENAI_API_KEY", None):
        raise BrowserRealtimeError("OPENAI_API_KEY is required to mint browser voice sessions.")

    await browser_realtime_session_store.check_throttle(
        throttle_key,
        max_per_minute=int(getattr(Config, "BROWSER_VOICE_LAB_MAX_SESSIONS_PER_MINUTE", 6)),
        max_active=int(getattr(Config, "BROWSER_VOICE_LAB_MAX_ACTIVE_SESSIONS", 3)),
    )
    payload = build_browser_client_secret_payload(settings)
    headers = {
        "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Safety-Identifier": safety_id,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            OPENAI_REALTIME_CLIENT_SECRETS_URL,
            headers=headers,
            json=payload,
        )
    if response.status_code >= 400:
        raise BrowserRealtimeError(f"OpenAI client-secret request failed with status {response.status_code}.")

    openai_payload = response.json()
    metadata = _setting_metadata(settings, preset=preset)
    metadata["throttle_key"] = throttle_key
    expires_at = _client_secret_expires_at(openai_payload)
    response_session = openai_payload.get("session")
    openai_session_id = response_session.get("id") if isinstance(response_session, Mapping) else openai_payload.get("id")
    browser_session = await browser_realtime_session_store.register(
        metadata=metadata,
        expires_at=expires_at,
        openai_session_id=openai_session_id,
    )
    return browser_session_public_response(
        browser_session=browser_session,
        openai_payload=openai_payload,
    )


class _BrowserToolConnectionManager:
    def __init__(self, session: BrowserRealtimeSession) -> None:
        self.state = SimpleNamespace(
            call_sid=None,
            stream_sid=None,
            caller_phone_number=None,
            is_outbound_call=False,
            call_record_saved=False,
            appointment_booked=False,
            confirmed_slot_display=None,
            priority=None,
            wait_for_user_count=0,
        )
        self.session = session
        self.sent_messages: list[dict[str, Any]] = []

    async def send_to_openai(self, message: Mapping[str, Any]) -> None:
        self.sent_messages.append(dict(message))

    def mark_twilio_closed(self) -> None:
        self.sent_messages.append({"type": "browser.session.close_requested"})

    async def close_twilio_connection(self, reason: str | None = None) -> None:
        self.sent_messages.append({
            "type": "browser.session.close_requested",
            "reason": reason,
        })


def _extract_tool_output(messages: list[Mapping[str, Any]], call_id: str) -> tuple[dict[str, Any], bool]:
    trigger_response = any(message.get("type") == "response.create" for message in messages)
    for message in messages:
        if message.get("type") != "conversation.item.create":
            continue
        item = message.get("item")
        if isinstance(item, Mapping) and item.get("type") == "function_call_output":
            output_item = dict(item)
            if "call_id" not in output_item and call_id:
                output_item["call_id"] = call_id
            return output_item, trigger_response
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": json.dumps({"success": False, "message": "Tool did not return output."}),
    }, trigger_response


async def execute_browser_tool_call(
    *,
    browser_session_id: str,
    call_id: str,
    name: str,
    arguments: Mapping[str, Any] | None,
) -> BrowserToolResult:
    """Execute an allowed tool call through existing Python handlers."""
    normalized_call_id = (call_id or "").strip()
    if not normalized_call_id:
        raise BrowserRealtimeError("Missing tool call_id.")
    session = await browser_realtime_session_store.get_valid(browser_session_id)
    duplicate = await browser_realtime_session_store.get_tool_result(
        browser_session_id,
        normalized_call_id,
    )
    if duplicate:
        return BrowserToolResult(
            call_id=duplicate.call_id,
            item=dict(duplicate.item),
            trigger_response=duplicate.trigger_response,
            duplicate=True,
        )

    from services.openai_service import OpenAISessionManager, OpenAIService

    allowed_tools = {tool.get("name") for tool in OpenAISessionManager._realtime_tools()}
    if name not in allowed_tools:
        raise BrowserRealtimeError("Unknown or unavailable tool.")
    if name == "end_call":
        output = json.dumps({
            "success": True,
            "message": (
                "Browser voice session end requested. Say one brief polite goodbye now, "
                "then stop speaking. The browser session can be closed by the user interface."
            ),
        })
        result = BrowserToolResult(
            call_id=normalized_call_id,
            item={
                "type": "function_call_output",
                "call_id": normalized_call_id,
                "output": output,
            },
            trigger_response=True,
        )
        await browser_realtime_session_store.remember_tool_result(
            browser_session_id,
            result,
        )
        return result

    connection_manager = _BrowserToolConnectionManager(session)
    service = OpenAIService()
    handled = await service.maybe_handle_tool_call(
        connection_manager,
        {
            "name": name,
            "arguments": dict(arguments or {}),
            "call_id": normalized_call_id,
        },
    )
    if not handled:
        raise BrowserRealtimeError("Tool was not handled.")
    item, trigger_response = _extract_tool_output(
        connection_manager.sent_messages,
        normalized_call_id,
    )
    result = BrowserToolResult(
        call_id=normalized_call_id,
        item=item,
        trigger_response=trigger_response,
    )
    await browser_realtime_session_store.remember_tool_result(
        browser_session_id,
        result,
    )
    return result
