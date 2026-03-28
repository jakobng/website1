from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

import models, schemas, database
from engine import CoproEngine

app = FastAPI(title="Film Coproduction Strategy Engine API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup_populate_db():
    # Create tables
    models.Base.metadata.create_all(bind=database.engine)
    
    db = database.SessionLocal()
    # Check if we have data, if not seed it
    if db.query(models.Incentive).count() == 0:
        seed_data(db)
    db.close()

def seed_data(db: Session):
    # Spain Rebate
    spain_rebate = models.Incentive(
        name="Spanish Tax Rebate",
        country="Spain",
        type=models.IncentiveType.tax_rebate,
        gross_rebate_percent=30.0,
        max_cap=10000000.0,
        min_local_spend_percent=25.0,
        net_yield_multiplier=0.85,
        recoupment_position=models.RecoupmentPosition.none,
        requires_territory_rights=True,
        state_aid_eligible=True
    )
    # UK Tax Credit (AVEC)
    uk_tax_credit = models.Incentive(
        name="UK AVEC",
        country="United Kingdom",
        type=models.IncentiveType.tax_rebate,
        gross_rebate_percent=25.5,
        max_cap=None,
        min_local_spend_percent=10.0,
        net_yield_multiplier=0.90,
        recoupment_position=models.RecoupmentPosition.none,
        requires_territory_rights=False,
        state_aid_eligible=True
    )
    # France Tax Rebate (TRIP)
    france_rebate = models.Incentive(
        name="French TRIP",
        country="France",
        type=models.IncentiveType.tax_rebate,
        gross_rebate_percent=30.0,
        max_cap=30000000.0,
        min_local_spend_percent=20.0,
        net_yield_multiplier=0.88,
        recoupment_position=models.RecoupmentPosition.none,
        requires_territory_rights=False,
        state_aid_eligible=True
    )
    
    db.add_all([spain_rebate, uk_tax_credit, france_rebate])
    
    # UK-Spain Treaty
    uk_spain_treaty = models.Treaty(
        country_a="United Kingdom",
        country_b="Spain",
        min_financial_share_a=20.0,
        min_financial_share_b=20.0,
        requires_official_copro_status=True
    )
    db.add(uk_spain_treaty)
    db.commit()

@app.get("/api/incentives", response_model=List[schemas.IncentiveSchema])
def get_incentives(db: Session = Depends(get_db)):
    return db.query(models.Incentive).all()

@app.get("/api/treaties", response_model=List[schemas.TreatySchema])
def get_treaties(db: Session = Depends(get_db)):
    return db.query(models.Treaty).all()

@app.post("/api/projects/analyze", response_model=List[schemas.Scenario])
def analyze_project(project: schemas.ProjectInput, db: Session = Depends(get_db)):
    incentives = db.query(models.Incentive).all()
    treaties = db.query(models.Treaty).all()
    
    engine = CoproEngine(incentives, treaties)
    scenarios = engine.generate_scenarios(project)
    
    return scenarios

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
