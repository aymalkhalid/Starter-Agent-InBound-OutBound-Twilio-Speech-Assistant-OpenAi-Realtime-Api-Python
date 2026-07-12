import asyncio
import inspect
import json
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from voice_realtime.browser import (
    BrowserToolResult,
    browser_realtime_session_store,
    browser_session_public_response,
    build_browser_client_secret_payload,
    execute_browser_tool_call,
)
from config import Config
from voice_realtime.settings import EffectiveRealtimeSettings


ROOT = Path(__file__).resolve().parents[1]


def _request(path: str = "/api/realtime/browser-session") -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(b"accept", b"application/json")],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "query_string": b"",
        },
        receive,
    )


def test_browser_session_payload_uses_high_fidelity_audio_not_pcmu():
    settings = EffectiveRealtimeSettings.from_mapping(
        {
            "model": "gpt-realtime-2.1",
            "voice": "marin",
            "vad_mode": "semantic_vad",
            "vad_eagerness": "low",
            "reasoning_effort": "low",
        }
    )

    payload = build_browser_client_secret_payload(
        settings,
        instructions="Test instructions",
        tools=[{"type": "function", "name": "wait_for_user", "parameters": {"type": "object"}}],
    )

    session = payload["session"]
    assert session["model"] == "gpt-realtime-2.1"
    assert session["audio"]["output"]["voice"] == "marin"
    assert session["audio"]["input"]["turn_detection"]["type"] == "semantic_vad"
    assert session["audio"]["input"]["transcription"]["model"] == Config.BROWSER_VOICE_LAB_TRANSCRIPTION_MODEL
    encoded = json.dumps(session)
    assert "audio/pcmu" not in encoded
    assert "Test instructions" in encoded
    assert "wait_for_user" in encoded


def test_browser_public_response_does_not_include_standard_api_key(monkeypatch):
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "sk-secret-standard-key")

    class Session:
        browser_session_id = "brs_test"
        openai_session_id = "sess_test"
        expires_at = time.time() + 60
        metadata = {"model": "gpt-realtime-2.1", "voice": "marin"}

    payload = browser_session_public_response(
        browser_session=Session(),
        openai_payload={
            "id": "sess_test",
            "client_secret": {"value": "ek_ephemeral", "expires_at": 123},
        },
    )

    encoded = json.dumps(payload)
    assert "ek_ephemeral" in encoded
    assert "sk-secret-standard-key" not in encoded
    assert "OPENAI_API_KEY" not in encoded


def test_browser_public_response_accepts_official_client_secret_shape(monkeypatch):
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "sk-secret-standard-key")

    class Session:
        browser_session_id = "brs_test"
        openai_session_id = "sess_official"
        expires_at = 123
        metadata = {"model": "gpt-realtime-2.1", "voice": "marin"}

    payload = browser_session_public_response(
        browser_session=Session(),
        openai_payload={
            "value": "ek_official_ephemeral",
            "expires_at": 456,
            "session": {"id": "sess_official"},
        },
    )

    assert payload["client_secret"]["value"] == "ek_official_ephemeral"
    assert payload["client_secret"]["expires_at"] == 456
    encoded = json.dumps(payload)
    assert "sk-secret-standard-key" not in encoded
    assert "OPENAI_API_KEY" not in encoded


def test_voice_lab_requires_configured_dashboard_auth(monkeypatch):
    from main import _require_configured_dashboard_auth

    monkeypatch.setattr(Config, "DASHBOARD_USERS", None)
    with pytest.raises(HTTPException) as exc_info:
        _require_configured_dashboard_auth(request=_request(), key=None, x_dashboard_key=None)
    assert exc_info.value.status_code == 403

    monkeypatch.setattr(Config, "DASHBOARD_USERS", "admin:secret")
    with pytest.raises(HTTPException) as exc_info:
        _require_configured_dashboard_auth(request=_request(), key=None, x_dashboard_key=None)
    assert exc_info.value.status_code == 401

    _require_configured_dashboard_auth(request=_request(), key=None, x_dashboard_key="secret")


def test_voice_lab_static_assets_do_not_reference_standard_api_key():
    html = (ROOT / "static" / "voice_lab.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")

    assert "/api/realtime/browser-session" in html
    assert "/api/realtime/browser-tool-call" in html
    assert "OPENAI_API_KEY" not in html
    assert "sk-" not in html
    assert 'id="voice-lab-link"' in dashboard
    assert "/dashboard/voice-lab" in dashboard


