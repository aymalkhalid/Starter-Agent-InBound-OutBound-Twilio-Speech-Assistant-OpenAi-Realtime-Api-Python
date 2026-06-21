# Onboarding

One-page path from clone to a working phone agent, with optional features in order. Visual flows: [Diagrams](./DIAGRAMS.md) · Interactive: Cursor canvas `voice-agent-architecture.canvas.tsx`.

---

## Step 1 — Minimum viable agent (~15 min)

| Step | Action | Verify |
| --- | --- | --- |
| 1 | `python3 -m venv env && source env/bin/activate && pip install -r requirements.txt` | Dependencies install |
| 2 | `cp .env.example .env` — set `OPENAI_API_KEY` | `python main.py` starts |
| 3 | Edit `prompts/main_system_instructions.md` (company tone, intake flow) | Prompt reflects your use case |
| 4 | Expose HTTPS: `ngrok http 5050` **or** `./scripts/deploy-cloudrun.sh` | Public URL reachable |
| 5 | Twilio Voice webhook → `{URL}/incoming-call` | Inbound call reaches AI |
| 6 | Place test call — greet, talk, say goodbye | Agent hangs up via `end_call` |

Diagram: [§2 Inbound sequence](./DIAGRAMS.md#2-inbound-call-sequence) · [§19 First deploy](./DIAGRAMS.md#19-first-deploy-checklist)

**Building for a specific client?** [Multi-client workflow](./MULTI_CLIENT_WORKFLOW.md) · [Client discovery template](./templates/CLIENT_DISCOVERY.md)

---

## Step 2 — Customize behavior

| What | Where |
| --- | --- |
| Conversation rules, tool policy, safety | `prompts/main_system_instructions.md` |
| Agent name, voice, language, accent | `.env` (`AGENT_NAME`, `VOICE`, `ASSISTANT_*`) |
| Tool schemas + side effects | `services/openai_service.py` |
| Greeting / farewell phrasing | `system_instructions.py` |

After prompt changes: `pytest tests/test_system_instructions.py`

Diagram: [§22 Prompt architecture](./DIAGRAMS.md#22-prompt-architecture-map) · Mapping: [STARTER_PROMPT_MAPPING.md](./references/STARTER_PROMPT_MAPPING.md)

---

## Step 3 — Optional features (enable in this order)

| Order | Feature | Required env / setup | Diagram |
| --- | --- | --- | --- |
| 1 | **Dashboard + call records** | `CALL_RECORD_BACKEND=supabase`, Supabase schema, `DASHBOARD_USERS` | [§14–15](./DIAGRAMS.md#14-dashboard-authentication) |
| 2 | **Google Calendar booking** | GCal service account JSON, `GOOGLE_CALENDAR_ID`, booking flags | [§13](./DIAGRAMS.md#13-google-calendar-booking-flow) |
| 3 | **Outbound campaigns** | `OUTBOUND_ENABLED=true`, Twilio + Supabase, `OUTBOUND_BASE_URL` | [§9](./DIAGRAMS.md#9-outbound-campaign) |
| 4 | **Call recording** | `CALL_RECORDING_ENABLED`, `RECORDING_STATUS_CALLBACK_BASE_URL` | [§10](./DIAGRAMS.md#10-call-recording-and-transcription) |
| 5 | **Transcription** | `TRANSCRIPTION_MODEL` (e.g. `tiny`) | [§18](./DIAGRAMS.md#18-transcription-pipeline) |
| 6 | **Missed-call AI callback** | Twilio creds + Supabase (reuses outbound) | [§17](./DIAGRAMS.md#17-missed-calls-and-ai-callback) |
| 7 | **Dashboard runtime settings** | Supabase `app_settings` table | [§20](./DIAGRAMS.md#20-dynamic-settings-dashboard-overrides) |

---

## Step 4 — Key files map

```
main.py                          HTTP/WS routes, Twilio orchestration
config.py + .env                 Env loading, prompt builders, feature flags
prompts/main_system_instructions.md   Agent behavior (edit first)
services/openai_service.py       Realtime session, tools, tool handlers
services/connection_manager.py   Twilio ↔ OpenAI WebSocket bridge
services/twilio_service.py       TwiML, caller cache, recording
services/call_records_service.py Call record facade
static/dashboard.html            Dashboard UI (optional)
```

Full module diagram: [§11 Module map](./DIAGRAMS.md#11-module-map)

---

## Step 5 — Verify

```bash
# Prompt rendering
pytest tests/test_system_instructions.py

# OpenAI service / tool helpers
pytest tests/test_openai_service.py
```

---

## Step 6 — Production deploy

```bash
./scripts/deploy-cloudrun.sh
```

Post-deploy:
- Twilio webhook → `{SERVICE_URL}/incoming-call`
- Recording: `RECORDING_STATUS_CALLBACK_BASE_URL={SERVICE_URL}`
- GCal on GCP: mount credentials via Cloud Run secrets (not local file path)

Diagram: [§16 Deployment topology](./DIAGRAMS.md#16-deployment-topology)

---

## Extending tools (future)

Built-in tools live in `openai_service.py`. External/MCP tools use the scaffold (disabled in v1):

- `services/tool_registry.py` — register schemas + handlers
- `services/mcp_adapter.py` — MCP loader (no-op placeholder)

Diagram: [§23 External tools scaffold](./DIAGRAMS.md#23-external-tools-scaffold-mcp--tool-registry)
