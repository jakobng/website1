"""Scenario generator: produces ranked coproduction financing scenarios.

Key design principles:
- ALWAYS returns scenarios — never an empty list
- Scenarios requiring fewest changes from the user's current setup come first
- "Stretch" scenarios (requiring major restructuring) are included but ranked lower
- Every country with incentive data is a candidate, not just shoot countries
"""
from __future__ import annotations

from sqlalchemy.orm import Session
from app.models import Incentive, Treaty, MultilateralMember, DocumentAnnotation
from app.schemas import (
    ProjectInput,
    Scenario,
    CoproductionPartner,
    EligibleIncentive,
    NearMiss,
    Requirement,
    Suggestion,
    TreatyInfo,
    SourceReference,
    DocumentReference,
)
from app.rule_engine import check_incentive_eligibility, check_near_miss, _percent_in_country
from app import countries


def _build_doc_lookup(db: Session) -> tuple[dict[int, list[DocumentAnnotation]], dict[int, list[DocumentAnnotation]]]:
    """Build lookups: incentive_id -> annotations, treaty_id -> annotations."""
    annotations = db.query(DocumentAnnotation).order_by(DocumentAnnotation.sort_order).all()
    by_incentive: dict[int, list[DocumentAnnotation]] = {}
    by_treaty: dict[int, list[DocumentAnnotation]] = {}
    for a in annotations:
        if a.incentive_id:
            by_incentive.setdefault(a.incentive_id, []).append(a)
        if a.treaty_id:
            by_treaty.setdefault(a.treaty_id, []).append(a)
    return by_incentive, by_treaty


def _first_doc_ref(anns: list[DocumentAnnotation]) -> DocumentReference:
    """Return a DocumentReference pointing to the first annotation."""
    return DocumentReference(document_id=anns[0].document_id, annotation_id=anns[0].id)


def _get_incentives_by_country(db: Session) -> dict[str, list[Incentive]]:
    """Group incentives by country code."""
    incentives = db.query(Incentive).all()
    by_country: dict[str, list[Incentive]] = {}
    for inc in incentives:
        key = inc.country_code.upper()
        by_country.setdefault(key, []).append(inc)
    return by_country


def _get_treaties_for_pair(db: Session, code_a: str, code_b: str) -> list[Treaty]:
    """Find treaties between two countries (bilateral or multilateral covering both)."""
    a, b = code_a.upper(), code_b.upper()
    bilateral = db.query(Treaty).filter(
        Treaty.is_active == True,
        Treaty.treaty_type == "bilateral",
        (
            ((Treaty.country_a_code == a) & (Treaty.country_b_code == b)) |
            ((Treaty.country_a_code == b) & (Treaty.country_b_code == a))
        )
    ).all()

    multilateral_ids_a = {m.treaty_id for m in db.query(MultilateralMember).filter(MultilateralMember.country_code == a).all()}
    multilateral_ids_b = {m.treaty_id for m in db.query(MultilateralMember).filter(MultilateralMember.country_code == b).all()}
    shared = multilateral_ids_a & multilateral_ids_b
    multilateral = db.query(Treaty).filter(Treaty.id.in_(shared), Treaty.is_active == True).all() if shared else []

    return bilateral + multilateral


def _get_all_treaty_partners(db: Session, code: str) -> list[str]:
    """All countries that have a treaty relationship with the given country."""
    c = code.upper()
    bilateral = db.query(Treaty).filter(
        Treaty.is_active == True,
        Treaty.treaty_type == "bilateral",
        ((Treaty.country_a_code == c) | (Treaty.country_b_code == c))
    ).all()
    partners = set()
    for t in bilateral:
        other = t.country_b_code if t.country_a_code.upper() == c else t.country_a_code
        partners.add(other.upper())

    my_treaties = {m.treaty_id for m in db.query(MultilateralMember).filter(MultilateralMember.country_code == c).all()}
    if my_treaties:
        co_members = db.query(MultilateralMember).filter(
            MultilateralMember.treaty_id.in_(my_treaties),
            MultilateralMember.country_code != c
        ).all()
        for m in co_members:
            partners.add(m.country_code.upper())

    return list(partners)


