"""Dashboard-safe Realtime option metadata sourced from registries."""
from __future__ import annotations

from voice_realtime.models import REALTIME_MODEL_REGISTRY, REALTIME_REASONING_EFFORT_VALUES
from voice_realtime.presets import list_voice_presets
from voice_realtime.settings import (
    RECOMMENDED_REALTIME_VOICES,
    SUPPORTED_REALTIME_VOICES,
    SUPPORTED_VAD_EAGERNESS,
    SUPPORTED_VAD_MODES,
)


VOICE_ORDER = ["marin", "cedar", "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"]
MODEL_ORDER = ["gpt-realtime-2.1", "gpt-realtime-2", "gpt-realtime-2.1-mini"]
REASONING_ORDER = ["minimal", "low", "medium", "high", "xhigh"]
VAD_MODE_ORDER = ["semantic_vad", "server_vad"]
VAD_EAGERNESS_ORDER = ["low", "medium", "high", "auto"]


def get_realtime_options_payload() -> dict:
    """Return model/voice/preset metadata safe for browser dashboard use."""
    models = []
    for model_id in MODEL_ORDER:
        capabilities = REALTIME_MODEL_REGISTRY[model_id]
        models.append(
            {
                "id": capabilities.model_id,
                "display_name": capabilities.display_name,
                "supports_reasoning_effort": capabilities.supports_reasoning_effort,
                "supports_audio": capabilities.supports_audio,
                "supports_function_calling": capabilities.supports_function_calling,
                "production_recommendation": capabilities.production_recommendation,
                "cost_tier": capabilities.cost_tier,
            }
        )
    voices = [
        {
            "id": voice,
            "display_name": voice,
            "recommended": voice in RECOMMENDED_REALTIME_VOICES,
        }
        for voice in VOICE_ORDER
        if voice in SUPPORTED_REALTIME_VOICES
    ]
    presets = [
        {
            "id": preset.preset_id,
            "display_name": preset.display_name,
            "settings": preset.to_overrides(),
        }
        for preset in list_voice_presets()
    ]
    return {
        "models": models,
        "voices": voices,
        "presets": presets,
        "vad_modes": [mode for mode in VAD_MODE_ORDER if mode in SUPPORTED_VAD_MODES],
        "vad_eagerness": [
            eagerness for eagerness in VAD_EAGERNESS_ORDER if eagerness in SUPPORTED_VAD_EAGERNESS
        ],
        "reasoning_efforts": [
            effort for effort in REASONING_ORDER if effort in REALTIME_REASONING_EFFORT_VALUES
        ],
    }
