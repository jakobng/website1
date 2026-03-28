"""SQLAlchemy ORM models for incentives and treaties."""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, Boolean, Text, JSON
from app.database import Base


class Incentive(Base):
    """A film financing incentive (tax credit, cash rebate, grant, fund)."""
    __tablename__ = "incentives"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    country_code = Column(String(2), nullable=False, index=True)  # ISO 3166-1 alpha-2
    region = Column(String, nullable=True)  # e.g., "Bavaria", "Canary Islands"

    incentive_type = Column(String, nullable=False)  # tax_credit, cash_rebate, grant, fund
    # What the rebate/credit applies to
    rebate_percent = Column(Float, nullable=True)  # e.g., 30.0 means 30%
    rebate_applies_to = Column(String, default="qualifying_spend")
    # One of: qualifying_spend, labour_only, all_local_spend
    # This fixes the Canada CPTC issue where 25% applies only to labour

    labour_fraction = Column(Float, nullable=True)  # Fraction of qualifying spend counted as labour; required when rebate_applies_to='labour_only'. Must have source citation.

    max_cap_amount = Column(Float, nullable=True)
    max_cap_currency = Column(String(3), default="EUR")

    # Thresholds — now correctly separated
    min_total_budget = Column(Float, nullable=True)        # Minimum total production budget
    min_qualifying_spend = Column(Float, nullable=True)    # Minimum spend in-country
    min_spend_currency = Column(String(3), nullable=True)  # Currency of min_total_budget / min_qualifying_spend
    # When null, defaults to max_cap_currency (or EUR). Needed because e.g. Poland's
    # PLN 1M threshold != EUR 1M.
    min_spend_percent = Column(Float, nullable=True)       # Min % of budget spent in-country
    min_shoot_percent = Column(Float, nullable=True)       # Min % of shoot days in-country
    min_shoot_days = Column(Integer, nullable=True)

    # Format-specific thresholds (documentary)
    # When set, these override min_total_budget / min_qualifying_spend for documentary projects
    min_total_budget_documentary = Column(Float, nullable=True)
    min_qualifying_spend_documentary = Column(Float, nullable=True)

    # Eligibility
    eligible_formats = Column(JSON, nullable=True)   # ["feature_fiction", "documentary", "series", "animation"]
    eligible_stages = Column(JSON, nullable=True)    # ["development", "production", "post"]

    # Mutual Exclusivity (IDs or Names of incentives this cannot be stacked with)
    mutually_exclusive_with = Column(JSON, nullable=True) # ["Incentive Name 1", "Incentive Name 2"]

    # Requirements
    local_producer_required = Column(Boolean, default=True)
    local_crew_min_percent = Column(Float, nullable=True)
    post_production_local_required = Column(Boolean, default=False)
    post_spend_min_percent = Column(Float, nullable=True)
    cultural_test_required = Column(Boolean, default=False)
    cultural_test_min_score = Column(Integer, nullable=True)
    cultural_test_total_score = Column(Integer, nullable=True)  # e.g., 35 for UK

    # Conditional rates — higher rates triggered by specific project characteristics
    # Format: [{"condition": "vfx_spend_gt", "threshold": 2000000, "rate": 40.0, "note": "..."}]
    conditional_rates = Column(JSON, nullable=True)

    stacking_allowed = Column(Boolean, default=True)

    # Provenance — mandatory per DATA_VERIFICATION.md
    source_url = Column(Text, nullable=True)
    source_description = Column(String, nullable=True)  # e.g., "BFI Cultural Test Guidance"
    clause_reference = Column(String, nullable=True)  # e.g., "Section 3.2", "Article 6(1)"
    notes = Column(Text, nullable=True)
    last_verified = Column(String, nullable=True)  # ISO date string


class Treaty(Base):
    """A bilateral or multilateral coproduction treaty."""
    __tablename__ = "treaties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # e.g., "France-Canada Bilateral Treaty"
    treaty_type = Column(String, default="bilateral")  # bilateral, multilateral

    country_a_code = Column(String(2), nullable=False)
    country_b_code = Column(String(2), nullable=True)  # null for multilateral

    # Financial share rules
    min_share_percent = Column(Float, nullable=True)  # Minimum contribution from minority coproducer
    max_share_percent = Column(Float, nullable=True)  # Maximum contribution from majority coproducer
    min_share_third_party = Column(Float, nullable=True)  # Min share for third-party coproducer

    # What the treaty covers
    eligible_formats = Column(JSON, nullable=True)  # ["feature_fiction", "documentary", "series", "animation"]

    # Creative contribution rules
    creative_contribution_required = Column(Boolean, default=True)
    creative_requirements_summary = Column(Text, nullable=True)
    # e.g., "Creative and technical contributions must be proportional to financial share"

    # Administration
    competent_authority_a = Column(String, nullable=True)  # e.g., "CNC" for France
    competent_authority_b = Column(String, nullable=True)  # e.g., "Telefilm Canada"
    requires_prior_approval = Column(Boolean, default=True)

    # Status
    date_signed = Column(String, nullable=True)
    date_entered_force = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    # Provenance
    source_url = Column(Text, nullable=True)
    source_description = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    last_verified = Column(String, nullable=True)