def _treaty_to_info(
    treaty: Treaty,
    doc_by_treaty: dict[int, list[DocumentAnnotation]] | None = None,
) -> TreatyInfo:
    """Convert a Treaty ORM object to a TreatyInfo schema."""
    authorities = []
    if treaty.competent_authority_a:
        authorities.append(treaty.competent_authority_a)
    if treaty.competent_authority_b:
        authorities.append(treaty.competent_authority_b)
    doc_ref = None
    if doc_by_treaty:
        anns = doc_by_treaty.get(treaty.id)
        if anns:
            doc_ref = _first_doc_ref(anns)
    source = None
    if treaty.source_url:
        source = SourceReference(
            url=treaty.source_url,
            description=treaty.source_description or treaty.name,
            accessed=treaty.last_verified,
            document_ref=doc_ref,
        )
    return TreatyInfo(
        treaty_name=treaty.name,
        min_share_percent=treaty.min_share_percent,
        max_share_percent=treaty.max_share_percent,
        creative_requirements=treaty.creative_requirements_summary,
        competent_authorities=authorities,
        requires_approval=treaty.requires_prior_approval,
        source=source,
    )


def _shoot_countries_sorted(project: ProjectInput) -> list[tuple[str, float]]:
    """List of (country_code, percent) sorted by percent descending."""
    result: list[tuple[str, float]] = []
    for loc in project.shoot_locations:
        if not loc.country or not loc.country.strip():
            continue
        code = countries.resolve_or_keep(loc.country)
        result.append((code.upper(), loc.percent))
    result.sort(key=lambda x: -x[1])
    return result


def _evaluate_country(
    project: ProjectInput,
    country_code: str,
    by_country: dict[str, list[Incentive]],
    doc_by_incentive: dict[int, list[DocumentAnnotation]] | None = None,
) -> tuple[list[EligibleIncentive], list[Requirement], float, list[NearMiss]]:
    """Evaluate all incentives for a country. Returns (eligible_incentives, requirements, total_pct, near_misses)."""
    eligible: list[EligibleIncentive] = []
    all_reqs: list[Requirement] = []
    near_misses: list[NearMiss] = []
    total_pct = 0.0
    doc_by_incentive = doc_by_incentive or {}

    # First pass: evaluate everything
    candidates = []
    ineligible_incs = []
    for inc in by_country.get(country_code.upper(), []):
        anns = doc_by_incentive.get(inc.id)
        doc_ref = _first_doc_ref(anns) if anns else None
        ok, reqs, rebate_pct, benefit = check_incentive_eligibility(project, inc, doc_ref)
        if ok:
            candidates.append({
                "inc": inc,
                "reqs": reqs,
                "rebate_pct": rebate_pct,
                "benefit": benefit
            })
        else:
            ineligible_incs.append(inc)

    # Second pass: handle mutual exclusivity
    # Sort by rebate_pct descending so we keep the best one if they conflict
    candidates.sort(key=lambda x: -x["rebate_pct"])

    selected_names = set()
    excluded_names = set()

    for cand in candidates:
        name = cand["inc"].name
        if name in excluded_names:
            continue

        eligible.append(EligibleIncentive(
            name=cand["inc"].name,
            country_code=cand["inc"].country_code,
            country_name=countries.display_name(cand["inc"].country_code),
            region=cand["inc"].region,
            incentive_type=cand["inc"].incentive_type,
            rebate_percent=cand["inc"].rebate_percent,
            requirements=cand["reqs"],
            benefit=cand["benefit"],
            estimated_contribution_percent=cand["rebate_pct"],
        ))
        total_pct += cand["rebate_pct"]
        all_reqs.extend(cand["reqs"])
        selected_names.add(name)

        # Mark mutually exclusive ones as excluded
        if cand["inc"].mutually_exclusive_with:
            for exc_name in cand["inc"].mutually_exclusive_with:
                excluded_names.add(exc_name)

    # Third pass: check near-misses for ineligible incentives
    for inc in ineligible_incs:
        anns = doc_by_incentive.get(inc.id)
        doc_ref = _first_doc_ref(anns) if anns else None
        nm = check_near_miss(project, inc, doc_ref=doc_ref)
        if nm and nm.incentive_name not in selected_names and nm.incentive_name not in excluded_names:
            near_misses.append(nm)

    # Fourth pass: check near-misses for eligible incentives with unmet requirements
    # This catches cases like "you're at 7% spend but need 10%" where the incentive
    # is technically eligible (soft req) but the user is close to a threshold
    for cand in candidates:
        if cand["reqs"]:  # has unmet requirements
            anns = doc_by_incentive.get(cand["inc"].id)
            doc_ref = _first_doc_ref(anns) if anns else None
            nm = check_near_miss(project, cand["inc"], doc_ref=doc_ref)
            if nm and nm.incentive_name in selected_names:
                near_misses.append(nm)

    return eligible, all_reqs, total_pct, near_misses


