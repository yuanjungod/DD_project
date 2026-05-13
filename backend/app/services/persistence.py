from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import AgentRun, AgentStep, AgentStepChatMessage, Evidence, Report


def _attach_run_children(db: Session, project_id: str, run: AgentRun, result: dict) -> None:
    for step in result.get("steps", []):
        db.add(
            AgentStep(
                id=step["id"],
                run_id=run.id,
                agent=step["agent"],
                status=step["status"],
                summary=step.get("summary", ""),
                result=step.get("result") or {},
            )
        )

    for item in result.get("evidence", []):
        db.add(
            Evidence(
                id=item["id"],
                run_id=run.id,
                project_id=project_id,
                title=item["title"],
                source_type=item["source_type"],
                source_url=item.get("source_url"),
                file_id=item.get("file_id"),
                excerpt=item["excerpt"],
                confidence=item["confidence"],
                collected_by=item["collected_by"],
                metadata_json=item.get("metadata", {}),
            )
        )

    report = result.get("report")
    if report:
        db.add(
            Report(
                project_id=project_id,
                run_id=run.id,
                title=report["title"],
                executive_summary=report["executive_summary"],
                overall_risk=report["overall_risk"],
                sections=report.get("sections", []),
            )
        )


def _clear_run_derived_records(db: Session, run_id: str) -> None:
    """Remove persisted steps/evidence/report for a run so finalize can replay agent truth."""
    db.query(AgentStep).filter(AgentStep.run_id == run_id).delete(synchronize_session=False)
    db.query(Evidence).filter(Evidence.run_id == run_id).delete(synchronize_session=False)
    report = db.query(Report).filter(Report.run_id == run_id).first()
    if report is not None:
        db.delete(report)


def persist_run_result(db: Session, project_id: str, result: dict) -> AgentRun:
    run = AgentRun(
        id=result["run_id"],
        project_id=project_id,
        session_id=None,
        attempt_index=1,
        status=result["status"],
        completed_at=datetime.utcnow() if result["status"] == "completed" else None,
        raw_result=result,
    )
    db.add(run)

    _attach_run_children(db, project_id, run, result)

    db.commit()
    db.refresh(run)
    return run


def create_pending_agent_run(
    db: Session,
    project_id: str,
    run_id: str,
    *,
    session_id: str | None = None,
    attempt_index: int = 1,
) -> AgentRun:
    run = AgentRun(
        id=run_id,
        project_id=project_id,
        session_id=session_id,
        attempt_index=attempt_index,
        status="running",
        raw_result={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finalize_agent_run(db: Session, project_id: str, run_id: str, result: dict) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise ValueError(f"AgentRun {run_id} not found")
    run.status = result["status"]
    run.completed_at = datetime.utcnow() if result["status"] == "completed" else None
    run.raw_result = result
    _clear_run_derived_records(db, run_id)
    _attach_run_children(db, project_id, run, result)
    db.commit()
    db.refresh(run)
    return run


def upsert_incremental_run_progress(
    db: Session,
    *,
    run_id: str,
    project_id: str,
    step_payload: dict,
    evidence_delta: list[dict],
) -> None:
    """Apply one step update and optional evidence upserts from agent-service callbacks."""
    run = db.get(AgentRun, run_id)
    if run is None or run.project_id != project_id:
        raise ValueError("Run not found or project mismatch")

    result_val = step_payload.get("result") or {}
    if not isinstance(result_val, dict):
        result_val = {}

    step_id = step_payload["id"]
    existing = db.get(AgentStep, step_id)
    if existing:
        if existing.run_id != run_id:
            raise ValueError("Step id bound to another run")
        existing.agent = step_payload["agent"]
        existing.status = step_payload["status"]
        existing.summary = step_payload.get("summary", "")
        existing.result = result_val
    else:
        db.add(
            AgentStep(
                id=step_id,
                run_id=run_id,
                agent=step_payload["agent"],
                status=step_payload["status"],
                summary=step_payload.get("summary", ""),
                result=result_val,
            )
        )

    for raw in evidence_delta:
        eid = raw["id"]
        metadata = raw.get("metadata", {})
        row = db.get(Evidence, eid)
        fields = {
            "title": raw["title"],
            "source_type": raw["source_type"],
            "source_url": raw.get("source_url"),
            "file_id": raw.get("file_id"),
            "excerpt": raw["excerpt"],
            "confidence": float(raw["confidence"]),
            "collected_by": raw["collected_by"],
            "metadata_json": metadata if isinstance(metadata, dict) else {},
        }
        if row:
            if row.run_id != run_id:
                raise ValueError("Evidence id bound to another run")
            row.project_id = project_id
            for key, val in fields.items():
                setattr(row, key, val)
        else:
            db.add(
                Evidence(
                    id=eid,
                    run_id=run_id,
                    project_id=project_id,
                    **fields,
                )
            )

    db.commit()


def append_agent_step_chat_message(db: Session, *, step_id: str, role: str, content: str) -> AgentStepChatMessage:
    row = AgentStepChatMessage(step_id=step_id, role=role, content=content)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mark_agent_run_failed(db: Session, run_id: str, message: str) -> AgentRun | None:
    run = db.get(AgentRun, run_id)
    if run is None:
        return None
    run.status = "failed"
    run.completed_at = datetime.utcnow()
    run.raw_result = {"error": message}
    db.commit()
    db.refresh(run)
    return run
