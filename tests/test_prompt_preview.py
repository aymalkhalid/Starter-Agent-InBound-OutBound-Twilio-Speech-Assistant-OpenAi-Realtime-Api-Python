"""Tests for prompt-as-code preview helper."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_prompt_preview_script_prints_rendered_system_prompt():
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "prompt-preview"  # pragma: allowlist secret
    env["CALL_RECORD_BACKEND"] = "webhook"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/preview_system_prompt.py",
            "--company-name",
            "Example HVAC",
            "--agent-name",
            "Nia",
            "--tone",
            "calm helpful",
            "--warmth",
            "very_warm",
            "--language",
            "English",
            "--accent",
            "neutral American",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    prompt = result.stdout
    assert "Example HVAC" in prompt
    assert "Nia" in prompt
    assert "Target tone: calm helpful." in prompt
    assert "Warmth: use a little more care and reassurance" in prompt
    assert "save_call_record" in prompt
    assert "{company_name}" not in prompt
    assert "{agent_name}" not in prompt


def test_prompt_preview_lists_portfolio_samples():
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "prompt-preview"  # pragma: allowlist secret

    result = subprocess.run(
        [sys.executable, "scripts/preview_system_prompt.py", "--list-samples"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "dentist\tprompts/samples/dentist_clinic_receptionist.md" in result.stdout
    assert "real-estate\tprompts/samples/real_estate_showing_scheduler.md" in result.stdout


def test_portfolio_sample_setup_lists_samples():
    result = subprocess.run(
        [sys.executable, "scripts/portfolio_sample_setup.py", "--list-samples"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "dentist\tDentist clinic\tsample_dentist_clinic\tprompts/samples/dentist_clinic_receptionist.md" in result.stdout
    assert "real-estate\tReal estate\tsample_real_estate\tprompts/samples/real_estate_showing_scheduler.md" in result.stdout


def test_portfolio_sample_setup_prints_copyable_env_and_checklist():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/portfolio_sample_setup.py",
            "ecommerce-support",
            "--company-name",
            "Demo Shop",
            "--agent-name",
            "Lena",
            "--no-outbound",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    output = result.stdout
    assert "Sample: E-commerce support" in output
    assert "SYSTEM_INSTRUCTIONS_PATH=prompts/samples/ecommerce_support_receptionist.md" in output
    assert "COMPANY_NAME=Demo Shop" in output
    assert "AGENT_NAME=Lena" in output
    assert "BOOKING_ENABLED=false" in output
    assert "CALL_RECORDING_ENABLED=true" in output
    assert "OUTBOUND_ENABLED=false" in output
    assert "sample_campaign_type=sample_ecommerce_support" in output
    assert "docs/PORTFOLIO_DEMO_ACCEPTANCE.md" in output
    assert "--with-booking-tools" not in output


def test_portfolio_sample_setup_prints_new_sample_checklist():
    result = subprocess.run(
        [sys.executable, "scripts/portfolio_sample_setup.py", "--new-sample-checklist"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    output = result.stdout
    assert "New Portfolio Sample Checklist" in output
    assert "portfolio_samples.py" in output
    assert "PortfolioSample(...)" in output
    assert "prompts/samples/" in output
    assert "docs/SAMPLE_PROMPT_QUALITY.md" in output
    assert "docs/PORTFOLIO_SAMPLES.md" in output
    assert "docs/samples/portfolio_outbound_contacts.csv" in output
    assert "docs/samples/trigger_call_payloads.json" in output
    assert "Do not add industry YAML/profile files." in output
    assert "python scripts/preview_system_prompt.py --list-samples" in output
    assert "python -m pytest tests/test_system_instructions.py tests/test_prompt_preview.py tests/test_outbound.py tests/test_generic_architecture.py" in output


def test_prompt_preview_renders_named_portfolio_sample():
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "prompt-preview"  # pragma: allowlist secret
    env["CALL_RECORD_BACKEND"] = "webhook"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/preview_system_prompt.py",
            "--sample",
            "real-estate",
            "--company-name",
            "Acme Realty",
            "--agent-name",
            "Mia",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    prompt = result.stdout
    assert "Acme Realty" in prompt
    assert "Mia" in prompt
    assert "real estate phone assistant" in prompt.lower()
    assert "save_call_record" in prompt
    assert "{company_name}" not in prompt


def test_prompt_preview_feature_flags_show_sample_tool_surface():
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "prompt-preview"  # pragma: allowlist secret

    result = subprocess.run(
        [
            sys.executable,
            "scripts/preview_system_prompt.py",
            "--sample",
            "dentist",
            "--with-booking-tools",
            "--with-call-records",
            "--with-human-transfer",
            "--company-name",
            "Bright Smile Dental",
            "--agent-name",
            "Ava",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    prompt = result.stdout
    assert "dental clinic phone receptionist" in prompt.lower()
    assert "Booking: When scheduling intent is clear" in prompt
    assert "- `save_call_record`" in prompt
    assert "- `get_availability`" in prompt
    assert "- `book_appointment`" in prompt
    assert "- `request_human_handoff`" in prompt


def test_prompt_preview_skips_dynamic_settings_network_load():
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "prompt-preview"  # pragma: allowlist secret
    env["CALL_RECORD_BACKEND"] = "supabase"
    env["SUPABASE_URL"] = "https://preview.invalid"
    env["SUPABASE_KEY"] = "preview-key"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/preview_system_prompt.py",
            "--company-name",
            "Offline Preview Co",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Offline Preview Co" in result.stdout
    assert "Dynamic settings load error" not in result.stdout
    assert "Dynamic settings load error" not in result.stderr


def test_prompt_preview_rejects_sample_and_prompt_path_together():
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "prompt-preview"  # pragma: allowlist secret

    result = subprocess.run(
        [
            sys.executable,
            "scripts/preview_system_prompt.py",
            "--sample",
            "dentist",
            "--prompt-path",
            "prompts/main_system_instructions.md",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "Use either --prompt-path or --sample" in result.stderr


def test_prompt_as_code_doc_locks_runtime_settings_boundary():
    doc = (ROOT / "docs" / "PROMPT_AS_CODE.md").read_text(encoding="utf-8")
    assert "Do not add industry YAML files" in doc
    assert "Do not store the main prompt" in doc
    assert "python scripts/preview_system_prompt.py" in doc


def test_portfolio_sample_registry_aligns_with_outbound_campaign_presets():
    from portfolio_samples import PORTFOLIO_SAMPLES, SAMPLE_PROMPTS

    os.environ.setdefault("PROMPT_PREVIEW_SKIP_DYNAMIC_SETTINGS", "true")
    from services.outbound_service import get_campaign_types

    campaign_types = get_campaign_types()
    assert set(SAMPLE_PROMPTS) == set(PORTFOLIO_SAMPLES)

    for sample in PORTFOLIO_SAMPLES.values():
        assert SAMPLE_PROMPTS[sample.key] == sample.prompt_path
        assert (ROOT / sample.prompt_path).is_file()
        assert sample.campaign_type in campaign_types
        assert campaign_types[sample.campaign_type]["system_instructions_path"] == sample.prompt_path
