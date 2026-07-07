from pathlib import Path
import csv
import json
import os


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_uses_calls_api_and_valid_call_record_identifiers():
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    forbidden = [
        "loadCall Records",
        "buildCall Records",
        "newCall Records",
        "refetchCall Records",
        "startCall Records",
        "stopCall Records",
        "scheduleCall Records",
    ]
    assert not any(token in html for token in forbidden)
    assert '"/calls?"' in html
    assert '"/calls/events"' in html
    assert '"/leads?"' not in html
    assert '"/leads/events"' not in html
    assert "call_records_changed" in html


def test_call_record_facade_is_primary_route_surface():
    main_py = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '@app.get("/calls"' in main_py
    assert '@app.patch("/calls/{record_id}"' in main_py
    assert '@app.delete("/calls/{record_id}"' in main_py
    assert '@app.get("/leads"' not in main_py
    assert 'from services.call_records_service import' in main_py
    assert 'from services.lead_events import' not in main_py


def test_call_record_modal_uses_compact_call_sid_lifecycle_display():
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")

    assert "function callSidOverviewHtml(" in html
    assert '"<dt>Call SID</dt><dd>" + callSidOverviewHtml(callContext) + "</dd>"' in html
    assert "<dt>Latest Call SID</dt>" not in html
    assert "<dt>Primary Call SID</dt>" not in html
    assert "<dt>Related Call SIDs</dt>" not in html
    assert "related call attempts" in html


def test_env_example_starts_from_generic_portfolio_ready_configuration():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "COMPANY_NAME=Acme Voice Agent Demo" in env_example
    assert "AGENT_LABEL=generic_voice_agent" in env_example
    assert "SYSTEM_INSTRUCTIONS_PATH=prompts/main_system_instructions.md" in env_example
    assert "# SYSTEM_INSTRUCTIONS_PATH=prompts/samples/dentist_clinic_receptionist.md" in env_example
    assert "# SYSTEM_INSTRUCTIONS_PATH=prompts/samples/real_estate_showing_scheduler.md" in env_example
    assert "# SYSTEM_INSTRUCTIONS_PATH=prompts/samples/b2b_lead_qualifier.md" in env_example
    assert "# SYSTEM_INSTRUCTIONS_PATH=prompts/generic_appointment_setter.md" in env_example
    assert "BOOKING_ENABLED=false" in env_example
    assert "CALL_RECORDING_ENABLED=false" in env_example
    assert "OUTBOUND_ENABLED=false" in env_example
    assert "prompts/aesthetic_appointment_setter.md" not in env_example
    assert "aesthetic_appointment_setter" not in env_example


def test_generic_surfaces_do_not_leak_old_niche_wording():
    generic_files = [
        ".env.example",
        "README.md",
        "docs/COPYABLE_MERMAID.md",
        "docs/PROMPT_AS_CODE.md",
        "docs/CONFIGURATION.md",
        "docs/PORTFOLIO_SAMPLES.md",
        "docs/SAMPLE_PROMPT_QUALITY.md",
        "docs/PORTFOLIO_DEMO_ACCEPTANCE.md",
        "prompts/main_system_instructions.md",
        "prompts/generic_appointment_setter.md",
        "static/dashboard.html",
    ]
    forbidden_phrases = [
        "clinic time",
        "clinic timezone",
        "at the clinic",
        "lead intake",
        "lead data",
        "lead id",
        "calling leads",
        "Lead Offer",
    ]

    for relative_path in generic_files:
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        lowered = content.lower()
        for phrase in forbidden_phrases:
            assert phrase.lower() not in lowered, f"{relative_path} still contains {phrase!r}"


