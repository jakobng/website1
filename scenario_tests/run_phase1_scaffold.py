"""Run phase1 scaffold scenario fixtures (JP/IN/CN/MX).

This runner does not alter default scenario tests.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCENARIOS = Path(__file__).resolve().parent / "scenarios_phase1"

sys.path.insert(0, str(BACKEND))

from app.database import SessionLocal, get_database_target  # noqa: E402
from app.models import Incentive, Treaty  # noqa: E402
from app.schemas import ProjectInput  # noqa: E402
from app.scenario_generator import generate_scenarios  # noqa: E402


def ensure_seeded(db) -> None:
    n_incentives = db.query(Incentive).count()
    n_treaties = db.query(Treaty).count()
    if n_incentives <= 0 or n_treaties <= 0:
        raise RuntimeError(
            "Database is empty for scaffold scenarios "
            f"(incentives={n_incentives}, treaties={n_treaties}, target={get_database_target()}). "
            "Run: cd backend && python scripts/backup_and_reseed.py"
        )


def main() -> None:
    files = sorted([p for p in SCENARIOS.glob("*.json") if p.is_file()])
    if not files:
        print("No phase1 scenario files found.")
        return

    db = SessionLocal()
    try:
        ensure_seeded(db)
        print(f"Running {len(files)} phase1 scenarios...\n")
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            project = ProjectInput(**data)
            scenarios = generate_scenarios(project, db)
            top = scenarios[0] if scenarios else None
            if not top:
                print(f"[{path.name}] no scenarios")
                continue
            partner_codes = ",".join([p.country_code for p in top.partners])
            print(
                f"[{path.name}] top={top.estimated_total_financing_percent:.1f}% "
                f"{top.financing_currency} {top.estimated_total_financing_amount:,.0f} "
                f"partners={partner_codes} near_misses={len(top.near_misses)}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
