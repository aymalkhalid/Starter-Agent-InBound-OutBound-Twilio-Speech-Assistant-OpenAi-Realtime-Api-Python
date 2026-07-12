"""Controlled presets for Realtime model and voice testing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from voice_realtime.settings import EffectiveRealtimeSettings


CUSTOM_PRESET_ID = "custom"


@dataclass(frozen=True)
class RealtimeVoicePreset:
    preset_id: str
    display_name: str
    model: str
    voice: str
    vad_mode: str
    vad_eagerness: str
    reasoning_effort: str | None
    tone: str
    warmth: str
    expressiveness: str
    pacing: str

    def to_overrides(self) -> dict[str, Any]:
        return {
            "preset": self.preset_id,
            "voice_profile": self.preset_id,
            "model": self.model,
            "voice": self.voice,
            "vad_mode": self.vad_mode,
            "vad_eagerness": self.vad_eagerness,
            "reasoning_effort": self.reasoning_effort,
            "tone": self.tone,
            "warmth": self.warmth,
            "expressiveness": self.expressiveness,
            "pacing": self.pacing,
        }


VOICE_PRESETS: dict[str, RealtimeVoicePreset] = {
    "quality": RealtimeVoicePreset(
        preset_id="quality",
        display_name="High-fidelity quality",
        model="gpt-realtime-2.1",
        voice="marin",
        vad_mode="semantic_vad",
        vad_eagerness="low",
        reasoning_effort="low",
        tone="warm conversational professional",
        warmth="warm",
        expressiveness="balanced",
        pacing="moderate",
    ),
    "professional_phone": RealtimeVoicePreset(
        preset_id="professional_phone",
        display_name="Professional phone",
        model="gpt-realtime-2.1",
        voice="cedar",
        vad_mode="semantic_vad",
        vad_eagerness="low",
        reasoning_effort="low",
        tone="warm professional",
        warmth="warm",
        expressiveness="balanced",
        pacing="moderate",
    ),
    "cost_optimized": RealtimeVoicePreset(
        preset_id="cost_optimized",
        display_name="Cost optimized",
        model="gpt-realtime-2.1-mini",
        voice="marin",
        vad_mode="semantic_vad",
        vad_eagerness="low",
        reasoning_effort=None,
        tone="warm professional",
        warmth="warm",
        expressiveness="balanced",
        pacing="moderate",
    ),
}


def list_voice_presets() -> list[RealtimeVoicePreset]:
    return [VOICE_PRESETS[key] for key in ("quality", "professional_phone", "cost_optimized")]


def get_voice_preset(preset_id: str) -> RealtimeVoicePreset:
    key = (preset_id or "").strip().lower()
    if key not in VOICE_PRESETS:
        known = ", ".join(sorted(VOICE_PRESETS))
        raise ValueError(f"Unknown voice preset '{preset_id}'. Known presets: {known}.")
    return VOICE_PRESETS[key]


def apply_voice_preset(
    preset_id: str,
    base_settings: EffectiveRealtimeSettings | None = None,
) -> EffectiveRealtimeSettings:
    preset = get_voice_preset(preset_id)
    base = base_settings or EffectiveRealtimeSettings()
    return base.with_overrides(preset.to_overrides())


def detect_voice_preset(settings: EffectiveRealtimeSettings) -> str:
    for preset in VOICE_PRESETS.values():
        preset_settings = apply_voice_preset(preset.preset_id, settings.with_overrides({"preset": CUSTOM_PRESET_ID}))
        comparable = (
            settings.model == preset_settings.model
            and settings.voice == preset_settings.voice
            and settings.vad_mode == preset_settings.vad_mode
            and settings.vad_eagerness == preset_settings.vad_eagerness
            and settings.reasoning_effort == preset_settings.reasoning_effort
            and settings.tone == preset_settings.tone
            and settings.warmth == preset_settings.warmth
            and settings.expressiveness == preset_settings.expressiveness
            and settings.pacing == preset_settings.pacing
        )
        if comparable:
            return preset.preset_id
    return CUSTOM_PRESET_ID
