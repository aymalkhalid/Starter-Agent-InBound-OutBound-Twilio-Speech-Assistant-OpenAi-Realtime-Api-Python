# Portfolio Demo Acceptance Checklist

Use this checklist before recording or publishing a portfolio sample. A demo is
ready only when the enabled features produce visible evidence in the app.

## Before The Call

- [ ] Run `python scripts/portfolio_sample_setup.py <sample>` and copy the env
  values for the sample.
- [ ] Run the printed `python scripts/preview_system_prompt.py ...` command.
- [ ] Confirm the rendered prompt uses the sample business name and agent name.
- [ ] Confirm no unresolved placeholders remain, such as `{company_name}` or
  `{agent_name}`.
- [ ] Confirm the expected tools appear in the prompt preview:
  `save_call_record` for call records, booking tools for booking samples, and
  `request_human_handoff` only when transfer is configured.

## Call Record Evidence

Required when `CALL_RECORD_BACKEND=supabase` or another call-record backend is
configured.

- [ ] A new row appears in `/dashboard` or `GET /calls`.
- [ ] The row has caller/contact name and phone when the caller provided them.
- [ ] `issue_summary` explains why the person called or why the agent called.
- [ ] `call_summary` describes the actual outcome.
- [ ] `lead_status` uses a useful outcome value, such as `booked`,
  `interested-callback`, `declined`, `do-not-contact`, `wrong-person`,
  `transfer-needed`, or `booking-error`.
- [ ] The modal shows one compact `Call SID` value, with related call attempts
  only when the same business record has multiple calls.

## Booking Evidence

Required when `BOOKING_ENABLED=true` and the sample demonstrates scheduling.

- [ ] The agent offers real slots from `get_availability`, not invented times.
- [ ] The agent calls `book_appointment` only after the caller confirms the slot
  and required contact details.
- [ ] The call record has `confirmed_slot` with a readable `display` value.
- [ ] The call record has `calendar_event_link` when Google Calendar returns one.
- [ ] Google Calendar contains the event at the same business appointment time.
- [ ] When caller timezone differs from business timezone, the agent says
  caller-local time first and business appointment time second.

## Recording And Transcript Evidence

Required when `CALL_RECORDING_ENABLED=true`.

- [ ] Twilio sends `/recording-status` with `RecordingStatus=completed`.
- [ ] The call record has `recording_link`.
- [ ] The dashboard modal can play or download the recording through
  `/recordings/{recording_sid}/media`.
- [ ] Generate transcript from the modal or call
  `POST /recordings/{recording_sid}/transcribe?record_id=<id>`.
- [ ] The call record has `transcript`.
- [ ] If transcript enhancement is enabled, `transcript_summary` and
  `transcript_issues` are filled after enhancement.

## Outbound Evidence

Required for campaign, dashboard single-call, one-shot API, or missed-call
callback demos.

- [ ] The campaign Type matches the selected sample, such as
  `sample_dentist_clinic` or `sample_real_estate`.
- [ ] The selected contact row starts as `pending`.
- [ ] When dialing begins, the contact row becomes `calling` and stores
  `call_sid`.
- [ ] After Twilio posts `/outbound-call-status`, terminal outcomes map to
  `completed` for `CallStatus=completed` or `failed` for `busy`, `no-answer`,
  `failed`, or `canceled`.
- [ ] The campaign progress counts match contact rows: pending, calling,
  completed, failed, and skipped.
- [ ] For one-shot API demos, the contact came from
  `POST /outbound/campaigns/{campaign_id}/trigger-call` and uses the matching
  object from `docs/samples/trigger_call_payloads.json`.

## Conversation Quality Gate

- [ ] The opening line fits the sample and does not mention the wrong industry.
- [ ] The agent asks one question at a time.
- [ ] The agent does not claim a booking, transfer, callback, or saved record
  until the tool succeeds.
- [ ] The agent handles refusal or wrong-person cases without pressure.
- [ ] The final goodbye matches the actual outcome.

## Portfolio Asset Gate

- [ ] Keep one successful booking or qualified-call recording for the sample.
- [ ] Keep one follow-up, handoff, or not-interested recording for contrast.
- [ ] Capture a dashboard screenshot showing the call record status, recording,
  transcript, and booking link when those features are enabled.
- [ ] Do not publish real caller phone numbers, emails, addresses, recording
  audio, or transcripts without permission.
