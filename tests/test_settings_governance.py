import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from config import Config
from voice_realtime.options import get_realtime_options_payload
from services import dynamic_settings


def test_realtime_options_payload_is_registry_backed():
    payload = get_realtime_options_payload()
    models = {item["id"]: item for item in payload["models"]}

    assert "gpt-realtime-2.1" in models
    assert models["gpt-realtime-2.1"]["supports_reasoning_effort"] is True
    assert "gpt-realtime-2.1-mini" in models
    assert models["gpt-realtime-2.1-mini"]["supports_reasoning_effort"] is False
    assert any(voice["id"] == "marin" and voice["recommended"] for voice in payload["voices"])
    assert any(preset["id"] == "professional_phone" for preset in payload["presets"])


def test_grouped_realtime_settings_ignore_realtime_per_key_rows():
    rows = [
        {"key": "OPENAI_REALTIME_MODEL", "value": "gpt-realtime-2"},
        {"key": "VOICE", "value": "cedar"},
        {"key": "COMPANY_NAME", "value": "Example Co"},
        {
            "key": dynamic_settings.GROUPED_REALTIME_SETTINGS_KEY,
            "value": json.dumps(
                {
                    "OPENAI_REALTIME_MODEL": "gpt-realtime-2.1",
                    "VOICE": "marin",
                    "VAD_MODE": "semantic_vad",
                }
            ),
        },
    ]

    overrides = dynamic_settings._settings_rows_to_overrides(rows)

    assert overrides["OPENAI_REALTIME_MODEL"] == "gpt-realtime-2.1"
    assert overrides["VOICE"] == "marin"
    assert overrides["VAD_MODE"] == "semantic_vad"
    assert overrides["COMPANY_NAME"] == "Example Co"


def test_save_overrides_writes_realtime_group_as_single_json_row(monkeypatch):
    upserts: list[dict] = []
    rows = [
        {
            "key": dynamic_settings.GROUPED_REALTIME_SETTINGS_KEY,
            "value": json.dumps({"VAD_MODE": "server_vad"}),
        }
    ]

    class FakeTable:
        def __init__(self):
            self.mode = "select"

        def select(self, *_args, **_kwargs):
            self.mode = "select"
            return self

        def upsert(self, row, **_kwargs):
            self.mode = "upsert"
            upserts.append(row)
            return self

        def execute(self):
            return SimpleNamespace(data=rows if self.mode == "select" else [])

    class FakeClient:
        def table(self, name):
            assert name == "app_settings"
            return FakeTable()

    monkeypatch.setitem(
        sys.modules,
        "supabase",
        SimpleNamespace(create_client=lambda _url, _key: FakeClient()),
    )
    monkeypatch.setattr(Config, "CALL_RECORD_BACKEND", "supabase")
    monkeypatch.setattr(Config, "SUPABASE_URL", "https://supabase.example")
    monkeypatch.setattr(Config, "SUPABASE_KEY", "service-key")

    ok = dynamic_settings.save_overrides_sync(
        {
            "OPENAI_REALTIME_MODEL": "gpt-realtime-2.1",
            "VOICE": "marin",
            "COMPANY_NAME": "Example Co",
        }
    )

    assert ok is True
    grouped_rows = [row for row in upserts if row["key"] == dynamic_settings.GROUPED_REALTIME_SETTINGS_KEY]
    assert len(grouped_rows) == 1
    grouped_payload = json.loads(grouped_rows[0]["value"])
    assert grouped_payload["OPENAI_REALTIME_MODEL"] == "gpt-realtime-2.1"
    assert grouped_payload["VOICE"] == "marin"
    assert grouped_payload["VAD_MODE"] == "server_vad"
    assert {"key": "COMPANY_NAME", "value": "Example Co"} in upserts
    assert not any(row["key"] == "OPENAI_REALTIME_MODEL" for row in upserts)
    assert not any(row["key"] == "VOICE" for row in upserts)


def test_effective_settings_sources_exclude_secrets(monkeypatch):
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "sk-secret-test")
    monkeypatch.setattr(Config, "OPENAI_REALTIME_MODEL", "gpt-realtime-2.1")

    payload = dynamic_settings.get_effective_settings_with_sources(
        {"OPENAI_REALTIME_MODEL": "gpt-realtime-2.1"}
    )

    assert payload["settings"]["OPENAI_REALTIME_MODEL"]["source"] == "supabase"
    assert payload["settings"]["OPENAI_REALTIME_MODEL"]["value"] == "gpt-realtime-2.1"
    encoded = json.dumps(payload)
    assert "OPENAI_API_KEY" not in encoded
    assert "sk-secret-test" not in encoded


def _request(path: str = "/api/realtime/options") -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [(b"accept", b"application/json")],
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        },
        receive,
    )


def test_realtime_options_endpoint_requires_dashboard_auth(monkeypatch):
    from main import _require_dashboard_key

    monkeypatch.setattr(Config, "DASHBOARD_USERS", "admin:secret")

    with pytest.raises(HTTPException) as exc_info:
        _require_dashboard_key(request=_request(), key=None, x_dashboard_key=None)
    assert exc_info.value.status_code == 401
    _require_dashboard_key(request=_request(), key=None, x_dashboard_key="secret")


def test_dashboard_settings_use_registry_options_endpoint():
    html = (Path(__file__).resolve().parents[1] / "static" / "dashboard.html").read_text(encoding="utf-8")

    assert 'buildDashboardApiUrl("/api/realtime/options")' in html
    assert 'id="setting-VOICE_PROFILE"' in html
    assert "updateReasoningControlState" in html
    assert "gpt-realtime-2.1" in html
