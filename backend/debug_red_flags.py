
from app.schemas import ProjectInput, ShootLocation
from app.scenario_generator import generate_scenarios
from app.database import SessionLocal
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.rule_engine")
logger.setLevel(logging.DEBUG)

def debug_country(country_name, country_code):
    print(f"\n{'='*60}")
    print(f"DEBUGGING: {country_name} ({country_code})")
    print(f"{'='*60}")
    
    db = SessionLocal()
    
    # Test scenario that SHOULD match (Doc, 500k, 100% shoot)
    project = ProjectInput(
        title=f"{country_name} Test",
        format="documentary",
        stage="production",
        budget=500_000,
        budget_currency="EUR",
        shoot_locations=[ShootLocation(country=country_name, percent=100)],
        director_nationalities=[country_name],
        willing_add_coproducer=True,
    )

    print(f"Project: {project.title}, Budget: {project.budget} {project.budget_currency}")
    
    scenarios = generate_scenarios(project, db)
    print(f"\nGenerated {len(scenarios)} scenarios")
    
    for i, s in enumerate(scenarios):
        print(f"  Scenario {i+1}: {s.estimated_total_financing_percent}% financing")
        for p in s.partners:
            print(f"    Partner: {p.country_name} ({p.country_code}), Incs: {len(p.eligible_incentives)}")
            for inc in p.eligible_incentives:
                print(f"      - {inc.name}: {inc.estimated_contribution_percent}%")

    if not scenarios:
        print("!!! NO SCENARIOS GENERATED !!!")

if __name__ == "__main__":
    red_flags = [
        ("Portugal", "PT"),
        ("Montenegro", "ME"),
        ("North Macedonia", "MK"),
        ("Malta", "MT"),
        ("Romania", "RO"),
        ("Serbia", "RS"),
        ("Slovenia", "SI"),
        ("Slovakia", "SK"),
        ("Turkey", "TR"),
        ("Ukraine", "UA")
    ]
    
    for name, code in red_flags:
        debug_country(name, code)
