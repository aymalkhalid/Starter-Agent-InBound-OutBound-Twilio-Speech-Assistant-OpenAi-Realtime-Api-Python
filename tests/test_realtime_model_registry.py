import pytest

from voice_realtime.models import (
    RealtimeModelValidationError,
    get_realtime_model_capabilities,
    realtime_model_supports_reasoning_effort,
    validate_realtime_model,
)


def test_registry_contains_required_realtime_models():
    assert get_realtime_model_capabilities("gpt-realtime-2").display_name == "GPT-Realtime-2"
    assert get_realtime_model_capabilities("gpt-realtime-2.1").display_name == "GPT-Realtime-2.1"
    mini = get_realtime_model_capabilities("gpt-realtime-2.1-mini")
    assert mini.supports_audio is True
    assert mini.supports_function_calling is True
    assert mini.cost_tier == "low"


def test_registry_reasoning_effort_capabilities_are_explicit():
    assert realtime_model_supports_reasoning_effort("gpt-realtime-2") is True
    assert realtime_model_supports_reasoning_effort("gpt-realtime-2.1") is True
    assert realtime_model_supports_reasoning_effort("gpt-realtime-2.1-mini") is False


def test_unknown_realtime_model_rejected_by_default():
    with pytest.raises(RealtimeModelValidationError):
        validate_realtime_model("gpt-realtime-future")


def test_unknown_realtime_model_can_be_allowed_without_reasoning_support():
    capabilities = get_realtime_model_capabilities(
        "gpt-realtime-future",
        allow_unregistered=True,
    )
    assert capabilities.model_id == "gpt-realtime-future"
    assert capabilities.registered is False
    assert capabilities.supports_reasoning_effort is False
