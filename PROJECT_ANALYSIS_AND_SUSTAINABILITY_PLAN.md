# CoPro Calculator: Project Analysis & Sustainability System

**Date**: 2026-03-26
**Purpose**: Comprehensive review of the CoPro Calculator project, user needs, outstanding implementation work, and a system design for maintaining reliability and currency without constant manual effort.

---

## Part 1: User Perspective — How Filmmakers Use This Tool

### The Filmmaker's Journey

A filmmaker (your user) comes to this tool with:
- **A film concept** (budget, format, shoot locations, nationalities)
- **A question**: "Who should I co-produce with to access financing incentives and treaties?"

**What the tool tells them:**
1. Which countries' incentive programs they *could* qualify for
2. Which bilateral/multilateral treaties could structure the coproduction
3. How much financing each scenario might recover (tax credits, rebates, grants)
4. What specific eligibility requirements they'd need to meet (cultural tests, spend breakdowns, crew nationality, etc.)
5. **The sources and calculation steps** behind each recommendation (for credibility with funders/co-producers)

### To Become Eligible (Filmmaker's Decisions)

The tool helps filmmakers understand **the knobs they can turn**:

1. **Budget allocation**: Where to place post-production, what percentage to shoot in each country
2. **Creative team composition**: Director, producer, and key crew nationalities (must meet treaty requirements)
3. **Production structure**: Lead vs. minority coproducer roles, which country is "prime" (affects which treaties apply)
4. **Spend timing and sequence**: Can influence which incentives apply (development, production, post-production)
5. **Cultural/narrative choices**: Does the project pass cultural tests (UK BFI, Australian content tests, etc.)?
6. **Flexibility trade-offs**: How much can they deviate from original concept to unlock a better incentive scenario?

### Key Insight: Data Freshness is Everything

A filmmaker will **abandon this tool instantly** if:
- A recommended incentive was **cancelled 6 months ago**
- A treaty **requirement changed** and they don't learn until they apply
- The calculator says "30% rebate" but the government now offers **25%** — or **40%** if you hit a new VFX threshold

**This is why the third part of your request (maintaining reliability without constant manual work) is so critical.**

---

## Part 2: Outstanding Implementation Work

### Tracked Issues (from IMPLEMENTATION_PLAN.md)

| Priority | Issue | Impact | Status |
|----------|-------|--------|--------|
| 🔴 HIGH | Issue 1: Fix qualifying spend calculation | Scenarios return inflated numbers (wrong budget split) | Design ready, needs implementation |
| 🟠 MED | Issue 2: Country selection UX | Hard to find countries beyond top 95; no keyboard nav | Design ready, needs implementation |
| 🟠 MED | Issue 3: Label the financing amount | Users don't understand what the big number represents | Design ready, trivial implementation |
| 🔴 HIGH | Issue 5: LLM adaptive intake (Gemini swap) | Current Claude intake doesn't ask scenario-aware questions; no PDF support | Partial (Claude works, want Gemini) |

**Order to tackle** (per plan): Issue 3 → Issue 2 → Issue 1 → Issue 5

### Geographic Coverage Backlog (from expansion_backlog.md)

**Phase 1 (P1)**: Convert 10 treaty-only countries to incentive-covered
- Japan, India, China, Mexico, Brazil, Singapore, Israel, Argentina, Chile, Uruguay
- Exit criteria: 8/10 become incentive_covered + scenario tests

**Phase 2 (P2)**: Add 10 high-volume no-coverage markets
- US (federal + state model), Thailand, Philippines, Malaysia, Indonesia, Nigeria, Egypt, UAE, Saudi Arabia, Vietnam
- Exit criteria: 7/10 covered + US 3-state stable + no regression

**Phase 3 (P3)**: Deepen existing coverage (regional variants, alternative programs, cultural test normalization)
- Target: FR, DE, GB, IT, ES, CA, AU, NL, BE + cultural-test countries

---

## Part 3: Sustainability System Design

### The Core Problem

Government incentive programs and treaties **change constantly**:
- Tax rates rise/fall with budgets
- New eligibility thresholds (esp. VFX, streaming, etc.)
- Programs cancel or rename
- Treaty amendments (rare but critical)
- Cultural test scoring rules evolve

