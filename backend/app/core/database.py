from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


DATABASE_URL = settings.resolved_database_url

if DATABASE_URL.startswith("sqlite"):
    sqlite_path = make_url(DATABASE_URL).database
    if sqlite_path and sqlite_path != ":memory:":
        Path(sqlite_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
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
    if "agent_runs" in tables:
        cols = {c["name"] for c in inspector.get_columns("agent_runs")}
        statements: list[str] = []
        if "session_id" not in cols:
            statements.append("ALTER TABLE agent_runs ADD COLUMN session_id VARCHAR")
        if "attempt_index" not in cols:
            statements.append("ALTER TABLE agent_runs ADD COLUMN attempt_index INTEGER DEFAULT 1 NOT NULL")
        if statements:
            with engine.begin() as conn:
                for stmt in statements:
                    conn.execute(text(stmt))

    if "projects" not in tables:
        return
    proj_cols = {c["name"] for c in inspector.get_columns("projects")}
    proj_statements: list[str] = []
    if "company_key" not in proj_cols:
        proj_statements.append("ALTER TABLE projects ADD COLUMN company_key VARCHAR DEFAULT 'company' NOT NULL")
    if "application_id" not in proj_cols:
        proj_statements.append("ALTER TABLE projects ADD COLUMN application_id VARCHAR DEFAULT 'default' NOT NULL")
    if "version" not in proj_cols:
        proj_statements.append("ALTER TABLE projects ADD COLUMN version INTEGER DEFAULT 1 NOT NULL")
    if proj_statements:
        with engine.begin() as conn:
            for stmt in proj_statements:
                conn.execute(text(stmt))
