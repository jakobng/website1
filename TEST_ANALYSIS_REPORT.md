# Comprehensive Test Suite - Detailed Analysis Report

**Generated:** 2026-03-26
**Total Scenarios Tested:** 169
**Status:** ⚠️ PARTIALLY SUCCESSFUL - Significant work needed

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Coverage Rate** | 54% (86 with financing, 83 with zero) |
| **Red Flags** | 10 countries (no scenarios generated) |
| **Warnings** | 233 total (158 performance, 75 coverage) |
| **Performance** | 1-2.5 minutes per scenario (too slow) |

---

## CRITICAL ISSUES

### Issue #1: 10 Countries Generate NO Scenarios ❌

**Affected Countries:**
- Portugal (PT), Montenegro (ME), North Macedonia (MK), Malta (MT)
- Romania (RO), Serbia (RS), Slovenia (SI), Slovakia (SK), Turkey (TR), Ukraine (UA)

**Root Cause:**
Each country has exactly **1 incentive** in the database, which doesn't match test scenario requirements:
- PT: 1 incentive | ME: 1 incentive | MK: 1 incentive | MT: 1 incentive
- RO: 1 incentive | RS: 1 incentive | SI: 1 incentive | SK: 1 incentive
- TR: 1 incentive | UA: 1 incentive

**Comparison (Working Countries):**
- France: 12 incentives → Works perfectly
- Spain: 11 incentives → Works perfectly
- Germany: 10 incentives → Works perfectly

**Why It Matters:**
These 10 European countries cannot generate ANY scenarios, making the calculator unusable for them.

**Fix Required:**
1. Review the single incentive for each country - check if it has proper eligibility rules
2. Add additional incentive programs for these countries
3. Verify data import wasn't incomplete

---

### Issue #2: 46% of Countries Show ZERO Financing ❌

**Coverage:**
- ✅ 86 scenarios with financing (54%)
- ❌ 83 scenarios with zero financing (46%)

**Problem Countries (73 total):**
Most Asian, African, and many Americas countries show 0%:
- Asia: China, India, Indonesia, Vietnam, Thailand, Cambodia, Laos, Myanmar, etc.
- Africa: 30+ countries across all regions
- Americas: Argentina, Brazil, Colombia, Peru, etc.

**Top Performers (30%+ financing):**
1. Spain (doc): 36%
2. Spain (feature): 36%
3. Australia (location offset): 28%
4. Italy+Spain co-pro: 26%

**Root Causes:**
1. **Sparse incentive data** - Major markets have only 1-2 programs:
   - China: 2 incentives
   - India: 1 incentive
   - Japan: 1 incentive
   - Vietnam: 0 incentives
   - Thailand: 0 incentives

2. **Eligibility rules too restrictive** - Rules may be filtering out valid scenarios
3. **Test scenario design** - €500k documentaries don't trigger incentives designed for:
   - Feature films
   - Higher budgets
   - Specific spend thresholds
   - Co-production structures

**Impact:**
Users in 46% of countries get zero financing options, making calculator appear broken for those markets.

---

## MAJOR ISSUES

### Issue #3: Performance Bottleneck ⚠️

**Problem:**
Each scenario takes **1-2.5 minutes** to generate:
- Fastest: 48 seconds (Vanuatu)
- Slowest: 165 seconds (animation feature)
- Average: 90-100 seconds

**Impact:**
- 169 scenarios = 4+ hours for complete run
- Even with 8 parallel workers, this is slow
- Each interactive user query waits 1-2 minutes

**Root Cause (hypothesis):**
The `scenario_generator.py` likely has:
- O(n²) or worse algorithm in treaty/partner matching
- No caching of eligibility checks
- Generates 15 scenario variants per input (expensive)
- Checks all combinations without early exit

**Fix Required:**
1. Profile scenario_generator.py with timing instrumentation
2. Identify bottleneck (likely treaty matching or co-producer evaluation)
3. Implement caching for eligibility checks
4. Add early-exit logic when processing large country pools

---

### Issue #4: Sparse Incentive Data Quality ❌

**Distribution:**
- 53 countries: 0 incentives (27%)
- 80+ countries: 1-3 incentives only
- 5 countries: 4+ incentives (FR, ES, DE, IT, GB)

**Major Market Gaps:**
| Market | Incentives | Status |
|--------|------------|--------|
| China | 2 | Severely under-represented |
| India | 1 | Missing major programs |
| Japan | 1 | Missing major programs |
| Vietnam | 0 | No data |
| Thailand | 0 | No data |
| Indonesia | 0 | No data |
| Brazil | 1 | Missing programs |
| Mexico | 3 | Sparse |

