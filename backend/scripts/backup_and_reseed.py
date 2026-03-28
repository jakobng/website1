"""Backup current DB (if present), migrate to head, and reseed canonical data."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
from shutil import which

from sqlalchemy.engine import make_url


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, SessionLocal, engine, get_database_target, get_database_url
import app.models  # noqa: F401
from app.models import Document, Incentive, Treaty


def _sqlite_db_path(db_url: str) -> Path | None:
    """Return the filesystem path for sqlite URLs, else None."""
    url = make_url(db_url)
    if url.get_backend_name() != "sqlite":
        return None
    if url.database in (None, "", ":memory:"):
        return None
    db_path = Path(url.database).expanduser()
    if not db_path.is_absolute():
        db_path = (BACKEND_DIR / db_path).resolve()
    return db_path


def _run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=BACKEND_DIR, check=True)


def _run_alembic_upgrade() -> None:
    """Upgrade DB schema using Alembic when available, else bootstrap via metadata."""
    alembic_exe = BACKEND_DIR / "venv" / "Scripts" / "alembic.exe"
    if alembic_exe.exists():
        _run([str(alembic_exe), "-c", "alembic.ini", "upgrade", "head"])
        return

    system_alembic = which("alembic")
    if system_alembic:
        _run([system_alembic, "-c", "alembic.ini", "upgrade", "head"])
        return

    # Fallback for restricted environments where Alembic cannot be installed.
    print("WARNING: Alembic is unavailable. Falling back to SQLAlchemy metadata bootstrap.")
    Base.metadata.create_all(bind=engine)


def _backup_if_present(db_path: Path | None) -> None:
    if db_path is None:
        print("No filesystem-backed SQLite database detected; skipping backup step.")
        return

    backups_dir = BACKEND_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"No existing database at {db_path}; skipping file backup.")
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backups_dir / f"{db_path.stem}-{stamp}{db_path.suffix or '.db'}"
    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")


def _print_counts() -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        incentives = db.query(Incentive).count()
        treaties = db.query(Treaty).count()
        documents = db.query(Document).count()
    finally:
        db.close()
    print(f"Post-seed counts: incentives={incentives}, treaties={treaties}, documents={documents}")
    return incentives, treaties, documents


def main() -> int:
    db_url = get_database_url()
    print(f"Database target: {get_database_target()}")

    _backup_if_present(_sqlite_db_path(db_url))

    # Schema first, then data.
    _run_alembic_upgrade()
    _run([sys.executable, "seed_data.py"])
    _run([sys.executable, "seed_documents.py"])

    incentives, treaties, documents = _print_counts()
    if incentives <= 0 or treaties <= 0:
        print("ERROR: database reseed did not produce required incentive/treaty data.")
        return 1

    print("Backup + migrate + reseed completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