def _count_changes_needed(
    project: ProjectInput,
    country_codes: list[str],
    by_country: dict[str, list[Incentive]],
) -> int:
    """Count how many changes the user would need to make for this scenario.
    Lower = more feasible / closer to current setup. Used for ranking."""
    changes = 0
    shoot_codes = set()
    for loc in project.shoot_locations:
        if loc.country and loc.country.strip():
            shoot_codes.add(countries.resolve_or_keep(loc.country).upper())

    nat_codes = set()
    for nat in (project.director_nationalities or []) + (project.producer_nationalities or []):
        if nat and nat.strip():
            nat_codes.add(countries.resolve_or_keep(nat).upper())
    for cc in project.production_company_countries or []:
        if cc and cc.strip():
            nat_codes.add(countries.resolve_or_keep(cc).upper())
    if getattr(project, 'production_company_country', None):
        nat_codes.add(countries.resolve_or_keep(project.production_company_country).upper())

    known_codes = shoot_codes | nat_codes

    for cc in country_codes:
        if cc not in known_codes:
            changes += 2  # adding a new country is a big change
        elif cc not in shoot_codes:
            changes += 1  # nationality connection but no shoot yet

    return changes


def _build_scenario(
    project: ProjectInput,
    country_codes: list[str],
    by_country: dict[str, list[Incentive]],
    db: Session,
    doc_by_incentive: dict[int, list[DocumentAnnotation]] | None = None,
    doc_by_treaty: dict[int, list[DocumentAnnotation]] | None = None,
) -> Scenario | None:
    """Build a scenario from a list of country codes. Returns None only if zero incentives exist in DB for these countries."""
    # Pre-sort countries to determine "majority" vs "minority"
    # Logic:
    # 1. If project has shoot locations, the one with highest shoot % is majority.
    # 2. If no shoot locations (or tied), the one with highest incentive benefit is majority.
    country_stats = []
    for cc in country_codes:
        eligible, _, pct, _ = _evaluate_country(project, cc, by_country, doc_by_incentive)
        shoot_pct = _percent_in_country(project, cc)
        # Sort key: (shoot_pct, total_incentive_pct, num_incentives)
        score = (shoot_pct, pct, len(eligible))
        country_stats.append((cc, score))

    # Sort by score descending
    sorted_codes = [cc for cc, _ in sorted(country_stats, key=lambda x: x[1], reverse=True)]

    partners: list[CoproductionPartner] = []
    all_requirements: list[Requirement] = []
    treaty_basis: list[TreatyInfo] = []
    total_pct = 0.0
    seen_treaties: set[int] = set()

    all_near_misses: list[NearMiss] = []

    for i, cc in enumerate(sorted_codes):
        eligible, reqs, pct, near_misses = _evaluate_country(project, cc, by_country, doc_by_incentive)
        all_near_misses.extend(near_misses)
        shoot_pct = _percent_in_country(project, cc)

        role = "majority" if i == 0 else "minority"

        partner_treaties: list[TreatyInfo] = []
        for other_cc in country_codes:
            if other_cc == cc:
                continue
            for treaty in _get_treaties_for_pair(db, cc, other_cc):
                if treaty.id not in seen_treaties:
                    seen_treaties.add(treaty.id)
                    info = _treaty_to_info(treaty, doc_by_treaty)
                    partner_treaties.append(info)
                    treaty_basis.append(info)

        partners.append(CoproductionPartner(
            country_code=cc,
            country_name=countries.display_name(cc),
            role=role,
            estimated_share_percent=round(shoot_pct, 1) if shoot_pct else None,
            eligible_incentives=eligible,
            applicable_treaties=partner_treaties,
        ))
        total_pct += pct
        all_requirements.extend(reqs)

    # Check there's at least some incentive data for these countries
    total_incentives = sum(len(p.eligible_incentives) for p in partners)
    if total_incentives == 0:
        # Check if the countries even have data — if not, skip entirely
        has_any_data = any(cc.upper() in by_country for cc in country_codes)
        if not has_any_data:
            print(f"    Total incentives: 0. has_any_data for {country_codes}: False")
            return None

    # Deduplicate requirements
    seen_descs: set[str] = set()
    unique_reqs: list[Requirement] = []
    for r in all_requirements:
        if r.description not in seen_descs:
            seen_descs.add(r.description)
            unique_reqs.append(r)

    amount = (project.budget * total_pct / 100) if project.budget else 0
    currency = project.budget_currency or "EUR"

    suggestions = _build_suggestions(project, country_codes, by_country, db, currency)
    rationale = _build_rationale(partners, treaty_basis, total_pct, currency, amount)

    # Sort near-misses by potential benefit (highest first), limit to top 5
    all_near_misses.sort(key=lambda nm: -(nm.potential_benefit_amount or 0))
    top_near_misses = all_near_misses[:5]

    return Scenario(
        partners=partners,
        estimated_total_financing_percent=round(total_pct, 1),
        estimated_total_financing_amount=round(amount, 0),
        financing_currency=currency,
        requirements=unique_reqs,
        suggestions=suggestions,
        near_misses=top_near_misses,
        rationale=rationale,
        treaty_basis=treaty_basis,
    )


