#!/usr/bin/env python
"""
Check source freshness: scan all incentive records and flag stale ones.

Run this weekly (e.g., via cron or GitHub Actions) to keep freshness_status current.

Usage:
  python scripts/check_source_freshness.py
"""
import os
import sys
from datetime import datetime, timedelta

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from app.database import SessionLocal
from app.models import Incentive, SourceAlert
from sqlalchemy import text


def check_freshness():
    """Scan all incentives, compute freshness status, store in source_alerts."""
    db = SessionLocal()

    try:
        # Clear old alerts (will recompute)
        db.query(SourceAlert).delete()
        db.commit()

        today = datetime.now().date()
        total_checked = 0
        counts = {"green": 0, "yellow": 0, "red": 0}

        for incentive in db.query(Incentive).order_by(Incentive.country_code, Incentive.name).all():
            total_checked += 1
            last_verified = incentive.last_verified  # Format: "2025-03" (YYYY-MM)
            days_old = None
            status = "red"  # Default: stale if no verification date

            if last_verified:
                try:
                    # Parse "2025-03" format to date (treat as end of month)
                    # We'll use the first day of next month, then subtract 1 day
                    parts = last_verified.split("-")
                    if len(parts) == 2:
                        year, month = int(parts[0]), int(parts[1])
                        # Date is treated as "verified in this month" = end of month
                        if month == 12:
                            last_verified_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
                        else:
                            last_verified_date = datetime(year, month + 1, 1).date() - timedelta(days=1)

                        days_old = (today - last_verified_date).days

                        # Color coding
                        if days_old < 180:
                            status = "green"
                        elif days_old < 365:
                            status = "yellow"
                        else:
                            status = "red"
                    else:
                        # Invalid format, mark as red
                        status = "red"
                        days_old = None
                except Exception as e:
                    print(f"  [WARN] {incentive.name} ({incentive.country_code}): parse error on '{last_verified}' — {e}")
                    status = "red"
                    days_old = None
            else:
                # No verification date at all
                status = "red"
                days_old = None

            # Record the alert
            alert = SourceAlert(
                incentive_id=incentive.id,
                last_verified=last_verified,
                days_old=days_old,
                status=status,
                checked_at=today.isoformat(),
            )
            db.add(alert)
            counts[status] += 1

        db.commit()

        # Print summary
        total = counts["green"] + counts["yellow"] + counts["red"]
        green_pct = round((counts["green"] / total) * 100) if total > 0 else 0

        print(f"\n[OK] Freshness check complete ({today.isoformat()})")
        print(f"   Total records scanned: {total_checked}")
        print(f"   [GREEN] Green (< 6 months):    {counts['green']:3d} ({green_pct}%)")
        print(f"   [YELLOW] Yellow (6-12 months): {counts['yellow']:3d}")
        print(f"   [RED] Red (> 12 months):    {counts['red']:3d}")

        if counts["red"] > 0:
            print(f"\n[WARNING] {counts['red']} records over 1 year stale. Prioritize re-verification.")
            print("   See /api/admin/freshness-status for breakdown by country.\n")
        else:
            print(f"\n[SUCCESS] All records current!\n")

    finally:
        db.close()


if __name__ == "__main__":
    check_freshness()
