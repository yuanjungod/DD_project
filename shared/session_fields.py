"""Workflow session id field names and legacy diligence_session compatibility."""

from __future__ import annotations

from typing import Any

WORKFLOW_SESSION_ID_FIELD = "workflow_session_id"
LEGACY_DILIGENCE_SESSION_ID_FIELD = "diligence_session_id"


def coalesce_workflow_session_id(data: dict[str, Any]) -> str | None:
    primary = str(data.get(WORKFLOW_SESSION_ID_FIELD) or "").strip()
    if primary:
        return primary
    legacy = str(data.get(LEGACY_DILIGENCE_SESSION_ID_FIELD) or "").strip()
    return legacy or None


def dual_write_session_id_fields(session_id: str | None) -> dict[str, str]:
    if not session_id or not str(session_id).strip():
        return {}
    sid = str(session_id).strip()
    return {WORKFLOW_SESSION_ID_FIELD: sid}
