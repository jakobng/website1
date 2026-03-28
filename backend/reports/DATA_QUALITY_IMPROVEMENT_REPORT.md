# CoPro Calculator: Data Quality & Performance Improvement Report

## Executive Summary
This report documents the completion of Phase 1 (Data Quality Audit & Fix) and Phase 2 (Core Engine Refinement) for the CoPro Calculator. Key improvements include a comprehensive data audit, significant data expansion in 9 Tier 1 markets, and critical logic fixes in the scenario generator and rule engine.

## Phase 1: Data Quality Audit & Fix

### 1.1 Data Quality Audit
- **Audit Tool:** Created `backend/scripts/data_quality_audit.py` to analyze incentive completeness.
- **Key Findings:** Identified 42 countries with zero incentive data and verified that many "Red Flag" countries were previously failing due to seeding inconsistencies.
- **Baseline Report:** Generated `backend/reports/DATA_AUDIT_REPORT.md` providing a per-country inventory of data completeness.

### 1.2 Priority Data Addition (Tier 1 Markets)
Enhanced coverage for 9 critical markets with 2026-verified data:
- **China (CN):** Added Wanda Studios (40% rebate), Hainan FTP (15% tax policy), and Hong Kong Collaboration Scheme (HK$9M grant). Total incentives: 4.
- **India (IN):** Verified 40% rebate (30% base + bonuses) and ₹30 Crore cap.
- **Japan (JP):** Updated JLOX+ with 50% rebate, 1 Billion JPY cap, and 2026 multi-year expenditure rules.
- **Brazil (BR):** Added Spcine (20-30%) and RioFilme (30-35%) cash rebates. Total incentives: 3.
- **Indonesia (ID):** Added $10M International Co-Production Matching Fund. Total incentives: 2.
- **Mexico (MX):** Added the 2026 Decree 30% transferable tax credit with MXN 40M cap.
- **South Korea (KR):** Updated KOFIC 2026 guidelines (25% rebate, KRW 400M threshold).
- **Thailand (TH) & Vietnam (VN):** Verified and updated current fund/rebate notes.

### 1.3 Documentation & Source Linking
- Updated `backend/seed_documents.py` with 2026 primary sources:
    - Japan: JLOX+ 2026 Guidelines (PDF)
    - India: Revised Incentive Guidelines 2024-2026 (PDF)
    - Mexico: Federal Stimulus Decree Feb 2026 (URL)
- Added specific **Document Annotations** for rebate rates and caps, enabling direct legal citations in calculator reports.

## Phase 2: Core Engine Refinement

### 2.1 Labour Fraction Inconsistency (Issue #3)
- Fixed the discrepancy between model and engine.
- The rule engine now correctly pulls `labour_fraction` from the incentive model (defaulting to 0.6 if null).
- Verified that Canada (CPTC/FISTC) and Jamaica records in `seed_data.py` utilize this field correctly.

### 2.2 Majority Partner Selection (Issue #4)
- **Problem:** Scenarios often labeled a 0% shoot country as "majority" if it had higher incentives.
- **Fix:** Modified `_build_scenario` in `scenario_generator.py` to prioritize `shoot_percent` for role assignment.
- **Result:** The country where the most filming occurs is now correctly identified as the "majority" partner.

### 2.3 Duplicate Requirements (Issue #5)
- Verified and enforced requirement deduplication in the scenario generator.
- Reports now present a clean "GLOBAL REQUIREMENTS / BLOCKS" section without redundant entries.

## Phase 3: Validation Results
- **Scaffold Tests:** Ran `scenario_tests/run_phase1_scaffold.py`.
- **Improvements:**
    - Japan: 20.0% financing (up from previous baseline).
    - China: 16.0% financing (verified with 2026 incentives).
    - All Tier 1 markets now generate valid, multi-partner scenarios.

## Next Steps
1. **Phase 3.2 (Production Launch):** Final regression testing on all 169 scenarios.
2. **Phase 4 (Performance):** If scale issues persist, implement the suggested `lru_cache` for `_to_eur` and treaty lookups.
3. **Continuous Audit:** Run `data_quality_audit.py` weekly to track expansion progress.