def test_portfolio_sample_doc_references_existing_prompt_files():
    os.environ.setdefault("PROMPT_PREVIEW_SKIP_DYNAMIC_SETTINGS", "true")
    from services.outbound_service import get_campaign_types
    from portfolio_samples import iter_samples

    doc = (ROOT / "docs" / "PORTFOLIO_SAMPLES.md").read_text(encoding="utf-8")
    assert "python scripts/portfolio_sample_setup.py --list-samples" in doc
    assert "python scripts/portfolio_sample_setup.py dentist" in doc
    assert "python scripts/portfolio_sample_setup.py --new-sample-checklist" in doc
    assert "## Adding A New Sample" in doc
    assert "./PORTFOLIO_DEMO_ACCEPTANCE.md" in doc
    assert "./SAMPLE_PROMPT_QUALITY.md" in doc
    assert "portfolio_samples.py" in doc
    assert "docs/samples/portfolio_outbound_contacts.csv" in doc
    assert "docs/samples/trigger_call_payloads.json" in doc
    assert "Do not add industry YAML/profile files." in doc
    campaign_types = get_campaign_types()
    for sample in iter_samples():
        assert sample.label in doc
        assert sample.campaign_type in doc
        assert sample.campaign_type in campaign_types
        assert sample.prompt_path in doc
        assert sample.primary_flow in doc
        assert sample.booking_use in doc
        assert (ROOT / sample.prompt_path).is_file()


def test_portfolio_demo_contact_assets_align_with_campaign_presets():
    os.environ.setdefault("PROMPT_PREVIEW_SKIP_DYNAMIC_SETTINGS", "true")
    from services.outbound_service import build_contact_from_payload, get_campaign_types
    from portfolio_samples import PORTFOLIO_SAMPLE_CAMPAIGN_TYPES

    campaign_types = get_campaign_types()
    expected_types = set(PORTFOLIO_SAMPLE_CAMPAIGN_TYPES)

    csv_path = ROOT / "docs" / "samples" / "portfolio_outbound_contacts.csv"
    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
    assert {row["sample_campaign_type"] for row in rows} == expected_types
    for row in rows:
        assert row["sample_campaign_type"] in campaign_types
        assert row["phone"].startswith("+1555555")
        assert row["email"].endswith("@example.com")
        contact = build_contact_from_payload(row)
        assert contact["name"]
        assert contact["phone"].startswith("+1555555")
        assert contact["custom_fields"]["lead_offer"]
        assert contact["custom_fields"]["contact_timezone"]

    payload_path = ROOT / "docs" / "samples" / "trigger_call_payloads.json"
    payloads = json.loads(payload_path.read_text(encoding="utf-8"))
    assert set(payloads) == expected_types
    for campaign_type, payload in payloads.items():
        assert campaign_type in campaign_types
        contact = build_contact_from_payload(payload)
        assert contact["name"]
        assert contact["phone"].startswith("+1555555")
        assert contact["email"].endswith("@example.com")
        assert contact["custom_fields"]["lead_offer"]
        assert contact["custom_fields"]["contact_timezone"]


def test_portfolio_demo_acceptance_doc_matches_runtime_surfaces():
    doc = (ROOT / "docs" / "PORTFOLIO_DEMO_ACCEPTANCE.md").read_text(encoding="utf-8")
    README = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    required_terms = [
        "GET /calls",
        "lead_status",
        "issue_summary",
        "call_summary",
        "confirmed_slot",
        "calendar_event_link",
        "/recording-status",
        "recording_link",
        "/recordings/{recording_sid}/media",
        "POST /recordings/{recording_sid}/transcribe?record_id=<id>",
        "transcript",
        "transcript_summary",
        "transcript_issues",
        "/outbound-call-status",
        "sample_dentist_clinic",
        "sample_real_estate",
        "POST /outbound/campaigns/{campaign_id}/trigger-call",
        "docs/samples/trigger_call_payloads.json",
    ]
    for term in required_terms:
        assert term in doc

    for status in ("pending", "calling", "completed", "failed", "skipped"):
        assert status in doc

    for outcome in (
        "booked",
        "interested-callback",
        "declined",
        "do-not-contact",
        "wrong-person",
        "transfer-needed",
        "booking-error",
    ):
        assert outcome in doc

    assert "PORTFOLIO_DEMO_ACCEPTANCE.md" in README
    assert "PORTFOLIO_DEMO_ACCEPTANCE.md" in docs_index
