"""Tests for the rule engine eligibility checks."""
import pytest
from app.models import Incentive
from app.schemas import ProjectInput, ShootLocation
from app.rule_engine import check_incentive_eligibility


def _make_project(**overrides) -> ProjectInput:
    """Create a ProjectInput with sensible defaults."""
    defaults = dict(
        title="Test Film",
        format="feature_fiction",
        stage="production",
        budget=3_500_000,
        budget_currency="EUR",
        shoot_locations=[ShootLocation(country="Spain", percent=50), ShootLocation(country="UK", percent=30)],
        director_nationalities=["France"],
        producer_nationalities=["United Kingdom"],
        production_company_country="United Kingdom",
        post_flexible=False,
        willing_add_coproducer=True,
    )
    defaults.update(overrides)
    return ProjectInput(**defaults)


def _make_incentive(**overrides) -> Incentive:
    """Create an Incentive ORM object with sensible defaults."""
    defaults = dict(
        id=1,
        name="Test Incentive",
        country_code="ES",
        incentive_type="tax_credit",
        rebate_percent=30.0,
        rebate_applies_to="qualifying_spend",
        max_cap_currency="EUR",
        eligible_formats=["feature_fiction", "documentary", "series", "animation"],
        eligible_stages=["production"],
        local_producer_required=True,
        stacking_allowed=True,
    )
    defaults.update(overrides)
    inc = Incentive()
    for k, v in defaults.items():
        setattr(inc, k, v)
    return inc


class TestFormatEligibility:
    def test_eligible_format(self):
        project = _make_project(format="feature_fiction")
        inc = _make_incentive()
        ok, reqs, pct, benefit = check_incentive_eligibility(project, inc)
        assert ok

    def test_ineligible_format_is_hard_block(self):
        """Format mismatch is a hard block — a documentary can't become a fiction film."""
        project = _make_project(format="documentary")
        inc = _make_incentive(eligible_formats=["feature_fiction"])
        ok, reqs, pct, benefit = check_incentive_eligibility(project, inc)
        assert not ok
        assert any("format" in r.category for r in reqs)
        assert benefit is None

    def test_format_mapping(self):
        """Feature documentary maps to 'documentary' internally."""
        project = _make_project(format="feature documentary")
        inc = _make_incentive(eligible_formats=["documentary"])
        ok, _, _, _ = check_incentive_eligibility(project, inc)
        assert ok


class TestBudgetThresholds:
    def test_below_min_total_budget_is_soft(self):
        """Budget below minimum is now a soft requirement."""
        project = _make_project(budget=500_000)
        inc = _make_incentive(min_total_budget=1_000_000)
        ok, reqs, _, benefit = check_incentive_eligibility(project, inc)
        assert ok  # still eligible, but with budget requirement
        assert any("budget" in r.category for r in reqs)
        assert benefit is not None

    def test_above_min_total_budget(self):
        project = _make_project(budget=2_000_000)
        inc = _make_incentive(min_total_budget=1_000_000)
        ok, _, _, _ = check_incentive_eligibility(project, inc)
        assert ok

    def test_min_qualifying_spend_adds_requirement(self):
        """If qualifying spend is below threshold, it's a requirement, not a hard block.

        Budget breakdown model: €500K × 40% shooting × (10/10) = €200K.
        Threshold is €250K, so spend requirement should be added.
        """
        project = _make_project(budget=500_000, shoot_locations=[ShootLocation(country="Spain", percent=10)])
        inc = _make_incentive(min_qualifying_spend=250_000)
        ok, reqs, _, _ = check_incentive_eligibility(project, inc)
        # Still eligible but with a spend requirement
        assert ok
        assert any("spend" in r.category for r in reqs)