**Manual re-verification is unsustainable** (every record checked by hand every 6–12 months).

### Proposed Three-Layer System

#### Layer 1: Automated Source Freshness & Health Monitoring

**What it does:**
- Every record in the database has a `last_verified` date (ISO string)
- Background job (weekly) flags records older than 12 months
- Monitors official government websites for policy announcements (RSS feeds, web scraping)
- Alerts: "FR TRIP rate change detected on CNC site" or "UK AVEC documentation updated"

**Implementation:**
```
backend/
  tasks/
    source_freshness_checker.py       # Weekly scan of last_verified dates
    policy_monitor.py                 # RSS/web scrape official sources
    alert_notifier.py                 # Slack/email alerts on stale/changed data
  data/
    source_registry.json              # { country: [urls to monitor], check_interval: "weekly" }
```

**Deploy as:**
- Local `cron` job or cloud scheduler (Cloud Tasks, GitHub Actions, Lambda)
- Logs to database (`source_alerts` table) — visible in admin UI

**Outcome:**
- You get a **data freshness dashboard**: which records are green (verified < 6 months) vs. yellow (6–12 months) vs. red (>12 months)
- Alerts tell you *which* records to manually re-verify (not all 200+)

---

#### Layer 2: Community-Driven Verification Workflow

**What it does:**
Turns the community into co-maintainers. Production companies, co-production consultants, and film commissions can propose updates.

**UX Flow:**
1. Filmmaker sees a scenario, notices the incentive rate looks outdated
2. Clicks "Report issue" or "Suggest update" on that incentive card
3. Opens a form: "Which source contradicts this?" + PDF upload + notes
4. Submission creates an **Issue** in a GitHub repo (or admin queue in the app)
5. You (or a domain expert) review, verify the new source, merge the change
6. Verification date resets; contributor gets credited in a changelog

**Implementation:**
```
backend/
  models/
    add DataUpdateProposal(
      user_email, incentive_id,
      field_name, old_value, new_value,
      proposed_source_url, proposed_source_description,
      pdf_attachment_url,
      status: "pending" | "approved" | "rejected",
      created_at, reviewed_at, reviewed_by
    )
  routes/
    POST /api/data/propose-update  (public, rate-limited)
    POST /api/admin/review-update  (auth-protected)

frontend/
  components/
    DataUpdateForm.tsx               # Modal on scenario/incentive card
    AdminReviewQueue.tsx             # Dashboard for reviewing proposals
```

**Deploy as:**
- Lightweight form in the UI (uses Claude to validate/parse proposals)
- GitHub integration: approved proposals → auto-PR in the data repo
- Or simple admin dashboard in the app (lower overhead)

**Outcome:**
- You're no longer the single point of truth
- Filmmakers and production professionals contribute real-world updates
- Data freshness is **crowdsourced**

---

#### Layer 3: Automated Data Validation & Testing

**What it does:**
Every time data is seeded or updated, it's automatically validated:
- Fields match schema (rebate % between 0–100, dates are ISO, etc.)
- Sources are reachable (HTTP HEAD request to `source_url`)
- Scenarios remain consistent (e.g., if you change a rate, do any scenarios break?)
- Cultural test scores are internally consistent

**Implementation:**
```
backend/
  scripts/
    validate_data_integrity.py      # Runs on `seed_data.py` completion
      - check all source URLs are reachable (HEAD request, cache results)
      - validate all numeric fields are in sane ranges
      - check date formats
      - run existing scenario tests after seed
  tests/
    test_scenario_stability.py      # "Golden snapshot" tests
      - Define fixture: "French €3.5M fiction, 50% shoot in FR"
      - Expected output: "TRIP ~€700K, Domestic Credit ~€525K, not both"
      - If you update TRIP rate, test fails with exact delta
```

**Deploy as:**
- Pre-commit hook: `validate_data_integrity.py` runs before merging any seed_data.py changes
- CI/CD: all 38 existing scenario tests run on every data change
- Automated snapshot diffs: "Changing TRIP rate from 30% to 28% would affect X scenarios by Y%"

