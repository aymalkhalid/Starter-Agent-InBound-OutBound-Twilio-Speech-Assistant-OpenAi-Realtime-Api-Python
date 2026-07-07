# Sample Prompt Quality Checklist

Use this checklist when creating or reviewing prompts in `prompts/samples/`.
Portfolio samples can vary by industry, but they should keep the same runtime
contract so inbound, outbound, booking, call records, transfer, and demo review
work consistently.

## Required Sections

Each sample prompt should include:

- `# Role and Objective`
- An industry-specific boundary or safety section
- `# Conversation Flow`
- `# Booking`
- `# Call Records`
- `# Human Handoff`
- `# Voice and Language`
- `# Tools`

## Required Placeholders

Keep these placeholders in every sample prompt:

- `{agent_name}`
- `{company_name}`
- `{booking_instruction}`
- `{call_record_instruction}`
- `{transfer_instruction}`
- `{reasoning_effort_instruction}`
- `{delivery_instruction}`
- `{language_instruction}`
- `{accent_instruction}`
- `{tools_availability_instruction}`
- `{tools_text}`

## Shared Behavior Rules

- Ask one question at a time.
- Use only tools present in the current Realtime session.
- Confirm before tool calls that write, transfer, book, edit, delete, or save.
- Use availability before offering exact appointment times when booking tools are
  enabled.
- Confirm exact day, date, time, timezone, name, and callback number before
  booking.
- Do not say the appointment, meeting, callback slot, handoff, or saved record
  is complete until the related tool succeeds.
- Do not invent prices, policies, availability, clinical/legal/financial advice,
  order status, property details, or business promises.
- If the request is outside known context or requires a person, save a call
  record or request human handoff.

## Demo Review

After updating a sample prompt:

```bash
python scripts/preview_system_prompt.py --sample <sample-key> --with-booking-tools --with-call-records --with-human-transfer
python -m pytest tests/test_system_instructions.py tests/test_prompt_preview.py tests/test_outbound.py tests/test_generic_architecture.py
```

Before publishing the sample, run the actual call through
`docs/PORTFOLIO_DEMO_ACCEPTANCE.md`.
