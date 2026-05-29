"""Rename diligence_sessions table to workflow_sessions."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "002_workflow_sessions"
down_revision: Union[str, None] = "001_engagement_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    bind = op.get_bind()
    return set(inspect(bind).get_table_names())


def upgrade() -> None:
    tables = _table_names()
    if "diligence_sessions" in tables and "workflow_sessions" not in tables:
        op.rename_table("diligence_sessions", "workflow_sessions")


def downgrade() -> None:
    tables = _table_names()
    if "workflow_sessions" in tables and "diligence_sessions" not in tables:
        op.rename_table("workflow_sessions", "diligence_sessions")