**Outcome:**
- You can update data *safely* — tests catch breakage before production
- Community proposals are validated before review (no malformed submissions)

---

#### Layer 4: Policy Change Registry & Automated Ingestion

**What it does:**
Maintains a living registry of *known* policy change schedules and real-time feeds.

**Sources to monitor:**
- **France**: CNC budget announcements (typically December)
- **UK**: BFI/DCMS policy changes (published to gov.uk RSS)
- **EU**: European Audiovisual Observatory's treaty amendments
- **Canada**: Telefilm and provincial tax credit updates
- **Australia**: Screen Australia incentive reviews (quarterly)
- **Government RSS feeds**: Many countries publish policy changes via RSS
- **Industry newsletters**: FilmL.A., MEDIA Programme, etc.

**Implementation:**
```
backend/
  data/
    policy_calendars.json           # Known announcement dates per country
    policy_feeds.json               # { country: [rss_urls, scrape_selectors] }

  tasks/
    policy_feed_monitor.py
      - Hourly: fetch all registered feeds
      - Parse announcements (use Claude to summarize policy changes)
      - Flag new changes for manual review
      - Auto-create GitHub issues with policy summary + source link

    # Example alert:
    # Title: "⚠️ AU: New VFX threshold in QAPE introduced (Screen Australia 2026-Q2)"
    # Body: "Policy change detected in Screen Australia announcement.
    #        New Rule: >$500k VFX spend triggers 40% (was 38%). Requires review."
    #        [Action: Review] [Snooze 1 week] [Mark false alarm]
```

**Deploy as:**
- Scheduled job (AWS Lambda, Cloud Tasks, or cron)
- Logs to database (`policy_announcements` table, visible in admin)
- Integrates with Layer 2 (proposed updates)

**Outcome:**
- You're **notified immediately** when a government announces a policy change
- Not waiting for a filmmaker to complain — you're proactive

---

### Integration: The Full Feedback Loop

```
┌─────────────────────────────────────────────────────────┐
│          Government Policy Change Announced             │
│           (e.g., France raises TRIP to 35%)             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │   Layer 4: Policy Feed Monitor  │  (automated)
        │   - Detects announcement       │
        │   - Creates GitHub issue       │
        └────────────────┬───────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │   Layer 2: Community Review     │  (you + contributors)
        │   - Filmmaker proposes update  │  (or you file it yourself)
        │   - Attaches official PDF      │
        │   - Submits for review         │
        └────────────────┬───────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │   Layer 3: Automated Validation        │  (pre-commit)
        │   - Validates source URL reachable   │
        │   - Runs scenario tests               │
        │   - Checks for unintended side effects│
        └────────────────┬──────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │   Merge to seed_data.py                │
        │   Run: python seed_data.py             │
        │   Update `last_verified` to today      │
        └────────────────┬──────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │   Layer 1: Freshness Dashboard         │  (ongoing)
        │   - Record now marked "verified 2026-03-26" │
        │   - No longer flagged as stale        │
        └────────────────────────────────────────┘
```

---

### Implementation Roadmap

**Phase A: Observability (Weeks 1–2)**
- [ ] Add `source_alerts` table (tracks stale records)
- [ ] Implement `source_freshness_checker.py` (weekly scan)
- [ ] Add admin dashboard: freshness status by country
- [ ] Set up GitHub Actions to run validator pre-merge

**Phase B: Crowdsourcing (Weeks 3–4)**
- [ ] Add `DataUpdateProposal` model
- [ ] Build "Report issue" modal in UI
- [ ] Implement admin review queue
- [ ] GitHub integration (auto-PR creation on approval)

**Phase C: Policy Monitoring (Weeks 5–6)**
- [ ] Create `policy_calendars.json` (known announcement dates)
- [ ] Implement `policy_feed_monitor.py` (RSS + web scrape)
- [ ] Set up policy alert email/Slack notifications
- [ ] Add admin dashboard: policy changes by country

**Phase D: Refinement & Scale (Weeks 7+)**
- [ ] Tune monitoring rules (reduce false positives)
- [ ] Expand registry to cover more countries' feeds
- [ ] Consider paid data sources (if budget allows)
- [ ] Quarterly audits by domain experts (film commissions, co-production consultants)

