#!/usr/bin/env python3
"""Print a copyable setup block for a built-in portfolio sample."""
from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from portfolio_samples import PortfolioSample, get_sample, iter_samples


def _bool_env(value: bool) -> str:
    return "true" if value else "false"


def _quote_command_arg(value: str) -> str:
    return shlex.quote(value)


def build_env_lines(
    sample: PortfolioSample,
    *,
    company_name: str | None = None,
    agent_name: str | None = None,
    agent_label: str | None = None,
    timezone: str | None = None,
    booking_enabled: bool | None = None,
    call_record_backend: str = "supabase",
    recording_enabled: bool = True,
    outbound_enabled: bool = True,
) -> list[str]:
    resolved_company_name = company_name or sample.company_name
    resolved_agent_name = agent_name or sample.agent_name
    resolved_agent_label = agent_label or sample.agent_label
    resolved_timezone = timezone or sample.timezone
    resolved_booking_enabled = sample.booking_enabled if booking_enabled is None else booking_enabled

    return [
        f"SYSTEM_INSTRUCTIONS_PATH={sample.prompt_path}",
        f"COMPANY_NAME={resolved_company_name}",
        f"AGENT_NAME={resolved_agent_name}",
        f"AGENT_LABEL={resolved_agent_label}",
        f"TIMEZONE={resolved_timezone}",
        f"BOOKING_ENABLED={_bool_env(resolved_booking_enabled)}",
        f"CALL_RECORD_BACKEND={call_record_backend}",
        f"CALL_RECORDING_ENABLED={_bool_env(recording_enabled)}",
        f"OUTBOUND_ENABLED={_bool_env(outbound_enabled)}",
    ]


def build_preview_command(
    sample: PortfolioSample,
    *,
    company_name: str | None = None,
    agent_name: str | None = None,
    booking_enabled: bool | None = None,
    call_record_backend: str = "supabase",
    human_transfer: bool = False,
) -> str:
    resolved_company_name = company_name or sample.company_name
    resolved_agent_name = agent_name or sample.agent_name
    resolved_booking_enabled = sample.booking_enabled if booking_enabled is None else booking_enabled

    parts = [
        "python",
        "scripts/preview_system_prompt.py",
        "--sample",
        sample.key,
    ]
    if resolved_booking_enabled:
        parts.append("--with-booking-tools")
    if call_record_backend != "none":
        parts.append("--with-call-records")
    if human_transfer:
        parts.append("--with-human-transfer")
    parts.extend(["--company-name", resolved_company_name, "--agent-name", resolved_agent_name])
    return " ".join(_quote_command_arg(part) for part in parts)


def render_setup(
    sample: PortfolioSample,
    *,
    company_name: str | None = None,
    agent_name: str | None = None,
    agent_label: str | None = None,
    timezone: str | None = None,
    booking_enabled: bool | None = None,
    call_record_backend: str = "supabase",
    recording_enabled: bool = True,
    outbound_enabled: bool = True,
    human_transfer: bool = False,
) -> str:
    env_lines = build_env_lines(
        sample,
        company_name=company_name,
        agent_name=agent_name,
        agent_label=agent_label,
        timezone=timezone,
        booking_enabled=booking_enabled,
        call_record_backend=call_record_backend,
        recording_enabled=recording_enabled,
        outbound_enabled=outbound_enabled,
    )
    preview_command = build_preview_command(
        sample,
        company_name=company_name,
        agent_name=agent_name,
        booking_enabled=booking_enabled,
        call_record_backend=call_record_backend,
        human_transfer=human_transfer,
    )

    lines = [
        f"Sample: {sample.label}",
        f"Prompt path: {sample.prompt_path}",
        f"Outbound campaign type: {sample.campaign_type}",
        f"Primary flow: {sample.primary_flow}",
        "",
        ".env starting point:",
        "```env",
        *env_lines,
        "```",
        "",
        "Add real secrets separately:",
        "- OPENAI_API_KEY",
        "- TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN",
        "- SUPABASE_URL and SUPABASE_KEY when CALL_RECORD_BACKEND=supabase or OUTBOUND_ENABLED=true",
        "- GOOGLE_CALENDAR_ID and GOOGLE_CALENDAR_CREDENTIALS_JSON when BOOKING_ENABLED=true",
        "- RECORDING_STATUS_CALLBACK_BASE_URL when CALL_RECORDING_ENABLED=true",
        "",
        "Preview command:",
        "```bash",
        preview_command,
        "```",
        "",
        "Outbound demo setup:",
        f"1. Create a dashboard campaign with Type `{sample.campaign_type}`.",
        "2. Upload `docs/samples/portfolio_outbound_contacts.csv`.",
        f"3. Keep the row where `sample_campaign_type={sample.campaign_type}`.",
        "4. For one-shot API testing, use the matching object from `docs/samples/trigger_call_payloads.json`.",
        "",
        "Acceptance checklist:",
        "- `docs/PORTFOLIO_DEMO_ACCEPTANCE.md`",
        "",
        "Suggested demo calls:",
    ]
    lines.extend(f"- {demo_call}" for demo_call in sample.demo_calls)
    return "\n".join(lines) + "\n"


