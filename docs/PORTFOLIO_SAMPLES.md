# Portfolio Sample Workflow

Use this starter as the shared base for portfolio demos and client builds. Keep
the core app generic; create each sample by changing prompt, env, campaign
message, screenshots, and demo call recordings rather than forking tool logic.

## Base Capability Set

Every portfolio sample can reuse the same production features:

- Inbound receptionist calls through `/incoming-call`.
- Outbound campaigns and one-shot contact trigger calls.
- Google Calendar appointment booking when `BOOKING_ENABLED=true`.
- Supabase dashboard call records, notes, recordings, and transcripts.
- Optional human transfer and missed-call AI callback.

## Recommended Sample Set

| Sample | Prompt path | Outbound campaign type | Primary flow | Booking use |
| --- | --- | --- | --- | --- |
| Dentist clinic | `prompts/samples/dentist_clinic_receptionist.md` | `sample_dentist_clinic` | New patient intake, insurance/basic FAQ, cleaning/consult booking | Google Calendar appointment |
| Medical office | `prompts/samples/medical_office_receptionist.md` | `sample_medical_office` | Receptionist, callback triage, non-emergency appointment scheduling | Google Calendar appointment |
| Real estate | `prompts/samples/real_estate_showing_scheduler.md` | `sample_real_estate` | Buyer/seller intake, showing requests, open-house callback | Showing calendar |
| Home services | `prompts/samples/home_services_estimate_scheduler.md` | `sample_home_services` | Estimate request, service address capture, technician visit booking | Estimate/service calendar |
| E-commerce support | `prompts/samples/ecommerce_support_receptionist.md` | `sample_ecommerce_support` | Order issue intake, return/exchange routing, escalation | Usually no booking; save call record or handoff |
| B2B lead qualifier | `prompts/samples/b2b_lead_qualifier.md` | `sample_b2b_qualifier` | Budget/timeline/use-case qualification, sales meeting booking | Sales calendar |
| General receptionist | `prompts/samples/general_receptionist.md` | `sample_general_receptionist` | Answer simple questions, capture messages, transfer or callback | Optional appointment calendar |

Code source of truth for sample keys, prompt paths, campaign types, default demo
identity, and demo call ideas: `portfolio_samples.py`. Update that
registry first when adding or renaming a sample, then update the prompt file,
docs table, and demo contact assets.

Prompt quality checklist: [Sample prompt quality](./SAMPLE_PROMPT_QUALITY.md).

## Adding A New Sample

Print the checklist:

```bash
python scripts/portfolio_sample_setup.py --new-sample-checklist
```

Use this order when adding a vertical beyond the built-ins:

1. Choose `sample_key`, `campaign_type`, `prompt_path`, and `agent_label`.
2. Add one `PortfolioSample(...)` entry in `portfolio_samples.py`.
3. Create the prompt file under `prompts/samples/`.
4. Check it against `docs/SAMPLE_PROMPT_QUALITY.md`.
5. Add one row to the Recommended Sample Set table above.
6. Add one fake contact row to `docs/samples/portfolio_outbound_contacts.csv`.
7. Add one matching object to `docs/samples/trigger_call_payloads.json`.
8. Keep custom fields generic: `lead_offer`, `contact_timezone`, `callback_number`, and sample-specific context in notes/summary fields unless code needs structure.
9. Run the preview and test commands printed by the helper.

Do not add industry YAML/profile files. Keep the prompt, registry, docs, and
demo assets as the sample boundary.

## Build Steps Per Sample

1. Copy the starter into a sample/client repo or branch.
2. Set identity in `.env`: `COMPANY_NAME`, `AGENT_NAME`, `AGENT_LABEL`, voice, language, accent, and timezone.
3. Start from `prompts/main_system_instructions.md` for inbound receptionist behavior or `prompts/generic_appointment_setter.md` for outbound appointment setting.
4. Keep custom fields generic: contact name, phone, email, interest/offer, timezone, callback number, source, and sample-specific details inside `issue_summary` or `call_summary` unless code needs structured fields.
5. Enable only the features the sample demonstrates: Supabase dashboard, Google Calendar booking, recording/transcription, outbound campaigns, transfer, or missed-call callback.
6. Create 2-3 scripted demo calls: successful booking, follow-up/callback, and handoff or not-interested outcome.
7. Verify the dashboard record, recording, transcript, booking link, and campaign/contact status after each demo call.

For outbound portfolio demos, create a dashboard campaign and choose the sample
campaign type from the Type dropdown. The dashboard will prefill the matching
sample prompt as the editable campaign script.

