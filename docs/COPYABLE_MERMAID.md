# Copyable Mermaid Architecture Diagrams

Use this file when you want to paste architecture source into ChatGPT, a Mermaid
renderer, or an image-generation prompt. These diagrams describe the current
repo structure: FastAPI + Twilio Media Streams + OpenAI Realtime, with optional
Supabase, outbound campaigns, Google Calendar, recording, and transcription.

## ChatGPT Image 2.0 Prompt

Paste one Mermaid block at a time, then use this prompt:

```text
Create a clean 16:9 technical architecture diagram from this Mermaid source.
Keep the exact components, route names, service names, and data-flow meaning.
Do not invent services or add extra runtime prompts.

Important accuracy rules:
- Show inbound and outbound calls converging on WS /media-stream.
- Show prompts being selected and sent at WS /media-stream via OpenAIService
  session.update, not directly from /incoming-call or /outbound-call-twiml.
- Show exactly one OpenAI Realtime instructions string per call:
  inbound uses Config.SYSTEM_MESSAGE; outbound uses build_outbound_system_message().
- Label prompts/generic_appointment_setter.md as the generic appointment-setter template input.
- Label prompts/aesthetic_appointment_setter.md as an optional sample template input,
  not a separate prompt sent directly to OpenAI.
- Show dynamic_settings.py updating shared Config values for both inbound and outbound.
- Show /outbound-call-status as the outbound completion callback that updates
  outbound contact status.

Use color groups for actors, FastAPI routes, shared realtime core, prompt paths,
Realtime tools, CRM/storage, Google Calendar, and post-call artifacts. Keep the
diagram readable and avoid crossing lines where possible.
```

For the full poster, use the master flowchart. For product demos, use the
use-case flow and one or two sequence diagrams.

---

## 1. Master Flow Diagram

