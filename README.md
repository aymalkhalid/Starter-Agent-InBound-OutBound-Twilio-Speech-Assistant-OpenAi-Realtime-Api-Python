# OpenAI Realtime + Twilio Voice Agent Starter

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Production-ready **Python/FastAPI** starter for inbound and outbound **phone AI agents**. [Twilio Media Streams](https://www.twilio.com/docs/voice/media-streams) bridge live caller audio to the [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime); you customize behavior in one markdown prompt and wire side effects through Python tool handlers.

**Repository:** [github.com/aymalkhalid/Twilio-speech-assistant-openai-realtime-api-python](https://github.com/aymalkhalid/Twilio-speech-assistant-openai-realtime-api-python)

---

## Features

### Core (works with `OPENAI_API_KEY` only)

- Twilio ↔ OpenAI Realtime audio bridge over WebSocket
- Voice selection, VAD, barge-in, and preemptive session renewal
- OpenAI-aligned silence handling via `wait_for_user`
- Context-aware `end_call` goodbyes
- Single editable prompt: `prompts/main_system_instructions.md` (Realtime 2-aligned)

### Built-in tools

| Tool | When available |
| --- | --- |
| `wait_for_user`, `end_call` | Always |
| `save_call_record` | Call-record backend configured |
| `request_human_handoff` | Live transfer configured |
| Booking tools (5) | Google Calendar + booking enabled |

### Optional (env-gated)

- Supabase call-record **dashboard** (`/dashboard`, `/calls`)
- **Google Calendar** appointment booking
- **Outbound** campaigns and missed-call AI callback
- Call **recording**, playback proxy, and **Whisper** transcription
- Dashboard **runtime settings** (voice, VAD, booking) via Supabase
- MCP / external tool registry scaffold (disabled in v1)

---

## Quick start

**Prerequisites:** Python 3.10+, [OpenAI API key](https://platform.openai.com/api-keys), [Twilio account](https://www.twilio.com/) with a Voice number, and a public HTTPS URL (ngrok or Cloud Run).

```bash
git clone https://github.com/aymalkhalid/Twilio-speech-assistant-openai-realtime-api-python.git
cd Twilio-speech-assistant-openai-realtime-api-python

python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then run:

```bash
python main.py
```

Point your Twilio Voice webhook to:

```text
https://YOUR_PUBLIC_HOST/incoming-call
```

**Full checklist (MVP → optional features):** [docs/ONBOARDING.md](./docs/ONBOARDING.md)

---

## Customize the agent

| Goal | Edit |
| --- | --- |
| Conversation behavior | `prompts/main_system_instructions.md` |
| Tool schemas + handlers | `services/openai_service.py` |
| Voice, language, accent, reasoning | `.env` or dashboard Settings (see [CONFIGURATION.md](./docs/CONFIGURATION.md)) |
| Greeting / farewell phrasing | `system_instructions.py` |

Prompting follows the [OpenAI Realtime guide](./docs/references/openai-realtime-models-prompting.md). Section mapping: [STARTER_PROMPT_MAPPING.md](./docs/references/STARTER_PROMPT_MAPPING.md).

Example env values:

```env
COMPANY_NAME=Acme Voice Agent Demo
AGENT_NAME=Alex
OPENAI_REALTIME_MODEL=gpt-realtime-2
REALTIME_REASONING_EFFORT=low
VOICE=cedar
ASSISTANT_LANGUAGE=English
ASSISTANT_ACCENT=neutral American
ASSISTANT_ACCENT_STRENGTH=light
LANGUAGE_SWITCH_POLICY=default_only
```

---

## Documentation

| Guide | Description |
| --- | --- |
| [ONBOARDING.md](./docs/ONBOARDING.md) | Clone → live agent checklist |
| [DIAGRAMS.md](./docs/DIAGRAMS.md) | 23 architecture Mermaid diagrams |
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Module overview and runtime flow |
| [CONFIGURATION.md](./docs/CONFIGURATION.md) | Env vars and prompt placeholders |
| [TOOLS.md](./docs/TOOLS.md) | Realtime tool behavior |
| [DEPLOY_CLOUD_RUN.md](./docs/DEPLOY_CLOUD_RUN.md) | Production deploy |

---

## Dashboard and storage

The core phone agent runs **without Supabase**. To enable the dashboard, call records, recordings, and transcripts:

```env
CALL_RECORD_BACKEND=supabase
SUPABASE_URL=...
SUPABASE_KEY=...
DASHBOARD_USERS=admin:your-secure-password
```

Default table: `call_records`. Legacy `leads` tables: set `SUPABASE_CALL_RECORD_TABLE=leads`.

Schema: [docs/supabase-schema/](./docs/supabase-schema/)

---

## Deploy to Cloud Run

```bash
./scripts/deploy-cloudrun.sh
```

Reads local `.env`, excludes local file-path secrets, and deploys the `speech-assistant` service. Post-deploy: set Twilio webhook to `{SERVICE_URL}/incoming-call`.

Details: [docs/DEPLOY_CLOUD_RUN.md](./docs/DEPLOY_CLOUD_RUN.md)

---

## Project structure

```text
main.py                          # FastAPI routes, Twilio WebSocket bridge
config.py                        # Env loading, prompt builders
prompts/main_system_instructions.md   # Agent behavior (edit first)
services/openai_service.py       # Realtime session, tools, handlers
services/connection_manager.py   # Twilio ↔ OpenAI WebSocket manager
services/twilio_service.py       # TwiML, caller cache, recording
static/dashboard.html            # Optional call-record UI
docs/                            # Onboarding, diagrams, configuration
```

---

## Development

```bash
pytest tests/test_system_instructions.py
pytest tests/test_openai_service.py
```

Pre-commit hooks scan for secrets (see `.pre-commit-config.yaml`).

---

## License

[MIT](LICENSE) — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community guidelines.
