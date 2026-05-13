from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import AgentStep, Evidence


def completed_slice_for_agent_service(db: Session, run_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Serialize ORM rows for agent_service RunRequest.completed_steps/evidence."""
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

    evid_rows = db.query(Evidence).filter(Evidence.run_id == run_id).order_by(Evidence.id).all()
    evidence_payload: list[dict[str, Any]] = []
    for e in evid_rows:
        evidence_payload.append(
            {
                "id": e.id,
                "title": e.title,
                "source_type": e.source_type,
                "source_url": e.source_url,
                "file_id": e.file_id,
                "excerpt": e.excerpt,
                "confidence": float(e.confidence),
                "collected_by": e.collected_by,
                "metadata": e.metadata_json or {},
            }
        )
    return steps_payload, evidence_payload


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
