"""Data Quality Audit for CoPro Calculator.

Analyzes backend/seed_data.py and generates a detailed completeness report.
"""
import re
import csv
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SEED_PATH = BACKEND / "seed_data.py"
REPORTS_DIR = BACKEND / "reports"
AUDIT_REPORT_MD = REPORTS_DIR / "DATA_AUDIT_REPORT.md"
AUDIT_REPORT_CSV = REPORTS_DIR / "data_audit.csv"

sys.path.insert(0, str(BACKEND))
from app import countries

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

def parse_val(block, key):
    # Matches key="val", key=val, key=['val'], key=True/False/None
    pattern = rf'{key}\s*=\s*([^,\n\)]+)'
    match = re.search(pattern, block)
    if not match:
        return None
    val = match.group(1).strip()
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1]
    if val == "None":
        return None
    if val == "True":
        return True
    if val == "False":
        return False
    try:
        if "." in val:
            return float(val.replace("_", ""))
        return int(val.replace("_", ""))
    except ValueError:
        return val

def calculate_completeness(inc_data):
    fields = [
        "name", "incentive_type", "rebate_percent", 
        "min_total_budget", "min_qualifying_spend",
        "eligible_formats", "source_url", "notes"
    ]
    filled = 0
    for f in fields:
        if inc_data.get(f) is not None and inc_data.get(f) != "":
            filled += 1
    return (filled / len(fields)) * 100

def main():
    if not SEED_PATH.exists():
        print(f"Error: {SEED_PATH} not found")
        return

    text = SEED_PATH.read_text(encoding="utf-8", errors="ignore")
    blocks = extract_call_blocks(text, "inc")
    
    country_incentives = defaultdict(list)
    
    for block in blocks:
        data = {
            "name": parse_val(block, "name"),
            "country_code": parse_val(block, "country_code"),
            "incentive_type": parse_val(block, "incentive_type"),
            "rebate_percent": parse_val(block, "rebate_percent"),
            "min_total_budget": parse_val(block, "min_total_budget"),
            "min_qualifying_spend": parse_val(block, "min_qualifying_spend"),
            "eligible_formats": parse_val(block, "eligible_formats"),
            "source_url": parse_val(block, "source_url"),
            "notes": parse_val(block, "notes"),
            "last_verified": parse_val(block, "last_verified"),
        }
        if data["country_code"]:
            data["completeness"] = calculate_completeness(data)
            country_incentives[data["country_code"]].append(data)

    all_countries = countries.all_countries()
    
    report_data = []
    for c in all_countries:
        code = c["code"]
        incs = country_incentives.get(code, [])
        num_incs = len(incs)
        avg_completeness = sum(i["completeness"] for i in incs) / num_incs if num_incs > 0 else 0
        
        report_data.append({
            "code": code,
            "name": c["name"],
            "num_incentives": num_incs,
            "avg_completeness": avg_completeness,
            "incentives": incs
        })

    # Sort by number of incentives (ascending) then completeness
    report_data.sort(key=lambda x: (x["num_incentives"], x["avg_completeness"]))

    # Write CSV
    with open(AUDIT_REPORT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Country Code", "Country Name", "Num Incentives", "Avg Completeness %"])
        for r in report_data:
            writer.writerow([r["code"], r["name"], r["num_incentives"], f"{r['avg_completeness']:.1f}"])

    # Write Markdown
    lines = [
        "# Data Quality Audit Report",
        f"Total Countries Analyzed: {len(report_data)}",
        "",
        "## Summary",
        f"- Countries with 0 incentives: {len([r for r in report_data if r['num_incentives'] == 0])}",
        f"- Countries with 1 incentive: {len([r for r in report_data if r['num_incentives'] == 1])}",
        f"- Countries with 3+ incentives: {len([r for r in report_data if r['num_incentives'] >= 3])}",
        "",
        "## Red Flag Countries (0 or 1 Incentive)",
        "| Code | Country | Num Incs | Avg Comp % |",
        "|---|---|---|---|",
    ]
    
    for r in report_data:
        if r["num_incentives"] <= 1:
            lines.append(f"| {r['code']} | {r['name']} | {r['num_incentives']} | {r['avg_completeness']:.1f}% |")

    lines.append("")
    lines.append("## Tier 1 Critical Markets Audit")
    tier1 = ["CN", "IN", "JP", "VN", "TH", "ID", "BR", "MX", "KR"]
    lines.append("| Code | Country | Num Incs | Avg Comp % |")
    lines.append("|---|---|---|---|")
    for code in tier1:
        r = next((x for x in report_data if x["code"] == code), None)
        if r:
            lines.append(f"| {r['code']} | {r['name']} | {r['num_incentives']} | {r['avg_completeness']:.1f}% |")

    lines.append("")
    lines.append("## Detailed Inventory")
    for r in report_data:
        if r["num_incentives"] > 0:
            lines.append(f"### {r['name']} ({r['code']})")
            lines.append(f"Total Incentives: {r['num_incentives']}")
            for i in r["incentives"]:
                lines.append(f"- **{i['name']}**")
                lines.append(f"  - Type: {i['incentive_type']}")
                lines.append(f"  - Rebate: {i['rebate_percent']}%")
                lines.append(f"  - Min Budget: {i['min_total_budget']}")
                lines.append(f"  - Min Spend: {i['min_qualifying_spend']}")
                lines.append(f"  - Completeness: {i['completeness']:.1f}%")
                lines.append(f"  - Last Verified: {i['last_verified']}")
            lines.append("")

    AUDIT_REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Audit report generated: {AUDIT_REPORT_MD}")

if __name__ == "__main__":
    main()
