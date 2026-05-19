from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import AgentStep


def completed_slice_for_agent_service(db: Session, run_id: str) -> list[dict[str, Any]]:
    """Serialize ORM rows for agent_service RunRequest.completed_steps."""
    step_rows = db.query(AgentStep).filter(AgentStep.run_id == run_id).order_by(AgentStep.id).all()
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
    rows = db.query(AgentStep).filter(AgentStep.run_id == run_id).order_by(AgentStep.id).all()
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.id == step_id:
            break
        if isinstance(row.result, dict) and row.result:
            out.append(row.result)
    return out
