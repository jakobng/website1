"""Rule engine: evaluates project against incentive and treaty rules.

Key fixes over previous version:
- Separates min_total_budget from min_qualifying_spend
- Handles rebate_applies_to (qualifying_spend vs labour_only)
- No hardcoded 20% post-production assumption
- Transparent calculation notes showing the math
- Source references attached to every requirement and benefit
- Live exchange rates with 24h cache (frankfurter.app / ECB)
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error

from app.schemas import (
    ProjectInput,
    EligibleIncentive,
    Requirement,
    IncentiveBenefit,
    CalculationStep,
    SourceReference,
    DocumentReference,
    NearMiss,
)
from app.models import Incentive
from app import countries

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exchange rates to EUR — live rates from frankfurter.app (ECB data).
# Cached for 24 hours. Falls back to static rates if API is unreachable.
# ---------------------------------------------------------------------------

_STATIC_RATES_TO_EUR: dict[str, float] = {
    "EUR": 1.0,
    "USD": 0.92,
    "GBP": 1.17,
    "CHF": 1.05,
    "PLN": 0.23,
    "NOK": 0.087,
    "SEK": 0.088,
    "DKK": 0.134,
    "CZK": 0.040,
    "HUF": 0.0025,
    "RON": 0.20,
    "BGN": 0.51,
    "HRK": 0.133,
    "ISK": 0.0067,
    "TRY": 0.027,
    "AUD": 0.60,
    "NZD": 0.55,
    "CAD": 0.68,
    "ZAR": 0.051,
    "KRW": 0.00069,
    "ARS": 0.00088,
    "COP": 0.00023,
    "BRL": 0.17,
    "CLP": 0.00098,
    "PEN": 0.25,
    "MXN": 0.053,
    "DOP": 0.016,
    "UYU": 0.022,
    "JMD": 0.006,
    # MENA
    "AED": 0.25,
    "QAR": 0.25,
    "SAR": 0.24,
    "EGP": 0.019,
    "JOD": 1.30,
    "TND": 0.30,
    "MAD": 0.091,
    "ILS": 0.25,
    # Asia-Pacific
    "INR": 0.011,
    "THB": 0.027,
    "MYR": 0.21,
    "SGD": 0.70,
    "PHP": 0.016,
    "IDR": 0.00006,
    "VND": 0.000037,
    "JPY": 0.0063,
    "CNY": 0.13,
    "TWD": 0.029,
    "HKD": 0.12,
    # Other
    "MDL": 0.051,
    "NGN": 0.00058,
    "BAM": 0.51,
    "UAH": 0.023,
}

# In-memory cache for live rates
_live_rates: dict[str, float] | None = None
_live_rates_fetched_at: float = 0.0
_CACHE_TTL_SECONDS = 86400  # 24 hours
_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "exchange_rates_cache.json")


def _fetch_live_rates() -> dict[str, float] | None:
    """Fetch latest EUR-base rates from frankfurter.app (ECB data). Returns None on failure."""
    try:
        req = urllib.request.Request(
            "https://api.frankfurter.app/latest?base=EUR",
            headers={"User-Agent": "CoPro-Calculator/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        rates = data.get("rates", {})
        if not rates:
            return None
        # frankfurter returns rates FROM EUR (e.g. EUR→USD = 1.08)
        # We need rates TO EUR (e.g. USD→EUR = 1/1.08 ≈ 0.926)
        to_eur: dict[str, float] = {"EUR": 1.0}
        for ccy, rate in rates.items():
            if rate and rate > 0:
                to_eur[ccy.upper()] = 1.0 / rate
        return to_eur
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, OSError) as e:
        logger.warning("Failed to fetch live exchange rates: %s", e)
        return None


def _load_cached_rates() -> tuple[dict[str, float] | None, float]:
    """Load rates from disk cache. Returns (rates, timestamp) or (None, 0)."""
    try:
        with open(_CACHE_FILE, "r") as f:
            cached = json.load(f)
        return cached.get("rates"), cached.get("fetched_at", 0.0)
    except (OSError, json.JSONDecodeError):
        return None, 0.0


def _save_cached_rates(rates: dict[str, float], fetched_at: float) -> None:
    """Persist rates to disk cache."""
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump({"rates": rates, "fetched_at": fetched_at}, f)
    except OSError as e:
        logger.warning("Failed to save exchange rate cache: %s", e)


def _get_rates() -> dict[str, float]:
    """Return current exchange rates (to EUR), using cache + live fetch + static fallback."""
    global _live_rates, _live_rates_fetched_at

    now = time.time()

    # 1. In-memory cache is fresh
    if _live_rates and (now - _live_rates_fetched_at) < _CACHE_TTL_SECONDS:
        return _live_rates

    # 2. Try disk cache
    disk_rates, disk_ts = _load_cached_rates()
    if disk_rates and (now - disk_ts) < _CACHE_TTL_SECONDS:
        _live_rates = disk_rates
        _live_rates_fetched_at = disk_ts
        logger.info("Loaded exchange rates from disk cache (age: %.0fh)", (now - disk_ts) / 3600)
        return _live_rates

    # 3. Fetch fresh rates
    fresh = _fetch_live_rates()
    if fresh:
        # Merge with static rates so currencies not covered by ECB still work
        merged = {**_STATIC_RATES_TO_EUR, **fresh}
        _live_rates = merged
        _live_rates_fetched_at = now
        _save_cached_rates(merged, now)
        logger.info("Fetched fresh exchange rates (%d currencies)", len(fresh))
        return _live_rates

    # 4. Stale disk cache is better than nothing
    if disk_rates:
        _live_rates = disk_rates
        _live_rates_fetched_at = disk_ts
        logger.warning("Using stale disk cache (age: %.0fh)", (now - disk_ts) / 3600)
        return _live_rates

    # 5. Final fallback: static rates
    logger.warning("Using static fallback exchange rates — live rates unavailable")
    _live_rates = _STATIC_RATES_TO_EUR
    _live_rates_fetched_at = now
    return _live_rates


def _to_eur(amount: float | None, currency: str) -> float | None:
    """Convert an amount to EUR using live rates (with fallback). Returns None if input is None."""
    if amount is None:
        return None
    currency = currency.upper()
    if currency == "EUR":
        return amount
    rates = _get_rates()
    rate = rates.get(currency)
    if rate is None:
        logger.warning("Unknown currency '%s' — using 1:1 fallback to EUR. Amount: %.2f", currency, amount)
        return amount
    return amount * rate


def _convert(amount: float | None, from_ccy: str, to_ccy: str) -> float | None:
    """Convert between any two supported currencies via EUR."""
    if amount is None:
        return None
    from_ccy = from_ccy.upper()
    to_ccy = to_ccy.upper()
    if from_ccy == to_ccy:
        return amount
    eur_amount = _to_eur(amount, from_ccy)
    if to_ccy == "EUR":
        return eur_amount
    rates = _get_rates()
    rate = rates.get(to_ccy)
    if rate is None:
        logger.warning("Unknown target currency '%s' — returning EUR amount", to_ccy)
        return eur_amount
    return eur_amount / rate


def _threshold_currency(incentive: Incentive) -> str:
    """Return the currency that min_total_budget / min_qualifying_spend are denominated in."""
    return incentive.min_spend_currency or incentive.max_cap_currency or "EUR"


def _effective_min_budget(project: ProjectInput, incentive: Incentive) -> float | None:
    """Return the minimum total budget threshold appropriate for the project's format."""
    FORMAT_MAP = {
        "feature fiction": "feature_fiction", "feature documentary": "documentary",
        "documentary": "documentary", "series": "series", "animation": "animation",
        "feature_fiction": "feature_fiction",
    }
    fmt = FORMAT_MAP.get(project.format.lower(), project.format.lower().replace(" ", "_"))
    if fmt == "documentary" and incentive.min_total_budget_documentary is not None:
        return incentive.min_total_budget_documentary
    return incentive.min_total_budget


