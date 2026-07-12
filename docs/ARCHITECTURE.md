# Architecture

## Runtime Flow

1. Twilio calls `/incoming-call`.
2. FastAPI returns TwiML that connects audio to `/media-stream`.
3. `main.py` creates a `ConnectionManager` and `OpenAIService`.
4. `OpenAIService` sends `Config.SYSTEM_MESSAGE` plus tool schemas to OpenAI Realtime.
5. Twilio audio frames and OpenAI audio deltas are bridged until the call ends.

### Non-addressed audio (`wait_for_user`)

When the model decides incoming audio does not need a reply:

1. It calls `wait_for_user` (tool schema in `openai_service.py`).
2. The handler completes the tool silently (`trigger_response=False`).
3. `main.py` may truncate/clear assistant filler audio and suppress further deltas for that turn.
4. Normal responses resume when the caller clearly addresses the agent again.

See [Realtime Tools](./TOOLS.md#wait_for_user-silence-and-background-audio).

## Main Modules

- `main.py`: HTTP/WebSocket routes and Twilio orchestration.
- `config.py`: env loading, tone/language/accent/reasoning builders, and `Config.SYSTEM_MESSAGE` rendering.
- `system_instructions.py`: prompt file loading, greeting, and farewell text.
- `services/openai_service.py`: Realtime session payloads, tools, and function-call handling.
- `services/call_records_service.py`: generic call-record facade used by app code.
- `services/webhook_service.py`: compatibility storage adapter for webhook/Supabase writes.
- `services/google_calendar_booking_service.py`: optional calendar tools.
- `services/outbound_service.py`: optional outbound campaign execution.
- `services/tool_registry.py` and `services/mcp_adapter.py`: future external tool integration.

## Call Record Lifecycle

Call records are CRM-style records that are enriched in stages:

1. The Realtime agent calls `save_call_record` during the call. This writes contact fields, `issue_summary`, `call_summary`, booking context, `lead_status`, `call_sid`, and metadata.
2. If recording is enabled, Twilio posts `/recording-status` after completion. The app matches by `call_sid` and stores `recording_link`.
3. The dashboard plays recordings through `GET /recordings/{recording_sid}/media`, a server-side Twilio-auth proxy with byte-range support for seeking.
4. `POST /recordings/{recording_sid}/transcribe?record_id=...` downloads the MP3 and writes a Whisper/faster-whisper transcript.
5. `POST /calls/{record_id}/enhance-transcript` uses the configured OpenAI text model to format the transcript and save `transcript_summary`, `transcript_issues`, and `transcript_enhanced_at`.
6. Dashboard users can separately save notes, status, name, and location.

The dashboard displays one compact `Call SID` field. When metadata contains more than one related SID, it shows the latest SID first and an expandable related-call history. `metadata.primary_call_sid` is the original/canonical call; `metadata.related_call_sids` ties follow-up calls to the same record.

## Prompt Pipeline

1. `prompts/main_system_instructions.md` holds static Realtime behavior rules.
2. `config.build_system_message()` injects placeholders (delivery style, language, accent, reasoning effort, enabled tools, booking/transfer/record instructions).
3. `OpenAISessionManager.create_session_update()` sends instructions plus tool schemas to OpenAI Realtime.
4. If the selected model registry entry supports configurable reasoning effort, `REALTIME_REASONING_EFFORT` is also set on the session payload.

See [Configuration](./CONFIGURATION.md) and [Starter prompt mapping](./references/STARTER_PROMPT_MAPPING.md).

## Diagrams

Visual flows live in [Diagrams](./DIAGRAMS.md) (23 sections, indexed). For a single shareable overview, see [Master diagram](./MASTER_DIAGRAM.md) and the poster at [`images/MasterArchitectureDiagram.png`](./images/MasterArchitectureDiagram.png). Quick start: [Onboarding](./ONBOARDING.md).
