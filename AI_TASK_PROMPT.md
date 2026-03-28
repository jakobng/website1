# CoPro Calculator - Data Quality & Performance Improvement Task

**Status:** High Priority
**Completion Target:** 2-3 weeks
**Difficulty:** Medium-High
**Key Blocker:** Yes - Affects usability in 46% of markets

---

## Project Context

The CoPro Calculator is a film co-production financing tool that:
- Takes project details (budget, format, shoot locations, nationalities)
- Queries a database of 143 countries' incentive programs
- Returns ranked financing scenarios with verified sources

**Current State:**
- ✅ Test infrastructure expanded to 169 comprehensive scenarios
- ✅ Parallel execution runner implemented
- ❌ **Critical issues identified in test results** (see below)
- ❌ 46% of countries show zero financing
- ❌ 10 countries generate NO scenarios at all
- ❌ Performance: 1-2.5 minutes per scenario generation

---

## Critical Issues to Address

### Issue #1: 10 Countries Generate NO Scenarios (RED FLAGS) 🔴

**Affected Countries:**
Portugal (PT), Montenegro (ME), North Macedonia (MK), Malta (MT), Romania (RO), Serbia (RS), Slovenia (SI), Slovakia (SK), Turkey (TR), Ukraine (UA)

**Problem:**
When these countries are used as shoot locations, the scenario generator returns an EMPTY list of scenarios. This is a hard failure - users get no financing options.

**Root Cause Analysis:**
Each of these countries has exactly **1 incentive** in the database, while working countries have 4-12:
- Portugal: 1 incentive program
- Montenegro: 1 incentive program
- ... (all 10 have 1 each)

**Why It Happens:**
The single incentive doesn't match test scenario requirements (likely due to missing eligibility rules, budget thresholds, or spend allocation requirements).

**Investigation Steps:**
1. For each of the 10 countries, examine the single incentive in `backend/seed_data.py`
2. Check what eligibility rules are defined for it
3. Create a debug test scenario with the exact parameters that SHOULD match
4. Trace through `rule_engine.py` to see where the filtering happens
5. Determine if:
   - The incentive data is incomplete (missing required fields)
   - The eligibility rules are too strict
   - The incentive needs multiple programs to be viable
   - Budget thresholds are blocking the match

**Example Debugging:**
```
Test: Portugal documentary, €500k, 100% Portugal shoot
Expected: Should match Portuguese incentive
Actual: No scenarios generated
Debug: Log each eligibility check to see which rule fails
```

**Deliverable:**
- Root cause document for each of the 10 countries
- Specific fix for each (add rules, add programs, or fix data)
- Updated seed data with corrections
- Verification that each country now generates at least 1 scenario

---

### Issue #2: 46% of Countries Show ZERO Financing (73 Countries) ❌

**Problem:**
83 out of 169 test scenarios produce 0% financing, meaning these countries have no viable incentives matching the test parameters.

**Affected Countries (Major Markets):**
- **Asia:** China (0%), Indonesia (0%), Vietnam (0%), Thailand (0%), Cambodia (0%), Laos (0%), Myanmar (0%), Mongolia (0%), etc.
- **Africa:** Most countries show 0%
- **Americas:** Argentina (0%), Brazil (0%), many others

**Root Causes (Multiple):**

**A. Sparse Incentive Data**
Current distribution:
- 53 countries: 0 incentives (27%)
- 80+ countries: 1-3 incentives only
- Only 5 countries: 4+ incentives

Major market gaps:
- China: 2 programs (needs 5+)
- India: 1 program (needs 3+)
- Japan: 1 program (needs 3+)
- Vietnam: 0 programs (needs complete data)
- Thailand: 0 programs (needs complete data)
- Indonesia: 0 programs (needs complete data)
- Brazil: 1 program (needs more)
- Mexico: 3 programs (sparse)

**B. Test Scenario Design Issue**
All SWEEP tests use identical template:
- Documentary format (not features)
- €500k budget
- 100% single-country shoot
- No co-productions

This template doesn't trigger incentives designed for:
- Feature films (€2-10M budgets)
- Higher spend allocations
- Co-production requirements

**C. Possible Eligibility Rule Issues**
Some countries with database incentives still show 0%, suggesting rules are too restrictive:
- Budget threshold checks
- Spend allocation requirements
- Nationality requirements
- Producer requirements

---

## Work Breakdown

### Phase 1: Data Quality Audit & Fix (CRITICAL)

