# Global Expansion Backlog (Phased)

This backlog is derived from [coverage_summary.md](/C:/Users/User/Documents/WORK/EXPERIMENTS/CoPro_Calculator/backend/reports/coverage_summary.md) and [coverage_matrix.csv](/C:/Users/User/Documents/WORK/EXPERIMENTS/CoPro_Calculator/backend/reports/coverage_matrix.csv).

## Guardrails (Do Not Break Existing Behavior)

1. Additive only: new records/modules first, no rule-engine rewrites unless required by failing tests.
2. Every new numeric rule needs `source_url`, `source_description`, `notes`, `last_verified`.
3. Every new country needs at least one deterministic scenario test fixture.
4. Keep explainability contract intact: requirements, math steps, and sources must remain inspectable.

## Country Packet Definition (Exact Records Per Country)

For each country `CC`, complete these records:

1. `INC-CC-01`: first national incentive record in `incentives`.
2. `DOC-INC-CC-01`: primary official guideline/legal source in `documents`.
3. `ANN-INC-CC-01..N`: clause annotations for rate, caps, thresholds, and eligibility.
4. `TRY-CC-VERIFY-*`: verify all existing treaty rows for that country (dates, authorities, active status).
5. `CT-CC-01` (if applicable): cultural-test scoring metadata (min/total points and requirements).
6. `SCN-CC-BASE`: baseline scenario fixture in `scenario_tests`.
7. `SCN-CC-EDGE`: one near-miss or threshold edge fixture.

## Phase 1: Treaty-Only -> Incentive-Covered (Highest ROI)

Objective: convert high-value treaty-only countries into incentive-covered countries.

| Priority | Country | Current State | Exact First Records |
|---|---|---|---|
| P1 | JP (Japan) | treaty_only (2 bilateral) | `INC-JP-01`, `DOC-INC-JP-01`, `ANN-INC-JP-*`, `TRY-JP-VERIFY-*`, `SCN-JP-BASE`, `SCN-JP-EDGE` |
| P1 | IN (India) | treaty_only (11 bilateral) | `INC-IN-01`, `DOC-INC-IN-01`, `ANN-INC-IN-*`, `TRY-IN-VERIFY-*`, `SCN-IN-BASE`, `SCN-IN-EDGE` |
| P1 | CN (China) | treaty_only (5 bilateral) | `INC-CN-01`, `DOC-INC-CN-01`, `ANN-INC-CN-*`, `TRY-CN-VERIFY-*`, `SCN-CN-BASE`, `SCN-CN-EDGE` |
| P1 | MX (Mexico) | treaty_only (3 bilateral) | `INC-MX-01`, `DOC-INC-MX-01`, `ANN-INC-MX-*`, `TRY-MX-VERIFY-*`, `SCN-MX-BASE`, `SCN-MX-EDGE` |
| P1 | BR (Brazil) | treaty_only (8 bilateral) | `INC-BR-01`, `DOC-INC-BR-01`, `ANN-INC-BR-*`, `TRY-BR-VERIFY-*`, `SCN-BR-BASE`, `SCN-BR-EDGE` |
| P1 | SG (Singapore) | treaty_only (2 bilateral) | `INC-SG-01`, `DOC-INC-SG-01`, `ANN-INC-SG-*`, `TRY-SG-VERIFY-*`, `SCN-SG-BASE`, `SCN-SG-EDGE` |
| P1 | IL (Israel) | treaty_only (6 bilateral) | `INC-IL-01`, `DOC-INC-IL-01`, `ANN-INC-IL-*`, `TRY-IL-VERIFY-*`, `SCN-IL-BASE`, `SCN-IL-EDGE` |
| P1 | AR (Argentina) | treaty_only (4 bilateral) | `INC-AR-01`, `DOC-INC-AR-01`, `ANN-INC-AR-*`, `TRY-AR-VERIFY-*`, `SCN-AR-BASE`, `SCN-AR-EDGE` |
| P1 | CL (Chile) | treaty_only (3 bilateral) | `INC-CL-01`, `DOC-INC-CL-01`, `ANN-INC-CL-*`, `TRY-CL-VERIFY-*`, `SCN-CL-BASE`, `SCN-CL-EDGE` |
| P1 | UY (Uruguay) | treaty_only (1 bilateral) | `INC-UY-01`, `DOC-INC-UY-01`, `ANN-INC-UY-*`, `TRY-UY-VERIFY-*`, `SCN-UY-BASE`, `SCN-UY-EDGE` |

Phase 1 exit criteria:

1. At least 8/10 countries above become `incentive_covered`.
2. Treaty rows for those countries pass a manual verification pass.
3. 20 new scenario fixtures added (`BASE` + `EDGE` per country).

## Phase 2: Add Major No-Coverage Markets

Objective: cover countries with high production relevance and no current incentive/treaty coverage.

| Priority | Country | Current State | Exact First Records |
|---|---|---|---|
| P2 | US (United States) | no_coverage | `INC-US-01..05` (federal/state model), `DOC-INC-US-*`, `ANN-INC-US-*`, `SCN-US-BASE`, `SCN-US-EDGE` |
| P2 | TH (Thailand) | no_coverage | `INC-TH-01`, `DOC-INC-TH-01`, `ANN-INC-TH-*`, `SCN-TH-BASE`, `SCN-TH-EDGE` |
| P2 | PH (Philippines) | no_coverage | `INC-PH-01`, `DOC-INC-PH-01`, `ANN-INC-PH-*`, `SCN-PH-BASE`, `SCN-PH-EDGE` |
| P2 | MY (Malaysia) | no_coverage | `INC-MY-01`, `DOC-INC-MY-01`, `ANN-INC-MY-*`, `SCN-MY-BASE`, `SCN-MY-EDGE` |
| P2 | ID (Indonesia) | no_coverage | `INC-ID-01`, `DOC-INC-ID-01`, `ANN-INC-ID-*`, `SCN-ID-BASE`, `SCN-ID-EDGE` |
| P2 | NG (Nigeria) | no_coverage | `INC-NG-01`, `DOC-INC-NG-01`, `ANN-INC-NG-*`, `SCN-NG-BASE`, `SCN-NG-EDGE` |
| P2 | EG (Egypt) | no_coverage | `INC-EG-01`, `DOC-INC-EG-01`, `ANN-INC-EG-*`, `SCN-EG-BASE`, `SCN-EG-EDGE` |
| P2 | AE (UAE) | no_coverage | `INC-AE-01`, `DOC-INC-AE-01`, `ANN-INC-AE-*`, `SCN-AE-BASE`, `SCN-AE-EDGE` |
| P2 | SA (Saudi Arabia) | no_coverage | `INC-SA-01`, `DOC-INC-SA-01`, `ANN-INC-SA-*`, `SCN-SA-BASE`, `SCN-SA-EDGE` |
| P2 | VN (Vietnam) | no_coverage | `INC-VN-01`, `DOC-INC-VN-01`, `ANN-INC-VN-*`, `SCN-VN-BASE`, `SCN-VN-EDGE` |

Phase 2 exit criteria:

1. At least 7/10 countries above become `incentive_covered`.
2. US has at least 3 stable state-level entries wired and tested.
3. No regression in existing 38 backend tests.

## Phase 3: Depth Pass for Existing Covered Countries

Objective: improve precision and unlock suggestions quality by deepening already covered countries.

| Priority | Country Group | Exact Records |
|---|---|---|
| P3 | FR, DE, GB, IT, ES | `INC-<CC>-REG-EXP-*` (regional/program variants), `DOC-INC-<CC>-EXTRA-*`, `ANN-INC-<CC>-EXTRA-*`, `SCN-<CC>-STACKING` |
| P3 | CA, AU, NL, BE | `INC-<CC>-ALT-*` for alternate programmes, `TRY-<CC>-VERIFY-*`, `SCN-<CC>-MULTI-PROG` |
| P3 | Cultural-test countries | `CT-<CC>-01` normalization + UI review prompts + `SCN-<CC>-CT-PASS` and `SCN-<CC>-CT-FAIL` |

Phase 3 exit criteria:

1. Near-miss suggestions reference at least one actionable lever for each top scenario.
2. Cultural-test pathways are explicit (pass/fail/unknown) for top countries requiring them.
3. Source freshness warnings are surfaced for records not verified in the last 12 months.

## Sequencing Recommendation

1. Execute Phase 1 first (highest unlock efficiency because treaty pathways already exist).
2. Run a release checkpoint (tests + scenario snapshots + UX review).
3. Execute Phase 2 in two mini-batches of five countries each.
4. Execute Phase 3 only after Phase 2 data quality is stable.

## Immediate Next Sprint (2 weeks)

1. Complete `INC-JP-01`, `INC-IN-01`, `INC-CN-01`, `INC-MX-01`.
2. Add their doc/annotation records and 8 scenario fixtures.
3. Re-run `build_coverage_matrix.py` and publish updated matrix.
4. Freeze outputs with golden snapshot tests for those four countries.
