"""
Comprehensive scenario testing for CoPro Calculator.

Runs ~73 realistic scenarios across all supported countries, generates per-scenario
markdown reports, and produces a summary with automated anomaly detection.

Usage:
    cd backend
    python ../scenario_tests/comprehensive_test_runner.py
    python ../scenario_tests/comprehensive_test_runner.py --category A
    python ../scenario_tests/comprehensive_test_runner.py --scenario doc_france_standard
    python ../scenario_tests/comprehensive_test_runner.py --summary-only
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ── DB bootstrap (same pattern as test_runner.py) ────────────────────────────
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from app.database import SessionLocal, get_database_target
from app.models import Incentive, Treaty
from app.schemas import ProjectInput, ShootLocation, Scenario
from app.scenario_generator import generate_scenarios

REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'reports', 'comprehensive')


# ── Result container ──────────────────────────────────────────────────────────
@dataclass
class ScenarioResult:
    name: str
    category: str
    project: ProjectInput
    scenarios: list = field(default_factory=list)
    error: Optional[str] = None
    runtime_ms: float = 0.0

    @property
    def top(self) -> Optional[Scenario]:
        return self.scenarios[0] if self.scenarios else None

    @property
    def num_scenarios(self) -> int:
        return len(self.scenarios)

    @property
    def total_financing_pct(self) -> float:
        return self.top.estimated_total_financing_percent if self.top else 0.0

    @property
    def total_financing_amount(self) -> float:
        return self.top.estimated_total_financing_amount if self.top else 0.0

    @property
    def financing_currency(self) -> str:
        return self.top.financing_currency if self.top else self.project.budget_currency

    @property
    def top_countries(self) -> list[str]:
        if not self.top:
            return []
        return [p.country_code for p in self.top.partners]

    @property
    def top_incentives(self) -> list[dict]:
        if not self.top:
            return []
        result = []
        for p in self.top.partners:
            for inc in p.eligible_incentives:
                result.append({
                    'name': inc.name,
                    'country': p.country_code,
                    'rate': inc.rebate_percent,
                    'amount': inc.benefit.benefit_amount if inc.benefit else 0.0,
                    'contribution_pct': inc.estimated_contribution_percent,
                })
        return result


# ── Scenario definitions ──────────────────────────────────────────────────────
def build_all_scenarios() -> list[dict]:
    scenarios = []

    def add(name, category, project):
        scenarios.append({'name': name, 'category': category, 'project': project})

    # ── Category A: Single-country documentaries ──────────────────────────────
    add('doc_france_standard', 'A', ProjectInput(
        title="Doc France Standard",
        format="documentary", stage="production",
        budget=800_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="France", percent=100)],
        director_nationalities=["France"],
        willing_add_coproducer=True,
    ))
    add('doc_uk_standard', 'A', ProjectInput(
        title="Doc UK Standard",
        format="documentary", stage="production",
        budget=500_000, budget_currency="GBP",
        shoot_locations=[ShootLocation(country="United Kingdom", percent=100)],
        director_nationalities=["United Kingdom"],
        willing_add_coproducer=True,
    ))
    add('doc_germany_below_threshold', 'A', ProjectInput(
        title="Doc Germany Below DFFF Threshold",
        format="documentary", stage="production",
        budget=180_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Germany", percent=100)],
        director_nationalities=["Germany"],
        willing_add_coproducer=True,
    ))
    add('doc_germany_above_threshold', 'A', ProjectInput(
        title="Doc Germany Above DFFF Threshold",
        format="documentary", stage="production",
        budget=250_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Germany", percent=100)],
        director_nationalities=["Germany"],
        willing_add_coproducer=True,
    ))
    add('doc_ireland_standard', 'A', ProjectInput(
        title="Doc Ireland Standard",
        format="documentary", stage="production",
        budget=400_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Ireland", percent=100)],
        director_nationalities=["Ireland"],
        willing_add_coproducer=True,
    ))
    add('doc_italy_standard', 'A', ProjectInput(
        title="Doc Italy Standard",
        format="documentary", stage="production",
        budget=600_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Italy", percent=100)],
        director_nationalities=["Italy"],
        willing_add_coproducer=True,
    ))
    add('doc_spain_standard', 'A', ProjectInput(
        title="Doc Spain Standard",
        format="documentary", stage="production",
        budget=500_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Spain", percent=100)],
        director_nationalities=["Spain"],
        willing_add_coproducer=True,
    ))
    add('doc_netherlands_below_threshold', 'A', ProjectInput(
        title="Doc Netherlands Below Threshold",
        format="documentary", stage="production",
        budget=200_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Netherlands", percent=100)],
        director_nationalities=["Netherlands"],
        willing_add_coproducer=True,
    ))
    add('doc_netherlands_above_threshold', 'A', ProjectInput(
        title="Doc Netherlands Above Threshold",
        format="documentary", stage="production",
        budget=300_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Netherlands", percent=100)],
        director_nationalities=["Netherlands"],
        willing_add_coproducer=True,
    ))
    add('doc_canada_labour', 'A', ProjectInput(
        title="Doc Canada Labour Rebate",
        format="documentary", stage="production",
        budget=500_000, budget_currency="CAD",
        shoot_locations=[ShootLocation(country="Canada", percent=100)],
        director_nationalities=["Canada"],
        willing_add_coproducer=True,
    ))
    add('doc_australia_producer_offset', 'A', ProjectInput(
        title="Doc Australia Producer Offset",
        format="documentary", stage="production",
        budget=800_000, budget_currency="AUD",
        shoot_locations=[ShootLocation(country="Australia", percent=100)],
        director_nationalities=["Australia"],
        willing_add_coproducer=True,
    ))
    add('doc_czech_republic', 'A', ProjectInput(
        title="Doc Czech Republic",
        format="documentary", stage="production",
        budget=400_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Czech Republic", percent=100)],
        director_nationalities=["Czech Republic"],
        willing_add_coproducer=True,
    ))
    add('doc_belgium', 'A', ProjectInput(
        title="Doc Belgium Tax Shelter",
        format="documentary", stage="production",
        budget=350_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Belgium", percent=100)],
        director_nationalities=["Belgium"],
        willing_add_coproducer=True,
    ))
    add('doc_south_africa', 'A', ProjectInput(
        title="Doc South Africa",
        format="documentary", stage="production",
        budget=300_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="South Africa", percent=100)],
        director_nationalities=["South Africa"],
        willing_add_coproducer=True,
    ))
    add('doc_greece', 'A', ProjectInput(
        title="Doc Greece",
        format="documentary", stage="production",
        budget=250_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Greece", percent=100)],
        director_nationalities=["Greece"],
        willing_add_coproducer=True,
    ))

    # ── Category B: Single-country feature fiction ────────────────────────────
    add('feature_france_high_budget', 'B', ProjectInput(
        title="Feature France High Budget",
        format="feature_fiction", stage="production",
        budget=8_000_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="France", percent=100)],
        director_nationalities=["France"],
        willing_add_coproducer=True,
    ))
    add('feature_uk_avec', 'B', ProjectInput(
        title="Feature UK AVEC",
        format="feature_fiction", stage="production",
        budget=5_000_000, budget_currency="GBP",
        shoot_locations=[ShootLocation(country="United Kingdom", percent=100)],
        director_nationalities=["United Kingdom"],
        willing_add_coproducer=True,
        cultural_test_passed=["GB"],
    ))
    add('feature_hungary', 'B', ProjectInput(
        title="Feature Hungary",
        format="feature_fiction", stage="production",
        budget=3_000_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Hungary", percent=100)],
        director_nationalities=["Hungary"],
        willing_add_coproducer=True,
    ))
    add('feature_spain', 'B', ProjectInput(
        title="Feature Spain Tiered Rate",
        format="feature_fiction", stage="production",
        budget=4_000_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Spain", percent=100)],
        director_nationalities=["Spain"],
        willing_add_coproducer=True,
    ))
    add('feature_germany_high', 'B', ProjectInput(
        title="Feature Germany High Budget",
        format="feature_fiction", stage="production",
        budget=12_000_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Germany", percent=100)],
        director_nationalities=["Germany"],
        willing_add_coproducer=True,
    ))
    add('feature_colombia', 'B', ProjectInput(
        title="Feature Colombia",
        format="feature_fiction", stage="production",
        budget=2_000_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Colombia", percent=100)],
        director_nationalities=["Colombia"],
        willing_add_coproducer=True,
    ))
    add('feature_new_zealand', 'B', ProjectInput(
        title="Feature New Zealand",
        format="feature_fiction", stage="production",
        budget=3_000_000, budget_currency="NZD",
        shoot_locations=[ShootLocation(country="New Zealand", percent=100)],
        director_nationalities=["New Zealand"],
        willing_add_coproducer=True,
    ))
    add('feature_south_korea', 'B', ProjectInput(
        title="Feature South Korea",
        format="feature_fiction", stage="production",
        budget=5_000_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="South Korea", percent=100)],
        director_nationalities=["South Korea"],
        willing_add_coproducer=True,
    ))

    # ── Category C: Two-country co-productions ────────────────────────────────
    add('copro_fr_be_doc', 'C', ProjectInput(
        title="Co-pro France-Belgium Doc",
        format="documentary", stage="production",
        budget=500_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="France", percent=60),
            ShootLocation(country="Belgium", percent=40),
        ],
        director_nationalities=["France"],
        has_coproducer=["Belgium"],
        willing_add_coproducer=True,
    ))
    add('copro_fr_de_doc', 'C', ProjectInput(
        title="Co-pro France-Germany Doc",
        format="documentary", stage="production",
        budget=400_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="France", percent=50),
            ShootLocation(country="Germany", percent=50),
        ],
        director_nationalities=["France"],
        has_coproducer=["Germany"],
        willing_add_coproducer=True,
    ))
    add('copro_gb_ie_doc', 'C', ProjectInput(
        title="Co-pro UK-Ireland Doc",
        format="documentary", stage="production",
        budget=600_000, budget_currency="GBP",
        shoot_locations=[
            ShootLocation(country="United Kingdom", percent=60),
            ShootLocation(country="Ireland", percent=40),
        ],
        director_nationalities=["United Kingdom"],
        has_coproducer=["Ireland"],
        willing_add_coproducer=True,
    ))
    add('copro_fr_ca_doc', 'C', ProjectInput(
        title="Co-pro France-Canada Doc",
        format="documentary", stage="production",
        budget=700_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="France", percent=55),
            ShootLocation(country="Canada", percent=45),
        ],
        director_nationalities=["France"],
        has_coproducer=["Canada"],
        willing_add_coproducer=True,
    ))
    add('copro_de_at_doc', 'C', ProjectInput(
        title="Co-pro Germany-Austria Doc",
        format="documentary", stage="production",
        budget=350_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="Germany", percent=60),
            ShootLocation(country="Austria", percent=40),
        ],
        director_nationalities=["Germany"],
        has_coproducer=["Austria"],
        willing_add_coproducer=True,
    ))
    add('copro_it_es_doc', 'C', ProjectInput(
        title="Co-pro Italy-Spain Doc",
        format="documentary", stage="production",
        budget=900_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="Italy", percent=50),
            ShootLocation(country="Spain", percent=50),
        ],
        director_nationalities=["Italy"],
        has_coproducer=["Spain"],
        willing_add_coproducer=True,
    ))
    add('copro_nordic_doc', 'C', ProjectInput(
        title="Co-pro Nordic Three-Way Doc",
        format="documentary", stage="production",
        budget=450_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="Sweden", percent=40),
            ShootLocation(country="Norway", percent=30),
            ShootLocation(country="Denmark", percent=30),
        ],
        director_nationalities=["Sweden"],
        has_coproducer=["Norway", "Denmark"],
        willing_add_coproducer=True,
    ))
    add('copro_fr_ch_doc', 'C', ProjectInput(
        title="Co-pro France-Switzerland Doc",
        format="documentary", stage="production",
        budget=600_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="France", percent=70),
            ShootLocation(country="Switzerland", percent=30),
        ],
        director_nationalities=["France"],
        has_coproducer=["Switzerland"],
        willing_add_coproducer=True,
    ))
    add('copro_de_pl_doc', 'C', ProjectInput(
        title="Co-pro Germany-Poland Doc",
        format="documentary", stage="production",
        budget=500_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="Germany", percent=55),
            ShootLocation(country="Poland", percent=45),
        ],
        director_nationalities=["Germany"],
        has_coproducer=["Poland"],
        willing_add_coproducer=True,
    ))
    add('copro_gb_ca_feature', 'C', ProjectInput(
        title="Co-pro UK-Canada Feature",
        format="feature_fiction", stage="production",
        budget=4_000_000, budget_currency="GBP",
        shoot_locations=[
            ShootLocation(country="United Kingdom", percent=60),
            ShootLocation(country="Canada", percent=40),
        ],
        director_nationalities=["United Kingdom"],
        has_coproducer=["Canada"],
        willing_add_coproducer=True,
        cultural_test_passed=["GB"],
    ))

    # ── Category D: Three-country co-productions ──────────────────────────────
    add('copro_3way_fr_be_lu', 'D', ProjectInput(
        title="Three-Way FR-BE-LU Doc",
        format="documentary", stage="production",
        budget=800_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="France", percent=50),
            ShootLocation(country="Belgium", percent=30),
            ShootLocation(country="Luxembourg", percent=20),
        ],
        director_nationalities=["France"],
        has_coproducer=["Belgium", "Luxembourg"],
        willing_add_coproducer=True,
    ))
    add('copro_3way_de_fr_it', 'D', ProjectInput(
        title="Three-Way DE-FR-IT Feature",
        format="feature_fiction", stage="production",
        budget=2_000_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="Germany", percent=40),
            ShootLocation(country="France", percent=35),
            ShootLocation(country="Italy", percent=25),
        ],
        director_nationalities=["Germany"],
        has_coproducer=["France", "Italy"],
        willing_add_coproducer=True,
    ))
    add('copro_3way_gb_ie_au', 'D', ProjectInput(
        title="Three-Way GB-IE-AU Feature",
        format="feature_fiction", stage="production",
        budget=3_000_000, budget_currency="GBP",
        shoot_locations=[
            ShootLocation(country="United Kingdom", percent=40),
            ShootLocation(country="Ireland", percent=30),
            ShootLocation(country="Australia", percent=30),
        ],
        director_nationalities=["United Kingdom"],
        has_coproducer=["Ireland", "Australia"],
        willing_add_coproducer=True,
        cultural_test_passed=["GB"],
    ))
    add('copro_3way_es_co_fr', 'D', ProjectInput(
        title="Three-Way ES-CO-FR Doc",
        format="documentary", stage="production",
        budget=1_500_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="Spain", percent=40),
            ShootLocation(country="Colombia", percent=30),
            ShootLocation(country="France", percent=30),
        ],
        director_nationalities=["Spain"],
        has_coproducer=["Colombia", "France"],
        willing_add_coproducer=True,
    ))
    add('copro_3way_it_de_ch', 'D', ProjectInput(
        title="Three-Way IT-DE-CH Doc",
        format="documentary", stage="production",
        budget=1_200_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="Italy", percent=40),
            ShootLocation(country="Germany", percent=35),
            ShootLocation(country="Switzerland", percent=25),
        ],
        director_nationalities=["Italy"],
        has_coproducer=["Germany", "Switzerland"],
        willing_add_coproducer=True,
    ))

    # ── Category E: Edge cases ─────────────────────────────────────────────────
    add('edge_de_below_dfff_threshold', 'E', ProjectInput(
        title="Edge: Germany Just Below DFFF Doc Threshold",
        format="documentary", stage="production",
        budget=190_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Germany", percent=100)],
        director_nationalities=["Germany"],
        willing_add_coproducer=True,
    ))
    add('edge_de_above_dfff_threshold', 'E', ProjectInput(
        title="Edge: Germany Just Above DFFF Doc Threshold",
        format="documentary", stage="production",
        budget=210_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Germany", percent=100)],
        director_nationalities=["Germany"],
        willing_add_coproducer=True,
    ))
    add('edge_nl_below_threshold', 'E', ProjectInput(
        title="Edge: Netherlands Just Below Threshold",
        format="documentary", stage="production",
        budget=240_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Netherlands", percent=100)],
        director_nationalities=["Netherlands"],
        willing_add_coproducer=True,
    ))
    add('edge_france_vfx_conditional', 'E', ProjectInput(
        title="Edge: France VFX Conditional Rate (30%->40%)",
        format="feature_fiction", stage="production",
        budget=10_000_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="France", percent=100)],
        director_nationalities=["France"],
        vfx_flexible=True,
        willing_add_coproducer=True,
    ))
    add('edge_4country_split_shoot', 'E', ProjectInput(
        title="Edge: Four-Country Split Shoot Doc",
        format="documentary", stage="production",
        budget=800_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="France", percent=25),
            ShootLocation(country="Italy", percent=25),
            ShootLocation(country="Spain", percent=25),
            ShootLocation(country="Greece", percent=25),
        ],
        director_nationalities=["France"],
        willing_add_coproducer=True,
    ))
    add('edge_post_different_country', 'E', ProjectInput(
        title="Edge: Shoot France, Post UK",
        format="documentary", stage="production",
        budget=500_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="France", percent=100)],
        director_nationalities=["France"],
        post_production_country="GB",
        post_flexible=True,
        willing_add_coproducer=True,
    ))
    add('edge_no_coproducer_willing', 'E', ProjectInput(
        title="Edge: France, No Coproducer Willing",
        format="documentary", stage="production",
        budget=500_000, budget_currency="EUR",
        shoot_locations=[ShootLocation(country="France", percent=100)],
        director_nationalities=["France"],
        willing_add_coproducer=False,
    ))
    add('edge_au_below_location_offset', 'E', ProjectInput(
        title="Edge: Australia Just Below Location Offset Threshold",
        format="feature_fiction", stage="production",
        budget=19_000_000, budget_currency="AUD",
        shoot_locations=[ShootLocation(country="Australia", percent=100)],
        director_nationalities=["Australia"],
        willing_add_coproducer=True,
    ))

    # ── Category F: Format and currency variations ────────────────────────────
    add('series_uk_standard', 'F', ProjectInput(
        title="Series UK Standard",
        format="series", stage="production",
        budget=8_000_000, budget_currency="GBP",
        shoot_locations=[ShootLocation(country="United Kingdom", percent=100)],
        director_nationalities=["United Kingdom"],
        willing_add_coproducer=True,
        cultural_test_passed=["GB"],
    ))
    add('animation_fr_be', 'F', ProjectInput(
        title="Animation France-Belgium",
        format="animation", stage="production",
        budget=3_000_000, budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="France", percent=60),
            ShootLocation(country="Belgium", percent=40),
        ],
        director_nationalities=["France"],
        has_coproducer=["Belgium"],
        willing_add_coproducer=True,
    ))
    add('doc_usd_budget', 'F', ProjectInput(
        title="Doc USD Budget FR-CA",
        format="documentary", stage="production",
        budget=400_000, budget_currency="USD",
        shoot_locations=[
            ShootLocation(country="France", percent=60),
            ShootLocation(country="Canada", percent=40),
        ],
        director_nationalities=["France"],
        has_coproducer=["Canada"],
        willing_add_coproducer=True,
    ))
    add('feature_cad_budget', 'F', ProjectInput(
        title="Feature CAD Budget Canada",
        format="feature_fiction", stage="production",
        budget=5_000_000, budget_currency="CAD",
        shoot_locations=[ShootLocation(country="Canada", percent=100)],
        director_nationalities=["Canada"],
        willing_add_coproducer=True,
    ))

    # ── Category SWEEP: Remaining countries not yet covered ───────────────────
    # Countries already in primary categories (shoot locations)
    covered = {
        'FR', 'GB', 'DE', 'IE', 'IT', 'ES', 'NL', 'CA', 'AU', 'CZ', 'BE', 'ZA', 'GR',
        'HU', 'CO', 'NZ', 'KR', 'AT', 'SE', 'NO', 'DK', 'CH', 'PL', 'LU',
    }
    sweep_countries = [
        ('AL', 'Albania'), ('BG', 'Bulgaria'), ('CY', 'Cyprus'), ('EE', 'Estonia'),
        ('FI', 'Finland'), ('GE', 'Georgia'), ('HR', 'Croatia'), ('IS', 'Iceland'),
        ('LT', 'Lithuania'), ('LV', 'Latvia'), ('MA', 'Morocco'), ('ME', 'Montenegro'),
        ('MK', 'North Macedonia'), ('MT', 'Malta'), ('PT', 'Portugal'), ('RO', 'Romania'),
        ('RS', 'Serbia'), ('SI', 'Slovenia'), ('SK', 'Slovakia'), ('TR', 'Turkey'),
        ('UA', 'Ukraine'),
    ]
    for cc, name in sweep_countries:
        if cc not in covered:
            add(f'sweep_doc_{cc.lower()}', 'SWEEP', ProjectInput(
                title=f"Sweep Doc {name}",
                format="documentary", stage="production",
                budget=500_000, budget_currency="EUR",
                shoot_locations=[ShootLocation(country=name, percent=100)],
                director_nationalities=[name],
                willing_add_coproducer=True,
            ))

    # Update covered to include existing European sweep countries
    covered.update(cc for cc, _ in sweep_countries)

    # ── Category SWEEP_EU: Remaining European countries ──────────────────────────
    sweep_eu = [
        ('AD', 'Andorra'), ('BA', 'Bosnia and Herzegovina'), ('MD', 'Moldova'), ('XK', 'Kosovo'),
    ]
    for cc, name in sweep_eu:
        if cc not in covered:
            add(f'sweep_doc_{cc.lower()}', 'SWEEP_EU', ProjectInput(
                title=f"Sweep Doc {name}",
                format="documentary", stage="production",
                budget=500_000, budget_currency="EUR",
                shoot_locations=[ShootLocation(country=name, percent=100)],
                director_nationalities=[name],
                willing_add_coproducer=True,
            ))
    covered.update(cc for cc, _ in sweep_eu)

    # ── Category SWEEP_AM: Americas countries ──────────────────────────────────────
    sweep_am = [
        ('AG', 'Antigua and Barbuda'), ('AR', 'Argentina'), ('BB', 'Barbados'), ('BO', 'Bolivia'),
        ('BR', 'Brazil'), ('BS', 'Bahamas'), ('BZ', 'Belize'), ('CL', 'Chile'), ('CR', 'Costa Rica'),
        ('CU', 'Cuba'), ('DM', 'Dominica'), ('DO', 'Dominican Republic'), ('EC', 'Ecuador'),
        ('GD', 'Grenada'), ('GT', 'Guatemala'), ('GY', 'Guyana'), ('JM', 'Jamaica'),
        ('KN', 'Saint Kitts and Nevis'), ('LC', 'Saint Lucia'), ('MX', 'Mexico'), ('PA', 'Panama'),
        ('PE', 'Peru'), ('PY', 'Paraguay'), ('SV', 'El Salvador'), ('TT', 'Trinidad and Tobago'),
        ('US', 'United States'), ('UY', 'Uruguay'), ('VC', 'Saint Vincent and the Grenadines'),
        ('VE', 'Venezuela'),
    ]
    for cc, name in sweep_am:
        if cc not in covered:
            add(f'sweep_doc_{cc.lower()}', 'SWEEP_AM', ProjectInput(
                title=f"Sweep Doc {name}",
                format="documentary", stage="production",
                budget=500_000, budget_currency="USD",
                shoot_locations=[ShootLocation(country=name, percent=100)],
                director_nationalities=[name],
                willing_add_coproducer=True,
            ))
    covered.update(cc for cc, _ in sweep_am)

    # ── Category SWEEP_AS: Asia-Pacific countries ──────────────────────────────────
    sweep_as = [
        ('BD', 'Bangladesh'), ('BH', 'Bahrain'), ('BN', 'Brunei'), ('BT', 'Bhutan'),
        ('CN', 'China'), ('ID', 'Indonesia'), ('IL', 'Israel'), ('IN', 'India'),
        ('IQ', 'Iraq'), ('JP', 'Japan'), ('JO', 'Jordan'), ('KH', 'Cambodia'),
        ('KW', 'Kuwait'), ('KZ', 'Kazakhstan'), ('LA', 'Laos'), ('LK', 'Sri Lanka'),
        ('MM', 'Myanmar'), ('MN', 'Mongolia'), ('MV', 'Maldives'), ('MY', 'Malaysia'),
        ('NP', 'Nepal'), ('OM', 'Oman'), ('PH', 'Philippines'), ('PK', 'Pakistan'),
        ('QA', 'Qatar'), ('SG', 'Singapore'), ('TH', 'Thailand'), ('TW', 'Taiwan'),
        ('UZ', 'Uzbekistan'), ('VN', 'Vietnam'),
    ]
    for cc, name in sweep_as:
        if cc not in covered:
            add(f'sweep_doc_{cc.lower()}', 'SWEEP_AS', ProjectInput(
                title=f"Sweep Doc {name}",
                format="documentary", stage="production",
                budget=500_000, budget_currency="USD",
                shoot_locations=[ShootLocation(country=name, percent=100)],
                director_nationalities=[name],
                willing_add_coproducer=True,
            ))
    covered.update(cc for cc, _ in sweep_as)

    # ── Category SWEEP_AF: Africa countries ────────────────────────────────────────
    sweep_af = [
        ('DZ', 'Algeria'), ('EG', 'Egypt'), ('GW', 'Guinea-Bissau'), ('KE', 'Kenya'),
        ('LR', 'Liberia'), ('LS', 'Lesotho'), ('LY', 'Libya'), ('MR', 'Mauritania'),
        ('MU', 'Mauritius'), ('MW', 'Malawi'), ('MZ', 'Mozambique'), ('NA', 'Namibia'),
        ('NE', 'Niger'), ('NG', 'Nigeria'), ('RW', 'Rwanda'), ('SC', 'Seychelles'),
        ('SD', 'Sudan'), ('SL', 'Sierra Leone'), ('SN', 'Senegal'), ('SS', 'South Sudan'),
        ('ST', 'Sao Tome and Principe'), ('SZ', 'Eswatini'), ('TD', 'Chad'), ('TG', 'Togo'),
        ('TN', 'Tunisia'), ('TZ', 'Tanzania'), ('UG', 'Uganda'), ('ZM', 'Zambia'), ('ZW', 'Zimbabwe'),
    ]
    for cc, name in sweep_af:
        if cc not in covered:
            add(f'sweep_doc_{cc.lower()}', 'SWEEP_AF', ProjectInput(
                title=f"Sweep Doc {name}",
                format="documentary", stage="production",
                budget=500_000, budget_currency="EUR",
                shoot_locations=[ShootLocation(country=name, percent=100)],
                director_nationalities=[name],
                willing_add_coproducer=True,
            ))
    covered.update(cc for cc, _ in sweep_af)

    # ── Category SWEEP_OC: Oceania countries ───────────────────────────────────────
    sweep_oc = [
        ('FJ', 'Fiji'), ('PG', 'Papua New Guinea'), ('VU', 'Vanuatu'),
    ]
    for cc, name in sweep_oc:
        if cc not in covered:
            add(f'sweep_doc_{cc.lower()}', 'SWEEP_OC', ProjectInput(
                title=f"Sweep Doc {name}",
                format="documentary", stage="production",
                budget=500_000, budget_currency="USD",
                shoot_locations=[ShootLocation(country=name, percent=100)],
                director_nationalities=[name],
                willing_add_coproducer=True,
            ))
    covered.update(cc for cc, _ in sweep_oc)

    # ── Category SWEEP_OT: Other/Middle East countries ──────────────────────────────
    sweep_ot = [
        ('AE', 'United Arab Emirates'), ('LB', 'Lebanon'), ('SA', 'Saudi Arabia'),
    ]
    for cc, name in sweep_ot:
        if cc not in covered:
            add(f'sweep_doc_{cc.lower()}', 'SWEEP_OT', ProjectInput(
                title=f"Sweep Doc {name}",
                format="documentary", stage="production",
                budget=500_000, budget_currency="USD",
                shoot_locations=[ShootLocation(country=name, percent=100)],
                director_nationalities=[name],
                willing_add_coproducer=True,
            ))

    return scenarios


# ── Anomaly detection ─────────────────────────────────────────────────────────
def check_anomalies(result: ScenarioResult) -> list[dict]:
    issues = []

    def flag(level, msg):
        issues.append({'level': level, 'message': msg})

    if result.error:
        flag('red', f"Runtime error: {result.error}")
        return issues

    if result.num_scenarios == 0:
        flag('red', "No scenarios generated -- generator should always return results")
        return issues

    top = result.top
    pct = result.total_financing_pct
    amount = result.total_financing_amount
    budget = result.project.budget

    # Red flags
    if amount < 0:
        flag('red', f"Negative benefit amount: {amount:,.0f}")
    if pct > 100:
        flag('red', f"Total financing > 100%: {pct:.1f}%")
    if amount > budget * 2:
        flag('red', f"Benefit ({amount:,.0f}) exceeds 2x project budget ({budget:,.0f})")

    # Orange warnings
    if pct > 70:
        flag('orange', f"Unusually high financing: {pct:.1f}% — verify no double-counting")

    shoot_countries = {sl.country for sl in result.project.shoot_locations}
    total_shoot_pct = sum(sl.percent for sl in result.project.shoot_locations)

    # If single-country shoot and no benefit
    if len(shoot_countries) == 1 and pct < 5 and total_shoot_pct >= 90:
        flag('orange', f"Very low financing ({pct:.1f}%) for 100% shoot in one country — check incentive coverage")

    # Check for zero-benefit incentives that have a rebate_percent
    for inc in result.top_incentives:
        if inc['rate'] and inc['rate'] > 0 and inc['amount'] == 0 and inc['contribution_pct'] == 0:
            flag('orange', f"Incentive '{inc['name']}' has {inc['rate']}% rate but 0 benefit — check spend threshold")

    # Mutual exclusivity: France TRIP + Crédit d'impôt should not both appear
    inc_names = [i['name'] for i in result.top_incentives]
    if any('TRIP' in n for n in inc_names) and any("Crédit d'impôt Cinéma" in n for n in inc_names):
        flag('orange', "France TRIP and Crédit d'impôt Cinéma both appear — mutual exclusivity violation?")

    # Non-EUR currency with EUR benefit — no conversion note
    if result.project.budget_currency not in ('EUR',) and result.financing_currency == 'EUR':
        flag('orange', f"Project budget in {result.project.budget_currency} but benefits shown in EUR — currency conversion not transparent")

    # Runtime check
    if result.runtime_ms > 10_000:
        flag('orange', f"Slow scenario generation: {result.runtime_ms:.0f}ms")

    # Info
    flag('info', f"{result.num_scenarios} scenario(s) generated in {result.runtime_ms:.0f}ms")
    if top.near_misses:
        flag('info', f"{len(top.near_misses)} near-miss(es): " +
             "; ".join(f"{nm.incentive_name} ({nm.gap_description})" for nm in top.near_misses[:3]))

    return issues


# ── Report generation ─────────────────────────────────────────────────────────
def generate_individual_report(result: ScenarioResult, anomalies: list[dict]) -> str:
    """Generate a detailed markdown report for one scenario."""
    report = []
    report.append(f"# SCENARIO: {result.name}")
    report.append(f"Category: **{result.category}** | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Anomalies first
    reds = [a for a in anomalies if a['level'] == 'red']
    oranges = [a for a in anomalies if a['level'] == 'orange']
    if reds or oranges:
        report.append("## ANOMALIES")
        for a in reds:
            report.append(f"- **[RED]** {a['message']}")
        for a in oranges:
            report.append(f"- **[WARN]** {a['message']}")
        report.append("")

    # Project input
    report.append("## PROJECT INPUT")
    report.append(f"```json\n{result.project.model_dump_json(indent=2)}\n```\n")

    if result.error:
        report.append(f"## ERROR\n```\n{result.error}\n```")
        return "\n".join(report)

    if not result.top:
        report.append("## RESULT\nNo scenarios generated.")
        return "\n".join(report)

    top = result.top
    report.append("## RESULT SUMMARY")
    report.append(f"- **Scenarios found:** {result.num_scenarios}")
    report.append(f"- **Top financing:** {result.total_financing_pct:.1f}% ({result.financing_currency} {result.total_financing_amount:,.0f})")
    report.append(f"- **Partners:** {', '.join(p.country_name for p in top.partners)}")
    report.append(f"- **Rationale:** {top.rationale}\n")

    report.append("## PARTNERS & INCENTIVES")
    for partner in top.partners:
        report.append(f"### {partner.country_name} ({partner.country_code}) — {partner.role}")
        report.append(f"Est. share: {partner.estimated_share_percent or 0:.1f}%")

        if partner.eligible_incentives:
            for inc in partner.eligible_incentives:
                report.append(f"\n#### {inc.name}")
                report.append(f"- Type: {inc.incentive_type} | Rate: {inc.rebate_percent or 'N/A'}% | Contribution: {inc.estimated_contribution_percent:.1f}%")
                if inc.benefit:
                    report.append(f"- Benefit: {inc.benefit.benefit_currency} {inc.benefit.benefit_amount:,.0f}")
                    report.append(f"- Explanation: {inc.benefit.benefit_explanation}")
                    if inc.benefit.calculation_steps:
                        report.append("- Calculation:")
                        for step in inc.benefit.calculation_steps:
                            report.append(f"  - {step.label}: `{step.formula}` = {step.value:,.0f} {step.currency or ''}")
                if inc.requirements:
                    report.append("- Requirements:")
                    for req in inc.requirements:
                        report.append(f"  - [{req.category}] {req.description}")
        else:
            report.append("*No eligible incentives found.*")

        if partner.applicable_treaties:
            report.append("\n**Treaties:**")
            for t in partner.applicable_treaties:
                report.append(f"- {t.treaty_name}")

        report.append("")

    if top.near_misses:
        report.append("## NEAR-MISSES")
        for nm in top.near_misses:
            benefit_str = f" (potential: {nm.potential_benefit_currency} {nm.potential_benefit_amount:,.0f})" if nm.potential_benefit_amount else ""
            report.append(f"- **{nm.incentive_name}** [{nm.country_code}]: {nm.gap_description}{benefit_str}")
        report.append("")

    if top.suggestions:
        report.append("## SUGGESTIONS")
        for s in top.suggestions:
            amount_str = f" (~{s.estimated_currency} {s.estimated_amount:,.0f})" if s.estimated_amount else ""
            report.append(f"- [{s.effort_level or 'N/A'}] {s.description}{amount_str}")
        report.append("")

    if top.requirements:
        report.append("## OUTSTANDING REQUIREMENTS")
        for req in top.requirements:
            report.append(f"- [{req.category}] {req.description}")
        report.append("")

    return "\n".join(report)


def write_summary_report(results: list[ScenarioResult], all_anomalies: dict):
    """Write comprehensive_summary.md with overview table and anomaly sections."""
    lines = []
    lines.append("# CoPro Calculator — Comprehensive Test Summary")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Total scenarios run: **{len(results)}**\n")

    # Overview table
    lines.append("## Overview")
    lines.append("| Scenario | Cat | Budget | Currency | Top Financing % | Amount | Scenarios | Runtime (ms) |")
    lines.append("|----------|-----|--------|----------|-----------------|--------|-----------|--------------|")
    for r in results:
        err = "ERROR" if r.error else ""
        pct = f"{r.total_financing_pct:.1f}%" if not r.error else err
        amt = f"{r.financing_currency} {r.total_financing_amount:,.0f}" if not r.error else err
        ns = str(r.num_scenarios) if not r.error else err
        lines.append(
            f"| {r.name} | {r.category} | {r.project.budget:,.0f} | {r.project.budget_currency} "
            f"| {pct} | {amt} | {ns} | {r.runtime_ms:.0f} |"
        )
    lines.append("")

    # Red flags
    reds = [(r, a) for r in results for a in all_anomalies.get(r.name, []) if a['level'] == 'red']
    lines.append("## RED FLAGS")
    if reds:
        for r, a in reds:
            lines.append(f"- **{r.name}**: {a['message']}")
    else:
        lines.append("*None — all scenarios completed without critical issues.*")
    lines.append("")

    # Orange warnings
    oranges = [(r, a) for r in results for a in all_anomalies.get(r.name, []) if a['level'] == 'orange']
    lines.append("## WARNINGS")
    if oranges:
        for r, a in oranges:
            lines.append(f"- **{r.name}**: {a['message']}")
    else:
        lines.append("*None.*")
    lines.append("")

    # Country coverage matrix
    lines.append("## Country Coverage")
    lines.append("Countries that appeared as eligible incentive sources in the top scenario:\n")
    country_hits: dict[str, list[str]] = {}
    for r in results:
        if r.top:
            for p in r.top.partners:
                if p.eligible_incentives:
                    country_hits.setdefault(p.country_code, []).append(r.name)
    if country_hits:
        lines.append("| Country | Scenarios where eligible |")
        lines.append("|---------|--------------------------|")
        for cc, scenario_names in sorted(country_hits.items()):
            lines.append(f"| {cc} | {', '.join(scenario_names[:5])}{'...' if len(scenario_names)>5 else ''} |")
    else:
        lines.append("*No country coverage data.*")
    lines.append("")

    # Incentive hit rate
    lines.append("## Incentive Hit Rate")
    lines.append("Incentives that fired (had benefit > 0) across all scenarios:\n")
    incentive_hits: dict[str, int] = {}
    for r in results:
        if r.top:
            for p in r.top.partners:
                for inc in p.eligible_incentives:
                    if inc.benefit and inc.benefit.benefit_amount > 0:
                        incentive_hits[inc.name] = incentive_hits.get(inc.name, 0) + 1
    if incentive_hits:
        lines.append("| Incentive | Times Fired |")
        lines.append("|-----------|-------------|")
        for name, count in sorted(incentive_hits.items(), key=lambda x: -x[1]):
            lines.append(f"| {name} | {count} |")
    else:
        lines.append("*No incentive benefit data.*")
    lines.append("")

    # Countries with incentives but never fired
    all_eligible_countries = set(country_hits.keys())
    shoot_countries_in_tests = set()
    for r in results:
        for sl in r.project.shoot_locations:
            shoot_countries_in_tests.add(sl.country)
    lines.append("## Countries With Zero Eligible Incentives")
    lines.append("Countries used as shoot locations that never produced eligible incentives:\n")
    never_fired = []
    for r in results:
        if r.top:
            for p in r.top.partners:
                if not p.eligible_incentives and p.country_code not in all_eligible_countries:
                    never_fired.append(f"{p.country_name} ({p.country_code}) in scenario '{r.name}'")
    if never_fired:
        for nf in sorted(set(never_fired)):
            lines.append(f"- {nf}")
    else:
        lines.append("*All tested countries produced at least one eligible incentive.*")
    lines.append("")

    # Near-miss summary
    lines.append("## Near-Miss Summary")
    lines.append("Most common near-misses across all scenarios:\n")
    nm_counts: dict[str, int] = {}
    for r in results:
        if r.top:
            for nm in r.top.near_misses:
                nm_counts[nm.incentive_name] = nm_counts.get(nm.incentive_name, 0) + 1
    if nm_counts:
        lines.append("| Incentive | Near-Miss Count |")
        lines.append("|-----------|-----------------|")
        for name, count in sorted(nm_counts.items(), key=lambda x: -x[1])[:20]:
            lines.append(f"| {name} | {count} |")
    else:
        lines.append("*No near-misses detected.*")
    lines.append("")

    out_path = os.path.join(REPORTS_DIR, 'comprehensive_summary.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"\nSummary report: {out_path}")


# ── Runner ────────────────────────────────────────────────────────────────────
def ensure_seeded() -> None:
    """Fail fast when the active DB has no incentive/treaty data."""
    db = SessionLocal()
    try:
        n_incentives = db.query(Incentive).count()
        n_treaties = db.query(Treaty).count()
    finally:
        db.close()

    if n_incentives <= 0 or n_treaties <= 0:
        raise RuntimeError(
            "Database is empty for comprehensive scenario tests "
            f"(incentives={n_incentives}, treaties={n_treaties}, target={get_database_target()}). "
            "Run: cd backend && python scripts/backup_and_reseed.py"
        )


def run_scenario(scenario_dict: dict, write_report: bool = True) -> tuple[ScenarioResult, list[dict]]:
    name = scenario_dict['name']
    category = scenario_dict['category']
    project = scenario_dict['project']

    start = time.time()
    error = None
    scenarios_out = []
    db = SessionLocal()
    try:
        scenarios_out = generate_scenarios(project, db)
    except Exception as e:
        error = str(e)
    finally:
        db.close()
    runtime_ms = (time.time() - start) * 1000

    result = ScenarioResult(
        name=name, category=category, project=project,
        scenarios=scenarios_out, error=error, runtime_ms=runtime_ms,
    )
    anomalies = check_anomalies(result)

    if write_report:
        report_content = generate_individual_report(result, anomalies)
        out_path = os.path.join(REPORTS_DIR, f"{name}.md")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

    return result, anomalies


def main():
    parser = argparse.ArgumentParser(description="Comprehensive CoPro Calculator scenario tests")
    parser.add_argument('--category', help='Run only this category (A/B/C/D/E/F/SWEEP/SWEEP_EU/SWEEP_AM/SWEEP_AS/SWEEP_AF/SWEEP_OC/SWEEP_OT)')
    parser.add_argument('--scenario', help='Run a single scenario by name')
    parser.add_argument('--summary-only', action='store_true', help='Skip individual report files')
    args = parser.parse_args()

    os.makedirs(REPORTS_DIR, exist_ok=True)
    try:
        ensure_seeded()
    except RuntimeError as err:
        print(f"ERROR: {err}")
        raise SystemExit(1) from err

    all_scenarios = build_all_scenarios()

    if args.scenario:
        all_scenarios = [s for s in all_scenarios if s['name'] == args.scenario]
    elif args.category:
        all_scenarios = [s for s in all_scenarios if s['category'].upper() == args.category.upper()]

    if not all_scenarios:
        print(f"No scenarios matched. Available categories: A B C D E F SWEEP SWEEP_EU SWEEP_AM SWEEP_AS SWEEP_AF SWEEP_OC SWEEP_OT")
        return

    print(f"Running {len(all_scenarios)} scenario(s)...\n")

    results = []
    all_anomalies = {}

    for i, s in enumerate(all_scenarios, 1):
        print(f"[{i:2d}/{len(all_scenarios)}] {s['category']:5s} {s['name']}", end=" ... ", flush=True)
        result, anomalies = run_scenario(s, write_report=not args.summary_only)
        results.append(result)
        all_anomalies[result.name] = anomalies

        reds = sum(1 for a in anomalies if a['level'] == 'red')
        oranges = sum(1 for a in anomalies if a['level'] == 'orange')

        status = f"{result.total_financing_pct:.1f}% ({result.financing_currency} {result.total_financing_amount:,.0f})"
        if result.error:
            status = f"ERROR: {result.error[:60]}"
        flags = ""
        if reds:
            flags += f" [RED x{reds}]"
        if oranges:
            flags += f" [WARN x{oranges}]"
        print(f"{status}{flags}")

    write_summary_report(results, all_anomalies)

    # Final counts
    total_reds = sum(1 for r in results for a in all_anomalies.get(r.name, []) if a['level'] == 'red')
    total_oranges = sum(1 for r in results for a in all_anomalies.get(r.name, []) if a['level'] == 'orange')
    print(f"\nDone. {len(results)} scenarios | RED {total_reds} | WARN {total_oranges}")
    print(f"Reports: {REPORTS_DIR}")


if __name__ == "__main__":
    main()
