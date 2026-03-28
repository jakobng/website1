"""Tests for scenario generation."""
import pytest
from app.database import SessionLocal, engine, Base
from app.models import Incentive, Treaty, MultilateralMember
from app.schemas import ProjectInput, ShootLocation
from app.scenario_generator import generate_scenarios


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables and seed minimal test data for each test."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clean
    db.query(MultilateralMember).delete()
    db.query(Treaty).delete()
    db.query(Incentive).delete()
    db.commit()

    # Add test incentives
    db.add(Incentive(
        name="Spain Tax Credit",
        country_code="ES",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        rebate_applies_to="qualifying_spend",
        eligible_formats=["feature_fiction", "documentary"],
        eligible_stages=["production"],
        local_producer_required=True,
        max_cap_currency="EUR",
        source_url="https://example.com/spain",
        source_description="Test source",
    ))
    db.add(Incentive(
        name="UK AVEC",
        country_code="GB",
        incentive_type="tax_credit",
        rebate_percent=34.0,
        rebate_applies_to="qualifying_spend",
        min_spend_percent=10.0,
        cultural_test_required=True,
        cultural_test_min_score=18,
        cultural_test_total_score=35,
        eligible_formats=["feature_fiction", "documentary"],
        eligible_stages=["production"],
        local_producer_required=True,
        max_cap_currency="GBP",
        source_url="https://example.com/uk",
        source_description="Test source",
    ))
    db.add(Incentive(
        name="France TRIP",
        country_code="FR",
        incentive_type="tax_rebate",
        rebate_percent=30.0,
        max_cap_amount=30_000_000,
        eligible_formats=["feature_fiction"],
        eligible_stages=["production"],
        local_producer_required=True,
        max_cap_currency="EUR",
        source_url="https://example.com/france",
        source_description="Test source",
    ))

    # Add a treaty
    db.add(Treaty(
        name="France-UK Treaty",
        treaty_type="bilateral",
        country_a_code="FR",
        country_b_code="GB",
        min_share_percent=20,
        max_share_percent=80,
        eligible_formats=["feature_fiction", "documentary"],
        creative_contribution_required=True,
        creative_requirements_summary="Proportional creative contribution",
        requires_prior_approval=True,
        is_active=True,
        source_url="https://example.com/treaty",
        source_description="Test treaty source",
    ))

    db.commit()
    db.close()
    yield
    # Cleanup
    db = SessionLocal()
    db.query(MultilateralMember).delete()
    db.query(Treaty).delete()
    db.query(Incentive).delete()
    db.commit()
    db.close()


def _make_project(**overrides) -> ProjectInput:
    defaults = dict(
        title="Test Film",
        format="feature_fiction",
        stage="production",
        budget=3_500_000,
        budget_currency="EUR",
        shoot_locations=[
            ShootLocation(country="Spain", percent=50),
            ShootLocation(country="United Kingdom", percent=30),
        ],
        director_nationalities=["France"],
        producer_nationalities=["United Kingdom"],
        willing_add_coproducer=True,
    )
    defaults.update(overrides)
    return ProjectInput(**defaults)


class TestScenarioGeneration:
    def test_generates_scenarios(self):
        db = SessionLocal()
        project = _make_project()
        scenarios = generate_scenarios(project, db)
        db.close()
        assert len(scenarios) > 0

    def test_scenarios_sorted_by_financing(self):
        db = SessionLocal()
        project = _make_project()
        scenarios = generate_scenarios(project, db)
        db.close()
        for i in range(len(scenarios) - 1):
            assert scenarios[i].estimated_total_financing_percent >= scenarios[i + 1].estimated_total_financing_percent

    def test_scenario_has_partners(self):
        db = SessionLocal()
        project = _make_project()
        scenarios = generate_scenarios(project, db)
        db.close()
        assert all(len(s.partners) > 0 for s in scenarios)

    def test_treaty_attached_when_applicable(self):
        db = SessionLocal()
        project = _make_project()
        scenarios = generate_scenarios(project, db)
        db.close()
        # At least one scenario should include both FR and GB, and thus the treaty
        has_treaty = any(
            len(s.treaty_basis) > 0 and any("France-UK" in t.treaty_name for t in s.treaty_basis)
            for s in scenarios
        )
        assert has_treaty

    def test_no_duplicate_scenarios(self):
        db = SessionLocal()
        project = _make_project()
        scenarios = generate_scenarios(project, db)
        db.close()
        combos = []
        for s in scenarios:
            combo = tuple(sorted(p.country_code for p in s.partners))
            combos.append(combo)
        assert len(combos) == len(set(combos))

    def test_director_nationality_creates_scenario(self):
        """Director from France should generate a scenario including France."""
        db = SessionLocal()
        project = _make_project(director_nationalities=["France"])
        scenarios = generate_scenarios(project, db)
        db.close()
        has_france = any(
            any(p.country_code == "FR" for p in s.partners)
            for s in scenarios
        )
        assert has_france

    def test_empty_shoot_locations(self):
        db = SessionLocal()
        project = _make_project(shoot_locations=[])
        scenarios = generate_scenarios(project, db)
        db.close()
        # Should still generate scenarios from director/producer nationalities
        # (may or may not find any — depends on eligibility)
        assert isinstance(scenarios, list)

    def test_benefit_amounts_are_positive(self):
        db = SessionLocal()
        project = _make_project()
        scenarios = generate_scenarios(project, db)
        db.close()
        for s in scenarios:
            if s.estimated_total_financing_percent > 0:
                assert s.estimated_total_financing_amount > 0

    def test_source_references_present(self):
        """Every incentive benefit should have source references."""
        db = SessionLocal()
        project = _make_project()
        scenarios = generate_scenarios(project, db)
        db.close()
        for s in scenarios:
            for p in s.partners:
                for inc in p.eligible_incentives:
                    if inc.benefit:
                        assert len(inc.benefit.sources) > 0, f"{inc.name} missing source references"


