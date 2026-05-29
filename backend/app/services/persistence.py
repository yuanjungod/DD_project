from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import AgentRun, AgentStep, AgentStepChatMessage, Report
from app.services.report_synthesis import synthesize_report_from_steps


def _attach_run_children(db: Session, project_id: str, run: AgentRun, result: dict) -> None:
    steps = result.get("steps", [])
    for step in steps:
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

    report = result.get("report")
    if not report and isinstance(steps, list):
        report = synthesize_report_from_steps(steps)
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
    """Remove persisted steps/report for a run so finalize can replay agent truth."""
    db.query(AgentStep).filter(AgentStep.run_id == run_id).delete(synchronize_session=False)
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
    started_by_user_id: str | None = None,
) -> AgentRun:
    run = AgentRun(
        id=run_id,
        project_id=project_id,
        started_by_user_id=started_by_user_id,
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
) -> None:
    """Apply one step update from agent-service callbacks."""
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