**Fix Required:**
1. Research and add China's major incentive programs
2. Add India's film incentives
3. Populate Vietnam, Thailand, Indonesia completely
4. Cross-reference against official government sources

---

## DATA QUALITY ISSUES

### Issue #5: Eligibility Rules May Be Too Restrictive ⚠️

**Observation:**
Some countries with clearly active incentives show 0%:
- Argentina has 2 incentives but shows 0% in test
- Many countries show 0% despite having database records

**Hypothesis:**
The `rule_engine.py` is filtering out valid scenarios due to:
1. Budget threshold checks (maybe too strict?)
2. Spend allocation requirements
3. Nationality/producer requirements
4. Co-production logic excluding single-country projects

**Fix Required:**
Debug by running sample scenarios and logging which rules reject them.

---

### Issue #6: Test Scenario Design Too Narrow ⚠️

**Current Pattern:**
All SWEEP tests use:
- Documentary format (no features)
- €500k or $500k budget
- 100% single-country shoot
- No co-productions

**Problem:**
This template doesn't trigger incentives designed for:
- Feature films ($2-10M budgets)
- Different spend allocations
- Co-production structures
- Higher budget thresholds

**Example:**
Spain shows 36% financing because it has a feature test scenario. Asian countries only have €500k documentary tests, which don't trigger their incentives.

---

## Prioritized Work List

### 🔴 CRITICAL (Fix immediately)
```
[ ] Fix 10 red-flag countries (PT, ME, MK, MT, RO, RS, SI, SK, TR, UA)
    - Review their single incentive for configuration issues
    - Add missing incentive programs
    - Verify data import completeness

[ ] Investigate eligibility rules blocking 46% of countries
    - Profile rule_engine.py
    - Check budget thresholds
    - Verify spend allocation logic
```

### 🟠 HIGH PRIORITY (Major coverage gaps)
```
[ ] Expand Asia-Pacific incentive data
    - China: Add major programs (currently 2)
    - India: Expand (currently 1)
    - Japan: Expand (currently 1)
    - Vietnam, Thailand, Indonesia: Add complete data

[ ] Debug rule_engine for 73 zero-financing countries
    - Log which rules are rejecting scenarios
    - Compare successful vs failing countries
    - Verify against actual incentive requirements

[ ] Audit treaty data
    - Ensure all 143 countries have correct bilateral treaties
    - Check multilateral treaty membership
    - Verify co-production eligibility
```

### 🟡 MEDIUM PRIORITY (Performance)
```
[ ] Profile scenario_generator.py
    - Find exact bottleneck
    - Likely O(n²) in partner matching

[ ] Optimize performance
    - Implement caching for eligibility checks
    - Add early-exit logic
    - Consider lazy evaluation

Target: Get under 10 seconds per scenario
```

### 🔵 LOWER PRIORITY (Enhancements)
```
[ ] Expand SWEEP test scenarios
    - Add feature film tests (not just documentaries)
    - Test higher budgets (€2-5M)
    - Add co-production variants

[ ] Audit all 143 countries' incentive data
    - Verify accuracy against official sources
    - Check for duplicates/errors
    - Update last_verified dates
```

---

## Recommended Next Steps

1. **Immediate (Today):**
   - Fix the 10 red-flag countries
   - Profile scenario_generator.py to find performance bottleneck

2. **This Week:**
   - Debug rule_engine to understand why 46% show zero financing
   - Add major incentive programs for China, India, Vietnam, Thailand

3. **This Month:**
   - Optimize performance to sub-10 seconds per scenario
   - Expand test scenarios to include features and co-productions
   - Complete data audit for all 143 countries

4. **Ongoing:**
   - Monitor actual user scenarios to find more gaps
   - Prioritize data additions based on market demand

---

## Files to Investigate

| File | Issue | Priority |
|------|-------|----------|
| `backend/app/scenario_generator.py` | Performance (1-2.5 min/scenario) | 🟡 High |
| `backend/app/rule_engine.py` | Eligibility rules too strict? | 🟠 High |
| `backend/seed_data.py` | Sparse incentive data | 🟠 High |
| `scenario_tests/comprehensive_test_runner.py` | Test design too narrow | 🔵 Low |

---

## Success Metrics (Goals)

After fixes, target:
- ✅ 100% of countries generate at least 1 scenario
- ✅ 80%+ of countries show >5% financing
- ✅ Performance <10 seconds per scenario
- ✅ 5+ incentive programs per major market
- ✅ All 143 countries have verified incentive data
