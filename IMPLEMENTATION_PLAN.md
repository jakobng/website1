# CoPro Calculator — Implementation Plan

## Context

The CoPro Calculator takes film project details and returns ranked co-production financing scenarios. Four issues need addressing: an inaccurate spend calculation, poor country selection UX, unclear result labeling, and the need for a robust LLM-powered adaptive intake flow using Gemini. (Issue 4 — suggestions improvement — skipped per user request.)

---

## Issue 1: Fix Qualifying Spend Calculation

**Problem**: `qualifying_spend = budget × shoot_%` assumes 100% of budget is location-dependent. In reality, shooting is ~40% of budget.

**Approach**: Introduce a budget breakdown model with sensible defaults, hidden behind an expandable UI.

### Default Budget Breakdown
- **Shooting**: 40% of total budget, divided equally across shoot locations
- **Post-production**: 35% of total budget, assignable to a specific country (or left blank to keep options open)
- **Other** (R&D, legal, contingency, above-the-line): 25% — not location-dependent, excluded from qualifying spend

### Backend Changes

**`backend/app/schemas.py`** — Add to `ProjectInput`:
```python
shooting_spend_fraction: float = 0.40
post_production_spend_fraction: float = 0.35
post_production_country: Optional[str] = None  # ISO code or None = flexible
```

**`backend/app/rule_engine.py`** — Change fallback spend calculation (lines 244-247):
- Old: `budget × shoot_pct / 100`
- New: `budget × shooting_spend_fraction × (shoot_pct / total_shoot_pct)` for shooting spend in that country
- Plus: if `post_production_country` matches this country, add `budget × post_production_spend_fraction`
- If `post_production_country` is None, post spend is NOT auto-assigned (keeps options open per user preference)
- Update `spend_basis` string and `CalculationStep` formula accordingly
- Explicit `spend_allocations` still override everything (existing behavior preserved)

**`backend/app/scenario_generator.py`** — Propagate same formula into `_build_suggestions` (lines 398, 445).

### Frontend Changes

**`frontend/src/types.ts`** — Add fields to `ProjectInput` interface.

**`frontend/src/App.tsx`** — Add defaults to `DEFAULT_PROJECT`.

**`frontend/src/components/ProjectForm.tsx`** — Add collapsible "Budget breakdown" section:
- Collapsed by default: shows one line like "Shooting 40% / Post 35% / Other 25%"
- Expanded: sliders or number inputs for shooting % and post %, auto-calculates "other"
- Post-production country selector (optional, can leave blank)
- Per-country spend override inputs (mirrors shoot_locations list but with currency amounts)

---

## Issue 2: Fix Country Selection UX

**Problem**: No keyboard navigation, only ~95 countries, `startsWith` filter only.

### Backend Changes

**`backend/app/countries.py`** — Expand `_COUNTRIES` to full ISO 3166-1 (~249 entries). Add all missing countries: DR Congo, Ethiopia, Ghana, Senegal, Cameroon, Fiji, Papua New Guinea, Kazakhstan, Barbados, Trinidad & Tobago, etc.

### Frontend Changes

**`frontend/src/components/ProjectForm.tsx`** — Both `CountryInput` and `MultiCountryInput`:

1. **Substring matching**: Change `.startsWith(query)` to `.includes(query)` (lines 390, 451)
2. **Keyboard navigation**: Add `highlightIndex` state + `onKeyDown` handler:
   - ArrowDown/ArrowUp: move highlight through suggestions
   - Enter: select highlighted suggestion
   - Escape: close dropdown
3. **Visual highlight**: Apply `bg-indigo-50` to the active suggestion item
4. **Scroll into view**: Auto-scroll dropdown to keep highlighted item visible

---

## Issue 3: Label the Big Number

**Problem**: The headline financing amount per scenario has no label explaining what it represents.

### Frontend Changes

**`frontend/src/components/ScenarioList.tsx`** — In `ScenarioCard` (lines 89-97):
- Add label above the amount: `"Estimated incentive recovery"` in small uppercase text
- Add tooltip on the percentage badge explaining it's the estimated % of budget recoverable through tax credits and rebates

---

## ~~Issue 4: Improve Suggestions~~ — SKIPPED

---

## Issue 5: LLM Adaptive Question Flow (Gemini 3.0 Flash)