def _effective_min_spend(project: ProjectInput, incentive: Incentive) -> float | None:
    """Return the minimum qualifying spend threshold appropriate for the project's format."""
    FORMAT_MAP = {
        "feature fiction": "feature_fiction", "feature documentary": "documentary",
        "documentary": "documentary", "series": "series", "animation": "animation",
        "feature_fiction": "feature_fiction",
    }
    fmt = FORMAT_MAP.get(project.format.lower(), project.format.lower().replace(" ", "_"))
    if fmt == "documentary" and incentive.min_qualifying_spend_documentary is not None:
        return incentive.min_qualifying_spend_documentary
    return incentive.min_qualifying_spend


def _percent_in_country(project: ProjectInput, country_code: str) -> float:
    """Return total shoot percentage in the given country."""
    total = 0.0
    for loc in project.shoot_locations:
        loc_code = countries.resolve_or_keep(loc.country)
        if loc_code.upper() == country_code.upper():
            total += loc.percent
    return total


def _spend_in_country(project: ProjectInput, country_code: str) -> float | None:
    """Return explicit spend allocation for a country, or None if not specified."""
    for alloc in project.spend_allocations:
        alloc_code = countries.resolve_or_keep(alloc.country)
        if alloc_code.upper() == country_code.upper():
            return alloc.amount
    return None


