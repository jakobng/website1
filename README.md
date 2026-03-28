# CoPro Calculator

Decision-support tool for filmmakers to explore coproduction structures, financing incentives, and treaty pathways with source-backed outputs.

## Stack
- Backend: FastAPI, SQLAlchemy, Alembic, SQLite
- Frontend: React + TypeScript + Vite + Tailwind

## Backend Setup
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
# Optional (recommended for managed schema migrations)
pip install -r requirements-migrations.txt
python scripts/backup_and_reseed.py
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000` and docs at `http://localhost:8000/docs`.

## Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and proxies `/api` to `http://localhost:8000`.

## Database Configuration
- Canonical DB defaults to `backend/coproduction.db`.
- Override with `DATABASE_URL` if needed (for local/CI/hosted databases).
- DB readiness can be checked via `GET /api/health/db`.
- `backup_and_reseed.py` uses Alembic when available; in restricted environments without Alembic it falls back to SQLAlchemy metadata bootstrap.

## Scenario Test Runners
```bash
cd scenario_tests
python test_runner.py --scenario basic_feature_fr.json
python comprehensive_test_runner.py --category A
```

If runners report an empty database, run:
```bash
cd backend
python scripts/backup_and_reseed.py
```

## Notes
- Intake PDF extraction requires `PyPDF2` (included in `requirements.txt`).
- In some restricted environments, frontend production build may fail with an `esbuild spawn EPERM` permission error; local dev server is usually unaffected.
