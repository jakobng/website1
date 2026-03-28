"""Build a country coverage matrix from seed_data.py.

Outputs:
- backend/reports/coverage_matrix.csv
- backend/reports/coverage_summary.md
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import sys


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SEED_PATH = BACKEND / "seed_data.py"
REPORTS_DIR = BACKEND / "reports"
CSV_PATH = REPORTS_DIR / "coverage_matrix.csv"
MD_PATH = REPORTS_DIR / "coverage_summary.md"

sys.path.insert(0, str(BACKEND))
from app import countries  # noqa: E402


EUROPE = {
    "AL", "AD", "AM", "AT", "AZ", "BY", "BE", "BA", "BG", "HR", "CY", "CZ",
    "DK", "EE", "FI", "FR", "GE", "DE", "GR", "HU", "IS", "IE", "IT", "XK",
    "LV", "LI", "LT", "LU", "MT", "MD", "MC", "ME", "NL", "MK", "NO", "PL",
    "PT", "RO", "RS", "SM", "SK", "SI", "ES", "SE", "CH", "TR", "UA", "GB",
    "VA",
}
AMERICAS = {
    "AG", "AR", "BS", "BB", "BZ", "BO", "BR", "CA", "CL", "CO", "CR", "CU",
    "DM", "DO", "EC", "SV", "GD", "GT", "GY", "HT", "HN", "JM", "MX", "NI",
    "PA", "PY", "PE", "KN", "LC", "VC", "SR", "TT", "US", "UY", "VE",
}
ASIA = {
    "AF", "BH", "BD", "BT", "BN", "KH", "CN", "IN", "ID", "IR", "IQ", "IL",
    "JP", "JO", "KZ", "KW", "KG", "LA", "MY", "MV", "MN", "MM", "NP", "KP",
    "OM", "PK", "PS", "PH", "QA", "KR", "SG", "LK", "SY", "TW", "TJ", "TH",
    "TL", "TM", "UZ", "VN", "YE",
}
AFRICA = {
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM", "CD",
    "CG", "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET", "GA", "GM", "GH", "GN",
    "GW", "KE", "LS", "LR", "LY", "MG", "MW", "ML", "MR", "MU", "MA", "MZ",
    "NA", "NE", "NG", "RW", "ST", "SN", "SC", "SL", "SO", "ZA", "SS", "SD",
    "TZ", "TG", "TN", "UG", "ZM", "ZW",
}
OCEANIA = {"AU", "FJ", "KI", "MH", "FM", "NR", "NZ", "PW", "PG", "WS", "SB", "TO", "TV", "VU"}


@dataclass
class CountryCoverage:
    code: str
    name: str
    macro_region: str
    incentives_count: int = 0
    regional_program_count: int = 0
    has_cultural_test_program: bool = False
    bilateral_treaty_count: int = 0
    multilateral_member: bool = False
    last_verified_latest: str = ""

    def coverage_status(self) -> str:
        if self.incentives_count > 0:
            return "incentive_covered"
        if self.bilateral_treaty_count > 0 or self.multilateral_member:
            return "treaty_only"
        return "no_coverage"

    def freshness_flag(self) -> str:
        if not self.last_verified_latest:
            return "unknown"
        # seed data uses YYYY-MM values
        if self.last_verified_latest >= "2025-01":
            return "fresh_2025"
        if self.last_verified_latest >= "2024-01":
            return "needs_refresh_2024"
        return "stale_pre_2024"


def macro_region(code: str) -> str:
    if code in EUROPE:
        return "Europe"
    if code in AMERICAS:
        return "Americas"
    if code in ASIA:
        return "Asia"
    if code in AFRICA:
        return "Africa"
    if code in OCEANIA:
        return "Oceania"
    return "Other"


def extract_call_blocks(text: str, call_name: str) -> list[str]:
    marker = f"{call_name}("
    blocks: list[str] = []
    i = 0
    while True:
        start = text.find(marker, i)
        if start == -1:
            break
        j = start + len(call_name)
        depth = 0
        in_str = False
        esc = False
        while j < len(text):
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        blocks.append(text[start : j + 1])
                        i = j + 1
                        break
            j += 1
        else:
            break
    return blocks


def parse_incentives(text: str) -> tuple[dict[str, int], dict[str, int], set[str], dict[str, str]]:
    incentive_count: dict[str, int] = defaultdict(int)
    regional_count: dict[str, int] = defaultdict(int)
    has_cultural: set[str] = set()
    latest_verified: dict[str, str] = {}

    for block in extract_call_blocks(text, "inc"):
        country_match = re.search(r'country_code\s*=\s*"([A-Z]{2})"', block)
        if not country_match:
            continue
        cc = country_match.group(1)
        incentive_count[cc] += 1

        region_match = re.search(r'region\s*=\s*"([^"]+)"', block)
        if region_match:
            regional_count[cc] += 1

        if re.search(r"cultural_test_required\s*=\s*True", block):
            has_cultural.add(cc)

        verified_match = re.search(r'last_verified\s*=\s*"(\d{4}-\d{2})"', block)
        if verified_match:
            val = verified_match.group(1)
            if val > latest_verified.get(cc, ""):
                latest_verified[cc] = val

    return incentive_count, regional_count, has_cultural, latest_verified


def parse_bilateral_treaties(text: str) -> dict[str, int]:
    bilateral_count: dict[str, int] = defaultdict(int)
    for block in extract_call_blocks(text, "bilateral"):
        # Match bilateral("Name", "AA", "BB", ...)
        pair = re.search(r',\s*"([A-Z]{2})"\s*,\s*"([A-Z]{2})"', block)
        if not pair:
            continue
        country_a, country_b = pair.groups()
        bilateral_count[country_a] += 1
        bilateral_count[country_b] += 1
    return bilateral_count


def parse_multilateral_members(text: str) -> set[str]:
    return set(re.findall(r'\("([A-Z]{2})"\s*,\s*"\d{4}-\d{2}-\d{2}"\s*,', text))


def compute_priority_score(row: CountryCoverage) -> tuple[int, str]:
    if row.incentives_count > 0:
        return 0, "already_has_incentives"

    score = 0
    reasons: list[str] = []

    strategic = {"US", "MX", "JP", "CN", "IN", "AE", "SA", "TH", "ID", "MY", "PH", "NG", "EG"}
    if row.code in strategic:
        score += 3
        reasons.append("major_market")

    if row.bilateral_treaty_count > 0 or row.multilateral_member:
        score += 2
        reasons.append("treaty_path_exists")

    if row.macro_region in {"Asia", "Americas"}:
        score += 2
        reasons.append("undercovered_region")
    elif row.macro_region in {"Africa", "Oceania"}:
        score += 1
        reasons.append("region_gap")

    if score == 0:
        reasons.append("lower_priority_gap")
    return score, "+".join(reasons)


def pct(part: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(part / total) * 100:.1f}%"


def ensure_reports_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def write_csv(rows: Iterable[dict[str, str]]) -> None:
    fieldnames = [
        "code",
        "name",
        "macro_region",
        "coverage_status",
        "incentives_count",
        "regional_program_count",
        "has_cultural_test_program",
        "bilateral_treaty_count",
        "multilateral_member",
        "last_verified_latest",
        "freshness_flag",
        "priority_score",
        "priority_reason",
    ]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    text = SEED_PATH.read_text(encoding="utf-8", errors="ignore")
    incentive_count, regional_count, has_cultural, latest_verified = parse_incentives(text)
    bilateral_count = parse_bilateral_treaties(text)
    multilateral_members = parse_multilateral_members(text)

    all_country_objs = countries.all_countries()
    by_code: dict[str, CountryCoverage] = {}
    for item in all_country_objs:
        code = item["code"]
        row = CountryCoverage(
            code=code,
            name=item["name"],
            macro_region=macro_region(code),
            incentives_count=incentive_count.get(code, 0),
            regional_program_count=regional_count.get(code, 0),
            has_cultural_test_program=code in has_cultural,
            bilateral_treaty_count=bilateral_count.get(code, 0),
            multilateral_member=code in multilateral_members,
            last_verified_latest=latest_verified.get(code, ""),
        )
        by_code[code] = row

    csv_rows: list[dict[str, str]] = []
    for code in sorted(by_code.keys()):
        row = by_code[code]
        p_score, p_reason = compute_priority_score(row)
        csv_rows.append({
            "code": row.code,
            "name": row.name,
            "macro_region": row.macro_region,
            "coverage_status": row.coverage_status(),
            "incentives_count": str(row.incentives_count),
            "regional_program_count": str(row.regional_program_count),
            "has_cultural_test_program": "yes" if row.has_cultural_test_program else "no",
            "bilateral_treaty_count": str(row.bilateral_treaty_count),
            "multilateral_member": "yes" if row.multilateral_member else "no",
            "last_verified_latest": row.last_verified_latest,
            "freshness_flag": row.freshness_flag(),
            "priority_score": str(p_score),
            "priority_reason": p_reason,
        })

    ensure_reports_dir()
    write_csv(csv_rows)

    total = len(csv_rows)
    incentive_covered = [r for r in csv_rows if r["coverage_status"] == "incentive_covered"]
    treaty_only = [r for r in csv_rows if r["coverage_status"] == "treaty_only"]
    no_coverage = [r for r in csv_rows if r["coverage_status"] == "no_coverage"]

    region_totals: dict[str, int] = defaultdict(int)
    region_cov: dict[str, int] = defaultdict(int)
    for r in csv_rows:
        region_totals[r["macro_region"]] += 1
        if r["coverage_status"] != "no_coverage":
            region_cov[r["macro_region"]] += 1

    highest_priority_missing = sorted(
        [r for r in csv_rows if r["coverage_status"] != "incentive_covered"],
        key=lambda r: (int(r["priority_score"]), r["macro_region"], r["code"]),
        reverse=True,
    )[:30]
    treaty_only_sorted = sorted(
        treaty_only,
        key=lambda r: (int(r["bilateral_treaty_count"]), r["code"]),
        reverse=True,
    )[:20]

    lines: list[str] = []
    lines.append("# Coverage Gap Summary")
    lines.append("")
    lines.append("This report is generated from `backend/seed_data.py` and `backend/app/countries.py`.")
    lines.append("")
    lines.append("## Snapshot")
    lines.append("")
    lines.append(f"- Supported countries in catalog: **{total}**")
    lines.append(f"- Countries with incentives: **{len(incentive_covered)}** ({pct(len(incentive_covered), total)})")
    lines.append(f"- Treaty-only countries (no incentive data yet): **{len(treaty_only)}** ({pct(len(treaty_only), total)})")
    lines.append(f"- No coverage (no incentives or treaties): **{len(no_coverage)}** ({pct(len(no_coverage), total)})")
    lines.append("")
    lines.append("## Regional Coverage (Incentive or Treaty)")
    lines.append("")
    for region in sorted(region_totals.keys()):
        cov = region_cov.get(region, 0)
        tot = region_totals[region]
        lines.append(f"- {region}: **{cov}/{tot}** ({pct(cov, tot)})")
    lines.append("")
    lines.append("## Highest-Priority Missing Additions")
    lines.append("")
    lines.append("| Code | Country | Region | Status | Priority | Reason |")
    lines.append("|---|---|---|---|---:|---|")
    for r in highest_priority_missing:
        lines.append(
            f"| {r['code']} | {r['name']} | {r['macro_region']} | {r['coverage_status']} | {r['priority_score']} | {r['priority_reason']} |"
        )
    lines.append("")
    lines.append("## Treaty-Only Countries (Good Next Incentive Targets)")
    lines.append("")
    lines.append("| Code | Country | Bilateral Treaties | Multilateral Member |")
    lines.append("|---|---|---:|---|")
    for r in treaty_only_sorted:
        lines.append(
            f"| {r['code']} | {r['name']} | {r['bilateral_treaty_count']} | {r['multilateral_member']} |"
        )
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append(f"- Matrix CSV: `{CSV_PATH.as_posix()}`")
    lines.append(f"- Summary report: `{MD_PATH.as_posix()}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `coverage_status` uses incentive data first, then treaty-only.")
    lines.append("- `priority_score` is a pragmatic heuristic for sequencing work, not a legal ranking.")
    lines.append("- Freshness is based on `last_verified` values embedded in seed data.")

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {MD_PATH}")


if __name__ == "__main__":
    main()
