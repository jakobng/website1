# CoPro Calculator: Executive Summary

**Date**: March 26, 2026
**Status**: Core product is solid; now entering maintenance + sustainability phase
**Key Risk**: Data decay (government incentive programs change frequently)
**Key Opportunity**: Turn the community into co-maintainers

---

## Current State

### ✅ What's Working Well

- **Solid engineering**: FastAPI + React, clean schema, well-documented models
- **Rich data**: 100+ incentives, 28+ countries, bilateral/multilateral treaty data
- **User-friendly**: Dual input modes (manual form + guided AI interview), inspectable sources
- **Verified data**: Every number is cited with official sources, last-verified dates
- **Test coverage**: Scenario fixtures, integration tests, data quality audits

### 🚨 What Needs Work

| Issue | Impact | Effort | Priority |
|-------|--------|--------|----------|
| Spend calculation (Issue 1) | Scenarios show inflated numbers (wrong budget split) | 1–2 weeks | HIGH |
| Country selection UX (Issue 2) | Can't find countries beyond top 95; no keyboard nav | 3–5 days | MED |
| Unlabeled financing amount (Issue 3) | Users don't know what the big number represents | 1–2 days | MED |
| LLM adaptive intake (Issue 5) | Current Claude intake doesn't ask scenario-aware questions | 2–3 weeks | HIGH |
| Data freshness | No automated monitoring; stale records risk user trust | 2–4 weeks | CRITICAL |

### 📈 Growth Opportunities

**Geographic expansion** (3 phases):
- Phase 1: Convert 10 treaty-only countries to incentive-covered (JP, IN, CN, MX, BR, SG, IL, AR, CL, UY)
- Phase 2: Add 10 high-volume markets (US, TH, PH, MY, ID, NG, EG, AE, SA, VN)
- Phase 3: Deepen existing coverage (regional variants, cultural test normalization)

---

## Core Problem: Data Decay

### Why This Matters

Government incentive programs **change constantly**:
- Tax rates rise/fall with annual budgets
- New VFX thresholds introduced
- Programs rename or consolidate
- Treaties get amended (rare but critical)
- Cultural test scoring rules evolve

### The Filmmaker's Worst-Case Scenario