def test_voice_lab_has_audio_reactive_voice_orb():
    html = (ROOT / "static" / "voice_lab.html").read_text(encoding="utf-8")

    assert 'id="voice-orb"' in html
    assert 'class="orb-core"' in html
    assert 'class="orb-wave"' in html
    assert 'data-state="idle"' in html
    assert "setOrbState" in html
    assert "attachMicMeter(localStream)" in html
    assert "attachRemoteMeter(event.streams[0])" in html
    assert "createAnalyser" in html
    assert "--voice-level" in html


def test_voice_lab_handles_live_realtime_transcript_events():
    html = (ROOT / "static" / "voice_lab.html").read_text(encoding="utf-8")

    assert "response.output_audio_transcript.delta" in html
    assert "response.output_audio_transcript.done" in html
    assert "conversation.item.input_audio_transcription.delta" in html
    assert "conversation.item.input_audio_transcription.completed" in html
    assert "appendTranscriptDelta" in html
    assert "completeTranscriptTurn" in html
    assert "Live transcript will appear here once speech is detected." in html


def test_voice_lab_batches_tool_outputs_before_followup_response():
    html = (ROOT / "static" / "voice_lab.html").read_text(encoding="utf-8")

    assert "queueRealtimeToolCall(event)" in html
    assert "handleToolCallsBatch(calls)" in html
    assert "deferResponseCreate" in html
    assert "remaining_booking_count" in html
    assert "sendToolResponseCreate()" in html


def test_invalid_browser_session_rejected():
    async def run():
        with pytest.raises(Exception) as exc_info:
            await execute_browser_tool_call(
                browser_session_id="missing",
                call_id="call_1",
                name="wait_for_user",
                arguments={},
            )
        assert "Invalid or expired browser session" in str(exc_info.value)

    asyncio.run(run())


def test_duplicate_browser_tool_call_executes_once():
    async def run():
        session = await browser_realtime_session_store.register(
            metadata={"model": "gpt-realtime-2.1"},
            expires_at=time.time() + 60,
            openai_session_id="sess_duplicate",
        )
        remembered = BrowserToolResult(
            call_id="call_dup",
            item={"type": "function_call_output", "call_id": "call_dup", "output": "OK"},
            trigger_response=False,
        )
        await browser_realtime_session_store.remember_tool_result(
            session.browser_session_id,
            remembered,
        )

        result = await execute_browser_tool_call(
            browser_session_id=session.browser_session_id,
            call_id="call_dup",
            name="wait_for_user",
            arguments={},
        )

        assert result.duplicate is True
        assert result.item["output"] == "OK"
        assert result.trigger_response is False

    asyncio.run(run())


def test_unknown_browser_tool_rejected():
    async def run():
        session = await browser_realtime_session_store.register(
            metadata={"model": "gpt-realtime-2.1"},
            expires_at=time.time() + 60,
            openai_session_id="sess_unknown_tool",
        )
        with pytest.raises(Exception) as exc_info:
            await execute_browser_tool_call(
                browser_session_id=session.browser_session_id,
                call_id="call_unknown",
                name="unknown_tool",
                arguments={},
            )
        assert "Unknown or unavailable tool" in str(exc_info.value)

    asyncio.run(run())


def test_browser_end_call_is_transport_specific(monkeypatch):
    from voice_realtime.browser import _BrowserToolConnectionManager
    from services.openai_service import OpenAIService

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Browser end_call should not use Twilio end-call handler")

    async def run():
        session = await browser_realtime_session_store.register(
            metadata={"model": "gpt-realtime-2.1"},
            expires_at=time.time() + 60,
            openai_session_id="sess_browser_end",
        )
        monkeypatch.setattr(OpenAIService, "maybe_handle_tool_call", fail_if_called)

        result = await execute_browser_tool_call(
            browser_session_id=session.browser_session_id,
            call_id="call_browser_end",
            name="end_call",
            arguments={"reason": "user said goodbye"},
        )

        assert result.trigger_response is True
        assert result.item["type"] == "function_call_output"
        assert result.item["call_id"] == "call_browser_end"
        assert "Browser voice session end requested" in result.item["output"]

        duplicate = await execute_browser_tool_call(
            browser_session_id=session.browser_session_id,
            call_id="call_browser_end",
            name="end_call",
            arguments={"reason": "user said goodbye"},
        )
        assert duplicate.duplicate is True
        assert duplicate.item == result.item

    assert inspect.iscoroutinefunction(_BrowserToolConnectionManager.mark_twilio_closed) is False
    asyncio.run(run())
