from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class ProjectFormat(str, Enum):
    feature_fiction = "feature_fiction"
    documentary = "documentary"
    series = "series"

class ProjectStage(str, Enum):
    dev = "dev"
    prod = "prod"
    post = "post"

class ShootLocation(BaseModel):
    country: str
    percent: float # Percent of total budget spent in this country

class ProjectInput(BaseModel):
    title: str
    format: ProjectFormat
    stage: ProjectStage
    total_budget: float
    global_svod_secured: bool
    director_nationality: str
    producer_nationality: str
    shoot_locations: List[ShootLocation]
    post_flexible: bool

class IncentiveSchema(BaseModel):
    id: int
    name: str
    country: str
    type: str
    gross_rebate_percent: float
    net_yield_multiplier: float
    state_aid_eligible: bool
    requires_territory_rights: bool

    class Config:
        from_attributes = True

class TreatySchema(BaseModel):
    id: int
    country_a: str
    country_b: str
    min_financial_share_a: float
    min_financial_share_b: float
    requires_official_copro_status: bool

    class Config:
        from_attributes = True

class Scenario(BaseModel):
    lead_country: str
    partner_countries: List[str]
    eligible_incentives: List[IncentiveSchema]
    total_gross_financing: float
    total_net_financing: float
    actionable_requirements: List[str]
    gap_percentage: float # Percentage of budget covered by net financing
