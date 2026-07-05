# Aesthetic Clinic Appointment Setter MVP

This document freezes the first implementation target for converting the TVAAI
demo into a reusable outbound appointment-setter starter for aesthetic clinics.

The goal is not to make a one-off TVAAI prompt. The goal is to create a reusable
clinic appointment-setter base that can be duplicated for future med spa,
aesthetic clinic, wellness clinic, or similar appointment-driven clients.

## 1. MVP Objective

Build an outbound voice agent that calls warm Facebook leads, identifies the
offer they requested, gives a short offer-specific pitch, handles basic
questions and objections, books a real appointment when the lead is ready, and
logs the outcome.

TVAAI is the first configured client and reference implementation.

## 2. Primary Call Flow

1. Open the call as the clinic assistant and reference the Facebook offer.
2. Confirm the lead has time to talk.
3. Route the conversation from the lead's latest opt-in offer.
4. Pitch the matching offer briefly.
5. Answer basic non-medical questions using approved facts.
6. Move to scheduling as soon as the caller shows booking intent.
7. Ask one broad time-preference question if needed.
8. Check real calendar availability before offering times.
9. Offer no more than two real returned slots.
10. Get explicit consent for the deposit or schedule-protection flow.
11. Create the booking only after slot selection and deposit consent.
12. Confirm only after the booking tool succeeds.
13. Log the call outcome and end or transfer cleanly.

## 3. Reusable Product Behavior

These behaviors should become part of the appointment-setter starter:

- Outbound warm-lead calling.
- Lead-offer routing from a provided opt-in field.
- Multi-offer script support.
- Short phone-friendly sales pitch.
- Controlled objection handling.
- Medical and candidacy boundaries.
- Real availability lookup before slot offers.
- Booking confirmation only after tool success.
- Optional deposit or schedule-protection consent.
- Live human handoff.
- Call outcome logging.
- Do-not-contact handling.
- Wrong-person handling.
- Delivery, language, and accent controls from existing config.

## 4. TVAAI-Specific Configuration

These should not be hardcoded into the reusable starter long term:

- Clinic name: The Vitality and Aesthetics Institute.
- Assistant name: Sophia.
- Offer 1: Wrinkle Reset Membership.
- Offer 1 keywords: Botox, Neurotoxin, Dysport, Wrinkle Reset, wrinkles,
  forehead lines, frown lines, crow's feet.
- Offer 1 facts: $9/month, no contract, $9/unit Botox, $4/unit Dysport,
  founding-member savings, 50 founding spots.
- Offer 2: T-Shape 2 body contouring voucher.
- Offer 2 keywords: T-Shape, body contouring, sculpting, tightening, cellulite,
  stomach, thighs, love handles, voucher.
- Offer 2 facts: $199 voucher, normally $350, non-invasive, 30-45 minutes,
  no needles, no surgery, no downtime, 30 vouchers available.
- Deposit amount: $29.
- Hold window: 2 hours.
- Appointment duration: controlled by `BOOKING_SLOT_DURATION_MINUTES`.
- Current appointment/business timezone: Pacific Time / Los Angeles
  (`America/Los_Angeles`), based on the current Google Calendar setup.
- Caller timezone comes from lead `contact_timezone` when available. It is used
  for spoken display and call-record context only; it does not change booking
  authority.
- When caller timezone differs, speak caller-local time first and clinic time
  second, for example: "For you, 12 PM Eastern, which is 9 AM Pacific at the
  clinic."
- Location: 2603 Augusta Dr., Suite 1450, Houston TX 77057.
- Front desk phone: (832) 230-2418.
- Provider facts: physician-led by Dr. Shirley Lima and Dr. Phillip Singer,
  plus professional aesthetic injectors.

## 5. Placeholder Strategy

The demo prompt currently uses Retell/GHL-style placeholders such as
`{{contact_latest_optin}}`. The starter repo currently renders Python-style
single-brace placeholders such as `{agent_name}` and `{company_name}`.

The reusable appointment-setter starter should standardize these fields:

| Field | Purpose |
| --- | --- |
| `{contact_first_name}` | Caller first name if known. |
| `{contact_last_name}` | Caller last name if known. |
| `{contact_name}` | Full name fallback. |
| `{contact_phone}` | Primary phone number. |
| `{contact_email}` | Email if known. |
| `{lead_offer}` | Latest opt-in or offer requested by the lead. |
| `{contact_timezone}` | Contact/caller timezone for display; appointment booking remains anchored to the business timezone. |
| `{contact_id}` | Contact record identifier. |
| `{call_id}` | Call/session identifier. |
| `{callback_number}` | Front desk fallback number. |

