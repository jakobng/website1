"""Validate phase1 scaffold completeness.

Checks that placeholder incentive records include required provenance fields.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD_PATH = ROOT / "backend" / "data" / "expansion" / "phase1_scaffold_records.json"

REQUIRED_INC_FIELDS = [
    "record_id",
    "country_code",
    "name",
    "incentive_type",
    "source_url",
    "source_description",
    "notes",
    "last_verified",
]


def main() -> None:
    data = json.loads(SCAFFOLD_PATH.read_text(encoding="utf-8"))
    missing = []

    for idx, rec in enumerate(data.get("incentive_records", []), start=1):
        for field in REQUIRED_INC_FIELDS:
            val = rec.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append((idx, rec.get("record_id", f"<index:{idx}>"), field))

    if missing:
        print("INVALID: missing required fields")
        for idx, rid, field in missing:
            print(f"- record {idx} ({rid}): missing '{field}'")
        raise SystemExit(1)

    print(f"OK: {len(data.get('incentive_records', []))} incentive scaffold records validated")


if __name__ == "__main__":
    main()
