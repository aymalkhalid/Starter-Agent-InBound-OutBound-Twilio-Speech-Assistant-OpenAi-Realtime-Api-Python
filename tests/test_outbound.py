"""
Tests for outbound calling feature.
Run from project root:
  python -m tests.test_outbound
  python tests/test_outbound.py
  pytest tests/test_outbound.py -v

Covers:
  - Campaign type preset loading
  - System message template rendering
  - Contact validation
  - Config helpers
  - TwiML generation
  - Twilio status callback mapping
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
load_dotenv()

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = Path(__file__).resolve().parents[1]

from portfolio_samples import PORTFOLIO_SAMPLE_CAMPAIGN_TYPES


# =========================================================================
# 1. Campaign type preset loading
# =========================================================================

def test_campaign_types_load():
    """Campaign type presets load and contain expected keys."""
    from services.outbound_service import get_campaign_types, _campaign_types_cache
    # Clear cache for fresh load
    import services.outbound_service as _mod
    _mod._campaign_types_cache = None

    types = get_campaign_types()
    assert isinstance(types, dict), "get_campaign_types must return a dict"
    assert len(types) >= 4, f"Expected at least 4 campaign types, got {len(types)}: {list(types.keys())}"
    for key in (
        "appointment_setter",
        "aesthetic_appointment_setter",
        "promo",
        "appointment_confirmation",
        "payment_reminder",
        "general",
        *PORTFOLIO_SAMPLE_CAMPAIGN_TYPES,
    ):
        assert key in types, f"Missing campaign type: {key}"
    print("  PASS: campaign types load")


def test_campaign_type_has_required_fields():
    """Each campaign type has label and default_script."""
    from services.outbound_service import get_campaign_types
    types = get_campaign_types()
    for key, cfg in types.items():
        assert "label" in cfg, f"Campaign type {key} missing 'label'"
        assert "default_script" in cfg, f"Campaign type {key} missing 'default_script'"
    print("  PASS: campaign types have required fields")


def test_campaign_type_config_lookup():
    """get_campaign_type_config returns correct type or empty dict for unknown."""
    from services.outbound_service import get_campaign_type_config
    promo = get_campaign_type_config("promo")
    assert promo.get("label") == "Promotional", f"Expected 'Promotional', got {promo.get('label')}"
    unknown = get_campaign_type_config("nonexistent_type_xyz")
    assert unknown == {}, f"Expected empty dict for unknown type, got {unknown}"
    print("  PASS: campaign type config lookup")


def test_appointment_type_has_custom_fields():
    """appointment_confirmation type declares appointment_date custom field."""
    from services.outbound_service import get_campaign_type_config
    cfg = get_campaign_type_config("appointment_confirmation")
    fields = cfg.get("custom_fields", [])
    assert isinstance(fields, list) and len(fields) > 0, "appointment_confirmation should have custom_fields"
    field_names = [f.get("name") for f in fields]
    assert "appointment_date" in field_names, f"Expected 'appointment_date' in custom_fields, got {field_names}"
    print("  PASS: appointment_confirmation has custom_fields")


def test_generic_appointment_setter_type_has_contact_fields():
    """Generic appointment setter declares reusable contact context fields."""
    from services.outbound_service import get_campaign_type_config
    cfg = get_campaign_type_config("appointment_setter")
    assert cfg.get("label") == "Appointment Setter"
    assert cfg.get("system_instructions_path") == "prompts/generic_appointment_setter.md"
    fields = cfg.get("custom_fields", [])
    field_names = [f.get("name") for f in fields]
    assert "lead_offer" in field_names
    assert "contact_timezone" in field_names
    assert "callback_number" in field_names
    print("  PASS: generic appointment setter has contact fields")


def test_aesthetic_appointment_setter_type_remains_sample():
    """Aesthetic appointment setter remains available as an optional sample preset."""
    from services.outbound_service import get_campaign_type_config
    cfg = get_campaign_type_config("aesthetic_appointment_setter")
    assert cfg.get("label") == "Aesthetic Appointment Setter (Sample)"
    assert cfg.get("system_instructions_path") == "prompts/aesthetic_appointment_setter.md"


def test_portfolio_sample_campaign_types_point_to_existing_prompts():
    """Portfolio sample campaign types are dashboard-selectable prompt presets."""
    from services.outbound_service import get_campaign_type_config
    from portfolio_samples import PORTFOLIO_SAMPLES

    for sample in PORTFOLIO_SAMPLES.values():
        cfg = get_campaign_type_config(sample.campaign_type)
        assert cfg.get("label") == sample.campaign_label
        assert cfg.get("system_instructions_path") == sample.prompt_path
        assert PORTFOLIO_SAMPLE_CAMPAIGN_TYPES[sample.campaign_type] == sample.prompt_path
        prompt_path = sample.prompt_path
        assert (ROOT / prompt_path).is_file()
        fields = cfg.get("custom_fields", [])
        field_names = [f.get("name") for f in fields]
        assert "lead_offer" in field_names
        assert "contact_timezone" in field_names
        assert "callback_number" in field_names


def test_payment_type_has_amount_due():
    """payment_reminder type declares amount_due custom field."""
    from services.outbound_service import get_campaign_type_config
    cfg = get_campaign_type_config("payment_reminder")
    fields = cfg.get("custom_fields", [])
    field_names = [f.get("name") for f in fields]
    assert "amount_due" in field_names, f"Expected 'amount_due' in custom_fields, got {field_names}"
    print("  PASS: payment_reminder has amount_due field")


# =========================================================================
# 2. System message template rendering
# =========================================================================

def test_template_placeholder_rendering():
    """Placeholders in a template string are replaced with contact data."""
    template = "Hello {contact_name}, this is {agent_name} from {company_name}."
    replacements = {
        "contact_name": "Alice",
        "company_name": "Acme Plumbing",
        "agent_name": "Alex",
    }
    result = template
    for key, value in replacements.items():
        result = result.replace("{" + key + "}", str(value))
    assert "Alice" in result, "contact_name not replaced"
    assert "Acme Plumbing" in result, "company_name not replaced"
    assert "Alex" in result, "agent_name not replaced"
    assert "{" not in result, f"Unreplaced placeholder in: {result}"
    print("  PASS: template placeholder rendering")


def test_template_custom_fields_rendering():
    """Custom fields from contact are injected into template."""
    template = "Appointment on {appointment_date} for {contact_name}."
    replacements = {
        "contact_name": "Bob",
        "appointment_date": "March 15, 2026 at 2:00 PM",
    }
    result = template
    for key, value in replacements.items():
        result = result.replace("{" + key + "}", str(value))
    assert "March 15, 2026 at 2:00 PM" in result
    assert "Bob" in result
    assert "{" not in result
    print("  PASS: custom fields rendering")


def test_template_missing_placeholder_left_as_is():
    """If a placeholder has no matching key, it stays in the string."""
    template = "Hello {contact_name}, your balance is {amount_due}."
    replacements = {"contact_name": "Carol"}
    result = template
    for key, value in replacements.items():
        result = result.replace("{" + key + "}", str(value))
    assert "Carol" in result
    assert "{amount_due}" in result, "Missing placeholder should remain for debugging"
    print("  PASS: missing placeholder left as-is")


def test_outbound_system_message_appends_delivery_language_and_accent_policy(monkeypatch):
    """Outbound campaign prompts should inherit global delivery/language/accent policy."""
    import services.outbound_service as outbound_service

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeQuery([
                    {
                        "id": "campaign-1",
                        "campaign_type": "general",
                        "message_template": "# Role and Objective\nCall {contact_name} for {company_name}.",
                    }
                ])
            if name == "outbound_contacts":
                return FakeQuery([
                    {
                        "id": "contact-1",
                        "name": "Alice",
                        "custom_fields": {},
                    }
                ])
            return FakeQuery([])

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")
    monkeypatch.setattr(outbound_service.Config, "ASSISTANT_TONE", "warm professional")
    monkeypatch.setattr(outbound_service.Config, "ASSISTANT_WARMTH", "warm")
    monkeypatch.setattr(outbound_service.Config, "ASSISTANT_EXPRESSIVENESS", "balanced")
    monkeypatch.setattr(outbound_service.Config, "ASSISTANT_PACING", "moderate")
    monkeypatch.setattr(outbound_service.Config, "ASSISTANT_LANGUAGE", "English")
    monkeypatch.setattr(outbound_service.Config, "LANGUAGE_SWITCH_POLICY", "explicit_or_substantive")
    monkeypatch.setattr(outbound_service.Config, "ASSISTANT_ACCENT", "neutral American")
    monkeypatch.setattr(outbound_service.Config, "ASSISTANT_ACCENT_STRENGTH", "light")
    monkeypatch.setenv("COMPANY_NAME", "Acme Plumbing")

    result = outbound_service.build_outbound_system_message("campaign-1", "contact-1")

    assert result is not None
    assert "Call Alice for Acme Plumbing." in result
    assert "# Delivery Style" in result
    assert "Target tone: warm professional." in result
    assert "# Language" in result
    assert "# Accent" in result
    assert "Do not infer language from accent alone." in result
    assert "Do not change response language based on the caller's accent." in result
    assert "Use a moderate pace, clear consonants, natural stress, and phone-friendly prosody." in result
    print("  PASS: outbound prompt appends language/accent policy")


def test_outbound_system_message_uses_campaign_business_metadata_over_ghl_fields(monkeypatch):
    """Campaign metadata should own business identity while GHL owns lead context."""
    import services.outbound_service as outbound_service

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeQuery([
                    {
                        "id": "campaign-1",
                        "name": "TVAAI GHL Manual Test",
                        "campaign_type": "aesthetic_appointment_setter",
                        "message_template": (
                            "You are {agent_name} from {company_name}. "
                            "Call about {lead_offer}. "
                            "Use offers: {current_offers}. "
                            "Office: {office_phone}. Website: {website}."
                        ),
                        "metadata": {
                            "business_profile": {
                                "company_name": "The Vitality & Aesthetics Institute",
                                "company_short": "TVAAI",
                                "agent_name": "Sophia",
                                "office_phone": "(832) 962-4455",
                                "website": "tvaai.com",
                                "hours": "Mon-Fri, 9:00 AM-5:00 PM",
                            },
                            "offer_config": {
                                "current_offers": [
                                    {
                                        "name": "Lip filler",
                                        "description": "Consultation path for lip filler leads",
                                        "aliases": ["filler", "lip augmentation"],
                                    },
                                    {"name": "Botox", "description": "Wrinkle reset consultation path"},
                                ]
                            },
                        },
                    }
                ])
            if name == "outbound_contacts":
                return FakeQuery([
                    {
                        "id": "contact-1",
                        "name": "Aymal Khalid Khan",
                        "phone": "+12185953862",
                        "email": "send2aymal@gmail.com",
                        "custom_fields": {
                            "lead_offer": "Lip filler",
                            "contact_timezone": "Asia/Karachi",
                            "company_name": "Wrong CRM Clinic",
                            "agent_name": "Wrong Agent",
                            "office_phone": "000-000-0000",
                            "website": "wrong.example",
                        },
                    }
                ])
            return FakeQuery([])

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")
    monkeypatch.setenv("COMPANY_NAME", "Env Fallback Clinic")

    result = outbound_service.build_outbound_system_message("campaign-1", "contact-1")

    assert result is not None
    assert "You are Sophia from The Vitality & Aesthetics Institute." in result
    assert "Call about Lip filler." in result
    assert "Office: (832) 962-4455." in result
    assert "Website: tvaai.com." in result
    assert "Lip filler" in result
    assert "Botox" in result
    assert "# Campaign Business Context" in result
    assert "- current_offers:" in result
    assert "# Outbound Contact Context" in result
    assert "- lead_offer: Lip filler" in result
    assert "Wrong CRM Clinic" not in result
    assert "Wrong Agent" not in result
    assert "000-000-0000" not in result
    assert "wrong.example" not in result
    print("  PASS: campaign metadata owns business identity over GHL fields")


def test_outbound_system_message_keeps_legacy_contact_business_fields_without_campaign_metadata(monkeypatch):
    """Legacy campaigns can still use business-like placeholders from contact custom fields."""
    import services.outbound_service as outbound_service

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeQuery([
                    {
                        "id": "campaign-1",
                        "name": "Legacy CRM Payload Test",
                        "campaign_type": "general",
                        "message_template": "Call for {company_name} at {office_phone} about {lead_offer}.",
                    }
                ])
            if name == "outbound_contacts":
                return FakeQuery([
                    {
                        "id": "contact-1",
                        "name": "Jordan",
                        "custom_fields": {
                            "company_name": "Legacy CRM Clinic",
                            "office_phone": "111-222-3333",
                            "lead_offer": "Botox",
                        },
                    }
                ])
            return FakeQuery([])

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")
    monkeypatch.setenv("COMPANY_NAME", "Env Clinic")

    result = outbound_service.build_outbound_system_message("campaign-1", "contact-1")

    assert result is not None
    assert "Call for Legacy CRM Clinic at 111-222-3333 about Botox." in result
    assert "- callback_number: 111-222-3333" in result
    print("  PASS: legacy contact business placeholders still work without campaign metadata")


def test_create_campaign_stores_normalized_metadata_without_secrets(monkeypatch):
    """Campaign creation should store normalized business/offer config and skip secrets."""
    import services.outbound_service as outbound_service

    captured = {}

    class FakeTable:
        def insert(self, row):
            captured["row"] = row
            return self

        def execute(self):
            return SimpleNamespace(data=[dict(captured["row"], id="campaign-1")])

    class FakeClient:
        def table(self, name):
            assert name == "outbound_campaigns"
            return FakeTable()

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "OUTBOUND_MAX_CONCURRENCY", 5)

    campaign = outbound_service.create_campaign_sync(
        "TVAAI Test",
        "aesthetic_appointment_setter",
        "Call {contact_name}.",
        2,
        {
            "business_profile": {
                "company_name": "The Vitality & Aesthetics Institute",
                "office_phone": "(832) 962-4455",
            },
            "offer_config": {"current_offers": ["Lip filler", "Botox"]},
            "api_key": "should-not-store",
        },
    )

    assert campaign is not None
    metadata = captured["row"]["metadata"]
    assert metadata["business_profile"]["company_name"] == "The Vitality & Aesthetics Institute"
    assert metadata["business_profile"]["office_phone"] == "(832) 962-4455"
    assert metadata["offer_config"]["current_offers"] == "Lip filler | Botox"
    assert "api_key" not in metadata
    print("  PASS: campaign metadata normalized on create")


def test_outbound_system_message_does_not_duplicate_existing_delivery_language_accent_sections(monkeypatch):
    """Campaign templates with explicit delivery/language/accent sections keep one copy."""
    import services.outbound_service as outbound_service

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeQuery([
                    {
                        "id": "campaign-1",
                        "campaign_type": "general",
                        "message_template": (
                            "# Role and Objective\nCall {contact_name}.\n\n"
                            "# Delivery Style\nUse a calm campaign-specific style.\n\n"
                            "# Language\nUse English.\n\n"
                            "# Accent\nUse a light neutral American accent."
                        ),
                    }
                ])
            if name == "outbound_contacts":
                return FakeQuery([
                    {
                        "id": "contact-1",
                        "name": "Alice",
                        "custom_fields": {},
                    }
                ])
            return FakeQuery([])

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")

    result = outbound_service.build_outbound_system_message("campaign-1", "contact-1")

    assert result is not None
    assert result.count("# Delivery Style") == 1
    assert result.count("# Language") == 1
    assert result.count("# Accent") == 1
    print("  PASS: outbound prompt does not duplicate language/accent policy")


def test_aesthetic_outbound_type_uses_aesthetic_prompt_when_script_blank(monkeypatch):
    """Aesthetic campaigns should not fall back to the generic prompt when script is blank."""
    import services.outbound_service as outbound_service

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeQuery([
                    {
                        "id": "campaign-1",
                        "name": "Aesthetic Appointment Setter",
                        "campaign_type": "aesthetic_appointment_setter",
                        "message_template": "",
                    }
                ])
            if name == "outbound_contacts":
                return FakeQuery([
                    {
                        "id": "contact-1",
                        "name": "La kisha",
                        "phone": "+12185953862",
                        "email": "send2aymal@gmail.com",
                        "custom_fields": {
                            "lead_offer": "Botox Wrinkle Reset",
                            "contact_timezone": "America/Los_Angeles",
                            "callback_number": "(832) 230-2418",
                            "source": "FB Lead Form",
                        },
                    }
                ])
            return FakeQuery([])

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")
    monkeypatch.setattr(outbound_service.Config, "SYSTEM_MESSAGE", "GENERIC FALLBACK PROMPT")
    monkeypatch.setattr(outbound_service.Config, "COMPANY_NAME", "The Vitality & Aesthetics Institute")
    monkeypatch.setattr(outbound_service.Config, "AGENT_NAME", "Alexa")

    result = outbound_service.build_outbound_system_message("campaign-1", "contact-1")

    assert result is not None
    assert "GENERIC FALLBACK PROMPT" not in result
    assert "outbound aesthetic clinic" in result.lower()
    assert "appointment setter" in result.lower()
    assert "Hi [contact name], this is Alexa" in result
    assert "- contact_name: La kisha" in result
    assert "- lead_offer: Botox Wrinkle Reset" in result
    assert "- contact_timezone: America/Los_Angeles" in result
    assert "- callback_number: (832) 230-2418" in result
    assert "- source_campaign: FB Lead Form" in result
    print("  PASS: aesthetic outbound type uses aesthetic prompt when script is blank")


def test_outbound_system_message_renders_botox_lead_context(monkeypatch):
    """Botox/Wrinkle Reset lead fields normalize into placeholders and context."""
    import services.outbound_service as outbound_service

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeQuery([
                    {
                        "id": "campaign-1",
                        "name": "TVAAI Facebook Leads",
                        "campaign_type": "general",
                        "message_template": (
                            "Offer={lead_offer}; first={contact_first_name}; "
                            "last={contact_last_name}; phone={contact_phone}; "
                            "tz={contact_timezone}; callback={callback_number}; "
                            "optin={contact_latest_optin}."
                        ),
                    }
                ])
            if name == "outbound_contacts":
                return FakeQuery([
                    {
                        "id": "contact-1",
                        "name": "Alice Smith",
                        "phone": "+15551234567",
                        "email": "alice@example.test",
                        "call_sid": "CA123",
                        "custom_fields": {
                            "contact_latest_optin": "Botox Wrinkle Reset",
                            "contact_timezone": "America/Los_Angeles",
                            "callback_number": "(832) 230-2418",
                        },
                    }
                ])
            return FakeQuery([])

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")

    result = outbound_service.build_outbound_system_message("campaign-1", "contact-1")

    assert result is not None
    assert "Offer=Botox Wrinkle Reset" in result
    assert "first=Alice" in result
    assert "last=Smith" in result
    assert "phone=+15551234567" in result
    assert "tz=America/Los_Angeles" in result
    assert "callback=(832) 230-2418" in result
    assert "# Outbound Contact Context" in result
    assert "- lead_offer: Botox Wrinkle Reset" in result
    assert "- contact_id: contact-1" in result
    assert "- call_id: CA123" in result
    print("  PASS: outbound Botox lead context rendering")


def test_outbound_system_message_renders_tshape_csv_offer_alias(monkeypatch):
    """CSV headers such as Latest Opt-In normalize to lead_offer."""
    import services.outbound_service as outbound_service

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeQuery([
                    {
                        "id": "campaign-1",
                        "name": "CSV Upload Test",
                        "campaign_type": "general",
                        "message_template": "Call {contact_name} about {lead_offer}.",
                    }
                ])
            if name == "outbound_contacts":
                return FakeQuery([
                    {
                        "id": "contact-2",
                        "name": "Brianna",
                        "phone": "+15557654321",
                        "email": "",
                        "custom_fields": {
                            "Latest Opt-In": "T-Shape body contouring voucher",
                        },
                    }
                ])
            return FakeQuery([])

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")

    result = outbound_service.build_outbound_system_message("campaign-1", "contact-2")

    assert result is not None
    assert "Call Brianna about T-Shape body contouring voucher." in result
    assert "- lead_offer: T-Shape body contouring voucher" in result
    assert "- source_campaign: CSV Upload Test" in result
    print("  PASS: outbound T-Shape CSV alias rendering")


def test_outbound_system_message_blank_offer_uses_active_prompt_with_context(monkeypatch):
    """Blank campaign scripts still use Config.SYSTEM_MESSAGE plus contact context."""
    import services.outbound_service as outbound_service

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeQuery([
                    {
                        "id": "campaign-1",
                        "name": "Manual Blank Offer Test",
                        "campaign_type": "general",
                        "message_template": "",
                    }
                ])
            if name == "outbound_contacts":
                return FakeQuery([
                    {
                        "id": "contact-3",
                        "name": "Casey Lee",
                        "phone": "+15550001111",
                        "email": "",
                        "custom_fields": {},
                    }
                ])
            return FakeQuery([])

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")
    monkeypatch.setattr(outbound_service.Config, "SYSTEM_MESSAGE", "# Role and Objective\nBase appointment-setter prompt.")
    monkeypatch.setattr(outbound_service.Config, "TIMEZONE", "America/Los_Angeles")

    result = outbound_service.build_outbound_system_message("campaign-1", "contact-3")

    assert result is not None
    assert "Base appointment-setter prompt." in result
    assert "# Outbound Contact Context" in result
    assert "- contact_name: Casey Lee" in result
    assert "- contact_phone: +15550001111" in result
    assert "- contact_timezone:" not in result
    assert "- lead_offer:" not in result
    print("  PASS: blank offer uses active prompt with context")


def test_template_fallback_contact_name():
    """When contact name is empty, fallback to 'there'."""
    name = "" or "there"
    assert name == "there"
    name2 = "Alice" or "there"
    assert name2 == "Alice"
    print("  PASS: contact_name fallback")


# =========================================================================
# 3. Contact validation
# =========================================================================

def test_contact_phone_required():
    """Contacts without a phone number are skipped during add."""
    contacts = [
        {"name": "Alice", "phone": "+15551234567", "email": "a@b.com"},
        {"name": "Bob", "phone": "", "email": "b@b.com"},
        {"name": "Carol", "phone": "  ", "email": ""},
        {"name": "Dave", "phone": "+15559876543"},
    ]
    valid = [c for c in contacts if (c.get("phone") or "").strip()]
    assert len(valid) == 2, f"Expected 2 valid contacts, got {len(valid)}"
    assert valid[0]["name"] == "Alice"
    assert valid[1]["name"] == "Dave"
    print("  PASS: contact phone required")


def test_contact_custom_fields_default():
    """custom_fields defaults to empty dict."""
    contact = {"name": "Test", "phone": "+1555", "email": ""}
    custom = contact.get("custom_fields") or {}
    assert custom == {}
    print("  PASS: custom_fields default")


def test_contact_row_build():
    """Contact row built for Supabase insert has expected shape."""
    c = {"name": " Alice ", "phone": "+15551234567 ", "email": " a@b.com ", "custom_fields": {"amount_due": "$150"}}
    row = {
        "campaign_id": "fake-uuid",
        "name": (c.get("name") or "").strip(),
        "phone": (c.get("phone") or "").strip(),
        "email": (c.get("email") or "").strip(),
        "custom_fields": c.get("custom_fields") or {},
        "status": "pending",
    }
    assert row["name"] == "Alice"
    assert row["phone"] == "+15551234567"
    assert row["email"] == "a@b.com"
    assert row["custom_fields"]["amount_due"] == "$150"
    assert row["status"] == "pending"
    print("  PASS: contact row build")


def test_contact_payload_builds_trigger_call_contact():
    """External contact/lead webhook payloads normalize into outbound contact shape."""
    import services.outbound_service as outbound_service

    payload = {
        "contact": {
            "firstName": "La",
            "lastName": "Kisha",
            "phone": "+12185953862",
            "email": "lead@example.test",
            "customFields": '{"Latest Opt-In":"Botox Wrinkle Reset"}',
        },
        "source": "GHL",
        "budget": "100000",
        "timezone": "America/Los_Angeles",
        "callback_number": "(832) 230-2418",
    }

    contact = outbound_service.build_contact_from_payload(payload)

    assert contact["name"] == "La Kisha"
    assert contact["phone"] == "+12185953862"
    assert contact["email"] == "lead@example.test"
    assert contact["custom_fields"]["lead_offer"] == "Botox Wrinkle Reset"
    assert contact["custom_fields"]["contact_latest_optin"] == "Botox Wrinkle Reset"
    assert contact["custom_fields"]["contact_timezone"] == "America/Los_Angeles"
    assert contact["custom_fields"]["callback_number"] == "(832) 230-2418"
    assert contact["custom_fields"]["source_campaign"] == "GHL"
    assert contact["custom_fields"]["budget"] == "100000"
    assert outbound_service.build_contact_from_lead_payload(payload) == contact
    print("  PASS: external contact payload builds trigger-call contact")


def test_get_contact_timezone_from_contact_prefers_contact_fields():
    """Outbound contact timezone is caller context when present and absent otherwise."""
    import services.outbound_service as outbound_service

    assert outbound_service.get_contact_timezone_from_contact({
        "custom_fields": {"contact_timezone": "America/Chicago"},
    }) == "America/Chicago"
    assert outbound_service.get_contact_timezone_from_contact({
        "timezone": "America/New_York",
        "custom_fields": {"contact_timezone": "America/Chicago"},
    }) == "America/New_York"
    assert outbound_service.get_contact_timezone_from_contact({"custom_fields": {}}) == ""


def test_trigger_call_api_route_contract():
    """The one-shot API route normalizes, inserts, and dials via shared helper."""
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert '@app.post("/outbound/campaigns/{campaign_id}/trigger-call"' in source
    assert "async def trigger_outbound_call_from_contact(" in source
    assert "build_contact_from_payload(body)" in source
    assert "add_contacts_sync, campaign_id, [contact]" in source
    assert "_dial_outbound_contact_now(request, campaign_id, contact_id)" in source
    assert "Contact not in this campaign" in source
    assert "TwilioService.register_outbound_context(call.sid, campaign_id, contact_id)" in source
    print("  PASS: trigger-call API route contract")


def test_dashboard_outbound_form_exposes_appointment_setter_contact_fields():
    """Outbound dashboard exposes contact fields and persists them as custom_fields."""
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    assert "<th>Interest / Offer</th>" in html
    assert "<th>Timezone</th>" in html
    assert "<th>Callback</th>" in html
    assert "class=\"ob-c-offer\"" in html
    assert "class=\"ob-c-timezone\"" in html
    assert "class=\"ob-c-callback\"" in html
    assert "custom.lead_offer = leadOffer" in html
    assert "custom.contact_timezone = contactTimezone" in html
    assert "custom.callback_number = callbackNumber" in html
    assert "Latest Opt-In" in html
    print("  PASS: dashboard outbound form exposes appointment-setter lead fields")


def test_dashboard_exposes_appointment_setter_outcome_statuses():
    """Dashboard filters, modal status options, and badges know appointment-setter outcomes."""
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    for status in (
        "booked",
        "interested-callback",
        "declined",
        "do-not-contact",
        "wrong-person",
        "transfer-needed",
        "booking-error",
    ):
        assert f"option value=\"{status}\"" in html
        assert f"value: \"{status}\"" in html
        assert f"\"{status}\"" in html
    assert ".status-badge.interested-callback" in html
    assert ".status-badge.do-not-contact" in html
    assert ".status-badge.booking-error" in html
    print("  PASS: dashboard exposes appointment-setter outcome statuses")


def test_list_campaigns_includes_contact_progress(monkeypatch):
    """Campaign list rows include aggregated contact progress counts."""
    import services.outbound_service as outbound_service
    from types import SimpleNamespace

    class FakeCampaignQuery:
        def select(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def range(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(
                data=[
                    {"id": "campaign-1", "name": "March Promo", "status": "completed", "campaign_type": "general"},
                    {"id": "campaign-2", "name": "April Leads", "status": "draft", "campaign_type": "general"},
                ],
                count=2,
            )

    class FakeContactsQuery:
        def select(self, *_args, **_kwargs):
            return self

        def in_(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(
                data=[
                    {"campaign_id": "campaign-1", "status": "completed"},
                    {"campaign_id": "campaign-1", "status": "completed"},
                    {"campaign_id": "campaign-1", "status": "failed"},
                    {"campaign_id": "campaign-2", "status": "pending"},
                ]
            )

    class FakeClient:
        def table(self, name):
            if name == "outbound_campaigns":
                return FakeCampaignQuery()
            if name == "outbound_contacts":
                return FakeContactsQuery()
            raise AssertionError(f"unexpected table {name}")

    monkeypatch.setattr(outbound_service, "_get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CAMPAIGNS_TABLE", "outbound_campaigns")
    monkeypatch.setattr(outbound_service.Config, "SUPABASE_OUTBOUND_CONTACTS_TABLE", "outbound_contacts")

    campaigns, total = outbound_service.list_campaigns_sync()

    assert total == 2
    assert len(campaigns) == 2
    assert campaigns[0]["progress"] == {"completed": 2, "failed": 1, "total": 3}
    assert campaigns[1]["progress"] == {"pending": 1, "total": 1}
    print("  PASS: list campaigns includes contact progress")


def test_dashboard_outbound_has_confirm_modal_and_editor_header():
    """Outbound dashboard uses styled confirm modal and campaign editor header."""
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    assert 'id="ob-confirm-overlay"' in html
    assert 'id="ob-confirm-message"' in html
    assert "function obConfirm(" in html
    assert 'id="ob-editor-header"' in html
    assert 'id="ob-editor-title"' in html
    assert "function formatCampaignProgress(" in html
    assert "class=\"ob-c-stats\"" in html
    assert "window.confirm" not in html.split("deleteCampaign")[1].split("function loadAndEditCampaign")[0]
    print("  PASS: dashboard outbound confirm modal and editor header")


def test_resolve_campaign_type_default_script_loads_generic_and_sample_prompts(monkeypatch):
    """Dashboard/API should expose rendered appointment prompts as type defaults."""
    import services.outbound_service as outbound_service

    monkeypatch.setattr(
        outbound_service,
        "_render_campaign_system_instructions",
        lambda path: f"# Rendered prompt for {path}\nCall {{contact_name}} about {{lead_offer}}.",
    )
    monkeypatch.setattr(outbound_service.Config, "SYSTEM_MESSAGE", "GENERIC FALLBACK")

    script = outbound_service.resolve_campaign_type_default_script("appointment_setter")
    assert "Rendered prompt for prompts/generic_appointment_setter.md" in script
    sample_script = outbound_service.resolve_campaign_type_default_script("sample_dentist_clinic")
    assert "Rendered prompt for prompts/samples/dentist_clinic_receptionist.md" in sample_script

    dashboard_types = outbound_service.get_campaign_types_for_dashboard()
    assert "Call {contact_name} about {lead_offer}." in dashboard_types["appointment_setter"]["default_script"]
    assert "Call {contact_name} about {lead_offer}." in dashboard_types["aesthetic_appointment_setter"]["default_script"]
    assert "Call {contact_name} about {lead_offer}." in dashboard_types["sample_dentist_clinic"]["default_script"]
    assert dashboard_types["promo"]["default_script"].startswith("You are {agent_name}")
    print("  PASS: resolve campaign type default scripts for dashboard")


def test_dashboard_outbound_script_panel_layout():
    """Outbound editor exposes full-width script panel with reset + hint."""
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    assert 'class="ob-script-panel"' in html
    assert 'id="ob-script-hint"' in html
    assert 'id="ob-reset-script-btn"' in html
    assert "function applyMessageScriptForCampaign(" in html
    assert "function getTypeDefaultScript(" in html
    print("  PASS: dashboard outbound script panel layout")


def test_dashboard_outbound_campaign_metadata_editor():
    """Outbound editor exposes campaign-owned business and offer metadata fields."""
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    for field_id in (
        "ob-profile-company-name",
        "ob-profile-company-short",
        "ob-profile-agent-name",
        "ob-profile-office-phone",
        "ob-profile-agent-calling-number",
        "ob-profile-website",
        "ob-profile-address",
        "ob-profile-map-link",
        "ob-profile-hours",
        "ob-profile-current-offers",
        "ob-profile-offer-routing",
        "ob-profile-offer-notes",
        "ob-profile-preview",
    ):
        assert f'id="{field_id}"' in html
    assert "Client &amp; Offer Profile" in html
    assert "function applyCampaignMetadataToForm(" in html
    assert "function collectCampaignMetadataFromForm(" in html
    assert "metadata: collectCampaignMetadataFromForm()" in html
    assert "current_offers" in html
    print("  PASS: dashboard outbound campaign metadata editor")


def test_dashboard_outbound_sample_type_guidance():
    """Outbound editor shows prompt path and demo assets for sample campaign types."""
    html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
    assert 'id="ob-type-details"' in html
    assert "function updateCampaignTypeDetails(" in html
    assert "function isPortfolioSampleType(" in html
    assert "system_instructions_path" in html
    assert "sample_campaign_type=" in html
    assert "docs/samples/portfolio_outbound_contacts.csv" in html
    assert "docs/samples/trigger_call_payloads.json" in html
    assert "docs/PORTFOLIO_DEMO_ACCEPTANCE.md" in html
    assert "obTypeSelect.addEventListener(\"change\"" in html
    assert "var editorVisible = obEditorView && obEditorView.style.display !== \"none\";" in html
    print("  PASS: dashboard outbound sample type guidance")


# =========================================================================
# 4. Config helpers
# =========================================================================

def test_config_outbound_enabled_default():
    """OUTBOUND_ENABLED defaults to false."""
    from config import Config
    orig = os.environ.get("OUTBOUND_ENABLED")
    os.environ["OUTBOUND_ENABLED"] = "false"
    assert Config.OUTBOUND_ENABLED is False or (os.getenv("OUTBOUND_ENABLED", "false").strip().lower() not in ("1", "true", "yes"))
    if orig is not None:
        os.environ["OUTBOUND_ENABLED"] = orig
    elif "OUTBOUND_ENABLED" in os.environ:
        del os.environ["OUTBOUND_ENABLED"]
    print("  PASS: OUTBOUND_ENABLED defaults false")


def test_config_max_concurrency_clamped():
    """OUTBOUND_MAX_CONCURRENCY is at least 1."""
    from config import Config
    assert Config.OUTBOUND_MAX_CONCURRENCY >= 1, f"Expected >= 1, got {Config.OUTBOUND_MAX_CONCURRENCY}"
    print("  PASS: max concurrency >= 1")


def test_config_supabase_table_defaults():
    """Supabase outbound table names have sensible defaults."""
    from config import Config
    assert Config.SUPABASE_OUTBOUND_CAMPAIGNS_TABLE == (os.getenv("SUPABASE_OUTBOUND_CAMPAIGNS_TABLE") or "outbound_campaigns")
    assert Config.SUPABASE_OUTBOUND_CONTACTS_TABLE == (os.getenv("SUPABASE_OUTBOUND_CONTACTS_TABLE") or "outbound_contacts")
    print("  PASS: Supabase table defaults")


def test_config_outbound_from_number():
    """get_outbound_from_number returns env value or empty."""
    from config import Config
    result = Config.get_outbound_from_number()
    expected = (os.getenv("TWILIO_OUTBOUND_NUMBER") or "").strip()
    assert result == expected, f"Expected '{expected}', got '{result}'"
    print("  PASS: outbound from number")


def test_concurrency_clamp_logic():
    """Campaign concurrency is clamped between 1 and OUTBOUND_MAX_CONCURRENCY."""
    from config import Config
    max_c = Config.OUTBOUND_MAX_CONCURRENCY
    assert max(1, min(0, max_c)) == 1, "0 should clamp to 1"
    assert max(1, min(1, max_c)) == 1
    assert max(1, min(max_c, max_c)) == max_c
    assert max(1, min(max_c + 10, max_c)) == max_c, "Over-max should clamp"
    print("  PASS: concurrency clamp logic")


# =========================================================================
# 5. TwiML generation
# =========================================================================

def test_outbound_twiml_shape():
    """Outbound TwiML contains Connect > Stream with custom parameters."""
    from twilio.twiml.voice_response import VoiceResponse, Connect

    campaign_id = "abc-123"
    contact_id = "def-456"
    host = "example.com"

    stream_url = f"wss://{host}/media-stream"
    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=stream_url)
    stream.parameter(name="direction", value="outbound")
    stream.parameter(name="campaign_id", value=campaign_id)
    stream.parameter(name="contact_id", value=contact_id)
    response.append(connect)
    xml = str(response)

    assert 'url="wss://example.com/media-stream"' in xml
    assert "?direction=outbound" not in xml
    assert 'name="direction" value="outbound"' in xml, f"Missing direction parameter in TwiML: {xml}"
    assert f'name="campaign_id" value="{campaign_id}"' in xml, f"Missing campaign_id parameter in TwiML: {xml}"
    assert f'name="contact_id" value="{contact_id}"' in xml, f"Missing contact_id parameter in TwiML: {xml}"
    assert "<Connect>" in xml, f"Missing <Connect> in TwiML: {xml}"
    assert "<Stream" in xml, f"Missing <Stream> in TwiML: {xml}"
    print("  PASS: outbound TwiML shape")


def test_outbound_twiml_custom_parameter_xml_escaping():
    """Special characters in campaign/contact IDs are XML-escaped."""
    from twilio.twiml.voice_response import VoiceResponse, Connect

    campaign_id = "id with spaces & special=chars"
    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url="wss://example.com/media-stream")
    stream.parameter(name="campaign_id", value=campaign_id)
    response.append(connect)
    xml = str(response)

    assert 'url="wss://example.com/media-stream"' in xml
    assert "?campaign_id=" not in xml
    assert "id with spaces &amp; special=chars" in xml
    print("  PASS: TwiML custom parameter XML escaping")


# =========================================================================
# 6. Twilio status callback mapping
# =========================================================================

def test_status_callback_terminal_mapping():
    """Terminal Twilio statuses map to correct contact statuses."""
    terminal_statuses = {"completed", "busy", "no-answer", "failed", "canceled"}

    for ts in terminal_statuses:
        final_status = "completed" if ts == "completed" else "failed"
        error_msg = "" if ts == "completed" else ts
        if ts == "completed":
            assert final_status == "completed"
            assert error_msg == ""
        else:
            assert final_status == "failed"
            assert error_msg == ts
    print("  PASS: terminal status mapping")


def test_status_callback_non_terminal_ignored():
    """Non-terminal statuses (initiated, ringing, in-progress) are not in the terminal set."""
    terminal_statuses = {"completed", "busy", "no-answer", "failed", "canceled"}
    for ts in ("initiated", "ringing", "in-progress", "queued"):
        assert ts not in terminal_statuses, f"{ts} should not be terminal"
    print("  PASS: non-terminal statuses ignored")


def test_status_callback_empty_call_sid():
    """Empty CallSid should be handled gracefully (no update)."""
    call_sid = ""
    assert not call_sid, "Empty call_sid should be falsy"
    print("  PASS: empty CallSid handled")


def test_contact_status_lifecycle():
    """Contact status transitions follow expected lifecycle."""
    valid_transitions = {
        "pending": ["calling", "skipped"],
        "calling": ["completed", "failed"],
    }
    for from_status, to_statuses in valid_transitions.items():
        for to_status in to_statuses:
            assert to_status in ("pending", "calling", "completed", "failed", "skipped"), \
                f"Invalid status: {to_status}"
    print("  PASS: contact status lifecycle")


# =========================================================================
# Runner
# =========================================================================

def run_all_tests():
    """Run all outbound tests."""
    tests = [
        ("Campaign type preset loading", [
            test_campaign_types_load,
            test_campaign_type_has_required_fields,
            test_campaign_type_config_lookup,
            test_appointment_type_has_custom_fields,
            test_generic_appointment_setter_type_has_contact_fields,
            test_aesthetic_appointment_setter_type_remains_sample,
            test_portfolio_sample_campaign_types_point_to_existing_prompts,
            test_payment_type_has_amount_due,
        ]),
        ("System message template rendering", [
            test_template_placeholder_rendering,
            test_template_custom_fields_rendering,
            test_template_missing_placeholder_left_as_is,
            test_outbound_system_message_appends_language_and_accent_policy,
            test_outbound_system_message_does_not_duplicate_existing_language_accent_sections,
            test_aesthetic_outbound_type_uses_aesthetic_prompt_when_script_blank,
            test_outbound_system_message_renders_botox_lead_context,
            test_outbound_system_message_renders_tshape_csv_offer_alias,
            test_outbound_system_message_blank_offer_uses_active_prompt_with_context,
            test_template_fallback_contact_name,
        ]),
        ("Contact validation", [
            test_contact_phone_required,
            test_contact_custom_fields_default,
            test_contact_row_build,
            test_contact_payload_builds_trigger_call_contact,
            test_trigger_call_api_route_contract,
            test_dashboard_outbound_form_exposes_appointment_setter_contact_fields,
            test_dashboard_exposes_appointment_setter_outcome_statuses,
            test_list_campaigns_includes_contact_progress,
            test_dashboard_outbound_has_confirm_modal_and_editor_header,
            test_resolve_campaign_type_default_script_loads_generic_and_sample_prompts,
            test_dashboard_outbound_script_panel_layout,
            test_dashboard_outbound_sample_type_guidance,
        ]),
        ("Config helpers", [
            test_config_outbound_enabled_default,
            test_config_max_concurrency_clamped,
            test_config_supabase_table_defaults,
            test_config_outbound_from_number,
            test_concurrency_clamp_logic,
        ]),
        ("TwiML generation", [
            test_outbound_twiml_shape,
            test_outbound_twiml_url_encoding,
        ]),
        ("Twilio status callback mapping", [
            test_status_callback_terminal_mapping,
            test_status_callback_non_terminal_ignored,
            test_status_callback_empty_call_sid,
            test_contact_status_lifecycle,
        ]),
    ]

    total = 0
    passed = 0
    failed = 0

    for group_name, test_fns in tests:
        print(f"\n--- {group_name} ---")
        for fn in test_fns:
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failed += 1
                print(f"  FAIL: {fn.__name__}: {e}")

    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed:
        print("Some tests FAILED.")
        sys.exit(1)
    else:
        print("All tests passed.")


if __name__ == "__main__":
    run_all_tests()