class TestLocalProducer:
    def test_no_local_producer_willing_to_add(self):
        project = _make_project(willing_add_coproducer=True, has_coproducer=[])
        inc = _make_incentive(country_code="ES", local_producer_required=True)
        ok, reqs, _, _ = check_incentive_eligibility(project, inc)
        assert ok
        assert any("coproducer" in r.description.lower() for r in reqs)

    def test_no_local_producer_not_willing(self):
        project = _make_project(willing_add_coproducer=False, has_coproducer=[])
        inc = _make_incentive(country_code="ES", local_producer_required=True)
        ok, _, _, _ = check_incentive_eligibility(project, inc)
        assert not ok

    def test_has_local_producer(self):
        project = _make_project(has_coproducer=["Spain"])
        inc = _make_incentive(country_code="ES", local_producer_required=True)
        ok, reqs, _, _ = check_incentive_eligibility(project, inc)
        assert ok
        assert not any("coproducer" in r.description.lower() for r in reqs)

    def test_nationality_counts_as_local(self):
        project = _make_project(director_nationalities=["Spain"])
        inc = _make_incentive(country_code="ES", local_producer_required=True)
        ok, reqs, _, _ = check_incentive_eligibility(project, inc)
        assert ok


class TestPostProduction:
    def test_post_required_not_flexible_is_soft(self):
        """Post-production requirement is now soft — shows as requirement, not hard block."""
        project = _make_project(post_flexible=False)
        inc = _make_incentive(post_production_local_required=True)
        ok, reqs, _, _ = check_incentive_eligibility(project, inc)
        assert ok  # soft requirement now
        assert any("post-production" in r.description.lower() for r in reqs)

    def test_post_required_flexible(self):
        project = _make_project(post_flexible=True)
        inc = _make_incentive(post_production_local_required=True)
        ok, reqs, _, _ = check_incentive_eligibility(project, inc)
        assert ok
        assert any("post-production" in r.description.lower() for r in reqs)


class TestBenefitCalculation:
    def test_basic_rebate_calculation(self):
        """Budget breakdown: €3.5M × 40% shooting × (50/50 country share) = €1.4M × 30% = €420K."""
        project = _make_project(budget=3_500_000, shoot_locations=[ShootLocation(country="Spain", percent=50)])
        inc = _make_incentive(rebate_percent=30.0, country_code="ES")
        ok, _, pct, benefit = check_incentive_eligibility(project, inc)
        assert ok
        assert benefit is not None
        assert benefit.benefit_amount == 420_000
        assert abs(pct - 12.0) < 0.2  # 12% of total budget

    def test_max_cap_applied(self):
        """Benefit should be capped at max_cap_amount."""
        project = _make_project(budget=100_000_000, shoot_locations=[ShootLocation(country="Spain", percent=80)])
        inc = _make_incentive(rebate_percent=30.0, max_cap_amount=10_000_000, country_code="ES")
        ok, _, _, benefit = check_incentive_eligibility(project, inc)
        assert ok
        assert benefit is not None
        assert benefit.benefit_amount == 10_000_000

    def test_labour_only_rebate(self):
        """Canada-style: 25% of labour, labour = 60% of local spend.

        Budget breakdown: €2M × 40% shooting × (100/100) = €800K local spend.
        Labour: €800K × 60% = €480K. Credit: €480K × 25% = €120K.
        """
        project = _make_project(budget=2_000_000, shoot_locations=[ShootLocation(country="Canada", percent=100)])
        inc = _make_incentive(
            country_code="CA", rebate_percent=25.0, rebate_applies_to="labour_only",
        )
        ok, _, _, benefit = check_incentive_eligibility(project, inc)
        assert ok
        assert benefit is not None
        assert benefit.benefit_amount == 120_000

    def test_zero_shoot_percent_gives_zero_benefit(self):
        """No shoot in country = no spend = no benefit."""
        project = _make_project(shoot_locations=[ShootLocation(country="UK", percent=100)])
        inc = _make_incentive(rebate_percent=30.0, country_code="ES")
        ok, _, pct, benefit = check_incentive_eligibility(project, inc)
        assert ok  # still "eligible" if willing to add coproducer
        assert benefit is not None
        assert benefit.benefit_amount == 0

    def test_grant_no_percentage(self):
        """Grant without rebate_percent gives benefit_amount = 0."""
        project = _make_project()
        inc = _make_incentive(rebate_percent=None, incentive_type="grant", max_cap_amount=5_000_000)
        ok, _, _, benefit = check_incentive_eligibility(project, inc)
        assert ok
        assert benefit is not None
        assert benefit.benefit_amount == 0
        assert "grant" in benefit.benefit_explanation.lower()


