# SCENARIO: feature_cad_budget
Category: **F** | Generated: 2026-03-26 21:26

## ANOMALIES
- **[WARN]** Slow scenario generation: 343035ms

## PROJECT INPUT
```json
{
  "title": "Feature CAD Budget Canada",
  "format": "feature_fiction",
  "stage": "production",
  "budget": 5000000.0,
  "budget_currency": "CAD",
  "budget_min": null,
  "budget_max": null,
  "shoot_locations_flexible": false,
  "open_to_copro_countries": [],
  "director_nationalities": [
    "Canada"
  ],
  "producer_nationalities": [],
  "production_company_country": null,
  "production_company_countries": [],
  "languages": [],
  "subject_country": null,
  "story_setting_country": null,
  "stages": [],
  "shooting_spend_fraction": 0.4,
  "post_production_spend_fraction": 0.35,
  "post_production_country": null,
  "shoot_locations": [
    {
      "country": "Canada",
      "percent": 100.0
    }
  ],
  "spend_allocations": [],
  "post_flexible": false,
  "vfx_flexible": false,
  "editor_nationality": null,
  "local_crew_percent": null,
  "has_coproducer": [],
  "willing_add_coproducer": true,
  "broadcaster_attached": null,
  "streamer_attached": false,
  "cultural_test_passed": [],
  "cultural_test_failed": []
}
```

## RESULT SUMMARY
- **Scenarios found:** 15
- **Top financing:** 20.6% (CAD 1,030,000)
- **Partners:** Canada
- **Rationale:** Single-country production in Canada. 3 eligible incentive(s) identified, estimated at 20.6% of budget (CAD 1,030,000).

## PARTNERS & INCENTIVES
### Canada (CA) — majority
Est. share: 100.0%

#### Manitoba Film and Video Production Tax Credit
- Type: tax_credit | Rate: 45.0% | Contribution: 10.8%
- Benefit: CAD 540,000
- Explanation: Meet Canada programme requirements. Rebate applies to qualified labour only. Estimated local spend: CAD 2,000,000 (estimated from budget breakdown (shooting 40% × 100%)). Labour estimated at 60% of local spend = CAD 1,200,000. Credit: 45.0% of CAD 1,200,000 = CAD 540,000. This is an estimate, not a binding figure.
- Calculation:
  - Qualifying spend (estimated): `budget × 40% shooting × 100% country share` = 2,000,000 CAD
  - Qualified labour (estimated): `qualifying spend × 60% (standard labour cap)` = 1,200,000 CAD
  - Tax Credit (45.0%): `qualified labour × 45.0%` = 540,000 CAD

#### Canada CPTC (Canadian Film or Video Production Tax Credit)
- Type: tax_credit | Rate: 25.0% | Contribution: 6.0%
- Benefit: CAD 300,000
- Explanation: You need: at least 50.0% local crew. Rebate applies to qualified labour only. Estimated local spend: CAD 2,000,000 (estimated from budget breakdown (shooting 40% × 100%)). Labour estimated at 60% of local spend = CAD 1,200,000. Credit: 25.0% of CAD 1,200,000 = CAD 300,000. This is an estimate, not a binding figure.
- Calculation:
  - Qualifying spend (estimated): `budget × 40% shooting × 100% country share` = 2,000,000 CAD
  - Qualified labour (estimated): `qualifying spend × 60% (standard labour cap)` = 1,200,000 CAD
  - Tax Credit (25.0%): `qualified labour × 25.0%` = 300,000 CAD
- Requirements:
  - [crew] At least 50.0% local crew in Canada

#### Canada FISTC (Film or Video Production Services Tax Credit)
- Type: tax_credit | Rate: 16.0% | Contribution: 3.8%
- Benefit: CAD 192,000
- Explanation: Meet Canada programme requirements. Rebate applies to qualified labour only. Estimated local spend: CAD 2,000,000 (estimated from budget breakdown (shooting 40% × 100%)). Labour estimated at 60% of local spend = CAD 1,200,000. Credit: 16.0% of CAD 1,200,000 = CAD 192,000. This is an estimate, not a binding figure.
- Calculation:
  - Qualifying spend (estimated): `budget × 40% shooting × 100% country share` = 2,000,000 CAD
  - Qualified labour (estimated): `qualifying spend × 60% (standard labour cap)` = 1,200,000 CAD
  - Tax Credit (16.0%): `qualified labour × 16.0%` = 192,000 CAD

## SUGGESTIONS
- [high] Add Norway as coproduction partner (Canada–Norway Film and Video Co-production Agreement) to access Norway Incentive Scheme for International Film and TV. (~NOK 500,000)
- [high] Add Belgium as coproduction partner (Belgium–Canada Coproduction Treaty) to access Belgium Tax Shelter. (~EUR 168,000)
- [high] Add Colombia as coproduction partner (Canada–Colombia Coproduction Treaty) to access Colombia Film Incentive. (~EUR 160,000)
- [high] Add Italy as coproduction partner (Canada–Italy Coproduction Treaty) to access Italy Tax Credit for Foreign Productions. (~EUR 160,000)
- [high] Add Australia as coproduction partner (Canada–Australia Coproduction Treaty) to access Australia Producer Offset. (~AUD 160,000)

## OUTSTANDING REQUIREMENTS
- [crew] At least 50.0% local crew in Canada