```mermaid
flowchart TB
    subgraph Actors
        Caller["Inbound caller"]
        Callee["Outbound callee"]
        Operator["Dashboard operator"]
        ExternalContact["External contact source<br/>GHL / n8n / API / Insomnia"]
        Human["Human transfer target"]
    end

    subgraph FastAPI["FastAPI app - main.py"]
        Incoming["/incoming-call"]
        OutboundStart["/outbound/campaigns/{id}/start"]
        SingleDial["/outbound/campaigns/{id}/contacts/{id}/call"]
        TriggerCall["/outbound/campaigns/{id}/trigger-call"]
        MissedCallback["/missed-calls/{call_sid}/callback-ai"]
        OutboundTwiML["/outbound-call-twiml/{campaign_id}"]
        OutboundStatus["/outbound-call-status"]
        MediaStream["WS /media-stream"]
        CallsAPI["/calls + /calls/events"]
        RecordingsAPI["/recordings/* + /recording-status"]
        TransferTwiML["/twiml/transfer-to-agent"]
        SettingsAPI["/settings"]
    end

    subgraph RealtimeCore["Shared realtime core"]
        TwilioService["services/twilio_service.py"]
        ConnectionManager["services/connection_manager.py"]
        AudioService["services/audio_service.py"]
        OpenAIService["services/openai_service.py"]
        OpenAIRealtime["OpenAI Realtime API"]
    end

    subgraph Prompting["Prompt paths"]
        ConfigState["config.py shared Config<br/>env + dashboard overrides"]
        InboundPrompt["Inbound instructions<br/>prompts/main_system_instructions.md<br/>system_instructions.py -> Config.SYSTEM_MESSAGE"]
        OutboundPrompt["Outbound instructions<br/>outbound_service.build_outbound_system_message()<br/>campaign template + contact data + contact context"]
        AppointmentPrompt["prompts/generic_appointment_setter.md<br/>template input for campaign_type=appointment_setter"]
        AestheticPrompt["prompts/aesthetic_appointment_setter.md<br/>optional sample template"]
        SessionUpdate["OpenAIService session.update<br/>one instructions string per call"]
    end

    subgraph Tools["Realtime tools"]
        CoreTools["Always registered<br/>wait_for_user<br/>end_call"]
        RecordTool["CRM tool<br/>save_call_record"]
        TransferTool["Transfer tool<br/>request_human_handoff"]
        BookingTools["Booking tools<br/>get_availability<br/>book_appointment<br/>list_my_bookings<br/>edit_booking<br/>delete_booking"]
    end

    subgraph Data["Storage and operations"]
        Supabase["Supabase<br/>call_records / app_settings<br/>outbound_campaigns / outbound_contacts"]
        CallRecords["services/call_records_service.py<br/>facade"]
        WebhookAdapter["services/webhook_service.py<br/>Supabase/webhook adapter"]
        OutboundService["services/outbound_service.py"]
        MissedCalls["services/missed_calls_service.py"]
        DynamicSettings["services/dynamic_settings.py"]
        ExternalCRM["External CRM webhook<br/>WEBHOOK_URL"]
    end

    subgraph Calendar["Google Calendar"]
        BookingService["services/google_calendar_booking_service.py"]
        GoogleCalendar["Google Calendar API"]
    end

    subgraph PostCall["Post-call artifacts"]
        TwilioRecording["Twilio recording"]
        Transcription["services/transcription_service.py<br/>faster-whisper + OpenAI enhancement"]
        Dashboard["static/dashboard.html"]
    end

    Caller --> Twilio["Twilio Voice"]
    Twilio --> Incoming
    Incoming --> TwilioService
    TwilioService -.->|"returns TwiML Connect Stream"| Twilio
    Twilio -->|"opens WebSocket"| MediaStream

    Operator --> OutboundStart
    Operator --> SingleDial
    ExternalContact --> TriggerCall
    Operator --> MissedCallback
    OutboundStart --> OutboundService
    SingleDial --> OutboundService
    TriggerCall --> OutboundService
    MissedCallback --> MissedCalls --> OutboundService
    OutboundService --> Supabase
    OutboundService --> Twilio
    Twilio --> Callee
    Twilio --> OutboundTwiML
    OutboundTwiML --> TwilioService
    TwilioService -.->|"returns TwiML + outbound parameters"| Twilio
    Twilio -->|"answered outbound call opens WebSocket"| MediaStream
    Twilio --> OutboundStatus --> OutboundService

    MediaStream --> ConnectionManager
    ConnectionManager --> AudioService
    ConnectionManager --> OpenAIService
    OpenAIService <--> OpenAIRealtime
    ConnectionManager <--> Twilio

    SettingsAPI --> DynamicSettings --> Supabase
    DynamicSettings -.-> ConfigState
    ConfigState -.-> InboundPrompt
    ConfigState -.-> OutboundPrompt
    MediaStream -.->|"inbound: system_message_override=None"| InboundPrompt
    MediaStream -.->|"outbound: campaign_id + contact_id"| OutboundPrompt
    AppointmentPrompt -.->|"template input only"| OutboundPrompt
    AestheticPrompt -.->|"sample template input only"| OutboundPrompt
    InboundPrompt --> SessionUpdate
    OutboundPrompt --> SessionUpdate
    SessionUpdate --> OpenAIService

    OpenAIService -.->|"registers schemas; handles function calls"| CoreTools
    OpenAIService -.->|"registers schema; handles function call"| RecordTool
    OpenAIService -.->|"registers schema; handles function call"| TransferTool
    OpenAIService -.->|"registers schemas; handles function calls"| BookingTools
    OpenAIRealtime -->|"function_call events"| OpenAIService
    RecordTool --> CallRecords
    TransferTool --> TransferTwiML --> Human
    BookingTools --> BookingService --> GoogleCalendar

    CallRecords --> WebhookAdapter
    WebhookAdapter --> Supabase
    WebhookAdapter --> ExternalCRM
    BookingService -.-> CallRecords

    Dashboard --> CallsAPI --> CallRecords
    Dashboard --> SettingsAPI
    TwilioRecording --> RecordingsAPI --> CallRecords
    RecordingsAPI --> Transcription --> CallRecords

    classDef inbound fill:#e0f2fe,stroke:#0369a1,stroke-width:2px
    classDef outbound fill:#dcfce7,stroke:#166534,stroke-width:2px
    classDef core fill:#ffedd5,stroke:#c2410c,stroke-width:2px
    classDef data fill:#fef9c3,stroke:#a16207,stroke-width:2px
    classDef calendar fill:#fce7f3,stroke:#be185d,stroke-width:2px
    classDef post fill:#ede9fe,stroke:#6d28d9,stroke-width:2px

    class Caller,Incoming,InboundPrompt inbound
    class Callee,ExternalContact,OutboundStart,SingleDial,TriggerCall,MissedCallback,OutboundTwiML,OutboundStatus,OutboundService,MissedCalls,OutboundPrompt,AppointmentPrompt,AestheticPrompt outbound
    class MediaStream,TwilioService,ConnectionManager,AudioService,OpenAIService,OpenAIRealtime,CoreTools,RecordTool,TransferTool,BookingTools,SessionUpdate core
    class Supabase,CallRecords,WebhookAdapter,DynamicSettings,ExternalCRM,CallsAPI,SettingsAPI,ConfigState data
    class BookingService,GoogleCalendar calendar
    class RecordingsAPI,TwilioRecording,Transcription,Dashboard post
```

