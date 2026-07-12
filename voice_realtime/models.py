"""Central Realtime model capability registry."""
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_REALTIME_MODEL = "gpt-realtime-2"
REALTIME_REASONING_EFFORT_VALUES = frozenset({"minimal", "low", "medium", "high", "xhigh"})


class RealtimeModelValidationError(ValueError):
    """Raised when a Realtime model is not registered or is incompatible."""


@dataclass(frozen=True)
class RealtimeModelCapabilities:
    model_id: str
    display_name: str
    supports_reasoning_effort: bool
    supports_audio: bool
    supports_function_calling: bool
    production_recommendation: str
    cost_tier: str
    registered: bool = True


REALTIME_MODEL_REGISTRY: dict[str, RealtimeModelCapabilities] = {
    "gpt-realtime-2": RealtimeModelCapabilities(
        model_id="gpt-realtime-2",
        display_name="GPT-Realtime-2",
        supports_reasoning_effort=True,
        supports_audio=True,
        supports_function_calling=True,
        production_recommendation="supported_reasoning_voice",
        cost_tier="high",
    ),
    "gpt-realtime-2.1": RealtimeModelCapabilities(
        model_id="gpt-realtime-2.1",
        display_name="GPT-Realtime-2.1",
        supports_reasoning_effort=True,
        supports_audio=True,
        supports_function_calling=True,
        production_recommendation="recommended_quality",
        cost_tier="high",
    ),
    "gpt-realtime-2.1-mini": RealtimeModelCapabilities(
        model_id="gpt-realtime-2.1-mini",
        display_name="GPT-Realtime-2.1 Mini",
        supports_reasoning_effort=False,
        supports_audio=True,
        supports_function_calling=True,
        production_recommendation="cost_optimized",
        cost_tier="low",
    ),
}


def normalize_realtime_model_id(raw: str | None, default: str = DEFAULT_REALTIME_MODEL) -> str:
    """Normalize a model id without falling back for unknown non-empty values."""
    model_id = (raw or default).strip()
    return model_id or default


def normalize_reasoning_effort(raw: str | None, default: str = "low") -> str:
    """Return a supported Realtime reasoning effort."""
    effort = (raw or default).strip().lower()
    return effort if effort in REALTIME_REASONING_EFFORT_VALUES else default


def get_realtime_model_capabilities(
    model_id: str | None,
    *,
    allow_unregistered: bool = False,
) -> RealtimeModelCapabilities:
    """Return capabilities for a Realtime model or raise a clear validation error."""
    normalized = normalize_realtime_model_id(model_id)
    capabilities = REALTIME_MODEL_REGISTRY.get(normalized)
    if capabilities:
        return capabilities
    if allow_unregistered:
        return RealtimeModelCapabilities(
            model_id=normalized,
            display_name=normalized,
            supports_reasoning_effort=False,
            supports_audio=True,
            supports_function_calling=True,
            production_recommendation="unregistered",
            cost_tier="unknown",
            registered=False,
        )
    known = ", ".join(sorted(REALTIME_MODEL_REGISTRY))
    raise RealtimeModelValidationError(
        f"Unknown OpenAI Realtime model '{normalized}'. Add it to REALTIME_MODEL_REGISTRY "
        f"or set ALLOW_UNREGISTERED_REALTIME_MODELS=true. Known models: {known}."
    )


def validate_realtime_model(
    model_id: str | None,
    *,
    allow_unregistered: bool = False,
) -> str:
    """Validate a Realtime model id and return the normalized id."""
    return get_realtime_model_capabilities(
        model_id,
        allow_unregistered=allow_unregistered,
    ).model_id


def realtime_model_supports_reasoning_effort(
    model_id: str | None,
    *,
    allow_unregistered: bool = False,
) -> bool:
    """Return True when the registry confirms configurable reasoning effort support."""
    return get_realtime_model_capabilities(
        model_id,
        allow_unregistered=allow_unregistered,
    ).supports_reasoning_effort
