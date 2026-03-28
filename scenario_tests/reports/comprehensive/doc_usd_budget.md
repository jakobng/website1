# SCENARIO: doc_usd_budget
Category: **F** | Generated: 2026-03-26 21:28

## ANOMALIES
- **[WARN]** Slow scenario generation: 638632ms

## PROJECT INPUT
```json
{
  "title": "Doc USD Budget FR-CA",
  "format": "documentary",
  "stage": "production",
  "budget": 400000.0,
  "budget_currency": "USD",
  "budget_min": null,
  "budget_max": null,
  "shoot_locations_flexible": false,
  "open_to_copro_countries": [],
  "director_nationalities": [
    "France"
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
      "country": "France",
      "percent": 60.0
    },
    {
      "country": "Canada",
      "percent": 40.0
    }
  ],
  "spend_allocations": [],
  "post_flexible": false,
  "vfx_flexible": false,
  "editor_nationality": null,
  "local_crew_percent": null,
  "has_coproducer": [
    "Canada"
  ],
  "willing_add_coproducer": true,
  "broadcaster_attached": null,
  "streamer_attached": false,
  "cultural_test_passed": [],
  "cultural_test_failed": []
}
```

## RESULT SUMMARY
- **Scenarios found:** 15
- **Top financing:** 14.2% (USD 56,800)
- **Partners:** Canada, France
- **Rationale:** Coproduction between Canada and France. Treaty basis: France–Canada Coproduction Treaty. 5 eligible incentive(s) identified, estimated at 14.2% of budget (USD 56,800).

## PARTNERS & INCENTIVES
### Canada (CA) — majority
Est. share: 40.0%

#### Manitoba Film and Video Production Tax Credit
- Type: tax_credit | Rate: 45.0% | Contribution: 4.3%
- Benefit: USD 17,280
- Explanation: Meet Canada programme requirements. Rebate applies to qualified labour only. Estimated local spend: USD 64,000 (estimated from budget breakdown (shooting 40% × 40%)). Labour estimated at 60% of local spend = USD 38,400. Credit: 45.0% of USD 38,400 = USD 17,280. This is an estimate, not a binding figure.
- Calculation:
  - Qualifying spend (estimated): `budget × 40% shooting × 40% country share` = 64,000 USD
  - Qualified labour (estimated): `qualifying spend × 60% (standard labour cap)` = 38,400 USD
  - Tax Credit (45.0%): `qualified labour × 45.0%` = 17,280 USD

#### Canada CPTC (Canadian Film or Video Production Tax Credit)
- Type: tax_credit | Rate: 25.0% | Contribution: 2.4%
- Benefit: USD 9,600
- Explanation: You need: at least 50.0% local crew. Rebate applies to qualified labour only. Estimated local spend: USD 64,000 (estimated from budget breakdown (shooting 40% × 40%)). Labour estimated at 60% of local spend = USD 38,400. Credit: 25.0% of USD 38,400 = USD 9,600. This is an estimate, not a binding figure.
- Calculation:
  - Qualifying spend (estimated): `budget × 40% shooting × 40% country share` = 64,000 USD
  - Qualified labour (estimated): `qualifying spend × 60% (standard labour cap)` = 38,400 USD
  - Tax Credit (25.0%): `qualified labour × 25.0%` = 9,600 USD
- Requirements:
  - [crew] At least 50.0% local crew in Canada

#### Canada FISTC (Film or Video Production Services Tax Credit)
- Type: tax_credit | Rate: 16.0% | Contribution: 1.5%
- Benefit: USD 6,144
- Explanation: Meet Canada programme requirements. Rebate applies to qualified labour only. Estimated local spend: USD 64,000 (estimated from budget breakdown (shooting 40% × 40%)). Labour estimated at 60% of local spend = USD 38,400. Credit: 16.0% of USD 38,400 = USD 6,144. This is an estimate, not a binding figure.
- Calculation:
  - Qualifying spend (estimated): `budget × 40% shooting × 40% country share` = 64,000 USD
  - Qualified labour (estimated): `qualifying spend × 60% (standard labour cap)` = 38,400 USD
  - Tax Credit (16.0%): `qualified labour × 16.0%` = 6,144 USD

**Treaties:**
- France–Canada Coproduction Treaty

### France (FR) — minority
Est. share: 60.0%

#### France Crédit d'impôt Cinéma (domestic)
- Type: tax_credit | Rate: 25.0% | Contribution: 6.0%
- Benefit: USD 24,000
- Explanation: Meet France programme requirements. Estimated qualifying spend: USD 96,000 (estimated from budget breakdown (shooting 40% × 60%)). Rebate: 25.0% of USD 96,000 = USD 24,000. This is an estimate, not a binding figure.
- Calculation:
  - Qualifying spend (estimated): `budget × 40% shooting × 60% country share` = 96,000 USD
  - Tax Credit (25.0%): `qualifying spend × 25.0%` = 24,000 USD

#### Île-de-France Film Commission Fund
- Type: grant | Rate: N/A% | Contribution: 0.0%
- Benefit: USD 0
- Explanation: Meet France programme requirements. This is a grant/fund programme; awards are competitive and case-specific.

## SUGGESTIONS
- [high] Add Italy as coproduction partner (France–Italy Coproduction Treaty) to access Italy Tax Credit for Foreign Productions. (~EUR 80,000)
- [high] Add Cyprus as coproduction partner (European Convention on Cinematographic Co-Production (Revised, 2017)) to access Cyprus Cash Rebate Scheme for Film and TV. (~EUR 70,000)
- [high] Add Estonia as coproduction partner (European Convention on Cinematographic Co-Production (Revised, 2017)) to access Estonia Cash Rebate for Film Production. (~EUR 60,000)
- [high] Add Netherlands as coproduction partner (European Convention on Cinematographic Co-Production (Revised, 2017)) to access Netherlands Film Production Incentive. (~EUR 52,500)
- [high] Add Austria as coproduction partner (European Convention on Cinematographic Co-Production (Revised, 2017)) to access Austria FISA+ (Film Location Austria Incentive). (~EUR 52,500)

## OUTSTANDING REQUIREMENTS
- [crew] At least 50.0% local crew in Canada