---

## 2. Use-Case Flow Diagram

```mermaid
flowchart LR
    subgraph UseCases["Supported use cases"]
        UC1["Inbound AI receptionist<br/>Caller dials Twilio number"]
        UC2["Outbound campaign<br/>Bulk dial pending contacts"]
        UC3["Dashboard single dial<br/>Call one contact now"]
        UC4["One-shot contact API<br/>GHL / n8n POSTs one contact"]
        UC5["Missed-call AI callback<br/>Call back an inbound missed call"]
        UC6["Post-call review<br/>Recording, transcript, enhancement"]
    end

    subgraph EntryPoints["Entry points"]
        E1["/incoming-call"]
        E2["POST /outbound/campaigns/{id}/start"]
        E3["POST /outbound/campaigns/{id}/contacts/{id}/call"]
        E4["POST /outbound/campaigns/{id}/trigger-call"]
        E5["POST /missed-calls/{call_sid}/callback-ai"]
        E6["/recordings/* and /calls/{id}/enhance-transcript"]
    end

    subgraph SharedPipeline["Shared call pipeline"]
        TwilioDial["Twilio voice call"]
        TwiML["TwiML stream response"]
        Stream["WS /media-stream"]
        Realtime["OpenAI Realtime session"]
        Tools["Tools: call record, booking, transfer"]
    end

    subgraph Outcomes["Outcomes"]
        CRM["Supabase call record or webhook payload"]
        Calendar["Google Calendar event"]
        Transfer["Human transfer"]
        Transcript["Recording + transcript + summary/issues"]
    end

    UC1 --> E1 --> TwiML
    UC2 --> E2 --> TwilioDial
    UC3 --> E3 --> TwilioDial
    UC4 --> E4 --> TwilioDial
    UC5 --> E5 --> TwilioDial
    TwilioDial --> TwiML --> Stream --> Realtime --> Tools
    Tools --> CRM
    Tools --> Calendar
    Tools --> Transfer
    UC6 --> E6 --> Transcript --> CRM
```

---