def _build_rationale(
    partners: list[CoproductionPartner],
    treaties: list[TreatyInfo],
    total_pct: float,
    currency: str,
    amount: float,
) -> str:
    """Generate a human-readable explanation of why this scenario works."""
    parts = []

    country_names = [p.country_name for p in partners]
    if len(country_names) == 1:
        parts.append(f"Single-country production in {country_names[0]}.")
    else:
        parts.append(f"Coproduction between {', '.join(country_names[:-1])} and {country_names[-1]}.")

    if treaties:
        treaty_names = [t.treaty_name for t in treaties]
        parts.append(f"Treaty basis: {'; '.join(treaty_names)}.")

    incentive_count = sum(len(p.eligible_incentives) for p in partners)
    if incentive_count > 0 and total_pct > 0:
        parts.append(f"{incentive_count} eligible incentive(s) identified, estimated at {total_pct}% of budget ({currency} {amount:,.0f}).")
    elif incentive_count > 0:
        parts.append(f"{incentive_count} incentive(s) identified; benefit depends on spend allocation and eligibility conditions being met.")
    else:
        parts.append("No incentives currently match, but treaty framework enables coproduction structure. See requirements for what's needed to qualify.")

    return " ".join(parts)


def _build_suggestions(
    project: ProjectInput,
    current_codes: list[str],
    by_country: dict[str, list[Incentive]],
    db: Session,
    currency: str,
) -> list[Suggestion]:
    """Suggest ways to unlock more funding."""
    suggestions: list[Suggestion] = []

    # Suggest increasing shoot in countries where min_shoot_percent isn't met
    for cc in current_codes:
        shoot_pct = _percent_in_country(project, cc)
        for inc in by_country.get(cc.upper(), []):
            if inc.min_shoot_percent and shoot_pct < inc.min_shoot_percent and inc.rebate_percent:
                # Estimate what benefit would be if threshold were met
                total_shoot = sum(loc.percent for loc in project.shoot_locations) or 100.0
                target_spend = project.budget * project.shooting_spend_fraction * (inc.min_shoot_percent / total_shoot)
                est_benefit = target_spend * (inc.rebate_percent / 100.0)
                inc_currency = inc.max_cap_currency or "EUR"
                if inc.max_cap_amount and est_benefit > inc.max_cap_amount:
                    est_benefit = inc.max_cap_amount
                source = None
                if inc.source_url:
                    source = SourceReference(url=inc.source_url, description=inc.source_description or inc.name)
                suggestions.append(Suggestion(
                    suggestion_type="increase_shoot",
                    country=countries.display_name(cc),
                    description=(
                        f"Increase shoot in {countries.display_name(cc)} from {shoot_pct:.0f}% to "
                        f"{inc.min_shoot_percent}% to qualify for {inc.name} ({inc.rebate_percent}%)."
                    ),
                    potential_benefit=f"~{inc_currency} {est_benefit:,.0f} ({inc.rebate_percent}% on qualifying spend)",
                    estimated_amount=round(est_benefit, 0),
                    estimated_currency=inc_currency,
                    effort_level="low" if (inc.min_shoot_percent - shoot_pct) <= 10 else "medium",
                    source=source,
                ))
                break

    # Suggest treaty partners not currently in the scenario
    partner_suggestions: list[Suggestion] = []
    seen_partner_codes: set[str] = set()
    for cc in current_codes:
        treaty_partners = _get_all_treaty_partners(db, cc)
        for partner_code in treaty_partners:
            if partner_code in current_codes or partner_code in seen_partner_codes:
                continue
            seen_partner_codes.add(partner_code)
            if project.open_to_copro_countries:
                open_codes = [countries.resolve_or_keep(c).upper() for c in project.open_to_copro_countries]
                if partner_code not in open_codes:
                    continue
            incs = by_country.get(partner_code, [])
            if not incs:
                continue
            best = max((i for i in incs if i.rebate_percent), key=lambda i: i.rebate_percent or 0, default=None)
            if best and best.rebate_percent:
                partner_name = countries.display_name(partner_code)
                treaties = _get_treaties_for_pair(db, cc, partner_code)
                treaty_note = ""
                if treaties:
                    treaty_note = f" ({treaties[0].name})"
                # Estimate benefit: assume 20% of shooting budget as qualifying spend in partner country
                assumed_spend_fraction = 0.20
                est_spend = project.budget * project.shooting_spend_fraction * assumed_spend_fraction
                # If min qualifying spend exceeds what we'd realistically spend, skip
                if best.min_qualifying_spend and est_spend < best.min_qualifying_spend:
                    if best.min_qualifying_spend > project.budget * 0.5:
                        continue  # unrealistic — min spend is more than half the budget
                    est_spend = best.min_qualifying_spend
                est_benefit = est_spend * (best.rebate_percent / 100.0)
                partner_currency = best.max_cap_currency or "EUR"
                if best.max_cap_amount and est_benefit > best.max_cap_amount:
                    est_benefit = best.max_cap_amount
                partner_suggestions.append(Suggestion(
                    suggestion_type="add_copro",
                    country=partner_name,
                    description=f"Add {partner_name} as coproduction partner{treaty_note} to access {best.name}.",
                    potential_benefit=f"~{partner_currency} {est_benefit:,.0f} ({best.rebate_percent}% on qualifying {partner_name} spend)",
                    estimated_amount=round(est_benefit, 0),
                    estimated_currency=partner_currency,
                    effort_level="high",
                    source=SourceReference(url=best.source_url, description=best.source_description or best.name) if best.source_url else None,
                ))

    # Sort partner suggestions by estimated benefit descending
    partner_suggestions.sort(key=lambda s: -(s.estimated_amount or 0))
    suggestions.extend(partner_suggestions)

    return suggestions[:5]


