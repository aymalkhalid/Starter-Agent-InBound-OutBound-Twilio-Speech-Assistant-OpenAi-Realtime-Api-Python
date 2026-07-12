"""Isolated effective settings for OpenAI Realtime sessions."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from voice_realtime.models import (
    DEFAULT_REALTIME_MODEL,
    get_realtime_model_capabilities,
    normalize_reasoning_effort,
    validate_realtime_model,
)


DEFAULT_REALTIME_VOICE = "cedar"
SUPPORTED_REALTIME_VOICES = frozenset(
    {
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "sage",
        "shimmer",
        "verse",
        "marin",
        "cedar",
    }
)
RECOMMENDED_REALTIME_VOICES = frozenset({"marin", "cedar"})
SUPPORTED_VAD_MODES = frozenset({"server_vad", "semantic_vad"})
SUPPORTED_VAD_EAGERNESS = frozenset({"low", "medium", "high", "auto"})


def _coerce_bool(raw: Any, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_float(raw: Any, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(raw) if raw is not None and str(raw).strip() != "" else default
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _coerce_int(raw: Any, default: int, minimum: int | None = None) -> int:
    try:
        value = int(raw) if raw is not None and str(raw).strip() != "" else default
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


def sanitize_prompt_control(raw: str | None, default: str, max_length: int = 64) -> str:
    value = " ".join(str(raw or "").split())
    allowed = []
    for char in value:
        if char.isalnum() or char in " -_'/":
            allowed.append(char)
    cleaned = " ".join("".join(allowed).split()).strip(" -_'/")
    return (cleaned[:max_length].strip() or default)


def normalize_realtime_voice(raw: str | None, default: str = DEFAULT_REALTIME_VOICE) -> str:
    voice = (raw or default).strip().lower()
    return voice if voice in SUPPORTED_REALTIME_VOICES else default


def normalize_voice_profile(raw: str | None, default: str = "custom") -> str:
    return sanitize_prompt_control(raw, default, 48).strip().lower().replace(" ", "_")


def normalize_vad_mode(raw: str | None, default: str = "server_vad") -> str:
    mode = (raw or default).strip().lower()
    return mode if mode in SUPPORTED_VAD_MODES else default


def normalize_vad_eagerness(raw: str | None, default: str = "auto") -> str:
    eagerness = (raw or default).strip().lower()
    return eagerness if eagerness in SUPPORTED_VAD_EAGERNESS else default


def normalize_warmth(raw: str | None) -> str:
    value = (raw or "warm").strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"neutral", "warm", "very_warm"}:
        return value
    if value in {"friendly", "high", "extra_warm"}:
        return "very_warm"
    return "warm"


def normalize_expressiveness(raw: str | None) -> str:
    value = (raw or "balanced").strip().lower().replace("-", "_").replace(" ", "_")
    return value if value in {"reserved", "balanced", "expressive"} else "balanced"


def normalize_pacing(raw: str | None) -> str:
    value = (raw or "moderate").strip().lower().replace("-", "_").replace(" ", "_")
    return value if value in {"relaxed", "moderate", "brisk"} else "moderate"


def normalize_accent_strength(raw: str | None) -> str:
    strength = (raw or "light").strip().lower()
    return strength if strength in {"none", "light", "moderate"} else "light"


@dataclass(frozen=True)
class EffectiveRealtimeSettings:
    model: str = DEFAULT_REALTIME_MODEL
    voice: str = DEFAULT_REALTIME_VOICE
    voice_profile: str = "custom"
    reasoning_effort: str | None = "low"
    vad_mode: str = "server_vad"
    vad_eagerness: str = "auto"
    vad_threshold: float = 0.6
    vad_silence_duration_ms: int = 600
    vad_prefix_padding_ms: int = 300
    tone: str = "warm professional"
    warmth: str = "warm"
    expressiveness: str = "balanced"
    pacing: str = "moderate"
    language: str = "English"
    accent: str = "neutral American"
    accent_strength: str = "light"
    preset: str = "custom"
    allow_unregistered_realtime_models: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> "EffectiveRealtimeSettings":
        raw = _canonicalize_settings(values or {})
        allow_unregistered = _coerce_bool(raw.get("allow_unregistered_realtime_models"), False)
        model = validate_realtime_model(raw.get("model"), allow_unregistered=allow_unregistered)
        capabilities = get_realtime_model_capabilities(model, allow_unregistered=allow_unregistered)
        reasoning_effort = normalize_reasoning_effort(raw.get("reasoning_effort"))
        if not capabilities.supports_reasoning_effort:
            reasoning_effort = None
        return cls(
            model=model,
            voice=normalize_realtime_voice(raw.get("voice")),
            voice_profile=normalize_voice_profile(raw.get("voice_profile")),
            reasoning_effort=reasoning_effort,
            vad_mode=normalize_vad_mode(raw.get("vad_mode")),
            vad_eagerness=normalize_vad_eagerness(raw.get("vad_eagerness")),
            vad_threshold=_coerce_float(raw.get("vad_threshold"), 0.6, 0.0, 1.0),
            vad_silence_duration_ms=_coerce_int(raw.get("vad_silence_duration_ms"), 600, 0),
            vad_prefix_padding_ms=_coerce_int(raw.get("vad_prefix_padding_ms"), 300, 0),
            tone=sanitize_prompt_control(raw.get("tone"), "warm professional", 80),
            warmth=normalize_warmth(raw.get("warmth")),
            expressiveness=normalize_expressiveness(raw.get("expressiveness")),
            pacing=normalize_pacing(raw.get("pacing")),
            language=sanitize_prompt_control(raw.get("language"), "English", 48),
            accent=sanitize_prompt_control(raw.get("accent"), "neutral American", 64),
            accent_strength=normalize_accent_strength(raw.get("accent_strength")),
            preset=normalize_voice_profile(raw.get("preset")),
            allow_unregistered_realtime_models=allow_unregistered,
        )

    @classmethod
    def from_config(
        cls,
        config_cls: Any,
        *,
        dynamic_settings: Mapping[str, Any] | None = None,
        temporary_overrides: Mapping[str, Any] | None = None,
    ) -> "EffectiveRealtimeSettings":
        config_values = {
            "OPENAI_REALTIME_MODEL": getattr(config_cls, "OPENAI_REALTIME_MODEL", DEFAULT_REALTIME_MODEL),
            "VOICE": getattr(config_cls, "VOICE", DEFAULT_REALTIME_VOICE),
            "VOICE_PROFILE": getattr(config_cls, "VOICE_PROFILE", "custom"),
            "REALTIME_REASONING_EFFORT": getattr(config_cls, "REALTIME_REASONING_EFFORT", "low"),
            "VAD_MODE": getattr(config_cls, "VAD_MODE", "server_vad"),
            "VAD_EAGERNESS": getattr(config_cls, "VAD_EAGERNESS", "auto"),
            "VAD_THRESHOLD": getattr(config_cls, "VAD_THRESHOLD", 0.6),
            "VAD_SILENCE_DURATION_MS": getattr(config_cls, "VAD_SILENCE_DURATION_MS", 600),
            "VAD_PREFIX_PADDING_MS": getattr(config_cls, "VAD_PREFIX_PADDING_MS", 300),
            "ASSISTANT_TONE": getattr(config_cls, "ASSISTANT_TONE", "warm professional"),
            "ASSISTANT_WARMTH": getattr(config_cls, "ASSISTANT_WARMTH", "warm"),
            "ASSISTANT_EXPRESSIVENESS": getattr(config_cls, "ASSISTANT_EXPRESSIVENESS", "balanced"),
            "ASSISTANT_PACING": getattr(config_cls, "ASSISTANT_PACING", "moderate"),
            "ASSISTANT_LANGUAGE": getattr(config_cls, "ASSISTANT_LANGUAGE", "English"),
            "ASSISTANT_ACCENT": getattr(config_cls, "ASSISTANT_ACCENT", "neutral American"),
            "ASSISTANT_ACCENT_STRENGTH": getattr(config_cls, "ASSISTANT_ACCENT_STRENGTH", "light"),
            "ALLOW_UNREGISTERED_REALTIME_MODELS": getattr(
                config_cls,
                "ALLOW_UNREGISTERED_REALTIME_MODELS",
                False,
            ),
        }
        return resolve_effective_realtime_settings(
            env_settings=config_values,
            dynamic_settings=dynamic_settings,
            temporary_overrides=temporary_overrides,
        )

    def with_overrides(self, overrides: Mapping[str, Any] | None = None) -> "EffectiveRealtimeSettings":
        if not overrides:
            return self
        merged = self.to_mapping()
        merged.update(_canonicalize_settings(overrides))
        return self.from_mapping(merged)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "voice": self.voice,
            "voice_profile": self.voice_profile,
            "reasoning_effort": self.reasoning_effort,
            "vad_mode": self.vad_mode,
            "vad_eagerness": self.vad_eagerness,
            "vad_threshold": self.vad_threshold,
            "vad_silence_duration_ms": self.vad_silence_duration_ms,
            "vad_prefix_padding_ms": self.vad_prefix_padding_ms,
            "tone": self.tone,
            "warmth": self.warmth,
            "expressiveness": self.expressiveness,
            "pacing": self.pacing,
            "language": self.language,
            "accent": self.accent,
            "accent_strength": self.accent_strength,
            "preset": self.preset,
            "allow_unregistered_realtime_models": self.allow_unregistered_realtime_models,
        }


_SETTING_ALIASES = {
    "OPENAI_REALTIME_MODEL": "model",
    "model": "model",
    "VOICE": "voice",
    "voice": "voice",
    "VOICE_PROFILE": "voice_profile",
    "voice_profile": "voice_profile",
    "REALTIME_REASONING_EFFORT": "reasoning_effort",
    "reasoning_effort": "reasoning_effort",
    "VAD_MODE": "vad_mode",
    "vad_mode": "vad_mode",
    "VAD_EAGERNESS": "vad_eagerness",
    "vad_eagerness": "vad_eagerness",
    "VAD_THRESHOLD": "vad_threshold",
    "vad_threshold": "vad_threshold",
    "VAD_SILENCE_DURATION_MS": "vad_silence_duration_ms",
    "vad_silence_duration_ms": "vad_silence_duration_ms",
    "VAD_PREFIX_PADDING_MS": "vad_prefix_padding_ms",
    "vad_prefix_padding_ms": "vad_prefix_padding_ms",
    "ASSISTANT_TONE": "tone",
    "tone": "tone",
    "ASSISTANT_WARMTH": "warmth",
    "warmth": "warmth",
    "ASSISTANT_EXPRESSIVENESS": "expressiveness",
    "expressiveness": "expressiveness",
    "ASSISTANT_PACING": "pacing",
    "pacing": "pacing",
    "ASSISTANT_LANGUAGE": "language",
    "language": "language",
    "ASSISTANT_ACCENT": "accent",
    "accent": "accent",
    "ASSISTANT_ACCENT_STRENGTH": "accent_strength",
    "accent_strength": "accent_strength",
    "preset": "preset",
    "PRESET": "preset",
    "ALLOW_UNREGISTERED_REALTIME_MODELS": "allow_unregistered_realtime_models",
    "allow_unregistered_realtime_models": "allow_unregistered_realtime_models",
}


def _canonicalize_settings(values: Mapping[str, Any]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for key, value in values.items():
        target = _SETTING_ALIASES.get(str(key), _SETTING_ALIASES.get(str(key).upper()))
        if target:
            canonical[target] = value
    return canonical


def resolve_effective_realtime_settings(
    *,
    env_settings: Mapping[str, Any] | None = None,
    dynamic_settings: Mapping[str, Any] | None = None,
    temporary_overrides: Mapping[str, Any] | None = None,
) -> EffectiveRealtimeSettings:
    """Resolve settings with precedence: temporary, dynamic, env, defaults."""
    merged: dict[str, Any] = {}
    merged.update(_canonicalize_settings(env_settings or {}))
    merged.update(_canonicalize_settings(dynamic_settings or {}))
    merged.update(_canonicalize_settings(temporary_overrides or {}))
    return EffectiveRealtimeSettings.from_mapping(merged)


def clone_effective_realtime_settings(settings: EffectiveRealtimeSettings) -> EffectiveRealtimeSettings:
    """Return a detached copy; useful when callers need explicit isolation."""
    return replace(settings)
