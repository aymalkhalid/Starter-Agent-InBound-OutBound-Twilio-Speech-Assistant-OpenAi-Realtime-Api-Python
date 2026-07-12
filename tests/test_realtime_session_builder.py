import pytest

from voice_realtime.models import RealtimeModelValidationError
from voice_realtime.session_builder import TRANSPORT_BROWSER, TRANSPORT_TWILIO, build_realtime_session
from voice_realtime.settings import EffectiveRealtimeSettings


def _settings(**overrides):
    return EffectiveRealtimeSettings.from_mapping(
        {
            "OPENAI_REALTIME_MODEL": "gpt-realtime-2.1",
            "VOICE": "marin",
            "VAD_MODE": "semantic_vad",
            "VAD_EAGERNESS": "low",
            "REALTIME_REASONING_EFFORT": "medium",
            **overrides,
        }
    )


def test_twilio_session_payload_preserves_pcmu_and_common_fields():
    payload = build_realtime_session(
        TRANSPORT_TWILIO,
        _settings(),
        "instructions",
        [{"type": "function", "name": "wait_for_user"}],
    )

    assert payload["model"] == "gpt-realtime-2.1"
    assert payload["instructions"] == "instructions"
    assert payload["tools"][0]["name"] == "wait_for_user"
    assert payload["audio"]["input"]["format"] == {"type": "audio/pcmu"}
    assert payload["audio"]["output"]["format"] == {"type": "audio/pcmu"}
    assert payload["audio"]["output"]["voice"] == "marin"
    assert payload["audio"]["input"]["turn_detection"] == {
        "type": "semantic_vad",
        "eagerness": "low",
        "create_response": True,
        "interrupt_response": True,
    }
    assert payload["reasoning"] == {"effort": "medium"}


def test_browser_session_payload_does_not_inherit_twilio_pcmu():
    payload = build_realtime_session(
        TRANSPORT_BROWSER,
        _settings(),
        "instructions",
        [],
    )

    assert "format" not in payload["audio"]["input"]
    assert "format" not in payload["audio"]["output"]
    assert payload["audio"]["output"]["voice"] == "marin"


def test_server_vad_payload_contains_server_fields_and_turn_flags():
    payload = build_realtime_session(
        TRANSPORT_TWILIO,
        _settings(
            VAD_MODE="server_vad",
            VAD_THRESHOLD=0.7,
            VAD_SILENCE_DURATION_MS=800,
            VAD_PREFIX_PADDING_MS=250,
        ),
        "instructions",
        [],
    )

    assert payload["audio"]["input"]["turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.7,
        "silence_duration_ms": 800,
        "prefix_padding_ms": 250,
        "create_response": True,
        "interrupt_response": True,
    }


def test_mini_session_omits_unsupported_reasoning_effort():
    payload = build_realtime_session(
        TRANSPORT_TWILIO,
        _settings(OPENAI_REALTIME_MODEL="gpt-realtime-2.1-mini", REALTIME_REASONING_EFFORT="high"),
        "instructions",
        [],
    )

    assert payload["model"] == "gpt-realtime-2.1-mini"
    assert "reasoning" not in payload


def test_unknown_model_rejected_before_session_payload():
    with pytest.raises(RealtimeModelValidationError):
        _settings(OPENAI_REALTIME_MODEL="gpt-realtime-future")
