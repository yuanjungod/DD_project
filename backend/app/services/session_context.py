from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.models.entities import AgentRun


def build_continuation_context(db: Session, previous_run_id: str) -> dict[str, Any]:
    """Structured digest from the last completed/failed attempt in a workflow session (for agent prompt)."""
    run = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.report))
        .filter(AgentRun.id == previous_run_id)
        .first()
    )
    if run is None:
        return {}

    steps = sorted(run.steps, key=lambda s: s.id)
    digest: list[dict[str, str]] = []
    for s in steps:
        digest.append({"agent": s.agent, "status": s.status, "summary": (s.summary or "")[:4000]})

    report_excerpt = ""
    if getattr(run, "report", None) is not None and run.report is not None:
        report_excerpt = (run.report.executive_summary or "")[:3500]

    return {
        "previous_run_id": run.id,
        "previous_attempt_index": getattr(run, "attempt_index", 1) or 1,
        "previous_run_status": run.status,
        "step_digests": digest,
        "report_executive_summary_excerpt": report_excerpt or None,
        "note_zh": (
            "以下为本 diligence Session 上一轮 attempt 的摘要（非断点快照）。"
            "本轮仍从零执行完整链路；请在其基础上纠错、补强，避免无理由重复上一轮已确认结论。"
        ),
    }


def latest_attempt_in_session(db: Session, session_id: str) -> AgentRun | None:
    return (
        db.query(AgentRun)
        .filter(AgentRun.session_id == session_id)
        .order_by(AgentRun.attempt_index.desc(), AgentRun.started_at.desc())
        .first()
    )


def next_attempt_index(db: Session, session_id: str) -> int:
    m = db.execute(select(func.max(AgentRun.attempt_index)).where(AgentRun.session_id == session_id)).scalar()
    return (int(m) + 1) if m is not None else 1