**Objective:** Ensure all 143 countries have complete incentive data

**Tasks:**

#### 1.1 Audit Current Incentive Data
**File:** `backend/seed_data.py`

```python
# Create inventory script to show:
# - Country code
# - Number of incentives
# - Incentive names
# - Budget ranges (min/max)
# - Required fields
# - Completeness score

# Example output:
# PT: 1 incentive (VERY INCOMPLETE)
#   - Portugal Film Commission Support Program
#   - Budget: Not specified
#   - Required fields: Missing eligibility details
#   - Completeness: 20%
```

**Deliverable:** CSV/JSON report showing completeness for all 143 countries

#### 1.2 Priority Data Addition (Tier 1 - Critical Markets)
**Target:** Add/expand incentive programs for markets with <2 programs

**Priority Order:**
1. **China** - Add major programs (likely Film Fund, regional incentives)
2. **India** - Expand from 1 to 3-4 programs
3. **Japan** - Expand from 1 to 3-4 programs
4. **Vietnam** - Add complete incentive structure
5. **Thailand** - Add complete incentive structure
6. **Indonesia** - Add complete incentive structure
7. **Brazil** - Expand from 1 to 3+ programs
8. **Mexico** - Expand from 3 to 5+ programs
9. **South Korea** - Verify current data, consider expansion
10. **Southeast Asia general** - Fill gaps in Cambodia, Laos, Myanmar

**Data to Research & Add:**
- Official government film incentive databases
- IMDb Pro production guides
- Government tourism/economic development offices
- International Film Commission Association resources

**For Each Incentive Program, Document:**
```python
{
    'country_code': 'CN',
    'name': 'Program Name',
    'incentive_type': 'rebate|credit|funding|tax_shelter',
    'rebate_percent': 25,  # or null if variable
    'description': 'Detailed description',
    'requirements': {
        'budget_min': 100000,
        'budget_max': None,  # None = unlimited
        'local_spend_min': 0.3,  # 30% minimum
        'formats': ['feature', 'documentary', 'series', 'animation'],
        'nationalities': ['any', 'co-production'],
        'production_country': True,
    },
    'source_url': 'official government URL',
    'source_description': 'Official source',
    'last_verified': '2026-03-26',
    'notes': 'Any special conditions'
}
```

**Deliverable:**
- Updated `seed_data.py` with 20+ new incentive programs
- Research documentation for each added program
- Verification that each country now has 3+ programs where available

#### 1.3 Verify/Complete Treaty Data
**File:** `backend/seed_data.py` (Treaties section)

**Task:**
- Ensure all bilateral treaties are documented between countries with co-production agreements
- Verify multilateral treaty memberships (EU, APEC, etc.)
- Test that co-production scenarios work for verified treaty pairs

**Deliverable:**
- Audit of treaty coverage
- Any missing treaties added
- Test scenarios for key treaty pairs

---

### Phase 2: Rule Engine Debugging & Optimization (HIGH PRIORITY)

**Objective:** Understand why eligible scenarios aren't being generated

**Files Involved:**
- `backend/app/rule_engine.py` - Core eligibility logic
- `backend/app/scenario_generator.py` - Scenario assembly logic

#### 2.1 Debug Red-Flag Countries (10 Countries)

**For Each of the 10 Red-Flag Countries:**

Create a detailed debug trace:

```python
# For Portugal, run this test:
from app.schemas import ProjectInput, ShootLocation
from app.scenario_generator import generate_scenarios
from app.database import SessionLocal
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

db = SessionLocal()

# Test scenario that SHOULD match
project = ProjectInput(
    title="Portugal Test",
    format="documentary",
    stage="production",
    budget=500_000,
    budget_currency="EUR",
    shoot_locations=[ShootLocation(country="Portugal", percent=100)],
    director_nationalities=["Portugal"],
    willing_add_coproducer=True,
)

# Run and trace
scenarios = generate_scenarios(project, db)
print(f"Generated {len(scenarios)} scenarios")

# Expected: At least 1 scenario with Portugal incentive
# Actual: 0 scenarios

# Debug logging should show:
# - What Portuguese incentives are available
# - Which eligibility rules are evaluated
# - Why each rule passes or fails
# - Why no scenarios were generated
```