def _estimate_spend_in_country(project: ProjectInput, country_code: str, shoot_pct: float) -> float:
    """Estimate spend in a country using the budget breakdown model.

    Shooting spend (default 40% of budget) is divided across shoot locations
    proportionally to their shoot percentages. Post-production spend (default 35%)
    is assigned to the post_production_country if specified. The remainder
    (overhead, legal, contingency) is not location-dependent.
    """
    total_shoot = sum(loc.percent for loc in project.shoot_locations) or 100.0
    # Shooting spend share for this country
    shooting_amount = project.budget * project.shooting_spend_fraction * (shoot_pct / total_shoot)
    # Post-production spend if assigned to this country
    post_amount = 0.0
    if project.post_production_country:
        post_cc = countries.resolve_or_keep(project.post_production_country)
        if post_cc.upper() == country_code.upper():
            post_amount = project.budget * project.post_production_spend_fraction
    return shooting_amount + post_amount


def _has_nationality(project: ProjectInput, country_code: str) -> bool:
    """Check if any key creative is from this country."""
    for nat in project.director_nationalities or []:
        if nat and countries.resolve_or_keep(nat).upper() == country_code.upper():
            return True
    for nat in project.producer_nationalities or []:
        if nat and countries.resolve_or_keep(nat).upper() == country_code.upper():
            return True
    for cc in project.production_company_countries or []:
        if cc and countries.resolve_or_keep(cc).upper() == country_code.upper():
            return True
    if getattr(project, 'production_company_country', None):
        if countries.resolve_or_keep(project.production_company_country).upper() == country_code.upper():
            return True
    if getattr(project, 'editor_nationality', None):
        if countries.resolve_or_keep(project.editor_nationality).upper() == country_code.upper():
            return True
    return False


def _make_source(incentive: Incentive, doc_ref: DocumentReference | None = None) -> SourceReference | None:
    """Build a SourceReference from an incentive's provenance fields."""
    if not incentive.source_url:
        return None
    return SourceReference(
        url=incentive.source_url,
        description=incentive.source_description or incentive.name,
        clause_reference=getattr(incentive, 'clause_reference', None),
        accessed=incentive.last_verified,
        document_ref=doc_ref,
    )


def _build_criteria_summary(incentive: Incentive, country_name: str, has_local: bool,
                            effective_min_budget: float | None = None,
                            effective_min_spend: float | None = None) -> str:
    """Human-readable list of what you need to qualify."""
    parts = []
    thresh_ccy = _threshold_currency(incentive)
    if incentive.local_producer_required and not has_local:
        parts.append(f"a {country_name} coproducer")
    min_spend = effective_min_spend if effective_min_spend is not None else incentive.min_qualifying_spend
    if min_spend:
        min_spend_eur = _to_eur(min_spend, thresh_ccy)
        if thresh_ccy != "EUR" and min_spend_eur:
            parts.append(f"min qualifying spend of {thresh_ccy} {min_spend:,.0f} (~EUR {min_spend_eur:,.0f}) in {country_name}")
        else:
            parts.append(f"min qualifying spend of EUR {min_spend:,.0f} in {country_name}")
    if incentive.min_spend_percent:
        parts.append(f"at least {incentive.min_spend_percent}% of budget spent in {country_name}")
    if incentive.min_shoot_percent:
        parts.append(f"at least {incentive.min_shoot_percent}% of shoot in {country_name}")
    if incentive.min_shoot_days:
        parts.append(f"minimum {incentive.min_shoot_days} shooting days in {country_name}")
    if incentive.local_crew_min_percent:
        parts.append(f"at least {incentive.local_crew_min_percent}% local crew")
    if incentive.post_production_local_required:
        parts.append(f"post-production in {country_name}")
    if incentive.cultural_test_required:
        score_info = ""
        if incentive.cultural_test_min_score and incentive.cultural_test_total_score:
            score_info = f" ({incentive.cultural_test_min_score}/{incentive.cultural_test_total_score} points)"
        elif incentive.cultural_test_min_score:
            score_info = f" (min {incentive.cultural_test_min_score} points)"
        parts.append(f"pass cultural test{score_info}")
    if not parts:
        return f"Meet {country_name} programme requirements."
    return "You need: " + "; ".join(parts) + "."