class TestConditionalRates:
    def test_format_eq_reduces_rate_for_documentary(self):
        """Australia Producer Offset: 40% for feature, 30% for documentary."""
        project = _make_project(
            format="documentary", budget=2_000_000,
            shoot_locations=[ShootLocation(country="Australia", percent=100)],
        )
        inc = _make_incentive(
            country_code="AU", rebate_percent=40.0,
            eligible_formats=["feature_fiction", "documentary"],
            conditional_rates=[
                {"condition": "format_eq", "format": "documentary", "rate": 30.0,
                 "note": "30% for documentary (40% for feature films)."}
            ],
        )
        ok, _, pct, benefit = check_incentive_eligibility(project, inc)
        assert ok
        assert benefit is not None
        # €2M × 40% shooting × (100/100) = €800K × 30% = €240K
        assert benefit.benefit_amount == 240_000

    def test_format_eq_does_not_apply_to_other_formats(self):
        """Feature fiction should still get the base 40% rate."""
        project = _make_project(
            format="feature_fiction", budget=2_000_000,
            shoot_locations=[ShootLocation(country="Australia", percent=100)],
        )
        inc = _make_incentive(
            country_code="AU", rebate_percent=40.0,
            eligible_formats=["feature_fiction", "documentary"],
            conditional_rates=[
                {"condition": "format_eq", "format": "documentary", "rate": 20.0,
                 "note": "20% for documentary."}
            ],
        )
        ok, _, pct, benefit = check_incentive_eligibility(project, inc)
        assert ok
        assert benefit is not None
        # €2M × 40% shooting × (100/100) = €800K × 40% = €320K
        assert benefit.benefit_amount == 320_000

    def test_format_eq_increases_rate_for_documentary(self):
        """Spain Navarre: 50% for documentary (vs 45% base)."""
        project = _make_project(
            format="documentary", budget=2_000_000,
            shoot_locations=[ShootLocation(country="Spain", percent=100)],
        )
        inc = _make_incentive(
            country_code="ES", rebate_percent=45.0,
            conditional_rates=[
                {"condition": "format_eq", "format": "documentary", "rate": 50.0,
                 "note": "50% rate for documentaries."}
            ],
        )
        ok, _, pct, benefit = check_incentive_eligibility(project, inc)
        assert ok
        assert benefit is not None
        # €2M × 40% shooting × (100/100) = €800K × 50% = €400K
        assert benefit.benefit_amount == 400_000


class TestCulturalTest:
    def test_cultural_test_adds_requirement(self):
        project = _make_project()
        inc = _make_incentive(cultural_test_required=True, cultural_test_min_score=18, cultural_test_total_score=35)
        ok, reqs, _, _ = check_incentive_eligibility(project, inc)
        assert ok
        assert any("cultural test" in r.description.lower() for r in reqs)
        assert any("18/35" in r.description for r in reqs)


class TestSourceReferences:
    def test_source_attached_to_requirements(self):
        """Requirements should carry source references from the incentive."""
        project = _make_project(post_flexible=True)
        inc = _make_incentive(
            post_production_local_required=True,
            source_url="https://example.com/rules",
            source_description="Official Rules, Art. 5",
        )
        ok, reqs, _, _ = check_incentive_eligibility(project, inc)
        assert ok
        post_req = [r for r in reqs if "post-production" in r.description.lower()]
        assert len(post_req) > 0
        assert post_req[0].source is not None
        assert post_req[0].source.url == "https://example.com/rules"

    def test_source_in_benefit(self):
        project = _make_project()
        inc = _make_incentive(
            source_url="https://example.com/rules",
            source_description="Test Source",
        )
        ok, _, _, benefit = check_incentive_eligibility(project, inc)
        assert ok
        assert benefit is not None
        assert len(benefit.sources) == 1
        assert benefit.sources[0].url == "https://example.com/rules"
