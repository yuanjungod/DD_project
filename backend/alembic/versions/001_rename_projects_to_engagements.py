"""Rename legacy project tables and columns to engagement naming."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "001_engagement_rename"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    bind = op.get_bind()
    return set(inspect(bind).get_table_names())


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return set()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _rename_column_if_needed(table: str, old: str, new: str) -> None:
    cols = _column_names(table)
    if old in cols and new not in cols:
        op.alter_column(table, old, new_column_name=new)


def upgrade() -> None:
    tables = _table_names()
    if "projects" in tables and "engagements" not in tables:
        op.rename_table("projects", "engagements")
        tables.discard("projects")
        tables.add("engagements")
    if "project_access" in tables and "engagement_access" not in tables:
        op.rename_table("project_access", "engagement_access")
        tables.discard("project_access")
        tables.add("engagement_access")

    for table in ("agent_runs", "reports", "diligence_sessions", "engagement_access"):
        _rename_column_if_needed(table, "project_id", "engagement_id")


def downgrade() -> None:
    tables = _table_names()
    for table in ("agent_runs", "reports", "diligence_sessions", "engagement_access"):
        _rename_column_if_needed(table, "engagement_id", "project_id")
    tables = _table_names()
    if "engagement_access" in tables and "project_access" not in tables:
        op.rename_table("engagement_access", "project_access")
    tables = _table_names()
    if "engagements" in tables and "projects" not in tables:
        op.rename_table("engagements", "projects")