def check_incentive_eligibility(
    project: ProjectInput, incentive: Incentive, doc_ref: DocumentReference | None = None,
) -> tuple[bool, list[Requirement], float, IncentiveBenefit | None]:
    """
    Evaluate project against one incentive.
    Returns (eligible, requirements, estimated_rebate_pct_of_budget, benefit_detail).

    Some requirements are "soft" (e.g. budget/spend thresholds not yet met),
    while others are "hard" (e.g. format mismatch). Hard blocks return
    eligible=False so impossible options don't leak into scenario totals.
    """
    requirements: list[Requirement] = []
    cc = incentive.country_code
    country_name = countries.display_name(cc)
    shoot_pct = _percent_in_country(project, cc)
    currency = project.budget_currency or "EUR"  # Labels now use project currency
    native_ccy = _threshold_currency(incentive)
    source = _make_source(incentive, doc_ref)

    # --- Format check (HARD block) ---
    FORMAT_MAP = {
        "feature fiction": "feature_fiction",
        "feature documentary": "documentary",
        "documentary": "documentary",
        "series": "series",
        "animation": "animation",
        "feature_fiction": "feature_fiction",
    }
    proj_format = FORMAT_MAP.get(project.format.lower(), project.format.lower().replace(" ", "_"))
    format_mismatch = bool(incentive.eligible_formats and proj_format not in incentive.eligible_formats)
    if format_mismatch:
        return False, [Requirement(
            description=f"Format '{project.format}' not eligible for {incentive.name}. Accepted: {', '.join(incentive.eligible_formats)}",
            category="format", source=source,
        )], 0.0, None

    # --- Stage check (HARD block) ---
    active_stages = [project.stage]
    if project.stages:
        for s in project.stages:
            if s not in active_stages:
                active_stages.append(s)
    
    stage_mismatch = bool(
        incentive.eligible_stages and
        not any(s in incentive.eligible_stages for s in active_stages)
    )
    if stage_mismatch:
        return False, [Requirement(
            description=f"Stage not eligible. This incentive covers: {', '.join(incentive.eligible_stages)}. Your selected stage(s): {', '.join(active_stages)}.",
            category="stage", source=source,
        )], 0.0, None

    # --- Minimum total budget (SOFT requirement) ---
    eff_min_budget = _effective_min_budget(project, incentive)
    eff_min_budget_proj = _convert(eff_min_budget, native_ccy, project.budget_currency)
    if eff_min_budget_proj and project.budget < eff_min_budget_proj:
        # Show threshold in project currency (and native if different)
        threshold_display = f"{project.budget_currency} {eff_min_budget_proj:,.0f}"
        if native_ccy != project.budget_currency:
            threshold_display += f" (~{native_ccy} {eff_min_budget:,.0f})"

        requirements.append(Requirement(
            description=f"Minimum total budget: {threshold_display}. Your budget: {project.budget_currency} {project.budget:,.0f}.",
            category="budget", source=source,
        ))

    # --- Post-production (soft) ---
    if incentive.post_production_local_required and not project.post_flexible:
        requirements.append(Requirement(
            description=f"Post-production in {country_name} required. Mark post-production as flexible to explore this incentive.",
            category="production", source=source,
        ))

    # --- Local producer: HARD block if user explicitly refuses ---
    has_local = (
        any(countries.resolve_or_keep(c).upper() == cc.upper() for c in (project.has_coproducer or []))
        or _has_nationality(project, cc)
    )
    if incentive.local_producer_required and not has_local and not project.willing_add_coproducer:
        return False, [Requirement(
            description=f"Requires a {country_name} coproducer. Enable 'willing to add coproducer' to explore this option.",
            category="producer", source=source,
        )], 0.0, None

    # --- Cultural test fail (HARD block if explicit) ---
    passed_codes = [c.upper() for c in (project.cultural_test_passed or [])]
    failed_codes = [c.upper() for c in (project.cultural_test_failed or [])]
    if cc.upper() in failed_codes:
        return False, [Requirement(
            description=f"Does not pass {country_name} cultural test (marked as failed).",
            category="cultural", source=source,
        )], 0.0, None

    # --- Shoot percent/days (HARD block) ---
    if incentive.min_shoot_percent and shoot_pct < incentive.min_shoot_percent:
        return False, [Requirement(
            description=f"Minimum shoot in {country_name}: {incentive.min_shoot_percent}%. Current: {shoot_pct}%.",
            category="production", source=source,
        )], 0.0, None

    if incentive.min_shoot_days:
        # min_shoot_days is a soft requirement — we can't verify actual days from
        # shoot percentage alone, so we surface it as a requirement instead of blocking.
        requirements.append(Requirement(
            description=f"Minimum {incentive.min_shoot_days} shooting days in {country_name} required.",
            category="production", source=source,
        ))

    # --- Soft requirements (warnings/conditions) ---

    if incentive.local_producer_required and not has_local:
        requirements.append(Requirement(
            description=f"Partner with a {country_name} coproducer (or maintain an active {country_name} production company)",
            category="producer", source=source,
        ))

    if incentive.local_crew_min_percent:
        requirements.append(Requirement(
            description=f"Hire at least {incentive.local_crew_min_percent}% local crew in {country_name}",
            category="crew", source=source,
        ))

    if incentive.post_production_local_required:
        requirements.append(Requirement(
            description=f"Complete post-production in {country_name}",
            category="production", source=source,
        ))

    if incentive.cultural_test_required:
        score_info = ""
        if incentive.cultural_test_min_score and incentive.cultural_test_total_score:
            score_info = f" (min {incentive.cultural_test_min_score}/{incentive.cultural_test_total_score} points)"
        requirements.append(Requirement(
            description=f"Pass {country_name} Cultural Test{score_info}",
            category="cultural", source=source,
        ))

    if incentive.min_spend_percent:
        requirements.append(Requirement(
            description=f"Ensure at least {incentive.min_spend_percent}% of the total budget is spent in {country_name}",
            category="spend", source=source,
        ))

    # --- Benefit calculation ---

    # Estimate qualifying spend in this country (stays in project currency)
    explicit_spend = _spend_in_country(project, cc)
    if explicit_spend is not None:
        estimated_qualifying_spend = explicit_spend
        spend_basis = "user-provided spend allocation"
    else:
        estimated_qualifying_spend = _estimate_spend_in_country(project, cc, shoot_pct)
        parts = []
        total_shoot = sum(loc.percent for loc in project.shoot_locations) or 100.0
        shooting_amount = project.budget * project.shooting_spend_fraction * (shoot_pct / total_shoot)
        if shooting_amount > 0:
            parts.append(f"shooting {project.shooting_spend_fraction*100:.0f}% × {shoot_pct/total_shoot*100:.0f}%")
        post_cc = countries.resolve_or_keep(project.post_production_country) if project.post_production_country else None
        if post_cc and post_cc.upper() == cc.upper():
            parts.append(f"post-production {project.post_production_spend_fraction*100:.0f}%")
        spend_basis = f"estimated from budget breakdown ({', '.join(parts)})"

    # Check minimum qualifying spend threshold (SOFT requirement)
    eff_min_spend = _effective_min_spend(project, incentive)
    eff_min_spend_proj = _convert(eff_min_spend, native_ccy, project.budget_currency)
    if eff_min_spend_proj and estimated_qualifying_spend < eff_min_spend_proj:
        spend_threshold_display = f"{project.budget_currency} {eff_min_spend_proj:,.0f}"
        if native_ccy != project.budget_currency:
            spend_threshold_display += f" (~{native_ccy} {eff_min_spend:,.0f})"

        requirements.append(Requirement(
            description=(
                f"Minimum qualifying spend: {spend_threshold_display}. "
                f"Estimated: {project.budget_currency} {estimated_qualifying_spend:,.0f} ({spend_basis})."
            ),
            category="spend", source=source,
        ))

    sources = [source] if source else []
    has_local_for_summary = has_local or not incentive.local_producer_required
    criteria = _build_criteria_summary(incentive, country_name, has_local_for_summary,
                                       effective_min_budget=eff_min_budget,
                                       effective_min_spend=eff_min_spend)
    src_url = incentive.source_url or None
    clause_ref = getattr(incentive, 'clause_reference', None)

    if incentive.rebate_percent:
        applies_to = incentive.rebate_applies_to or "qualifying_spend"
        steps: list[CalculationStep] = []

        effective_rebate = incentive.rebate_percent
        conditional_note = ""
        if incentive.conditional_rates:
            for cond in incentive.conditional_rates:
                condition = cond.get("condition", "")
                if condition == "vfx_spend_gt":
                    threshold = cond.get("threshold", 0)
                    threshold_proj = _convert(threshold, native_ccy, project.budget_currency)
                    new_rate = cond.get("rate", effective_rebate)
                    # Estimate VFX spend based on format (not a flat 30%)
                    vfx_fraction = {"animation": 0.50, "series": 0.20,
                                    "feature_fiction": 0.15, "documentary": 0.05
                                    }.get(proj_format, 0.15)
                    vfx_est = estimated_qualifying_spend * vfx_fraction
                    if project.vfx_flexible and vfx_est >= threshold_proj * 0.5:
                        effective_rebate = new_rate
                        conditional_note = cond.get("note", f"Enhanced rate {new_rate}% applied (VFX condition)")
                    elif vfx_est >= threshold_proj:
                        effective_rebate = new_rate
                        conditional_note = cond.get("note", f"Enhanced rate {new_rate}% applied")
                elif condition == "budget_gte":
                    threshold = cond.get("threshold", 0)
                    threshold_proj = _convert(threshold, native_ccy, project.budget_currency)
                    if project.budget >= threshold_proj:
                        conditional_note = cond.get("note", f"Relaxed threshold applied for budget ≥{project.budget_currency} {threshold_proj:,.0f}")
                elif condition == "format_eq":
                    # Format-specific rate override (e.g. AU Producer Offset: 20% for documentary)
                    target_format = cond.get("format", "")
                    if proj_format == target_format:
                        new_rate = cond.get("rate", effective_rebate)
                        effective_rebate = new_rate
                        conditional_note = cond.get("note", f"Rate adjusted to {new_rate}% for {target_format} format")

        # Step 1: qualifying spend
        if explicit_spend is None:
            formula_parts = [f"budget × {project.shooting_spend_fraction*100:.0f}% shooting × {shoot_pct:.0f}% country share"]
            post_cc = countries.resolve_or_keep(project.post_production_country) if project.post_production_country else None
            if post_cc and post_cc.upper() == cc.upper():
                formula_parts.append(f"+ budget × {project.post_production_spend_fraction*100:.0f}% post-production")
            spend_formula = " ".join(formula_parts)
        else:
            spend_formula = "user-provided spend allocation"
        steps.append(CalculationStep(
            label="Qualifying spend (estimated)",
            formula=spend_formula,
            value=round(estimated_qualifying_spend, 0),
            currency=currency,
            note=spend_basis,
            source_url=src_url,
            clause_reference=clause_ref,
        ))

        if conditional_note:
            steps.append(CalculationStep(
                label="Enhanced rate applied",
                formula=f"base rate {incentive.rebate_percent}% → {effective_rebate}%",
                value=effective_rebate,
                note=conditional_note,
                source_url=src_url,
                clause_reference=clause_ref,
            ))

        if applies_to == "labour_only":
            labour_fraction = incentive.labour_fraction if incentive.labour_fraction is not None else 0.6
            # TODO: labour_fraction should be set per incentive in seed data with source citation
            qualifying_base = estimated_qualifying_spend * labour_fraction
            benefit_amount = qualifying_base * (effective_rebate / 100)
            steps.append(CalculationStep(
                label="Qualified labour (estimated)",
                formula=f"qualifying spend × {labour_fraction*100:.0f}% (standard labour cap)",
                value=round(qualifying_base, 0),
                currency=currency,
                source_url=src_url,
                clause_reference=clause_ref,
            ))
            steps.append(CalculationStep(
                label=f"{incentive.incentive_type.replace('_', ' ').title()} ({effective_rebate}%)",
                formula=f"qualified labour × {effective_rebate}%",
                value=round(benefit_amount, 0),
                currency=currency,
                source_url=src_url,
                clause_reference=clause_ref,
            ))
            calc_notes = (
                f"Rebate applies to qualified labour only. "
                f"Estimated local spend: {currency} {estimated_qualifying_spend:,.0f} ({spend_basis}). "
                f"Labour estimated at {labour_fraction*100:.0f}% of local spend = {currency} {qualifying_base:,.0f}. "
                f"Credit: {effective_rebate}% of {currency} {qualifying_base:,.0f} = {currency} {benefit_amount:,.0f}."
            )
        else:
            qualifying_base = estimated_qualifying_spend
            benefit_amount = qualifying_base * (effective_rebate / 100)
            steps.append(CalculationStep(
                label=f"{incentive.incentive_type.replace('_', ' ').title()} ({effective_rebate}%)",
                formula=f"qualifying spend × {effective_rebate}%",
                value=round(benefit_amount, 0),
                currency=currency,
                source_url=src_url,
                clause_reference=clause_ref,
            ))
            calc_notes = (
                f"Estimated qualifying spend: {currency} {estimated_qualifying_spend:,.0f} ({spend_basis}). "
                f"Rebate: {effective_rebate}% of {currency} {qualifying_base:,.0f} = {currency} {benefit_amount:,.0f}."
            )

        if incentive.max_cap_amount:
            cap_proj = _convert(incentive.max_cap_amount, native_ccy, project.budget_currency)
            if benefit_amount > cap_proj:
                calc_notes += f" Capped at {currency} {cap_proj:,.0f}."
                steps.append(CalculationStep(
                    label="Programme cap applied",
                    formula=f"min(calculated benefit, {currency} {cap_proj:,.0f})",
                    value=round(cap_proj, 0),
                    currency=currency,
                    note=f"Benefit capped at programme maximum of {currency} {cap_proj:,.0f} (~{native_ccy} {incentive.max_cap_amount:,.0f})",
                    source_url=src_url,
                    clause_reference=clause_ref,
                ))
                benefit_amount = cap_proj

        estimated_rebate_pct = (benefit_amount / project.budget) * 100 if project.budget else 0

        explanation = (
            f"{criteria} {calc_notes} "
            f"This is an estimate, not a binding figure."
        )

        benefit = IncentiveBenefit(
            criteria_summary=criteria,
            estimated_qualifying_spend=round(estimated_qualifying_spend, 0),
            spend_currency=currency,
            benefit_type=incentive.incentive_type or "tax_credit",
            benefit_amount=round(benefit_amount, 0),
            benefit_currency=currency,
            benefit_explanation=explanation,
            calculation_notes=calc_notes,
            calculation_steps=steps,
            sources=sources,
        )
    else:
        # Grant/fund without a stored percentage
        benefit_amount = 0.0
        estimated_rebate_pct = 0.0
        cap_note = ""
        if incentive.max_cap_amount:
            cap_proj = _convert(incentive.max_cap_amount, native_ccy, project.budget_currency)
            cap_note = f" Award ceiling up to {currency} {cap_proj:,.0f} (competitive, case-specific)."
        explanation = (
            f"{criteria} This is a grant/fund programme; awards are competitive and case-specific.{cap_note}"
        )
        benefit = IncentiveBenefit(
            criteria_summary=criteria,
            estimated_qualifying_spend=round(estimated_qualifying_spend, 0),
            spend_currency=currency,
            benefit_type=incentive.incentive_type or "grant",
            benefit_amount=0.0,
            benefit_currency=currency,
            benefit_explanation=explanation,
            calculation_notes="No percentage stored; grant amounts are determined case-by-case.",
            calculation_steps=[],
            sources=sources,
        )

    return True, requirements, round(estimated_rebate_pct, 1), benefit