**The big feature.** Replace Claude intake with Gemini-powered adaptive flow supporting PDF uploads and scenario-aware questioning.

### Phase 1: Gemini SDK Swap

**`backend/.env`** — Add `GEMINI_API_KEY=...`

**`backend/app/llm_intake.py`** — Rewrite:
- Replace `anthropic` SDK with `google-genai` SDK
- Model: `gemini-3.0-flash`
- Use `client.models.generate_content()` with `response_mime_type="application/json"`
- Keep same session management pattern (`_sessions` dict)
- Keep same response shape (`reply`, `project_draft`, `completeness_score`, `is_ready`)

### Phase 2: PDF Upload

**`backend/app/routes.py`** — New endpoint `POST /api/intake/upload`:
- Accepts `multipart/form-data` with PDF file + `session_id`
- Sends raw PDF bytes to Gemini via `types.Part.from_bytes(data=content, mime_type="application/pdf")`
- Returns same `IntakeResponse` shape

**`frontend/src/components/IntakeChat.tsx`** — Add upload button:
- Paperclip/upload icon next to text input
- Accepts `.pdf` files
- POSTs as FormData, shows progress
- Also supports plain text paste (textarea for synopsis/treatment text)

### Phase 3: Adaptive Questioning

**`backend/app/llm_intake.py`** — Two-phase questioning:

**Phase A — Basic extraction** (existing flow): title, format, budget, shoot locations, nationalities. Until `completeness_score > 0.5`.

**Phase B — Scenario-aware follow-up**: Once basic info is gathered:
1. Run preliminary `generate_scenarios()` against the current draft
2. Identify near-misses (incentives close to qualifying)
3. Build an `ADAPTIVE_CONTEXT` addition to the system prompt:
   ```
   Based on preliminary analysis, these incentives are close to qualifying:
   - [UK BFI Fund]: needs cultural test info — ask about British cultural content, crew nationality
   - [France TRIP]: needs spend breakdown — ask about French spend proportion
   Ask ONLY about the relevant requirements. Don't ask every project about every test.
   ```
4. Gemini then asks targeted questions naturally in the conversation
5. Each response re-runs preliminary analysis, updating which questions are relevant

**`backend/app/routes.py`** — Pass `db: Session` to `send_message` so it can run preliminary scenarios.

### Phase 4: Side Panel (Transparency)

**`frontend/src/components/IntakeChat.tsx`** — Add side panel showing:
- "What I'm investigating" — list of incentives being explored
- Why specific questions are being asked
- Preliminary scenario preview (updates as conversation progresses)
- Completeness indicator per section (basic info, cultural tests, spend details)

---

## Implementation Order

1. **Issue 3** — Label the big number (trivial)
2. **Issue 2** — Country selection UX (standalone)
3. **Issue 1** — Spend calculation fix + budget breakdown UI
4. **Issue 5** — Gemini adaptive flow (largest, 4 phases)

## Key Files to Modify

| File | Issues |
|------|--------|
| `backend/app/schemas.py` | 1 |
| `backend/app/rule_engine.py` | 1 |
| `backend/app/scenario_generator.py` | 1 |
| `backend/app/countries.py` | 2 |
| `backend/app/llm_intake.py` | 5 (rewrite) |
| `backend/app/routes.py` | 5 |
| `frontend/src/types.ts` | 1, 5 |
| `frontend/src/App.tsx` | 1 |
| `frontend/src/components/ProjectForm.tsx` | 1, 2 |
| `frontend/src/components/ScenarioList.tsx` | 3 |
| `frontend/src/components/IntakeChat.tsx` | 5 |

## Verification

- **Issue 1**: Enter a €3.5M budget with 50% shoot in France → qualifying spend should be ~€700K (40% × 50%) not €1.75M. Expand budget breakdown, adjust fractions, verify recalculation.
- **Issue 2**: Type "cong" in country field → DR Congo should appear. Arrow down to select, press Enter. Verify keyboard works.
- **Issue 3**: Visual check — each scenario card should say "Estimated incentive recovery" above the amount.
- **Issue 5**: Start guided interview → upload a treatment PDF → verify extraction. Continue chatting → verify adaptive questions appear for near-miss incentives. Check side panel shows investigation context.
