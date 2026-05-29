from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import AgentStep

_STEP_SEQ_RE = re.compile(r"_step_(\d+)")


def _step_execution_order(step_id: str) -> tuple[int, str]:
    match = _STEP_SEQ_RE.search(step_id or "")
    seq = int(match.group(1)) if match else 0
    return seq, step_id


def completed_slice_for_agent_service(db: Session, run_id: str) -> list[dict[str, Any]]:
    """Serialize ORM rows for agent_service RunRequest.completed_steps."""
    step_rows = (
        db.query(AgentStep)
        .filter(AgentStep.run_id == run_id)
        .order_by(AgentStep.id)
        .all()
    )
    step_rows.sort(key=lambda row: _step_execution_order(row.id))
    steps_payload: list[dict[str, Any]] = []
    for row in step_rows:
        raw = row.result
        steps_payload.append(
            {
                "id": row.id,
                "agent": row.agent,
                "status": row.status,
                "summary": row.summary,
                "result": raw if isinstance(raw, dict) and raw else None,
            }
        )
    return steps_payload


def previous_results_before_step(db: Session, run_id: str, step_id: str) -> list[dict[str, Any]]:
    """AgentResult dicts for steps strictly before step_id in id order."""
    rows = db.query(AgentStep).filter(AgentStep.run_id == run_id).all()
    rows.sort(key=lambda row: _step_execution_order(row.id))
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.id == step_id:
            break
        if isinstance(row.result, dict) and row.result:
            out.append(row.result)
    return out