## 3. Inbound Call Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Twilio
    participant API as FastAPI main.py
    participant TS as TwilioService
    participant WS as WS /media-stream
    participant CM as WebSocketConnectionManager
    participant OS as OpenAIService
    participant OAI as OpenAI Realtime
    participant CRM as call_records_service

    Caller->>Twilio: Calls Twilio number
    Twilio->>API: GET/POST /incoming-call
    API->>TS: create_incoming_call_response(request)
    TS-->>Twilio: TwiML Connect Stream + caller_number
    Twilio->>WS: WebSocket connect /media-stream
    WS->>CM: start event with CallSid, From, streamSid
    CM->>OAI: WebSocket connect
    OS->>OAI: session.update with Config.SYSTEM_MESSAGE + tools
    OS->>OAI: send_initial_greeting(full inbound welcome)
    loop Conversation
        Twilio->>CM: media frames
        CM->>OAI: input_audio_buffer.append
        OAI-->>CM: response.output_audio.delta
        CM-->>Twilio: media frames
    end
    OAI->>OS: function_call save_call_record
    OS->>CRM: save_call_record_async(payload)
```

---

## 4. One-Shot Outbound Contact API Sequence

Use this for GHL, n8n, Insomnia, or any API client that wants to submit one contact
payload and trigger one outbound call against an existing campaign. Lead-shaped
CRM payloads are still accepted for compatibility.

```mermaid
sequenceDiagram
    autonumber
    participant Source as GHL / n8n / API Client
    participant API as FastAPI main.py
    participant OBS as outbound_service
    participant SB as Supabase
    participant TW as Twilio
    participant Contact as Contact phone
    participant MS as WS /media-stream
    participant OAI as OpenAI Realtime

    Source->>API: POST /outbound/campaigns/{campaign_id}/trigger-call<br/>contact JSON + dashboard auth
    API->>OBS: build_contact_from_payload(body)
    API->>OBS: add_contacts_sync(campaign_id, contact)
    OBS->>SB: Insert outbound_contacts row
    API->>OBS: _dial_outbound_contact_now(campaign_id, contact_id)
    OBS->>TW: create_outbound_call(to=contact.phone)
    TW->>Contact: Ring phone
    Contact-->>TW: Answer
    TW->>API: GET /outbound-call-twiml/{campaign_id}?contact_id=...
    API-->>TW: TwiML Connect Stream + outbound parameters
    TW->>MS: WebSocket connect
    MS->>OBS: build_outbound_system_message(campaign_id, contact_id)
    OBS->>SB: Fetch campaign, contact, custom_fields
    MS->>OAI: session.update with campaign prompt + contact context
    MS->>OAI: send_initial_greeting(is_outbound=true)
    TW->>API: POST /outbound-call-status
    API->>OBS: update_contact_status_sync
```

---

## 5. Appointment Setter Booking Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Contact
    participant AI as OpenAI Realtime Agent
    participant OS as OpenAIService
    participant Cal as google_calendar_booking_service
    participant GCal as Google Calendar
    participant CRM as call_records_service

    AI->>Contact: Opens with interest/offer context from lead_offer/contact_latest_optin
    Contact->>AI: Interested in appointment
    AI->>OS: get_availability(days_ahead, for_date?, caller_timezone?)
    OS->>Cal: booking_get_availability()
    Cal->>GCal: freeBusy query in business timezone
    GCal-->>Cal: Busy windows
    Cal-->>OS: Available slots with business/caller display
    OS-->>AI: Tool result
    AI->>Contact: Offers two available times
    Contact->>AI: Chooses a slot
    AI->>OS: book_appointment(slot_start_iso, contact details)
    OS->>Cal: booking_book_appointment()
    Cal->>GCal: Create calendar event
    Cal-->>OS: confirmed_slot + calendar_event_link
    OS->>CRM: sync_call_record_after_booking_action_async()
    AI->>OS: save_call_record(outcome_tag=booked, confirmed_slot)
    OS->>CRM: Save/update call record
```

---