---

### Deployment Infrastructure

**Recommended stack** (minimal operational overhead):

| Component | Service | Cost | Notes |
|-----------|---------|------|-------|
| Source monitoring | GitHub Actions (free) or AWS Lambda | Free–$0.20/month | 1–2 scheduled jobs |
| Policy feeds | GitHub Actions (free) | Free | Hourly feed check |
| Data storage | SQLite (self-hosted) or RDS | Free–$30/month | Existing DB, add alerts table |
| Admin UI | Streamlit (Python) or simple FastAPI admin | Free–$50/month | Runs in existing backend |
| Notifications | Slack webhook (free) + email | Free | Alert routing |
| Analytics | DataStudio (free) + PostgreSQL | Free | Track data freshness trends |

**No need for:** Kafka, Elasticsearch, complex event systems. Start simple, scale if needed.

---

## Part 4: Integrated Roadmap (Next 4 Months)

### Sprint 1 (Weeks 1–2): Fix Outstanding Issues
- **Issue 3**: Label scenarios ("Estimated incentive recovery") — trivial frontend change
- **Issue 2**: Expand country list (249 countries) + keyboard navigation
- **Issue 1**: Fix spend calculation (budget breakdown UI)

### Sprint 2 (Weeks 3–4): LLM Adaptive Intake
- **Issue 5**: Swap Claude for Gemini (Phase 1), add PDF upload (Phase 2), adaptive questions (Phase 3)

### Sprint 3 (Weeks 5–6): Data Sustainability (Phase A + B)
- Source freshness tracking
- Community update proposals
- Admin review dashboard

### Sprint 4 (Weeks 7–8): Phase 1 Expansion
- Add incentive data for P1 countries (JP, IN, CN, MX)
- Scenario fixtures + tests

### Sprint 5 (Weeks 9–10): Policy Monitoring (Phase C)
- Policy feed monitoring
- Automated alerts
- Calendar of known changes

### Sprint 6+ (Ongoing)
- Phase 2 expansion (10 no-coverage markets)
- Phase D refinement (tune monitoring, user feedback)

---

## Part 5: Why This Matters for Your Filmmaker Users

Once these systems are in place:

1. **Trustworthiness**: "Last verified 2026-03-20" on every number. Stale data is flagged and gets re-checked.
2. **Responsiveness**: Policy changes trigger alerts within 24 hours, not weeks.
3. **Community**: Filmmakers and production professionals contribute real-world data, making the tool better for everyone.
4. **Sustainability**: You're not manually re-verifying 200+ records every 6 months. The system flags *only* the stale ones.
5. **Global reach**: Expansion happens methodically, with every new country backed by tests and source verification.

**Bottom line**: The tool becomes **a living, community-maintained resource** instead of slowly decaying.

---

## Implementation Checklist

### Before You Start Any Code:
- [ ] Get a GitHub Actions workflow running (free test runner)
- [ ] Identify 3–5 government RSS feeds or policy announcement sources (France, UK, Canada, Australia)
- [ ] Design the `source_alerts` table schema (with freshness thresholds)
- [ ] Create a simple admin UI mockup for freshness dashboard

### Then, in order:
1. Fix Issues 3, 2, 1 (UI improvements — highest immediate value)
2. Implement Layer 1 (freshness monitoring — low-effort, high-visibility win)
3. Implement Layer 2 (community proposals — unlock crowdsourcing)
4. Expand to Phase 1 countries (JP, IN, CN, MX with tests)
5. Implement Layer 3 & 4 (automated validation + policy feeds — mature the system)

---

## Conclusion

The CoPro Calculator is **well-designed and comprehensive**. Its main risk is data decay — not because you're lazy, but because government policy changes are frequent and hard to track at scale.

The four-layer system above turns that risk into a **feature**: the tool becomes *more accurate over time* as your community discovers and contributes corrections, and automated monitors catch policy changes in real-time.

**Next step**: Pick the easiest outstanding issue (Issue 3) and ship it. That builds momentum. Then layer in the freshness tracking (Layer 1) for quick credibility wins. The rest follows naturally.