## Setup Helper

Use the local helper to print a copyable env block, preview command, outbound
campaign type, demo contact instructions, and suggested demo calls for one
sample:

```bash
python scripts/portfolio_sample_setup.py --list-samples
python scripts/portfolio_sample_setup.py dentist
```

For a client-specific name while keeping the same sample structure:

```bash
python scripts/portfolio_sample_setup.py real-estate \
  --company-name "Pine Ridge Realty" \
  --agent-name "Mia" \
  --timezone America/Denver
```

The helper does not create secrets or edit `.env`; it prints the values to copy
after you choose a sample.

Before recording or publishing a demo, run the sample call through the
[portfolio demo acceptance checklist](./PORTFOLIO_DEMO_ACCEPTANCE.md).

## Demo Contact Assets

Use these fake contacts for portfolio testing:

| Asset | Use |
| --- | --- |
| `docs/samples/portfolio_outbound_contacts.csv` | Upload rows into a dashboard campaign. Select the matching `sample_*` campaign type first. |
| `docs/samples/trigger_call_payloads.json` | Copy one payload into Insomnia, n8n, Zapier, or another API client for `POST /outbound/campaigns/{campaign_id}/trigger-call`. |

Dashboard campaign test:

1. Open `/dashboard`.
2. Click Outbound.
3. Create a campaign.
4. Choose a sample Type, such as `Sample: Dentist Clinic`.
5. Upload `docs/samples/portfolio_outbound_contacts.csv`.
6. Keep only the matching row for that sample, or upload a smaller copy with just that row.
7. Save the campaign, then use Call on one contact or Start for the campaign.

One-shot API test:

```http
POST /outbound/campaigns/{campaign_id}/trigger-call
X-Dashboard-Key: <dashboard-password-or-api-key>
Content-Type: application/json
```

Use the object matching the campaign type from
`docs/samples/trigger_call_payloads.json`, for example `sample_real_estate`.

## Preview Commands

List the built-in sample shortcuts:

```bash
python scripts/preview_system_prompt.py --list-samples
```

Preview a sample with temporary identity values:

```bash
python scripts/preview_system_prompt.py \
  --sample dentist \
  --with-booking-tools \
  --with-call-records \
  --with-human-transfer \
  --company-name "Bright Smile Dental" \
  --agent-name "Ava"
```

The `--with-*` flags affect only local prompt preview. They do not configure
Google Calendar, Supabase, webhook delivery, or Twilio transfer for runtime.

Preview by explicit prompt path when testing a client-specific copy:

```bash
python scripts/preview_system_prompt.py \
  --prompt-path prompts/samples/real_estate_showing_scheduler.md \
  --company-name "Acme Realty" \
  --agent-name "Mia"
```

Run the prompt checks:

```bash
pytest tests/test_system_instructions.py tests/test_prompt_preview.py
```

## Env Starting Points

Each sample can start with the same feature flags, then change identity and
prompt path:

```env
SYSTEM_INSTRUCTIONS_PATH=prompts/samples/dentist_clinic_receptionist.md
COMPANY_NAME=Bright Smile Dental
AGENT_NAME=Ava
AGENT_LABEL=dentist_demo
TIMEZONE=America/Los_Angeles
BOOKING_ENABLED=true
CALL_RECORD_BACKEND=supabase
CALL_RECORDING_ENABLED=true
OUTBOUND_ENABLED=true
```

Suggested labels:

| Sample | `AGENT_LABEL` | Demo calls |
| --- | --- | --- |
| Dentist clinic | `dentist_demo` | new patient cleaning, tooth-pain callback, insurance follow-up |
| Medical office | `medical_office_demo` | routine visit booking, message for provider, urgent-symptom safety routing |
| Real estate | `real_estate_demo` | showing request, seller consultation, property question callback |
| Home services | `home_services_demo` | estimate booking, urgent issue capture, service-area callback |
| E-commerce support | `ecommerce_support_demo` | return request, damaged item, order-status escalation |
| B2B lead qualifier | `b2b_qualifier_demo` | discovery call booking, not-ready callback, technical handoff |
| General receptionist | `receptionist_demo` | appointment booking, message taking, live transfer |

## What Stays Generic

- Tool names and handlers in `services/openai_service.py`.
- Booking implementation in `services/google_calendar_booking_service.py`.
- Call-record facade in `services/call_records_service.py`.
- Supabase schemas in `docs/supabase-schema/`.
- Deployment, Twilio, and dashboard flow.

Add code only when a sample needs a real integration or structured field that
cannot be captured reliably in the existing call-record summary fields.