Compatibility for `{{...}}` placeholders can be added later if direct
Retell/GHL script import becomes important. The first implementation should use
the starter's existing single-brace rendering path.

## 6. Lead Intake Strategy

The appointment-setter starter should support multiple ways to start outbound
test calls and production calls:

| Source | Purpose |
| --- | --- |
| Manual outbound form | Fastest MVP test path: enter one lead, offer, phone, and optional email, then click call/send. |
| CSV upload | Batch outbound testing and campaign-style lead import. |
| API endpoint | Long-term path for Facebook lead forms, GHL, Zapier, n8n, or another CRM to push leads into the outbound queue. |

The same normalized lead fields should be used regardless of source:

- contact name
- phone
- email if available
- latest opt-in / lead offer
- timezone
- source campaign
- optional custom fields

Manual form, CSV upload, and one-shot API intake now use the same normalized
lead fields and outbound prompt path.

The one-shot lead API is now the production integration path for GHL, n8n,
Zapier, Insomnia testing, or direct Facebook lead-form middleware:

```http
POST /outbound/campaigns/{campaign_id}/trigger-call
X-Dashboard-Key: <dashboard-password-or-api-key>
Content-Type: application/json
```

Example payload:

```json
{
  "name": "La kisha",
  "phone": "+12185953862",
  "email": "lead@example.com",
  "lead_offer": "Botox Wrinkle Reset",
  "contact_timezone": "America/Los_Angeles",
  "callback_number": "(832) 230-2418",
  "source": "GHL"
}
```

Accepted aliases include `contact_latest_optin`, `latest_optin`, `offer`,
`timezone`, `tz`, `clinic_phone`, `office_phone`, and nested
`contact`/`lead` objects. Extra scalar fields and explicit `custom_fields`,
`customFields`, or `extra` objects are stored on the outbound contact as
custom fields.

API execution flow:

1. Validate dashboard/API auth and outbound configuration.
2. Load the target campaign.
3. Normalize the posted lead payload into an outbound contact.
4. Insert that contact into the campaign with `pending` status.
5. Immediately dial the contact through Twilio.
6. Register the Twilio `call_sid` to the campaign/contact context.
7. When the call is answered, `/outbound-call-twiml/{campaign_id}` starts the
   media stream.
8. The websocket session renders the campaign prompt and appends
   `# Outbound Lead Context`, so the AI starts from the actual posted lead data.

For manual outbound form tests, use the first-class row fields:

- Lead Offer: `Botox Wrinkle Reset` or `T-Shape body contouring voucher`
- Timezone: `America/Los_Angeles`
- Callback: `(832) 230-2418`

Use the Extra JSON cell only for additional custom fields, for example:

```json
{"source":"FB Lead Form"}
```

For CSV upload, use normal columns for `name`, `phone`, and `email`. Any other
columns are imported into `custom_fields`. The lead offer can be supplied by any
of these column names:

- `lead_offer`
- `contact_latest_optin`
- `latest_optin`
- `latest opt-in`
- `Latest Opt-In`
- `offer`
- `facebook_offer`
- `fb_offer`
- `requested_offer`

## 7. Tool Mapping

The TVAAI demo names tools differently from this repo. The appointment-setter
prompt should use the repo's existing tools first.

| TVAAI demo concept | Starter repo tool |
| --- | --- |
| `get_slots_tool` | `get_availability` |
| `create_appointment_tool` | `book_appointment` |
| `update_contact_data_tool` | `save_call_record` and outbound contact status |
| `transfer_call` | `request_human_handoff` |
| `end_call` | `end_call` |
| silence / hold handling | `wait_for_user` |

Code aliases can be considered later, but the first conversion should keep the
tool surface simple and aligned with the starter. The current implementation
direction is to use the starter tool names in the prompt and not add Retell
alias tools unless testing shows that compatibility is needed.

## 8. Required Safety Rules

- Do not provide medical advice.
- Do not assess candidacy or safety for a specific caller.
- Transfer immediately for health, medication, pregnancy, side-effect, or
  candidacy questions.
- Never collect payment card details over the phone.
- Do not confirm a booking until the booking tool succeeds.
- Do not invent appointment availability.
- Honor do-not-contact requests without pushing back.
- If transfer or booking fails, provide a callback or follow-up path.

