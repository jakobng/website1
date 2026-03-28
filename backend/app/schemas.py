"""Pydantic schemas for API request/response."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ShootLocation(BaseModel):
    country: str
    percent: float = Field(..., ge=0, le=100)


class SpendAllocation(BaseModel):
    """Optional per-country spend breakdown (more accurate than shoot %)."""
    country: str
    amount: float = Field(..., ge=0)
    currency: str = "EUR"


class ProjectInput(BaseModel):
    """User-submitted project parameters."""
    title: str = "Untitled Project"
    format: str = "feature_fiction"
    stage: str = "development"
    budget: float = Field(..., gt=0)
    budget_currency: str = "EUR"

    # Flexibility
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    shoot_locations_flexible: bool = False
    open_to_copro_countries: list[str] = Field(default_factory=list)

    # Creative team
    director_nationalities: list[str] = Field(default_factory=list)
    producer_nationalities: list[str] = Field(default_factory=list)
    production_company_countries: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    subject_country: Optional[str] = None
    story_setting_country: Optional[str] = None

    # Stage — primary stage plus any additional stages the project will pass through
    # e.g. a project currently in development that will shoot soon can add "production"
    # to see what production-stage incentives they should be planning for
    stages: list[str] = Field(default_factory=list)  # if set, overrides single `stage` for eligibility checks

    # Budget breakdown — detailed allocation into standard film budget sections
    # All values are fractions of total budget (0.0 to 1.0)
    # 1. Development (R&D, Script, Legal)
    development_fraction: float = 0.05
    # 2. Above-the-Line (Producer, Director, Lead Cast)
    above_the_line_fraction: float = 0.20
    # 3. Production / Below-the-Line (Crew, Equipment, Locations, etc. - location dependent)
    production_btl_fraction: float = 0.40
    # 4. Post-Production / Below-the-Line (Edit, Sound, VFX, Lab - location dependent)
    post_production_btl_fraction: float = 0.25
    # 5. Other (Insurance, Completion Bond, Contingency)
    other_fraction: float = 0.10

    # Backwards compatibility / simplified internal use
    # shooting_spend_fraction now maps to production_btl_fraction
    # post_production_spend_fraction now maps to post_production_btl_fraction
    @property
    def shooting_spend_fraction(self) -> float:
        return self.production_btl_fraction
    
    @property
    def post_production_spend_fraction(self) -> float:
        return self.post_production_btl_fraction

    post_production_country: Optional[str] = None  # ISO code, or None = flexible/unassigned

    # Production plan
    shoot_locations: list[ShootLocation] = Field(default_factory=list)
    spend_allocations: list[SpendAllocation] = Field(default_factory=list)  # optional override
    post_flexible: bool = False
    vfx_flexible: bool = False
    editor_nationality: Optional[str] = None
    local_crew_percent: Optional[float] = None

    # Partnership
    has_coproducer: list[str] = Field(default_factory=list)
    willing_add_coproducer: bool = True

    # Existing financing
    broadcaster_attached: Optional[str] = None
    streamer_attached: bool = False

    # Cultural test status — set by the user after reviewing requirements
    # country codes (e.g. "GB") where user has confirmed they pass the cultural test
    cultural_test_passed: list[str] = Field(default_factory=list)
    # country codes where user has confirmed they fail (or chosen not to pursue)
    cultural_test_failed: list[str] = Field(default_factory=list)


class DocumentReference(BaseModel):
    """Lightweight pointer to a PDF document and optional annotation."""
    document_id: int
    annotation_id: Optional[int] = None


class SourceReference(BaseModel):
    """A verifiable reference to a primary source."""
    url: str
    description: str  # e.g., "BFI Cultural Test Guidance"
    clause_reference: Optional[str] = None  # e.g., "Section 3.2", "Article 6(1)"
    accessed: Optional[str] = None  # ISO date
    document_ref: Optional[DocumentReference] = None  # link to embedded PDF


class Requirement(BaseModel):
    description: str
    category: str = "general"
    source: Optional[SourceReference] = None


class CalculationStep(BaseModel):
    """One line in a step-by-step benefit calculation."""
    label: str                          # e.g. "Qualifying spend"
    formula: str                        # e.g. "budget × shoot% / 100"
    value: float                        # the numeric result
    currency: Optional[str] = None      # e.g. "EUR"
    note: Optional[str] = None          # e.g. "capped at programme maximum"
    source_url: Optional[str] = None
    clause_reference: Optional[str] = None


class IncentiveBenefit(BaseModel):
    """Clear explanation of one incentive's benefit with source references."""
    criteria_summary: str
    estimated_qualifying_spend: float
    spend_currency: str = "EUR"
    benefit_type: str  # "tax_credit", "cash_rebate", "grant"
    benefit_amount: float
    benefit_currency: str = "EUR"
    benefit_explanation: str
    calculation_notes: str = ""  # prose summary (kept for backwards compat)
    calculation_steps: list[CalculationStep] = Field(default_factory=list)  # structured steps
    sources: list[SourceReference] = Field(default_factory=list)