class TestDocumentaryProjects:
    """Validate scenarios for real-world documentary project profiles."""

    def test_low_budget_documentary(self):
        """€100K micro-budget documentary shooting in Spain.

        Should still generate scenarios — no hard budget block for docs.
        """
        db = SessionLocal()
        project = _make_project(
            format="documentary",
            budget=100_000,
            shoot_locations=[ShootLocation(country="Spain", percent=100)],
            director_nationalities=["Spain"],
        )
        scenarios = generate_scenarios(project, db)
        db.close()
        assert isinstance(scenarios, list)
        # Spain incentive should be eligible for documentaries
        spain_found = any(
            any(p.country_code == "ES" for p in s.partners)
            for s in scenarios
        )
        assert spain_found, "€100K documentary should find Spain scenario"

    def test_mid_budget_documentary_multi_country(self):
        """€500K documentary shooting in Spain and UK.

        Both countries' incentives accept documentaries.
        """
        db = SessionLocal()
        project = _make_project(
            format="documentary",
            budget=500_000,
            shoot_locations=[
                ShootLocation(country="Spain", percent=60),
                ShootLocation(country="United Kingdom", percent=40),
            ],
            director_nationalities=["France"],
            producer_nationalities=["United Kingdom"],
        )
        scenarios = generate_scenarios(project, db)
        db.close()
        assert len(scenarios) > 0
        # Should have multi-country scenario
        multi = [s for s in scenarios if len(s.partners) > 1]
        assert len(multi) > 0, "Multi-country documentary should produce multi-partner scenarios"

    def test_documentary_excluded_from_fiction_only(self):
        """France TRIP in test data only covers feature_fiction — documentary should not match it."""
        db = SessionLocal()
        project = _make_project(
            format="documentary",
            budget=1_500_000,
            shoot_locations=[ShootLocation(country="France", percent=100)],
            director_nationalities=["France"],
        )
        scenarios = generate_scenarios(project, db)
        db.close()
        # France TRIP is fiction-only in test data, so no France incentive match
        for s in scenarios:
            for p in s.partners:
                if p.country_code == "FR":
                    for inc in p.eligible_incentives:
                        assert "TRIP" not in inc.name, "Documentary should not match fiction-only TRIP"

    def test_documentary_benefit_calculation(self):
        """Verify benefit amounts are calculated correctly for documentaries."""
        db = SessionLocal()
        project = _make_project(
            format="documentary",
            budget=2_000_000,
            shoot_locations=[ShootLocation(country="Spain", percent=80)],
        )
        scenarios = generate_scenarios(project, db)
        db.close()
        spain_scenarios = [
            s for s in scenarios
            if any(p.country_code == "ES" for p in s.partners)
        ]
        assert len(spain_scenarios) > 0
        # Check that benefit amounts are positive and reasonable
        for s in spain_scenarios:
            for p in s.partners:
                if p.country_code == "ES":
                    for inc in p.eligible_incentives:
                        if inc.benefit and inc.benefit.benefit_amount > 0:
                            # 30% of qualifying spend — should be meaningful portion
                            assert inc.benefit.benefit_amount <= project.budget