class MultilateralMember(Base):
    """Membership in a multilateral treaty (e.g., European Convention)."""
    __tablename__ = "multilateral_members"

    id = Column(Integer, primary_key=True, index=True)
    treaty_id = Column(Integer, nullable=False)
    country_code = Column(String(2), nullable=False)
    date_ratified = Column(String, nullable=True)
    notes = Column(Text, nullable=True)


class Document(Base):
    """A PDF document (treaty text, fund guidelines, legislation)."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    document_type = Column(String, nullable=False)  # incentive_guidelines, treaty_text, legislation, regional_fund
    language = Column(String, default="en")  # ISO 639-1
    country_codes = Column(JSON, nullable=False)  # ["NO"] or ["SE", "NO"]
    filename = Column(String, nullable=False, unique=True)
    page_count = Column(Integer, nullable=True)
    original_url = Column(Text, nullable=True)
    publisher = Column(String, nullable=True)
    date_downloaded = Column(String, nullable=True)
    incentive_id = Column(Integer, nullable=True)  # FK to incentives.id
    treaty_id = Column(Integer, nullable=True)  # FK to treaties.id


class DocumentAnnotation(Base):
    """A highlighted section within a document, linked to a specific clause/rule."""
    __tablename__ = "document_annotations"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, nullable=False)  # FK to documents.id
    page_number = Column(Integer, nullable=False)  # 1-indexed
    search_text = Column(Text, nullable=True)  # Text to find & highlight on the page
    clause_reference = Column(String, nullable=True)  # "Section 4.2", "Article 6(1)"
    topic = Column(String, nullable=True)  # rebate_rate, minimum_spend, eligible_formats, creative_requirements
    original_text = Column(Text, nullable=True)  # Quoted text in original language (for non-English)
    english_summary = Column(Text, nullable=False)  # English summary of what this clause says
    incentive_id = Column(Integer, nullable=True)
    treaty_id = Column(Integer, nullable=True)
    sort_order = Column(Integer, default=0)


class SourceAlert(Base):
    """Track source freshness — when an incentive record was last verified."""
    __tablename__ = "source_alerts"

    id = Column(Integer, primary_key=True, index=True)
    incentive_id = Column(Integer, nullable=False, index=True)  # FK to incentives.id
    last_verified = Column(String, nullable=True)  # ISO date string from incentive.last_verified
    days_old = Column(Integer, nullable=True)  # Days since last_verified
    status = Column(String, nullable=False)  # "green" (<180 days), "yellow" (180-365), "red" (>365)
    checked_at = Column(String, nullable=False)  # ISO date when we ran the check


class DataUpdateProposal(Base):
    """Community-submitted proposal to update an incentive field."""
    __tablename__ = "data_update_proposals"

    id = Column(Integer, primary_key=True, index=True)
    incentive_id = Column(Integer, nullable=False, index=True)  # FK to incentives.id
    field_name = Column(String, nullable=False)  # e.g., "rebate_percent", "min_qualifying_spend"
    old_value = Column(String, nullable=True)  # Current value in DB (for audit trail)
    new_value = Column(String, nullable=False)  # Proposed new value
    proposed_source_url = Column(Text, nullable=False)  # Where the proposer found the new info
    proposed_source_description = Column(String, nullable=True)  # e.g., "Official CNC website, March 2026"
    proposer_email = Column(String, nullable=False)  # For follow-up
    status = Column(String, default="pending")  # "pending", "approved", "rejected"
    created_at = Column(String, nullable=False)  # ISO timestamp
    reviewed_at = Column(String, nullable=True)  # ISO timestamp when reviewed
    reviewed_by = Column(String, nullable=True)  # Admin who reviewed it
    notes = Column(Text, nullable=True)  # Admin review notes (why approved/rejected)
