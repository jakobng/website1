# CoPro Calculator — Next Steps (Week of March 26, 2026)

## Status: Core Product Complete ✅

All 4 major implementation issues are **done**:
- ✅ Issue 1: Spend calculation (budget breakdown 40/35/25)
- ✅ Issue 2: Country selection UX (keyboard nav, 190+ countries)
- ✅ Issue 3: Financing label ("Estimated incentive recovery")
- ✅ Issue 5: Gemini-powered adaptive intake with scenario-aware questions

The tool is **fully functional and ready for use**. Filmmakers can now:
1. Use the guided interview to explore financing scenarios
2. Get accurate qualifying spend calculations based on budget breakdown
3. See which countries/incentives apply to their project
4. Understand every figure backed by official sources

---

## The Real Work: Making It Sustainable 🔄

The main challenge isn't building features—it's **keeping the data current** as government incentive programs change.

Your best chance of success is a **four-layer system** that turns your community into co-maintainers. See `PROJECT_ANALYSIS_AND_SUSTAINABILITY_PLAN.md` for the full design.

---

## This Week (March 26–31)

### Immediate action: Layer 1 (Source Freshness Monitoring)

**Why first?** It's the quickest win (1–2 weeks), highest visibility, and unblocks everything else.

**What to do:**
1. Read: `SUSTAINABILITY_IMPLEMENTATION_START.md` (Layers 1–2 walkthrough)
2. Implement Layer 1:
   - Add `source_alerts` database table
   - Write `check_source_freshness.py` script
   - Add admin dashboard endpoint + frontend indicator
   - Schedule weekly cron job
3. Test: Run the script, see which records are green/yellow/red
4. Deploy: Makes freshness **visible to you and users**

**Time estimate:** 5–8 hours of coding, 2 hours testing

**Result:** Dashboard showing "82% of incentive data verified in last 6 months" or "12 records over 1 year stale"

---

## Week of April 2–9

### Layer 2 (Community Update Proposals)

**Why?** Turns filmmakers into data contributors.

**What to do:**
1. Add `data_update_proposals` table
2. Build "Report issue" button on scenario cards
3. Create admin review queue
4. Implement approve/reject workflow (auto-updates `last_verified`)

**Result:** Filmmakers report stale data → you review → data is auto-updated

---

## Week of April 9–16

### Phase 1: Geographic Expansion (JP, IN, CN, MX)

**Why?** High-ROI: treaties already exist, just need local incentive data.

**What to do:**
1. Japan: Find official incentive details (METI/JETRO)
   - Add to `seed_data.py`
   - Add source documents & annotations
   - Add scenario tests
   - Run tests, verify they pass
2. Repeat for India, China, Mexico

**Time estimate:** 2–3 weeks per country (research + validation + testing)

**Result:** 4 new countries become incentive-covered, scenarios unlock for filmmakers

---

## Longer term (April–June)

### Phase 2: 10 No-Coverage Markets (US, TH, PH, MY, ID, NG, EG, AE, SA, VN)
### Phase 3: Deepen Existing Coverage (regional variants, cultural test normalization)

---

## Key files to understand

| File | Purpose |
|------|---------|
| `PROJECT_ANALYSIS_AND_SUSTAINABILITY_PLAN.md` | Deep dive on strategy + 4-layer system design |
| `SUSTAINABILITY_IMPLEMENTATION_START.md` | **START HERE** — concrete code walkthrough for Layers 1–2 |
| `EXECUTIVE_SUMMARY.md` | High-level overview for stakeholders |
| `QUICK_START_FOR_FILMMAKERS.md` | User guide (how filmmakers use the tool) |
| `backend/seed_data.py` | Incentive data (source of truth) |
| `backend/app/rule_engine.py` | Spend calculation logic |
| `backend/app/llm_intake.py` | Gemini interview + adaptive context |
| `backend/reports/expansion_backlog.md` | Geographic expansion roadmap |

---

## Two parallel tracks going forward

You can work on **two things in parallel**:

1. **Sustainability (data quality)**
   - Layer 1: Freshness monitoring (1–2 weeks)
   - Layer 2: Community proposals (1–2 weeks)
   - Layer 3: Automated validation (1–2 weeks) [optional, can skip initially]
   - Layer 4: Policy monitoring (1–2 weeks) [optional, can skip initially]

2. **Expansion (geographic coverage)**
   - Phase 1: Japan, India, China, Mexico (8 weeks total, can do in parallel)
   - Phase 2: 10 no-coverage markets (ongoing)

**Recommendation:** Do Layer 1 (freshness) this week (it's fast), then start Phase 1 expansion (Japan) in parallel while Layer 2 (community proposals) is being built.

---

## Success looks like (End of Q2 2026)

- [ ] Layer 1 live: Freshness dashboard visible to users
- [ ] Layer 2 live: Filmmakers can report issues, you can approve updates
- [ ] Phase 1 complete: JP, IN, CN, MX are incentive-covered with tests
- [ ] 80%+ of records verified in last 6 months
- [ ] 30–40 countries covered (up from 28)
- [ ] Filmmaker testimonial: "This tool helped me close financing. The data was accurate."

---

## Running the tool (for reference)

```bash
# Terminal 1: Backend
cd backend
source venv/Scripts/activate  # or venv/bin/activate on Mac/Linux
python -m uvicorn app.main:app --reload
# Runs at http://localhost:8000

# Terminal 2: Frontend
cd frontend
npm run dev
# Runs at http://localhost:5173

# In browser: http://localhost:5173
# API docs: http://localhost:8000/docs
```

---

## Questions? Start here

1. **How do I add a new incentive?** → Read `backend/seed_data.py`, add entry with sources
2. **How do scenarios calculate financing?** → Read `backend/app/rule_engine.py`, line 162 onward
3. **How does the interview work?** → Read `backend/app/llm_intake.py`, lines 34–99 (system prompt)
4. **How do I test scenarios?** → Read `backend/scenario_tests/scenarios_phase1/` folder
5. **What does completeness_score mean?** → See `llm_intake.py` lines 56–62

---

## The next 4 months

```
Week 1: Layer 1 (Freshness monitoring) — 1 person, 1 week
Week 2: Layer 2 setup (Community proposals) — 1 person, start of week
Week 3: Layer 2 complete + Phase 1 Japan starts — 2 people
Week 4–6: Phase 1 India, China, Mexico in parallel
Week 7: Refinement, testing, snapshot reports
Week 8+: Phase 2 (10 no-coverage markets)
```

**Estimated capacity needed:** 1 engineer, 50% time (or 0.5 FTE for 3 months)

---

## Go build it 🎬

Start with `SUSTAINABILITY_IMPLEMENTATION_START.md`. That's your roadmap for the next 4 weeks.

Good luck!