def check_near_miss(
    project: ProjectInput, incentive: Incentive, threshold: float = 0.50,
    doc_ref: DocumentReference | None = None,
) -> NearMiss | None:
    """Check if a project is close to qualifying for an incentive it currently misses.

    Returns a NearMiss if the project fails a requirement by <= threshold
    (e.g., 50% of the target value). Returns None if too far off or if format is wrong.
    """
    cc = incentive.country_code
    country_name = countries.display_name(cc)
    shoot_pct = _percent_in_country(project, cc)
    native_ccy = _threshold_currency(incentive)
    source = _make_source(incentive, doc_ref)

    # Hard block: format mismatch — can't near-miss this
    FORMAT_MAP = {
        "feature fiction": "feature_fiction",
        "feature documentary": "documentary",
        "documentary": "documentary",
        "series": "series",
        "animation": "animation",
        "feature_fiction": "feature_fiction",
    }
    proj_format = FORMAT_MAP.get(project.format.lower(), project.format.lower().replace(" ", "_"))
    if incentive.eligible_formats and proj_format not in incentive.eligible_formats:
        return None

    # Hard block: won't add coproducer — can't near-miss
    has_local = (
        any(countries.resolve_or_keep(c).upper() == cc.upper() for c in (project.has_coproducer or []))
        or _has_nationality(project, cc)
    )
    if incentive.local_producer_required and not has_local and not project.willing_add_coproducer:
        return None

    # Hard block: explicitly failed cultural test — can't near-miss
    failed_codes = [c.upper() for c in (project.cultural_test_failed or [])]
    if cc.upper() in failed_codes:
        return None

    # No rebate percentage stored — can't compute potential benefit easily
    if not incentive.rebate_percent:
        return None

    # Resolve format-aware thresholds and convert to project currency
    eff_min_budget = _effective_min_budget(project, incentive)
    eff_min_spend = _effective_min_spend(project, incentive)
    eff_min_budget_proj = _convert(eff_min_budget, native_ccy, project.budget_currency)
    eff_min_spend_proj = _convert(eff_min_spend, native_ccy, project.budget_currency)

    # Estimate potential benefit if fully qualifying (in project currency)
    target_pct = max(shoot_pct, incentive.min_shoot_percent or 0)
    total_shoot = sum(loc.percent for loc in project.shoot_locations) or 100.0
    potential_spend = project.budget * project.shooting_spend_fraction * (target_pct / total_shoot)
    if eff_min_spend_proj and potential_spend < eff_min_spend_proj:
        potential_spend = eff_min_spend_proj
    
    potential_benefit = potential_spend * (incentive.rebate_percent / 100.0)
    if incentive.max_cap_amount:
        cap_proj = _convert(incentive.max_cap_amount, native_ccy, project.budget_currency)
        if potential_benefit > cap_proj:
            potential_benefit = cap_proj

    # Check each requirement for near-miss gaps (return the CLOSEST gap)

    # Shoot percentage gap
    if incentive.min_shoot_percent and shoot_pct < incentive.min_shoot_percent:
        gap_ratio = shoot_pct / incentive.min_shoot_percent if incentive.min_shoot_percent else 0
        if gap_ratio >= (1 - threshold):
            return NearMiss(
                incentive_name=incentive.name,
                country_code=cc,
                country_name=country_name,
                region=incentive.region,
                incentive_type=incentive.incentive_type,
                rebate_percent=incentive.rebate_percent,
                gap_description=(
                    f"Increase shoot in {country_name} from {shoot_pct:.0f}% to {incentive.min_shoot_percent:.0f}% "
                    f"({incentive.min_shoot_percent - shoot_pct:.0f}pp gap)"
                ),
                gap_category="shoot",
                current_value=shoot_pct,
                required_value=incentive.min_shoot_percent,
                potential_benefit_amount=round(potential_benefit, 0),
                potential_benefit_currency=project.budget_currency,
                source=source,
            )

    # Budget gap
    if eff_min_budget_proj and project.budget < eff_min_budget_proj:
        gap_ratio = project.budget / eff_min_budget_proj
        if gap_ratio >= (1 - threshold):
            threshold_display = f"{project.budget_currency} {eff_min_budget_proj:,.0f}"
            if native_ccy != project.budget_currency:
                threshold_display += f" (~{native_ccy} {eff_min_budget:,.0f})"
            return NearMiss(
                incentive_name=incentive.name,
                country_code=cc,
                country_name=country_name,
                region=incentive.region,
                incentive_type=incentive.incentive_type,
                rebate_percent=incentive.rebate_percent,
                gap_description=(
                    f"Budget {project.budget_currency} {project.budget:,.0f} is {(1-gap_ratio)*100:.0f}% below "
                    f"minimum {threshold_display}"
                ),
                gap_category="budget",
                current_value=project.budget,
                required_value=eff_min_budget_proj,
                potential_benefit_amount=round(potential_benefit, 0),
                potential_benefit_currency=project.budget_currency,
                source=source,
            )

    # Qualifying spend gap
    explicit_spend = _spend_in_country(project, cc)
    est_spend = explicit_spend if explicit_spend is not None else _estimate_spend_in_country(project, cc, shoot_pct)
    if eff_min_spend_proj and est_spend < eff_min_spend_proj:
        gap_ratio = est_spend / eff_min_spend_proj if eff_min_spend_proj else 0
        if gap_ratio >= (1 - threshold):
            threshold_display = f"{project.budget_currency} {eff_min_spend_proj:,.0f}"
            if native_ccy != project.budget_currency:
                threshold_display += f" (~{native_ccy} {eff_min_spend:,.0f})"
            return NearMiss(
                incentive_name=incentive.name,
                country_code=cc,
                country_name=country_name,
                region=incentive.region,
                incentive_type=incentive.incentive_type,
                rebate_percent=incentive.rebate_percent,
                gap_description=(
                    f"Qualifying spend {project.budget_currency} {est_spend:,.0f} is {(1-gap_ratio)*100:.0f}% below "
                    f"minimum {threshold_display}"
                ),
                gap_category="spend",
                current_value=est_spend,
                required_value=eff_min_spend_proj,
                potential_benefit_amount=round(potential_benefit, 0),
                potential_benefit_currency=project.budget_currency,
                source=source,
            )

    return None

    return None
