# Sustainability System Implementation — Start Here

**Status**: All 4 major implementation issues (1-3, 5) are DONE. Focus is now on keeping data fresh.

---

## Layer 1: Source Freshness Monitoring (Weeks 1–2)

**Goal**: Visible dashboard showing which records are green (verified), yellow (aging), or red (stale).

### What to build

1. **Database table** `source_alerts`:
```sql
CREATE TABLE source_alerts (
  id INTEGER PRIMARY KEY,
  incentive_id INTEGER NOT NULL,
  last_verified TEXT,  -- ISO date string from incentive.last_verified
  days_old INTEGER,    -- Days since last_verified
  status TEXT,         -- "green" (<6 months), "yellow" (6-12), "red" (>12)
  checked_at TEXT,     -- When we last ran the check (ISO date)
  FOREIGN KEY(incentive_id) REFERENCES incentives(id)
);
```

2. **Script** `backend/scripts/check_source_freshness.py`:
```python
"""Weekly scan of incentive freshness."""
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import Incentive
from sqlalchemy import text

def check_freshness():
    db = SessionLocal()

    # Clear old alerts
    db.execute(text("DELETE FROM source_alerts"))

    today = datetime.now().date()

    for incentive in db.query(Incentive).all():
        last_verified = incentive.last_verified  # ISO date string like "2025-03"
        if not last_verified:
            status = "red"  # No verification date = red
            days_old = 999
        else:
            # Parse "2025-03" format (month precision)
            try:
                date = datetime.strptime(last_verified, "%Y-%m").date()
                days_old = (today - date).days
            except:
                status = "red"
                days_old = 999
                continue

            if days_old < 180:
                status = "green"  # < 6 months
            elif days_old < 365:
                status = "yellow"  # 6-12 months
            else:
                status = "red"  # > 12 months

        # Insert alert
        db.execute(text(
            "INSERT INTO source_alerts (incentive_id, last_verified, days_old, status, checked_at) "
            "VALUES (:id, :lv, :days, :status, :now)"
        ), {
            "id": incentive.id,
            "lv": last_verified,
            "days": days_old,
            "status": status,
            "now": today.isoformat(),
        })

    db.commit()
    db.close()
    print(f"Checked {len(list(db.query(Incentive)))} records")
```

3. **API endpoint** `backend/app/routes.py`:
```python
@router.get("/admin/freshness-status")
def freshness_status(db: Session = Depends(get_db)):
    """Return source freshness summary."""
    from sqlalchemy import func

    alerts = db.query(SourceAlert).all()

    summary = {
        "total_incentives": db.query(Incentive).count(),
        "green": len([a for a in alerts if a.status == "green"]),
        "yellow": len([a for a in alerts if a.status == "yellow"]),
        "red": len([a for a in alerts if a.status == "red"]),
        "by_country": {},
    }

    # Group by country
    for alert in alerts:
        inc = db.query(Incentive).get(alert.incentive_id)
        cc = inc.country_code
        if cc not in summary["by_country"]:
            summary["by_country"][cc] = {"green": 0, "yellow": 0, "red": 0}
        summary["by_country"][cc][alert.status] += 1

    return summary
```

4. **Frontend** `frontend/src/components/FreshnessIndicator.tsx` (new):
{% raw %}
```tsx
import { useState, useEffect } from 'react'

export function FreshnessIndicator() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/admin/freshness-status')
      .then(r => r.json())
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return null
  if (!status) return null

  const total = status.green + status.yellow + status.red
  const greenPct = Math.round((status.green / total) * 100)

  return (
    <div className="p-4 rounded-lg border border-slate-200 bg-slate-50">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-slate-800">Data Freshness</h3>
        <span className="text-xs text-slate-500">{greenPct}% current</span>
      </div>
      <div className="flex h-2 gap-1 rounded-full overflow-hidden bg-slate-200">
        <div
          className="bg-emerald-400"
          style={{ width: `${(status.green / total) * 100}%` }}
        />
        <div
          className="bg-amber-400"
          style={{ width: `${(status.yellow / total) * 100}%` }}
        />
        <div
          className="bg-red-400"
          style={{ width: `${(status.red / total) * 100}%` }}
        />
      </div>
      <div className="mt-2 text-xs text-slate-500">
        {status.green} current, {status.yellow} aging, {status.red} stale
      </div>
    </div>
  )
}
```
{% endraw %}