**Logging Requirements:**
Add detailed logging to `rule_engine.py`:
```python
def check_incentive_eligibility(project, incentive, db):
    logger.debug(f"Checking {incentive.name} for {project.title}")

    # Each check should log:
    logger.debug(f"  Budget check: ${project.budget} vs ${incentive.budget_min}")
    logger.debug(f"  Format check: {project.format} vs {incentive.formats}")
    logger.debug(f"  Spend check: {project.local_spend} vs {incentive.local_spend_min}")

    if not passes_check:
        logger.debug(f"  FAILED: {reason}")
        return False

    logger.debug(f"  PASSED")
    return True
```

**Deliverable:**
- Debug trace for each of 10 red-flag countries
- Identified root cause for each
- Specific fix (add rules, adjust thresholds, fix data)

#### 2.2 Analyze Zero-Financing Countries (Sample of 10)

**Approach:**
Pick 10 countries from the 73 that show 0% financing. For each:
1. Check what incentives are in the database
2. Create a test scenario
3. Trace why incentives don't match
4. Determine if issue is: data, rules, or test design

**Example: China**
```
China has 2 incentives in DB:
  - Film Fund (budget min: 1M)
  - Regional Incentive (budget min: 500k)

Test scenario: €500k documentary
Expected: Should match "Regional Incentive"
Actual: 0% financing

Debug questions:
  1. Is Regional Incentive correctly configured?
  2. What eligibility rules block it?
  3. Is budget threshold issue (500k EUR vs expected currency)?
  4. Are co-production rules blocking single-country scenario?
```

**Deliverable:**
- Analysis of 10 sample zero-financing countries
- Root cause breakdown (% data vs rules vs test design)
- Recommendations for each

#### 2.3 Review & Optimize Eligibility Rules

**Task:** Ensure rules aren't overly restrictive

**Rules to Audit (in `rule_engine.py`):**
- Budget minimum/maximum checks
- Spend allocation requirements
- Nationality/producer requirements
- Co-production logic
- Currency conversion logic
- Format-specific rules

**For Each Rule:**
1. Document its purpose
2. Verify it matches actual incentive requirements
3. Check if thresholds are correct
4. Test with sample scenarios

**Deliverable:**
- Rule audit report
- Any adjustments needed
- Test cases verifying rules are correct

---

### Phase 3: Performance Optimization (MEDIUM PRIORITY)

**Objective:** Reduce scenario generation time from 1-2.5 minutes to <10 seconds

**File:** `backend/app/scenario_generator.py`

#### 3.1 Profile to Find Bottleneck

**Add Timing Instrumentation:**
```python
import time

def generate_scenarios(project, db):
    start = time.time()

    # Phase 1: Get all countries
    phase1_start = time.time()
    all_countries = get_eligible_countries(project)
    print(f"Phase 1 (eligible countries): {time.time()-phase1_start:.2f}s")

    # Phase 2: Check treaties
    phase2_start = time.time()
    treaties = get_applicable_treaties(all_countries)
    print(f"Phase 2 (treaties): {time.time()-phase2_start:.2f}s")

    # Phase 3: Check incentives
    phase3_start = time.time()
    for country in all_countries:
        incentives = check_incentive_eligibility(project, country)
    print(f"Phase 3 (incentives): {time.time()-phase3_start:.2f}s")

    # Phase 4: Generate scenarios
    phase4_start = time.time()
    scenarios = assemble_scenarios(...)
    print(f"Phase 4 (assemble): {time.time()-phase4_start:.2f}s")

    total = time.time() - start
    print(f"TOTAL: {total:.2f}s")

    return scenarios
```

**Run Against Test Scenarios:**
- Identify which phase is slowest
- Focus optimization there

**Expected Issues to Find:**
- Likely O(n²) in partner/treaty matching
- Inefficient database queries
- Repeated eligibility checks without caching
- Generating too many intermediate scenarios

#### 3.2 Implement Caching

**Cache Eligibility Results:**
```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def check_incentive_eligibility_cached(project_hash, incentive_id):
    # Cached results - huge speedup for repeated checks
    return check_incentive_eligibility(...)
```

#### 3.3 Optimize Database Queries

**Audit Current Queries:**
- Are we loading all 143 countries unnecessarily?
- Can we filter at DB level instead of in Python?
- Are we doing N+1 queries?

**Optimization Opportunities:**
- Eager load treaties with countries
- Use SQL joins instead of Python loops
- Pre-filter to applicable countries before checking incentives

#### 3.4 Early Exit Logic

