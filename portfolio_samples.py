"""Built-in portfolio sample metadata.

This is the code source of truth for reusable demo samples. Runtime campaign
presets, local setup helpers, prompt preview shortcuts, and tests should consume
this module instead of repeating sample prompt/campaign mappings.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioSample:
    key: str
    label: str
    campaign_label: str
    prompt_path: str
    campaign_type: str
    company_name: str
    agent_name: str
    agent_label: str
    timezone: str
    booking_enabled: bool
    booking_use: str
    primary_flow: str
    demo_calls: tuple[str, ...]


PORTFOLIO_SAMPLES: dict[str, PortfolioSample] = {
    "dentist": PortfolioSample(
        key="dentist",
        label="Dentist clinic",
        campaign_label="Sample: Dentist Clinic",
        prompt_path="prompts/samples/dentist_clinic_receptionist.md",
        campaign_type="sample_dentist_clinic",
        company_name="Bright Smile Dental",
        agent_name="Ava",
        agent_label="dentist_demo",
        timezone="America/Los_Angeles",
        booking_enabled=True,
        booking_use="Google Calendar appointment",
        primary_flow="New patient intake, insurance/basic FAQ, cleaning/consult booking",
        demo_calls=("new patient cleaning", "tooth-pain callback", "insurance follow-up"),
    ),
    "medical-office": PortfolioSample(
        key="medical-office",
        label="Medical office",
        campaign_label="Sample: Medical Office",
        prompt_path="prompts/samples/medical_office_receptionist.md",
        campaign_type="sample_medical_office",
        company_name="Oak Valley Medical",
        agent_name="Mia",
        agent_label="medical_office_demo",
        timezone="America/New_York",
        booking_enabled=True,
        booking_use="Google Calendar appointment",
        primary_flow="Receptionist, callback triage, non-emergency appointment scheduling",
        demo_calls=("routine visit booking", "message for provider", "urgent-symptom safety routing"),
    ),
    "real-estate": PortfolioSample(
        key="real-estate",
        label="Real estate",
        campaign_label="Sample: Real Estate",
        prompt_path="prompts/samples/real_estate_showing_scheduler.md",
        campaign_type="sample_real_estate",
        company_name="Acme Realty",
        agent_name="Mia",
        agent_label="real_estate_demo",
        timezone="America/Denver",
        booking_enabled=True,
        booking_use="Showing calendar",
        primary_flow="Buyer/seller intake, showing requests, open-house callback",
        demo_calls=("showing request", "seller consultation", "property question callback"),
    ),
    "home-services": PortfolioSample(
        key="home-services",
        label="Home services",
        campaign_label="Sample: Home Services",
        prompt_path="prompts/samples/home_services_estimate_scheduler.md",
        campaign_type="sample_home_services",
        company_name="Summit Home Services",
        agent_name="Noah",
        agent_label="home_services_demo",
        timezone="America/Chicago",
        booking_enabled=True,
        booking_use="Estimate/service calendar",
        primary_flow="Estimate request, service address capture, technician visit booking",
        demo_calls=("estimate booking", "urgent issue capture", "service-area callback"),
    ),
    "ecommerce-support": PortfolioSample(
        key="ecommerce-support",
        label="E-commerce support",
        campaign_label="Sample: E-commerce Support",
        prompt_path="prompts/samples/ecommerce_support_receptionist.md",
        campaign_type="sample_ecommerce_support",
        company_name="Northstar Goods",
        agent_name="Lena",
        agent_label="ecommerce_support_demo",
        timezone="America/Los_Angeles",
        booking_enabled=False,
        booking_use="Usually no booking; save call record or handoff",
        primary_flow="Order issue intake, return/exchange routing, escalation",
        demo_calls=("return request", "damaged item", "order-status escalation"),
    ),
    "b2b-qualifier": PortfolioSample(
        key="b2b-qualifier",
        label="B2B lead qualifier",
        campaign_label="Sample: B2B Lead Qualifier",
        prompt_path="prompts/samples/b2b_lead_qualifier.md",
        campaign_type="sample_b2b_qualifier",
        company_name="Atlas Growth Systems",
        agent_name="Eli",
        agent_label="b2b_qualifier_demo",
        timezone="America/New_York",
        booking_enabled=True,
        booking_use="Sales calendar",
        primary_flow="Budget/timeline/use-case qualification, sales meeting booking",
        demo_calls=("discovery call booking", "not-ready callback", "technical handoff"),
    ),
    "general-receptionist": PortfolioSample(
        key="general-receptionist",
        label="General receptionist",
        campaign_label="Sample: General Receptionist",
        prompt_path="prompts/samples/general_receptionist.md",
        campaign_type="sample_general_receptionist",
        company_name="Acme Services",
        agent_name="Alex",
        agent_label="receptionist_demo",
        timezone="America/Los_Angeles",
        booking_enabled=True,
        booking_use="Optional appointment calendar",
        primary_flow="Answer simple questions, capture messages, transfer or callback",
        demo_calls=("appointment booking", "message taking", "live transfer"),
    ),
}


SAMPLE_PROMPTS = {key: sample.prompt_path for key, sample in PORTFOLIO_SAMPLES.items()}
PORTFOLIO_SAMPLE_CAMPAIGN_TYPES = {
    sample.campaign_type: sample.prompt_path for sample in PORTFOLIO_SAMPLES.values()
}


def iter_samples() -> tuple[PortfolioSample, ...]:
    return tuple(PORTFOLIO_SAMPLES[key] for key in sorted(PORTFOLIO_SAMPLES))


def get_sample(key: str) -> PortfolioSample:
    return PORTFOLIO_SAMPLES[key]
