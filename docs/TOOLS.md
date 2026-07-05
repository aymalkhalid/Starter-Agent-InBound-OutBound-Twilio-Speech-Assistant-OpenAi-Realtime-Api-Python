# Realtime Tools

Built-in tools are registered in `services/openai_service.py` and listed dynamically in the prompt via `{tools_availability_instruction}`.

## Always available

| Tool | Purpose |
| --- | --- |
| `wait_for_user` | End the turn silently when audio does not need a reply (silence, hold music, TV, side conversation, speech not addressed to the agent) |
| `end_call` | Hang up when the caller explicitly ends the conversation |

### `wait_for_user` (silence and background audio)

Follows the [OpenAI Realtime guide](./references/openai-realtime-models-prompting.md#handle-silence-and-background-audio): the model calls this no-op tool instead of speaking filler such as “I'm here” or “I didn't catch that.”

**When to use (prompt):** non-addressed audio — silence, background noise, hold music, TV, side conversation.

**When not to use:** the caller is clearly speaking to the agent but the content is garbled; ask one clarification instead (`# Unclear Audio` in the prompt).

**Server behavior** (`services/openai_service.py`, wired in `main.py`):

1. Returns tool output with `trigger_response=False` so no follow-up spoken turn is created.
2. Suppresses assistant audio as soon as the streaming tool call names `wait_for_user`.
3. Truncates and clears any filler audio already sent to Twilio (`finalize_wait_for_user`).
4. Logs `wait_for_user` events and increments `connection_manager.state.wait_for_user_count` per call.

VAD settings (`VAD_MODE`, `VAD_THRESHOLD`, etc.) reduce spurious turns from noise but do not replace `wait_for_user`. See [Configuration](./CONFIGURATION.md#voice-activity-detection-vad).

## Conditional tools

| Tool | When available |
| --- | --- |
| `save_call_record` | Call-record backend configured |
| `request_human_handoff` | Live transfer configured |
| `get_availability` | Booking enabled + Google Calendar configured |
| `book_appointment` | Booking enabled + Google Calendar configured |
| `list_my_bookings` | Booking enabled + Google Calendar configured |
| `edit_booking` | Booking enabled + Google Calendar configured |
| `delete_booking` | Booking enabled + Google Calendar configured |

`submit_lead` remains accepted inside the compatibility adapter only as a legacy alias. It is not advertised in the generic starter prompt or tool list.

## Prompting conventions

Slow or external tools include **preamble sample phrases** in their descriptions (`get_availability`, booking tools, `save_call_record`, `request_human_handoff`).

| Tool type | Expected behavior |
| --- | --- |
| Read-only lookup | Call when intent and required fields are clear |
| Read-only with phone identity | Confirm callback number digit by digit when not from caller context |
| Write / external | Summarize action, get confirmation, then call with a short preamble |
| Validation failure | Structured JSON: `{"success": false, "message": "...", "next_step": "..."}` |

Exact values matter for booking and records: use ISO slot times from `get_availability`, confirm phone/email before writes, and recover from failures without repeating identical failed calls.

## Booking tool timezone behavior

Booking tools keep one appointment/business timezone as the booking authority:
`Config.TIMEZONE`. Caller timezone is used only for display and call-record
context.

| Tool | Timezone behavior |
| --- | --- |
| `get_availability` | Returns UTC slot starts plus appointment display and caller-local display when caller timezone differs. |
| `book_appointment` | Books the exact returned `slot_start_iso`; writes Google Calendar event timezone as the appointment timezone. |
| `edit_booking` | Reschedules to the exact returned ISO slot and preserves appointment timezone authority. |
| `list_my_bookings` | Displays existing bookings and caller-local time when stored. |

After a successful booking, the call-record payload should include
`confirmed_slot`, `calendar_event_link`, and `metadata.appointments[]` so the
dashboard Booking row can show the appointment and Calendar link. See
[Booking timezones](./BOOKING_TIMEZONES.md).

Future external tools register through `services/tool_registry.py` and load via `services/mcp_adapter.py` (disabled no-op in v1). See [Diagrams §23](./DIAGRAMS.md#23-external-tools-scaffold-mcp--tool-registry).