1. Calculator recommends incentive offering 30% rebate
2. Filmmaker structures production around this
3. **Government just lowered it to 25%** (but the tool doesn't know yet)
4. Financing plan breaks; deal collapses
5. User abandonment: "This tool is unreliable"

### Current Manual Approach is Unsustainable

- 200+ records to re-verify
- Manual checks every 6–12 months
- You can't monitor 28 countries' policy announcements by yourself

---

## Solution: Four-Layer Sustainability System

### Layer 1: Automated Freshness Monitoring (Low Effort, High Value)
- Weekly scan of `last_verified` dates
- Flag records older than 12 months
- Admin dashboard: "Green (< 6 months)", "Yellow (6–12 months)", "Red (> 12 months)"
- **Result**: You know exactly which records need re-verification, not all of them

### Layer 2: Community-Driven Verification (Leverage Filmmakers)
- "Report issue" button on each scenario
- Filmmakers submit: "This rate is now 28%, not 30%" + source PDF
- You review, validate, merge
- Contributor gets credited in changelog
- **Result**: 50+ filmmakers become your eyes on the ground

### Layer 3: Automated Data Validation (Safety Net)
- Pre-commit validation: sources reachable, ranges sensible
- Run scenario tests on every data change
- Catch unintended side effects (e.g., changing TRIP rate affects 15 scenarios)
- **Result**: You can update data confidently, with test coverage

### Layer 4: Policy Change Monitoring (Proactive Detection)
- RSS feeds + web scrape: official government announcements
- Policy change detected → auto-alert you within 24 hours
- Example: "France raised TRIP to 35%, requires your review"
- **Result**: You're notified *before* filmmakers discover the discrepancy

---

## Recommended Roadmap (Next 16 Weeks)

### Sprint 1 (Weeks 1–2): Quick Wins
- **Issue 3**: Label scenarios ("Estimated incentive recovery") — 1–2 days
- **Issue 2**: Expand country list, keyboard nav — 3–5 days
- **Issue 1**: Fix spend calculation + budget breakdown UI — 5–10 days
- **Result**: Better UX, more accurate scenarios

### Sprint 2 (Weeks 3–4): LLM Adaptive Intake
- **Issue 5**: Gemini swap, PDF upload, adaptive questioning
- **Result**: Smarter intake, better data collection

### Sprint 3 (Weeks 5–6): Sustainability Phase A
- Layer 1: Source freshness tracking + admin dashboard
- Layer 3: Data validation framework + pre-commit hooks
- **Result**: You can safely update data; you see freshness status

### Sprint 4 (Weeks 7–8): First Expansion Wave
- Add incentive data for P1 countries (JP, IN, CN, MX)
- Scenario fixtures + tests
- **Result**: 4 new countries, proven expansion process

### Sprint 5 (Weeks 9–10): Sustainability Phase B & C
- Layer 2: Community update proposals + review queue
- Layer 4: Policy feed monitoring + auto-alerts
- **Result**: Crowdsourced data + proactive change detection

### Sprint 6+ (Ongoing): Scale
- Phase 2 expansion (10 more countries)
- Phase 3 deepening (regional variants, cultural test polish)
- Routine maintenance

---

## Key Metrics to Track

| Metric | Current | Target | Why |
|--------|---------|--------|-----|
| Avg data age (last_verified) | Likely 2–6 months | < 6 months avg | User trust |
| % records verified < 12 months | Likely 60–70% | > 90% | Detect stale data |
| Scenario test coverage | 38 tests | + 8/sprint | Prevent regression |
| Countries covered | 28 + treaty-only | 50+ (Phase 2 complete) | User reach |
| Community proposals/month | 0 | 10–20 | Engagement |
| Policy alerts/month | 0 | 3–5 | Proactiveness |

---

## Investment Required

### Personnel
- **You (filmmaker/tool owner)**: 1–2 hours/week for review, approval, policy monitoring
- **Engineers**: 1–2 months total implementation (sprint 1–5 above)
- **Community contributors**: Free (filmmakers propose updates as they discover issues)

### Infrastructure (Minimal)
- Existing: SQLite DB (self-hosted)
- Add: `source_alerts` table (~1KB)
- Add: `DataUpdateProposal` model (~2KB)
- Add: GitHub Actions (free) for monitoring
- **Total additional cost**: < $10/month (if you use cloud scheduler, add $0.20–$1/month)

### No Need For
- Complex event streaming (Kafka, Kinesis)
- Advanced databases (Elasticsearch, DynamoDB)
- ML/AI for data extraction (use Claude/Gemini API, already budgeted)

---

## Why This Approach Works

1. **Automated monitoring catches drift**: Humans forget; robots don't
2. **Community participation scales**: Filmmakers have direct stake in accuracy
3. **Validation prevents bad data**: Tests catch unintended consequences
4. **Proactive alerts keep you ahead**: You fix issues before users find them
5. **Low operational overhead**: No complex infrastructure, fits within existing DevOps

---

## Success Criteria (End of Q2 2026)

- [ ] All 4 outstanding issues are fixed
- [ ] Layer 1 (freshness monitoring) is live + visible in UI
- [ ] Layer 2 (community proposals) is live + getting 10+ proposals/month
- [ ] Layer 3 (validation) is live + all pre-commit hooks working
- [ ] Layer 4 (policy monitoring) is live + catching 3–5 policy changes/month
- [ ] Phase 1 expansion complete: 8/10 countries incentive-covered
- [ ] 80%+ of records verified in last 6 months
- [ ] Zero regressions (existing tests still pass)
- [ ] Filmmaker testimonial: "This tool helped me structure my financing, and I trust the numbers"

---

## One-Sentence Pitch to Your Users

> "We show you every co-production financing opportunity for your film — and every number is backed by an official source that we keep current for you."

---

## What Success Looks Like in 12 Months

1. **Filmmaker comes to the tool**: Gets a scenario showing €1.2M in incentives
2. **Filmmaker shares with co-producers**: "Every number links to an official government source"
3. **Filmmaker starts production**: Financing plan is solid; no surprises
4. **6 months later**: Filmmaker notices a policy change, uploads a PDF to report it
5. **You review & approve**: Database is automatically updated for the next filmmaker
6. **Tool improves every time someone uses it**: Network effect kicks in

---

## Next Step

1. **Pick Issue 3** (label the financing amount) — it's trivial and quick
2. **Get it shipped** — builds momentum
3. **Then tackle Issues 2 & 1** (UX improvements) — more visible wins
4. **Then start Layer 1** (freshness monitoring) — credibility + confidence
5. **Then expand to 4 new countries** (Phase 1) — proof it works at scale

**Estimated time to "fully functional + sustainable"**: 3–4 months if you have 1 engineer working on it part-time, or 6–8 weeks with full-time focus.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Filmmaker finds a stale record | Layer 1 flags it; Layer 2 collects fixes; you review |
| Data update breaks scenarios | Layer 3 validation catches it before production |
| Government policy changes | Layer 4 alerts you within 24 hours |
| Geographic expansion introduces errors | Tests + scenario fixtures prevent regression |
| Community spams proposals | Rate limiting + validation filters noise |
| You get overwhelmed by updates | Triage: green/yellow/red freshness guide priorities |

---

## Conclusion

The CoPro Calculator is **genuinely valuable** — it solves a real problem for filmmakers. The main challenge is keeping the data current as government policies evolve.

The four-layer system above turns that challenge into an **asset**: the tool gets *better* over time as your community discovers and contributes corrections, and automated monitors catch policy changes proactively.

**You're not building a one-off tool. You're building a living, community-maintained resource.**

---

## For Immediate Action

```bash
# Week 1: Issues 3, 2, 1 (Quick wins)
cd frontend/src/components
# - Add label to ScenarioList.tsx (30 min)
# - Fix ProjectForm.tsx country nav + expand country list (4 hours)
# - Update rule_engine.py spend calculation (2 hours)

# Week 2: Testing
python -m pytest backend/tests/
# - All existing tests pass
# - New scenario fixtures for budget breakdown

# Week 3: Deploy
# - Merge Issues 1–3
# - Test live with 3–5 filmmakers
# - Get feedback

# Week 4: Layer 1
# - Add source_alerts table
# - Implement freshness_checker.py
# - Add admin dashboard view
```

**Status**: Ready to start. Pick the first task.
