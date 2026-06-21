# Architecture Diagrams

Visual reference for the Twilio + OpenAI Realtime voice-agent starter. Diagrams match the current code in `main.py`, `config.py`, and `services/`.

For narrative context see [Architecture](./ARCHITECTURE.md). For the rendered poster see [`images/MasterArchitectureDiagram.png`](./images/MasterArchitectureDiagram.png) and [Master diagram](./MASTER_DIAGRAM.md). For tool behavior see [Realtime Tools](./TOOLS.md). Quick start checklist: [Onboarding](./ONBOARDING.md).

## Index

| § | Topic |
| --- | --- |
| 1 | [System overview](#1-system-overview) |
| 2 | [Inbound call sequence](#2-inbound-call-sequence) |
| 3 | [Media stream concurrency](#3-media-stream-concurrency) |
| 4 | [Prompt pipeline](#4-prompt-pipeline) |
| 5 | [Realtime tool routing](#5-realtime-tool-routing) |
| 6 | [`wait_for_user` flow](#6-wait_for_user-flow) |
| 7 | [Call record storage](#7-call-record-storage) |
| 8 | [Human transfer](#8-human-transfer) |
| 9 | [Outbound campaign](#9-outbound-campaign) |
| 10 | [Call recording](#10-call-recording-and-transcription) |
| 11 | [Module map](#11-module-map) |
| 12 | [Configuration → behavior](#12-configuration--behavior) |
| 13 | [Google Calendar booking](#13-google-calendar-booking-flow) |
| 14 | [Dashboard authentication](#14-dashboard-authentication) |
| 15 | [Dashboard live updates](#15-dashboard-live-updates) |
| 16 | [Deployment topology](#16-deployment-topology) |
| 17 | [Missed calls + AI callback](#17-missed-calls-and-ai-callback) |
| 18 | [Transcription pipeline](#18-transcription-pipeline) |
| 19 | [First deploy checklist](#19-first-deploy-checklist) |
| 20 | [Dynamic settings](#20-dynamic-settings-dashboard-overrides) |
| 21 | [`end_call` goodbye state machine](#21-end_call-goodbye-state-machine) |
| 22 | [Prompt architecture map](#22-prompt-architecture-map) |
| 23 | [External tools scaffold](#23-external-tools-scaffold-mcp--tool-registry) |

---

## 1. System overview

```mermaid
flowchart TB
    subgraph External["External services"]
        Caller["Phone caller"]
        Twilio["Twilio Voice + Media Streams"]
        OpenAI["OpenAI Realtime API"]
        Supabase["Supabase (optional)"]
        GCal["Google Calendar (optional)"]
    end

    subgraph App["FastAPI — main.py"]
        IC["POST/GET /incoming-call"]
        MS["WS /media-stream"]
        Dash["/dashboard /calls /login"]
        Out["/outbound/*"]
        Rec["/recordings/* /recording-status"]
    end

    subgraph Core["Core services"]
        TS["TwilioService"]
        WCM["WebSocketConnectionManager"]
        OS["OpenAIService"]
        AS["AudioService"]
    end

    subgraph Prompt["Prompt pipeline"]
        MD["prompts/main_system_instructions.md"]
        SI["system_instructions.py"]
        CFG["config.py → Config.SYSTEM_MESSAGE"]
    end

    subgraph Storage["Call records (optional)"]
        CRS["call_records_service.py"]
        WH["webhook_service.py"]
    end

    Caller --> Twilio
    Twilio --> IC
    IC --> TS
    TS --> MS
    MS --> WCM
    WCM --> OS
    WCM --> AS
    OS --> OpenAI
    WCM --> Twilio

    MD --> SI --> CFG --> OS

    OS --> CRS --> WH
    WH --> Supabase
    OS --> GCal
    Dash --> CRS
    Out --> Supabase
    Rec --> Twilio
```

---

## 2. Inbound call sequence

Source: `TwilioService.create_incoming_call_response()` → `handle_media_stream()` in `main.py`.

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller
    participant T as Twilio
    participant F as FastAPI
    participant TS as TwilioService
    participant WCM as WebSocketConnectionManager
    participant OS as OpenAIService
    participant AS as AudioService
    participant O as OpenAI Realtime

    C->>T: Inbound call
    T->>F: POST /incoming-call (From, CallSid)
    F->>TS: create_incoming_call_response
    TS->>TS: Cache caller in _CALLER_CACHE
    TS-->>T: TwiML Connect Stream → wss://host/media-stream
    T->>F: WebSocket /media-stream

    F->>F: dynamic_settings.load_overrides_sync (optional)
    F->>WCM: Accept Twilio WS
    WCM->>O: websockets.connect (OpenAI Realtime)
    OS->>O: session.update (instructions, tools, voice, VAD)
    O-->>WCM: session.updated

    T->>F: event start (streamSid, callSid)
    Note over WCM: Resolve caller from URL or _CALLER_CACHE
    OS->>O: send_caller_phone_session_update
    OS->>O: send_initial_greeting (response.create)
    OS->>OS: prewarm_availability_cache (if booking)

    loop Conversation
        T->>F: event media (μ-law base64)
        AS->>AS: process_incoming_audio
        WCM->>O: input_audio_buffer.append
        O-->>WCM: response.audio.delta
        AS->>AS: process_outgoing_audio
        WCM->>T: media + mark
    end

    OS->>OS: maybe_handle_tool_call
    OS->>WCM: finalize_goodbye → close Twilio WS
```

---

## 3. Media stream concurrency

Three coroutines run in `asyncio.gather()` inside `handle_media_stream()`:

```mermaid
flowchart TB
    subgraph Gather["asyncio.gather()"]
        TW_RCV["receive_from_twilio()"]
        OAI_RCV["receive_from_openai()"]
        RENEW["renew_openai_session()"]
    end

    TW_RCV -->|media| HME["handle_media_event → AudioService"]
    HME --> WCM["WebSocketConnectionManager.send_to_openai"]

    TW_RCV -->|start| HSS["handle_stream_start"]
    HSS --> OS["OpenAIService.initialize_session + greeting"]

    TW_RCV -->|mark| HMK["handle_mark_event → AudioService"]

    OAI_RCV -->|response.audio.delta| HAD["handle_audio_delta"]
    HAD --> AS["AudioService.process_outgoing_audio"]
    HAD --> WCM2["send_to_twilio"]

    OAI_RCV -->|input_audio_buffer.speech_started| HIS["handle_speech_started"]
    HIS --> TRUNC["truncate / clear (interruption)"]

    OAI_RCV -->|function_call, session.updated, response.done| HOE["handle_other_openai_event"]
    HOE --> TOOL["OpenAIService.maybe_handle_tool_call"]

    RENEW -->|every REALTIME_SESSION_RENEW_SECONDS| RECON["close + reconnect OpenAI WS"]
    RECON --> REINIT["initialize_session again"]
```

**Interruption guards** (`main.py`):

- Debounce after outgoing audio (`VAD_DEBOUNCE_AFTER_OUTGOING_MS`)
- Optional confirm window (`VAD_INTERRUPTION_CONFIRM_MS`) before truncating
- Goodbye flow is non-interruptible (`is_goodbye_pending()`)

---

## 4. Prompt pipeline

```mermaid
flowchart LR
    A["main_system_instructions.md"]
    B[".env placeholders"]
    C["config.build_system_message()"]
    D["Config.SYSTEM_MESSAGE"]
    E["OpenAISessionManager.create_session_update()"]
    F["OpenAI session.update"]

    A --> C
    B --> C
    C --> D --> E --> F

    G["outbound_service.build_outbound_system_message()"] -.->|outbound calls| E
    H["dynamic_settings (Supabase app_settings)"] -.->|per-call overrides| B
```

Injected placeholders include: `{agent_name}`, `{company_name}`, `{language_instruction}`, `{accent_instruction}`, `{reasoning_effort_instruction}`, `{tools_availability_instruction}`, `{call_record_instruction}`, `{booking_instruction}`, `{transfer_instruction}`.

For `gpt-realtime-2`, `REALTIME_REASONING_EFFORT` is set on the session payload.

---

## 5. Realtime tool routing

Tools are registered in `OpenAISessionManager._realtime_tools()` and executed in `OpenAIService.maybe_handle_tool_call()`.

```mermaid
flowchart TD
    EVT["OpenAI function_call event"]
    ACC["accumulate_tool_call"]
    VAL["_normalize_and_validate_tool_args"]
    OK{Valid args?}

    EVT --> ACC --> VAL --> OK
    OK -->|No| FAIL["Structured failure JSON to model"]
    OK -->|Yes| ROUTE{Tool name}

    ROUTE --> WFU["wait_for_user<br/>suppress audio, trigger_response=false"]
    ROUTE --> EC["end_call<br/>context-aware farewell → hangup"]
    ROUTE --> HH["request_human_handoff<br/>save record + Twilio redirect"]
    ROUTE --> SCR["save_call_record<br/>call_records_service → webhook_service"]
    ROUTE --> BK["booking tools<br/>google_calendar_booking_service"]
```

### Tool availability

| Tool | Always | Condition |
| --- | --- | --- |
| `wait_for_user` | Yes | — |
| `end_call` | Yes | — |
| `save_call_record` | No | `has_call_record_backend_configured()` |
| `request_human_handoff` | No | `Config.is_human_transfer_enabled()` |
| `get_availability` | No | Booking + Google Calendar |
| `book_appointment` | No | Booking + Google Calendar |
| `list_my_bookings` | No | Booking + Google Calendar |
| `edit_booking` | No | Booking + Google Calendar |
| `delete_booking` | No | Booking + Google Calendar |

Future external tools: `services/tool_registry.py` + `services/mcp_adapter.py` (disabled by default).

---

## 6. `wait_for_user` flow

```mermaid
sequenceDiagram
    participant O as OpenAI Realtime
    participant M as main.py
    participant OS as OpenAIService
    participant T as Twilio

    O->>M: function_call wait_for_user
    M->>OS: maybe_handle_tool_call
    OS->>OS: suppress_assistant_audio()
    OS->>O: tool output (trigger_response=false)
    M->>OS: finalize_wait_for_user (truncate/clear filler)
    Note over O,T: No spoken reply; VAD resumes when caller addresses agent
```

---

## 7. Call record storage

```mermaid
flowchart LR
    OS["OpenAIService tool handler"]
    CRS["call_records_service<br/>(facade)"]
    WS["webhook_service<br/>(adapter)"]
    WH["Webhook URL"]
    SB["Supabase call_records / leads"]
    ALT["Sheets / Email / Airtable / etc."]

    OS --> CRS --> WS
    WS --> WH
    WS --> SB
    WS --> ALT

    API["/calls REST + SSE"] --> CRS
    UI["static/dashboard.html"] --> API
```

---

## 8. Human transfer

```mermaid
sequenceDiagram
    participant AI as OpenAI Agent
    participant OS as OpenAIService
    participant CRS as call_records_service
    participant TS as TwilioService
    participant T as Twilio

    AI->>OS: request_human_handoff
    OS->>CRS: save_call_record_async (if backend configured)
    OS->>TS: redirect_call_to_url_async(callSid, TRANSFER_URL)
    TS->>T: Update live call
    T->>T: Fetch /twiml/transfer-to-agent
```

---

## 9. Outbound campaign

Requires `OUTBOUND_ENABLED=true` with Twilio + Supabase.

```mermaid
sequenceDiagram
    participant D as Dashboard
    participant F as FastAPI
    participant OBS as outbound_service
    participant SB as Supabase
    participant T as Twilio
    participant MS as /media-stream

    D->>F: POST /outbound/campaigns/{id}/start
    F->>OBS: Dial contacts (Twilio REST)
    T->>F: GET /outbound-call-twiml/{campaign_id}
    F-->>T: TwiML → wss://host/media-stream?direction=outbound&...
    T->>MS: WebSocket connect
    MS->>OBS: build_outbound_system_message()
    MS->>MS: Minimal outbound greeting (not inbound welcome)
    T->>F: POST /outbound-call-status
    OBS->>SB: Update contact status
```

---

## 10. Call recording and transcription

Optional when `CALL_RECORDING_ENABLED` is set.

```mermaid
flowchart TD
    START["handle_stream_start in main.py"]
    REC["TwilioService.start_call_recording_async"]
    CB["POST /recording-status"]
    PROXY["GET /recordings/{sid}/media"]
    TX["transcription_service (faster-whisper)"]
    ENH["POST /calls/{id}/enhance-transcript"]

    START --> REC
    REC --> CB
    CB --> SB["Update Supabase call record"]
    PROXY --> TX
    ENH --> SB
```

---

## 11. Module map

```mermaid
flowchart TB
    subgraph Entry
        main["main.py"]
        cfg["config.py"]
    end

    subgraph Prompt
        md["prompts/main_system_instructions.md"]
        si["system_instructions.py"]
    end

    subgraph Realtime
        oai["services/openai_service.py"]
        cm["services/connection_manager.py"]
        aud["services/audio_service.py"]
        twi["services/twilio_service.py"]
    end

    subgraph Optional
        gcal["google_calendar_booking_service.py"]
        out["outbound_service.py"]
        tx["transcription_service.py"]
        miss["missed_calls_service.py"]
        dyn["dynamic_settings.py"]
    end

    subgraph Storage
        crs["call_records_service.py"]
        wh["webhook_service.py"]
        ev["call_record_events.py"]
    end

    main --> oai & cm & twi
    cfg --> si --> md
    oai --> crs --> wh
    oai --> gcal
    main --> out & tx & miss & dyn
    crs --> ev
```

---

## 12. Configuration → behavior

| Setting | Effect |
| --- | --- |
| `OPENAI_API_KEY` | Required — authenticates OpenAI Realtime WebSocket |
| `OPENAI_REALTIME_MODEL=gpt-realtime-2` | Adds `reasoning.effort` to session payload |
| `REALTIME_SESSION_RENEW_SECONDS` | Preemptive session reconnect (default 3300 s) |
| `CALL_RECORD_BACKEND=supabase` | Enables `save_call_record` + dashboard |
| Google Calendar + booking env | Enables five booking tools |
| `HUMAN_TRANSFER_*` | Enables `request_human_handoff` |
| `OUTBOUND_ENABLED=true` | Enables `/outbound/*` campaign APIs |
| `CALL_RECORDING_ENABLED` | Starts Twilio recording on stream start |
| Supabase `app_settings` | Runtime overrides via `dynamic_settings` on connect |

---

## 13. Google Calendar booking flow

Tools run in `OpenAIService.maybe_handle_tool_call()`; calendar I/O is in `google_calendar_booking_service.py` via `run_in_executor` so the event loop stays responsive.

```mermaid
sequenceDiagram
    autonumber
    participant AI as OpenAI Agent
    participant OS as OpenAIService
    participant GBS as google_calendar_booking_service
    participant GCal as Google Calendar
    participant CRS as call_records_service
    participant ST as ConnectionState

    Note over AI,ST: New booking path
    AI->>OS: get_availability(days_ahead, for_date?)
    OS->>GBS: booking_get_availability (thread pool)
    GBS->>GCal: freeBusy + slot generation
    GCal-->>GBS: busy times
    GBS-->>OS: by_day + slots_flat (ISO start per slot)
    OS-->>AI: Tool result with display + ISO times

    AI->>OS: book_appointment(slot_start_iso, contact_*)
    OS->>GBS: booking_book_appointment
    GBS->>GCal: create event (caller_phone in extendedProperties)
    GBS->>GBS: invalidate_availability_cache()
    GBS-->>OS: success + confirmed_slot + event_id
    OS->>ST: appointment_booked, confirmed_slot_display
    OS->>CRS: sync_call_record_after_booking_action_async (if call_sid)
    OS-->>AI: Booking confirmation message

    Note over AI,ST: Manage existing booking
    AI->>OS: list_my_bookings(contact_phone)
    OS->>GBS: filter by caller_phone ownership
    GBS-->>OS: ranked candidates + event_id
    alt Reschedule
        AI->>OS: get_availability (fresh slots)
        AI->>OS: edit_booking(event_id, new_slot_start_iso)
        OS->>GBS: booking_edit_booking
        GBS->>GBS: invalidate_availability_cache()
        OS->>CRS: sync rescheduled call record
    else Cancel
        AI->>OS: delete_booking(event_id)
        OS->>GBS: booking_delete_booking
        GBS->>GBS: invalidate_availability_cache()
        OS->>CRS: sync cancelled call record
    end
```

**Cache:** `prewarm_availability_cache()` runs on stream start; mutations invalidate cache so the next `get_availability` reflects updated busy times.

---

## 14. Dashboard authentication

When `DASHBOARD_USERS` is unset, dashboard routes are open. When set, `_require_dashboard_key()` in `main.py` enforces auth.

Format: `DASHBOARD_USERS=user1:pass1,user2:pass2` (parsed in `Config.get_dashboard_auth()`).

```mermaid
flowchart TD
    REQ["Browser or API request<br/>/dashboard, /calls, /outbound/*, etc."]
    CHECK{DASHBOARD_USERS set?}
    OPEN["Allow — no auth required"]
    AUTH["_require_dashboard_key()"]

    REQ --> CHECK
    CHECK -->|No| OPEN
    CHECK -->|Yes| AUTH

    AUTH --> C1{Valid session cookie?<br/>dashboard_session}
    C1 -->|Yes| OK["Authorized"]
    C1 -->|No| C2{?key= or X-Dashboard-Key<br/>matches any user password?}
    C2 -->|Yes| OK
    C2 -->|No| C3{Accept: text/html?}
    C3 -->|Yes| LOGIN["302 → /login?next=..."]
    C3 -->|No| UNAUTH["401 JSON"]

    LOGIN --> FORM["POST /login<br/>username + password"]
    FORM --> VALID{Credentials match<br/>DASHBOARD_USERS?}
    VALID -->|No| ERR["401 login.html error"]
    VALID -->|Yes| COOKIE["Set signed cookie<br/>expiry.username.HMAC"]
    COOKIE --> REDIR["Redirect to next path"]
    REDIR --> OK
```

**Session cookie:** HMAC-signed value `expiry.username.sig` (24 h TTL). Signing key is the first user's password from `DASHBOARD_USERS`.

**API note:** `/calls/events` (SSE) accepts cookie or `?key=` because browser `EventSource` cannot send custom headers.

---

## 15. Dashboard live updates

Requires `CALL_RECORD_BACKEND=supabase`.

```mermaid
sequenceDiagram
    participant UI as dashboard.html
    participant API as FastAPI /calls
    participant SSE as /calls/events
    participant EV as call_record_events
    participant WH as webhook_service
    participant SB as Supabase

    UI->>API: GET /calls?key= or cookie
    API->>WH: list_call_records_sync
    WH->>SB: SELECT call_records
    SB-->>UI: JSON rows

    UI->>SSE: EventSource /calls/events
    SSE->>EV: register_subscriber(queue)

    Note over WH,SB: save_call_record or dashboard PATCH
    WH->>EV: notify_subscribers()
    EV->>SSE: call_records_changed
    SSE-->>UI: SSE data event
    UI->>API: Re-fetch /calls
```

---

## 16. Deployment topology

Production path: `./scripts/deploy-cloudrun.sh` → Google Cloud Run service `speech-assistant` (region `us-central1`, timeout 3600 s).

Local dev: `python main.py` + ngrok for Twilio webhook.

```mermaid
flowchart TB
    subgraph Dev["Local development"]
        APP_LOCAL["python main.py :5050"]
        NGROK["ngrok http 5050"]
        APP_LOCAL --> NGROK
    end

    subgraph GCP["Google Cloud Run"]
        CR["speech-assistant service<br/>us-central1 · timeout 3600s"]
        SEC["Secret Manager<br/>google-calendar-credentials"]
        ENV["Env vars from .env<br/>(deploy-cloudrun.sh)"]
        ENV --> CR
        SEC -->|GOOGLE_CALENDAR_CREDENTIALS_JSON| CR
    end

    subgraph External["External integrations"]
        TW["Twilio Voice<br/>webhook + media streams"]
        OAI["OpenAI Realtime API"]
        SB["Supabase (optional)"]
        GCAL["Google Calendar (optional)"]
    end

    NGROK -->|HTTPS /incoming-call| TW
    CR -->|HTTPS /incoming-call| TW
    TW -->|WSS /media-stream| CR
    CR --> OAI
    CR --> SB
    CR --> GCAL

    TW -->|POST /recording-status| CR
    TW -->|POST /outbound-call-status| CR
```

**Deploy script skips:** `PORT` (Cloud Run sets it), `GOOGLE_CALENDAR_CREDENTIALS_JSON` and `GOOGLE_APPLICATION_CREDENTIALS` as local file paths — mount via Cloud Run secrets instead.

**Post-deploy:** Point Twilio Voice webhook to `{SERVICE_URL}/incoming-call`. If recording is enabled, set `RECORDING_STATUS_CALLBACK_BASE_URL` to the service URL.

---

## 17. Missed calls and AI callback

Source: `services/missed_calls_service.py`, `/missed-calls/*` in `main.py`.

A missed call is either:
1. Twilio inbound status in `{no-answer, busy, failed, canceled}`, or
2. Inbound `completed` with **no** Supabase call-record row (caller hung up before `save_call_record`).

Handled calls (`lead_status=missed_handled`) are hidden from the list.

```mermaid
flowchart TD
    subgraph List["GET /missed-calls"]
        TW["Twilio Calls API<br/>inbound to TWILIO_OUTBOUND_NUMBER"]
        FILTER["Filter missed statuses + completed-without-record"]
        SB1["Cross-ref Supabase call_sid statuses"]
        OUT["JSON missed_calls array"]
        TW --> FILTER --> SB1 --> OUT
    end

    subgraph Actions["Dashboard actions"]
        MARK["POST /missed-calls/{sid}/handled"]
        CB["POST /missed-calls/{sid}/callback-ai"]
    end

    MARK --> UPSERT["Upsert call record<br/>status=missed_handled"]

    CB --> CAMP["get_or_create_callback_campaign_sync<br/>__missed_call_callbacks__"]
    CAMP --> CONTACT["add_callback_contact_sync"]
    CONTACT --> DIAL["TwilioService.create_outbound_call"]
    DIAL --> TWIML["/outbound-call-twiml/{campaign_id}"]
    TWIML --> MS["WS /media-stream (outbound)"]

    DIAL --> STATUS["POST /outbound-call-status"]
    STATUS --> FIN["finalize_callback_if_missed_sync"]
    FIN -->|completed| UPSERT
    FIN --> NOTE["Link new lead row to original missed CallSid"]
```

**Requirements:** Twilio credentials for list/dial; Supabase for AI callback (reuses outbound pipeline); public `OUTBOUND_BASE_URL` (not localhost).

---

## 18. Transcription pipeline

Post-call transcription uses **faster-whisper**; optional OpenAI chat enhancement formats dialogue and adds summary/issues.

```mermaid
sequenceDiagram
    autonumber
    participant MS as media-stream
    participant TS as TwilioService
    participant T as Twilio
    participant CB as POST /recording-status
    participant SB as Supabase
    participant UI as dashboard.html
    participant API as FastAPI
    participant TX as transcription_service

    Note over MS,T: Recording capture
    MS->>TS: start_call_recording_async(callSid)
    TS->>T: Twilio REST Recordings API
    T->>CB: RecordingStatusCallback (completed)
    CB->>SB: Update call record recording_link

    Note over UI,TX: Manual or dashboard-triggered transcribe
    UI->>API: POST /recordings/{sid}/transcribe?record_id=
    API->>TX: transcribe_recording (thread)
    TX->>T: Fetch MP3 by Recording SID
    TX->>TX: transcribe_audio (faster-whisper)
    opt TRANSCRIPT_ENHANCEMENT_MODE=auto
        TX->>TX: enhance_transcript (OpenAI mini)
    end
    TX-->>API: transcript text
    API->>SB: Update call record transcript
    API-->>UI: JSON transcript

    Note over UI,TX: Manual enhancement
    UI->>API: POST /calls/{id}/enhance-transcript
    API->>TX: enhance_transcript_with_summary
    TX-->>API: transcript + summary + issues
    API->>SB: Save enhanced fields
```

| Step | Env / gate |
| --- | --- |
| Start recording | `CALL_RECORDING_ENABLED=true` + `RECORDING_STATUS_CALLBACK_BASE_URL` |
| Whisper transcribe | `TRANSCRIPTION_MODEL` (e.g. `tiny`) + Twilio credentials |
| Auto-enhance on transcribe | `TRANSCRIPT_ENHANCEMENT_MODE=auto` |
| Manual enhance button | `TRANSCRIPT_ENHANCEMENT_MODE=manual` + Supabase backend |
| Playback in dashboard | `GET /recordings/{sid}/media` (server-side Twilio Basic Auth proxy) |

---

## 19. First deploy checklist

End-to-end path from zero to a working phone agent with optional dashboard.

```mermaid
flowchart TD
    S1["1. Clone + venv<br/>pip install -r requirements.txt"]
    S2["2. cp .env.example .env"]
    S3["3. Set OPENAI_API_KEY"]
    S4["4. Customize prompt<br/>prompts/main_system_instructions.md"]
    S5["5. Local test<br/>python main.py"]
    S6["6. Expose HTTPS<br/>ngrok OR ./scripts/deploy-cloudrun.sh"]
    S7["7. Twilio webhook<br/>{URL}/incoming-call"]
    S8["8. Place test call"]
    S9{"Optional dashboard?"}
    S10["9. Supabase schema<br/>docs/supabase-schema/"]
    S11["10. CALL_RECORD_BACKEND=supabase<br/>+ SUPABASE_URL/KEY"]
    S12["11. DASHBOARD_USERS=user:pass"]
    S13{"Optional booking?"}
    S14["12. Google Calendar creds<br/>+ booking env vars"]
    S13B{"Optional recording?"}
    S15["13. CALL_RECORDING_ENABLED<br/>+ RECORDING_STATUS_CALLBACK_BASE_URL"]
    S16["14. TRANSCRIPTION_MODEL=tiny"]

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9
    S9 -->|Yes| S10 --> S11 --> S12
    S9 -->|No| DONE["Live voice agent"]
    S12 --> S13
    S13 -->|Yes| S14 --> S13B
    S13 -->|No| S13B
    S13B -->|Yes| S15 --> S16 --> DONE
    S13B -->|No| DONE
```

### Minimum viable (phone agent only)

| # | Action | Verify |
| --- | --- | --- |
| 1 | Set `OPENAI_API_KEY` | App starts without config error |
| 2 | Run `python main.py` | Listening on port 5050 |
| 3 | Public HTTPS URL (ngrok or Cloud Run) | Twilio can reach webhook |
| 4 | Twilio Voice → `{URL}/incoming-call` | Inbound call connects to AI |
| 5 | Edit `prompts/main_system_instructions.md` | Agent behavior matches intent |

### Optional layers (enable in order)

| Layer | Key env vars | Unlocks |
| --- | --- | --- |
| Dashboard | `CALL_RECORD_BACKEND=supabase`, Supabase creds, `DASHBOARD_USERS` | `/dashboard`, `save_call_record` tool |
| Booking | Google Calendar JSON + `GOOGLE_CALENDAR_ID` + booking flags | Five calendar tools |
| Outbound | `OUTBOUND_ENABLED=true`, Twilio + Supabase, `OUTBOUND_BASE_URL` | Campaign dial APIs |
| Recording | `CALL_RECORDING_ENABLED`, `RECORDING_STATUS_CALLBACK_BASE_URL` | Twilio recordings on call records |
| Transcription | `TRANSCRIPTION_MODEL` | Whisper transcribe from dashboard |
| Missed calls | Twilio creds + Supabase | `/missed-calls`, AI callback |

---

## 20. Dynamic settings (dashboard overrides)

Source: `services/dynamic_settings.py`, `GET/PATCH /settings` in `main.py`.

Overrides load from Supabase `app_settings` when `CALL_RECORD_BACKEND=supabase`. Applied on every `/media-stream` connect and when the dashboard opens Settings.

```mermaid
flowchart TD
    ENV[".env + config.py<br/>(process defaults)"]
    SB["Supabase app_settings table"]
    LOAD["load_overrides_sync()"]
    APPLY["apply_overrides_to_config()"]
    CFG["Config.* attributes"]
    REBUILD["rebuild_system_message()<br/>(if language/accent/company/booking flags changed)"]
    SESSION["OpenAISessionManager.create_session_update()"]
    CALL["Each inbound call<br/>handle_media_stream on connect"]

    ENV --> CFG
    SB --> LOAD --> APPLY --> CFG
    APPLY --> REBUILD
    REBUILD --> CFG
    CFG --> SESSION

    DASH["Dashboard Settings modal"] -->|PATCH /settings| SAVE["save_overrides_sync()"]
    SAVE --> SB
    SAVE --> APPLY

    CALL --> LOAD
    CALL --> APPLY
```

### Override categories (selected keys)

| Category | Example keys |
| --- | --- |
| Voice / model | `VOICE`, `OPENAI_REALTIME_MODEL`, `REALTIME_REASONING_EFFORT`, `TEMPERATURE` |
| Language / accent | `ASSISTANT_LANGUAGE`, `ASSISTANT_ACCENT`, `LANGUAGE_SWITCH_POLICY` |
| VAD | `VAD_MODE`, `VAD_THRESHOLD`, `VAD_DEBOUNCE_AFTER_OUTGOING_MS`, `VAD_INTERRUPTION_CONFIRM_MS` |
| Booking | `BOOKING_ENABLED`, `BOOKING_DAYS_ENABLED`, `GOOGLE_CALENDAR_ID`, slot hours |
| Ops | `CALL_RECORDING_ENABLED`, `TRANSCRIPTION_MODEL`, `HUMAN_TRANSFER_ENABLED` |

Prompt-affecting keys trigger `rebuild_system_message()`; booking keys also sync to `os.environ` for calendar helpers.

---

## 21. `end_call` goodbye state machine

Source: `OpenAIService.maybe_handle_tool_call()` + `main.py` event handlers.

```mermaid
stateDiagram-v2
    [*] --> ActiveCall

    ActiveCall --> GoodbyeQueued: end_call tool
    GoodbyeQueued --> GoodbyeQueued: duplicate end_call ignored

    GoodbyeQueued --> FarewellPlaying: response.create with farewell instructions
    FarewellPlaying --> AudioHeard: response.audio.delta → mark_goodbye_audio_heard

    GoodbyeQueued --> Finalizing: watchdog timeout (no audio)
    note right of GoodbyeQueued
        END_CALL_WATCHDOG_SECONDS
        default 10s (config.py)
    end note

    AudioHeard --> Finalizing: response.done matches goodbye item_id
    note right of AudioHeard
        Interruptions blocked
        is_goodbye_pending()
    end note

    Finalizing --> GraceSleep: finalize_goodbye()
    GraceSleep --> Hangup: END_CALL_GRACE_SECONDS (default 6s)
    Hangup --> [*]: Twilio REST completed + close Twilio WS
```

### Context-aware farewell text

`get_farewell_instruction()` in `system_instructions.py` picks instructions based on `ConnectionState`:

| State | Farewell emphasis |
| --- | --- |
| `appointment_booked` + `confirmed_slot_display` | Confirm appointment time |
| `priority` = emergency/high/urgent | Time-sensitive follow-up |
| `call_record_saved` | Details saved for team |
| Default | Brief polite goodbye |

---

## 22. Prompt architecture map

How the starter aligns behavior across markdown, config, and runtime. Full guide mapping: [STARTER_PROMPT_MAPPING.md](./references/STARTER_PROMPT_MAPPING.md).

```mermaid
flowchart LR
    subgraph Static["Static behavior"]
        MD["main_system_instructions.md<br/>Role, flow, tools rules, safety"]
    end

    subgraph Injected["config.py builders"]
        LANG["language_instruction"]
        ACC["accent_instruction"]
        REAS["reasoning_effort_instruction"]
        TOOLS["tools_availability_instruction"]
        CR["call_record_instruction"]
        BK["booking_instruction"]
        TR["transfer_instruction"]
    end

    subgraph Runtime["Runtime assembly"]
        RENDER["system_instructions.render_system_instructions()"]
        MSG["Config.SYSTEM_MESSAGE"]
        SESS["session.update instructions"]
        TOOLREG["OpenAISessionManager._realtime_tools()"]
    end

    MD --> RENDER
    LANG & ACC & REAS & TOOLS & CR & BK & TR --> RENDER
    RENDER --> MSG --> SESS
    TOOLREG --> SESS

    DYN["dynamic_settings<br/>(Supabase app_settings)"] -.->|rebuild on change| MSG
    OUT["outbound_system_message"] -.->|outbound calls| SESS
```

### Where to change what

| Goal | Edit first |
| --- | --- |
| Agent behavior / conversation rules | `prompts/main_system_instructions.md` |
| Language, accent, reasoning effort | `.env` or dashboard Settings (`dynamic_settings`) |
| Tool availability text in prompt | `config.py` builders (driven by env flags) |
| Tool schemas + side effects | `services/openai_service.py` |
| Greeting / farewell phrasing | `system_instructions.py` |
| OpenAI Realtime alignment audit | [openai-realtime-models-prompting.md](./references/openai-realtime-models-prompting.md) |

After prompt or builder changes: `pytest tests/test_system_instructions.py`.

---

## 23. External tools scaffold (MCP + tool registry)

The starter ships a **disabled-by-default** extension point for tools beyond the built-in set. Built-in tools stay in `openai_service.py`; external tools register through `tool_registry.py`.

```mermaid
flowchart TD
    subgraph Builtin["Built-in (always in openai_service.py)"]
        BT["wait_for_user, end_call"]
        COND["save_call_record, booking, transfer<br/>(conditional on config)"]
    end

    subgraph Scaffold["Extension scaffold (v1 no-op)"]
        REG["ToolRegistry<br/>external_tool_registry"]
        MCP["mcp_adapter.load_mcp_tools()"]
        REGIST["RegisteredTool<br/>name + schema + handler"]
    end

    subgraph Session["Session registration"]
        RT["_realtime_tools()"]
        SESS["session.update tools array"]
    end

    subgraph Dispatch["Runtime dispatch"]
        MHC["maybe_handle_tool_call()"]
        HAND["registered_tool.handler(args, connection_manager)"]
        OUT["_send_tool_result → OpenAI"]
    end

    BT --> RT
    COND --> RT
    MCP --> REG
    REGIST --> REG
    REG --> RT
    RT --> SESS

    MHC -->|built-in names| Builtin
    MHC -->|unknown name| REG
    REG -->|handler set| HAND --> OUT
    REG -->|no handler| OUT
```

### Integration steps (when implementing MCP)

Documented in `services/mcp_adapter.py`:

1. Load allowed MCP servers/tools from config.
2. Convert MCP tool schemas to OpenAI Realtime function schemas.
3. Register via `external_tool_registry.register(RegisteredTool(...))`.
4. `load_mcp_tools()` runs inside `_realtime_tools()` before session start.
5. `maybe_handle_tool_call()` dispatches to `handler` after built-in tools miss.

### Current v1 behavior

| Component | Status |
| --- | --- |
| `services/tool_registry.py` | `ToolRegistry` + empty `external_tool_registry` |
| `services/mcp_adapter.py` | `load_mcp_tools()` is a no-op |
| `openai_service.py` | Imports registry; extends tools list; dispatches external handlers |
| Prompt | Built-in tools only — external tools need prompt text when enabled |

No MCP runtime dependency is bundled in the starter requirements.

