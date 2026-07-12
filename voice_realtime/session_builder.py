"""Transport-aware OpenAI Realtime session payload builder."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from voice_realtime.models import get_realtime_model_capabilities
from voice_realtime.settings import EffectiveRealtimeSettings


TRANSPORT_TWILIO = "twilio"
TRANSPORT_BROWSER = "browser"
SUPPORTED_REALTIME_TRANSPORTS = frozenset({TRANSPORT_TWILIO, TRANSPORT_BROWSER})


class RealtimeSessionBuildError(ValueError):
    """Raised when a Realtime session cannot be built safely."""


def build_turn_detection(settings: EffectiveRealtimeSettings) -> dict[str, Any]:
    if settings.vad_mode == "semantic_vad":
        return {
            "type": "semantic_vad",
            "eagerness": settings.vad_eagerness,
            "create_response": True,
            "interrupt_response": True,
        }
    return {
        "type": "server_vad",
        "threshold": settings.vad_threshold,
        "silence_duration_ms": settings.vad_silence_duration_ms,
        "prefix_padding_ms": settings.vad_prefix_padding_ms,
        "create_response": True,
        "interrupt_response": True,
    }


def build_realtime_session(
    transport: str,
    effective_settings: EffectiveRealtimeSettings,
    instructions: str,
    tools: Sequence[Mapping[str, Any]] | None,
    *,
    input_transcription: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Realtime session payload shared by Twilio and browser transports."""
    transport_id = (transport or "").strip().lower()
    if transport_id not in SUPPORTED_REALTIME_TRANSPORTS:
        raise RealtimeSessionBuildError(
            f"Unsupported Realtime transport '{transport}'. Expected one of: "
            f"{', '.join(sorted(SUPPORTED_REALTIME_TRANSPORTS))}."
        )
    capabilities = get_realtime_model_capabilities(
        effective_settings.model,
        allow_unregistered=effective_settings.allow_unregistered_realtime_models,
    )
    if not capabilities.supports_audio:
        raise RealtimeSessionBuildError(
            f"Realtime model '{effective_settings.model}' does not support audio sessions."
        )
    session_tools = list(tools or [])
    if session_tools and not capabilities.supports_function_calling:
        raise RealtimeSessionBuildError(
            f"Realtime model '{effective_settings.model}' does not support function calling."
        )

    audio_input: dict[str, Any] = {
        "turn_detection": build_turn_detection(effective_settings),
    }
    audio_output: dict[str, Any] = {
        "voice": effective_settings.voice,
    }
    if input_transcription:
        audio_input["transcription"] = dict(input_transcription)
    if transport_id == TRANSPORT_TWILIO:
        audio_input["format"] = {"type": "audio/pcmu"}
        audio_output["format"] = {"type": "audio/pcmu"}

    session_payload: dict[str, Any] = {
        "type": "realtime",
        "model": effective_settings.model,
        "output_modalities": ["audio"],
        "audio": {
            "input": audio_input,
            "output": audio_output,
        },
        "instructions": instructions,
        "tools": session_tools,
    }
    if capabilities.supports_reasoning_effort and effective_settings.reasoning_effort:
        session_payload["reasoning"] = {"effort": effective_settings.reasoning_effort}
    return session_payload