def generate_scenarios(project: ProjectInput, db: Session) -> list[Scenario]:
    """Generate and rank financing scenarios.

    Strategy: cast a wide net of country combinations, build scenarios for each,
    then rank by (financing_amount DESC, changes_needed ASC). Always returns results.
    """
    by_country = _get_incentives_by_country(db)
    doc_by_incentive, doc_by_treaty = _build_doc_lookup(db)
    shoot_sorted = _shoot_countries_sorted(project)
    scenarios: list[Scenario] = []
    seen_combos: set[tuple[str, ...]] = set()

    def _try_scenario(codes: list[str]) -> None:
        # Filter out empty/invalid codes
        codes = [c.upper() for c in codes if c and c.strip()]
        if not codes:
            return
        key = tuple(sorted(codes))
        if key in seen_combos:
            return
        seen_combos.add(key)
        # print(f"Trying scenario for codes: {codes}")
        s = _build_scenario(project, codes, by_country, db, doc_by_incentive, doc_by_treaty)
        if s:
            # print(f"  Success: {s.estimated_total_financing_percent}%")
            scenarios.append(s)
        else:
            print(f"  Failed to build scenario for {codes}")

    shoot_codes = [c for c, _ in shoot_sorted]

    # --- Phase 1: Scenarios close to current setup ---

    # All shoot countries together
    if shoot_codes:
        _try_scenario(shoot_codes[:4])

    # Each shoot country as primary + others
    for code, _ in shoot_sorted:
        others = [c for c in shoot_codes if c != code][:3]
        _try_scenario([code] + others)

    # Director/producer nationality countries + shoot countries
    for nat_list in [project.director_nationalities, project.producer_nationalities]:
        for nat in (nat_list or []):
            if not nat or not nat.strip():
                continue
            code = countries.resolve_or_keep(nat).upper()
            if code not in shoot_codes:
                _try_scenario([code] + shoot_codes[:3])

    # Production company countries
    for cc in project.production_company_countries or []:
        if cc and cc.strip():
            code = countries.resolve_or_keep(cc).upper()
            if code not in shoot_codes:
                _try_scenario([code] + shoot_codes[:3])
    if getattr(project, 'production_company_country', None):
        code = countries.resolve_or_keep(project.production_company_country).upper()
        if code not in shoot_codes:
            _try_scenario([code] + shoot_codes[:3])

    # Treaty partners of shoot countries
    for shoot_code, _ in shoot_sorted[:3]:
        treaty_partners = _get_all_treaty_partners(db, shoot_code)
        for partner_code in treaty_partners:
            if partner_code not in shoot_codes:
                _try_scenario(shoot_codes[:3] + [partner_code])

    # User-specified copro countries
    for country in project.open_to_copro_countries or []:
        code = countries.resolve_or_keep(country).upper()
        if code not in shoot_codes:
            _try_scenario([code] + shoot_codes[:3])

    # --- Phase 2: Broader exploration (countries the user hasn't mentioned) ---

    # All countries with incentive data — try each one paired with user's shoot countries
    all_incentive_countries = sorted(by_country.keys())
    for cc in all_incentive_countries:
        if cc in shoot_codes:
            continue
        # Solo country
        _try_scenario([cc])
        # Country + user's shoot countries
        if shoot_codes:
            _try_scenario(shoot_codes[:2] + [cc])

    # Nationality-based solo scenarios (if user hasn't specified shoot locations)
    if not shoot_codes:
        all_nat_lists = [project.director_nationalities, project.producer_nationalities,
                         project.production_company_countries]
        for nat_list in all_nat_lists:
            for nat in (nat_list or []):
                if not nat or not nat.strip():
                    continue
                code = countries.resolve_or_keep(nat).upper()
                _try_scenario([code])
                # Also try this country with its top treaty partners
                for partner in _get_all_treaty_partners(db, code)[:5]:
                    _try_scenario([code, partner])

    # --- Phase 3: If we still have nothing, generate single-country fallbacks ---
    if not scenarios:
        # Try every country with incentive data as a standalone option
        for cc in all_incentive_countries:
            _try_scenario([cc])

    # --- Rank: best financing first, fewest changes as tiebreaker ---
    def _score(s: Scenario) -> tuple[float, int]:
        changes = _count_changes_needed(project, [p.country_code for p in s.partners], by_country)
        # Primary: higher financing is better (negate for sort)
        # Secondary: fewer changes is better
        return (-s.estimated_total_financing_percent, changes)

    scenarios.sort(key=_score)
    return scenarios[:15]
