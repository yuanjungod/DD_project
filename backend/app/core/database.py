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


def _rename_column_if_needed(conn, inspector, table: str, old: str, new: str) -> None:
    if table not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(table)}
    if old in cols and new not in cols:
        conn.execute(text(f'ALTER TABLE "{table}" RENAME COLUMN {old} TO {new}'))


def ensure_schema_patches(engine) -> None:
    """Add columns introduced after first deploy (SQLite lacks auto-migrations)."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "agent_runs" in tables:
        cols = {c["name"] for c in inspector.get_columns("agent_runs")}
        statements: list[str] = []
        if "session_id" not in cols:
            statements.append("ALTER TABLE agent_runs ADD COLUMN session_id VARCHAR")
        if "attempt_index" not in cols:
            statements.append("ALTER TABLE agent_runs ADD COLUMN attempt_index INTEGER DEFAULT 1 NOT NULL")
        if "started_by_user_id" not in cols:
            statements.append("ALTER TABLE agent_runs ADD COLUMN started_by_user_id VARCHAR")
        if statements:
            with engine.begin() as conn:
                for stmt in statements:
                    conn.execute(text(stmt))

    with engine.begin() as conn:
        if "projects" in tables and "engagements" not in tables:
            conn.execute(text("ALTER TABLE projects RENAME TO engagements"))
            tables.discard("projects")
            tables.add("engagements")
        if "project_access" in tables and "engagement_access" not in tables:
            conn.execute(text("ALTER TABLE project_access RENAME TO engagement_access"))
            tables.discard("project_access")
            tables.add("engagement_access")

    inspector = inspect(engine)
    with engine.begin() as conn:
        tables = set(inspector.get_table_names())
        if "diligence_sessions" in tables and "workflow_sessions" in tables:
            legacy_count = conn.execute(text("SELECT COUNT(*) FROM diligence_sessions")).scalar_one()
            harness_count = conn.execute(text("SELECT COUNT(*) FROM workflow_sessions")).scalar_one()
            if legacy_count and not harness_count:
                conn.execute(text("DROP TABLE workflow_sessions"))
                conn.execute(text("ALTER TABLE diligence_sessions RENAME TO workflow_sessions"))
            elif not legacy_count and harness_count:
                conn.execute(text("DROP TABLE diligence_sessions"))
            tables.discard("diligence_sessions")
        elif "diligence_sessions" in tables and "workflow_sessions" not in tables:
            conn.execute(text("ALTER TABLE diligence_sessions RENAME TO workflow_sessions"))
            tables.discard("diligence_sessions")
            tables.add("workflow_sessions")

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in ("agent_runs", "reports", "workflow_sessions", "diligence_sessions", "engagement_access"):
            _rename_column_if_needed(conn, inspector, table, "project_id", "engagement_id")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "engagements" not in tables:
        return
    eng_cols = {c["name"] for c in inspector.get_columns("engagements")}
    eng_statements: list[str] = []
    if "subject_key" not in eng_cols:
        if "company_key" in eng_cols:
            with engine.begin() as conn:
                _rename_column_if_needed(conn, inspect(engine), "engagements", "company_key", "subject_key")
        else:
            eng_statements.append("ALTER TABLE engagements ADD COLUMN subject_key VARCHAR DEFAULT 'subject' NOT NULL")
    if "instance_config" not in eng_cols:
        if "company_config" in eng_cols:
            with engine.begin() as conn:
                _rename_column_if_needed(conn, inspect(engine), "engagements", "company_config", "instance_config")
        else:
            eng_statements.append("ALTER TABLE engagements ADD COLUMN instance_config JSON NOT NULL DEFAULT '{}'")
    if "application_id" not in eng_cols:
        eng_statements.append("ALTER TABLE engagements ADD COLUMN application_id VARCHAR DEFAULT 'default' NOT NULL")
    if "version" not in eng_cols:
        eng_statements.append("ALTER TABLE engagements ADD COLUMN version INTEGER DEFAULT 1 NOT NULL")
    if eng_statements:
        with engine.begin() as conn:
            for stmt in eng_statements:
                conn.execute(text(stmt))
