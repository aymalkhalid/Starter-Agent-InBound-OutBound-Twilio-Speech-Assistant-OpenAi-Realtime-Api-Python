#!/usr/bin/env python3
"""Print the fully rendered Realtime system prompt.

This is a local prompt-as-code helper: it does not call OpenAI or Twilio. It
sets PROMPT_PREVIEW_SKIP_DYNAMIC_SETTINGS by default so previews stay offline.
It then applies optional preview overrides, rebuilds Config.SYSTEM_MESSAGE, and
writes the final prompt to stdout.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from portfolio_samples import SAMPLE_PROMPTS


def _load_environment() -> None:
    """Load .env before importing config, but do not require a real API key."""
    load_dotenv(PROJECT_ROOT / ".env")
    os.environ.setdefault("OPENAI_API_KEY", "prompt-preview")
    os.environ.setdefault("PROMPT_PREVIEW_SKIP_DYNAMIC_SETTINGS", "true")
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render and print Config.SYSTEM_MESSAGE for prompt review."
    )
    parser.add_argument("--prompt-path", help="Prompt markdown path, default from SYSTEM_INSTRUCTIONS_PATH.")
    parser.add_argument("--sample", choices=sorted(SAMPLE_PROMPTS), help="Render a built-in portfolio sample prompt.")
    parser.add_argument("--list-samples", action="store_true", help="List built-in portfolio sample prompt names and paths.")
    parser.add_argument("--with-booking-tools", action="store_true", help="Preview as if Google Calendar booking tools are available.")
    parser.add_argument("--with-call-records", action="store_true", help="Preview as if save_call_record is available.")
    parser.add_argument("--with-human-transfer", action="store_true", help="Preview as if request_human_handoff is available.")
    parser.add_argument("--company-name", help="Preview COMPANY_NAME.")
    parser.add_argument("--agent-name", help="Preview AGENT_NAME.")
    parser.add_argument("--tone", help="Preview ASSISTANT_TONE.")
    parser.add_argument("--warmth", help="Preview ASSISTANT_WARMTH.")
    parser.add_argument("--expressiveness", help="Preview ASSISTANT_EXPRESSIVENESS.")
    parser.add_argument("--pacing", help="Preview ASSISTANT_PACING.")
    parser.add_argument("--language", help="Preview ASSISTANT_LANGUAGE.")
    parser.add_argument("--language-switch-policy", help="Preview LANGUAGE_SWITCH_POLICY.")
    parser.add_argument("--accent", help="Preview ASSISTANT_ACCENT.")
    parser.add_argument("--accent-strength", help="Preview ASSISTANT_ACCENT_STRENGTH.")
    parser.add_argument("--model", help="Preview OPENAI_REALTIME_MODEL.")
    parser.add_argument("--reasoning-effort", help="Preview REALTIME_REASONING_EFFORT.")
    args = parser.parse_args()

    if args.list_samples:
        for name in sorted(SAMPLE_PROMPTS):
            print(f"{name}\t{SAMPLE_PROMPTS[name]}")
        return 0

    if args.prompt_path and args.sample:
        parser.error("Use either --prompt-path or --sample, not both.")

    _load_environment()

    from config import Config, rebuild_system_message

    if args.sample:
        Config.SYSTEM_INSTRUCTIONS_PATH = SAMPLE_PROMPTS[args.sample]
    elif args.prompt_path:
        Config.SYSTEM_INSTRUCTIONS_PATH = args.prompt_path
    if args.company_name:
        Config.COMPANY_NAME = args.company_name
    if args.agent_name is not None:
        Config.AGENT_NAME = args.agent_name
    if args.tone:
        Config.ASSISTANT_TONE = args.tone
    if args.warmth:
        Config.ASSISTANT_WARMTH = args.warmth
    if args.expressiveness:
        Config.ASSISTANT_EXPRESSIVENESS = args.expressiveness
    if args.pacing:
        Config.ASSISTANT_PACING = args.pacing
    if args.language:
        Config.ASSISTANT_LANGUAGE = args.language
    if args.language_switch_policy:
        Config.LANGUAGE_SWITCH_POLICY = args.language_switch_policy
    if args.accent:
        Config.ASSISTANT_ACCENT = args.accent
    if args.accent_strength:
        Config.ASSISTANT_ACCENT_STRENGTH = args.accent_strength
    if args.model:
        Config.OPENAI_REALTIME_MODEL = args.model
    if args.reasoning_effort:
        Config.REALTIME_REASONING_EFFORT = args.reasoning_effort
    if args.with_call_records:
        Config.CALL_RECORD_BACKEND = "webhook"
        Config.LEAD_BACKEND = "webhook"
        Config.WEBHOOK_URL = Config.WEBHOOK_URL or "https://example.invalid/call-record-preview"
    if args.with_booking_tools:
        Config.BOOKING_ENABLED = True
        from services import google_calendar_booking_service

        google_calendar_booking_service.is_booking_enabled = lambda: True
    if args.with_human_transfer:
        Config.HUMAN_TRANSFER_ENABLED = True
        Config.HUMAN_TRANSFER_URL = Config.HUMAN_TRANSFER_URL or "/twiml/transfer-to-agent"

    rebuild_system_message()
    sys.stdout.write(Config.SYSTEM_MESSAGE)
    if not Config.SYSTEM_MESSAGE.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
