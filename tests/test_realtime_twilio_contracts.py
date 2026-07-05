"""Contracts for the Twilio Media Stream bridge and Realtime connection URL."""

import asyncio
import json
import os
import sys
from pathlib import Path

from fastapi.websockets import WebSocketDisconnect
from starlette.requests import Request

# Ensure project root is on path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = Path(__file__).resolve().parents[1]

from config import Config
from services.connection_manager import WebSocketConnectionManager
from services.twilio_service import TwilioService


def _request(method: str, host: str, body: bytes = b"") -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/incoming-call",
            "headers": [(b"host", host.encode("ascii"))],
            "server": (host, 443),
            "scheme": "https",
            "query_string": b"",
        },
        receive,
    )


def test_incoming_twiml_uses_custom_parameter_for_caller_number():
    request = _request(
        "POST",
        "example.com",
        b"From=%2B15551234567&CallSid=CA123",
    )

    response = asyncio.run(TwilioService.create_incoming_call_response(request))
    xml = response.body.decode("utf-8")

    assert 'url="wss://example.com/media-stream"' in xml
    assert "?caller_number=" not in xml
    assert 'name="caller_number" value="+15551234567"' in xml


def test_outbound_twiml_uses_custom_parameters():
    response = TwilioService.create_outbound_stream_response(
        "example.com",
        campaign_id="campaign-123",
        contact_id="contact-456",
    )
    xml = response.body.decode("utf-8")

    assert 'url="wss://example.com/media-stream"' in xml
    assert "?direction=outbound" not in xml
    assert 'name="direction" value="outbound"' in xml
    assert 'name="campaign_id" value="campaign-123"' in xml
    assert 'name="contact_id" value="contact-456"' in xml


def test_create_outbound_call_rejects_twilio_number_as_destination(monkeypatch):
    """The lead phone must not be the same number used as Twilio caller ID."""
    monkeypatch.setattr(Config, "has_twilio_credentials", classmethod(lambda cls: True))
    monkeypatch.setattr(Config, "get_outbound_from_number", classmethod(lambda cls: "+12185957805"))

    try:
        asyncio.run(
            TwilioService.create_outbound_call(
                to="(218) 595-7805",
                twiml_url="https://voice.example.test/outbound-call-twiml/campaign-1",
            )
        )
        raise AssertionError("Expected create_outbound_call to reject self-call")
    except RuntimeError as exc:
        assert "Outbound destination matches TWILIO_OUTBOUND_NUMBER" in str(exc)


def test_recording_media_endpoint_supports_byte_ranges():
    """Dashboard MP3 playback needs range responses for browser seeking."""
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "def _parse_http_range_header(" in source
    assert "\"Accept-Ranges\": \"bytes\"" in source
    assert "\"Content-Range\": f\"bytes {start}-{end}/{content_length}\"" in source
    assert "status_code=206" in source
    assert "status_code=416" in source


def test_dashboard_recording_player_keeps_seek_state():
    """Custom recording player should seek by seconds and not snap back while dragging."""
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")

    assert "class=\\\"custom-audio-seek\\\" min=\\\"0\\\" max=\\\"0\\\" step=\\\"0.01\\\" value=\\\"0\\\" disabled" in html
    assert "var isSeeking = false;" in html
    assert "range.max = String(audio.duration);" in html
    assert "if (syncRangeBounds() && !isSeeking) range.value = String(cur || 0);" in html
    assert "audio.currentTime = target;" in html
    assert "range.addEventListener(\"pointerdown\"" in html
    assert "range.addEventListener(\"pointerup\"" in html


class _FakeTwilioWebSocket:
    def __init__(self, messages: list[dict]):
        self._messages = messages

    async def iter_text(self):
        for message in self._messages:
            yield json.dumps(message)


def test_stream_start_custom_parameters_hydrate_connection_state():
    manager = WebSocketConnectionManager(
        _FakeTwilioWebSocket(
            [
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZ123",
                        "callSid": "CA123",
                        "customParameters": {
                            "caller_number": "+15551234567",
                            "direction": "outbound",
                            "campaign_id": "campaign-123",
                            "contact_id": "contact-456",
                        },
                    },
                }
            ]
        )
    )
    starts: list[str] = []

    async def on_media(_: dict) -> None:
        raise AssertionError("media handler should not run")

    async def on_start(stream_sid: str) -> None:
        starts.append(stream_sid)

    async def on_mark() -> None:
        raise AssertionError("mark handler should not run")

    async def run() -> None:
        try:
            await manager.receive_from_twilio(on_media, on_start, on_mark)
        except WebSocketDisconnect:
            pass

    asyncio.run(run())

    assert starts == ["MZ123"]
    assert manager.state.stream_sid == "MZ123"
    assert manager.state.call_sid == "CA123"
    assert manager.state.caller_phone_number == "+15551234567"
    assert manager.state.is_outbound_call is True
    assert manager.state.outbound_campaign_id == "campaign-123"
    assert manager.state.outbound_contact_id == "contact-456"


def test_realtime_websocket_url_uses_model_only(monkeypatch):
    monkeypatch.setattr(Config, "OPENAI_REALTIME_MODEL", "gpt-realtime-2")
    monkeypatch.setattr(Config, "TEMPERATURE", 0.1)
    monkeypatch.setattr(Config, "VOICE", "cedar")

    url = Config.get_openai_websocket_url()

    assert url == "wss://api.openai.com/v1/realtime?model=gpt-realtime-2"
    assert "temperature=" not in url
    assert "voice=" not in url