5. **Cron job** (add to `backend/.env` or GitHub Actions):
```bash
# Run weekly on Sunday at 2am UTC
0 2 * * 0 cd /path/to/backend && python scripts/check_source_freshness.py
```

### Expected result
- Dashboard shows green/yellow/red indicator
- Users see at a glance: "80% of our data is verified in last 6 months"
- Red-flagged records can be prioritized for re-verification

---

## Layer 2: Community Update Proposals (Weeks 3–4)

**Goal**: Filmmakers/consultants can report stale/incorrect data; you review and approve.

### Quick implementation

1. **Database table** `data_update_proposals`:
```sql
CREATE TABLE data_update_proposals (
  id INTEGER PRIMARY KEY,
  incentive_id INTEGER,
  field_name TEXT,  -- "rebate_percent", "min_qualifying_spend", etc.
  old_value TEXT,
  new_value TEXT,
  proposed_source_url TEXT,
  proposed_source_description TEXT,
  proposer_email TEXT,
  created_at TEXT,
  status TEXT,  -- "pending", "approved", "rejected"
  reviewed_by TEXT,
  reviewed_at TEXT,
  notes TEXT,
  FOREIGN KEY(incentive_id) REFERENCES incentives(id)
);
```

2. **API endpoint** `POST /api/data/propose-update`:
```python
class DataUpdateRequest(BaseModel):
    incentive_id: int
    field_name: str
    new_value: str
    proposed_source_url: str
    proposed_source_description: str
    proposer_email: str  # For follow-up

@router.post("/data/propose-update")
def propose_update(req: DataUpdateRequest, db: Session = Depends(get_db)):
    """Submit a data correction proposal."""
    prop = DataUpdateProposal(
        incentive_id=req.incentive_id,
        field_name=req.field_name,
        old_value="...",  # Fetch from DB
        new_value=req.new_value,
        proposed_source_url=req.proposed_source_url,
        proposed_source_description=req.proposed_source_description,
        proposer_email=req.proposer_email,
        created_at=datetime.now().isoformat(),
        status="pending",
    )
    db.add(prop)
    db.commit()
    return {"id": prop.id, "status": "pending"}
```

3. **Admin review queue** (simple dashboard):
- List pending proposals
- Show: old value, new value, proposed source link
- Actions: Approve (auto-updates seed_data.py comment + resets last_verified) / Reject with notes

4. **Frontend**: Add "Report issue" button on each scenario card

### Expected result
- Filmmaker sees outdated data, clicks "Report"
- You get notification
- You click "Approve" → `last_verified` resets to today
- Data is now fresh without manual audit

---

## Phase 1 Geographic Expansion: JP, IN, CN, MX (Weeks 5–8)

**Goal**: Turn 4 treaty-only countries into incentive-covered countries. High-ROI since treaties already exist.

### For each country (example: Japan):

1. **Add primary incentive to `backend/seed_data.py`**:
```python
inc(
    name="Japan—Film Incentive Programme (FIP)",
    country_code="JP",
    incentive_type="cash_rebate",
    rebate_percent=30.0,  # Verify from METI/JETRO
    max_cap_amount=2_000_000_000,  # In JPY, convert to EUR thresholds
    min_qualifying_spend=100_000_000,  # Min ¥100M spend
    min_spend_currency="JPY",
    eligible_formats=["feature_fiction", "documentary", "animation"],
    eligible_stages=["production", "post"],
    local_producer_required=True,
    source_url="https://www.jetro.go.jp/...",
    source_description="JETRO—Film Incentive Programme",
    clause_reference="METI Subsidy Guidelines 2025",
    notes="30% rebate on eligible Japanese production spend. Requires local co-producer approval.",
    last_verified="2026-03",
),
```