**Stop Processing When:**
- We've found N viable scenarios (don't generate all 15)
- We've determined a country is ineligible (skip all its incentives)
- Financing hits 100% (no need for more options)

**Deliverable:**
- Profiling report showing timing before/after
- Code changes that reduce time to <10 seconds
- Benchmarks showing improvement

---

### Phase 4: Test Scenario Expansion (LOWER PRIORITY)

**Objective:** Make tests more realistic and trigger more incentives

**Current Issue:**
All SWEEP tests use identical template (€500k documentaries). This doesn't test:
- Feature films (which many incentives target)
- Higher budgets
- Co-productions
- Animation/series formats

**Expansion Plan:**

#### 4.1 Add Feature Film Tests to Major Markets

For each major region, add:
- Feature film (€2-5M) tests
- Co-production tests
- Series/animation variants

**Example New Scenarios:**
```python
# For China
sweep_doc_cn_feature = ProjectInput(  # Feature film variant
    title="China Feature Test",
    format="feature_fiction",
    budget=3_000_000,
    budget_currency="USD",
    shoot_locations=[ShootLocation(country="China", percent=100)],
    ...
)

sweep_doc_cn_copro = ProjectInput(  # Co-production variant
    title="China Co-production",
    format="documentary",
    budget=1_500_000,
    budget_currency="USD",
    shoot_locations=[
        ShootLocation(country="China", percent=60),
        ShootLocation(country="Hong Kong", percent=40),
    ],
    has_coproducer=["Hong Kong"],
    ...
)
```

#### 4.2 Update SWEEP Categories

Add new sub-categories:
- `SWEEP_AM_FEATURE` - Americas feature films
- `SWEEP_AS_FEATURE` - Asia-Pacific features
- `SWEEP_AF_FEATURE` - Africa features
- `SWEEP_COPRO` - 2-3 country co-productions

**Deliverable:**
- Updated `comprehensive_test_runner.py` with new categories
- 50+ new test scenarios covering features, co-productions, high budgets
- Results showing improved coverage

---

## Implementation Sequence

### Week 1: Critical Issues
1. **Day 1-2:** Data audit and inventory all 143 countries
2. **Day 3:** Debug 10 red-flag countries (PT, ME, MK, MT, RO, RS, SI, SK, TR, UA)
3. **Day 4-5:** Add missing incentive programs for top 10 markets (China, India, Japan, Vietnam, Thailand, Indonesia, Brazil, Mexico, etc.)

### Week 2: Rule Engine
1. **Day 1-2:** Profile scenario_generator to find bottleneck
2. **Day 3:** Debug sample of zero-financing countries
3. **Day 4:** Optimize performance and implement caching
4. **Day 5:** Run full 169-scenario test suite, measure improvements

### Week 3: Polish & Validation
1. **Day 1-2:** Expand test scenarios (features, co-productions)
2. **Day 3:** Final data audit and cleanup
3. **Day 4:** Run comprehensive validation tests
4. **Day 5:** Documentation and knowledge transfer

---

## Success Criteria

### Objective 1: Fix Critical Issues
- ✅ All 10 red-flag countries generate at least 1 scenario
- ✅ 100% of countries can generate scenarios without errors

### Objective 2: Improve Coverage
- ✅ 80%+ of countries show >5% financing
- ✅ All 143 countries have 3+ incentive programs (where available)
- ✅ Major markets (China, India, Japan, Brazil, Mexico) have 5+ programs each

### Objective 3: Performance
- ✅ Each scenario generates in <10 seconds (target: <5 seconds)
- ✅ Full 169-scenario suite completes in <30 minutes (vs current 4+ hours)
- ✅ Interactive queries get results in <5 seconds

### Objective 4: Data Quality
- ✅ All 143 countries have verified incentive data
- ✅ All incentives have complete eligibility rules
- ✅ All treaties are documented
- ✅ Last_verified dates updated

---

## Deliverables

### Code Changes
- ✅ Updated `backend/seed_data.py` (20+ new incentive programs)
- ✅ Updated `backend/app/rule_engine.py` (optimized, with logging)
- ✅ Updated `backend/app/scenario_generator.py` (performance improvements)
- ✅ Updated `scenario_tests/comprehensive_test_runner.py` (new test scenarios)

### Documentation
- ✅ `DATA_AUDIT_REPORT.md` - Inventory of all 143 countries
- ✅ `ROOT_CAUSE_ANALYSIS.md` - Why each of 10 red-flag countries fails
- ✅ `PERFORMANCE_OPTIMIZATION_REPORT.md` - Timing improvements
- ✅ `INCENTIVE_RESEARCH.md` - Sources for new incentive programs