class NearMiss(BaseModel):
    """An incentive the project almost qualifies for."""
    incentive_name: str
    country_code: str
    country_name: str = ""
    region: Optional[str] = None
    incentive_type: str = ""
    rebate_percent: Optional[float] = None
    gap_description: str  # e.g. "Increase UK shoot from 15% to 20% (5pp gap)"
    gap_category: str  # shoot, budget, spend, crew, cultural, post
    current_value: float = 0.0
    required_value: float = 0.0
    potential_benefit_amount: Optional[float] = None
    potential_benefit_currency: str = "EUR"
    source: Optional[SourceReference] = None


class EligibleIncentive(BaseModel):
    name: str
    country_code: str
    country_name: str = ""
    region: Optional[str] = None
    incentive_type: str = ""
    rebate_percent: Optional[float] = None
    requirements: list[Requirement] = Field(default_factory=list)
    benefit: Optional[IncentiveBenefit] = None
    estimated_contribution_percent: float = 0.0


class TreatyInfo(BaseModel):
    """Treaty information relevant to a scenario."""
    treaty_name: str
    min_share_percent: Optional[float] = None
    max_share_percent: Optional[float] = None
    creative_requirements: Optional[str] = None
    competent_authorities: list[str] = Field(default_factory=list)
    requires_approval: bool = True
    source: Optional[SourceReference] = None


class Suggestion(BaseModel):
    suggestion_type: str
    country: Optional[str] = None
    description: str
    potential_benefit: Optional[str] = None
    estimated_amount: Optional[float] = None
    estimated_currency: str = "EUR"
    effort_level: Optional[str] = None  # "low", "medium", "high"
    source: Optional[SourceReference] = None


class CoproductionPartner(BaseModel):
    """A country's role in a coproduction structure."""
    country_code: str
    country_name: str = ""
    role: str = "minority"  # majority, minority, third_party
    estimated_share_percent: Optional[float] = None
    eligible_incentives: list[EligibleIncentive] = Field(default_factory=list)
    applicable_treaties: list[TreatyInfo] = Field(default_factory=list)


class Scenario(BaseModel):
    """A coproduction financing structure."""
    partners: list[CoproductionPartner] = Field(default_factory=list)
    estimated_total_financing_percent: float = 0.0
    estimated_total_financing_amount: float = 0.0
    financing_currency: str = "EUR"
    requirements: list[Requirement] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    near_misses: list[NearMiss] = Field(default_factory=list)
    rationale: str = ""
    treaty_basis: list[TreatyInfo] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    project_summary: str
    scenarios: list[Scenario]
    warnings: list[str] = Field(default_factory=list)
    data_disclaimer: str = (
        "Figures are based on published programme rules and treaty texts cited in each result. "
        "They change with budget rounds, law amendments, and programme updates. "
        "This tool does not replace professional legal or accounting advice."
    )


# --- Document / PDF viewer schemas ---

class DocumentAnnotationResponse(BaseModel):
    id: int
    page_number: int
    search_text: Optional[str] = None
    clause_reference: Optional[str] = None
    topic: Optional[str] = None
    original_text: Optional[str] = None
    english_summary: str

class DocumentResponse(BaseModel):
    id: int
    title: str
    document_type: str
    language: str
    country_codes: list[str]
    page_count: Optional[int] = None
    original_url: Optional[str] = None
    publisher: Optional[str] = None
    annotations: list[DocumentAnnotationResponse] = Field(default_factory=list)
