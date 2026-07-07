"""Tests for the clean starter prompt layer."""
from pathlib import Path

import pytest

from portfolio_samples import SAMPLE_PROMPTS
from config import Config, rebuild_system_message
from services.openai_service import OpenAISessionManager, OpenAIService
from system_instructions import (
    DEFAULT_SYSTEM_INSTRUCTIONS_PATH,
    REQUIRED_PROMPT_PLACEHOLDERS,
    get_greeting_instruction,
    load_system_instructions,
    render_system_instructions,
)

_PROMPT_KWARGS = {
    "company_name": "Example Co",
    "agent_name": "Alex",
    "delivery_instruction": "# Delivery Style\nTarget tone: warm professional.",
    "language_instruction": "# Language\nUse English.",
    "accent_instruction": "# Accent\nUse clear phone speech.",
    "reasoning_effort_instruction": "## Reasoning effort\nSession API reasoning effort is `low`.",
    "tools_availability_instruction": "## Tool Availability\nAvailable in this session:\n- `wait_for_user`",
    "call_record_instruction": "Use save_call_record for follow-up.",
    "booking_instruction": "Booking tools are disabled.",
    "transfer_instruction": "Transfer is disabled.",
    "instructions_path": "prompts/main_system_instructions.md",
}

_APPOINTMENT_SETTER_PROMPT_KWARGS = {
    **_PROMPT_KWARGS,
    "instructions_path": "prompts/aesthetic_appointment_setter.md",
}

_GENERIC_APPOINTMENT_SETTER_PROMPT_KWARGS = {
    **_PROMPT_KWARGS,
    "instructions_path": "prompts/generic_appointment_setter.md",
}

_SAMPLE_PROMPT_PATHS = tuple(SAMPLE_PROMPTS.values())


def test_main_system_instructions_file_is_single_source_of_truth():
    assert DEFAULT_SYSTEM_INSTRUCTIONS_PATH.is_file()
    template = load_system_instructions()
    for placeholder in REQUIRED_PROMPT_PLACEHOLDERS:
        assert placeholder in template, f"missing placeholder {placeholder}"


def test_load_system_instructions_raises_when_file_missing():
    with pytest.raises(FileNotFoundError, match="System instructions file not found"):
        load_system_instructions("prompts/does-not-exist.md")


