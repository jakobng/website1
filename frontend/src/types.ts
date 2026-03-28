/** API types matching backend schemas */

export interface ShootLocation {
  country: string
  percent: number
}

export interface SpendAllocation {
  country: string
  amount: number
  currency: string
}

export interface ProjectInput {
  title: string
  format: string
  stage: string
  budget: number
  budget_currency: string
  budget_min?: number
  budget_max?: number
  shoot_locations_flexible: boolean
  open_to_copro_countries: string[]
  director_nationalities: string[]
  producer_nationalities: string[]
  production_company_countries: string[]
  languages: string[]
  subject_country?: string
  story_setting_country?: string
  
  // Budget breakdown fractions (0.0 - 1.0)
  development_fraction: number
  above_the_line_fraction: number
  production_btl_fraction: number
  post_production_btl_fraction: number
  other_fraction: number

  post_production_country?: string
  shoot_locations: ShootLocation[]
  spend_allocations: SpendAllocation[]
  stages: string[]
  post_flexible: boolean
  vfx_flexible: boolean
  editor_nationality?: string
  local_crew_percent?: number
  has_coproducer: string[]
  willing_add_coproducer: boolean
  broadcaster_attached?: string
  streamer_attached: boolean
  cultural_test_passed: string[]
  cultural_test_failed: string[]
}

export interface DocumentReference {
  document_id: number
  annotation_id?: number | null
}

export interface DocumentAnnotation {
  id: number
  page_number: number
  search_text?: string | null
  clause_reference?: string | null
  topic?: string | null
  original_text?: string | null
  english_summary: string
}

export interface DocumentInfo {
  id: number
  title: string
  document_type: string
  language: string
  country_codes: string[]
  page_count?: number | null
  original_url?: string | null
  publisher?: string | null
  annotations: DocumentAnnotation[]
}

export interface SourceReference {
  url: string
  description: string
  clause_reference?: string | null
  accessed?: string
  document_ref?: DocumentReference | null
}

export interface InvestigatingItem {
  incentive: string
  country: string
  gap: string
  potential_amount?: number
  potential_currency?: string
}

export interface IntakeResponse {
  session_id: string
  reply: string
  project_draft: ProjectInput
  completeness_score: number
  is_ready: boolean
  error?: string
  investigating?: InvestigatingItem[]
}

export interface Requirement {
  description: string
  category: string
  source?: SourceReference | null
}

export interface CalculationStep {
  label: string
  formula: string
  value: number
  currency?: string | null
  note?: string | null
  source_url?: string | null
  clause_reference?: string | null
}

export interface IncentiveBenefit {
  criteria_summary: string
  estimated_qualifying_spend: number
  spend_currency: string
  benefit_type: string
  benefit_amount: number
  benefit_currency: string
  benefit_explanation: string
  calculation_notes: string
  calculation_steps: CalculationStep[]
  sources: SourceReference[]
}

export interface EligibleIncentive {
  id?: number
  name: string
  country_code: string
  country_name: string
  region?: string
  incentive_type: string
  rebate_percent?: number
  requirements: Requirement[]
  benefit?: IncentiveBenefit | null
  estimated_contribution_percent: number
}

export interface TreatyInfo {
  treaty_name: string
  min_share_percent?: number
  max_share_percent?: number
  creative_requirements?: string
  competent_authorities: string[]
  requires_approval: boolean
  source?: SourceReference | null
}

export interface NearMiss {
  incentive_name: string
  country_code: string
  country_name: string
  region?: string
  incentive_type: string
  rebate_percent?: number
  gap_description: string
  gap_category: string
  current_value: number
  required_value: number
  potential_benefit_amount?: number
  potential_benefit_currency: string
  source?: SourceReference | null
}

export interface Suggestion {
  suggestion_type: string
  country?: string
  description: string
  potential_benefit?: string
  estimated_amount?: number
  estimated_currency?: string
  effort_level?: string
  source?: SourceReference | null
}

export interface CoproductionPartner {
  country_code: string
  country_name: string
  role: string
  estimated_share_percent?: number
  eligible_incentives: EligibleIncentive[]
  applicable_treaties: TreatyInfo[]
}

export interface Scenario {
  partners: CoproductionPartner[]
  estimated_total_financing_percent: number
  estimated_total_financing_amount: number
  financing_currency: string
  requirements: Requirement[]
  suggestions: Suggestion[]
  near_misses: NearMiss[]
  rationale: string
  treaty_basis: TreatyInfo[]
}

export interface AnalyzeResponse {
  project_summary: string
  scenarios: Scenario[]
  warnings: string[]
  data_disclaimer: string
}

export interface CountryOption {
  code: string
  name: string
}
