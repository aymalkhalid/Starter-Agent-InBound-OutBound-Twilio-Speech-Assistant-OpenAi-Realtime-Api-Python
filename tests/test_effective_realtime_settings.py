from config import Config
from voice_realtime.presets import apply_voice_preset, detect_voice_preset
from voice_realtime.settings import EffectiveRealtimeSettings, resolve_effective_realtime_settings


def test_effective_settings_precedence_temporary_dynamic_env_defaults():
    settings = resolve_effective_realtime_settings(
        env_settings={
            "OPENAI_REALTIME_MODEL": "gpt-realtime-2",
            "VOICE": "cedar",
            "VAD_MODE": "server_vad",
        },
        dynamic_settings={
            "OPENAI_REALTIME_MODEL": "gpt-realtime-2.1",
            "VOICE": "marin",
            "VAD_MODE": "semantic_vad",
            "VAD_EAGERNESS": "medium",
        },
        temporary_overrides={
            "VOICE": "ash",
            "VAD_EAGERNESS": "low",
        },
    )

    assert settings.model == "gpt-realtime-2.1"
    assert settings.voice == "ash"
    assert settings.vad_mode == "semantic_vad"
    assert settings.vad_eagerness == "low"


def test_effective_settings_temporary_overrides_do_not_mutate_config(monkeypatch):
    monkeypatch.setattr(Config, "OPENAI_REALTIME_MODEL", "gpt-realtime-2")
    monkeypatch.setattr(Config, "VOICE", "cedar")

    settings = EffectiveRealtimeSettings.from_config(
        Config,
        temporary_overrides={
            "OPENAI_REALTIME_MODEL": "gpt-realtime-2.1",
            "VOICE": "marin",
        },
    )

    assert settings.model == "gpt-realtime-2.1"
    assert settings.voice == "marin"
    assert Config.OPENAI_REALTIME_MODEL == "gpt-realtime-2"
    assert Config.VOICE == "cedar"


def test_effective_settings_for_mini_omit_reasoning_effort():
    settings = EffectiveRealtimeSettings.from_mapping(
        {
            "OPENAI_REALTIME_MODEL": "gpt-realtime-2.1-mini",
            "REALTIME_REASONING_EFFORT": "high",
        }
    )

    assert settings.model == "gpt-realtime-2.1-mini"
    assert settings.reasoning_effort is None


def test_voice_presets_populate_fields_and_custom_detection():
    quality = apply_voice_preset("quality")
    assert quality.model == "gpt-realtime-2.1"
    assert quality.voice == "marin"
    assert quality.vad_mode == "semantic_vad"
    assert quality.vad_eagerness == "low"
    assert quality.reasoning_effort == "low"
    assert detect_voice_preset(quality) == "quality"

    edited = quality.with_overrides({"VOICE": "cedar"})
    assert detect_voice_preset(edited) == "custom"


def test_cost_optimized_preset_uses_mini_without_reasoning_effort():
    settings = apply_voice_preset("cost_optimized")
    assert settings.model == "gpt-realtime-2.1-mini"
    assert settings.voice == "marin"
    assert settings.reasoning_effort is None