### Validation
- ✅ All 169 scenarios generate without errors
- ✅ All 10 red-flag countries produce scenarios
- ✅ 80%+ of countries show >5% financing
- ✅ Performance benchmarks showing <10 sec/scenario

### Test Results
- ✅ New comprehensive test suite run (169 scenarios)
- ✅ Coverage report showing improvement
- ✅ Performance metrics showing speedup

---

## Technical Details & Resources

### Key Files to Modify
```
backend/
  app/
    rule_engine.py          # Eligibility rules (DEBUG & OPTIMIZE)
    scenario_generator.py   # Main logic (PROFILE & OPTIMIZE)
    models.py              # ORM models (READ ONLY)
  seed_data.py             # Incentive data (ADD NEW PROGRAMS)
  scripts/
    backup_and_reseed.py  # Data loading script

scenario_tests/
  comprehensive_test_runner.py  # Test suite (ADD NEW SCENARIOS)
```

### Database Schema Reference
The incentive data includes:
```python
{
    'country_code': 'XX',
    'name': 'Program name',
    'incentive_type': 'rebate|credit|funding|tax_shelter',
    'rebate_percent': 25,
    'description': 'Details',
    'requirements': {
        'budget_min': 100000,
        'budget_max': None,
        'local_spend_min': 0.3,
        'formats': ['feature', 'documentary'],
        'nationalities': ['any', 'co-production'],
        'production_country': True,
    },
    'source_url': 'URL',
    'source_description': 'Source info',
    'last_verified': '2026-03-26'
}
```

### Research Sources for Incentive Data
- **China:** SARFT (State Administration of Radio, Film, and Television), regional film commissions
- **India:** Ministry of I&B, National Film Development Corporation
- **Japan:** Ministry of Economy, local prefecture offices
- **Vietnam:** Ministry of Culture, Sports and Tourism
- **Thailand:** Thai Film Board, Department of Cultural Promotion
- **Indonesia:** Ministry of Education and Culture
- **Brazil:** Cinema Agency (Agência Nacional do Cinema)
- **Mexico:** Mexican Film Institute (IMCINE)
- **IMDb Pro:** Production guides by country
- **IFCAA:** International Film Commission Association

---

## Questions to Answer During Implementation

1. **Why do 10 countries generate NO scenarios?**
   - Is it a data completeness issue?
   - Is it rule exclusions?
   - Is it database schema mismatch?

2. **Why do 46% of countries show 0% financing?**
   - Sparse incentive data? (most likely)
   - Eligibility rules too strict?
   - Test scenario template unsuitable?
   - Currency/budget mismatches?

3. **What's the bottleneck causing 1-2.5 min per scenario?**
   - Treaty lookup O(n²)?
   - Inefficient database queries?
   - Generating too many variants?
   - Eligibility checking inefficiency?

4. **Are the eligibility rules correct?**
   - Budget minimums/maximums realistic?
   - Spend allocation requirements match actual incentives?
   - Nationality rules accurate?
   - Co-production rules make sense?

---

## Notes & Constraints

- **Database:** SQLite at `backend/coproduction.db`
- **ORM:** SQLAlchemy
- **Testing:** Run scenarios with `scenario_tests/comprehensive_test_runner.py`
- **Parallel Testing:** Use `scenario_tests/parallel_runner.py` for faster runs
- **Logging:** Add detailed logging to trace issues
- **Git:** Commit changes with clear messages
- **No Breaking Changes:** Maintain backward compatibility with existing API

---

## Success Metrics (Final)

After completing this work:

| Metric | Current | Target |
|--------|---------|--------|
| **Countries generating scenarios** | 133/143 (93%) | 143/143 (100%) |
| **Countries with >5% financing** | 86/169 (54%) | ~140/169 (80%+) |
| **Scenario generation time** | 90-120 sec | <10 sec |
| **Full suite execution** | 4+ hours | <30 min |
| **Red flag countries** | 10 | 0 |
| **Countries with 1 incentive** | 10+ | <5 (acceptable for very small markets) |
| **Countries with 3+ programs** | Very few | Most major markets |

---

**This is a comprehensive task for improving the CoPro Calculator's data quality, rule engine, and performance. Work systematically through each phase, thoroughly document findings, and validate improvements with test runs.**