## 9. Outcome Tags

The reusable appointment setter should track these outcomes:

- `booked`
- `interested-callback`
- `declined`
- `do-not-contact`
- `wrong-person`
- `transfer-needed`
- `booking-error`

These are first-class `outcome_tag` values on `save_call_record` and
`request_human_handoff`. The storage adapter mirrors valid tags into Supabase
`lead_status` and keeps the same value in
`metadata.appointment_setter.outcome_tag`. The dashboard exposes the same tags
as status filters and editable status values.

## 10. Implementation Gates

Each gate should be implemented and tested before moving to the next one.

### Gate 1: MVP Report

Deliver this document and review it for scope accuracy.

Test/review:
- Confirm the reusable behavior matches the client demo.
- Confirm the TVAAI-specific facts are correct.
- Confirm the placeholder and tool-mapping direction is acceptable.

### Gate 2: Reusable Prompt File

Create an appointment-setter prompt that keeps the starter's required
config/render placeholders while replacing the generic business flow with the
aesthetic-clinic outbound flow.

Test/review:
- Render the prompt.
- Confirm no unresolved critical placeholders.
- Confirm the prompt still includes delivery style, language, accent, tools,
  booking, transfer, and call-record injected sections.

### Gate 3: Placeholder Rendering

Update outbound rendering so contact fields and custom fields can populate the
appointment-setter prompt consistently.

Test/review:
- Render one Botox lead.
- Render one T-Shape lead.
- Render one blank-offer lead.

### Gate 3A: Outbound Lead Entry

Make outbound testing practical from the dashboard or API.

Test/review:
- Manually enter one lead and trigger one outbound call.
- Upload a CSV with at least two leads and verify campaign contacts are created.
- POST one lead to `/outbound/campaigns/{campaign_id}/trigger-call` and verify
  one contact is created and called immediately.
- Confirm the lead offer field is passed into the rendered prompt.

### Gate 4: Tool-Aligned Booking Flow

Ensure the prompt uses `get_availability`, `book_appointment`,
`save_call_record`, and `request_human_handoff` correctly.

Test/review:
- Happy-path booking.
- No-slot fallback.
- Booking failure fallback.
- Deposit refusal transfer path.

Manual call tests:

1. Happy path: lead accepts the offer, asks to book, picks one offered slot,
   explicitly accepts the $29 secure-link deposit, and the agent calls
   `book_appointment`.
2. No-slot path: availability returns no useful slots, and the agent offers
   front-desk transfer instead of inventing times.
3. Booking failure path: booking tool fails or returns unclear status, and the
   agent does not say the appointment is booked.
4. Deposit refusal path: caller refuses the deposit after one explanation, and
   the agent transfers or saves a callback record.
5. Medical question path: caller asks whether treatment is safe for them, and
   the agent transfers without answering medically.

### Gate 5: Outcome Logging

Make sure booking, callback, decline, do-not-contact, wrong-person, transfer,
and booking-error outcomes are recorded in a useful way.

Implementation:
- `save_call_record.outcome_tag` accepts only the seven supported tags.
- `request_human_handoff.outcome_tag` accepts the same tags and defaults to
  `transfer-needed`.
- Underscore aliases such as `interested_callback` normalize to hyphenated
  storage tags such as `interested-callback`.
- Invalid tags are rejected before side effects.

Test/review:
- Confirm dashboard/storage payloads.
- Confirm call summaries include offer discussed and next step.

### Gate 6: Reusable Client Onboarding

Document how to duplicate this starter for another clinic and where to change
clinic name, offers, copy, booking rules, phone number, and transfer settings.

Test/review:
- Use a fake second clinic config and render its prompt without TVAAI leakage.

## 11. First Client: TVAAI Acceptance Checklist

- [ ] Botox/Wrinkle Reset lead routes directly to Wrinkle Reset.
- [ ] T-Shape lead routes directly to T-Shape 2.
- [ ] Blank or unclear lead is asked to choose between offers.
- [ ] Agent stops selling immediately once caller wants to book.
- [ ] Agent checks real availability before offering slots.
- [ ] Agent asks for deposit consent only after a slot is selected.
- [ ] Agent books only after explicit deposit consent.
- [ ] Agent transfers for medical questions.
- [ ] Agent transfers when caller asks for a human.
- [ ] Agent logs the outcome.
- [ ] Agent ends politely without open-ended unrelated help.