2. **Add document/annotations** (sources for each field):
```python
doc = Document(
    document_type="policy_guideline",
    country_code="JP",
    title="JETRO Film Incentive Programme Guidelines",
    source_url="https://...",
    effective_from="2025-01-01",
    notes="Official guidelines for FIP eligibility and rebate calculation",
)
db.add(doc)

annotation = DocumentAnnotation(
    document_id=doc.id,
    incentive_id=inc_id,
    field_name="rebate_percent",
    field_value="30.0",
    clause_text="Art. 3.2: 30% rebate on verified production spend",
    page_reference="p. 5",
)
db.add(annotation)
```

3. **Add scenario tests** `backend/scenario_tests/scenarios_phase1/`:
```json
{
  "name": "JP_BASE: Japanese feature, Tokyo-based producer",
  "project": {
    "title": "Tokyo Noir",
    "format": "feature_fiction",
    "budget": 1_000_000_000,
    "budget_currency": "JPY",
    "shoot_locations": [{"country": "Japan", "percent": 100}],
    "director_nationalities": ["France"],
    "producer_nationalities": ["Japan"],
    "production_company_countries": ["Japan"]
  },
  "expected_eligible_incentives": ["Japan—Film Incentive Programme"],
  "expected_min_financing": 300_000_000
}
```

4. **Run tests**:
```bash
cd backend
python -m pytest tests/test_scenario_generator.py::test_jp_base -v
```

5. **Repeat for India, China, Mexico** (4 countries × 2 weeks = 8 weeks if done sequentially, 2 weeks if parallel)

### Expected result
- 4 new countries become incentive-covered
- Treaty pathways (FR-JP, UK-IN, etc.) now unlock financing scenarios
- Scenario tests prove correctness

---

## Execution checklist

### Week 1–2 (Layer 1)
- [ ] Add `source_alerts` table via Alembic migration
- [ ] Write `check_source_freshness.py` script
- [ ] Add `/api/admin/freshness-status` endpoint
- [ ] Build `FreshnessIndicator` component
- [ ] Set up weekly cron job (GitHub Actions or local)
- [ ] Test: Run script, verify dashboard shows green/yellow/red

### Week 3–4 (Layer 2)
- [ ] Add `data_update_proposals` table
- [ ] Implement `POST /api/data/propose-update` endpoint
- [ ] Build admin review UI (simple list + approve/reject buttons)
- [ ] Add "Report issue" button on scenario cards
- [ ] Email notification on new proposal (optional)
- [ ] Test: Submit proposal, approve, verify last_verified resets

### Week 5–8 (Phase 1 Expansion)
- [ ] JP: Add incentive record + source + tests (✓)
- [ ] IN: Add incentive record + source + tests (✓)
- [ ] CN: Add incentive record + source + tests (✓)
- [ ] MX: Add incentive record + source + tests (✓)
- [ ] Run full test suite: `pytest backend/tests/`
- [ ] Create snapshot report: coverage matrix (countries, incentives, coverage %)
- [ ] Test live: Try scenarios with new countries

---

## Success metrics

| Metric | Target | How to measure |
|--------|--------|-----------------|
| Data freshness (green %) | > 80% | Dashboard shows 80% green |
| Community proposals/month | 5–10 | Check `data_update_proposals` count |
| Phase 1 countries incentive-covered | 4/4 | Run tests for JP, IN, CN, MX |
| Regression tests pass | 100% | `pytest backend/tests/` all green |
| Geographic coverage | 38 → 42 countries | Count in `backend/reports/coverage_matrix.csv` |

---

## Tools & References

- **Database migrations**: Alembic (`backend/alembic/`)
- **Test fixtures**: `backend/scenario_tests/scenarios_phase1/`
- **Coverage report**: `backend/reports/build_coverage_matrix.py`
- **Incentive data**: `backend/seed_data.py` (authoritative source)

---

## Next: After Layer 1

Once Layer 1 is live, you'll see exactly which records need attention. That drives prioritization for Layer 2 (community proposals) and Phase 2 expansion (10 no-coverage markets).

**Start with Layer 1 this week. It's the quickest win and most visible to users.**
