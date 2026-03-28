from app.database import SessionLocal
from app.schemas import ProjectInput
from app.scenario_generator import generate_scenarios
import json

project_json = {
  "title": "Doc USD Budget FR-CA",
  "format": "documentary",
  "stage": "production",
  "budget": 400000.0,
  "budget_currency": "USD",
  "shoot_locations": [
    {
      "country": "France",
      "percent": 60.0
    },
    {
      "country": "Canada",
      "percent": 40.0
    }
  ],
  "director_nationalities": ["France"],
  "has_coproducer": ["Canada"],
  "willing_add_coproducer": True
}

project = ProjectInput(**project_json)
from sqlalchemy import inspect
# ...
db = SessionLocal()
try:
    inspector = inspect(db.get_bind())
    tables = inspector.get_table_names()
    print(f"Tables in DB: {tables}")
    if "incentives" in tables:
        from sqlalchemy import text
        count = db.execute(text("SELECT count(*) FROM incentives")).scalar()
        print(f"Count in 'incentives': {count}")
    
    scenarios = generate_scenarios(project, db)
    print(f"Generated {len(scenarios)} scenarios.")
    if scenarios:
        print(f"Top financing: {scenarios[0].estimated_total_financing_percent}%")
    else:
        print("No scenarios generated!")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
