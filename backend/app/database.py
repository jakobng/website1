"""Database configuration."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _default_sqlite_path() -> Path:
    """Return the canonical SQLite database path in backend/."""
    return Path(__file__).resolve().parent.parent / "coproduction.db"


def get_database_url() -> str:
    """Resolve the active database URL from environment or default SQLite path."""
    return os.getenv("DATABASE_URL", f"sqlite:///{_default_sqlite_path()}")


def get_database_target() -> str:
    """Return a user-safe representation of the active database target."""
    db_url = get_database_url()
    if "://" in db_url and "@" in db_url:
        scheme, remainder = db_url.split("://", 1)
        creds, host = remainder.split("@", 1)
        username = creds.split(":", 1)[0]
        return f"{scheme}://{username}:***@{host}"
    return db_url


SQLALCHEMY_DATABASE_URL = get_database_url()
CONNECT_ARGS = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=CONNECT_ARGS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