def render_new_sample_checklist() -> str:
    lines = [
        "New Portfolio Sample Checklist",
        "",
        "Use this when adding a new vertical beyond the built-in samples.",
        "",
        "Choose names first:",
        "- `sample_key`: short CLI key, such as `legal-intake` or `auto-repair`.",
        "- `campaign_type`: use `sample_<vertical>`, such as `sample_legal_intake`.",
        "- `prompt_path`: use `prompts/samples/<vertical>_receptionist.md` or another clear sample prompt name.",
        "- `agent_label`: use a stable demo label, such as `legal_intake_demo`.",
        "",
        "Required edits:",
        "1. Add one `PortfolioSample(...)` entry in `portfolio_samples.py`.",
        "2. Create the prompt file under `prompts/samples/`.",
        "3. Check the prompt against `docs/SAMPLE_PROMPT_QUALITY.md`.",
        "4. Add one row to the Recommended Sample Set table in `docs/PORTFOLIO_SAMPLES.md`.",
        "5. Add one fake contact row to `docs/samples/portfolio_outbound_contacts.csv`.",
        "6. Add one matching object to `docs/samples/trigger_call_payloads.json`.",
        "7. Keep custom fields generic: `lead_offer`, `contact_timezone`, `callback_number`, and sample-specific context in notes/summary fields unless code needs structure.",
        "8. Do not add industry YAML/profile files.",
        "",
        "Registry snippet shape:",
        "```python",
        '    "sample-key": PortfolioSample(',
        '        key="sample-key",',
        '        label="Sample label",',
        '        campaign_label="Sample: Sample Label",',
        '        prompt_path="prompts/samples/sample_prompt.md",',
        '        campaign_type="sample_sample_label",',
        '        company_name="Demo Company",',
        '        agent_name="Alex",',
        '        agent_label="sample_label_demo",',
        '        timezone="America/Los_Angeles",',
        "        booking_enabled=True,",
        '        booking_use="Google Calendar appointment",',
        '        primary_flow="Primary call outcome in one short phrase",',
        '        demo_calls=("successful booking", "callback request", "handoff or declined"),',
        "    ),",
        "```",
        "",
        "Verification commands:",
        "```bash",
        "python scripts/preview_system_prompt.py --list-samples",
        "python scripts/portfolio_sample_setup.py <sample-key>",
        "python scripts/preview_system_prompt.py --sample <sample-key> --with-call-records --company-name \"Demo Company\" --agent-name \"Alex\"",
        "python -m pytest tests/test_system_instructions.py tests/test_prompt_preview.py tests/test_outbound.py tests/test_generic_architecture.py",
        "```",
        "",
        "Demo acceptance gate:",
        "- Run the calls through `docs/PORTFOLIO_DEMO_ACCEPTANCE.md` before publishing recordings, screenshots, or transcripts.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print env values and a checklist for a built-in portfolio sample."
    )
    parser.add_argument("sample", nargs="?", choices=[sample.key for sample in iter_samples()])
    parser.add_argument("--list-samples", action="store_true", help="List available sample keys.")
    parser.add_argument("--new-sample-checklist", action="store_true", help="Print the checklist for adding a new portfolio sample.")
    parser.add_argument("--company-name", help="Override COMPANY_NAME in the printed env block.")
    parser.add_argument("--agent-name", help="Override AGENT_NAME in the printed env block.")
    parser.add_argument("--agent-label", help="Override AGENT_LABEL in the printed env block.")
    parser.add_argument("--timezone", help="Override TIMEZONE in the printed env block.")
    parser.add_argument("--booking-enabled", dest="booking_enabled", action="store_true", help="Force BOOKING_ENABLED=true.")
    parser.add_argument("--no-booking", dest="booking_enabled", action="store_false", help="Force BOOKING_ENABLED=false.")
    parser.set_defaults(booking_enabled=None)
    parser.add_argument(
        "--call-record-backend",
        choices=("supabase", "webhook", "none"),
        default="supabase",
        help="CALL_RECORD_BACKEND value to print.",
    )
    parser.add_argument("--no-recording", action="store_true", help="Print CALL_RECORDING_ENABLED=false.")
    parser.add_argument("--no-outbound", action="store_true", help="Print OUTBOUND_ENABLED=false.")
    parser.add_argument("--with-human-transfer", action="store_true", help="Add human transfer to the preview command.")
    args = parser.parse_args()

    if args.list_samples:
        for sample in iter_samples():
            print(f"{sample.key}\t{sample.label}\t{sample.campaign_type}\t{sample.prompt_path}")
        return 0

    if args.new_sample_checklist:
        print(render_new_sample_checklist(), end="")
        return 0

    if not args.sample:
        parser.error("Choose a sample, pass --list-samples, or pass --new-sample-checklist.")

    setup = render_setup(
        get_sample(args.sample),
        company_name=args.company_name,
        agent_name=args.agent_name,
        agent_label=args.agent_label,
        timezone=args.timezone,
        booking_enabled=args.booking_enabled,
        call_record_backend=args.call_record_backend,
        recording_enabled=not args.no_recording,
        outbound_enabled=not args.no_outbound,
        human_transfer=args.with_human_transfer,
    )
    print(setup, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