def test_prompt_file_renders_generic_voice_agent():
    prompt = render_system_instructions(**_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "generic business voice agent" in lower
    assert "save_call_record" in prompt
    assert "wait_for_user" in prompt
    assert "unclear audio" in lower or "unclear" in lower
    assert "verbosity" in lower
    assert "delivery style" in lower
    assert "get_availability" in prompt
    assert "plumbing" not in lower
    assert "industry" not in lower


def test_aesthetic_appointment_setter_prompt_has_required_placeholders():
    template = load_system_instructions("prompts/aesthetic_appointment_setter.md")
    for placeholder in REQUIRED_PROMPT_PLACEHOLDERS:
        assert placeholder in template, f"missing placeholder {placeholder}"


def test_generic_appointment_setter_prompt_has_required_placeholders():
    template = load_system_instructions("prompts/generic_appointment_setter.md")
    for placeholder in REQUIRED_PROMPT_PLACEHOLDERS:
        assert placeholder in template, f"missing placeholder {placeholder}"


def test_generic_appointment_setter_prompt_renders_reusable_flow():
    prompt = render_system_instructions(**_GENERIC_APPOINTMENT_SETTER_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "outbound appointment-setting voice agent" in lower
    assert "contact context" in lower
    assert "use `get_availability` before offering exact times" in lower
    assert "business time" in lower
    assert "do not call it \"my time\"" in lower
    assert "aesthetic clinic" not in lower
    assert "botox" not in lower
    assert "t-shape" not in lower
    assert "save_call_record" in prompt
    assert "book_appointment" in prompt
    assert "wait_for_user" in prompt
    for placeholder in REQUIRED_PROMPT_PLACEHOLDERS:
        assert placeholder not in prompt, f"unrendered placeholder {placeholder}"


@pytest.mark.parametrize("instructions_path", _SAMPLE_PROMPT_PATHS)
def test_portfolio_sample_prompts_keep_required_placeholder_contract(instructions_path):
    template = load_system_instructions(instructions_path)
    for placeholder in REQUIRED_PROMPT_PLACEHOLDERS:
        assert placeholder in template, f"{instructions_path} missing placeholder {placeholder}"


@pytest.mark.parametrize("instructions_path", _SAMPLE_PROMPT_PATHS)
def test_portfolio_sample_prompts_render_core_tool_guidance(instructions_path):
    prompt = render_system_instructions(**{**_PROMPT_KWARGS, "instructions_path": instructions_path})
    lower = prompt.lower()
    assert "save_call_record" in prompt
    assert "booking" in lower
    assert "handoff" in lower
    assert "available tool names may include" in lower
    assert "use only tools present in the current session" in lower
    for placeholder in REQUIRED_PROMPT_PLACEHOLDERS:
        assert placeholder not in prompt, f"{instructions_path} has unrendered placeholder {placeholder}"


@pytest.mark.parametrize("instructions_path", _SAMPLE_PROMPT_PATHS)
def test_portfolio_sample_prompts_follow_shared_quality_contract(instructions_path):
    template = load_system_instructions(instructions_path)
    lower = template.lower()
    for heading in (
        "# Role and Objective",
        "# Conversation Flow",
        "# Booking",
        "# Call Records",
        "# Human Handoff",
        "# Voice and Language",
        "# Tools",
    ):
        assert heading in template, f"{instructions_path} missing {heading}"

    assert "boundaries" in lower or "safety" in lower, f"{instructions_path} needs a boundary/safety section"
    assert "ask one question" in lower, f"{instructions_path} should ask one question at a time"
    assert "use only tools present in the current session" in lower
    assert "confirm before write actions" in lower
    assert "save a call record" in lower or "save_call_record" in template
    assert "handoff" in lower
    assert (
        "do not say the appointment, meeting, callback slot, handoff, or saved record is complete "
        "until the related tool succeeds"
    ) in lower


def test_sample_prompt_quality_doc_is_linked_and_actionable():
    root = Path(__file__).resolve().parents[1]
    doc = (root / "docs" / "SAMPLE_PROMPT_QUALITY.md").read_text(encoding="utf-8")
    portfolio_doc = (root / "docs" / "PORTFOLIO_SAMPLES.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    docs_index = (root / "docs" / "README.md").read_text(encoding="utf-8")

    assert "Sample Prompt Quality Checklist" in doc
    assert "Required Sections" in doc
    assert "Required Placeholders" in doc
    assert "Shared Behavior Rules" in doc
    assert "`# Role and Objective`" in doc
    assert "`# Booking`" in doc
    assert "`# Call Records`" in doc
    assert "`# Human Handoff`" in doc
    assert "{booking_instruction}" in doc
    assert "{call_record_instruction}" in doc
    assert "{transfer_instruction}" in doc
    assert "Ask one question at a time." in doc
    assert "Use only tools present in the current Realtime session." in doc
    assert "Do not say the appointment, meeting, callback slot, handoff, or saved record" in doc
    assert "docs/PORTFOLIO_DEMO_ACCEPTANCE.md" in doc
    assert "SAMPLE_PROMPT_QUALITY.md" in portfolio_doc
    assert "SAMPLE_PROMPT_QUALITY.md" in readme
    assert "SAMPLE_PROMPT_QUALITY.md" in docs_index


def test_aesthetic_appointment_setter_prompt_renders_core_flow():
    prompt = render_system_instructions(**_APPOINTMENT_SETTER_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "outbound aesthetic clinic" in lower
    assert "appointment setter" in lower
    assert "wrinkle reset" in lower
    assert "t-shape 2" in lower
    assert "deposit" in lower
    assert "pacific time" in lower
    assert "for you, i have monday at 2 pm central" in lower
    assert "1 pm pacific at the clinic" in lower
    assert "do not\ncall the clinic timezone \"my time\"" in lower
    assert "get_availability" in prompt
    assert "book_appointment" in prompt
    assert "save_call_record" in prompt
    assert "request_human_handoff" in prompt
    assert "wait_for_user" in prompt
    assert "get_slots_tool" not in prompt
    assert "create_appointment_tool" not in prompt
    assert "update_contact_data_tool" not in prompt
    assert "transfer_call" not in prompt
    for placeholder in REQUIRED_PROMPT_PLACEHOLDERS:
        assert placeholder not in prompt, f"unrendered placeholder {placeholder}"


def test_aesthetic_appointment_setter_prompt_uses_lead_data_in_opener():
    prompt = render_system_instructions(**_APPOINTMENT_SETTER_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "use the contact name when available" in lower
    assert "reference the offer" in lower
    assert "do not mention phone, email" in lower
    assert "Hi [contact name], this is Alex" in prompt


def test_aesthetic_appointment_setter_prompt_locks_booking_sequence():
    prompt = render_system_instructions(**_APPOINTMENT_SETTER_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "use `get_availability` before offering exact times" in lower
    assert "offer no more than two times at" in lower
    assert "ask for consent to the deposit" in lower
    assert "silence is not consent" in lower
    assert "call `book_appointment` only after all of these are true" in lower
    assert "`get_availability` returned the chosen slot" in lower
    assert "the caller explicitly agreed to the deposit flow" in lower
    assert "appointment is booked until `book_appointment` succeeds" in lower
    assert "caller accepted the $29 secure-link deposit with" in lower
    assert "go to transfer to human" in lower


def test_aesthetic_appointment_setter_prompt_defines_outcome_tags():
    prompt = render_system_instructions(**_APPOINTMENT_SETTER_PROMPT_KWARGS)
    assert "exactly\none `outcome_tag`" in prompt
    for tag in (
        "booked",
        "interested-callback",
        "declined",
        "do-not-contact",
        "wrong-person",
        "transfer-needed",
        "booking-error",
    ):
        assert f"`{tag}`" in prompt
    assert "Do not invent other outcome tags." in prompt


def test_prompt_includes_openai_aligned_preamble_guidance():
    prompt = render_system_instructions(**_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "when to use a preamble" in lower
    assert "when not to use a preamble" in lower
    assert "request_human_handoff" in prompt
    assert "let me think" in lower


def test_prompt_includes_reasoning_and_verbosity_guidance():
    prompt = render_system_instructions(**_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "respond quickly and do not reason" in lower
    assert "do not perform extended reasoning when the caller's audio is unclear" in lower
    assert "session api reasoning effort is `low`" in lower
    assert "product or option comparisons" in lower
    assert "example comparison style" in lower


def test_prompt_includes_instruction_precision_guidance():
    prompt = render_system_instructions(**_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "instruction precision" in lower
    assert "avoid broad scope" in lower
    assert "confirmation code" in lower
    assert "always ask for confirmation before doing anything" in lower


def test_prompt_includes_tool_behavior_and_failure_recovery():
    prompt = render_system_instructions(**_PROMPT_KWARGS)
    lower = prompt.lower()
    assert "tool availability" in lower
    assert "tool-call eagerness" in lower
    assert "tool failures" in lower
    assert "booking timezones" in lower
    assert "appointment or business timezone as the booking authority" in lower
    assert "never offer or confirm a bare time when caller timezone may differ" in lower
    assert "caller-local time first" in lower
    assert "business time" in lower
    assert "never call it \"my time\"" in lower
    assert "do not repeatedly call the same tool with the same arguments after failure" in lower
    assert "entity collection order" in lower
    assert "spelled-out characters" in lower
    assert "spoken number handling" in lower
    assert "email confirmation" in lower
    assert "entity collection workflow" in lower
    assert "never call tools with guessed, partial, ambiguous, or unconfirmed exact values" in lower
    assert "exact iso slot values" in lower


def test_build_tools_availability_instruction_lists_core_tools(monkeypatch):
    from config import _build_tools_availability_instruction

    monkeypatch.setattr("services.call_records_service.has_call_record_backend_configured", lambda: True)
    monkeypatch.setattr("services.google_calendar_booking_service.is_booking_enabled", lambda: False)
    monkeypatch.setattr(Config, "HUMAN_TRANSFER_ENABLED", False)
    monkeypatch.setattr(Config, "HUMAN_TRANSFER_URL", "")
    text = _build_tools_availability_instruction()
    assert "`wait_for_user`" in text
    assert "`save_call_record`" in text
    assert "`get_availability`" not in text


def test_tool_validation_failure_returns_structured_json():
    service = OpenAIService()
    state = type("State", (), {"caller_phone_number": "+15551234567"})()
    manager = type("Manager", (), {"state": state})()
    ok, _, error = service._normalize_and_validate_tool_args(
        "book_appointment",
        {"slot_start_iso": "not-iso", "contact_name": "Avery", "contact_phone": "+15551234567"},
        manager,
    )
    assert ok is False
    assert "slot_start_iso" in (error or "")


def test_format_tool_failure_output_includes_next_step():
    payload = OpenAIService._format_tool_failure_output("No match found.", next_step="Confirm the phone number.")
    assert '"success": false' in payload.lower()
    assert "Confirm the phone number." in payload


def test_build_language_instruction_default_only_english_policy():
    from config import _build_language_instruction

    text = _build_language_instruction("English", "default_only")
    assert "English is the default response language." in text
    assert "Do not infer language from accent alone." in text
    assert "isolated foreign words" in text
    assert "support is limited to English" in text


def test_build_language_instruction_multilingual_policy():
    from config import _build_language_instruction

    text = _build_language_instruction("English", "explicit_or_substantive")
    assert "Default to English unless the caller clearly uses another language." in text
    assert "substantive utterance" in text
    assert "Would you like me to continue in English or another language?" in text
    assert "Do not switch languages based on:" in text


def test_build_accent_instruction_keeps_language_separate():
    from config import _build_accent_instruction

    text = _build_accent_instruction("English", "neutral American", "light")
    assert "Speak English with a light neutral American accent." in text
    assert "Keep the accent stable from the first word to the last." in text
    assert "natural vowel shaping" in text
    assert "Do not change response language based on the caller's accent." in text


def test_build_delivery_instruction_controls_tone_and_expressiveness():
    from config import _build_delivery_instruction

    text = _build_delivery_instruction("calm helpful", "very_warm", "expressive", "relaxed")
    assert "# Delivery Style" in text
    assert "Target tone: calm helpful." in text
    assert "more care and reassurance" in text
    assert "upbeat energy and vocal variety" in text
    assert "speak slightly slower" in text
    assert "vary naturally rather than repeat mechanically" in text
    assert "Do not mention these delivery controls to the caller." in text


def test_rebuild_system_message_pins_english_by_default(monkeypatch):
    monkeypatch.setattr(Config, "ASSISTANT_LANGUAGE", "English")
    monkeypatch.setattr(Config, "ASSISTANT_TONE", "warm professional")
    monkeypatch.setattr(Config, "ASSISTANT_WARMTH", "warm")
    monkeypatch.setattr(Config, "ASSISTANT_EXPRESSIVENESS", "balanced")
    monkeypatch.setattr(Config, "ASSISTANT_PACING", "moderate")
    monkeypatch.setattr(Config, "LANGUAGE_SWITCH_POLICY", "default_only")
    monkeypatch.setattr(Config, "ASSISTANT_ACCENT", "neutral American")
    monkeypatch.setattr(Config, "ASSISTANT_ACCENT_STRENGTH", "light")
    rebuild_system_message()
    assert "Target tone: warm professional." in Config.SYSTEM_MESSAGE
    assert "Expressiveness: use mild natural emphasis" in Config.SYSTEM_MESSAGE
    assert "English is the default response language." in Config.SYSTEM_MESSAGE
    assert "Speak English with a light neutral American accent." in Config.SYSTEM_MESSAGE
    assert "mirror the user" in Config.SYSTEM_MESSAGE.lower()


def test_build_reasoning_effort_instruction_for_gpt_realtime_2():
    from config import _build_reasoning_effort_instruction

    text = _build_reasoning_effort_instruction("gpt-realtime-2", "medium")
    assert "Session API reasoning effort is `medium`" in text
    assert "multi-step rescheduling" in text


def test_build_reasoning_effort_instruction_omitted_for_older_model():
    from config import _build_reasoning_effort_instruction

    assert _build_reasoning_effort_instruction("gpt-realtime-1.5", "low") == ""


def test_rebuild_system_message_includes_reasoning_effort_for_realtime_2(monkeypatch):
    monkeypatch.setattr(Config, "OPENAI_REALTIME_MODEL", "gpt-realtime-2")
    monkeypatch.setattr(Config, "REALTIME_REASONING_EFFORT", "low")
    rebuild_system_message()
    assert "Session API reasoning effort is `low`" in Config.SYSTEM_MESSAGE
    assert "respond quickly and do not reason" in Config.SYSTEM_MESSAGE.lower()


def test_slow_tool_descriptions_include_preamble_sample_phrases(monkeypatch):
    monkeypatch.setattr("services.openai_service.has_call_record_backend_configured", lambda: True)
    monkeypatch.setattr("services.openai_service.is_booking_enabled", lambda: True)
    monkeypatch.setattr(Config, "HUMAN_TRANSFER_ENABLED", True)
    monkeypatch.setattr(Config, "HUMAN_TRANSFER_URL", "https://example.test/transfer")
    tools = {tool["name"]: tool for tool in OpenAISessionManager._realtime_tools()}
    for name in (
        "get_availability",
        "list_my_bookings",
        "book_appointment",
        "edit_booking",
        "delete_booking",
        "save_call_record",
        "request_human_handoff",
    ):
        assert "Preamble sample phrases:" in tools[name]["description"], name


def test_rebuild_system_message_uses_main_prompt(monkeypatch):
    monkeypatch.setattr(Config, "COMPANY_NAME", "Example Co")
    monkeypatch.setattr(Config, "AGENT_NAME", "Alex")
    monkeypatch.setattr(Config, "SYSTEM_INSTRUCTIONS_PATH", "prompts/main_system_instructions.md")
    rebuild_system_message()
    assert "Example Co" in Config.SYSTEM_MESSAGE
    assert "Alex" in Config.SYSTEM_MESSAGE
    assert "save_call_record" in Config.SYSTEM_MESSAGE


def test_greeting_uses_company_and_agent(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "Sam")
    assert get_greeting_instruction("Example Co") == "You've reached Example Co. I'm Sam. How can I help?"


def test_session_tools_expose_save_call_record_when_backend_configured(monkeypatch):
    monkeypatch.setattr("services.openai_service.has_call_record_backend_configured", lambda: True)
    monkeypatch.setattr("services.openai_service.is_booking_enabled", lambda: False)
    tools = OpenAISessionManager._realtime_tools()
    names = {tool["name"] for tool in tools}
    assert "save_call_record" in names
    assert "wait_for_user" in names
    assert "submit_lead" not in names
    assert "end_call" in names


def test_submit_lead_legacy_alias_still_validates():
    service = OpenAIService()
    state = type("State", (), {"caller_phone_number": "+15551234567"})()
    manager = type("Manager", (), {"state": state})()
    args = {
        "contact_name": "Avery",
        "contact_phone": "caller's number",
        "issue_summary": "General question",
        "priority": "normal",
        "call_summary": "Caller asked a general question and wants follow-up.",
    }
    ok, normalized, error = service._normalize_and_validate_tool_args("submit_lead", args, manager)
    assert ok is True
    assert error is None
    assert normalized["contact_phone"] == "+15551234567"


def test_repo_has_no_industry_profile_yaml_files():
    root = Path(__file__).resolve().parents[1]
    ignored_parts = {
        ".agents",
        ".codex",
        ".git",
        ".pytest_cache",
        ".venv",
        "env",
        "venv",
        "site-packages",
        "__pycache__",
    }
    allowed_tooling_files = {".pre-commit-config.yaml"}
    yaml_files = []
    for path in list(root.rglob("*.yaml")) + list(root.rglob("*.yml")):
        rel = path.relative_to(root)
        if path.name in allowed_tooling_files:
            continue
        if any(part in ignored_parts for part in rel.parts):
            continue
        yaml_files.append(rel)
    assert yaml_files == []
