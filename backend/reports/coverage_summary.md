# Coverage Gap Summary

This report is generated from `backend/seed_data.py` and `backend/app/countries.py`.

## Snapshot

- Supported countries in catalog: **196**
- Countries with incentives: **143** (73.0%)
- Treaty-only countries (no incentive data yet): **0** (0.0%)
- No coverage (no incentives or treaties): **53** (27.0%)

## Regional Coverage (Incentive or Treaty)

- Africa: **31/54** (57.4%)
- Americas: **31/35** (88.6%)
- Asia: **31/41** (75.6%)
- Europe: **42/49** (85.7%)
- Oceania: **5/14** (35.7%)
- Other: **3/3** (100.0%)

## Highest-Priority Missing Additions

| Code | Country | Region | Status | Priority | Reason |
|---|---|---|---|---:|---|
| YE | Yemen | Asia | no_coverage | 2 | undercovered_region |
| TM | Turkmenistan | Asia | no_coverage | 2 | undercovered_region |
| TL | Timor-Leste | Asia | no_coverage | 2 | undercovered_region |
| TJ | Tajikistan | Asia | no_coverage | 2 | undercovered_region |
| SY | Syria | Asia | no_coverage | 2 | undercovered_region |
| PS | Palestine | Asia | no_coverage | 2 | undercovered_region |
| KP | North Korea | Asia | no_coverage | 2 | undercovered_region |
| KG | Kyrgyzstan | Asia | no_coverage | 2 | undercovered_region |
| IR | Iran | Asia | no_coverage | 2 | undercovered_region |
| AF | Afghanistan | Asia | no_coverage | 2 | undercovered_region |
| SR | Suriname | Americas | no_coverage | 2 | undercovered_region |
| NI | Nicaragua | Americas | no_coverage | 2 | undercovered_region |
| HT | Haiti | Americas | no_coverage | 2 | undercovered_region |
| HN | Honduras | Americas | no_coverage | 2 | undercovered_region |
| WS | Samoa | Oceania | no_coverage | 1 | region_gap |
| TV | Tuvalu | Oceania | no_coverage | 1 | region_gap |
| TO | Tonga | Oceania | no_coverage | 1 | region_gap |
| SB | Solomon Islands | Oceania | no_coverage | 1 | region_gap |
| PW | Palau | Oceania | no_coverage | 1 | region_gap |
| NR | Nauru | Oceania | no_coverage | 1 | region_gap |
| MH | Marshall Islands | Oceania | no_coverage | 1 | region_gap |
| KI | Kiribati | Oceania | no_coverage | 1 | region_gap |
| FM | Micronesia | Oceania | no_coverage | 1 | region_gap |
| SO | Somalia | Africa | no_coverage | 1 | region_gap |
| ML | Mali | Africa | no_coverage | 1 | region_gap |
| MG | Madagascar | Africa | no_coverage | 1 | region_gap |
| KM | Comoros | Africa | no_coverage | 1 | region_gap |
| GQ | Equatorial Guinea | Africa | no_coverage | 1 | region_gap |
| GN | Guinea | Africa | no_coverage | 1 | region_gap |
| GM | Gambia | Africa | no_coverage | 1 | region_gap |

## Treaty-Only Countries (Good Next Incentive Targets)

| Code | Country | Bilateral Treaties | Multilateral Member |
|---|---|---:|---|

## Files

- Matrix CSV: `C:/Users/User/Documents/WORK/EXPERIMENTS/CoPro_Calculator/backend/reports/coverage_matrix.csv`
- Summary report: `C:/Users/User/Documents/WORK/EXPERIMENTS/CoPro_Calculator/backend/reports/coverage_summary.md`

## Notes

- `coverage_status` uses incentive data first, then treaty-only.
- `priority_score` is a pragmatic heuristic for sequencing work, not a legal ranking.
- Freshness is based on `last_verified` values embedded in seed data.
