from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import AgentRun, AgentStep, Evidence, Report


def persist_run_result(db: Session, project_id: str, result: dict) -> AgentRun:
    run = AgentRun(
        id=result["run_id"],
        project_id=project_id,
        status=result["status"],
        completed_at=datetime.utcnow() if result["status"] == "completed" else None,
        raw_result=result,
    )
    db.add(run)

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

    db.commit()
    db.refresh(run)
    return run