## 6. Call Record, Recording, And Transcript Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant AI as OpenAI Realtime
    participant OS as OpenAIService
    participant CRM as call_records_service
    participant SB as Supabase call_records
    participant TW as Twilio
    participant API as FastAPI main.py
    participant UI as Dashboard
    participant TX as transcription_service

    AI->>OS: function_call save_call_record
    OS->>CRM: build_call_record_payload()
    CRM->>SB: Insert/update row with call_sid, summaries, status, metadata

    Note over TW,API: Recording enabled
    TW->>API: POST /recording-status with CallSid + RecordingUrl
    API->>CRM: update_call_record_by_call_sid(recording_link)
    CRM->>SB: Store recording_link

    UI->>API: GET /recordings/{recording_sid}/media
    API->>TW: Fetch MP3 with server-side Twilio auth
    API-->>UI: audio/mpeg with byte-range support

    UI->>API: POST /recordings/{recording_sid}/transcribe?record_id=...
    API->>TX: transcribe_recording()
    TX->>TW: Download recording MP3
    TX->>TX: faster-whisper transcription
    API->>CRM: update transcript
    CRM->>SB: Store transcript

    UI->>API: POST /calls/{record_id}/enhance-transcript
    API->>TX: enhance_transcript_with_summary()
    TX->>TX: OpenAI text model formats transcript + summary + issues
    API->>CRM: update transcript_enhanced_at, transcript_summary, transcript_issues
    CRM->>SB: Store enhanced transcript fields

    UI->>API: PATCH /calls/{record_id}
    API->>CRM: Save notes, lead_status, name, location
```

---

## 7. Diagram Use-Case Prompts

Use these prompts with the Mermaid blocks above:

| Use case | Prompt |
| --- | --- |
| Master architecture poster | "Render the master flow as a 16:9 technical architecture poster. Emphasize shared `WS /media-stream`, one OpenAI Realtime `session.update` instructions string per call, inbound vs outbound prompt selection, four outbound triggers, Supabase, Google Calendar, and post-call artifacts." |
| Outbound API demo | "Render the one-shot outbound sequence for GHL/n8n contact intake. Highlight POST `/trigger-call`, Supabase contact insert, Twilio dial, and Realtime prompt construction." |
| Appointment setter demo | "Render the generic appointment setter booking flow. Highlight interest or offer context, availability lookup, two slot choices, Google Calendar booking, and call-record update." |
| Call-record lifecycle | "Render the call-record lifecycle as staged enrichment: live summary, recording link, playback, Whisper transcript, OpenAI enhancement, manual notes/status." |
| Executive overview | "Use the use-case flow diagram. Make it simple and business-readable: inbound, outbound, booking, dashboard, transcript review." |

### Copy-Ready ChatGPT Image 2.0 Prompt

Use this with the **Master Flow Diagram** Mermaid block:

```text
Create a clean 16:9 technical architecture poster from this Mermaid diagram.
Use the Mermaid as the source of truth. Keep all route names, service names,
data stores, tools, and APIs exactly as shown. Do not invent extra services.

Accuracy requirements:
- Inbound and outbound calls must both converge on WS /media-stream.
- /incoming-call and /outbound-call-twiml return TwiML; they do not send prompts
  directly to OpenAI.
- Prompt selection happens at WS /media-stream before OpenAIService sends
  session.update.
- Show exactly one OpenAI Realtime instructions string per call:
  inbound uses Config.SYSTEM_MESSAGE; outbound uses build_outbound_system_message().
- prompts/aesthetic_appointment_setter.md is only an outbound campaign template
  input, not a separate runtime prompt sent directly to OpenAI.
- dynamic_settings.py updates shared Config values used by both inbound and outbound.
- /outbound-call-status is the outbound completion callback that updates contact
  status in Supabase.
- Realtime tools are registered and handled by services/openai_service.py.

Visual style:
- Use grouped sections for Actors, FastAPI routes, Shared Realtime Core, Prompt
  Paths, Realtime Tools, Storage/Operations, Google Calendar, and Post-Call
  Artifacts.
- Use distinct colors for inbound flow, outbound flow, operator/system actions,
  realtime core, storage, calendar, and post-call processing.
- Keep labels readable. Avoid adding decorative icons that obscure the flow.
```
