from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_patches(engine) -> None:
    """Add columns introduced after first deploy (SQLite lacks auto-migrations)."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "agent_runs" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("agent_runs")}
    statements: list[str] = []
    if "session_id" not in cols:
        statements.append("ALTER TABLE agent_runs ADD COLUMN session_id VARCHAR")
    if "attempt_index" not in cols:
        statements.append("ALTER TABLE agent_runs ADD COLUMN attempt_index INTEGER DEFAULT 1 NOT NULL")
    if not statements:
        return
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
