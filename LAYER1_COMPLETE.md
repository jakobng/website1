# Layer 1: Source Freshness Monitoring — IMPLEMENTED ✅

**Status**: Live and working. Freshness data being tracked and exposed via API.

---

## What Was Built

### 1. Database Model (`backend/app/models.py`)
Added `SourceAlert` table to track record freshness:
```python
class SourceAlert(Base):
    id: int
    incentive_id: int (FK to Incentive)
    last_verified: str (ISO date from incentive)
    days_old: int (days since last verification)
    status: str ("green" <180d, "yellow" 180-365d, "red" >365d)
    checked_at: str (when we ran the check)
```

### 2. Alembic Migration (`backend/alembic/versions/20260326_03_add_source_alerts.py`)
Creates the `source_alerts` table with proper indexing on `incentive_id`.

### 3. Freshness Checker Script (`backend/scripts/check_source_freshness.py`)
Weekly job that:
- Scans all 242 incentive records
- Parses `last_verified` date (YYYY-MM format)
- Computes days old
- Assigns color status (green/yellow/red)
- Stores results in `source_alerts` table
- Prints summary to console

**Run it:**
```bash
python backend/scripts/check_source_freshness.py
```

**Output example:**
```
[OK] Freshness check complete (2026-03-27)
   Total records scanned: 242
   [GREEN] Green (< 6 months):    134 (55%)
   [YELLOW] Yellow (6-12 months): 108
   [RED] Red (> 12 months):       0

[SUCCESS] All records current!
```

### 4. API Endpoint (`backend/app/routes.py`)
`GET /api/admin/freshness-status`

**Response:**
```json
{
  "total_incentives": 242,
  "green": 134,
  "yellow": 108,
  "red": 0,
  "green_percent": 55,
  "by_country": {
    "FR": {"country_name": "France", "green": 0, "yellow": 12, "red": 0, "total": 12},
    "DE": {"country_name": "Germany", "green": 0, "yellow": 10, "red": 0, "total": 10},
    ...
  },
  "last_checked": "2026-03-27"
}
```

### 5. Frontend Component (`frontend/src/components/FreshnessIndicator.tsx`)
React component showing:
- **Color-coded progress bar**: Green/Yellow/Red split
- **Status text**: "55% of records verified in last 6 months"
- **Breakdown by country**: Expandable detail view
- **Alert**: Shows warning if >25% red or <75% green

**Integrated into**: `frontend/src/App.tsx` (top of results section)

---

## Current Data Status

| Metric | Value |
|--------|-------|
| Total incentives | 242 |
| Green (verified < 6 months) | 134 (55%) |
| Yellow (6-12 months old) | 108 (45%) |
| Red (> 12 months old) | 0 (0%) |
| Last check | 2026-03-27 |

### By Major Country
- **France**: 12 total, 0 green, 12 yellow (all 6-12 months old)
- **Germany**: 10 total, 0 green, 10 yellow
- **Spain**: 11 total, 0 green, 11 yellow
- **Italy**: 14 total, 0 green, 14 yellow
- **US**: 5 total, **all green** (verified recently)
- **Canada**: 7 total, 5 green + 2 yellow
- **Australia**: 2 total, 0 green, 2 yellow
- **Brazil**: 3 total, all green
- **Mexico**: 3 total, all green
- **Japan**: 1 total, green

---

## Next Steps

### To keep data fresh:

1. **Schedule weekly scan**:
   - GitHub Actions (recommended):
     ```yaml
     # .github/workflows/freshness-check.yml
     name: Check Source Freshness
     on:
       schedule:
         - cron: '0 2 * * 0'  # Sunday 2am UTC
     jobs:
       check:
         runs-on: ubuntu-latest
         steps:
           - uses: actions/checkout@v3
           - name: Run freshness check
             run: |
               cd backend
               python scripts/check_source_freshness.py
     ```
   - Or local cron:
     ```bash
     0 2 * * 0 cd /path/to/backend && python scripts/check_source_freshness.py
     ```

2. **Monitor the dashboard**:
   - Visit `http://localhost:5173` (if running locally)
   - Freshness indicator appears at top of results
   - Expand "Details" to see by-country breakdown

3. **Re-verify yellow/red records**:
   - Click on a scenario to see which incentive is aging
   - Use the source link to check current government requirements
   - Update `seed_data.py` with new values
   - Reset `last_verified` to today (format: YYYY-MM)
   - Run `python backend/scripts/check_source_freshness.py` again

4. **Next: Layer 2 (Community Proposals)**:
   - Add "Report issue" button on scenarios
   - Filmmakers can propose updates
   - You approve via admin interface
   - Approved updates auto-reset `last_verified`

---

## Files Modified

| File | Changes |
|------|---------|
| `backend/app/models.py` | Added `SourceAlert` model |
| `backend/alembic/versions/20260326_03_add_source_alerts.py` | Migration to create table |
| `backend/scripts/check_source_freshness.py` | New script to compute freshness |
| `backend/app/routes.py` | Added `/api/admin/freshness-status` endpoint |
| `frontend/src/components/FreshnessIndicator.tsx` | New React component |
| `frontend/src/App.tsx` | Integrated FreshnessIndicator |

---

## How It Improves User Experience

**Before Layer 1:**
- Filmmakers had no way to know if data was current
- Stale records silently decayed
- No visibility into what was verified when

**After Layer 1:**
- Dashboard shows "55% verified in last 6 months"
- Color coding: green (trust it), yellow (might be outdated), red (definitely re-verify)
- By-country breakdown shows which countries need updates
- Incentive sources always show `last_verified` date
- Builds confidence: "This data is actively maintained"

---

## Testing

All components tested:
- ✅ Database migration creates table
- ✅ Script scans 242 records in ~2 seconds
- ✅ API endpoint returns full JSON payload
- ✅ Frontend component renders correctly
- ✅ Color coding works (green for recent, yellow for aging)
- ✅ By-country breakdown accurate

---

## Ready for Layer 2?

Yes! Now that you have visibility into freshness, the next logical step is **community contributions**:

Layer 2 will let filmmakers propose updates when they find discrepancies:
1. Filmmaker sees an incentive rate that's outdated
2. Clicks "Report issue" button
3. Submits new value + official government source URL
4. You review and approve
5. `last_verified` resets to today
6. Data is fresh again

This turns your community into co-maintainers and dramatically improves data reliability.

See `SUSTAINABILITY_IMPLEMENTATION_START.md` for Layer 2 walkthrough.
