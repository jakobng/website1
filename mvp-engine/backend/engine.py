from typing import List, Tuple
from models import Incentive, Treaty
from schemas import ProjectInput, Scenario, IncentiveSchema

class CoproEngine:
    def __init__(self, incentives: List[Incentive], treaties: List[Treaty]):
        self.incentives = incentives
        self.treaties = treaties

    def evaluate_eligibility(self, project: ProjectInput, incentive: Incentive) -> Tuple[bool, List[str], float, float]:
        """Returns (is_eligible, requirements, gross_yield, net_yield)"""
        requirements = []
        is_eligible = True
        
        # 1. IP/Rights Logic
        if project.global_svod_secured and incentive.requires_territory_rights:
            return False, ["Disqualified: Global SVOD deal conflicts with territory rights requirement."], 0, 0
        
        # 2. Spend/Threshold Logic
        # Find spend in the incentive's country
        local_spend_percent = 0.0
        for loc in project.shoot_locations:
            if loc.country.lower() == incentive.country.lower():
                local_spend_percent = loc.percent
                break
        
        if local_spend_percent < incentive.min_local_spend_percent:
            is_eligible = False
            requirements.append(f"Insufficient local spend: {local_spend_percent}% (Min: {incentive.min_local_spend_percent}%)")
        
        # 3. Calculate Yields
        local_spend_amount = (local_spend_percent / 100.0) * project.total_budget
        gross_yield = local_spend_amount * (incentive.gross_rebate_percent / 100.0)
        
        # Apply max cap if present
        if incentive.max_cap and gross_yield > incentive.max_cap:
            gross_yield = incentive.max_cap
            
        net_yield = gross_yield * incentive.net_yield_multiplier
        
        if is_eligible:
            requirements.append(f"Must hire local coproducer to unlock {incentive.name}")
            
        return is_eligible, requirements, gross_yield, net_yield

    def generate_scenarios(self, project: ProjectInput) -> List[Scenario]:
        scenarios = []
        
        # Simple strategy: Try each country in shoot_locations as a lead country
        countries = [loc.country for loc in project.shoot_locations]
        
        for lead_country in countries:
            eligible_incentives = []
            all_requirements = []
            total_gross = 0.0
            total_net = 0.0
            state_aid_total_gross = 0.0
            partner_countries = [c for c in countries if c != lead_country]
            
            # Check all involved countries for incentives
            for country in countries:
                country_incentives = [i for i in self.incentives if i.country.lower() == country.lower()]
                for inc in country_incentives:
                    eligible, reqs, gross, net = self.evaluate_eligibility(project, inc)
                    if eligible:
                        eligible_incentives.append(IncentiveSchema.from_orm(inc))
                        all_requirements.extend(reqs)
                        total_gross += gross
                        total_net += net
                        if inc.state_aid_eligible:
                            state_aid_total_gross += gross

            # 4. State Aid Stacking Cap (50% of total budget)
            stacking_limit = project.total_budget * 0.5
            if state_aid_total_gross > stacking_limit:
                reduction_ratio = stacking_limit / state_aid_total_gross
                all_requirements.append(f"State aid cap reached (50%). Reducing {state_aid_total_gross:,.2f} to {stacking_limit:,.2f}")
                
                # Adjust total gross and net (simplified: proportional reduction of state aid part)
                # First remove the state aid part from totals
                non_state_aid_gross = total_gross - state_aid_total_gross
                # We need a way to track net reduction too. For simplicity, we reduce total_net by same ratio on the state aid portion.
                # This is an approximation for the MVP.
                
                # Recalculate net reduction
                state_aid_net = sum(
                    (inc.gross_rebate_percent/100 * (next(loc.percent for loc in project.shoot_locations if loc.country == inc.country)/100) * project.total_budget) * inc.net_yield_multiplier
                    for inc in eligible_incentives if inc.state_aid_eligible
                )
                # Apply reduction to totals
                total_gross = non_state_aid_gross + stacking_limit
                total_net = (total_net - state_aid_net) + (state_aid_net * reduction_ratio)

            # Treaty Logic: Check if lead and partners have treaties
            for partner in partner_countries:
                treaty = self.find_treaty(lead_country, partner)
                if treaty:
                    all_requirements.append(f"Treaty found: {lead_country}-{partner}. Min financial share for {partner}: {treaty.min_financial_share_b}%")
                else:
                    all_requirements.append(f"No bilateral treaty found between {lead_country} and {partner}. May require non-official copro.")

            scenarios.append(Scenario(
                lead_country=lead_country,
                partner_countries=partner_countries,
                eligible_incentives=eligible_incentives,
                total_gross_financing=total_gross,
                total_net_financing=total_net,
                actionable_requirements=list(set(all_requirements)),
                gap_percentage=(total_net / project.total_budget) * 100 if project.total_budget > 0 else 0
            ))

        # Rank by total_net_financing descending
        scenarios.sort(key=lambda x: x.total_net_financing, reverse=True)
        return scenarios[:3]

    def find_treaty(self, country_a: str, country_b: str) -> Treaty:
        for t in self.treaties:
            if (t.country_a.lower() == country_a.lower() and t.country_b.lower() == country_b.lower()) or \
               (t.country_a.lower() == country_b.lower() and t.country_b.lower() == country_a.lower()):
                return t
        return None
