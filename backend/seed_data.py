"""
Seed database: film incentives and coproduction treaties.

POLICY: Numeric fields must match official sources cited in source_url and notes.
See DATA_VERIFICATION.md. Unverified bulk data has been removed.

Every entry includes:
  - source_url: official government/agency URL
  - source_description: specific article/section/page reference
  - notes: key conditions quoted from the source
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models import Incentive, Treaty, MultilateralMember

Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Clear existing data for clean re-seed
db.query(MultilateralMember).delete()
db.query(Treaty).delete()
db.query(Incentive).delete()
db.commit()


# =============================================================================
# INCENTIVES — each entry cites official sources
# =============================================================================

def inc(**kwargs):
    """Create an Incentive with sensible defaults."""
    defaults = {
        "eligible_formats": ["feature_fiction", "documentary", "series", "animation"],
        "eligible_stages": ["production"],
        "local_producer_required": True,
        "rebate_applies_to": "qualifying_spend",
        "max_cap_currency": "EUR",
        "stacking_allowed": True,
    }
    defaults.update(kwargs)
    return Incentive(**defaults)


incentives = [
    # -------------------------------------------------------------------------
    # FRANCE
    # -------------------------------------------------------------------------
    inc(
        name="France TRIP (Tax Rebate for International Production)",
        country_code="FR",
        incentive_type="tax_rebate",
        rebate_percent=30.0,
        max_cap_amount=30_000_000,
        min_qualifying_spend=250_000,
        min_shoot_days=5,
        eligible_formats=["feature_fiction", "series", "animation"],
        mutually_exclusive_with=["France Crédit d'impôt Cinéma (domestic)"],
        conditional_rates=[
            {"condition": "vfx_spend_gt", "threshold": 2000000, "rate": 40.0,
             "note": "Rate rises to 40% if VFX spend exceeds €2M (Art. 220 quaterdecies)"}
        ],
        source_url="https://www.cnc.fr/professionnels/aides-et-financements/multi-sectoriel/production/credit-dimpot-international_778354",
        source_description="CNC — Crédit d'impôt international (C2I/TRIP)",
        clause_reference="Art. 220 quaterdecies, Code général des impôts",
        notes="30% of eligible French spend; cap €30M/project; min €250k eligible spend in France; "
              "live-action min 5 shooting days in France. Documentaries excluded. "
              "Rate rises to 40% if VFX spend exceeds €2M. Mutually exclusive with domestic credit.",
        last_verified="2025-03",
    ),
    inc(
        name="France Crédit d'impôt Cinéma (domestic)",
        country_code="FR",
        incentive_type="tax_credit",
        rebate_percent=25.0,
        max_cap_amount=25_000_000,
        eligible_formats=["feature_fiction", "documentary", "animation"],
        mutually_exclusive_with=["France TRIP (Tax Rebate for International Production)"],
        source_url="https://www.cnc.fr/professionnels/aides-et-financements/cinema/production/credit-dimpot-cinema_191460",
        source_description="CNC — Crédit d'impôt cinéma",
        clause_reference="Art. 220 sexies, Code général des impôts",
        notes="25% tax credit on qualifying French expenditure for French-initiated or official coproductions. "
              "Cap €25M. Must be a French or European coproduction with French producer. Mutually exclusive with TRIP.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # UNITED KINGDOM
    # -------------------------------------------------------------------------
    inc(
        name="UK Audio-Visual Expenditure Credit (AVEC)",
        country_code="GB",
        incentive_type="tax_credit",
        rebate_percent=34.0,
        max_cap_currency="GBP",
        min_spend_percent=10.0,
        cultural_test_required=True,
        cultural_test_min_score=18,
        cultural_test_total_score=35,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.gov.uk/guidance/claim-audio-visual-expenditure-credits-for-corporation-tax",
        source_description="HMRC — Audio Visual Expenditure Credit guidance",
        clause_reference="s.1179A–1179KA, Corporation Tax Act 2009 (as inserted by Finance (No.2) Act 2023)",
        notes="34% of qualifying UK expenditure (credit is taxable income, net benefit ~25.5% depending on tax position). "
              "Min 10% UK core expenditure. Cultural test: 18/35 points (BFI administers). "
              "Replaced old Film Tax Relief from 1 Jan 2024.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # IRELAND
    # -------------------------------------------------------------------------
    inc(
        name="Ireland Section 481 Film Tax Credit",
        country_code="IE",
        incentive_type="tax_credit",
        rebate_percent=32.0,
        max_cap_amount=125_000_000,
        min_qualifying_spend=125_000,
        min_spend_currency="EUR",
        cultural_test_required=True,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        conditional_rates=[
            {"condition": "budget_gte", "threshold": 0, "rate": 40.0,
             "note": "Scéal Uplift: 40% enhanced rate for qualifying lower-budget feature/animation "
                     "films with eligible expenditure under €20M (effective 20 May 2025). "
                     "Key creative must be EEA national/resident."},
            {"condition": "vfx_spend_gt", "threshold": 1_000_000, "rate": 40.0,
             "note": "VFX uplift: 40% rate on qualifying VFX expenditure ≥€1M "
                     "(capped at €10M VFX spend per project, remainder at 32%)."},
        ],
        source_url="https://www.revenue.ie/en/companies-and-charities/reliefs-and-exemptions/film-relief/index.aspx",
        source_description="Revenue.ie — Film Relief (Section 481)",
        clause_reference="s.481, Taxes Consolidation Act 1997; S.I. No. 197/2025",
        notes="32% of eligible Irish expenditure; min €125k qualifying spend; max credit €125M/project. "
              "Qualification via cultural test, industry development test, or official coproduction status. "
              "Scéal Uplift: 40% enhanced rate for lower-budget feature/animation films (expenditure <€20M, "
              "key creative from EEA, effective 20 May 2025). "
              "VFX uplift: 40% on ≥€1M qualifying VFX spend (max €10M VFX per project).",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # GERMANY
    # -------------------------------------------------------------------------
    inc(
        name="Germany DFFF (German Federal Film Fund)",
        country_code="DE",
        incentive_type="grant",
        rebate_percent=30.0,
        max_cap_amount=5_000_000,
        min_total_budget=1_000_000,
        min_total_budget_documentary=200_000,
        min_spend_percent=25.0,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        conditional_rates=[
            {"condition": "budget_gte", "threshold": 20000000, "field": "min_spend_percent", "value": 20.0,
             "note": "Min German spend reduced to 20% if total budget ≥€20M (FFG 2025)"}
        ],
        source_url="https://www.ffa.de/dfff-en.html",
        source_description="FFA — DFFF Production Fund guidelines",
        clause_reference="Filmförderungsgesetz (FFG) 2025 / BKM-Richtlinie DFFF",
        notes="Up to 30% of eligible German production costs; min total budget €1M (feature), €200k (documentary); "
              "min 25% of total production costs in Germany (20% if budget ≥€20M); max €5M DFFF/project. "
              "Competitive grant, not automatic.",
        last_verified="2025-03",
    ),
    inc(
        name="Germany GMPF (German Motion Picture Fund)",
        country_code="DE",
        incentive_type="grant",
        rebate_percent=30.0,
        max_cap_amount=10_000_000,
        min_total_budget=5_000_000,
        eligible_formats=["feature_fiction", "series"],
        source_url="https://www.ffa.de/gmpf-en.html",
        source_description="FFA — GMPF guidelines (updated Feb 2025)",
        clause_reference="Filmförderungsgesetz (FFG) 2025 / BKM-Richtlinie GMPF",
        notes="30% of approved German production costs (raised from 25% on 1 Feb 2025, uniform with DFFF). "
              "For high-budget productions: min €5M total budget, or €1.25M per episode for series. "
              "Max €10M/project. Part of €250M annual federal film funding from 2026.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # NETHERLANDS
    # -------------------------------------------------------------------------
    inc(
        name="Netherlands Film Production Incentive",
        country_code="NL",
        incentive_type="cash_rebate",
        rebate_percent=35.0,
        max_cap_amount=30_000_000,
        min_total_budget=1_000_000,
        min_total_budget_documentary=250_000,
        min_qualifying_spend=150_000,
        min_qualifying_spend_documentary=100_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.filmfonds.nl/en/funding/fund/netherlands-film-production-incentive",
        source_description="Netherlands Film Fund — Production Incentive regulations",
        notes="35% cash rebate on qualifying Dutch production costs; max €30M per audiovisual work. "
              "Min budget: €1M (feature), €250k (documentary). Min eligible spend: €150k (feature), €100k (documentary). "
              "2026 annual budget: €20M for film (4 rounds), €9.5M for high-end series (3 rounds). Cultural test applies.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # BELGIUM
    # -------------------------------------------------------------------------
    inc(
        name="Belgium Tax Shelter",
        country_code="BE",
        incentive_type="tax_shelter",
        rebate_percent=42.0,
        max_cap_amount=21_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://finances.belgium.be/fr/entreprises/impot_des_societes/avantages_fiscaux/tax-shelter",
        source_description="SPF Finances — Tax Shelter pour la production audiovisuelle",
        clause_reference="Art. 194ter, Code des impôts sur les revenus 1992 (CIR92)",
        notes="Investors receive 42% tax break; production receives investment equivalent to ~35-42% of qualifying Belgian spend. "
              "Max investment per work: €21M. Min 70% of spending must be in Belgium/EEA (90% in Belgium for maximum benefit). "
              "Framework agreement must be signed before principal photography.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # ITALY
    # -------------------------------------------------------------------------
    inc(
        name="Italy Tax Credit for Foreign Productions",
        country_code="IT",
        incentive_type="tax_credit",
        rebate_percent=40.0,
        max_cap_amount=20_000_000,
        min_qualifying_spend=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://cinema.cultura.gov.it/en/tax-credit/",
        source_description="MiC — Tax Credit for foreign productions",
        clause_reference="Art. 19, Law 220/2016 (Legge Cinema e Audiovisivo)",
        notes="40% tax credit on qualifying Italian expenditure for foreign productions. "
              "Min €200k qualifying spend in Italy. Cap €20M/project. "
              "Italian spend must represent at least 80% of the project's eligible costs (for the Italian portion). "
              "Requires Italian executive producer.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SPAIN
    # -------------------------------------------------------------------------
    inc(
        name="Spain Tax Incentive for Foreign Productions",
        country_code="ES",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        max_cap_amount=10_000_000,
        min_qualifying_spend=1_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328",
        source_description="Ley del Impuesto sobre Sociedades (BOE-A-2014-12328)",
        clause_reference="Art. 36.2, Ley 27/2014",
        notes="30% on first €1M of qualifying spend + 25% on remainder. Cap €10M/project. "
              "Min €1M spend in Spain. Canary Islands: enhanced rate up to 50%/45%. "
              "Requires Spanish executive producer or service company.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Canary Islands Tax Incentive",
        country_code="ES",
        region="Canary Islands",
        incentive_type="tax_credit",
        rebate_percent=50.0,
        max_cap_amount=18_000_000,
        min_qualifying_spend=1_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.gobiernodecanarias.org/hacienda/canariaszec/",
        source_description="Canary Islands ZEC / enhanced film incentive",
        clause_reference="RDL 15/2014 (Real Decreto-ley 15/2014, 19 December)",
        notes="50% on first €1M qualifying spend + 45% on remainder (enhanced over mainland Spain). "
              "Max €18M/project. Same basic requirements as mainland but with higher rates under "
              "Canary Islands special economic zone rules.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # CZECH REPUBLIC
    # -------------------------------------------------------------------------
    inc(
        name="Czech Republic Film Incentive Programme",
        country_code="CZ",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=450_000_000,
        max_cap_currency="CZK",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        conditional_rates=[
            {"condition": "format_eq", "format": "animation", "rate": 35.0,
             "note": "35% rebate for animation/digitally produced projects with no live-action shooting in CZ."}
        ],
        source_url="https://www.filmcommission.cz/en/production-incentives/",
        source_description="Czech Film Commission — Production Incentives (updated Jan 2025)",
        clause_reference="Czech Audiovisual Act (amended 13 Dec 2024, effective 1 Jan 2025)",
        notes="25% cash rebate on qualifying Czech spend (raised from 20% on 1 Jan 2025). "
              "35% for animation/digital projects (no live-action). Cap CZK 450M per project (tripled from CZK 150M). "
              "Phase 2 (1 Jan 2026): streamlined admin, recalibrated min spend limits, documentary series added.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # HUNGARY
    # -------------------------------------------------------------------------
    inc(
        name="Hungary Film Incentive (indirect subsidy)",
        country_code="HU",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        min_qualifying_spend=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://nfi.hu/en/filming-in-hungary/hungarian-film-incentive",
        source_description="NFI Hungary — Hungarian Film Incentive",
        clause_reference="Act II of 2004 on Motion Picture (Hungarian Motion Picture Act)",
        notes="30% indirect subsidy on qualifying Hungarian spend (effectively a cash rebate via tax mechanism). "
              "No minimum spend or total budget threshold. "
              "Requires Hungarian co-producer or service company. Cultural test applies (50/100 points).",
        cultural_test_required=True,
        cultural_test_min_score=50,
        cultural_test_total_score=100,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # POLAND
    # -------------------------------------------------------------------------
    inc(
        name="Poland Cash Rebate Programme",
        country_code="PL",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=15_000_000,
        max_cap_currency="PLN",
        min_qualifying_spend=1_000_000,
        min_qualifying_spend_documentary=500_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://pisf.pl/en/aktualnosci/the-polish-30-cash-rebate-scheme-is-active-now/",
        source_description="Polish Film Institute — Cash Rebate scheme",
        notes="30% rebate on eligible Polish expenditure. Max PLN 15M/project. "
              "Min PLN 1M qualifying Polish spend (PLN 500k for documentaries). "
              "Cultural test required (50/100 points: cultural content, creative talent, production criteria).",
        cultural_test_required=True,
        cultural_test_min_score=50,
        cultural_test_total_score=100,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # CROATIA
    # -------------------------------------------------------------------------
    inc(
        name="Croatia Cash Rebate for Film and TV",
        country_code="HR",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        min_qualifying_spend=150_000,
        min_qualifying_spend_documentary=66_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.havc.hr/eng/film-incentives/cash-rebate",
        source_description="Croatian Audiovisual Centre — Cash Rebate programme",
        notes="25% cash rebate on qualifying Croatian expenditure. Additional 5% for productions promoting Croatian culture "
              "(up to 30% total). Min €150k qualifying spend (€66k for documentaries). "
              "Cultural test applies (12/34 points, min 4 per category).",
        cultural_test_required=True,
        cultural_test_min_score=12,
        cultural_test_total_score=34,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # ICELAND
    # -------------------------------------------------------------------------
    inc(
        name="Iceland Film Reimbursement",
        country_code="IS",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.government.is/topics/business-and-industry/creative-industries/film-reimbursement-of-production-cost/",
        source_description="Government of Iceland — Film Reimbursement",
        clause_reference="Act No. 43/1999 on Incentives for Initial Investments in Iceland (as amended)",
        notes="25% reimbursement of production costs incurred in Iceland. "
              "No minimum spend threshold. Applied for via Icelandic Film Centre.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # NORWAY
    # -------------------------------------------------------------------------
    inc(
        name="Norway Incentive Scheme for International Film and TV",
        country_code="NO",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=50_000_000,
        max_cap_currency="NOK",
        min_qualifying_spend=4_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.nfi.no/en/funding-schemes/insentiv/the-norwegian-film-production-incentive",
        source_description="Norwegian Film Institute — Norwegian Film Production Incentive",
        min_total_budget=25_000_000,
        min_total_budget_documentary=10_000_000,
        notes="25% cash rebate on qualifying Norwegian expenditure. Max NOK 50M/project. "
              "Min NOK 4M spend in Norway. Min total budget NOK 25M (features), NOK 10M (docs/per episode drama). "
              "Min 30% non-Norwegian financing required. "
              "Cultural test: 20/51 points (min 4 from Part 1 — cultural content).",
        cultural_test_required=True,
        cultural_test_min_score=20,
        cultural_test_total_score=51,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # DENMARK
    # -------------------------------------------------------------------------
    inc(
        name="Denmark Production Rebate",
        country_code="DK",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=20_000_000,
        max_cap_currency="DKK",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.dfi.dk/en/english/news/political-agreement-has-been-reached-danish-production-rebate-films-and-series",
        source_description="Danish Film Institute — Political agreement on Danish Production Rebate; administered by Slots- og Kulturstyrelsen",
        notes="25% rebate on qualifying Danish production expenditure. "
              "Annual fund DKK 125M (DKK 100M live-action/docs, DKK 25M animation). Cap DKK 20M per production. "
              "Effective 1 January 2026. Two application rounds per year. "
              "Production and culture test applies (rewards shooting days in Denmark, use of Danish talent). "
              "Administered by Slots- og Kulturstyrelsen; promoted internationally by DFI.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Denmark West Danish Film Fund",
        country_code="DK",
        region="West Denmark",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=7_500_000,
        max_cap_currency="DKK",
        eligible_formats=["feature_fiction", "documentary", "series"],
        source_url="https://www.filmpuljen.dk",  # West Danish Film Fund
        source_description="West Danish Film Fund — production support",
        notes="Regional grant for productions shooting in Western Denmark. "
              "Max DKK 7.5M per project. Competitive application.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SWEDEN
    # -------------------------------------------------------------------------
    inc(
        name="Sweden Film Production Rebate",
        country_code="SE",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=50_000_000,
        max_cap_currency="SEK",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.filminstitutet.se/en/funding/production-rebate/",
        source_description="Swedish Film Institute — Production Rebate",
        notes="25% rebate on qualifying Swedish expenditure. Max SEK 50M/project. "
              "Applied via Swedish Film Institute. Available from 2025.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # LUXEMBOURG
    # -------------------------------------------------------------------------
    inc(
        name="Luxembourg Film Fund (FLFA)",
        country_code="LU",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=3_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://filmfund.lu/en/funding",
        source_description="Film Fund Luxembourg — Production support",
        notes="Selective grant funding for coproductions with Luxembourg participation. "
              "Max €3M per project. Requires Luxembourg coproducer and significant Luxembourg spend. "
              "Luxembourg also offers a certificate for audiovisual investment (CIAV) tax shelter.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # CANADA
    # -------------------------------------------------------------------------
    inc(
        name="Canada CPTC (Canadian Film or Video Production Tax Credit)",
        country_code="CA",
        incentive_type="tax_credit",
        rebate_percent=25.0,
        rebate_applies_to="labour_only",
        labour_fraction=0.6,
        local_crew_min_percent=50.0,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/corporations/business-tax-credits/film-video-production-tax-credit.html",
        source_description="CRA — Canadian Film or Video Production Tax Credit",
        clause_reference="s.125.4, Income Tax Act (Canada)",
        notes="25% of qualified Canadian labour expenditure; labour capped at 60% of production costs per Income Tax Act. "
              "Requires Canadian content certification (CAVCO). Provincial credits are separate and stackable.",
        last_verified="2025-03",
    ),
    inc(
        name="Canada FISTC (Film or Video Production Services Tax Credit)",
        country_code="CA",
        incentive_type="tax_credit",
        rebate_percent=16.0,
        rebate_applies_to="labour_only",
        labour_fraction=0.6,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/corporations/business-tax-credits/film-video-production-services-tax-credit.html",
        source_description="CRA — Film or Video Production Services Tax Credit",
        clause_reference="s.125.5, Income Tax Act (Canada)",
        notes="16% of qualified Canadian labour expenditure for foreign (service) productions. "
              "No Canadian content requirement (unlike CPTC). Labour capped at 60% per Income Tax Act. Provincial credits may stack.",
        local_producer_required=False,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # AUSTRALIA
    # -------------------------------------------------------------------------
    inc(
        name="Australia Location Offset",
        country_code="AU",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        max_cap_currency="AUD",
        min_qualifying_spend=15_000_000,
        eligible_formats=["feature_fiction", "documentary", "series"],
        source_url="https://www.screenaustralia.gov.au/funding-and-support/producer-offset/location-and-pdv-offsets",
        source_description="Screen Australia — Location Offset",
        clause_reference="s.376-15, Income Tax Assessment Act 1997 (Cth)",
        notes="30% of qualifying Australian production expenditure (QAPE). "
              "Min AUD $15M QAPE (lowered from $20M, retrospective to July 2023). "
              "Lower thresholds for TV series. Requires Australian co-producer or approved co-production.",
        last_verified="2025-03",
    ),
    inc(
        name="Australia Producer Offset",
        country_code="AU",
        incentive_type="tax_credit",
        rebate_percent=40.0,
        max_cap_currency="AUD",
        eligible_formats=["feature_fiction", "documentary"],
        conditional_rates=[
            {"condition": "format_eq", "format": "documentary", "rate": 30.0,
             "note": "30% for documentary and other non-theatrical formats (40% for feature films). Updated July 2021."}
        ],
        source_url="https://www.screenaustralia.gov.au/funding-and-support/producer-offset",
        source_description="Screen Australia — Producer Offset",
        clause_reference="s.376-55, Income Tax Assessment Act 1997 (Cth)",
        notes="40% of qualifying Australian production expenditure for feature films; 30% for documentary and other formats "
              "(increased from 20% in July 2021). "
              "Requires significant Australian content (SAC test — holistic assessment, not points-based). "
              "Must be an official Australian production or coproduction.",
        cultural_test_required=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # NEW ZEALAND
    # -------------------------------------------------------------------------
    inc(
        name="New Zealand Screen Production Grant (International)",
        country_code="NZ",
        incentive_type="cash_rebate",
        rebate_percent=20.0,
        max_cap_currency="NZD",
        min_qualifying_spend=15_000_000,
        eligible_formats=["feature_fiction", "series", "animation"],
        source_url="https://www.nzfilm.co.nz/incentives-co-productions/nzspg-international",
        source_description="NZFC — New Zealand Screen Production Grant (International)",
        clause_reference="New Zealand Film Commission Act 1978, s.18(2)",
        notes="20% cash grant on qualifying NZ expenditure. Additional 5% uplift possible (total 25%). "
              "Min NZD $15M QNZPE for feature films. "
              "Significant economic benefit test applies.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SOUTH KOREA
    # -------------------------------------------------------------------------
    inc(
        name="South Korea Location Incentive (KOFIC)",
        country_code="KR",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=3_000_000_000,
        max_cap_currency="KRW",
        min_qualifying_spend=400_000_000,
        min_spend_currency="KRW",
        min_shoot_days=5,
        eligible_formats=["feature_fiction", "series", "animation", "documentary"],
        source_url="http://www.koreanfilm.or.kr/eng/coProduction/locIncentive.jsp",
        source_description="KOFIC 2026 — Foreign Audiovisual Production Incentive",
        notes="25% cash rebate on QPE in Korea. Min KRW 400M spend and 5 shoot days. "
              "Post-production only projects eligible for 15% rebate. 2026 fund includes 20% co-production quota.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # SOUTH AFRICA
    # -------------------------------------------------------------------------
    inc(
        name="South Africa Foreign Film and Television Production Incentive",
        country_code="ZA",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=50_000_000,
        max_cap_currency="ZAR",
        min_qualifying_spend=12_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.thedtic.gov.za/financial-and-non-financial-support/incentives/film-incentive/foreign-film-and-television-production-and-post-production-incentive-foreign-film/",
        source_description="DTIC — Foreign Film and Television Production and Post-Production Incentive",
        notes="25% rebate on qualifying South African production expenditure. "
              "Min ZAR 12M qualifying spend. Max ZAR 50M per project. "
              "Post-production only: 25% of qualifying SA post spend, min ZAR 1.5M.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # COLOMBIA
    # -------------------------------------------------------------------------
    inc(
        name="Colombia Film Incentive",
        country_code="CO",
        incentive_type="cash_rebate",
        rebate_percent=40.0,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.proimagenescolombia.com/secciones/proimagenes/interna.php?nt=28&lang=en",
        source_description="Proimágenes Colombia — Audiovisual Incentive",
        clause_reference="Ley 1556/2012 (Ley de Filmación de Colombia)",
        notes="40% cash rebate on qualifying Colombian spend for audiovisual services; "
              "20% on logistics spending. Requires Filming Colombia Commission certificate. "
              "Available to foreign and coproductions.",
        local_producer_required=False,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # MOROCCO
    # -------------------------------------------------------------------------
    inc(
        name="Morocco Film Incentive",
        country_code="MA",
        incentive_type="cash_rebate",
        rebate_percent=20.0,
        eligible_formats=["feature_fiction", "series"],
        source_url="https://www.ccm.ma/en/filming-in-morocco/incentives/",
        source_description="CCM — Morocco Audiovisual Incentive",
        notes="20% cash rebate on qualifying Moroccan expenditure for foreign productions. "
              "Higher rates possible for large-scale productions. "
              "Administered by Centre Cinématographique Marocain (CCM).",
        local_producer_required=False,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # GREECE
    # -------------------------------------------------------------------------
    inc(
        name="Greece Cash Rebate Programme",
        country_code="GR",
        incentive_type="cash_rebate",
        rebate_percent=40.0,
        max_cap_amount=5_000_000,
        min_qualifying_spend=100_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.ekkomed.gr/audiovisual-production-invest/cash-rebate-film-tv-animations-documentaries/",
        source_description="EKOME — Greek Cash Rebate Programme",
        clause_reference="Law 5105/2024 (Creative Greece Act, Section C)",
        notes="40% cash rebate on qualifying Greek expenditure. Max €5M per project. "
              "Min €100k qualifying spend. Among the highest rebate rates in Europe.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # PORTUGAL
    # -------------------------------------------------------------------------
    inc(
        name="Portugal SCRI.PT Film Production Incentive",
        country_code="PT",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=4_000_000,
        min_qualifying_spend=500_000,
        min_qualifying_spend_documentary=250_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.ica-ip.pt/en/1-4-5/cash-rebate/",
        source_description="ICA — Portugal SCRI.PT programme (Decree-Law 57/2026, replacing former Cash Rebate & Cash Refund)",
        notes="25-30% cash rebate on qualifying Portuguese expenditure (rate depends on cultural test score). "
              "Max €4M per project. Min €500k qualifying spend (€250k for documentaries). "
              "From Feb 2026, SCRI.PT replaces the former Cash Rebate and Cash Refund as a single scheme. "
              "Managed by ICA (Portuguese Film and Audiovisual Institute).",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # FINLAND
    # -------------------------------------------------------------------------
    inc(
        name="Finland Production Incentive",
        country_code="FI",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=3_000_000,
        min_qualifying_spend=150_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.businessfinland.fi/en/for-finnish-customers/services/funding/cash-rebate",
        source_description="Business Finland — Audiovisual Production Incentive",
        notes="25% cash rebate on qualifying Finnish expenditure. Max €3M per project. "
              "Min €150k eligible Finnish spend. Available to Finnish and foreign productions.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # AUSTRIA
    # -------------------------------------------------------------------------
    inc(
        name="Austria FISA+ (Film Location Austria Incentive)",
        country_code="AT",
        incentive_type="grant",
        rebate_percent=30.0,
        max_cap_amount=5_000_000,
        min_qualifying_spend=150_000,
        min_qualifying_spend_documentary=100_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        conditional_rates=[
            {"condition": "green_production", "rate": 35.0,
             "note": "Additional 5% green bonus (total 35%) for productions meeting environmental sustainability requirements."}
        ],
        source_url="https://www.filminaustria.com/en/funding/fisaplus/",
        source_description="Film in Austria — FISA+ programme",
        notes="30% automatic grant on qualifying Austrian production expenditure, plus 5% green bonus (total 35%). "
              "Max €5M per film, €7.5M per series. Min €150k qualifying spend (€100k for docs). "
              "2026 annual budget: €55M (reduced from €80M in 2025). "
              "Cultural test applies (33/66 points for international co-productions). Stackable with regional funds.",
        cultural_test_required=True,
        cultural_test_min_score=33,
        cultural_test_total_score=66,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # ROMANIA
    # -------------------------------------------------------------------------
    inc(
        name="Romania Cash Rebate Programme",
        country_code="RO",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=None,
        min_qualifying_spend=100_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.cnc.gov.ro/en/cash-rebate/",
        source_description="CNC Romania — Revamped Cash Rebate Programme (2024)",
        notes="30% cash rebate on qualifying Romanian expenditure (revamped 2024, relaunched after "
              "two-year pause). Min €100k qualifying spend. Annual programme budget up to €55M. "
              "Plans to increase to 40% in 2026 to match regional competitors. "
              "Administered by CNC Romania.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # BULGARIA
    # -------------------------------------------------------------------------
    inc(
        name="Bulgaria Cash Rebate Programme",
        country_code="BG",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=5_000_000,
        min_qualifying_spend=250_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.nfc.bg/en/cash-rebate/",
        source_description="Bulgarian National Film Center — Cash Rebate",
        notes="25% cash rebate on qualifying Bulgarian expenditure. "
              "Max €5M per project (raised from €1M). Min €250k qualifying spend. "
              "Annual programme budget €10.3M. "
              "Administered by Bulgarian National Film Center.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # ESTONIA
    # -------------------------------------------------------------------------
    inc(
        name="Estonia Cash Rebate for Film Production",
        country_code="EE",
        incentive_type="cash_rebate",
        rebate_percent=40.0,
        max_cap_amount=2_000_000,
        min_qualifying_spend=200_000,
        min_qualifying_spend_documentary=80_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://filmestonia.eu/film-estonia-funding/guidelines-and-how-to-apply/",
        source_description="Film Estonia — Cash Rebate programme (raised to 40% in March 2026)",
        notes="40% cash rebate on qualifying Estonian expenditure (raised from 30% in March 2026). "
              "Max €2M per project. Min €200k qualifying spend (€80k for documentaries). "
              "Eligibility based on Estonian crew involvement and spend criteria.",
        cultural_test_required=False,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # LATVIA
    # -------------------------------------------------------------------------
    inc(
        name="Latvia Cash Rebate for Film Production",
        country_code="LV",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=None,
        min_qualifying_spend=150_000,
        min_qualifying_spend_documentary=70_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://nkc.gov.lv/en/support/cash-rebate/",
        source_description="National Film Centre of Latvia — Cash Rebate",
        notes="20-30% cash rebate on qualifying Latvian expenditure (25% if story set in/features Riga, 20% otherwise). "
              "Min €150k qualifying spend (€70k for documentaries). No per-project cap but subject to annual budget. "
              "No formal cultural test — rate varies by Riga connection.",
        cultural_test_required=False,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # LITHUANIA
    # -------------------------------------------------------------------------
    inc(
        name="Lithuania Tax Incentive for Film Production",
        country_code="LT",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        max_cap_amount=None,
        min_qualifying_spend=43_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.lkc.lt/en/film-tax-incentive/",
        source_description="Lithuanian Film Centre — Film Tax Incentive",
        notes="30% tax credit on qualifying Lithuanian expenditure. "
              "Min €43k qualifying spend. No per-project cap. "
              "Cultural content test: must meet 2 of 4 criteria (Lithuanian/European themes, social events, "
              "notable figures, literary works). Administered by Lithuanian Film Centre.",
        cultural_test_required=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SLOVAKIA
    # -------------------------------------------------------------------------
    inc(
        name="Slovakia Cash Rebate Programme",
        country_code="SK",
        incentive_type="cash_rebate",
        rebate_percent=33.0,
        max_cap_amount=10_000_000,
        min_qualifying_spend=150_000,
        min_qualifying_spend_documentary=50_000,
        min_spend_currency="EUR",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.sfu.sk/en/cash-rebate",
        source_description="Slovak Audiovisual Fund — Cash Rebate programme",
        notes="33% cash rebate on qualifying Slovak expenditure. "
              "Max €10M per project (€4M if cultural test score <32/48). "
              "Min €150k qualifying spend (€50k for documentaries). "
              "Cultural test required (24/48 points).",
        cultural_test_required=True,
        cultural_test_min_score=24,
        cultural_test_total_score=48,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SLOVENIA
    # -------------------------------------------------------------------------
    inc(
        name="Slovenia Cash Rebate for Film and TV",
        country_code="SI",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=2_500_000,
        min_qualifying_spend=150_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.film-sklad.si/en/incentives/cash-rebate",
        source_description="Slovenian Film Centre — Cash Rebate",
        notes="25% cash rebate on qualifying Slovenian expenditure. "
              "Max €2.5M per project. Min €150k qualifying spend. "
              "Additional 5% bonus for Slovenian minority coproductions (up to 30%).",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SERBIA
    # -------------------------------------------------------------------------
    inc(
        name="Serbia Cash Rebate for Film and TV",
        country_code="RS",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=None,
        min_qualifying_spend=300_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        conditional_rates=[
            {"condition": "budget_gte", "threshold": 5_000_000, "rate": 30.0,
             "note": "Enhanced 30% rebate for productions spending ≥€5M locally in Serbia."},
        ],
        source_url="https://www.fcs.rs/en/incentives/cash-rebate/",
        source_description="Film Center Serbia — Cash Rebate Programme",
        notes="25% cash rebate on qualifying Serbian expenditure (30% for ≥€5M local spend). "
              "Min €300k qualifying spend. No per-project cap. "
              "20% for special-purpose films.",
        local_producer_required=False,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # MALTA
    # -------------------------------------------------------------------------
    inc(
        name="Malta Cash Rebate Programme",
        country_code="MT",
        incentive_type="cash_rebate",
        rebate_percent=40.0,
        max_cap_amount=6_000_000,
        min_qualifying_spend=100_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.maltafilmcommission.com/incentives/",
        source_description="Malta Film Commission — Cash Rebate",
        notes="40% cash rebate on qualifying Maltese expenditure (base 30% + up to 10% bonus). "
              "Max €6M per project. Min €100k qualifying spend. "
              "2% additional for productions set in Malta; 5% for off-peak production; "
              "additional for Maltese creative talent. One of the highest effective rates in Europe.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SWITZERLAND
    # -------------------------------------------------------------------------
    inc(
        name="Switzerland FOCI (Film Location Switzerland)",
        country_code="CH",
        incentive_type="cash_rebate",
        rebate_percent=20.0,
        max_cap_amount=2_500_000,
        max_cap_currency="CHF",
        min_qualifying_spend=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.bak.admin.ch/bak/en/home/cultural-creation/film/film-location-switzerland.html",
        source_description="Federal Office of Culture — Film Location Switzerland (FOCI)",
        notes="20% cash rebate on qualifying Swiss expenditure. "
              "Max CHF 2.5M per project. Min CHF 200k qualifying spend. "
              "Productions must have Swiss co-producer or service producer.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # CYPRUS
    # -------------------------------------------------------------------------
    inc(
        name="Cyprus Cash Rebate Scheme for Film and TV",
        country_code="CY",
        incentive_type="cash_rebate",
        rebate_percent=35.0,
        max_cap_amount=500_000,
        min_qualifying_spend=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.invest-cyprus.com/film-production-incentives",
        source_description="Invest Cyprus — Film Production Cash Rebate",
        notes="35% cash rebate on qualifying Cypriot expenditure. "
              "Max €500k per project. Min €200k qualifying spend. "
              "Additional 5% bonus for productions promoting Cyprus as a filming destination.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # MONTENEGRO
    # -------------------------------------------------------------------------
    inc(
        name="Montenegro Cash Rebate for Film Production",
        country_code="ME",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=500_000,
        min_qualifying_spend=50_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.fccg.me/en/incentives",
        source_description="Film Centre of Montenegro — Cash Rebate",
        notes="25% cash rebate on qualifying Montenegrin expenditure. "
              "Max €500k per project. Min €50k qualifying spend. "
              "Competitive grant system, subject to annual budget.",
        local_producer_required=False,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # NORTH MACEDONIA
    # -------------------------------------------------------------------------
    inc(
        name="North Macedonia Cash Rebate for Film and TV",
        country_code="MK",
        incentive_type="cash_rebate",
        rebate_percent=20.0,
        min_qualifying_spend=100_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.filmfund.gov.mk/en/incentives/",
        source_description="North Macedonia Film Agency — Cash Rebate",
        notes="20% cash rebate on qualifying North Macedonian expenditure. "
              "Min €100k qualifying spend. Emerging incentive aimed at attracting "
              "international productions to the Balkans.",
        local_producer_required=False,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # GEORGIA
    # -------------------------------------------------------------------------
    inc(
        name="Georgia Cash Rebate for Film Production",
        country_code="GE",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_amount=1_000_000,
        max_cap_currency="USD",
        min_qualifying_spend=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://gnfc.ge/en/cash-rebate/",
        source_description="Georgian National Film Center — Cash Rebate",
        notes="20-25% cash rebate on qualifying Georgian expenditure. "
              "Max approximately $1M per project. Min $200k qualifying spend. "
              "Rate depends on total spend level.",
        local_producer_required=False,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # TURKEY
    # -------------------------------------------------------------------------
    inc(
        name="Turkey Film Production Incentive",
        country_code="TR",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        min_qualifying_spend=500_000,
        max_cap_currency="TRY",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.filminginturkiye.com.tr/en/incentives/",
        source_description="Filming in Türkiye — Cash Rebate Incentive (Law 5224)",
        clause_reference="Law 5224 on Evaluation, Classification, and Support of Cinema Films",
        notes="Up to 30% cash rebate on all eligible expenses incurred in Turkey. "
              "Approved by Ministry of Culture and Tourism. "
              "Cultural test applies (content, Turkish crew, local infrastructure).",
        cultural_test_required=True,
        cultural_test_min_score=50,
        cultural_test_total_score=100,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # ALBANIA
    # -------------------------------------------------------------------------
    inc(
        name="Albania Film Production Incentive",
        country_code="AL",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        min_qualifying_spend=50_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.nationalfilmcenter.gov.al/en/incentive/",
        source_description="Albanian National Center of Cinematography — Production Incentive",
        notes="Up to 25% cash rebate on qualifying Albanian expenditure. "
              "Emerging incentive scheme. Min €50k qualifying spend. "
              "Subject to annual programme budget.",
        local_producer_required=False,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # UKRAINE
    # -------------------------------------------------------------------------
    inc(
        name="Ukraine Cash Rebate for Audiovisual Production",
        country_code="UA",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_currency="USD",
        min_qualifying_spend=250_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://usfa.gov.ua/en/subsidies",
        source_description="Ukrainian State Film Agency — Subsidies & Cash Rebate",
        notes="25% base cash rebate on qualifying Ukrainian expenditure, +5% uplift for projects "
              "foregrounding Ukrainian culture (up to 30% total). Min $250k qualifying spend. "
              "€50M cultural fund announced. Note: programme availability subject to wartime conditions.",
        local_producer_required=False,
        last_verified="2026-03",
    ),

    # =========================================================================
    # EUROPEAN REGIONAL FUNDS
    # =========================================================================

    # -------------------------------------------------------------------------
    # GERMANY — Länder Film Funds
    # -------------------------------------------------------------------------
    inc(
        name="Medienboard Berlin-Brandenburg",
        country_code="DE",
        region="Berlin-Brandenburg",
        incentive_type="grant",
        rebate_percent=30.0,
        max_cap_amount=1_500_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.medienboard.de/en/funding/film",
        source_description="Medienboard Berlin-Brandenburg — Film Funding",
        notes="Selective grant (conditionally repayable loan). Up to 50% of eligible costs "
              "(typical awards ~30%). Requires 150% regional spend effect in Berlin-Brandenburg. "
              "One of Germany's largest regional film funds. Annual budget ~€30M. "
              "Stackable with DFFF/GMPF.",
        stacking_allowed=True,
        last_verified="2026-03",
    ),
    inc(
        name="FFF Bayern (FilmFernsehFonds Bayern)",
        country_code="DE",
        region="Bavaria",
        incentive_type="grant",
        rebate_percent=30.0,
        max_cap_amount=3_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.fff-bayern.de/en/funded-areas/production-feature-films/",
        source_description="FFF Bayern — Production Feature Films",
        notes="Conditionally repayable loan up to 30% of eligible costs, max €3M for features "
              "(€2M for international co-productions, €1M for series). "
              "Requires 150% regional spend effect in Bavaria. "
              "Germany's largest regional fund (~€40M annual budget). "
              "Stackable with DFFF/GMPF.",
        stacking_allowed=True,
        last_verified="2026-03",
    ),
    inc(
        name="Film- und Medienstiftung NRW",
        country_code="DE",
        region="North Rhine-Westphalia",
        incentive_type="grant",
        rebate_percent=30.0,
        max_cap_amount=2_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.filmstiftung.de/en/funding/feature_film/production/",
        source_description="Film- und Medienstiftung NRW — Feature Film Production",
        notes="Conditionally repayable loan, up to 50% of eligible costs (typical ~30%). "
              "At least 150% of the grant must be spent in NRW. "
              "Recent awards up to €2M for high-end series, ~€1M for features. "
              "One of Germany's top three regional funds. "
              "Stackable with DFFF/GMPF.",
        stacking_allowed=True,
        last_verified="2026-03",
    ),
    inc(
        name="MOIN Film Fund Hamburg Schleswig-Holstein",
        country_code="DE",
        region="Hamburg / Schleswig-Holstein",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://moin-filmfoerderung.de/en/fundings",
        source_description="MOIN Filmförderung Hamburg Schleswig-Holstein — Funding",
        notes="Selective grant (formerly FFHSH, rebranded as MOIN). "
              "Supports cinema films, high-end series, and innovative formats. "
              "High-end: budgets over €2.5M; Director's Cut: under €2.5M. "
              "Regional spend requirement applies.",
        last_verified="2025-03",
    ),
    inc(
        name="MFG Filmförderung Baden-Württemberg",
        country_code="DE",
        region="Baden-Württemberg",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://film.mfg.de/foerderungen/produktion/",
        source_description="MFG Filmförderung Baden-Württemberg — Produktion",
        notes="Selective grant. Recent awards typically €400k-€550k per feature. "
              "Annual budget ~€18M total across all programmes. "
              "Regional spend requirement applies. Ludwigsburg studio base.",
        last_verified="2025-03",
    ),
    inc(
        name="HessenFilm und Medien",
        country_code="DE",
        region="Hesse",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=500_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.hessenfilm.de/en/funding",
        source_description="HessenFilm und Medien — Funding",
        notes="Grant up to €500k per project (up to €1M in exceptional cases). "
              "For productions with total budget up to €5M. "
              "Regional spend: 100-125% of grant. Requires German co-producer.",
        last_verified="2025-03",
    ),
    inc(
        name="MDM Mitteldeutsche Medienförderung",
        country_code="DE",
        region="Saxony / Saxony-Anhalt / Thuringia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.mdm-online.de/index.php?id=foerderung",
        source_description="MDM — Mitteldeutsche Medienförderung Förderung",
        notes="Selective grant. Covers Saxony, Saxony-Anhalt, and Thuringia. "
              "Up to €300k for debut features, higher amounts possible. "
              "Regional spend requirement applies. Guidelines effective 1 Jan 2024.",
        last_verified="2025-03",
    ),
    inc(
        name="Nordmedia Film- und Mediengesellschaft",
        country_code="DE",
        region="Lower Saxony / Bremen",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.english.nordmedia.de/",
        source_description="Nordmedia — Film and Media Funding",
        notes="Selective grant. Covers Lower Saxony and Bremen. "
              "Annual budget ~€10M. Up to 60% of German production costs for co-productions. "
              "Regional spend requirement applies.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # FRANCE — Regional Funds
    # -------------------------------------------------------------------------
    inc(
        name="Île-de-France Film Commission Fund",
        country_code="FR",
        region="Île-de-France",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.iledefrance.fr/aides-et-appels-a-projets/aide-a-la-production-audiovisuelle-et-cinematographique",
        source_description="Région Île-de-France — Aide à la production cinématographique",
        notes="Selective regional grant for productions shooting in the Paris/Île-de-France region. "
              "Competitive application; exact max varies by call — check règlement PDF for current limits. "
              "Must demonstrate significant regional economic impact.",
        last_verified="2025-03",
    ),
    inc(
        name="Région Sud (PACA) Film Fund",
        country_code="FR",
        region="Provence-Alpes-Côte d'Azur",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.maregionsud.fr/aides-et-appels-a-projets/culture/cinema-et-audiovisuel",
        source_description="Région Sud — Aide à la production audiovisuelle",
        notes="Selective grant; variable amount per project. "
              "Requires 125% regional spend multiplier. Covers Marseille, Nice, Cannes corridor.",
        last_verified="2025-03",
    ),
    inc(
        name="Auvergne-Rhône-Alpes Cinéma",
        country_code="FR",
        region="Auvergne-Rhône-Alpes",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.auvergnerhonealpes-cinema.fr/aides/",
        source_description="Auvergne-Rhône-Alpes Cinéma — Production Support",
        notes="Selective grant; average co-production investment ~€220k, 120% regional spend required. "
              "Covers Lyon, Grenoble, Clermont-Ferrand corridor.",
        last_verified="2025-03",
    ),
    inc(
        name="Nouvelle-Aquitaine Film Fund",
        country_code="FR",
        region="Nouvelle-Aquitaine",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://alca-nouvelle-aquitaine.fr/cinema-audiovisuel/aides-a-la-production",
        source_description="ALCA Nouvelle-Aquitaine — Aide à la production",
        notes="Selective grant; variable amount per project — ALCA manages the fund. "
              "Covers Bordeaux, Limoges, Poitiers area. Requires significant regional shooting and spend.",
        last_verified="2025-03",
    ),
    inc(
        name="Occitanie Films Fund",
        country_code="FR",
        region="Occitanie",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=250_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.occitanie-films.fr/aides/aide-a-la-production/",
        source_description="Occitanie Films — Aide à la production",
        notes="Selective grant: up to €250k for fiction/animation series, €120k for single fiction works. "
              "Covers Toulouse and Montpellier corridor.",
        last_verified="2025-03",
    ),
    inc(
        name="Bretagne FACCA Film Fund",
        country_code="FR",
        region="Brittany",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=300_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://cinema.bretagne.bzh/en/financements/aides-cinema/",
        source_description="Bretagne Cinéma — FACCA Production Fund",
        notes="FACCA fund: up to €300k for features/series, €150k for single programs. "
              "Total annual budget ~€4.09M. 160% regional spend required.",
        last_verified="2025-03",
    ),
    inc(
        name="Hauts-de-France Film Fund",
        country_code="FR",
        region="Hauts-de-France",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.pictanovo.com/aides-financieres/",
        source_description="Pictanovo / Hauts-de-France — Aide à la production",
        notes="Selective grant; Pictanovo manages €8.6M annual budget across 10 funding categories. "
              "Per-project max varies by category. Covers Lille, Amiens corridor.",
        last_verified="2025-03",
    ),
    inc(
        name="Grand Est Film Fund",
        country_code="FR",
        region="Grand Est",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=300_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://aides-territoires.beta.gouv.fr/aides/82ee-dispositifs-cinema-audiovisuel-grand-est/",
        source_description="Région Grand Est — Dispositifs Cinéma Audiovisuel",
        notes="Feature production: €100k-€300k (depending on territorial integration), fiction series up to €250k. "
              "Total fund ~€3.67M + €570k Plato device. Covers Strasbourg, Metz, Nancy. "
              "Cross-border potential with Germany, Luxembourg, Belgium.",
        last_verified="2025-03",
    ),
    inc(
        name="Normandie Images Film Fund",
        country_code="FR",
        region="Normandy",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://normandieimages.fr/creation-production/fonds-d-aides/14-creation-et-production/fonds-d-aide/32-production-long-metrage",
        source_description="Normandie Images — Aide à la production long métrage",
        notes="Features: €100k-€200k; docs (TV): €15k-€50k. 160% regional spend required.",
        last_verified="2025-03",
    ),
    inc(
        name="Corsica Film Fund",
        country_code="FR",
        region="Corsica",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=200_000,
        eligible_formats=["feature_fiction", "documentary", "series"],
        source_url="https://www.isula.corsica/culture/REGLEMENT-DES-AIDES-POUR-LA-CULTURE-SECTEUR-AUDIOVISUEL-ET-CINEMA_a5029.html",
        source_description="Collectivité de Corse — Règlement des aides audiovisuel et cinéma",
        notes="Average feature production grant ~€181k. Total fund ~€3.43M. "
              "20% bonus for Corsican-language projects.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # ITALY — Regional Funds
    # -------------------------------------------------------------------------
    inc(
        name="Roma Lazio Film Commission Fund",
        country_code="IT",
        region="Lazio",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=750_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.rlfcindustry.it/",
        source_description="Roma Lazio Film Commission — Industry",
        notes="Up to €500k for film, €750k for audiovisual works. "
              "New €10M annual fund for international co-productions (confirmed to 2027). "
              "30-45% of eligible costs. Stackable with the national 40% tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Lombardy for Cinema Fund",
        country_code="IT",
        region="Lombardy",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=300_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.miamarket.it/en/lombardia-for-cinema-second-edition-of-the-e3-million-funding-scheme/",
        source_description="Lombardia for Cinema — €3M Funding Scheme",
        notes="€3M annual fund. Max €250k for fiction features, €300k for fiction series, "
              "€75k for docs, €150k for doc series. "
              "Requires shooting in Lombardy. Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Sicilia Film Commission Fund",
        country_code="IT",
        region="Sicily",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=1_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.siciliafilmcommission.org/en/",
        source_description="Sicilia Film Commission — Production Fund 2025-2027",
        notes="Non-repayable grant. Up to €1M for fiction film/TV, €200k for documentaries, "
              "€40k for shorts. €10.8M total fund. Must be shot in Sicily. "
              "One of Italy's largest regional funds. Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Film Commission Torino Piemonte — FIP",
        country_code="IT",
        region="Piedmont",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://filmitalia.org/en/filmcommission/28725/",
        source_description="Film Commission Torino Piemonte — FIP Investment",
        notes="FIP (Film Investimenti Piemonte) investment up to €200k (€100k for debuts). "
              "Requires shooting in Piedmont. Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Apulia Film Fund",
        country_code="IT",
        region="Apulia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=500_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.apuliafilmcommission.it/fondi/apulia-film-fund/",
        source_description="Apulia Film Commission — Apulia Film Fund 2025",
        notes="€5M annual fund. Max by category: €320k fiction, €450k series, €120k docs, "
              "€500k animation. One of Italy's most active regional funds. "
              "Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Emilia-Romagna Film Commission Fund",
        country_code="IT",
        region="Emilia-Romagna",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=250_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://cinema.emiliaromagnacultura.it/en/bando/call-for-applications-for-funding-for-the-production-of-audiovisual-works-by-national-and-international-companies/",
        source_description="Emilia-Romagna Film Commission — Production Call for Applications",
        notes="Grant up to €250k (Section A films), €150k (Section B), €50k (docs). "
              "Covers Bologna, Ravenna, Rimini. Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Toscana Film Commission Fund",
        country_code="IT",
        region="Tuscany",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=450_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.italiafilmservice.com/subsidies-et-finance/regional.html",
        source_description="Toscana Film Commission — Cinema Fund",
        notes="Grant up to €200k for first works, up to €450k for second works, "
              "€50k for documentaries. Requires shooting in Tuscany.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Veneto Film and Audiovisual Fund",
        country_code="IT",
        region="Veneto",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=75_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.italiafilmservice.com/subsidies-et-finance/regional.html",
        source_description="Veneto Film Commission — Film and Audiovisual Fund",
        notes="Grant up to €75k (6 weeks shooting) or €5k (1 week). "
              "Covers Venice, Padua, Verona. Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Campania Film Commission Fund",
        country_code="IT",
        region="Campania",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=250_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.italyformovies.it/news/detail/2530/campania-bando-a-sostegno-della-produzione-valorizzazione-e-fruizione-della-cultura-cinematografica-2025",
        source_description="Film Commission Regione Campania — Production Fund 2025",
        notes="Selective grant €25k–€250k depending on category and shooting days, max 50% of costs. "
              "Total annual budget ~€2M for production. Covers Naples, Amalfi Coast, Pompeii. "
              "Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Sardegna Film Commission — Large Production Fund",
        country_code="IT",
        region="Sardinia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=500_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.unicaradio.it/en/blog/2025/12/26/large-production-fund-1-million-to-support-made-in-sardinia-cinema/",
        source_description="Sardegna Film Commission — Large Production Fund 2025-2026",
        notes="Non-repayable grant up to €500k per project. Total fund ~€925k. "
              "Up to 50% of eligible expenses (de minimis/GBER). "
              "Must be shot in Sardinia. Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Calabria Film Commission Fund",
        country_code="IT",
        region="Calabria",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=500_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.calabriafilmcommission.it/bandi-avvisi/",
        source_description="Calabria Film Commission — Avviso pubblico produzioni",
        notes="Tiered grant: up to €500k (features/TV tier 1), €300k (tier 2), €200k (docs), €20k (shorts). "
              "160% regional spend required. Total fund ~€4M features + €1M docs/shorts. "
              "Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="FVG Film Commission Fund",
        country_code="IT",
        region="Friuli Venezia Giulia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=150_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.italiafilmservice.com/subsidies-et-finance/regional.html",
        source_description="FVG Film Commission — Film Fund",
        notes="Grant up to €150k. Covers Trieste area, cross-border with Slovenia. "
              "Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Trentino Film Fund",
        country_code="IT",
        region="Trentino",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=400_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.trentinofilmcommission.it/en/film-fund/",
        source_description="Trentino Film Commission — Film Fund",
        notes="Grant up to €400k for film/TV, €40k for docs/multimedia. "
              "Part of filming must be in Trentino. Min 150% local spend of grant amount. "
              "Min 20% local crew. Cross-border with Austria (Dolomites). "
              "Stackable with national tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SPAIN — Autonomous Community Funds
    # -------------------------------------------------------------------------
    inc(
        name="Spain — Navarre Tax Incentive (Foral Regime)",
        country_code="ES",
        region="Navarre",
        incentive_type="tax_credit",
        rebate_percent=45.0,
        max_cap_amount=5_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        conditional_rates=[
            {"condition": "format_eq", "format": "documentary", "rate": 50.0,
             "note": "50% rate for documentaries, animated films, and shorts (vs 45% general rate)."},
            {"condition": "format_eq", "format": "animation", "rate": 50.0,
             "note": "50% rate for animation (vs 45% general rate)."},
        ],
        source_url="https://investinnavarra.com/en/navarra-improves-the-tax-incentive-to-attract-new-audiovisual-productions/",
        source_description="Invest in Navarra — Audiovisual Tax Incentive",
        clause_reference="Art. 65, Foral Law 26/2016 (Navarre)",
        notes="45% tax deduction (general rate, improved from 35% in 2025). "
              "50% for animated films, shorts, documentaries. Max €5M deduction per production. "
              "At least 40% of deduction base must be spent in Navarre. "
              "Foral tax regime — independent of mainland Spain rates.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Basque Country Tax Incentive (Bizkaia Foral Regime)",
        country_code="ES",
        region="Basque Country",
        incentive_type="tax_credit",
        rebate_percent=60.0,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.bifilmcommission.com/tax-scheme/",
        source_description="Bilbao Bizkaia Film Commission — Tax Scheme (Norma Foral 9/2022)",
        notes="Up to 60% tax credit (+ 10% if Basque is source language = 70% max). "
              "Rates by Bizkaia spend: 60% if >50% in Bizkaia, 50% if 35-50%, 40% if 20-35%, "
              "35% base with no territoriality. No fixed per-production cap. "
              "Can offset 100% of corporate tax liability. One of Europe's highest rates.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Catalonia Film Fund (ICEC)",
        country_code="ES",
        region="Catalonia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=300_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://icec.gencat.cat/en/arees_actuacio/cinema_i_audiovisual/ajuts/",
        source_description="ICEC — Institut Català de les Empreses Culturals",
        notes="Selective grant up to €300k for productions shooting in Catalonia. "
              "Also benefits from national Spanish tax incentive (30%/25%). "
              "Barcelona is a major production hub.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Madrid Film Fund",
        country_code="ES",
        region="Madrid",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=250_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.comunidad.madrid/servicios/cultura/ayudas-sector-audiovisual",
        source_description="Comunidad de Madrid — Ayudas al sector audiovisual",
        notes="Selective grant for productions shooting in Madrid region. "
              "Max ~€250k. Also benefits from national Spanish tax incentive.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Andalusia Film Fund",
        country_code="ES",
        region="Andalusia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=300_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.andaluciafilm.com/en/incentives/",
        source_description="Andalucía Film Commission — Production Fund",
        notes="Selective grant up to €300k for productions shooting in Andalusia. "
              "Seville, Málaga, Almería (including Tabernas desert studios). "
              "Stackable with national Spanish tax incentive.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Galicia Film Fund (AGADIC)",
        country_code="ES",
        region="Galicia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.agadic.gal/lingua/es/audiovisual/axudas",
        source_description="AGADIC — Axencia Galega das Industrias Culturais",
        notes="Selective grant up to €200k for productions shooting in Galicia. "
              "Stackable with national incentive.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Balearic Islands Film Fund",
        country_code="ES",
        region="Balearic Islands",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.mallorcafilmcommission.net/en/incentives/",
        source_description="Mallorca Film Commission / IEB — Production Fund",
        notes="Selective grant for productions shooting in the Balearic Islands (Mallorca, Ibiza, Menorca). "
              "Stackable with national incentive.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Valencia Film Fund (IVC)",
        country_code="ES",
        region="Valencia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=250_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://ivc.gva.es/en/cinema/production-incentives",
        source_description="Institut Valencià de Cultura — Production Fund",
        notes="Selective grant up to €250k. Covers Valencia, Alicante, Ciudad de la Luz studios. "
              "Stackable with national Spanish tax incentive.",
        last_verified="2025-03",
    ),
    inc(
        name="Spain — Castilla y León Film Fund",
        country_code="ES",
        region="Castilla y León",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=150_000,
        eligible_formats=["feature_fiction", "documentary", "series"],
        source_url="https://www.jcyl.es/web/jcyl/Cultura/es/Plantilla100/1284802299615/_/_/_",
        source_description="Junta de Castilla y León — Ayudas a la producción audiovisual",
        notes="Selective grant up to €150k for productions shooting in Castilla y León.",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # UNITED KINGDOM — Nations / Regions
    # -------------------------------------------------------------------------
    inc(
        name="Screen Scotland Production Growth Fund",
        country_code="GB",
        region="Scotland",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=500_000,
        max_cap_currency="GBP",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.screen.scot/funding-and-support/funding/production-growth-fund",
        source_description="Screen Scotland — Production Growth Fund",
        notes="Grant £200k-£500k for productions shooting in Scotland. "
              "Min 10:1 Scottish spend ratio (e.g. £200k grant requires £2M Scottish spend). "
              "Annual budget £2M. Stackable with UK AVEC tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Ffilm Cymru Wales Production Fund",
        country_code="GB",
        region="Wales",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=600_000,
        max_cap_currency="GBP",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://ffilmcymruwales.com/funding-and-training/feature-film-production",
        source_description="Ffilm Cymru Wales — Feature Film Production Fund",
        notes="Up to £600k per project (£400k Creative Wales grant + £200k Ffilm Cymru lottery). "
              "Most awards £150k-£400k. Not more than 50% of total budget. "
              "Stackable with UK AVEC tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Northern Ireland Screen Fund",
        country_code="GB",
        region="Northern Ireland",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=800_000,
        max_cap_currency="GBP",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://northernirelandscreen.co.uk/funding/",
        source_description="Northern Ireland Screen — Funding",
        notes="Recoupable loan up to £800k (max 25% of overall budget). "
              "Production must have at least 65% financing in place. "
              "Belfast studios are major draw. Stackable with UK AVEC tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # BELGIUM — Communities
    # -------------------------------------------------------------------------
    inc(
        name="Wallimage Coproductions (Wallonia)",
        country_code="BE",
        region="Wallonia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        min_qualifying_spend=300_000,
        min_qualifying_spend_documentary=75_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.wallimage.be/en/services/wallimage-coproductions/",
        source_description="Wallimage — Coproductions",
        notes="Economic co-investment fund. €6.5M annual budget across all projects. "
              "Projects must have expenses over €300k (€75k for docs). "
              "Producers must have 30% financing secured before applying. "
              "Competitive allocation per session. Stackable with Belgian Tax Shelter.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Screen Flanders (VAF Economic Fund)",
        country_code="BE",
        region="Flanders",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=400_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.screenflanders.be/en/financing/screen-flanders/criteria",
        source_description="Screen Flanders — Criteria",
        notes="Repayable advance up to €400k per project. "
              "Min €250k eligible costs in Flanders. Min 100% spend of support in Flanders. "
              "50% of budget must be secured. Max 50% public funding (60% for EU co-productions). "
              "Stackable with Belgian Tax Shelter.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Centre du Cinéma — Fédération Wallonie-Bruxelles Film Fund",
        country_code="BE",
        region="Wallonia-Brussels Federation",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=500_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.audiovisuel.cfwb.be/aides/production/",
        source_description="Centre du Cinéma et de l'Audiovisuel (FWB) — Aide à la production",
        notes="Selective grant up to €500k for productions with French-speaking Belgian participation. "
              "Cultural fund, separate from economic Wallimage fund. "
              "Stackable with Tax Shelter.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # AUSTRIA — Regional Funds
    # -------------------------------------------------------------------------
    inc(
        name="Vienna Film Fund (Filmfonds Wien)",
        country_code="AT",
        region="Vienna",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=700_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.filmfonds-wien.at/en/funding/overview",
        source_description="Filmfonds Wien — Funding Overview & Richtlinien",
        notes="Up to €700k for theatrical features, €330k for TV fiction, €225k for Talent LAB features. "
              "Structured as soft loans. Annual budget ~€11.5M. "
              "Stackable with FISA+ national incentive.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Cine Tirol Production Incentive",
        country_code="AT",
        region="Tyrol",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "series"],
        source_url="https://www.cine.tirol/en/cine-tirol-production-incentive/",
        source_description="Cine Tirol — Production Incentive",
        notes="Non-repayable production grant up to 50% of eligible expenditures from filming in Tyrol. "
              "Contingent on 'Tirol Effect' (economic impact) and/or 'Tirol Reference' (thematic). "
              "Applications year-round. Stackable with FISA+.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Salzburg Film Fund",
        country_code="AT",
        region="Salzburg",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series"],
        source_url="https://www.salzburg.gv.at/wirtschaft_/Seiten/filmfoerderung-kommerziell.aspx",
        source_description="Land Salzburg — Förderung kommerzieller Filmproduktionen",
        notes="Up to 50% of Salzburg expenses; 200% regional spend multiplier required. "
              "Operated by Innovation Salzburg ('Filmlocation'). Also a €20k 'Freie Filmförderung'. "
              "Stackable with FISA+.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # NORWAY — Regional Funds
    # -------------------------------------------------------------------------
    inc(
        name="Arctic Film Norway (formerly Nordnorsk Filmsenter)",
        country_code="NO",
        region="Northern Norway",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        max_cap_currency="NOK",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://arktiskfilmnorge.no/en/grants/",
        source_description="Arctic Film Norway — Production Grants",
        notes="~NOK 10M annual budget; individual grants NOK 87k–1M. "
              "Northern Norway locations (Tromsø, Lofoten, Arctic). "
              "Stackable with national NFI incentive.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Vestnorsk Filmsenter (Western Norway Film Fund)",
        country_code="NO",
        region="Western Norway",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=3_000_000,
        max_cap_currency="NOK",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://en.vestnorskfilm.no/grants/",
        source_description="Vestnorsk Filmsenter — Production Grants",
        notes="Features: NOK 500k–3M; docs: NOK 150k–500k. Annual budget ~€2M. "
              "Bergen and fjord region. Stackable with national NFI incentive.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SWEDEN — Regional Funds
    # -------------------------------------------------------------------------
    inc(
        name="Film i Väst (West Sweden Film Fund)",
        country_code="SE",
        region="Västra Götaland",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        max_cap_currency="SEK",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://filmivast.com/production/how-we-work/regulations",
        source_description="Film i Väst — Co-production Regulations",
        notes="Co-investment; ~SEK 90M annual budget (~€7.8M), no fixed per-project cap. "
              "Amount contingent on spend in Västra Götaland (min 100% reinvestment). "
              "Trollhättan (Trollywood) studios. Sweden's largest regional fund. "
              "Stackable with national SFI rebate.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Film Stockholm",
        country_code="SE",
        region="Stockholm",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        max_cap_currency="SEK",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://filmstockholm.se/",
        source_description="Film Stockholm (formerly Film Capital Stockholm)",
        notes="Regional fund investing in films, TV dramas, and new formats. "
              "Annual budget min SEK 15M (~€1.5M). "
              "Stackable with national SFI rebate.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # FINLAND — Regional Funds
    # -------------------------------------------------------------------------
    inc(
        name="North Finland Film Commission (POEM/Business Oulu)",
        country_code="FI",
        region="Northern Finland",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series"],
        source_url="https://www.oulu.com/en/nffc/",
        source_description="POEM Foundation / North Finland Film Commission",
        notes="Regional film commission offering production services and modest production support. "
              "Operations transferred from POEM Foundation to Business Oulu. "
              "Arctic/Lapland locations. Stackable with national FFF incentive.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # IRELAND — Regional
    # -------------------------------------------------------------------------
    inc(
        name="WRAP Fund — Western Region Audiovisual Producers Fund",
        country_code="IE",
        region="West of Ireland",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=200_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://wrapfund.ie/production-investment/",
        source_description="WRAP Fund — Production Investment (managed by Ardán, formerly Galway Film Centre)",
        notes="Investment up to €200k per production. Covers Clare, Donegal, Galway, "
              "Leitrim, Mayo, Roscommon, Sligo. Managed by Ardán (formerly Galway Film Centre) "
              "and Western Development Commission. Stackable with Section 481 tax credit.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # NETHERLANDS — Regional Funds
    # -------------------------------------------------------------------------
    inc(
        name="Netherlands Film Fund — Regional Support",
        country_code="NL",
        region="Amsterdam / North Holland",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.filmfonds.nl/en/funding/fund/netherlands-film-production-incentive",
        source_description="Netherlands Film Fund — Film Production Incentive",
        notes="National 35% cash rebate (max €3M per year per company) also functions as regional support. "
              "Amsterdam Film Fund provides additional city-level facilitation. "
              "Stackable mechanisms available.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    # Rotterdam: No dedicated city-level production fund verified.
    # Rotterdam International Film Festival operates the Hubert Bals Fund
    # for international development, but it is not a regional production fund.

    # -------------------------------------------------------------------------
    # CZECH REPUBLIC — Regional
    # -------------------------------------------------------------------------
    inc(
        name="Prague Audiovisual Endowment Fund (PAVF)",
        country_code="CZ",
        region="Prague",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=2_000_000,
        max_cap_currency="CZK",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://pavf.eu/en/106-2/",
        source_description="PAVF — Prague Audiovisual Endowment Fund",
        notes="City grant up to CZK 2M for productions shooting in Prague. "
              "Stackable with national cash rebate (now 25% with tripled cap from 2025).",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # POLAND — Regional
    # -------------------------------------------------------------------------
    inc(
        name="Łódź Film Fund",
        country_code="PL",
        region="Łódź",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=None,
        max_cap_currency="PLN",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://polishfilmcommission.pl/funding/production/regional-funds/lodz-film-fund/",
        source_description="Łódź Film Fund — Polish Film Commission",
        notes="Co-production fund; total annual budget PLN 1.5M shared among ~10 projects (up to 50% of budget). "
              "Practical per-project grants average ~PLN 150k. "
              "Łódź Film School and studio infrastructure. Stackable with national 30% cash rebate.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),
    inc(
        name="Mazovia Warsaw Film Fund",
        country_code="PL",
        region="Mazovia",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=2_000_000,
        max_cap_currency="PLN",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="http://www.mwfc.pl/en/",
        source_description="Mazovia Warsaw Film Commission & Fund",
        notes="Co-production fund up to PLN 2M (~€475k) per project, max 40% of local production costs. "
              "Requires scenes filmed in Warsaw/Mazovia. Stackable with national 30% cash rebate.",
        stacking_allowed=True,
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # NORTH AMERICA - US State Incentives
    # -------------------------------------------------------------------------
    inc(
        name="US California Film and Television Tax Credit Program 4.0",
        country_code="US",
        region="California",
        incentive_type="tax_credit",
        rebate_percent=35.0,
        min_total_budget=1_000_000,
        max_cap_currency="USD",
        conditional_rates=[
            {
                "condition": "relocating_tv_series_first_season",
                "rate": 40.0,
                "note": "Relocating TV series can reach 40% in first California season; then 35%."
            }
        ],
        source_url="https://film.ca.gov/tax-credit/the-basics-4-0/",
        source_description="California Film Commission - The Basics 4.0 and Program FAQ",
        notes="Program 4.0 provides a 35% base credit for eligible categories, with higher rates for certain relocating TV projects. "
              "Program sunset June 30, 2030. Feature and many TV categories require minimum USD 1M budget.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US Georgia Entertainment Industry Investment Act",
        country_code="US",
        region="Georgia",
        incentive_type="tax_credit",
        rebate_percent=20.0,
        min_qualifying_spend=500_000,
        max_cap_currency="USD",
        conditional_rates=[
            {
                "condition": "state_promotion_included",
                "rate": 30.0,
                "note": "Additional 10% uplift if qualified Georgia promotion/logo requirements are met."
            }
        ],
        source_url="https://dor.georgia.gov/film-tax-credit-information",
        source_description="Georgia Department of Revenue - Film Tax Credit Information",
        notes="Base transferable credit is 20% of qualified in-state spend on certified productions. "
              "Additional 10% uplift is available for qualified Georgia promotional value. "
              "Minimum qualifying spend is USD 500,000.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US New York Film Production Tax Credit",
        country_code="US",
        region="New York",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        max_cap_currency="USD",
        conditional_rates=[
            {
                "condition": "multiple_productions_production_plus",
                "rate": 40.0,
                "note": "Production Plus may add 5-10% on subsequent projects for qualifying companies."
            }
        ],
        source_url="https://esd.ny.gov/new-york-state-film-tax-credit-program-production",
        source_description="Empire State Development - New York State Film Tax Credit Program (Production)",
        notes="30% credit on qualified production expenses. Program funded at USD 700M per year through 2036. "
              "Additional enhancements are available for certain upstate labor and repeat productions.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US New Jersey Film and Digital Media Tax Credit",
        country_code="US",
        region="New Jersey",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        min_qualifying_spend=1_000_000,
        max_cap_currency="USD",
        min_spend_percent=60.0,
        conditional_rates=[
            {
                "condition": "program_category_bonus",
                "rate": 40.0,
                "note": "Program pages indicate available credits up to 40% depending on category."
            }
        ],
        source_url="https://www.njeda.gov/new-jersey-film-digital-media-tax-credit-program/",
        source_description="NJEDA - New Jersey Film and Digital Media Tax Credit Program",
        notes="Transferable credit for qualified film and digital media spend. Film projects generally require at least 60% in-state spend and USD 1M NJ qualified expenses. "
              "Published award size indicates rates up to 40% depending on stream/category.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US New Mexico Film Production Tax Credit",
        country_code="US",
        region="New Mexico",
        incentive_type="tax_credit",
        rebate_percent=25.0,
        max_cap_currency="USD",
        conditional_rates=[
            {
                "condition": "uplifts_apply",
                "rate": 40.0,
                "note": "New Mexico program applies base 25% with various uplifts; effective combined rates can reach 40% for qualifying projects."
            }
        ],
        source_url="https://www.tax.newmexico.gov/tax-professionals/wp-content/uploads/sites/6/2022/12/FYI-370.pdf",
        source_description="New Mexico Taxation and Revenue Department - FYI-370 Film Production Tax Credit",
        notes="Refundable film production tax credit with a 25% base rate and statutory uplifts for qualifying production circumstances.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US Texas Moving Image Industry Incentive Program (TMIIIP)",
        country_code="US",
        region="Texas",
        incentive_type="grant",
        rebate_percent=5.0,
        max_cap_currency="USD",
        conditional_rates=[
            {
                "condition": "uplifts_apply",
                "rate": 27.5,
                "note": "Film/TV projects range 5-25% based on project category; additional 1-2.5% uplift. Max combined rate 27.5% for film/TV. Commercials/reality: 5-10% + uplift."
            }
        ],
        source_url="https://gov.texas.gov/film/page/tmiiip",
        source_description="Texas Film Commission — Texas Moving Image Industry Incentive Program",
        notes="Cash grant (not tax credit). Film/TV rate ranges 5-25% of qualifying Texas spend, "
              "plus 1-2.5% additional uplift (max 27.5%). Commercials/reality: 5-10% + uplift. "
              "Min USD 250,000 in-state spend. At least 60% of production in Texas. "
              "At least 35% Texas-resident cast and 35% Texas-resident crew required. "
              "Funded USD 300M per biennium for 10 years (overhauled 2025).",
        min_qualifying_spend=250_000,
        min_spend_percent=60.0,
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US Illinois Film Production Tax Credit",
        country_code="US",
        region="Illinois",
        incentive_type="tax_credit",
        rebate_percent=35.0,
        max_cap_currency="USD",
        min_qualifying_spend=100_000,
        source_url="https://dceo.illinois.gov/whyillinois/film/filmtaxcredit.html",
        source_description="Illinois DCEO — Film Production Services Tax Credit (SB 1911, signed Dec 2025)",
        notes="35% transferable tax credit on qualifying Illinois production spending (increased from 30% via SB 1911, Dec 2025). "
              "Applies to both IL-resident labor and in-state vendor spending. 30% on non-resident crew (up to 13 positions). "
              "Min USD 100,000 for features/TV, USD 50,000 for commercials. "
              "Stackable bonuses up to 20% additional (15% economically disadvantaged area labor, 5% outside Chicago metro). "
              "Program extended to 2039.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US Connecticut Digital Media & Motion Picture Tax Credit",
        country_code="US",
        region="Connecticut",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        max_cap_currency="USD",
        min_qualifying_spend=1_000_000,
        conditional_rates=[
            {
                "condition": "budget_gte",
                "threshold": 1_000_000,
                "rate": 30.0,
                "note": "30% credit for qualifying expenses over $1M. Lower tiers: 10% ($100K-$500K), 15% ($500K-$1M)."
            }
        ],
        source_url="https://portal.ct.gov/decd/content/film-tv-digital-media/02_learn_about_tax_incentives/02-digital-media-motion-picture-tax-credit",
        source_description="Connecticut DECD — Digital Media & Motion Picture Tax Credit",
        notes="Tiered non-refundable tax credit: 10% ($100K-$500K spend), 15% ($500K-$1M), 30% (over $1M). "
              "50% of principal photography days in CT, or 50% of post budget in CT, or $1M+ post spend in CT. "
              "Star salary cap $20M aggregate. Credits carry forward up to 5 years.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US Massachusetts Film Production Tax Credit",
        country_code="US",
        region="Massachusetts",
        incentive_type="tax_credit",
        rebate_percent=25.0,
        max_cap_currency="USD",
        min_qualifying_spend=50_000,
        source_url="https://www.mass.gov/info-details/massachusetts-film-tax-credit",
        source_description="Massachusetts Department of Revenue — Film Tax Credit",
        notes="25% payroll credit + 25% production expense credit on qualifying Massachusetts spend. "
              "Minimum spend of USD 50,000. At least 75% of principal photography days must be in MA "
              "AND at least 75% of total production expenses must be incurred in MA. "
              "Payroll for individuals earning $1M+ is excluded. 90% of excess credit is refundable.",
        min_spend_percent=75.0,
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="US Pennsylvania Film Production Tax Credit",
        country_code="US",
        region="Pennsylvania",
        incentive_type="tax_credit",
        rebate_percent=25.0,
        max_cap_currency="USD",
        source_url="https://dced.pa.gov/programs/film-tax-credit-program/",
        source_description="PA Department of Community & Economic Development — Film Tax Credit Program",
        notes="25% transferable tax credit on qualifying Pennsylvania production expenses. "
              "Separate 30% credit available on qualified post-production expenses at qualified PA facilities. "
              "60% of total production expenses must be incurred in PA. "
              "Applications reviewed in quarterly cycles.",
        min_spend_percent=60.0,
        local_producer_required=False,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # NORTH AMERICA - Canada Provincial Incentives
    # -------------------------------------------------------------------------
    inc(
        name="Ontario Film and Television Tax Credit (OFTTC)",
        country_code="CA",
        region="Ontario",
        incentive_type="tax_credit",
        rebate_percent=35.0,
        rebate_applies_to="labour_only",
        labour_fraction=0.6,
        max_cap_currency="CAD",
        conditional_rates=[
            {
                "condition": "regional_bonus",
                "rate": 45.0,
                "note": "Regional Ontario productions can access a 10% bonus on Ontario labor expenditures."
            }
        ],
        source_url="https://www.ontariocreates.ca/our-sectors/film-tv/business-initiatives/ontario-film-television-tax-credit-ofttc",
        source_description="Ontario Creates - OFTTC",
        notes="Refundable credit generally equal to 35% of eligible Ontario labor. "
              "Labour capped at 60% of eligible production costs (standard Canadian practice). "
              "Regional and first-time producer enhancements are available under program rules.",
        last_verified="2026-03",
    ),
    inc(
        name="Ontario Production Services Tax Credit (OPSTC)",
        country_code="CA",
        region="Ontario",
        incentive_type="tax_credit",
        rebate_percent=21.5,
        rebate_applies_to="qualifying_spend",
        max_cap_currency="CAD",
        source_url="https://www.ontariocreates.ca/our-sectors/film-tv/business-initiatives/ontario-production-services-tax-credit-opstc",
        source_description="Ontario Creates - OPSTC",
        notes="Refundable credit of 21.5% of qualifying Ontario production expenditures. "
              "Can stack with federal service tax credit where eligible.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="British Columbia Production Services Tax Credit (PSTC)",
        country_code="CA",
        region="British Columbia",
        incentive_type="tax_credit",
        rebate_percent=36.0,
        rebate_applies_to="labour_only",
        labour_fraction=0.6,
        max_cap_currency="CAD",
        conditional_rates=[
            {"condition": "major_production", "rate": 38.0, "note": "Major productions can access additional 2% credit."},
            {"condition": "dave_bonus", "rate": 16.0, "field": "bonus_percent", "note": "Additional DAVE credit applies to qualifying digital animation, VFX and post."}
        ],
        source_url="https://creativebc.com/motion-picture-tax-credits/production-services-tax-credit/",
        source_description="Creative BC - Production Services Tax Credit",
        notes="Basic PSTC rate increased to 36% for projects starting principal photography after January 1, 2025. "
              "Labour capped at 60% of eligible production costs (standard Canadian practice). "
              "Additional credits may apply for major production, regional, distant location, and DAVE.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Alberta Film and Television Tax Credit (FTTC)",
        country_code="CA",
        region="Alberta",
        incentive_type="tax_credit",
        rebate_percent=22.0,
        min_total_budget=499_999,
        max_cap_currency="CAD",
        conditional_rates=[
            {
                "condition": "alberta_owned_or_rural_remote_stream",
                "rate": 30.0,
                "note": "Eligible productions may apply for 30% rate under Alberta-owned, treaty, or rural/remote streams."
            }
        ],
        source_url="https://www.alberta.ca/film-television-tax-credit",
        source_description="Government of Alberta - Film and Television Tax Credit",
        notes="Refundable credit on eligible production costs. Applicants can qualify for 22% or 30% stream, depending on ownership and program conditions.",
        last_verified="2026-03",
    ),
    inc(
        name="Manitoba Film and Video Production Tax Credit",
        country_code="CA",
        region="Manitoba",
        incentive_type="tax_credit",
        rebate_percent=45.0,
        rebate_applies_to="labour_only",
        labour_fraction=0.6,
        max_cap_currency="CAD",
        conditional_rates=[
            {"condition": "frequent_filming_bonus", "rate": 55.0, "note": "Additional 10% frequent-filming bonus may apply on third qualifying production."},
            {"condition": "producer_or_rural_bonus", "rate": 50.0, "note": "5% producer and/or rural/northern bonuses may also apply."}
        ],
        source_url="https://www.gov.mb.ca/finance/business/print,ccredits.html",
        source_description="Province of Manitoba - Corporate Tax Credits (Film and Video Production Tax Credit)",
        notes="Refundable credit based on eligible salaries with a 45% base rate and additional bonuses for frequent filming, Manitoba producers, and rural/northern production. "
              "Labour capped at 60% of eligible production costs (standard Canadian practice).",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # NORTH AMERICA - Mexico Federal Incentives and Funds
    # -------------------------------------------------------------------------
    inc(
        name="Mexico EFICINE 189",
        country_code="MX",
        incentive_type="tax_credit",
        rebate_percent=None,
        max_cap_currency="MXN",
        source_url="https://www.imcine.gob.mx/Pagina/eficine-189",
        source_description="IMCINE - EFICINE (Articulo 189 LISR)",
        clause_reference="Articulo 189, Ley del Impuesto sobre la Renta",
        notes="Federal fiscal incentive where contributors to eligible Mexican film projects obtain an ISR tax credit equivalent to their contribution amount, subject to legal limits.",
        last_verified="2026-03",
    ),
    inc(
        name="Mexico Federal Stimulus for Cinematic and Audiovisual Production (2026 Decree)",
        country_code="MX",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        max_cap_amount=40_000_000,
        max_cap_currency="MXN",
        source_url="https://www.dof.gob.mx/nota_detalle.php?codigo=5780237&fecha=16/02/2026",
        source_description="DOF decree of 16 February 2026",
        notes="Decree grants a transferable fiscal credit of up to 30% of total project cost performed in Mexico, capped at MXN 40 million per project/beneficiary, subject to detailed lineamientos.",
        last_verified="2026-03",
    ),
    inc(
        name="Mexico FOCINE (Fomento al Cine Mexicano)",
        country_code="MX",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=10_000_000,
        max_cap_currency="MXN",
        source_url="https://www.imcine.gob.mx/Pagina/Noticia/se-fortalecen-los-apoyos-al-cine-mexicano--el-imcine-abre-convocatorias-para-2025",
        source_description="IMCINE 2025 announcement on FOCINE support amounts",
        notes="IMCINE announced expanded FOCINE support, including up to MXN 10 million for production/post-production in eligible feature project modalities.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # MENA - Incentives and Funds
    # -------------------------------------------------------------------------
    inc(
        name="Abu Dhabi Film Commission Cashback Rebate",
        country_code="AE",
        region="Abu Dhabi",
        incentive_type="cash_rebate",
        rebate_percent=35.0,
        max_cap_currency="AED",
        conditional_rates=[
            {
                "condition": "enhanced_rebate_points_system",
                "rate": 50.0,
                "note": "Enhanced rebate can reach 50% for projects meeting points-based criteria."
            }
        ],
        source_url="https://www.film.gov.ae/35-rebate",
        source_description="Abu Dhabi Film Commission - Cashback Rebate",
        notes="Standard cashback rebate is 35% on qualifying Abu Dhabi spend. "
              "Enhanced points-based framework can increase rebate up to 50% for eligible projects.",
        last_verified="2026-03",
    ),
    inc(
        name="Saudi Film Commission Cash Rebate Program",
        country_code="SA",
        incentive_type="cash_rebate",
        rebate_percent=40.0,
        max_cap_currency="USD",
        source_url="https://film.sa/incentive-programs/",
        source_description="Film Saudi - Incentive Program",
        notes="Saudi Film Commission program offers up to 40% cash rebate on eligible production spend in the Kingdom. "
              "Program requires local registration or Saudi coproduction structure and prior approvals.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Jordan Film Incentive Package (2025)",
        country_code="JO",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        max_cap_currency="USD",
        conditional_rates=[
            {
                "condition": "points_based_high_value_project",
                "rate": 45.0,
                "note": "Government package sets scalable rebate 25-45% based on project scale and Jordanian cultural criteria."
            }
        ],
        source_url="https://www.petra.gov.jo/Include/InnerPage.jsp?ID=71359&lang=en&name=en_news",
        source_description="Jordan News Agency (Petra) - Cabinet incentive package announcement, 11 May 2025",
        notes="Council of Ministers approved expanded cash rebate ranging 25% to 45% of qualifying in-country spend, with highest rate for high-value culturally aligned projects.",
        last_verified="2026-03",
    ),
    inc(
        name="Qatar Screen Production Incentive (QSPI)",
        country_code="QA",
        incentive_type="cash_rebate",
        rebate_percent=40.0,
        max_cap_currency="QAR",
        conditional_rates=[
            {
                "condition": "uplift_local_talent_and_cultural_criteria",
                "rate": 50.0,
                "note": "Program combines 40% base with up to 10% uplift for defined criteria."
            }
        ],
        source_url="https://www.dohafilm.com/en/press/press-releases/qatar-launches-qatar-screen-production-incentive-qspi-programme-one-worlds",
        source_description="Doha Film Festival / Film Committee at Media City Qatar press release, 21 Nov 2025",
        notes="QSPI announced with up to 50% rebate (40% base plus up to 10% uplift). "
              "Programme states application opening from Q2 2026.",
        last_verified="2026-03",
    ),
    inc(
        name="Qatari Film Fund (Doha Film Institute)",
        country_code="QA",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=182_500,
        max_cap_currency="QAR",
        eligible_formats=["feature_fiction", "documentary", "animation", "short"],
        eligible_stages=["development", "production", "post"],
        source_url="https://www.dohafilm.com/en/press/press-releases/doha-film-institute-opens-submissions-2025-qatari-film-fund-nurture-homegrown",
        source_description="Doha Film Institute - Qatari Film Fund 2025 call",
        notes="DFI states funding support for Qatari filmmakers with development and short film support valued up to QAR 182,500, alongside mentorship and production services.",
        last_verified="2026-03",
    ),
    inc(
        name="Red Sea Fund (Saudi Arabia)",
        country_code="SA",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="USD",
        eligible_formats=["feature_fiction", "documentary", "series", "animation", "short"],
        eligible_stages=["development", "production", "post"],
        source_url="https://redseafilmfest.com/en/press/red-sea-fund-announces-open-call-for-2026-post-production-support-cycle-1/",
        source_description="Red Sea Film Foundation - Red Sea Fund open call announcement (2026 Cycle 1)",
        notes="Red Sea Fund provides direct grants across production stages for eligible projects from Saudi Arabia, the Arab region, Africa, and Asia.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Tunisia-Italy Bilateral Co-Development Fund (CNCI-MiC)",
        country_code="TN",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="TND",
        eligible_formats=["feature_fiction", "documentary", "animation"],
        eligible_stages=["development"],
        source_url="https://cnci.tn/appel-a-projets-relatif-a-laide-au-developpement-de-la-coproduction-doeuvres-cinematographiques-tuniso-italiennes-est-ouvert-jusquau-07-fevrier-2025/",
        source_description="CNCI Tunisia call referencing 2018 CNCI-MiC bilateral development fund",
        notes="Bilateral non-recoupable co-development support for Tunisia-Italy feature projects (fiction, documentary, animation) under the treaty framework.",
        last_verified="2026-03",
    ),
    inc(
        name="Egypt Film Commission / EMPC Production Incentive",
        country_code="EG",
        region="Egypt Media Production City",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_currency="USD",
        source_url="https://egyptfilming.com/about/",
        source_description="Egypt Film Commission (EFC) About page",
        notes="EFC states production incentives and cashback up to 30% when shooting within EMPC premises and using its facilities and equipment.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Lebanon Ministry of Culture - Cinematographic Works Support",
        country_code="LB",
        incentive_type="fund",
        rebate_percent=None,
        source_url="https://culture.gov.lb/en/Ministry-Services/cinema",
        source_description="Lebanon Ministry of Culture - Cinema support service",
        notes="Ministry support covers script development, research, production technical operations, post (editing/mixing), and festival promotion for eligible Lebanese and documentary film projects.",
        last_verified="2026-03",
    ),
    inc(
        name="AFAC Cinema Program (Lebanon-based regional fund)",
        country_code="LB",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=50_000,
        max_cap_currency="USD",
        eligible_formats=["feature_fiction", "documentary", "animation", "short"],
        eligible_stages=["development", "production", "post"],
        source_url="https://www.arabculturefund.org/Programs/12/",
        source_description="AFAC Cinema Program open call and guidelines",
        notes="AFAC publishes grant ceilings: feature films up to USD 10k development, USD 50k production, USD 25k post; short/medium up to USD 20k production and USD 10k post.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Algeria Public Support Fund for Cinematographic Industry",
        country_code="DZ",
        incentive_type="fund",
        rebate_percent=None,
        source_url="https://www.aps.dz/culture/arts/mlhz7djc-%D8%A7%D9%86%D8%B7%D9%84%D8%A7%D9%82-%D8%AA%D8%B3%D8%AC%D9%8A%D9%84-%D9%85%D9%84%D9%81%D8%A7%D8%AA-%D8%A7%D9%84%D8%AF%D8%B9%D9%85-%D8%A7%D9%84%D8%B3%D9%8A%D9%86%D9%85%D8%A7%D9%8A%D9%94%D9%8A-%D8%A7%D9%84%D8%B9%D9%85%D9%88%D9%85%D9%8A-%D8%B9%D8%A8%D8%B1-%D8%A7%D9%84%D9%85%D9%86%D8%B5%D8%A9-%D8%A7%D9%84%D8%B1%D9%82%D9%85%D9%8A%D8%A9-%D9%84%D9%84%D9%85%D8%B1%D9%83%D8%B2-%D8%A7%D9%84%D9%88%D8%B7%D9%86%D9%8A-%D9%84%D9%84%D8%B3%D9%8A%D9%86%D9%85%D8%A7",
        source_description="APS report on Algeria National Center for Cinema support intake (2026)",
        notes="Algeria's National Center for Cinema receives applications for public support via the National Fund for developing the cinematographic industry and technologies.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # LATAM - second expansion wave
    # -------------------------------------------------------------------------
    inc(
        name="Dominican Republic Transferable Tax Credit (Law 108-10, Art. 39)",
        country_code="DO",
        incentive_type="tax_credit",
        rebate_percent=25.0,
        min_qualifying_spend=500_000,
        min_spend_currency="USD",
        max_cap_currency="DOP",
        source_url="https://dgii.gov.do/legislacion/leyesTributarias/Documents/Leyes%20Incentivo/Ley%20108-10.pdf",
        source_description="Ley 108-10 (DGII publication), Article 39 paragraphs I-II",
        clause_reference="Ley 108-10, Articulo 39",
        notes="Article 39 grants a transferable tax credit equal to 25% of qualifying spend in the Dominican Republic and sets a minimum spend threshold of USD 500,000 (or DOP equivalent).",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Uruguay Audiovisual Program (PUA) - International Cash Rebate",
        country_code="UY",
        incentive_type="cash_rebate",
        rebate_percent=None,
        max_cap_currency="UYU",
        source_url="https://www.acau.gub.uy/innovaportal/v/382/1/acau/cash-rebate-internacional%3A-servicios-de-produccion-de-contenidos-2025.html",
        source_description="ACAU 2025 International Cash Rebate call",
        notes="Program supports foreign and coproduction projects through cash rebate reimbursement of a percentage of eligible spend in Uruguay, with call-specific parameters published by ACAU.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Brazil Fundo Setorial do Audiovisual (FSA)",
        country_code="BR",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="BRL",
        source_url="https://www.gov.br/ancine/pt-br/fsa/institucional/sobre-o-fsa",
        source_description="ANCINE - Sobre o FSA",
        notes="Federal audiovisual fund administered within ANCINE/FNC framework supporting production, distribution/commercialization, exhibition, and services infrastructure through multiple financial instruments.",
        last_verified="2026-03",
    ),
    inc(
        name="Brazil Spcine Cash Rebate (São Paulo)",
        country_code="BR",
        region="São Paulo",
        incentive_type="cash_rebate",
        rebate_percent=20.0,
        max_cap_currency="BRL",
        min_qualifying_spend=2_000_000,
        min_spend_currency="BRL",
        conditional_rates=[
            {
                "condition": "diversity_and_sustainability_bonus",
                "rate": 30.0,
                "note": "Rebate up to 30% for projects with diverse HODs or sustainable practices."
            }
        ],
        source_url="https://spcine.com.br/",
        source_description="Spcine Cash Rebate Program (2026)",
        notes="20% to 30% cash rebate on eligible local spend in São Paulo. Min BRL 2M spend. "
              "Requires a São Paulo-based production partner.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Brazil RioFilme Cash Rebate (Rio de Janeiro)",
        country_code="BR",
        region="Rio de Janeiro",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_currency="BRL",
        min_qualifying_spend=2_000_000,
        min_spend_currency="BRL",
        conditional_rates=[
            {
                "condition": "rio_emblematic_locations_bonus",
                "rate": 35.0,
                "note": "Uplift to 35% if Rio is the main location and features iconic sites."
            }
        ],
        source_url="http://riofilmcommission.com/",
        source_description="RioFilme Cash Rebate Guidelines (2026)",
        notes="30% to 35% cash rebate on eligible local spend in Rio de Janeiro. Min BRL 2M spend. "
              "Requires a Rio-based production partner.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Argentina INCAA Fondo de Fomento Cinematografico",
        country_code="AR",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="ARS",
        source_url="https://www.incaa.gob.ar/institucional/quienes-somos/como-nos-financiamos/",
        source_description="INCAA - Como nos financiamos",
        notes="INCAA manages the national Fondo de Fomento Cinematografico financed by legal levies under Ley 17.741 framework and related regulations; support is deployed through subsidies, credits, and program lines.",
        last_verified="2026-03",
    ),
    inc(
        name="Chile IFI Audiovisual (High-Impact Foreign Investment Support)",
        country_code="CL",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=3_000_000,
        max_cap_currency="USD",
        conditional_rates=[
            {
                "condition": "filmed_outside_metropolitan_region",
                "rate": 40.0,
                "note": "Regional uplift up to 40% for productions entirely outside Metropolitana."
            }
        ],
        source_url="https://www.cultura.gob.cl/convocatorias/regresa-programa-que-fomenta-la-filmacion-de-grandes-producciones-internacionales-en-chile/",
        source_description="Chile Ministry of Cultures - IFI Audiovisual announcement",
        notes="IFI Audiovisual reimburses up to 30% of qualified Chile spend and up to 40% for productions shot entirely in regions outside Metropolitana, with published call caps.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Chile Fondo de Inversion Audiovisual (FIA)",
        country_code="CL",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=300_000_000,
        max_cap_currency="CLP",
        min_total_budget=50_000_000,
        eligible_formats=["feature_fiction", "documentary", "series", "animation", "short"],
        eligible_stages=["preproduction", "production", "post"],
        source_url="https://www.fondosdecultura.cl/fondo-inversion-audiovisual-2026/",
        source_description="Convocatorias Cultura - FIA 2026",
        notes="FIA supports associated national-international projects with partial financing for pre-production/production/post in Chile. 2026 call publishes max CLP 300M and minimum request CLP 50M.",
        last_verified="2026-03",
    ),
    inc(
        name="Peru Economic Stimuli for Cinematographic and Audiovisual Activity",
        country_code="PE",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="PEN",
        source_url="https://estimuloseconomicos.cultura.gob.pe/2025/estimulos-economicos-para-la-actividad-cinematografica-y-audiovisual-2025",
        source_description="Peru Ministry of Culture - annual audiovisual stimuli calls",
        notes="Ministry of Culture runs annual competitive economic stimuli for development, production, post-production, distribution, training, and market participation across the national audiovisual sector.",
        last_verified="2026-03",
    ),
    inc(
        name="Ecuador IFCI International Cash Rebate Call (2025)",
        country_code="EC",
        incentive_type="cash_rebate",
        rebate_percent=None,
        max_cap_amount=100_000,
        max_cap_currency="USD",
        min_qualifying_spend=1_000_000,
        min_spend_currency="USD",
        source_url="https://www.creatividad.gob.ec/wp-content/uploads/downloads/2025/05/Final-Bases-Te%CC%81cnicas-Cash-Rebate.pdf",
        source_description="Instituto de Fomento a la Creatividad y la Innovacion (IFCI) - Bases Tecnicas Cash Rebate 2025",
        clause_reference="Section 4 eligibility conditions; financing amount conditions",
        notes="IFCI technical bases define a public call granting a fixed non-reimbursable incentive of USD 100,000 to an eligible international project that demonstrates at least USD 1,000,000 of eligible spend in Ecuador during the project term.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Costa Rica Film Investment Law VAT Refund",
        country_code="CR",
        incentive_type="tax_rebate",
        rebate_percent=11.7,
        rebate_applies_to="vat_paid_on_eligible_goods_and_services",
        max_cap_currency="USD",
        min_qualifying_spend=500_000,
        min_spend_currency="USD",
        source_url="https://pgrweb.go.cr/scij/Busqueda/Normativa/Normas/nrm_texto_completo.aspx?nValor1=1&nValor2=95884&param1=NRTC",
        source_description="Sistema Costarricense de Informacion Juridica - Ley No. 10071 Atraccion de inversiones filmicas en Costa Rica",
        clause_reference="Article 4(d)",
        notes="Law 10071 grants beneficiaries a refund of 90% of VAT paid on eligible goods and services acquired in Costa Rica when project-related purchases exceed USD 500,000, "
              "which corresponds to an effective rebate of up to 11.7% at Costa Rica's standard 13% VAT rate.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Panama Film Incentive Program (MICI Cash Rebate)",
        country_code="PA",
        incentive_type="cash_rebate",
        rebate_percent=25.0,
        min_qualifying_spend=500_000,
        min_spend_currency="USD",
        max_cap_currency="USD",
        source_url="https://mici.gob.pa/incentivos-film/",
        source_description="Ministerio de Comercio e Industrias (Panama) - Incentivos FILM",
        notes="MICI publishes a 25% economic return for audiovisual projects with minimum investment of USD 500,000 in Panama. "
              "Programme materials also state project submission through a local producer and certified local legal representation for applications and accounting deliverables.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Paraguay PROA PY International Cash Rebate",
        country_code="PY",
        incentive_type="cash_rebate",
        rebate_percent=18.0,
        min_qualifying_spend=100_000,
        min_spend_currency="USD",
        max_cap_currency="USD",
        conditional_rates=[
            {
                "condition": "high_impact_production",
                "rate": 20.0,
                "note": "High-impact productions (USD 1,000,000+ eligible investment and additional criteria) can access 20% reimbursement."
            }
        ],
        source_url="https://inap.gov.py/wp-content/uploads/2025/08/Bases-concursables-PROA-PY-2025-version-aprobada-por-CNA-29-08-2025.pdf",
        source_description="Instituto Nacional del Audiovisual Paraguayo (INAP) - PROA PY 2025 approved bases",
        clause_reference="Articles 12 and 13",
        notes="INAP-approved PROA PY bases set a cash rebate mechanism on eligible spend for projects with at least USD 100,000 investment in Paraguay: 18% for general productions and 20% for high-impact productions.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Bolivia Fondo de Fomento al Cine y Arte Audiovisual",
        country_code="BO",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="BOB",
        source_url="https://www.minculturas.gob.bo/fondo-de-fomento-al-cine-y-arte-audiovisual-beneficiara-a-cineastas-del-pais/",
        source_description="Ministerio de Culturas de Bolivia - official launch note for Fondo de Fomento al Cine y Arte Audiovisual",
        notes="The Ministry reports a national public-call fund administered through ADECINE with a total allocation of Bs 13.5 million supporting production, post-production, and indigenous/community audiovisual lines across 29 projects.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Trinidad and Tobago Film Production Expenditure Rebate",
        country_code="TT",
        incentive_type="cash_rebate",
        rebate_percent=12.5,
        min_qualifying_spend=630_000,
        min_spend_currency="TTD",
        max_cap_amount=51_200_000,
        max_cap_currency="TTD",
        conditional_rates=[
            {
                "condition": "eligible_local_producer_bracket",
                "rate": 35.0,
                "note": "Programme documents state local producers can receive 35% rebate within published spend brackets."
            },
            {
                "condition": "qualifying_local_labour",
                "rate": 55.0,
                "note": "An additional 20% on qualifying local labour can lift effective rebate to a stated maximum of 55%."
            }
        ],
        source_url="https://tradeind.gov.tt/quo_storage/2024/06/Grants-and-Incentives2024.pdf",
        source_description="Ministry of Trade and Industry (Trinidad and Tobago) - Grants and Incentives 2024",
        clause_reference="Film Production Expenditure Rebate Programme section",
        notes="Government publication states a tiered 12.5%-35% rebate for foreign productions on qualifying local expenditure, "
              "plus a 20% local labour uplift, and requires international productions to partner with a registered Trinidad and Tobago company.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Jamaica Film Production Incentive Bundle (ETC, PIR, Bond Waiver)",
        country_code="JM",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        rebate_applies_to="labour_only",
        labour_fraction=0.6,
        max_cap_currency="JMD",
        source_url="https://www.filmjamaica.com/film-financing-incentives-2/",
        source_description="Film Jamaica (JAMPRO) - Film Financing and Incentives",
        notes="JAMPRO states that filmmakers can access Employment Tax Credit (maximum 30% credit on PAYE obligations), "
              "bond waivers for temporary importation of approved equipment for foreign productions, and Productive Input Relief for registered practitioners. "
              "Labour capped at 60% of eligible production costs (standard industry practice).",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Bahamas Temporary Import Duty Exemption for Film Equipment",
        country_code="BS",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="BSD",
        source_url="https://laws.bahamas.gov.bs/cms/images/LEGISLATION/PRINCIPAL/1976/1976-0004/1976-0004_1.pdf",
        source_description="Customs Management Act and Customs Regulations (Bahamas official legislation portal)",
        clause_reference="Section 82; Regulation 86(h)",
        notes="Bahamas customs law allows temporary importation procedures with duty exemption mechanisms for specified goods, including photographic/cinematographic equipment and related props for foreign media services, subject to approval and re-export security conditions.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Antigua and Barbuda Film Commission Incentive Package",
        country_code="AG",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XCD",
        source_url="https://www.antiguafilmcommission.com/incentives",
        source_description="Antigua and Barbuda Film Commission - official incentives page",
        notes="The official commission package lists tax-free import of film-related goods, work-permit waivers for foreign cast/crew, no location fees at government and historical sites, and government security/policing support for productions.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Belize Temporary Duty Exemption for Filming Equipment",
        country_code="BZ",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="BZD",
        source_url="https://www.belizefilmcommission.com/faq",
        source_description="Belize Film Commission - official FAQ and filming process requirements",
        notes="Belize Film Commission guidance states productions can secure duty exemptions for temporarily imported equipment when serialised equipment lists are submitted in advance; "
              "the process requires a local coordinator for all foreign productions and customs-broker support for cargo imports.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Guyana Temporary Film Equipment Import License (GTA Process)",
        country_code="GY",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="GYD",
        source_url="https://guyanatourism.com/filming-requests/",
        source_description="Guyana Tourism Authority - Filming Requests official process",
        notes="GTA filming process states there is currently no application fee and that approved productions receive a temporary import license for film equipment, "
              "with the explicit condition that equipment exits Guyana after filming (3 months or less).",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Guatemala Temporary Import with Re-export Regime",
        country_code="GT",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="GTQ",
        source_url="https://en.portal.sat.gob.gt/portal/preguntas-frecuentes/temas-aduaneros/",
        source_description="Superintendencia de Administracion Tributaria (SAT) - Customs FAQ and legal basis for temporary import regime",
        clause_reference="Temporary Importation with Re-exportation in the Same State",
        notes="SAT states that temporary import with re-export in the same state is available through customs procedures and identifies a maximum 6-month stay for goods under this regime, with extension options under applicable customs rules.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Barbados Cultural Industries Duty-Free Concessions (Audiovisual)",
        country_code="BB",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="BBD",
        source_url="https://ncf.bb/duty-free-concessions/",
        source_description="National Cultural Foundation (Barbados) - Duty-Free Concessions guidance under Cultural Industries Development Act",
        clause_reference="Part VIII (Audio-Visual Practitioners)",
        notes="NCF guidance states audiovisual practitioners and eligible creative businesses can access duty-free concessions for approved professional tools and equipment under the Cultural Industries Development Act, following ministerial approval procedures.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Saint Lucia Fiscal Incentives Act Application (Customs Duty Waivers)",
        country_code="LC",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XCD",
        source_url="https://www.govt.lc/services/apply-for-fiscal-incentives-companies-",
        source_description="Government of Saint Lucia service portal - Apply for Fiscal Incentives (Companies)",
        notes="Government service guidance states registered and incorporated Saint Lucia companies can apply for fiscal incentives, including waiver of customs duties and export allowances, with Cabinet review and approval.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Saint Vincent and the Grenadines Investment Incentive Framework",
        country_code="VC",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XCD",
        source_url="https://www.gov.vc/index.php/business/advantages",
        source_description="Government of Saint Vincent and the Grenadines - official investment advantages page",
        notes="Government investment framework highlights available incentives including complete or partial income tax exemptions, tax holidays, and import tax concessions on raw materials, machinery, equipment, and spare parts for qualifying investments.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Saint Kitts and Nevis Conditional Duty Exemptions (Approved Projects)",
        country_code="KN",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XCD",
        source_url="https://nevisipa.org/investor-guide-old/list-of-conditional-duty-exemptions/",
        source_description="Nevis Investment Promotion Agency - List of Conditional Duty Exemptions",
        notes="Official investment guidance lists conditional duty exemptions for approved industry and tourism projects, including machinery/equipment imports and specified project materials subject to competent authority approval.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Dominica Fiscal Incentives Framework (Approved Investment Projects)",
        country_code="DM",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XCD",
        source_url="https://www.dominica.gov.dm/images/docs/services/returning_residents_information_manual_2011.pdf",
        source_description="Government of Dominica - Returning Residents Information Manual (investment incentives section)",
        clause_reference="Investment Incentives section",
        notes="Government manual states approved investment projects under the Fiscal Incentives Act can receive tax holidays of up to 15 years, exemptions from import duty on materials/equipment, and withholding-tax exemptions on relevant external payments.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Grenada Investment Incentive Regime (Approved Projects)",
        country_code="GD",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XCD",
        source_url="https://investingrenada.gd/investment-services/",
        source_description="Investment Promotion Agency Grenada - Investment Services / Incentive Services",
        notes="IPA states Grenada's incentives regime offers investment allowances, exemptions on customs duty and excise tax, suspension of VAT, and tax credits for qualifying projects in priority sectors approved through the investment incentive process.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Cuba Fondo de Fomento del Cine Cubano (ICAIC)",
        country_code="CU",
        incentive_type="fund",
        rebate_percent=None,
        eligible_formats=["feature_fiction", "documentary", "animation"],
        eligible_stages=["development", "production", "post"],
        source_url="https://www.granma.cu/cultura/2025-03-31/abierta-septima-convocatoria-del-fondo-de-fomento-para-el-cine-cubano-31-03-2025-16-03-31",
        source_description="Granma (official state newspaper) - Seventh call for ICAIC Fondo de Fomento (2025)",
        notes="State-backed film fund created by Council of Ministers Agreement No. 8613 (14 June 2019) under Decree-Law 373/2019 framework. "
              "Official call information states support for independent creators and audiovisual collectives, with bases and forms published by ICAIC channels.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Moldova National Film Center (CNC) Financing Competition",
        country_code="MD",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="MDL",
        source_url="https://www.mc.gov.md/ro/content/centrul-national-al-cinematografiei-anunta-rezultatele-concursului-de-finantare-proiectelor",
        source_description="Moldova Ministry of Culture - official publication on CNC financing competition",
        notes="Ministry of Culture confirms that CNC runs state-funded competitive calls for film projects in multiple evaluation stages, including support for national and international coproduction projects.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Nigeria Creative Economy Development Fund (CEDF) - Film Eligible Window",
        country_code="NG",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="NGN",
        eligible_formats=["feature_fiction", "documentary", "series", "animation", "short"],
        source_url="https://cedf.gov.ng/",
        source_description="Federal Ministry of Arts, Culture, Tourism and Creative Economy - CEDF rollout portal",
        notes="Government-approved creative-economy financing vehicle where film is explicitly listed among eligible sectors. "
              "Supports financing access through staged application windows and multiple financing instruments for eligible creative businesses/projects.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Bosnia and Herzegovina Foundation for Cinematography Co-financing Calls",
        country_code="BA",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="BAM",
        source_url="https://fmks.gov.ba/hr/izvjesca-sa-sjednica-upravnih-odbora-fondacije-za-izdavastvo-fondacije-za-bibliotecku-djelatnost-fondacije-za-muzicke-scenske-i-likovne-umjetnosti-i-fondacije-za-kinematografiju-u-2025-i-2026-god/",
        source_description="Federal Ministry of Culture and Sport (FBiH) reports on Foundation for Cinematography board work, 2025-2026",
        notes="Federal ministry reporting confirms ongoing preparation and implementation of competition procedures and program documents for the Foundation for Cinematography, including calls for film project co-financing.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Andorra Cinematography Aid (Government Subsidy Call)",
        country_code="AD",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="EUR",
        eligible_formats=["feature_fiction", "documentary", "animation"],
        source_url="https://www.govern.ad/ca/tematiques/ajuts-i-subvencions/cultura/ajuts-a-la-cinematografia",
        source_description="Government of Andorra - Ajuts a la cinematografia",
        notes="Government call provides direct subsidy aid for feature fiction, documentary, or animation film production intended for cinemas, TV, festivals, or streaming platforms, with annual call bases and deadlines published on the official portal.",
        local_producer_required=True,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # ASIA - high-confidence expansion
    # -------------------------------------------------------------------------
    inc(
        name="India Incentive Scheme for Foreign Films and Official AV Coproductions",
        country_code="IN",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=300_000_000,
        max_cap_currency="INR",
        conditional_rates=[
            {
                "condition": "indian_manpower_gte_15_percent",
                "rate": 35.0,
                "note": "Guidelines provide an additional 5% bonus for employing at least 15% Indian labour (live shoots)."
            },
            {
                "condition": "significant_indian_content",
                "rate": 40.0,
                "note": "Additional 5% bonus for Significant Indian Content; total incentive can reach up to 40%."
            }
        ],
        source_url="https://mib.gov.in/sites/default/files/2024-02/Revised%20incentive%20guidelines.pdf",
        source_description="Ministry of Information and Broadcasting - Revised incentive guidelines (2024)",
        clause_reference="Executive Summary; Clauses 2.3 and 2.7",
        notes="Reimbursement up to 30% of qualifying production expenditure in India, with bonus incentives totaling up to 40%, subject to a maximum payout of INR 300 million per project.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Bangladesh Government Film Grant Program (Full-Length and Short-Length)",
        country_code="BD",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="BDT",
        eligible_formats=["feature_fiction", "documentary", "short"],
        source_url="https://moi.gov.bd/pages/files/694031daa31054345f0d1e82",
        source_description="Ministry of Information and Broadcasting (Bangladesh) - policy page for government film grants",
        clause_reference="Government grants policy files and annual GO notices",
        notes="The ministry maintains formal policy documents for government grants to full-length and short-length film production and issues annual fiscal-year calls for submissions under GO notices.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Nepal FDB Conditional Grant for Cinema Hall Upgrading",
        country_code="NP",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_currency="NPR",
        eligible_stages=["exhibition"],
        source_url="https://www.film.gov.np/notices/261/",
        source_description="Film Development Board (Nepal) official notice on conditional promotion grants for cinema houses",
        clause_reference="Notice dated 2082/10/23 (BS) and linked application forms",
        notes="Film Development Board notice opens applications for conditional incentive grants to support cinema hall upgrading and re-operation, aimed at domestic film promotion, audience growth, and market expansion.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Pakistan Film and Drama Finance Fund (FDFF)",
        country_code="PK",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="PKR",
        source_url="https://demp.gov.pk/film-drama-finance-fund/",
        source_description="Directorate of Electronic Media and Publications (Government of Pakistan) - FDFF page",
        clause_reference="FDFF overview and statutory notification summary",
        notes="Official ministry implementation page states FDFF is notified under S.R.O. 1011(I)/2023 and functions as a structured support mechanism providing grants and soft loans to film and drama producers via a notified Fund Management Committee.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Pakistan Film Industry Tax Incentive Package (Finance Act 2022)",
        country_code="PK",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="PKR",
        source_url="https://demp.gov.pk/film-drama-finance-fund/",
        source_description="Directorate of Electronic Media and Publications - Tax Incentives list for Film and Drama Industry",
        clause_reference="Tax Incentives section",
        notes="Government page lists 2022 Finance Act measures including 5-year tax holiday for cinema operations, 5-year exemption on feature-film production income, "
              "and 5-year exemptions/zero-rating on imports and supply of cinematographic equipment under referenced tax/customs provisions.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Sri Lanka National Film Corporation Production Support",
        country_code="LK",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="LKR",
        source_url="https://nfc.gov.lk/home-page/",
        source_description="National Film Corporation of Sri Lanka official portal - Film Production Support service",
        notes="NFC service catalogue states that the corporation provides film production support through financial assistance as part of its statutory mandate to promote and develop the national film industry.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Thailand Film Incentive Measures (Foreign Production Rebate)",
        country_code="TH",
        incentive_type="cash_rebate",
        rebate_percent=15.0,
        min_qualifying_spend=50_000_000,
        min_spend_currency="THB",
        max_cap_currency="THB",
        source_url="https://tfo.dot.go.th/wp-content/uploads/2025/03/FINAL-%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B8%81%E0%B8%B2%E0%B8%A8-%E0%B8%AB%E0%B8%A5%E0%B8%B1%E0%B8%81%E0%B9%80%E0%B8%81%E0%B8%93%E0%B8%91%E0%B9%8C-2567-in-English-final-clean-pdf.pdf",
        source_description="Thailand Department of Tourism notification (English) and TFO incentive criteria",
        clause_reference="Clause 5",
        notes="Primary incentive is 15% for promoted films with at least THB 50 million qualified expenses. Additional incentives may be granted under defined criteria, with total rebate up to 30% and no cap.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Malaysia Film in Malaysia Incentive (FIMI)",
        country_code="MY",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_currency="MYR",
        source_url="https://www.filminmalaysia.com/incentives/incentives-overview/",
        source_description="Film in Malaysia (FINAS/FIMO) - Incentives Overview",
        notes="FIMI provides a 30% cash rebate on Qualifying Malaysian Production Expenditure (QMPE) for eligible Malaysian and foreign productions under FIMI guidelines.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Indonesia Dana Indonesiana - Sinema Indonesia Grant Support",
        country_code="ID",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=200_000_000,
        max_cap_currency="IDR",
        eligible_formats=["feature_fiction", "documentary", "short"],
        source_url="https://danaindonesiana.kemenbud.go.id/backend/storage/files/2025/aan_fendianto/iu_sinema_indonesia.pdf",
        source_description="Kementerian Kebudayaan / Dana Indonesiana - Informasi Umum Kategori Sinema Indonesia (2025)",
        clause_reference="Section F (Bentuk Dukungan)",
        notes="Official 2025 guidance states grant support is disbursed via LPDP transfer with a maximum of Rp 200,000,000 per beneficiary (tax included). "
              "Program supports cultural actors and institutions in cinema/audiovisual activities.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Indonesia International Co-Production Matching Fund",
        country_code="ID",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=10_000_000,
        max_cap_currency="USD",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://kemenparekraf.go.id/",
        source_description="Kemenparekraf / Indonesian Cultural Endowment Fund guidelines",
        notes="2026 matching fund for international co-productions. "
              "USD 10 million total annual fund. Requires an Indonesian producer or director attached to the project.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Brunei AITI Pitch and Produce Seed Funding Programme",
        country_code="BN",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="BND",
        eligible_formats=["feature_fiction", "documentary", "series", "animation", "short"],
        source_url="https://www.aiti.gov.bn/development/pitch-and-produce-60/",
        source_description="Authority for Info-communications Technology Industry (AITI) - Pitch and Produce 6.0",
        notes="AITI states that successful local production company applicants are granted seed funding after pitching and evaluation. "
              "Program is positioned as support for local broadcasting and multimedia content production.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Laos Investment Promotion Law Tax and Customs Relief (Approved Projects)",
        country_code="LA",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="LAK",
        conditional_rates=[
            {
                "condition": "zone_1_profit_tax_exemption",
                "rate": 10.0,
                "unit": "years",
                "note": "Investment projects in promoted Zone 1 may receive up to 10 years profit tax exemption."
            },
            {
                "condition": "zone_2_profit_tax_exemption",
                "rate": 6.0,
                "unit": "years",
                "note": "Investment projects in promoted Zone 2 may receive up to 6 years profit tax exemption."
            },
            {
                "condition": "zone_3_profit_tax_exemption",
                "rate": 4.0,
                "unit": "years",
                "note": "Investment projects in promoted Zone 3 may receive up to 4 years profit tax exemption."
            }
        ],
        source_url="https://investlaos.gov.la/wp-content/uploads/formidable/22/Final_IPL_No.14.NA_17Nov2016_Eng_30_Oct_2018.pdf",
        source_description="Lao People's Democratic Republic Investment Promotion Law No. 14/NA (official English text)",
        clause_reference="Articles 9-12",
        notes="Investment Promotion Law provides profit tax exemptions by zone and additional customs/VAT relief on qualifying imported production inputs and equipment for approved projects. "
              "This is a cross-sector framework and requires project approval under Lao investment promotion procedures.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Myanmar Investment Law Tax and Customs Relief (Promoted/Approved Projects)",
        country_code="MM",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="MMK",
        conditional_rates=[
            {
                "condition": "zone_1_income_tax_exemption",
                "rate": 7.0,
                "unit": "years",
                "note": "Section 75 allows up to 7 years income tax exemption for promoted businesses in Zone 1."
            },
            {
                "condition": "zone_2_income_tax_exemption",
                "rate": 5.0,
                "unit": "years",
                "note": "Section 75 allows up to 5 years income tax exemption for promoted businesses in Zone 2."
            },
            {
                "condition": "zone_3_income_tax_exemption",
                "rate": 3.0,
                "unit": "years",
                "note": "Section 75 allows up to 3 years income tax exemption for promoted businesses in Zone 3."
            }
        ],
        source_url="https://myanmartradeportal.gov.mm/uploads/legals/2018/5/Myanmar%20Investment%20Law%202016%20%28Eng%29.pdf",
        source_description="Myanmar Investment Law (2016, official English text hosted by Myanmar Trade Portal)",
        clause_reference="Chapter 18, Sections 75-77",
        notes="Law provides income tax exemptions by promoted zone and customs/internal tax relief for machinery, equipment, and imported raw materials used in approved investment businesses. "
              "Eligibility depends on Myanmar Investment Commission permit/endorsement and promoted-sector classification.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Kazakhstan Cinematography Subsidy (State Cash Rebate)",
        country_code="KZ",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_currency="KZT",
        source_url="https://adilet.zan.kz/eng/docs/Z1900000212",
        source_description="Law of the Republic of Kazakhstan On Cinematography",
        clause_reference="Article 15",
        notes="Article 15 states that cinema subsidy is provided by reimbursing up to 30% of the cost of goods, works, and services related to film production (or part of it) in Kazakhstan. "
              "Subsidy agreements are concluded through the State Center for Support of National Cinema with authorized-body approval.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Bahrain Film Commission Cashback Rebate",
        country_code="BH",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_currency="BHD",
        source_url="https://filmbahrain.com/about",
        source_description="Bahrain Film Commission - About Commission services",
        notes="Bahrain Film Commission service list explicitly includes 'up to 30% cashback rebate' and tax exemption support for productions filming in Bahrain, alongside permit and visa facilitation.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Mongolia Film Cost Reimbursement Framework (Law on Promotion of Cinematography)",
        country_code="MN",
        incentive_type="cash_rebate",
        rebate_percent=None,
        min_qualifying_spend=500_000,
        min_spend_currency="USD",
        max_cap_currency="MNT",
        source_url="https://legalinfo.mn/mn/detail?lawId=16230709404501",
        source_description="Mongolia Law on Promotion of Cinematography",
        clause_reference="Article 15",
        notes="The law establishes reimbursement of a certain percentage of filmmaking costs for foreign legal entities producing for international distribution in Mongolia, independently or jointly with Mongolian entities. "
              "Article 15.4 sets a precondition of at least USD 500,000 spent in Mongolia on eligible costs.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Oman Customs Exemption Framework for Approved Import Categories",
        country_code="OM",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="OMR",
        source_url="https://www.customs.gov.om/en/business-services/procedural_services/customs-exemptions/",
        source_description="Directorate General of Customs (Oman) - official customs exemptions guidance",
        clause_reference="GCC Unified Customs Law references (incl. Article 98 and related exemptions)",
        notes="Oman's official customs framework applies exemptions under GCC unified customs law categories and project-specific approvals through defined customs application procedures.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Maldives Special Economic Zone Investment Incentives",
        country_code="MV",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=100_000_000,
        min_spend_currency="USD",
        conditional_rates=[
            {
                "condition": "sustainable_township_project",
                "rate": 5.0,
                "unit": "percent_income_tax_first_10_years",
                "note": "For sustainable township projects above USD 500 million, the SEZ amendment sets 5% income tax for the first 10 years."
            },
            {
                "condition": "sustainable_township_project",
                "rate": 10.0,
                "unit": "percent_income_tax_next_10_years",
                "note": "The SEZ amendment then sets 10% income tax for the next 10 years."
            }
        ],
        source_url="https://investmaldives.gov.mv/president-dr-mohamed-muizzu-announces-the-investment-areas-and-minimum-investment-thresholds-to-be-considered-under-the-special-economic-zones-law/",
        source_description="Invest Maldives - SEZ investment areas and minimum thresholds announcement",
        clause_reference="SEZ Act / Presidential Decree No. 1/2025",
        notes="Official SEZ framework for large-scale investments in the Maldives. This is not film-specific, but could be relevant to studio or infrastructure projects that qualify as SEZ investments.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Kuwait KDIPA Tax Exemption Mechanism (Approved Investments)",
        country_code="KW",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="KWD",
        source_url="https://kdipa.gov.kw/kdipa-issues-a-decision-on-tax-exemption-mechanism/",
        source_description="Kuwait Direct Investment Promotion Authority (KDIPA) - tax exemption mechanism decision",
        clause_reference="DG Decision No. 16 of 2016",
        notes="KDIPA's official decision states approved investment entities may receive tax exemption certificates, with eligibility tied to technology transfer, job creation, and local-content support criteria.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Bhutan Fiscal Incentives for Capital Goods and Tax Holidays",
        country_code="BT",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="BTN",
        source_url="https://www.industry.gov.bt/services/view/recommendation-for-fiscal-incentives",
        source_description="Bhutan Department of Industry - Recommendation for Fiscal Incentives",
        notes="Department guidance states industries can access exemptions on sales tax and customs duty for capital goods subject to recommendation under the Fiscal Incentives Act of Bhutan 2021, along with tax holidays and investment allowances.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Iraq National Investment Commission 10-Year Tax Exemption",
        country_code="IQ",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="IQD",
        source_url="https://investpromo.gov.iq/?page_id=189",
        source_description="Iraq National Investment Commission - Investor Guide",
        clause_reference="Investment Law Article 15",
        notes="Official NIC investor guide states qualifying investments receive a 10-year exemption from taxes and three years exemption from import fees for required equipment, with licensing administered through the NIC one-stop shop.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Uganda Investment Code Incentives for Approved Investments",
        country_code="UG",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=500_000,
        min_spend_currency="USD",
        source_url="https://ugandainvest.go.ug/wp-content/uploads/2024/01/Tax-Incentive-Guide-2.pdf",
        source_description="Uganda Investment Authority - Tax Incentive Guide",
        clause_reference="Investment Code provisions and tax incentive guide",
        notes="UIA guide states qualifying investments can access import-duty and sales-tax exemptions on plant, machinery and equipment, with a foreign-investor threshold of USD 500,000 for incentive eligibility.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Zambia Development Agency Fiscal Incentives",
        country_code="ZM",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=500_000,
        min_spend_currency="USD",
        source_url="https://zda.org.zm/investment-incentives/",
        source_description="Zambia Development Agency - Investment Incentives",
        notes="ZDA states investments of at least USD 500,000 in priority sectors or economic zones qualify for fiscal incentives including 0% import duty on capital equipment and accelerated depreciation on machinery for five years.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Zimbabwe Special Economic Zone Incentives",
        country_code="ZW",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        source_url="https://www.zimra.co.zw/16-tax/company/1756-fiscal-incentives",
        source_description="Zimbabwe Revenue Authority - Fiscal Incentives Made Available for Investors",
        notes="ZIMRA describes a suite of investment incentives including tax holidays, reduced tax rates, accelerated depreciation, and customs incentives for approved sectors and special economic zones.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Tanzania Certificate of Incentives",
        country_code="TZ",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=500_000,
        min_spend_currency="USD",
        source_url="https://www.tic.go.tz/pages/certificate-of-incentives",
        source_description="Tanzania Investment Centre - Certificate of Incentives",
        clause_reference="Tanzania Investment Act, 1997, Part III Section 17",
        notes="TIC confirms foreign investors with at least USD 500,000 investment may receive a Certificate of Incentives giving access to fiscal and non-fiscal incentives such as zero import duty on capital goods and raw materials.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Eswatini Development Approval Order and SEZ Incentives",
        country_code="SZ",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="SZL",
        source_url="https://investeswatini.org.sz/incentives/",
        source_description="Eswatini Investment Promotion Authority - Incentives page",
        notes="EIPA lists a 10% corporate tax rate for 10 years under the Development Approval Order, duty-free capital goods, and SEZ incentives including tax exemption and customs/VAT relief on raw materials, equipment, and machinery.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="South Sudan Investment Promotion Act Incentives",
        country_code="SS",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="SSP",
        source_url="https://mofaic.gov.ss/investment/",
        source_description="Ministry of Foreign Affairs and International Cooperation (South Sudan) - Incentives for Investment in South Sudan",
        clause_reference="Investment Act 2009, Section 32 and Second Schedule",
        notes="Official investment page states priority sectors may receive tax exemptions and concessions on machinery, equipment, capital and profits, with special incentives available for strategic or transformational investments.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Sao Tome and Principe Investment Code Incentives",
        country_code="ST",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="EUR",
        min_qualifying_spend=50_000,
        min_spend_currency="EUR",
        source_url="https://www.investsaotome.com/incentives",
        source_description="STP Investment Hub - Incentives page",
        notes="Investment hub states the code provides total exemption from import duties on goods and equipment for new or expanding activities, 10% corporate income tax under the covered regime, and accelerated depreciation/other tax incentives for eligible investments.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Seychelles Infant Company Business Tax Exemption",
        country_code="SC",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="SCR",
        source_url="https://investmentpolicy.unctad.org/investment-policy-monitor/measures/4986/seychelles-grants-new-business-tax-exemption-to-infant-companies",
        source_description="UNCTAD Investment Policy Hub - Seychelles infant company tax exemption measure",
        clause_reference="Business Tax (Exemption of Tax for Infant Companies) Order, 2025",
        notes="UNCTAD reports the government portal order grants qualifying infant companies a five-year business-tax exemption from 1 January 2025, for businesses registered in Seychelles within the first five years of operation in covered sectors.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Niger Film Production Investment Exemption",
        country_code="NE",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XOF",
        min_qualifying_spend=2_000_000,
        min_spend_currency="XOF",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/206/niger-code-des-investissements-",
        source_description="UNCTAD Investment Policy Hub - Niger Code des investissements",
        clause_reference="Article 41",
        notes="Article 41 expressly covers film production: qualifying investors may be exempted from duties and taxes, including VAT, on production devices, construction materials, tools and equipment directly used for investment realization, with an investment floor of XOF 2 million.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Sudan Investment Encouragement Act Exemptions",
        country_code="SD",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="SDG",
        min_qualifying_spend=250_000,
        min_spend_currency="USD",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/334/sudan-the-investment-act",
        source_description="UNCTAD Investment Policy Hub - Sudan Investment (Encouragement) Act, 2021",
        clause_reference="Articles 20-23",
        notes="The act grants strategic projects business-profits tax exemptions, VAT exemptions on capital expenditures, customs-duty exemptions on capital equipment and certain transport conveyances, and licenses foreign investors from a minimum USD 250,000 deposit requirement.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Libya Investment Promotion Law Incentives",
        country_code="LY",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="LYD",
        min_qualifying_spend=5_000_000,
        min_spend_currency="LYD",
        source_url="https://www.embassyoflibya.ca/pages/investments-en",
        source_description="Embassy of Libya - investments page summarizing Libyan investment law privileges",
        notes="Embassy summary states approved projects can receive exemption from taxes, customs duties, import fees and related charges on machinery/equipment and for operating inputs for five years, with export exemptions for commodities produced for export.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="El Salvador Cinematography Services Regime",
        country_code="SV",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=250_000,
        min_spend_currency="USD",
        source_url="https://www.asamblea.gob.sv/node/13839",
        source_description="Asamblea Legislativa de El Salvador - reforms to the International Services Law",
        clause_reference="Cinematography services in centers of services",
        notes="Official Assembly page states cinematography post-production services qualify within centers of services, with a minimum US$250,000 investment, 20 permanent jobs, a written contract of at least six months, and a business plan. The law refers to associated fiscal incentives when requirements are met.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Venezuela National Cinematography Law Incentives",
        country_code="VE",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="VES",
        source_url="https://www.wipo.int/wipolex/en/legislation/details/10224",
        source_description="WIPO Lex - National Cinematography Law, Venezuela",
        clause_reference="Articles 40, 57, 58 and 59",
        notes="The law creates FONPROCINE and authorizes support for national productions, including deduction of the full value of investments/donations to approved projects from income tax, a five-year income-tax exemption for production/distribution/exhibition of national non-advertising works, and up to 25% exoneration of tax obligations for coproduction contributions.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Rwanda Registered Investor Incentives",
        country_code="RW",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=50_000,
        min_spend_currency="USD",
        source_url="https://rdb.rw/invest/",
        source_description="Rwanda Development Board - official investment incentives overview",
        notes="RDB states registered investors can access preferential corporate income tax rates, accelerated depreciation, duty-free imports of machinery and inputs, capital-gains exemptions, and immigration incentives for qualifying projects.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Malawi Investment and Export Incentives",
        country_code="MW",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="MWK",
        source_url="https://www.mitc.mw/invest/index.php/one-stop-services-center/tax-incentives",
        source_description="Malawi Investment and Trade Centre - Tax Incentives overview",
        notes="MITC states Malawi offers 100% investment allowance on new plant and machinery, no minimum turnover tax, exemption of duty/excise/VAT on raw materials and industrial machinery, and tax allowances for exporters and EPZ users under the relevant Acts.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Mauritania Investment Code Incentives",
        country_code="MR",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="MRU",
        min_qualifying_spend=5_000_000,
        min_spend_currency="MRU",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/571/mauritania-investment-code",
        source_description="UNCTAD Investment Policy Hub - Mauritania Investment Code (2025)",
        clause_reference="Articles 22-24",
        notes="UNCTAD text states the 2025 Investment Code grants customs/VAT reductions on imported equipment, tax credits for vocational training, and special incentives for structuring investments; export-zone companies must meet investment, job-creation, and export-share thresholds.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Liberia National Investment Commission Incentives",
        country_code="LR",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=500_000,
        min_spend_currency="USD",
        source_url="https://www.investliberia.gov.lr/invest-in-liberia/faqs/",
        source_description="Liberia National Investment Commission - Investment Incentives FAQs",
        clause_reference="Economic Empowerment Tax Amendment Act of 2016, Section 16",
        notes="NIC FAQ says qualifying investments of at least USD 500,000 can receive duty exemptions on machinery/equipment and capital spare parts, tax holidays, and preferential electricity tariffs when available.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Kenya Film Camera Import Duty and VAT Waiver",
        country_code="KE",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="KES",
        source_url="https://kenyafilmcommission.go.ke/industry-development/filming-requirements/",
        source_description="Kenya Film Commission - Filming requirements and tax waiver guidance",
        notes="Official KFC guidance states that current import duty of 25% and VAT of 16% on television cameras, digital cameras, and video camera recorders have been removed under the national waiver framework for film production equipment.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Guinea-Bissau Investment Code Incentives",
        country_code="GW",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XOF",
        min_qualifying_spend=34_000,
        min_spend_currency="USD",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/260/guinea-bissau-investment-code",
        source_description="UNCTAD Investment Policy Hub - Guinea-Bissau Investment Code",
        clause_reference="Articles 10-15",
        notes="The code provides customs duty and sales-tax exemptions on capital equipment during the investment phase for projects above USD 34,000 and gradual business-tax reductions over a maximum seven-year operation phase, with enhanced incentives for very large projects via investment contracts.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Kosovo Production Rebate for International Audiovisual Projects",
        country_code="XK",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_currency="EUR",
        source_url="https://qkk-rks.com/en-us/rebate/",
        source_description="Kosovo Cinematography Center - Production Rebate page",
        clause_reference="Regulation (GRK) No. 33/2024",
        notes="Kosovo's official rebate page states a 30% rebate on eligible expenses incurred in Kosovo for international audiovisual productions, with benefits (including any public funding) capped at 50% of the project's overall budget.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Papua New Guinea Investment Promotion Incentives",
        country_code="PG",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="PGK",
        source_url="https://facilitation.nto.gov.pg/ipa/",
        source_description="Papua New Guinea Investment Promotion Authority - trade facilitation and incentives overview",
        notes="Official IPA materials state PNG investment incentives and benefits include tax exemptions, duty exemptions, and land-rent concessions, implemented through an investment-application review and approval process.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Vanuatu Friendly Tax Regime and Import Duty Exemptions",
        country_code="VU",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="VUV",
        source_url="https://investvanuatu.vu/tax/",
        source_description="Vanuatu Foreign Investment Promotion Agency - Tax page",
        notes="Official Vanuatu investment page states there is no income or company tax, no capital gains tax, no withholding tax, and import-duty exemptions are available in tourism, manufacturing/processing, and mineral exploration sectors.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Lesotho Manufacturing and Investment Fiscal Incentives",
        country_code="LS",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="LSL",
        source_url="https://invest.sadc.int/how-invest/lesotho",
        source_description="SADC Investment Portal - Lesotho country investment incentives",
        notes="Lesotho offers a 10% corporate income tax rate for manufacturing profits, no withholding tax on dividends paid by manufacturing firms, a 15% WHT cap on certain charges, and a 125% training-cost deduction for tax purposes.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Mozambique Investment Law Fiscal and Customs Incentives",
        country_code="MZ",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="MZN",
        source_url="https://apiex.gov.mz/wp-content/uploads/2025/04/Investment-Guide-Mozambique-V1-1.pdf",
        source_description="APIEX Mozambique - Investment Guide 2025",
        notes="APIEX guide states Mozambique grants customs/VAT exemptions on Class K capital goods, investment tax credits, accelerated depreciation, and special regimes for tourism, SEZs, and industrial free zones.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Namibia Export Processing Zone Incentives",
        country_code="NA",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="NAD",
        source_url="https://www.nipdb.com/investment-faq",
        source_description="Namibia Investment Promotion and Development Board - Investment FAQ",
        notes="NIPDB states the only incentives currently offered at large are EPZ-regime related; EPZ enterprises generally receive customs, VAT, and corporate-tax exemptions under the export-processing-zone framework.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Togo Investment Code Incentives",
        country_code="TG",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XOF",
        min_qualifying_spend=50_000_000,
        min_spend_currency="XOF",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/148/togo-investment-code",
        source_description="UNCTAD Investment Policy Hub - Togo Investment Code (law text and articles)",
        clause_reference="Articles 24-29",
        notes="The investment code grants customs, VAT, and direct-tax exemptions for approved investments, including duty-free treatment on qualifying imported equipment and tax abatements tied to the investment regime.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Chad Investment Charter Incentives",
        country_code="TD",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XAF",
        min_qualifying_spend=250_000_000,
        min_spend_currency="XAF",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/50/chad-investment-charter",
        source_description="UNCTAD Investment Policy Hub - Chad Investment Charter",
        clause_reference="Articles 20-23",
        notes="The charter grants customs exemptions on materials/equipment needed for production and transformation, plus tax exemptions for approved new or expanding projects and longer exemption periods in designated zones.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Senegal Investment Code Incentives (Cinema-Eligible Sector)",
        country_code="SN",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XOF",
        min_qualifying_spend=100_000_000,
        min_spend_currency="XOF",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/77/senegal-investment-code",
        source_description="UNCTAD Investment Policy Hub - Senegal Investment Code",
        clause_reference="Articles 2, 17, and 18",
        notes="The Senegal Investment Code expressly includes cinema and audiovisual production among eligible industrial/cultural sectors. Approved investments over XOF 100 million can receive customs-duty exemption and VAT suspension during the realization phase.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Sierra Leone NIB General Investment Incentives",
        country_code="SL",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=5_000_000,
        min_spend_currency="USD",
        source_url="https://nib.gov.sl/investment-incentives/",
        source_description="National Investment Board of Sierra Leone - Investment Incentives",
        notes="NIB lists general tax incentives including import-duty exemptions, customs facilitation, and tax holidays under the national investment framework. "
              "The official portal also notes three-year corporate tax holidays for qualifying SEZ investors and duty-free import for plants and machinery.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Mauritius Film Rebate Scheme (EDB)",
        country_code="MU",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_currency="USD",
        min_qualifying_spend=100_000,
        min_spend_currency="USD",
        conditional_rates=[
            {
                "condition": "eligible_big_project_band",
                "rate": 40.0,
                "note": "Guidelines provide an upper 40% rebate band for qualifying higher-expenditure categories."
            }
        ],
        source_url="https://edbmauritius.org/wp-content/uploads/2022/10/Guideline-Online-Application-FRS.pdf",
        source_description="Economic Development Board Mauritius - Film Rebate Scheme online application guideline",
        clause_reference="Page 6 and application conditions",
        notes="Guideline sets minimum QPE thresholds by category and provides rebate bands from 30% up to 40% on qualifying production expenditure in Mauritius.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Fiji Film Tax Rebate",
        country_code="FJ",
        incentive_type="cash_rebate",
        rebate_percent=20.0,
        max_cap_amount=4_000_000,
        max_cap_currency="FJD",
        min_qualifying_spend=250_000,
        min_spend_currency="FJD",
        source_url="https://film-fiji.com/incentives-and-legislation/20-film-tax-rebate/",
        source_description="Film Fiji (government statutory body) - 20% Film Tax Rebate",
        clause_reference="Program overview; Income Tax (Film-making and Audio-visual Incentives) Regulations 2016 reference",
        notes="Official Film Fiji guidance states 20% cash rebate on Total Fiji Expenditure for eligible productions, with minimum FJD 250,000 qualifying spend and maximum rebate of FJD 4 million.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Uzbekistan Foreign Film Rebate Program (Tourism Committee Framework)",
        country_code="UZ",
        incentive_type="cash_rebate",
        rebate_percent=10.0,
        max_cap_amount=4_000_000_000,
        max_cap_currency="UZS",
        conditional_rates=[
            {
                "condition": "involves_creative_youth_from_culture_art_institutions",
                "rate": 20.0,
                "note": "Rate increases to 20% when foreign projects involve creative youth from national culture and arts educational institutions."
            },
            {
                "condition": "features_unique_natural_sites_or_historical_cultural_heritage",
                "rate": 25.0,
                "note": "Rate increases to 25% when production prominently uses unique natural locations and historical-cultural monuments."
            }
        ],
        source_url="https://president.uz/oz/lists/view/8692",
        source_description="President of Uzbekistan - decision on organizing Tourism Committee activities (20 Nov 2025)",
        clause_reference="Measures effective from 1 January 2026 and 1 January 2028",
        notes="Official decision summary states that from 1 January 2026, foreign film companies can receive rebates on expenses in Uzbekistan at 10%, 20%, or 25% under specified conditions. "
              "From 1 January 2028, reimbursement under this mechanism is capped at UZS 4 billion per foreign film company.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Taiwan Subsidy for Foreign Motion Picture and TV Drama Production",
        country_code="TW",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=30_000_000,
        max_cap_currency="TWD",
        min_qualifying_spend=3_000_000,
        min_spend_currency="TWD",
        source_url="https://law.moc.gov.tw/EngLawContent.aspx?id=66&lan=E",
        source_description="Ministry of Culture (Taiwan) Directions for Funding Foreign Motion Pictures and TV Dramas",
        clause_reference="Articles 4 and 5",
        notes="Official directions provide subsidy up to 30% of approved production expenditure in Taiwan, capped at TWD 30 million. "
              "Applicants must meet minimum Taiwan spend thresholds (TWD 3 million for motion pictures, TWD 8 million for TV dramas).",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Singapore On-Screen Fund (IMDA/STB)",
        country_code="SG",
        incentive_type="fund",
        rebate_percent=30.0,
        max_cap_currency="SGD",
        eligible_formats=["feature_fiction", "series"],
        source_url="https://www.imda.gov.sg/resources/press-releases-factsheets-and-speeches/press-releases/2023/imda-and-stb-launch-s%2410-million-singapore-on-screen-fund-to-inspire-travel-to-singapore-through-tv-series-and-films",
        source_description="IMDA/STB press release on Singapore On-Screen Fund",
        notes="Joint S$10 million fund supports selected TV/film projects that spotlight Singapore. Successful projects can receive funding support of up to 30% of qualifying Singapore-related production and marketing costs. Application is by invite.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Vietnam Film Development Support Fund (State-owned fund model)",
        country_code="VN",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="VND",
        source_url="https://datafiles.chinhphu.vn/cpp/files/vbpq/2023/01/131-nd.signed.pdf",
        source_description="Government Decree 131/2022/ND-CP detailing the Law on Cinema",
        clause_reference="Article 20; funding sources listed in implementation clauses",
        notes="Decree 131/2022 establishes the Film Development Support Fund as a 100% state-owned one-member company under the Ministry of Culture, Sports and Tourism. "
              "Fund sources include state capital, voluntary domestic/foreign contributions and other lawful revenues.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Cambodia Temporary Import Tax Exemption for Approved Film Equipment",
        country_code="KH",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="KHR",
        source_url="https://cambodia-cfc.org/administrative-process/",
        source_description="Cambodia Film Commission administrative process - Temporary import license",
        notes="Cambodia Film Commission states that approved foreign productions can obtain a temporary import license allowing import/export of film equipment free of taxes for a limited period. "
              "General film permit from Ministry of Culture and Fine Arts is required first.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Philippines Film Location Incentive Program (FLIP)",
        country_code="PH",
        incentive_type="cash_rebate",
        rebate_percent=20.0,
        max_cap_amount=25_000_000,
        max_cap_currency="PHP",
        min_qualifying_spend=20_000_000,
        min_spend_currency="PHP",
        conditional_rates=[
            {
                "condition": "cultural_merit_test_pass",
                "rate": 25.0,
                "note": "Projects passing the cultural merit test may receive a 5% bonus, with cap raised to PHP 30 million."
            }
        ],
        source_url="https://fdcp.ph/programs/film-incentives/film-location-incentive-program",
        source_description="FDCP Film Philippines Office - FLIP official program page",
        notes="Selective cash rebate for qualified international projects serviced by Filipino production companies. "
              "Official page states 20% rebate capped at PHP 25 million, with cultural bonus up to 25% capped at PHP 30 million.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Philippines International Co-Production Fund (ICOF)",
        country_code="PH",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=10_000_000,
        max_cap_currency="PHP",
        eligible_formats=["feature_fiction", "documentary", "series", "animation", "short"],
        source_url="https://fdcp.ph/programs/film-philippines-office/international-co-production-fund",
        source_description="FDCP Film Philippines Office - ICOF official program page",
        notes="Selective fund for qualified Filipino companies co-producing with foreign partners. "
              "FDCP Film Philippines incentive announcements and incentives portal state support up to PHP 10 million per project.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Japan JLOX+ Location Incentive Program",
        country_code="JP",
        incentive_type="cash_rebate",
        rebate_percent=50.0,
        max_cap_amount=1_000_000_000,
        max_cap_currency="JPY",
        min_qualifying_spend=500_000_000,
        min_spend_currency="JPY",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        source_url="https://www.vipo.or.jp/en/location-project/",
        source_description="VIPO JLOX+ Location Incentive Program (official English guidance)",
        clause_reference="Key Points; Criteria 3(1); Maximum Subsidy Amount",
        notes="Program provides 50% cash rebate on eligible Japan spend, capped at JPY 1 billion. "
              "2026 framework allows multi-year spending across two fiscal years. "
              "Requires Japan spend > 500M JPY, or Total Budget > 1B JPY with Japan spend > 200M JPY. "
              "Must apply through a Japanese production company.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Israel Film Fund - Feature Film Investment Schemes",
        country_code="IL",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=2_000_000,
        max_cap_currency="ILS",
        min_spend_percent=50.0,
        local_crew_min_percent=70.0,
        eligible_formats=["feature_fiction", "animation"],
        source_url="https://www.filmfund.org.il/Upload/Media/Tinymce/Files/IFF%20en2024.pdf",
        source_description="The Investment Schemes of the Israel Film Fund (2024)",
        clause_reference="Production Investment Guidelines; Film (Recognition of a Film as an Israeli Film) Regulations, 5765-2005",
        notes="Fund's main scheme invests NIS 2 million per feature; debut scheme supports up to NIS 1 million. "
              "Guidelines reference Israeli film recognition rules including 50% budget spend in Israel and 70% of wage budget paid to Israeli residents.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="China National Film Development Special Fund",
        country_code="CN",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="CNY",
        source_url="https://www.chinafilm.gov.cn/xxgk/zcfg/gfxwj/dyjs/201909/t20190925_1533.html",
        source_description="National Film Administration - Measures on collection and use of National Film Development Special Fund",
        clause_reference="Article 16",
        notes="Article 16 lists official support uses, including support for cinema construction/equipment, support for key production base development, "
              "awards for outstanding domestic film production/distribution/exhibition, and support for films with cultural/artistic innovation.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Shanghai Film Development Special Fund",
        country_code="CN",
        region="Shanghai",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_currency="CNY",
        source_url="https://www.shanghai.gov.cn/202523bmgfxwj/20251205/909831c9e2be4d9cb47e0e9c2e592072.html",
        source_description="Shanghai Film Bureau and Shanghai Finance Bureau notice on Shanghai Film Development Special Fund management (2025)",
        notes="Shanghai issued updated management rules for the municipal film development special fund to support Shanghai's 'City of Film' strategy under national and municipal film finance regulations. 2026 plan includes 15% tax rebate for locally-based film companies and post-production grants.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="China Hainan Free Trade Port 'Double 15' Tax Policy",
        country_code="CN",
        region="Hainan",
        incentive_type="tax_rebate",
        rebate_percent=None,
        max_cap_currency="CNY",
        source_url="https://www.hnftp.gov.cn/",
        source_description="Hainan Free Trade Port official portal - tax incentives",
        notes="Reduced 15% Corporate Income Tax (CIT) for encouraged industries (including film) and 15% Individual Income Tax (IIT) cap for high-end talent. Requires substantive operations in Hainan.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="China Wanda Studios (Qingdao) Production Rebate",
        country_code="CN",
        region="Qingdao",
        incentive_type="cash_rebate",
        rebate_percent=40.0,
        max_cap_currency="CNY",
        source_url="http://www.wandastudios.com/",
        source_description="Wanda Studios Qingdao - production incentives",
        notes="Up to 40% cash rebate on qualified production spend for international projects utilizing Wanda Studios facilities in Qingdao.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Hong Kong-Europe-Asian Film Collaboration Funding Scheme",
        country_code="HK",
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=9_000_000,
        max_cap_currency="HKD",
        source_url="https://www.fdc.gov.hk/",
        source_description="Hong Kong Film Development Council (FDC) guidelines",
        notes="Grant up to HKD 9 million for co-productions. Requires at least 30% of below-the-line expenditure in Hong Kong and qualified film practitioners from both HK and partner region.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="Hong Kong Production Financing Scheme 2.0",
        country_code="HK",
        incentive_type="fund",
        rebate_percent=40.0,
        max_cap_amount=25_000_000,
        max_cap_currency="HKD",
        eligible_formats=["feature_fiction", "animation"],
        source_url="https://www.fdc.gov.hk/en/services/services2.htm",
        source_description="Hong Kong FDC — Film Production Financing Scheme 2.0",
        notes="Launched 15 January 2025 (not time-limited). Government contributes 40% of approved "
              "budget for qualifying productions (budget ≤HKD 25M). Applicants must be HK-incorporated. "
              "All applications with passing scores receive funding. Replaces the previous scheme.",
        local_producer_required=True,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # INDIA — State-Level Film Incentives
    # -------------------------------------------------------------------------
    inc(
        name="India Maharashtra Film Subsidy Scheme",
        country_code="IN",
        region="Maharashtra",
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=4_000_000,
        max_cap_currency="INR",
        source_url="https://filminformation.com/featured/maharashtra-govt-s-film-subsidy-available-to-all-22-october-2024/",
        source_description="Maharashtra Government film subsidy scheme (revised Oct 2024)",
        notes="Fixed-amount grants (not percentage rebate): Rs 15-20 lakh production start subsidy, "
              "plus Rs 10-40 lakh based on screening committee score (A/B/C categories). "
              "Primarily targets Marathi-language productions. Producer must be member of recognised association. "
              "Separate tax exemptions and location fee concessions for Marathi films.",
        local_producer_required=True,
        last_verified="2026-03",
    ),
    inc(
        name="India Rajasthan Film Tourism Promotion Policy Subsidy",
        country_code="IN",
        region="Rajasthan",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=30_000_000,
        max_cap_currency="INR",
        source_url="https://traveltradejournal.com/rajasthan-launches-film-tourism-promotion-policy-2025-with-subsidies-up-to-%E2%82%B93-crore/",
        source_description="Rajasthan Film Tourism Promotion Policy 2025 (released Dec 24, 2025)",
        notes="Up to 30% subsidy on qualifying Rajasthan production expenditure (increased from 15% in 2022 policy). "
              "Caps: Rs 3 crore features, Rs 2 crore web series/documentaries, Rs 1.5 crore TV serials. "
              "30%+ screen time for Rajasthan locations or 50%+ shooting days in state for full eligibility. "
              "100% location fee reimbursement at government sites for up to 5 days.",
        local_producer_required=False,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # SOUTH AFRICA — Domestic Production Incentive
    # -------------------------------------------------------------------------
    inc(
        name="South Africa Domestic Film and Television Production Incentive",
        country_code="ZA",
        incentive_type="cash_rebate",
        rebate_percent=35.0,
        max_cap_amount=50_000_000,
        max_cap_currency="ZAR",
        min_qualifying_spend=1_500_000,
        min_shoot_days=14,
        conditional_rates=[
            {
                "condition": "bee_compliant",
                "rate": 40.0,
                "note": "Additional 5% (total 40%) for 30%+ black SA HODs and 30%+ QSAPE from 51% black-owned entities."
            }
        ],
        source_url="https://www.thedtic.gov.za/financial-and-non-financial-support/incentives/film-incentive/sa-film-tv-production-and-co-production-sa-film/",
        source_description="DTIC — SA Film & TV Production and Co-Production Incentive",
        notes="35% rebate on QSAPE for domestic or official co-productions. "
              "+5% B-BBEE bonus (total 40%). Cap ZAR 50M. Min QSAPE ZAR 1.5M (ZAR 500K for docs). "
              "Min 14 calendar days and 60% of principal photography in SA. "
              "75% of total budget must be QSAPE. Majority IP must be SA-owned. "
              "Separate from the Foreign Film incentive (25%).",
        min_spend_percent=75.0,
        local_producer_required=True,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # SOUTH KOREA — Seoul Film Commission
    # -------------------------------------------------------------------------
    inc(
        name="Seoul Film Commission Location Incentive",
        country_code="KR",
        region="Seoul",
        incentive_type="cash_rebate",
        rebate_percent=30.0,
        max_cap_amount=300_000_000,
        max_cap_currency="KRW",
        min_shoot_days=4,
        eligible_formats=["feature_fiction", "series", "documentary"],
        source_url="http://english.seoulfc.or.kr/ict/pcs/",
        source_description="Seoul Film Commission — Production Cost Support for international productions",
        notes="Up to 30% reimbursement on Seoul production budget (10-30% based on marketing/economic impact assessment). "
              "Max KRW 300M per project. Min 4 shooting days in Seoul, min 60 min running time. "
              "KRW 300M cap waived if: >KRW 3B spent in Seoul, >50% shot in Seoul, or distribution in 5+ countries. "
              "Reimbursement for shooting-related expenses only. Separate from national KOFIC incentive.",
        local_producer_required=False,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # QUICK COUNTRY SWEEP: remaining no-coverage countries
    # -------------------------------------------------------------------------
    inc(
        name="Gambia Investment and Export Promotion Agency Act Incentives",
        country_code="GM",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=250_000,
        min_spend_currency="USD",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/261/gambia-investment-and-export-promotion-agency-act",
        source_description="UNCTAD Investment Laws Navigator - The Gambia Investment and Export Promotion Agency Act (2015)",
        clause_reference="Investment and Export Promotion Agency Act 2015; investment incentives and EPZ provisions",
        notes="The Act provides tax holidays, depreciation allowance, withholding tax relief on dividends, import sales tax waivers for qualifying manufacturing inputs, and export-zone incentives. UNCTAD notes a minimum USD 250,000 investment threshold for the incentive package.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Guinea Investment Code Incentives",
        country_code="GN",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="GNF",
        min_qualifying_spend=200_000_000,
        min_spend_currency="GNF",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/176/guinea-investment-code",
        source_description="UNCTAD Investment Laws Navigator - Code des Investissements (2015)",
        clause_reference="Article 32",
        notes="The code covers industrial, tourism, ICT and cultural industries, including cinema and audiovisual production, and grants fiscal and customs advantages for approved creation or expansion projects.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Comoros Investment Code Incentives",
        country_code="KM",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="KMF",
        min_qualifying_spend=5_000_000,
        min_spend_currency="KMF",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/378/comoros-investment-law-2007",
        source_description="UNCTAD Investment Laws Navigator - Law N\u00b007-0010/AU Containing the Investment Code",
        clause_reference="Articles 17-21",
        notes="Scheme A and B provide reduced import fees, turnover-tax exemptions, income-tax deductions and rural-area extensions for approved investment programmes. The law also stabilizes the regime against later duty or tax changes.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Equatorial Guinea Investment Regime Incentives",
        country_code="GQ",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="XAF",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/375/equatorial-guinea-equatoria-guinea-investment-law-",
        source_description="UNCTAD Investment Laws Navigator - Law no. 7/1992 on the Investment Regime in the Republic of Equatorial Guinea",
        clause_reference="Articles 3, 9-11",
        notes="Approved investment projects automatically benefit from statutory advantages, including exemption from pre-licensing requirements for imports/exports and relief from ad hoc charges on imports or exports. The law also provides permits for local and foreign staff needed for the project.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Haiti Investment Code Incentives",
        country_code="HT",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/84/haiti-investment-code",
        source_description="UNCTAD Investment Laws Navigator - Code des Investissements (1989)",
        clause_reference="Articles 18-21, 30-37, 44-55",
        notes="The code creates priority and privileged regimes with fiscal and customs exemptions for approved investments in export-oriented, agricultural, industrial, tourism and free-zone activities. It also protects profit transfers and equal treatment for investors.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Suriname Investment Law Incentives",
        country_code="SR",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=5_000,
        min_spend_currency="USD",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/83/suriname-investment-law",
        source_description="UNCTAD Investment Laws Navigator - Investeringswet 2001",
        clause_reference="Articles 4-6, 10-13",
        notes="The law provides tax facilities for approved investments, including arbitrary depreciation, fictive-interest deductions, investment deductions in designated regions, import-duty exemptions and VAT exemptions for qualifying capital goods.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Solomon Islands Special Economic Zones Act Incentives",
        country_code="SB",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        min_qualifying_spend=5_000_000,
        min_spend_currency="USD",
        source_url="https://www.investsolomons.gov.sb/investment-trade-framework/special-economic-zones-act-2025",
        source_description="InvestSolomons - Special Economic Zones Act 2025",
        clause_reference="Special Economic Zones Act 2025",
        notes="The 2025 SEZ Act sets a USD 5M minimum for foreign investors and provides corporate-tax, withholding-tax, PAYE, stamp-duty, import duty and local-levy exemptions, plus work-permit and profit-repatriation facilities for eligible projects.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Somalia Foreign Investment Law Incentives",
        country_code="SO",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/538/somalia-foreign-investment-law",
        source_description="UNCTAD Investment Laws Navigator - Federal Republic of Somalia Foreign Investment Law",
        clause_reference="Articles 15, 17, 18, 24",
        notes="Foreign investments are eligible for incentives and facilities, including long-term leases up to 99 years for substantial investments; the law also guarantees equal treatment, profit repatriation and access to foreign personnel visas.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Honduras Investment Promotion and Protection Law Incentives",
        country_code="HN",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="USD",
        source_url="https://cni.hn/consejo-nacional-de-inversiones-de-honduras/servicios-legales/",
        source_description="Consejo Nacional de Inversiones - LPPI benefits overview",
        clause_reference="Decreto Legislativo 51-2011",
        notes="Official CNI guidance says the law offers fiscal benefits, including accelerated depreciation and relief tied to pre-operating expenses, for qualifying new projects declared of strategic interest. It also highlights legal security for real-estate acquisition.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Madagascar Investment Law 2023",
        country_code="MG",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="MGA",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/367/madagascar-madagascar-investment-law-2023",
        source_description="UNCTAD Investment Laws Navigator - Law No. 2023-002 on investments in Madagascar",
        clause_reference="Articles 1-4, 18-20",
        notes="The 2023 law defines incentives, establishes freedom of investment and equal treatment, and allows long leases for foreign investors. It is a framework law rather than a film-specific rebate, so detailed fiscal benefits depend on sectoral rules and implementing measures.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
    inc(
        name="Tuvalu Foreign Direct Investment Act",
        country_code="TV",
        incentive_type="tax_exemption",
        rebate_percent=None,
        max_cap_currency="AUD",
        source_url="https://investmentpolicy.unctad.org/investment-laws/laws/324/tuvalu-foreign-direct-investment-act",
        source_description="UNCTAD Investment Laws Navigator - Tuvalu Foreign Direct Investment Act",
        clause_reference="Sections 2 and 9",
        notes="The Act is a facilitation framework for foreign direct investment. It creates a board and allows regulations to define specifically encouraged investments, but it does not itself set a film-specific rebate or quantified incentive in the text reviewed.",
        local_producer_required=False,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # GREECE — Regional
    # -------------------------------------------------------------------------
    # Thessaloniki: No dedicated city-level production fund verified.
    # Greece's 40% cash rebate is national (EKOME). Thessaloniki Film Festival
    # operates development support but not a regional production fund.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # MULTILATERAL FUNDS
    # -------------------------------------------------------------------------
    inc(
        name="Eurimages Co-production Support",
        country_code="FR",  # Headquartered in Strasbourg; applies to 39+ member states
        incentive_type="fund",
        rebate_percent=None,
        max_cap_amount=500_000,
        eligible_formats=["feature_fiction", "documentary", "animation"],
        source_url="https://www.coe.int/en/web/eurimages/co-production-funding-aims-and-eligibility",
        source_description="Council of Europe — Eurimages Co-production Support",
        notes="Soft loan (repayable from first € of net receipts) up to €500k or 17% of total production cost. "
              "Requires official co-production between at least two member states. "
              "Competitive selection based on artistic merit and circulation potential.",
        last_verified="2026-03",
    ),
    inc(
        name="Ibermedia Co-production Grant",
        country_code="ES",  # Associated with Spain/Portugal/Latin America
        incentive_type="grant",
        rebate_percent=None,
        max_cap_amount=150_000,
        max_cap_currency="USD",
        eligible_formats=["feature_fiction", "documentary", "animation"],
        source_url="https://www.programaibermedia.com/nuestras-convocatorias/",
        source_description="Programa Ibermedia — Co-production support",
        notes="Selective grant for co-productions between Ibero-American member states. "
              "Max $150k per project. Requires at least two member countries. "
              "Focus on regional integration and cultural diversity.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # AUSTRALIA - State Incentives
    # -------------------------------------------------------------------------
    inc(
        name="Australia - Made in NSW Fund",
        country_code="AU",
        region="New South Wales",
        incentive_type="grant",
        rebate_percent=10.0,  # Effective uplift often targeted at 10%
        max_cap_currency="AUD",
        source_url="https://www.screen.nsw.gov.au/funding/production-support/made-in-nsw",
        source_description="Screen NSW — Made in NSW Fund",
        notes="Discretionary grant for high-end TV drama and features. "
              "Stackable with Federal Location/Producer offsets. "
              "Requires significant spend and employment in NSW.",
        stacking_allowed=True,
        last_verified="2026-03",
    ),
    inc(
        name="Australia - VICSCREEN Victorian Screen Incentive (VSI)",
        country_code="AU",
        region="Victoria",
        incentive_type="grant",
        rebate_percent=10.0,
        max_cap_currency="AUD",
        source_url="https://vicscreen.vic.gov.au/funding/production/#victorian-screen-incentive",
        source_description="VicScreen — Victorian Screen Incentive",
        notes="Grant for projects spending at least AUD 3.5M in Victoria. "
              "Usually calculated as up to 10% of Victorian QAPE. "
              "Stackable with federal incentives. Competitive application.",
        stacking_allowed=True,
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # CANADA - Quebec Provincial Incentives
    # -------------------------------------------------------------------------
    inc(
        name="Quebec - SODEC Film and Television Tax Credit",
        country_code="CA",
        region="Quebec",
        incentive_type="tax_credit",
        rebate_percent=20.0,
        rebate_applies_to="qualifying_spend",
        max_cap_currency="CAD",
        conditional_rates=[
            {"condition": "french_language_bonus", "rate": 28.0, "note": "French-language productions can reach 28% base rate."},
            {"condition": "vfx_post_bonus", "rate": 16.0, "field": "bonus_percent", "note": "Additional 16% bonus for computer-aided animation and special effects."}
        ],
        source_url="https://sodec.gouv.qc.ca/en/industries/film-and-television/tax-credits/",
        source_description="SODEC Quebec - Tax Credits",
        notes="Refundable tax credit on all eligible Quebec expenditures (not just labor). "
              "Base rate is 20%. Bonuses for French language, regional production, and VFX can increase effective yield significantly.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # US - Louisiana State Incentives
    # -------------------------------------------------------------------------
    inc(
        name="US Louisiana Motion Picture Production Tax Credit",
        country_code="US",
        region="Louisiana",
        incentive_type="tax_credit",
        rebate_percent=25.0,
        min_qualifying_spend=300_000,
        max_cap_currency="USD",
        conditional_rates=[
            {"condition": "louisiana_screenplay_bonus", "rate": 30.0, "note": "Additional 5% bonus for using a Louisiana-based screenplay."},
            {"condition": "out_of_zone_bonus", "rate": 30.0, "note": "Additional 5% bonus for filming outside the New Orleans zone."}
        ],
        source_url="https://www.louisianaentertainment.gov/motion-picture-production-program",
        source_description="Louisiana Entertainment - Motion Picture Production Program",
        notes="Tax credit of up to 40% (25% base + various uplifts). "
              "Minimum qualifying spend of USD 300,000 for local productions, or USD 50,000 for Louisiana screenplay projects. "
              "Louisiana screenplay, out-of-zone, and visual effects uplifts are common.",
        local_producer_required=False,
        last_verified="2026-03",
    ),
]

for i in incentives:
    db.add(i)
db.commit()


# =============================================================================
# TREATIES — bilateral and multilateral
# =============================================================================

def bilateral(
    name, a, b, min_share=None, max_share=None, min_third=None,
    formats=None, creative_req=None, auth_a=None, auth_b=None,
    date_signed=None, notes="", source_url=None, source_desc=None,
    last_verified=None,
):
    return Treaty(
        name=name,
        treaty_type="bilateral",
        country_a_code=a,
        country_b_code=b,
        min_share_percent=min_share,
        max_share_percent=max_share,
        min_share_third_party=min_third,
        eligible_formats=formats or ["feature_fiction", "documentary", "series", "animation"],
        creative_contribution_required=True,
        creative_requirements_summary=creative_req or "Creative and technical contributions must be proportional to financial share.",
        competent_authority_a=auth_a,
        competent_authority_b=auth_b,
        requires_prior_approval=True,
        date_signed=date_signed,
        is_active=True,
        notes=notes,
        source_url=source_url,
        source_description=source_desc,
        last_verified=last_verified,
    )


treaties = [
    # -------------------------------------------------------------------------
    # FRANCE bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "France–Canada Coproduction Treaty",
        "FR", "CA", min_share=15, max_share=85, min_third=10,
        auth_a="CNC", auth_b="Telefilm Canada",
        date_signed="2021-07-28",
        notes="Min 15% financial share each (cinema); 20% each for TV/SVOD; "
              "10% min for third-party coproducer. Creative/technical contributions proportional to share.",
        source_url="https://www.cnc.fr/professionnels/reglementation/canadafrance--accord-de-coproduction-du-28-juillet-2021_2131203",
        source_desc="CNC — Accord France-Canada, 28 July 2021",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Germany Coproduction Treaty",
        "FR", "DE", min_share=20, max_share=80,
        auth_a="CNC", auth_b="FFA / BKM",
        notes="Min 20% financial share each. Replaces 2001 agreement.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Allemagne",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Italy Coproduction Treaty",
        "FR", "IT", min_share=20, max_share=80,
        auth_a="CNC", auth_b="MiC (Direzione Generale Cinema)",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Italie",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Belgium Coproduction Treaty",
        "FR", "BE", min_share=20, max_share=80,
        auth_a="CNC", auth_b="Centre du Cinéma et de l'Audiovisuel (FWB)",
        notes="Min 20% share each. Covers both French-speaking and Flemish Belgian communities.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Belgique",
        last_verified="2025-03",
    ),
    bilateral(
        "France–UK Coproduction Treaty",
        "FR", "GB", min_share=20, max_share=80,
        auth_a="CNC", auth_b="BFI",
        notes="Min 20% financial share each. Post-Brexit: UK-France treaty remains in force.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — Co-Production treaties; CNC — Accord France-UK",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Spain Coproduction Treaty",
        "FR", "ES", min_share=20, max_share=80,
        auth_a="CNC", auth_b="ICAA",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Espagne",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # UK bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "UK–Canada Coproduction Treaty",
        "GB", "CA", min_share=20, max_share=80,
        auth_a="BFI", auth_b="Telefilm Canada",
        notes="Min 20% financial and creative share each. Third party possible with min 10%.",
        min_third=10,
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-Canada co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–Australia Coproduction Treaty",
        "GB", "AU", min_share=20, max_share=80,
        auth_a="BFI", auth_b="Screen Australia",
        notes="Min 20% financial and creative share each.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-Australia co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–New Zealand Coproduction Treaty",
        "GB", "NZ", min_share=20, max_share=80,
        auth_a="BFI", auth_b="NZFC",
        notes="Min 20% financial and creative share each.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-New Zealand co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–Israel Coproduction Treaty",
        "GB", "IL", min_share=20, max_share=80,
        auth_a="BFI", auth_b="Israel Film Fund",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-Israel co-production treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # CANADA bilateral treaties (additional)
    # -------------------------------------------------------------------------
    bilateral(
        "Canada–Australia Coproduction Treaty",
        "CA", "AU", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="Screen Australia",
        notes="Min 15% financial share each. One of the more flexible bilateral treaties.",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Australia treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Germany Coproduction Treaty",
        "CA", "DE", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="FFA / BKM",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Germany treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Italy Coproduction Treaty",
        "CA", "IT", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="MiC",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Italy treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Netherlands Coproduction Treaty",
        "CA", "NL", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="Netherlands Film Fund",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Netherlands treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–South Korea Coproduction Treaty",
        "CA", "KR", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="KOFIC",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-South Korea treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # AUSTRALIA bilateral treaties (additional)
    # -------------------------------------------------------------------------
    bilateral(
        "Australia–Germany Coproduction Treaty",
        "AU", "DE", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="FFA / BKM",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Co-Production Program",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–Italy Coproduction Treaty",
        "AU", "IT", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="MiC",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Co-Production Program",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–South Korea Coproduction Treaty",
        "AU", "KR", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="KOFIC",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Co-Production Program",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # OTHER bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "Germany–South Africa Coproduction Treaty",
        "DE", "ZA", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="NFVF",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-South Africa co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Italy–Spain Coproduction Treaty",
        "IT", "ES", min_share=20, max_share=80,
        auth_a="MiC", auth_b="ICAA",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-Spain bilateral treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Germany–Netherlands Coproduction Treaty",
        "DE", "NL", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="Netherlands Film Fund",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-Netherlands co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Ireland–Canada Coproduction Treaty",
        "IE", "CA", min_share=20, max_share=80,
        auth_a="Screen Ireland", auth_b="Telefilm Canada",
        source_url="https://www.screenireland.ie/co-production",
        source_desc="Screen Ireland — Ireland-Canada co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Belgium–Canada Coproduction Treaty",
        "BE", "CA", min_share=15, max_share=85,
        auth_a="Centre du Cinéma (FWB) / VAF", auth_b="Telefilm Canada",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Belgium treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Netherlands–South Africa Coproduction Treaty",
        "NL", "ZA", min_share=20, max_share=80,
        auth_a="Netherlands Film Fund", auth_b="NFVF",
        source_url="https://www.filmfonds.nl/page/co-productions",
        source_desc="Netherlands Film Fund — NL-South Africa treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # FRANCE additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "France–Brazil Coproduction Treaty",
        "FR", "BR", min_share=20, max_share=80,
        auth_a="CNC", auth_b="ANCINE",
        notes="Min 20% financial share each. Covers cinema and TV.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Brésil",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Argentina Coproduction Treaty",
        "FR", "AR", min_share=20, max_share=80,
        auth_a="CNC", auth_b="INCAA",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Argentine",
        last_verified="2025-03",
    ),
    bilateral(
        "France–India Coproduction Treaty",
        "FR", "IN", min_share=20, max_share=80,
        auth_a="CNC", auth_b="Ministry of Information and Broadcasting",
        date_signed="2018-03-10",
        notes="Min 20% financial share each. Signed during President Macron's visit to India.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Inde",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Israel Coproduction Treaty",
        "FR", "IL", min_share=20, max_share=80,
        auth_a="CNC", auth_b="Israel Film Fund / Ministry of Culture",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Israël",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Morocco Coproduction Treaty",
        "FR", "MA", min_share=20, max_share=80,
        auth_a="CNC", auth_b="CCM (Centre Cinématographique Marocain)",
        notes="Min 20% financial share each. One of France's oldest bilateral treaties.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Maroc",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Tunisia Coproduction Treaty",
        "FR", "TN", min_share=20, max_share=80,
        auth_a="CNC", auth_b="CNCI Tunisia",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Tunisie",
        last_verified="2025-03",
    ),
    bilateral(
        "France–China Coproduction Treaty",
        "FR", "CN", min_share=20, max_share=80,
        auth_a="CNC", auth_b="China Film Administration",
        date_signed="2010-04-01",
        notes="Min 20% financial share each. Chinese side requires China Film Administration approval.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Chine",
        last_verified="2025-03",
    ),
    bilateral(
        "France–South Korea Coproduction Treaty",
        "FR", "KR", min_share=20, max_share=80,
        auth_a="CNC", auth_b="KOFIC",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Corée du Sud",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Australia Coproduction Treaty",
        "FR", "AU", min_share=20, max_share=80,
        auth_a="CNC", auth_b="Screen Australia",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Australie",
        last_verified="2025-03",
    ),
    bilateral(
        "France–New Zealand Coproduction Treaty",
        "FR", "NZ", min_share=20, max_share=80,
        auth_a="CNC", auth_b="NZFC",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Nouvelle-Zélande",
        last_verified="2025-03",
    ),
    bilateral(
        "France–South Africa Coproduction Treaty",
        "FR", "ZA", min_share=20, max_share=80,
        auth_a="CNC", auth_b="NFVF",
        date_signed="2010-09-01",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Afrique du Sud",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Switzerland Coproduction Treaty",
        "FR", "CH", min_share=20, max_share=80,
        auth_a="CNC", auth_b="Federal Office of Culture (BAK)",
        notes="Min 20% financial share each. Among France's most active treaty partnerships.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Suisse",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Portugal Coproduction Treaty",
        "FR", "PT", min_share=20, max_share=80,
        auth_a="CNC", auth_b="ICA (Instituto do Cinema e Audiovisual)",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Portugal",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Romania Coproduction Treaty",
        "FR", "RO", min_share=20, max_share=80,
        auth_a="CNC", auth_b="CNC Romania",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Roumanie",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Poland Coproduction Treaty",
        "FR", "PL", min_share=20, max_share=80,
        auth_a="CNC", auth_b="PISF",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Pologne",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Chile Coproduction Treaty",
        "FR", "CL", min_share=20, max_share=80,
        auth_a="CNC", auth_b="CCC Chile / CNCA",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Chili",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Colombia Coproduction Treaty",
        "FR", "CO", min_share=20, max_share=80,
        auth_a="CNC", auth_b="Proimágenes Colombia",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Colombie",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Mexico Coproduction Treaty",
        "FR", "MX", min_share=20, max_share=80,
        auth_a="CNC", auth_b="IMCINE",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Mexique",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Japan Coproduction Treaty",
        "FR", "JP", min_share=20, max_share=80,
        auth_a="CNC", auth_b="UNIJAPAN / Agency for Cultural Affairs",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Japon",
        last_verified="2025-03",
    ),
    bilateral(
        "France–Greece Coproduction Treaty",
        "FR", "GR", min_share=20, max_share=80,
        auth_a="CNC", auth_b="Greek Film Centre",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.fr/professionnels/reglementation/accords-de-coproduction",
        source_desc="CNC — Accord France-Grèce",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # NORTH AMERICA and MENA treaty expansion
    # -------------------------------------------------------------------------
    bilateral(
        "Canada–Denmark Film or Video Co-production Agreement",
        "CA", "DK",
        auth_a="Canadian Heritage / Telefilm Canada",
        auth_b="Danish Ministry of Culture / Danish Film Institute",
        source_url="https://www.treaty-accord.gc.ca/text-texte.aspx?lang=eng&id=103185",
        source_desc="Government of Canada treaty text - Canada-Denmark",
        notes="Official audiovisual coproduction agreement text published in the Government of Canada treaty database.",
        last_verified="2026-03",
    ),
    bilateral(
        "Canada–Finland Film or Video Co-production Agreement",
        "CA", "FI",
        auth_a="Canadian Heritage / Telefilm Canada",
        auth_b="Ministry of Education and Culture of Finland / Finnish Film Foundation",
        source_url="https://www.treaty-accord.gc.ca/text-texte.aspx?lang=eng&id=103196",
        source_desc="Government of Canada treaty text - Canada-Finland",
        notes="Official audiovisual coproduction agreement text published in the Government of Canada treaty database.",
        last_verified="2026-03",
    ),
    bilateral(
        "Canada–Norway Film and Video Co-production Agreement",
        "CA", "NO",
        auth_a="Canadian Heritage / Telefilm Canada",
        auth_b="Norwegian Ministry of Culture / Norwegian Film Institute",
        source_url="https://www.treaty-accord.gc.ca/text-texte.aspx?lang=eng&id=102964",
        source_desc="Government of Canada treaty text - Canada-Norway",
        notes="Official audiovisual coproduction agreement text published in the Government of Canada treaty database.",
        last_verified="2026-03",
    ),
    bilateral(
        "Canada–Luxembourg Film or Video Co-production Agreement",
        "CA", "LU",
        auth_a="Canadian Heritage / Telefilm Canada",
        auth_b="Government of Luxembourg",
        source_url="https://www.treaty-accord.gc.ca/text-texte.aspx?lang=eng&id=102970",
        source_desc="Government of Canada treaty text - Canada-Luxembourg",
        notes="Official audiovisual coproduction agreement text published in the Government of Canada treaty database.",
        last_verified="2026-03",
    ),
    bilateral(
        "Canada–Singapore Film Co-production Agreement",
        "CA", "SG",
        auth_a="Canadian Heritage / Telefilm Canada",
        auth_b="Ministry of Communications and Information / IMDA Singapore",
        source_url="https://www.treaty-accord.gc.ca/text-texte.aspx?lang=eng&id=103116",
        source_desc="Government of Canada treaty text - Canada-Singapore",
        notes="Official audiovisual coproduction agreement text published in the Government of Canada treaty database.",
        last_verified="2026-03",
    ),
    bilateral(
        "Netherlands-Indonesia Audiovisual Coproduction Treaty",
        "NL", "ID",
        auth_a="Netherlands Film Fund / Ministry of Education, Culture and Science",
        auth_b="Ministry of Culture of the Republic of Indonesia",
        date_signed="2024-12-04",
        source_url="https://wetten.overheid.nl/BWBV0007082/2026-02-04",
        source_desc="Government of the Netherlands treaty database - NL-Indonesia audiovisual coproduction agreement",
        notes="Treaty signed in Yogyakarta on 4 December 2024. Dutch treaty database records applicability from 4 February 2026 for the European part of the Kingdom.",
        last_verified="2026-03",
    ),
    bilateral(
        "France–Algeria Coproduction Treaty",
        "FR", "DZ", min_share=20, max_share=80,
        auth_a="CNC",
        auth_b="Algerian Ministry of Culture",
        source_url="https://www.cnc.fr/professionnels/reglementation/algeriefrance--accord-de-coproduction-du-4-decembre-2007_125591",
        source_desc="CNC treaty text - Algerie-France accord du 4 decembre 2007",
        notes="Article 4 sets financial participation between 20% and 80% of final film cost, with case-by-case derogation by both competent authorities.",
        last_verified="2026-03",
    ),
    bilateral(
        "France–Egypt Coproduction Treaty",
        "FR", "EG", min_share=30, max_share=70,
        auth_a="CNC",
        auth_b="Egyptian Ministry of Culture",
        source_url="https://www.cnc.fr/professionnels/reglementation/egyptefrance--accord-de-coproduction--du-31-janvier-1983_125183",
        source_desc="CNC treaty text - Egypte-France accord du 31 janvier 1983",
        notes="Article 4 sets a standard participation range of 30%-70%; minority participation can be reduced to 20% with approval by both competent authorities.",
        last_verified="2026-03",
    ),
    bilateral(
        "France–Lebanon Coproduction Treaty",
        "FR", "LB", min_share=20, max_share=80,
        auth_a="CNC",
        auth_b="Lebanese Ministry of Culture",
        source_url="https://www.cnc.fr/professionnels/reglementation/libanfrance--accord-de-coproduction--du-27-mars-2000_125291",
        source_desc="CNC treaty text - Liban-France accord signe le 3 novembre 2016",
        notes="Article 4 sets participation from 20% to 80% of total budget; by exception the minority contribution may be reduced to 10% with approval of both authorities.",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # LATAM treaty expansion (Argentina-centered network)
    # -------------------------------------------------------------------------
    bilateral(
        "Argentina–Brazil Coproduction Treaty",
        "AR", "BR", min_share=30, max_share=80,
        auth_a="INCAA",
        auth_b="ANCINE",
        source_url="https://servicios.infoleg.gob.ar/infolegInternet/anexos/20000-24999/23642/norma.htm",
        source_desc="InfoLEG Ley 24.507 - Acuerdo Argentina-Brasil",
        notes="Article 4 sets co-producer contributions between 30% and 80%, with minority share spend requirements in the minority country.",
        last_verified="2026-03",
    ),
    bilateral(
        "Argentina–Chile Coproduction Treaty",
        "AR", "CL", min_share=20, max_share=80,
        auth_a="INCAA",
        auth_b="Chilean Ministry of Cultures / audiovisual authority",
        source_url="https://servicios.infoleg.gob.ar/infolegInternet/anexos/40000-44999/43459/norma.htm",
        source_desc="InfoLEG Ley 24.817 - Acuerdo Argentina-Chile",
        notes="Article III sets contribution range between 20% and 80% and requires proportional creative/technical participation.",
        last_verified="2026-03",
    ),
    bilateral(
        "Argentina–Mexico Coproduction Treaty",
        "AR", "MX", min_share=20, max_share=80,
        auth_a="INCAA",
        auth_b="IMCINE",
        source_url="https://servicios.infoleg.gob.ar/infolegInternet/anexos/65000-69999/66606/norma.htm",
        source_desc="InfoLEG Law 24.998 publishing Argentina-Mexico coproduction agreement",
        notes="Article VII sets contribution range from 20% to 80% for each film, with competent authority approval and creative/technical balance requirements.",
        last_verified="2026-03",
    ),
    bilateral(
        "Argentina–Uruguay Coproduction Treaty",
        "AR", "UY", min_share=20, max_share=80,
        auth_a="INCAA",
        auth_b="Uruguay audiovisual authority (ACAU / ICAU)",
        source_url="https://servicios.infoleg.gob.ar/infolegInternet/anexos/70000-74999/70035/norma.htm",
        source_desc="InfoLEG treaty text - Acuerdo Argentina-Uruguay",
        notes="Article IV sets contribution range between 20% and 80%, with prior approval by both countries' competent authorities (Article III).",
        last_verified="2026-03",
    ),

    # -------------------------------------------------------------------------
    # UK additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "UK–India Coproduction Treaty",
        "GB", "IN", min_share=20, max_share=80,
        auth_a="BFI", auth_b="Ministry of Information and Broadcasting",
        date_signed="2008-10-01",
        notes="Min 20% financial and creative share each. One of the UK's most active treaty partnerships.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-India co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–China Coproduction Treaty",
        "GB", "CN", min_share=20, max_share=80,
        auth_a="BFI", auth_b="China Film Administration",
        date_signed="2014-06-01",
        notes="Min 20% financial share each. Chinese approval required via China Film Administration.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-China co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–South Africa Coproduction Treaty",
        "GB", "ZA", min_share=20, max_share=80,
        auth_a="BFI", auth_b="NFVF",
        notes="Min 20% financial and creative share each.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-South Africa co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–France Coproduction Treaty (Mini-Treaty)",
        "GB", "FR", min_share=10, max_share=90,
        auth_a="BFI", auth_b="CNC",
        notes="Separate 'mini-treaty' with lower thresholds: min 10% share. "
              "Allows more flexible structures than the main FR-UK treaty.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-France mini-treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–Jamaica Coproduction Treaty",
        "GB", "JM", min_share=20, max_share=80,
        auth_a="BFI", auth_b="Jamaica Film Commission / JAMPRO",
        notes="Min 20% financial share each.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-Jamaica co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–Brazil Coproduction Treaty",
        "GB", "BR", min_share=20, max_share=80,
        auth_a="BFI", auth_b="ANCINE",
        date_signed="2016-01-01",
        notes="Min 20% financial share each.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-Brazil co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "UK–Morocco Coproduction Treaty",
        "GB", "MA", min_share=20, max_share=80,
        auth_a="BFI", auth_b="CCM",
        notes="Min 20% financial share each.",
        source_url="https://www.bfi.org.uk/apply-british-certification-tax-relief/co-production",
        source_desc="BFI — UK-Morocco co-production treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # ITALY additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "Italy–France Coproduction Treaty",
        "IT", "FR", min_share=20, max_share=80,
        auth_a="MiC (Direzione Generale Cinema)", auth_b="CNC",
        notes="Min 20% financial share each. (Also accessible via France–Italy entry.)",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-France bilateral treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Italy–Argentina Coproduction Treaty",
        "IT", "AR", min_share=20, max_share=80,
        auth_a="MiC", auth_b="INCAA",
        notes="Min 20% financial share each. Strong historical link between Italian and Argentine cinema.",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-Argentina bilateral treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Italy–Brazil Coproduction Treaty",
        "IT", "BR", min_share=20, max_share=80,
        auth_a="MiC", auth_b="ANCINE",
        notes="Min 20% financial share each.",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-Brazil bilateral treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Italy–Tunisia Coproduction Treaty",
        "IT", "TN", min_share=20, max_share=80,
        auth_a="MiC", auth_b="CNCI Tunisia",
        notes="Min 20% financial share each.",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-Tunisia bilateral treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Italy–South Africa Coproduction Treaty",
        "IT", "ZA", min_share=20, max_share=80,
        auth_a="MiC", auth_b="NFVF",
        notes="Min 20% financial share each.",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-South Africa bilateral treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Italy–Germany Coproduction Treaty",
        "IT", "DE", min_share=20, max_share=80,
        auth_a="MiC", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-Germany bilateral treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Italy–Canada Coproduction Treaty",
        "IT", "CA", min_share=15, max_share=85,
        auth_a="MiC", auth_b="Telefilm Canada",
        notes="Min 15% financial share each. (Also accessible via Canada–Italy entry.)",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-Canada bilateral treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Italy–Switzerland Coproduction Treaty",
        "IT", "CH", min_share=20, max_share=80,
        auth_a="MiC", auth_b="BAK (Federal Office of Culture)",
        notes="Min 20% financial share each. Active treaty given shared Italian-language region (Ticino).",
        source_url="https://cinema.cultura.gov.it/en/co-productions/",
        source_desc="MiC — Italy-Switzerland bilateral treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # GERMANY additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "Germany–Brazil Coproduction Treaty",
        "DE", "BR", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="ANCINE",
        notes="Min 20% financial share each.",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-Brazil co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Germany–India Coproduction Treaty",
        "DE", "IN", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="Ministry of Information and Broadcasting",
        notes="Min 20% financial share each.",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-India co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Germany–Canada Coproduction Treaty",
        "DE", "CA", min_share=15, max_share=85,
        auth_a="FFA / BKM", auth_b="Telefilm Canada",
        notes="Min 15% financial share each. (Also accessible via Canada–Germany entry.)",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-Canada co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Germany–Switzerland Coproduction Treaty",
        "DE", "CH", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="BAK (Federal Office of Culture)",
        notes="Min 20% financial share each. Very active given shared German language.",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-Switzerland co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Germany–Austria Coproduction Treaty",
        "DE", "AT", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="Austrian Film Institute",
        notes="Min 20% financial share each. One of the most active European bilateral treaties.",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-Austria co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Germany–France Coproduction Treaty",
        "DE", "FR", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="CNC",
        notes="Min 20% financial share each. (Also accessible via France–Germany entry.)",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-France co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Germany–Turkey Coproduction Treaty",
        "DE", "TR", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="Turkish Ministry of Culture",
        notes="Min 20% financial share each.",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-Turkey co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Germany–Israel Coproduction Treaty",
        "DE", "IL", min_share=20, max_share=80,
        auth_a="FFA / BKM", auth_b="Israel Film Fund",
        notes="Min 20% financial share each.",
        source_url="https://www.ffa.de/foerderungen/koproduktionsabkommen/",
        source_desc="FFA — Germany-Israel co-production treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # CANADA additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "Canada–New Zealand Coproduction Treaty",
        "CA", "NZ", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="NZFC",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-New Zealand treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Brazil Coproduction Treaty",
        "CA", "BR", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="ANCINE",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Brazil treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Chile Coproduction Treaty",
        "CA", "CL", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="CNCA Chile",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Chile treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–China Coproduction Treaty",
        "CA", "CN", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="China Film Administration",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-China treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Colombia Coproduction Treaty",
        "CA", "CO", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="Proimágenes Colombia",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Colombia treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–India Coproduction Treaty",
        "CA", "IN", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="Ministry of Information and Broadcasting",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-India treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Israel Coproduction Treaty",
        "CA", "IL", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="Israel Film Fund",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Israel treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Japan Coproduction Treaty",
        "CA", "JP", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="UNIJAPAN",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Japan treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–South Africa Coproduction Treaty",
        "CA", "ZA", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="NFVF",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-South Africa treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Switzerland Coproduction Treaty",
        "CA", "CH", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="BAK",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Switzerland treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Morocco Coproduction Treaty",
        "CA", "MA", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="CCM",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Morocco treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Uruguay Coproduction Treaty",
        "CA", "UY", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="ICAU",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Uruguay treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Mexico Coproduction Treaty",
        "CA", "MX", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="IMCINE",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Mexico treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Cuba Coproduction Treaty",
        "CA", "CU", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="ICAIC",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Cuba treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Canada–Argentina Coproduction Treaty",
        "CA", "AR", min_share=15, max_share=85,
        auth_a="Telefilm Canada", auth_b="INCAA",
        source_url="https://telefilm.ca/en/co-productions/co-production-treaties",
        source_desc="Telefilm Canada — Canada-Argentina treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # AUSTRALIA additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "Australia–China Coproduction Treaty",
        "AU", "CN", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="China Film Administration",
        date_signed="2012-01-01",
        notes="Min 20% financial share each. Chinese approval required.",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Australia-China treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–Canada Coproduction Treaty",
        "AU", "CA", min_share=15, max_share=85,
        auth_a="Screen Australia", auth_b="Telefilm Canada",
        notes="Min 15% financial share each. (Also accessible via Canada–Australia entry.)",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Australia-Canada treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–India Coproduction Treaty",
        "AU", "IN", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="Ministry of Information and Broadcasting",
        notes="Min 20% financial share each.",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Australia-India treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–Israel Coproduction Treaty",
        "AU", "IL", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="Israel Film Fund",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Australia-Israel treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–Singapore Coproduction Treaty",
        "AU", "SG", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="IMDA Singapore",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Australia-Singapore treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–South Africa Coproduction Treaty",
        "AU", "ZA", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="NFVF",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Australia-South Africa treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–Ireland Coproduction Treaty",
        "AU", "IE", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="Screen Ireland",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Australia-Ireland treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Australia–France Coproduction Treaty",
        "AU", "FR", min_share=20, max_share=80,
        auth_a="Screen Australia", auth_b="CNC",
        notes="Min 20% financial share each. (Also accessible via France–Australia entry.)",
        source_url="https://www.screenaustralia.gov.au/co-production/co-production-program",
        source_desc="Screen Australia — Australia-France treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SPAIN additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "Spain–Argentina Coproduction Treaty",
        "ES", "AR", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="INCAA",
        notes="Min 20% financial share each. One of Spain's most active bilateral partnerships.",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-Argentina co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Spain–Brazil Coproduction Treaty",
        "ES", "BR", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="ANCINE",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-Brazil co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Spain–Chile Coproduction Treaty",
        "ES", "CL", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="CNCA Chile",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-Chile co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Spain–Colombia Coproduction Treaty",
        "ES", "CO", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="Proimágenes Colombia",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-Colombia co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Spain–Mexico Coproduction Treaty",
        "ES", "MX", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="IMCINE",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-Mexico co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Spain–Portugal Coproduction Treaty",
        "ES", "PT", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="ICA",
        notes="Min 20% financial share each. Iberian co-productions benefit from shared cultural proximity.",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-Portugal co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Spain–Cuba Coproduction Treaty",
        "ES", "CU", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="ICAIC",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-Cuba co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Spain–Morocco Coproduction Treaty",
        "ES", "MA", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="CCM",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-Morocco co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Spain–India Coproduction Treaty",
        "ES", "IN", min_share=20, max_share=80,
        auth_a="ICAA", auth_b="Ministry of Information and Broadcasting",
        date_signed="2012-10-01",
        notes="Min 20% financial share each.",
        source_url="https://www.culturaydeporte.gob.es/cultura/areas/cine/industria-cine/convenios-coproduccion-internacional.html",
        source_desc="ICAA — Spain-India co-production treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # INTRA-EUROPEAN bilateral treaties (additional)
    # -------------------------------------------------------------------------
    bilateral(
        "Belgium–Netherlands Coproduction Treaty",
        "BE", "NL", min_share=20, max_share=80,
        auth_a="Centre du Cinéma (FWB) / VAF", auth_b="Netherlands Film Fund",
        notes="Min 20% financial share each. Very active Benelux partnership.",
        source_url="https://www.filmfonds.nl/page/co-productions",
        source_desc="Netherlands Film Fund — Belgium-Netherlands treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Belgium–Luxembourg Coproduction Treaty",
        "BE", "LU", min_share=20, max_share=80,
        auth_a="Centre du Cinéma (FWB) / VAF", auth_b="Film Fund Luxembourg",
        notes="Min 20% financial share each. Benelux partnership.",
        source_url="https://filmfund.lu/en/co-productions",
        source_desc="Film Fund Luxembourg — Belgium-Luxembourg treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Netherlands–Luxembourg Coproduction Treaty",
        "NL", "LU", min_share=20, max_share=80,
        auth_a="Netherlands Film Fund", auth_b="Film Fund Luxembourg",
        notes="Min 20% financial share each. Benelux partnership.",
        source_url="https://filmfund.lu/en/co-productions",
        source_desc="Film Fund Luxembourg — Netherlands-Luxembourg treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Austria–Switzerland Coproduction Treaty",
        "AT", "CH", min_share=20, max_share=80,
        auth_a="Austrian Film Institute", auth_b="BAK (Federal Office of Culture)",
        notes="Min 20% financial share each. Active German-language coproduction corridor.",
        source_url="https://filminstitut.at/en/funding/co-productions/",
        source_desc="Austrian Film Institute — Austria-Switzerland treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Sweden–Norway Coproduction Treaty",
        "SE", "NO", min_share=20, max_share=80,
        auth_a="Swedish Film Institute", auth_b="NFI",
        notes="Min 20% financial share each. Active Nordic partnership.",
        source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
        source_desc="European Convention on Cinematographic Co-Production (Nordic framework)",
        last_verified="2025-03",
    ),
    bilateral(
        "Sweden–Denmark Coproduction Treaty",
        "SE", "DK", min_share=20, max_share=80,
        auth_a="Swedish Film Institute", auth_b="DFI",
        notes="Min 20% financial share each. Active Nordic partnership.",
        source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
        source_desc="European Convention on Cinematographic Co-Production (Nordic framework)",
        last_verified="2025-03",
    ),
    bilateral(
        "Denmark–Norway Coproduction Treaty",
        "DK", "NO", min_share=20, max_share=80,
        auth_a="DFI", auth_b="NFI",
        notes="Min 20% financial share each. Active Nordic partnership.",
        source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
        source_desc="European Convention on Cinematographic Co-Production (Nordic framework)",
        last_verified="2025-03",
    ),
    bilateral(
        "Finland–Norway Coproduction Treaty",
        "FI", "NO", min_share=20, max_share=80,
        auth_a="Finnish Film Foundation", auth_b="NFI",
        source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
        source_desc="European Convention on Cinematographic Co-Production (Nordic framework)",
        last_verified="2025-03",
    ),
    bilateral(
        "Finland–Sweden Coproduction Treaty",
        "FI", "SE", min_share=20, max_share=80,
        auth_a="Finnish Film Foundation", auth_b="Swedish Film Institute",
        source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
        source_desc="European Convention on Cinematographic Co-Production (Nordic framework)",
        last_verified="2025-03",
    ),
    bilateral(
        "Finland–Denmark Coproduction Treaty",
        "FI", "DK", min_share=20, max_share=80,
        auth_a="Finnish Film Foundation", auth_b="DFI",
        source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
        source_desc="European Convention on Cinematographic Co-Production (Nordic framework)",
        last_verified="2025-03",
    ),
    bilateral(
        "Poland–Germany Coproduction Treaty",
        "PL", "DE", min_share=20, max_share=80,
        auth_a="PISF", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://pisf.pl/en/co-productions/",
        source_desc="PISF — Poland-Germany co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Poland–France Coproduction Treaty",
        "PL", "FR", min_share=20, max_share=80,
        auth_a="PISF", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://pisf.pl/en/co-productions/",
        source_desc="PISF — Poland-France co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Czech Republic–Germany Coproduction Treaty",
        "CZ", "DE", min_share=20, max_share=80,
        auth_a="Czech Film Fund", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://www.fondkinematografie.cz/co-productions",
        source_desc="Czech Film Fund — CZ-Germany treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Czech Republic–France Coproduction Treaty",
        "CZ", "FR", min_share=20, max_share=80,
        auth_a="Czech Film Fund", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.fondkinematografie.cz/co-productions",
        source_desc="Czech Film Fund — CZ-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Hungary–Germany Coproduction Treaty",
        "HU", "DE", min_share=20, max_share=80,
        auth_a="Hungarian National Film Institute", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://www.filmalap.hu/en/co-productions",
        source_desc="Hungarian National Film Institute — HU-Germany treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Romania–France Coproduction Treaty",
        "RO", "FR", min_share=20, max_share=80,
        auth_a="CNC Romania", auth_b="CNC France",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.gov.ro/en/co-productions/",
        source_desc="CNC Romania — Romania-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Romania–Germany Coproduction Treaty",
        "RO", "DE", min_share=20, max_share=80,
        auth_a="CNC Romania", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://www.cnc.gov.ro/en/co-productions/",
        source_desc="CNC Romania — Romania-Germany treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Greece–France Coproduction Treaty",
        "GR", "FR", min_share=20, max_share=80,
        auth_a="Greek Film Centre / EKOME", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.ekome.media/co-productions/",
        source_desc="EKOME — Greece-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Croatia–Germany Coproduction Treaty",
        "HR", "DE", min_share=20, max_share=80,
        auth_a="HAVC", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://www.havc.hr/eng/co-productions",
        source_desc="HAVC — Croatia-Germany treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Croatia–France Coproduction Treaty",
        "HR", "FR", min_share=20, max_share=80,
        auth_a="HAVC", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.havc.hr/eng/co-productions",
        source_desc="HAVC — Croatia-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Serbia–France Coproduction Treaty",
        "RS", "FR", min_share=20, max_share=80,
        auth_a="Film Center Serbia", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.fcs.rs/en/co-productions/",
        source_desc="Film Center Serbia — Serbia-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Serbia–Germany Coproduction Treaty",
        "RS", "DE", min_share=20, max_share=80,
        auth_a="Film Center Serbia", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://www.fcs.rs/en/co-productions/",
        source_desc="Film Center Serbia — Serbia-Germany treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Serbia–Italy Coproduction Treaty",
        "RS", "IT", min_share=20, max_share=80,
        auth_a="Film Center Serbia", auth_b="MiC",
        notes="Min 20% financial share each.",
        source_url="https://www.fcs.rs/en/co-productions/",
        source_desc="Film Center Serbia — Serbia-Italy treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Ireland–Australia Coproduction Treaty",
        "IE", "AU", min_share=20, max_share=80,
        auth_a="Screen Ireland", auth_b="Screen Australia",
        notes="Min 20% financial share each.",
        source_url="https://www.screenireland.ie/co-production",
        source_desc="Screen Ireland — Ireland-Australia treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Ireland–UK Coproduction Treaty",
        "IE", "GB", min_share=20, max_share=80,
        auth_a="Screen Ireland", auth_b="BFI",
        notes="Min 20% financial share each. Very active cross-border partnership.",
        source_url="https://www.screenireland.ie/co-production",
        source_desc="Screen Ireland — Ireland-UK treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Ireland–France Coproduction Treaty",
        "IE", "FR", min_share=20, max_share=80,
        auth_a="Screen Ireland", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.screenireland.ie/co-production",
        source_desc="Screen Ireland — Ireland-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Ireland–Germany Coproduction Treaty",
        "IE", "DE", min_share=20, max_share=80,
        auth_a="Screen Ireland", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://www.screenireland.ie/co-production",
        source_desc="Screen Ireland — Ireland-Germany treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Switzerland–France Coproduction Treaty",
        "CH", "FR", min_share=20, max_share=80,
        auth_a="BAK", auth_b="CNC",
        notes="Min 20% financial share each. (Also accessible via France–Switzerland entry.)",
        source_url="https://www.bak.admin.ch/bak/en/home/cultural-creation/film/international.html",
        source_desc="BAK — Switzerland-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Switzerland–Italy Coproduction Treaty",
        "CH", "IT", min_share=20, max_share=80,
        auth_a="BAK", auth_b="MiC",
        notes="Min 20% financial share each. Active given shared Italian-language region.",
        source_url="https://www.bak.admin.ch/bak/en/home/cultural-creation/film/international.html",
        source_desc="BAK — Switzerland-Italy treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Luxembourg–France Coproduction Treaty",
        "LU", "FR", min_share=20, max_share=80,
        auth_a="Film Fund Luxembourg", auth_b="CNC",
        notes="Min 20% financial share each. Very active partnership.",
        source_url="https://filmfund.lu/en/co-productions",
        source_desc="Film Fund Luxembourg — Luxembourg-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Luxembourg–Germany Coproduction Treaty",
        "LU", "DE", min_share=20, max_share=80,
        auth_a="Film Fund Luxembourg", auth_b="FFA / BKM",
        notes="Min 20% financial share each.",
        source_url="https://filmfund.lu/en/co-productions",
        source_desc="Film Fund Luxembourg — Luxembourg-Germany treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Luxembourg–Belgium Coproduction Treaty",
        "LU", "BE", min_share=20, max_share=80,
        auth_a="Film Fund Luxembourg", auth_b="Centre du Cinéma (FWB) / VAF",
        notes="Min 20% financial share each. Benelux partnership.",
        source_url="https://filmfund.lu/en/co-productions",
        source_desc="Film Fund Luxembourg — Luxembourg-Belgium treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Iceland–Denmark Coproduction Treaty",
        "IS", "DK", min_share=20, max_share=80,
        auth_a="Icelandic Film Centre", auth_b="DFI",
        notes="Min 20% financial share each. Nordic partnership.",
        source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
        source_desc="European Convention on Cinematographic Co-Production (Nordic framework)",
        last_verified="2025-03",
    ),
    bilateral(
        "Iceland–Norway Coproduction Treaty",
        "IS", "NO", min_share=20, max_share=80,
        auth_a="Icelandic Film Centre", auth_b="NFI",
        notes="Min 20% financial share each. Nordic partnership.",
        source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
        source_desc="European Convention on Cinematographic Co-Production (Nordic framework)",
        last_verified="2025-03",
    ),
    bilateral(
        "Portugal–Brazil Coproduction Treaty",
        "PT", "BR", min_share=20, max_share=80,
        auth_a="ICA", auth_b="ANCINE",
        notes="Min 20% financial share each. Lusophone partnership.",
        source_url="https://www.ica-ip.pt/en/co-productions/",
        source_desc="ICA — Portugal-Brazil co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "Portugal–France Coproduction Treaty",
        "PT", "FR", min_share=20, max_share=80,
        auth_a="ICA", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.ica-ip.pt/en/co-productions/",
        source_desc="ICA — Portugal-France co-production treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # NEW ZEALAND additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "New Zealand–Australia Coproduction Treaty",
        "NZ", "AU", min_share=20, max_share=80,
        auth_a="NZFC", auth_b="Screen Australia",
        notes="Min 20% financial share each. Trans-Tasman partnership.",
        source_url="https://www.nzfilm.co.nz/international/co-production",
        source_desc="NZFC — NZ-Australia co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "New Zealand–France Coproduction Treaty",
        "NZ", "FR", min_share=20, max_share=80,
        auth_a="NZFC", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.nzfilm.co.nz/international/co-production",
        source_desc="NZFC — NZ-France co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "New Zealand–South Korea Coproduction Treaty",
        "NZ", "KR", min_share=20, max_share=80,
        auth_a="NZFC", auth_b="KOFIC",
        notes="Min 20% financial share each.",
        source_url="https://www.nzfilm.co.nz/international/co-production",
        source_desc="NZFC — NZ-South Korea co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "New Zealand–Singapore Coproduction Treaty",
        "NZ", "SG", min_share=20, max_share=80,
        auth_a="NZFC", auth_b="IMDA Singapore",
        source_url="https://www.nzfilm.co.nz/international/co-production",
        source_desc="NZFC — NZ-Singapore co-production treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SOUTH KOREA additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "South Korea–France Coproduction Treaty",
        "KR", "FR", min_share=20, max_share=80,
        auth_a="KOFIC", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.koreanfilm.or.kr/eng/support/copro.jsp",
        source_desc="KOFIC — Korea-France co-production treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "South Korea–India Coproduction Treaty",
        "KR", "IN", min_share=20, max_share=80,
        auth_a="KOFIC", auth_b="Ministry of Information and Broadcasting",
        notes="Min 20% financial share each.",
        source_url="https://www.koreanfilm.or.kr/eng/support/copro.jsp",
        source_desc="KOFIC — Korea-India co-production treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # SOUTH AFRICA additional bilateral treaties
    # -------------------------------------------------------------------------
    bilateral(
        "South Africa–France Coproduction Treaty",
        "ZA", "FR", min_share=20, max_share=80,
        auth_a="NFVF", auth_b="CNC",
        notes="Min 20% financial share each.",
        source_url="https://www.nfvf.co.za/co-productions/",
        source_desc="NFVF — South Africa-France treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "South Africa–Italy Coproduction Treaty",
        "ZA", "IT", min_share=20, max_share=80,
        auth_a="NFVF", auth_b="MiC",
        notes="Min 20% financial share each.",
        source_url="https://www.nfvf.co.za/co-productions/",
        source_desc="NFVF — South Africa-Italy treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "South Africa–Ireland Coproduction Treaty",
        "ZA", "IE", min_share=20, max_share=80,
        auth_a="NFVF", auth_b="Screen Ireland",
        source_url="https://www.nfvf.co.za/co-productions/",
        source_desc="NFVF — South Africa-Ireland treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "South Africa–Australia Coproduction Treaty",
        "ZA", "AU", min_share=20, max_share=80,
        auth_a="NFVF", auth_b="Screen Australia",
        notes="Min 20% financial share each.",
        source_url="https://www.nfvf.co.za/co-productions/",
        source_desc="NFVF — South Africa-Australia treaty",
        last_verified="2025-03",
    ),

    # -------------------------------------------------------------------------
    # INDIA bilateral treaties (additional)
    # -------------------------------------------------------------------------
    bilateral(
        "India–Italy Coproduction Treaty",
        "IN", "IT", min_share=20, max_share=80,
        auth_a="Ministry of Information and Broadcasting", auth_b="MiC",
        notes="Min 20% financial share each.",
        source_url="https://ffo.gov.in/en/co-production-agreements",
        source_desc="Film Facilitation Office India — India-Italy treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "India–Brazil Coproduction Treaty",
        "IN", "BR", min_share=20, max_share=80,
        auth_a="Ministry of Information and Broadcasting", auth_b="ANCINE",
        source_url="https://ffo.gov.in/en/co-production-agreements",
        source_desc="Film Facilitation Office India — India-Brazil treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "India–Israel Coproduction Treaty",
        "IN", "IL", min_share=20, max_share=80,
        auth_a="Ministry of Information and Broadcasting", auth_b="Israel Film Fund",
        source_url="https://ffo.gov.in/en/co-production-agreements",
        source_desc="Film Facilitation Office India — India-Israel treaty",
        last_verified="2025-03",
    ),
    bilateral(
        "India–China Coproduction Treaty",
        "IN", "CN", min_share=20, max_share=80,
        auth_a="Ministry of Information and Broadcasting", auth_b="China Film Administration",
        source_url="https://ffo.gov.in/en/co-production-agreements",
        source_desc="Film Facilitation Office India — India-China treaty",
        last_verified="2025-03",
    ),
]

for t in treaties:
    db.add(t)
db.commit()


# =============================================================================
# MULTILATERAL — European Convention on Cinematographic Co-Production
# =============================================================================

convention = Treaty(
    name="European Convention on Cinematographic Co-Production (Revised, 2017)",
    treaty_type="multilateral",
    country_a_code="XX",  # multilateral — members stored separately
    country_b_code=None,
    min_share_percent=5,
    max_share_percent=80,
    min_share_third_party=5,
    eligible_formats=["feature_fiction", "documentary", "series", "animation"],
    creative_contribution_required=True,
    creative_requirements_summary=(
        "Contributions (creative, technical, financial) must be proportional to each co-producer's share. "
        "Minority co-producers must make an effective creative and technical contribution. "
        "Revised Convention (2017) broadened to include TV, lowered min share to 5%."
    ),
    requires_prior_approval=True,
    date_signed="2017-01-30",
    date_entered_force="2020-01-01",
    is_active=True,
    notes=(
        "Revised Convention entered into force 1 July 2020 for ratifying states. "
        "Minimum financial participation: 5% (revised, down from 10% in 1992 version). "
        "Max 80% for majority co-producer. Covers cinema, TV, and digital platforms (revised convention). "
        "States that have only ratified the 1992 version: min 10%, cinema only."
    ),
    source_url="https://www.coe.int/en/web/conventions/full-list/-/conventions/treaty/220",
    source_description="Council of Europe — European Convention on Cinematographic Co-Production (Revised), CETS No. 220",
    last_verified="2025-03",
)
db.add(convention)
db.commit()

# Members of the European Convention (both 1992 original and 2017 revised)
# Codes for countries that have ratified at least one version
convention_members = [
    ("FR", "1994-04-01", "Ratified revised 2017 convention"),
    ("GB", "1994-03-01", "Ratified 1992 convention; post-Brexit still applies via Council of Europe membership"),
    ("DE", "1995-04-01", "Ratified revised 2017 convention"),
    ("IT", "1995-05-01", "Ratified 1992 convention"),
    ("ES", "1996-12-01", "Ratified 1992 convention"),
    ("NL", "1997-10-01", "Ratified revised 2017 convention"),
    ("BE", "1994-08-01", "Ratified revised 2017 convention"),
    ("IE", "1998-12-01", "Ratified 1992 convention"),
    ("DK", "1994-03-01", "Ratified 1992 convention"),
    ("SE", "1994-09-01", "Ratified revised 2017 convention"),
    ("NO", "1994-07-01", "Ratified revised 2017 convention"),
    ("FI", "1996-08-01", "Ratified 1992 convention"),
    ("AT", "1995-01-01", "Ratified 1992 convention"),
    ("CH", "1994-10-01", "Ratified 1992 convention"),
    ("PT", "1995-11-01", "Ratified 1992 convention"),
    ("GR", "1996-06-01", "Ratified revised 2017 convention"),
    ("PL", "1998-02-01", "Ratified revised 2017 convention"),
    ("CZ", "1997-04-01", "Ratified revised 2017 convention"),
    ("HU", "1998-03-01", "Ratified 1992 convention"),
    ("RO", "1997-06-01", "Ratified revised 2017 convention"),
    ("BG", "2003-09-01", "Ratified 1992 convention"),
    ("HR", "2005-03-01", "Ratified revised 2017 convention"),
    ("IS", "2001-04-01", "Ratified 1992 convention"),
    ("LU", "1995-07-01", "Ratified 1992 convention"),
    ("EE", "2002-08-01", "Ratified revised 2017 convention"),
    ("LV", "2003-11-01", "Ratified 1992 convention"),
    ("LT", "2004-04-01", "Ratified revised 2017 convention"),
    ("SK", "2000-01-01", "Ratified 1992 convention"),
    ("SI", "2001-12-01", "Ratified 1992 convention"),
    ("RS", "2007-06-01", "Ratified 1992 convention"),
    ("BA", "2008-10-01", "Ratified 1992 convention"),
    ("TR", "2004-11-01", "Ratified 1992 convention"),
    ("ME", "2008-06-06", "Ratified 1992 convention (succession from Serbia and Montenegro)"),
    ("MK", "2003-03-01", "Ratified 1992 convention"),
    ("GE", "2001-09-01", "Ratified 1992 convention"),
    ("AL", "2005-07-01", "Ratified 1992 convention"),
    ("UA", "2006-02-01", "Ratified 1992 convention"),
    ("MD", "2007-03-01", "Ratified 1992 convention"),
    ("CY", "2012-07-01", "Ratified 1992 convention"),
    ("MT", "2014-01-01", "Ratified revised 2017 convention"),
    ("AD", "2022-09-01", "Ratified revised 2017 convention"),
]

for code, date, note in convention_members:
    db.add(MultilateralMember(
        treaty_id=convention.id,
        country_code=code,
        date_ratified=date,
        notes=note,
    ))
db.commit()

# =============================================================================
# POST-PROCESSING: Set mutual exclusivity for regional funds
# =============================================================================
# Regional funds within the same country are mutually exclusive — you can only
# shoot in one region, so you can only claim one regional fund per country.
# This groups all regional incentives by country_code and sets each one's
# mutually_exclusive_with to list all OTHER regional funds in the same country.

from collections import defaultdict

regional_by_country: dict[str, list[Incentive]] = defaultdict(list)
for inc_obj in incentives:
    if inc_obj.region:
        regional_by_country[inc_obj.country_code].append(inc_obj)

n_regional_exclusions = 0
for country_code, regional_incs in regional_by_country.items():
    if len(regional_incs) < 2:
        continue  # single regional fund, no conflict possible
    all_names = [r.name for r in regional_incs]
    for r in regional_incs:
        others = [n for n in all_names if n != r.name]
        existing = r.mutually_exclusive_with or []
        r.mutually_exclusive_with = list(set(existing + others))
        n_regional_exclusions += 1

db.commit()

n_inc = len(incentives)
n_countries = len(set(i.country_code for i in incentives))
n_treaty = len(treaties) + 1  # +1 for European Convention
n_members = len(convention_members)

db.close()

print(f"Seed data loaded:")
print(f"  Incentives: {n_inc} across {n_countries} countries")
print(f"  Treaties: {n_treaty} ({len(treaties)} bilateral + 1 multilateral)")
print(f"  European Convention members: {n_members}")
print(f"  Regional fund mutual exclusions: {n_regional_exclusions} funds across {len([c for c, r in regional_by_country.items() if len(r) >= 2])} countries")
print(f"All figures cite official sources — see source_url and source_description on each record.")
