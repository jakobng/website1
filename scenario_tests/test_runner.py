
import os
import sys
import json
from datetime import datetime
from typing import Any

# Add backend to path so we can import app modules
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from app.database import SessionLocal, get_database_target
from app.models import Incentive, Treaty
from app.schemas import ProjectInput, Scenario
from app.scenario_generator import generate_scenarios


def ensure_seeded(db) -> None:
    """Fail fast when the active DB has no source data."""
    n_incentives = db.query(Incentive).count()
    n_treaties = db.query(Treaty).count()
    if n_incentives <= 0 or n_treaties <= 0:
        raise RuntimeError(
            "Database is empty for scenario tests "
            f"(incentives={n_incentives}, treaties={n_treaties}, target={get_database_target()}). "
            "Run: cd backend && python scripts/backup_and_reseed.py"
        )


def generate_llm_report(project: ProjectInput, scenario: Scenario) -> str:
    """Generate a detailed Markdown report for LLM review."""
    report = []
    report.append(f"# SCENARIO REVIEW REPORT: {project.title}")
    report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    report.append("## PROJECT INPUT")
    report.append(f"```json\n{project.model_dump_json(indent=2)}\n```\n")
    
    report.append("## CALCULATOR OUTPUT SUMMARY")
    report.append(f"- **Total Financing:** {scenario.estimated_total_financing_percent}%")
    report.append(f"- **Total Amount:** {scenario.financing_currency} {scenario.estimated_total_financing_amount:,.0f}")
    report.append(f"- **Rationale:** {scenario.rationale}\n")
    
    report.append("## PARTNERS & INCENTIVES")
    for partner in scenario.partners:
        report.append(f"### Partner: {partner.country_name} ({partner.country_code})")
        report.append(f"- **Role:** {partner.role}")
        report.append(f"- **Est. Share:** {partner.estimated_share_percent or 0}%")
        
        if partner.eligible_incentives:
            for inc in partner.eligible_incentives:
                report.append(f"\n#### Incentive: {inc.name}")
                report.append(f"- **Type:** {inc.incentive_type}")
                report.append(f"- **Contribution:** {inc.estimated_contribution_percent}%")
                if inc.benefit:
                    report.append(f"- **Explanation:** {inc.benefit.benefit_explanation}")
                    if inc.benefit.calculation_steps:
                        report.append("- **Calculation Steps:**")
                        for step in inc.benefit.calculation_steps:
                            report.append(f"  - {step.label}: `{step.formula}` = {step.value:,.0f} {step.currency}")
                
                if inc.requirements:
                    report.append("- **Requirements:**")
                    for req in inc.requirements:
                        report.append(f"  - [{req.category}] {req.description}")
        else:
            report.append("- *No eligible incentives found for this partner.*")
        
        if partner.applicable_treaties:
            report.append("\n#### Applicable Treaties:")
            for treaty in partner.applicable_treaties:
                report.append(f"- **{treaty.treaty_name}**")
                if treaty.min_share_percent: report.append(f"  - Min Share: {treaty.min_share_percent}%")
                if treaty.creative_requirements: report.append(f"  - Creative: {treaty.creative_requirements}")
        report.append("")

    if scenario.requirements:
        report.append("## GLOBAL REQUIREMENTS / BLOCKS")
        for req in scenario.requirements:
            report.append(f"- [{req.category}] {req.description}")
        report.append("")

    report.append("## LLM REVIEW GUIDELINES")
    report.append("Please analyze the above data and check for:")
    report.append("1. **Logical Inconsistencies**: Are any 'requirements' listed as unmet, but the incentive is still marked as providing a contribution?")
    report.append("2. **Math Errors**: Do the 'Calculation Steps' logically lead to the 'Total Financing' amount?")
    report.append("3. **Eligibility Conflicts**: Check the Project Input (format, budget, stages, locations) against the Incentive explanations.")
    report.append("4. **Missing Opportunities**: Based on the partners and locations, are there obvious treaties or incentives that SHOULD be here but aren't?")
    
    return "\n".join(report)

def run_test_scenario(file_path: str, db, review_mode: bool = False):
    print(f"\n{'='*80}")
    print(f"RUNNING SCENARIO: {os.path.basename(file_path)}")
    print(f"{'='*80}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    try:
        project = ProjectInput(**data)
    except Exception as e:
        print(f"ERROR parsing ProjectInput: {e}")
        return

    scenarios = generate_scenarios(project, db)
    
    if not scenarios:
        print("RESULT: No scenarios generated.")
        return

    print(f"RESULT: Found {len(scenarios)} scenarios.")
    
    # Analyze the top scenario
    top = scenarios[0]
    print(f"TOP SCENARIO: {top.estimated_total_financing_percent}% financing found.")
    
    if review_mode:
        report_content = generate_llm_report(project, top)
        report_filename = os.path.basename(file_path).replace('.json', '_report.md')
        report_path = os.path.join(os.path.dirname(__file__), 'reports', report_filename)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"LLM REVIEW REPORT GENERATED: {report_path}")
    else:
        # Standard summary output
        print(f"\nTOP SCENARIO SUMMARY:")
        print(f"  Total Financing: {top.estimated_total_financing_percent}% ({top.financing_currency} {top.estimated_total_financing_amount:,.0f})")
        print(f"  Partners: {', '.join(p.country_name for p in top.partners)}")
        
        found_any = False
        for p in top.partners:
            for inc in p.eligible_incentives:
                found_any = True
                print(f"    - [{p.country_code}] {inc.name}: {inc.estimated_contribution_percent}%")
        
        if top.requirements:
            print("\n  OUTSTANDING REQUIREMENTS / BLOCKS:")
            for req in top.requirements:
                print(f"    - [{req.category}] {req.description}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', action='store_true', help='Generate detailed reports for LLM review')
    parser.add_argument('--scenario', help='Specific scenario file to run')
    args = parser.parse_args()

    scenarios_dir = os.path.join(os.path.dirname(__file__), 'scenarios')
    db = SessionLocal()
    
    try:
        ensure_seeded(db)
        if args.scenario:
            files = [args.scenario if args.scenario.endswith('.json') else args.scenario + '.json']
        else:
            files = [f for f in os.listdir(scenarios_dir) if f.endswith('.json')]
            
        if not files:
            print(f"No scenario files found.")
            return
            
        for file_name in files:
            full_path = os.path.join(scenarios_dir, file_name)
            if os.path.exists(full_path):
                run_test_scenario(full_path, db, args.review)
            else:
                print(f"Scenario not found: {full_path}")
    except RuntimeError as err:
        print(f"ERROR: {err}")
        raise SystemExit(1) from err
    finally:
        db.close()

if __name__ == "__main__":
    main()
