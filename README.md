# OpenAI Realtime + Twilio Voice Agent Starter

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Production-ready **Python/FastAPI** starter for **inbound and outbound phone AI agents**. [Twilio Media Streams](https://www.twilio.com/docs/voice/media-streams) bridge live caller audio to the [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime); you customize behavior in one markdown prompt and wire side effects through Python tool handlers.

Includes a reference **aesthetic clinic appointment setter** outbound flow (warm Facebook leads → offer routing → Google Calendar booking).

**Repository:** [github.com/aymalkhalid/Starter-Agent-InBound-OutBound-Twilio-Speech-Assistant-OpenAi-Realtime-Api-Python](https://github.com/aymalkhalid/Starter-Agent-InBound-OutBound-Twilio-Speech-Assistant-OpenAi-Realtime-Api-Python)

---

## Architecture

One shared **WebSocket media bridge** (`/media-stream`) powers **inbound** calls and all **outbound** triggers: campaign bulk dial, dashboard single-contact dial, one-shot lead intake API, and missed-call AI callback. Optional layers—Supabase CRM, Google Calendar booking, human transfer, recording, and transcription—attach via Realtime tools and env config.

<p align="center">
  <a href="./docs/MASTER_DIAGRAM.md">
    <img
      src="docs/images/MasterArchitectureDiagram.png?v=4ed761d"
      alt="Voice Agent Starter master architecture: inbound and outbound call triggers, shared WebSocket media bridge, Supabase CRM, Google Calendar, and optional post-call services"
      width="900"
    />
  </a>
</p>

<p align="center"><sub>Click the diagram for the full breakdown and Mermaid source · <a href="./docs/MASTER_DIAGRAM.md">docs/MASTER_DIAGRAM.md</a></sub></p>

| Layer | Required | What it does |
| --- | --- | --- |
| Twilio + OpenAI Realtime | Yes | Phone audio ↔ speech AI (`OPENAI_API_KEY` + Twilio webhook) |
| Inbound | Yes (default) | Caller → `/incoming-call` → `/media-stream` → default system prompt |
| Outbound (4 triggers) | Optional | Dashboard, API, or missed-call callback → Twilio REST dial → same `/media-stream` with campaign prompt |
| Supabase CRM | Optional | Call records, dashboard, outbound campaigns, runtime settings |
| Webhook CRM | Optional | `save_call_record` POST to `WEBHOOK_URL` (no dashboard) |
| Google Calendar | Optional | Five booking tools when `BOOKING_ENABLED=true` |
| Post-call | Optional | Twilio recording + faster-whisper transcription (dashboard-triggered) |

**Diagram source & breakdown:** [docs/MASTER_DIAGRAM.md](./docs/MASTER_DIAGRAM.md) · **Detailed flows (23 Mermaid diagrams):** [docs/DIAGRAMS.md](./docs/DIAGRAMS.md) · **Module narrative:** [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)

---

## Features

### Core (no Supabase required)

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
- **Outbound** campaigns, dashboard single-contact dial, one-shot lead intake API, and missed-call AI callback
- **Appointment setter** campaign type (`aesthetic_appointment_setter`) with lead-offer routing and outcome tags
- Timezone-aware **Google Calendar** booking (caller-local display, clinic-time writes)
- Call **recording**, playback proxy, and **Whisper** transcription
- Dashboard **runtime settings** (voice, VAD, booking) via Supabase
- MCP / external tool registry scaffold (disabled in v1)

### Outbound entry points

| Route | Use case |
| --- | --- |
| `POST /outbound/campaigns/{id}/start` | Dial all pending contacts in a campaign |
| `POST /outbound/campaigns/{id}/contacts/{contact_id}/call` | Dial one saved contact from the dashboard |
| `POST /outbound/campaigns/{id}/trigger-call` | External API submits one lead and immediately triggers one call |
| `POST /missed-calls/{call_sid}/callback-ai` | AI calls back a missed inbound caller |

---

## Quick start

**Prerequisites:** Python 3.10+, [OpenAI API key](https://platform.openai.com/api-keys), [Twilio account](https://www.twilio.com/) with a Voice number, and a public HTTPS URL (ngrok or Cloud Run).

```bash
git clone https://github.com/aymalkhalid/Starter-Agent-InBound-OutBound-Twilio-Speech-Assistant-OpenAi-Realtime-Api-Python.git
cd Starter-Agent-InBound-OutBound-Twilio-Speech-Assistant-OpenAi-Realtime-Api-Python

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
| Default inbound behavior | `prompts/main_system_instructions.md` |
| Outbound appointment setter | `prompts/aesthetic_appointment_setter.md` (see [APPOINTMENT_SETTER_MVP.md](./docs/APPOINTMENT_SETTER_MVP.md)) |
| Tool schemas + handlers | `services/openai_service.py` |
| Tone, voice, language, accent, reasoning | `.env` or dashboard Settings (see [CONFIGURATION.md](./docs/CONFIGURATION.md)) |
| Greeting / farewell phrasing | `system_instructions.py` |

Prompting follows the [OpenAI Realtime guide](./docs/references/openai-realtime-models-prompting.md). Section mapping: [STARTER_PROMPT_MAPPING.md](./docs/references/STARTER_PROMPT_MAPPING.md).

For client or industry builds, keep behavior as prompt-as-code: use an agentic coding tool to edit the prompt and related tests/docs, then preview the rendered instructions before deploying:

```bash
python scripts/preview_system_prompt.py
pytest tests/test_system_instructions.py
```

Workflow: [PROMPT_AS_CODE.md](./docs/PROMPT_AS_CODE.md).

Example env values:

```env
COMPANY_NAME=Acme Voice Agent Demo
AGENT_NAME=Alex
OPENAI_REALTIME_MODEL=gpt-realtime-2
REALTIME_REASONING_EFFORT=low
VOICE=cedar
ASSISTANT_TONE=warm professional
ASSISTANT_WARMTH=warm
ASSISTANT_EXPRESSIVENESS=balanced
ASSISTANT_PACING=moderate
ASSISTANT_LANGUAGE=English
ASSISTANT_ACCENT=neutral American
ASSISTANT_ACCENT_STRENGTH=light
LANGUAGE_SWITCH_POLICY=default_only
```

---

## Documentation

| Guide | Description |
| --- | --- |
| [MASTER_DIAGRAM.md](./docs/MASTER_DIAGRAM.md) | Master architecture (PNG + Mermaid + step-by-step breakdown) |
| [COPYABLE_MERMAID.md](./docs/COPYABLE_MERMAID.md) | Copy-paste Mermaid diagrams and ChatGPT prompts for architecture images |
| [ONBOARDING.md](./docs/ONBOARDING.md) | Clone → live agent checklist |
| [APPOINTMENT_SETTER_MVP.md](./docs/APPOINTMENT_SETTER_MVP.md) | Outbound clinic appointment-setter scope and call flow |
| [BOOKING_TIMEZONES.md](./docs/BOOKING_TIMEZONES.md) | Timezone authority for availability, booking, and dashboard links |
| [PROMPT_AS_CODE.md](./docs/PROMPT_AS_CODE.md) | Code-first prompt customization workflow |
| [MULTI_CLIENT_WORKFLOW.md](./docs/MULTI_CLIENT_WORKFLOW.md) | Separate deploy per client (real estate, lead qualifier, …) |
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

Call records are enriched in stages: live AI summary, Twilio recording link, Whisper transcript, optional OpenAI transcript enhancement, then manual notes/status. The dashboard collapses latest/primary/related Twilio SIDs into one `Call SID` row, with related attempts expandable when present.

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
main.py                               # FastAPI routes, Twilio WebSocket bridge
config.py                             # Env loading, prompt builders
prompts/main_system_instructions.md   # Default inbound agent behavior
prompts/aesthetic_appointment_setter.md  # Outbound appointment-setter prompt
services/openai_service.py            # Realtime session, tools, handlers
services/call_records_service.py      # App-facing call-record storage facade
services/outbound_service.py          # Campaign, single-call, and one-shot outbound pipeline
services/missed_calls_service.py      # Missed-call detection and AI callback support
services/google_calendar_booking_service.py  # Booking tools + timezone-aware slots
services/timezone_utils.py            # Caller/clinic timezone helpers
services/transcription_service.py     # Twilio MP3 fetch, faster-whisper, transcript enhancement
services/dynamic_settings.py          # Supabase-backed runtime settings
services/connection_manager.py        # Twilio ↔ OpenAI WebSocket manager
services/twilio_service.py            # TwiML, caller cache, recording
static/dashboard.html                 # Optional call-record UI
docs/                                 # Onboarding, diagrams, configuration
docs/images/MasterArchitectureDiagram.png  # Master architecture poster
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
