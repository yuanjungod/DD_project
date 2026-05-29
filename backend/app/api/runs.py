from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from app.core.auth import accessible_engagement_ids, ensure_engagement_access, ensure_engagement_write_access, require_roles
from app.core.database import get_db
from app.models.entities import AgentRun, AgentStep, AgentStepChatMessage, Engagement, User, WorkflowSession
from app.schemas import (
    AgentRunBriefRead,
    AgentRunRead,
    AgentStepRead,
    StartAgentRunBody,
    StepReviewChatIn,
    StepReviewChatOut,
    StepReviewChatTurnRead,
    WorkflowSessionRead,
)
from app.services.agent_step_output_files import (
    build_output_folder_zip,
    list_output_files,
    output_dir_from_step_result,
    read_output_file,
    resolve_file_in_folder,
    resolve_output_folder,
)
from app.services.agent_client import AgentServiceClient, AgentServiceError
from app.services.agent_run_resume import completed_slice_for_agent_service, previous_results_before_step
from app.services.persistence import append_agent_step_chat_message, create_pending_agent_run
from app.services.run_agent_context import build_agent_dispatch_context
from app.services.run_dispatch import dispatch_agent_background
from app.services.run_status import resolve_effective_run_status
from app.services.session_context import build_continuation_context, latest_attempt_in_session, next_attempt_index


router = APIRouter(tags=["runs"])


def _agent_run_read(run: AgentRun) -> AgentRunRead:
    effective = resolve_effective_run_status(
        status=run.status,
        steps=run.steps,
        started_at=run.started_at,
        raw_result=run.raw_result if isinstance(run.raw_result, dict) else {},
    )
    read = AgentRunRead.model_validate(run)
    if effective == read.status:
        return read
    return read.model_copy(update={"status": effective})


def _reconcile_stale_run_status(db: Session, run: AgentRun) -> AgentRunRead:
    effective = resolve_effective_run_status(
        status=run.status,
        steps=run.steps,
        started_at=run.started_at,
        raw_result=run.raw_result if isinstance(run.raw_result, dict) else {},
    )
    if run.status == "running" and effective != run.status:
        run.status = effective
        if effective in {"completed", "failed"} and run.completed_at is None:
            run.completed_at = datetime.utcnow()
        db.add(run)
    return _agent_run_read(run)


def _reconcile_run_reads(db: Session, runs: list[AgentRun]) -> list[AgentRunRead]:
    changed = False
    reads: list[AgentRunRead] = []
    for run in runs:
        before = run.status
        reads.append(_reconcile_stale_run_status(db, run))
        if run.status != before:
            changed = True
    if changed:
        db.commit()
    return reads


async def parse_start_run_body(request: Request) -> StartAgentRunBody:
    raw_bytes = await request.body()
    if not raw_bytes or not raw_bytes.strip():
        return StartAgentRunBody()
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Run body must be a JSON object")
    try:
        return StartAgentRunBody.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _load_step_output_folder(step: AgentStep) -> tuple[Path | None, str]:
    output_dir = output_dir_from_step_result(step.result)
    if not output_dir:
        return None, "output_dir is not ready"
    folder = resolve_output_folder(output_dir)
    if folder is None:
        return Path(output_dir).expanduser().resolve(), "output folder does not exist on backend filesystem"
    return folder, ""


def _ensure_step_for_run(db: Session, user: User, run_id: str, step_id: str) -> tuple[AgentRun, AgentStep]:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_engagement_access(db, user, run.engagement_id)
    step = db.get(AgentStep, step_id)
    if step is None or step.run_id != run.id:
        raise HTTPException(status_code=404, detail="Step not found for this run")
    return run, step


def _workflow_session_reads(sessions: list[WorkflowSession]) -> list[WorkflowSessionRead]:
    out: list[WorkflowSessionRead] = []
    for sess in sessions:
        runs_sorted = sorted(sess.runs, key=lambda r: (r.attempt_index or 1, r.started_at))
        briefs = [AgentRunBriefRead.model_validate(r) for r in runs_sorted]
        out.append(
            WorkflowSessionRead(
                id=sess.id,
                engagement_id=sess.engagement_id,
                status=sess.status,
                created_at=sess.created_at,
                updated_at=sess.updated_at,
                runs=briefs,
            )
        )
    return out


@router.get("/engagements/{engagement_id}/workflow-sessions", response_model=list[WorkflowSessionRead])
def list_workflow_sessions(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[WorkflowSessionRead]:
    ensure_engagement_access(db, user, engagement_id)
    sessions = (
        db.query(WorkflowSession)
        .options(joinedload(WorkflowSession.runs))
        .filter(WorkflowSession.engagement_id == engagement_id)
        .order_by(WorkflowSession.created_at.desc())
        .all()
    )
    return _workflow_session_reads(sessions)


async def _execute_start_agent_run(
    *,
    engagement_id: str,
    db: Session,
    user: User,
    background_tasks: BackgroundTasks,
    body: StartAgentRunBody,
) -> AgentRun:
    """Create session + pending run row and enqueue agent dispatch."""
    engagement = ensure_engagement_write_access(db, user, engagement_id)
    dispatch_ctx = build_agent_dispatch_context(engagement)
    run_id = f"run_{uuid4().hex[:12]}"

    continuation_context: dict | None = None
    workflow_sess: WorkflowSession
    attempt_ix: int

    if body.session_mode == "continue":
        if not body.workflow_session_id:
            raise HTTPException(status_code=400, detail="workflow_session_id required when session_mode is continue")
        workflow_sess = db.get(WorkflowSession, body.workflow_session_id)
        if workflow_sess is None or workflow_sess.engagement_id != engagement.id:
            raise HTTPException(status_code=404, detail="Workflow session not found for this engagement")
        inflight = (
            db.query(AgentRun)
            .filter(AgentRun.session_id == workflow_sess.id, AgentRun.status == "running")
            .first()
        )
        if inflight is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Another attempt is already running for this session ({inflight.id}).",
            )
        prev_run = latest_attempt_in_session(db, workflow_sess.id)
        if prev_run is None:
            raise HTTPException(status_code=400, detail="Session has no previous attempt to continue from")
        continuation_context = build_continuation_context(db, prev_run.id)
        attempt_ix = next_attempt_index(db, workflow_sess.id)
        workflow_sess.updated_at = datetime.utcnow()
        db.add(workflow_sess)
        db.flush()
    else:
        workflow_sess = WorkflowSession(engagement_id=engagement.id)
        db.add(workflow_sess)
        db.flush()
        attempt_ix = 1

    create_pending_agent_run(
        db,
        engagement.id,
        run_id,
        session_id=workflow_sess.id,
        attempt_index=attempt_ix,
        started_by_user_id=user.id,
    )

    loaded = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.report))
        .filter(AgentRun.id == run_id)
        .first()
    )
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to create run")

    pause_gate = body.interaction_mode == "step_gated"
    background_tasks.add_task(
        dispatch_agent_background,
        engagement.id,
        run_id,
        user.id,
        dispatch_ctx.company_config,
        dispatch_ctx.workflow_snapshot,
        workflow_session_id=workflow_sess.id,
        attempt_index=attempt_ix,
        continuation_context=continuation_context,
        pause_after_each_step=pause_gate,
        resume_from_step_index=0,
        completed_steps=[],
    )
    return loaded


@router.post("/engagements/{engagement_id}/runs", response_model=AgentRunRead)
async def start_run(
    engagement_id: str,
    background_tasks: BackgroundTasks,
    body: Annotated[StartAgentRunBody, Depends(parse_start_run_body)],
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> AgentRun:
    return await _execute_start_agent_run(
        engagement_id=engagement_id,
        db=db,
        user=user,
        background_tasks=background_tasks,
        body=body,
    )


@router.get("/runs", response_model=list[AgentRunRead])
def list_runs(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[AgentRun]:
    query = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.report))
        .order_by(AgentRun.started_at.desc())
    )
    engagement_ids = accessible_engagement_ids(db, user)
    if engagement_ids is not None:
        query = query.filter(AgentRun.engagement_id.in_(engagement_ids))
    return _reconcile_run_reads(db, query.all())


@router.get("/engagements/{engagement_id}/runs", response_model=list[AgentRunRead])
def list_engagement_runs(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[AgentRun]:
    ensure_engagement_access(db, user, engagement_id)
    runs = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.report))
        .filter(AgentRun.engagement_id == engagement_id)
        .order_by(AgentRun.started_at.desc())
        .all()
    )
    return _reconcile_run_reads(db, runs)


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> AgentRun:
    run = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.report))
        .filter(AgentRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_engagement_access(db, user, run.engagement_id)
    before = run.status
    read = _reconcile_stale_run_status(db, run)
    if run.status != before:
        db.commit()
    return read


@router.get("/runs/{run_id}/steps", response_model=list[AgentStepRead])
def list_run_steps(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[AgentStep]:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_engagement_access(db, user, run.engagement_id)
    return db.query(AgentStep).filter(AgentStep.run_id == run_id).all()


@router.get("/runs/{run_id}/steps/{step_id}/output-folder")
def get_agent_step_output_folder(
    run_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict:
    _, step = _ensure_step_for_run(db, user, run_id, step_id)
    folder, reason = _load_step_output_folder(step)
    if folder is None:
        return {"available": False, "step_id": step.id, "agent": step.agent, "reason": reason}
    if reason:
        return {
            "available": False,
            "step_id": step.id,
            "agent": step.agent,
            "folder_path": str(folder),
            "reason": reason,
        }

    files = list_output_files(folder)
    readme_file = next((item for item in files if item["path"] == "README.md"), None)
    return {
        "available": True,
        "step_id": step.id,
        "agent": step.agent,
        "folder_path": str(folder),
        "readme_path": str(folder / "README.md"),
        "readme": readme_file.get("content", "") if readme_file else "",
        "files": files,
    }


@router.get("/runs/{run_id}/steps/{step_id}/output-folder/file")
def get_agent_step_output_file(
    run_id: str,
    step_id: str,
    path: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict:
    _, step = _ensure_step_for_run(db, user, run_id, step_id)
    folder, reason = _load_step_output_folder(step)
    if folder is None or reason:
        raise HTTPException(status_code=404, detail=reason or "output folder is not available")
    return read_output_file(folder, path)


@router.get("/runs/{run_id}/steps/{step_id}/output-folder/download")
def download_agent_step_output_file(
    run_id: str,
    step_id: str,
    path: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> FileResponse:
    _, step = _ensure_step_for_run(db, user, run_id, step_id)
    folder, reason = _load_step_output_folder(step)
    if folder is None or reason:
        raise HTTPException(status_code=404, detail=reason or "output folder is not available")
    target = resolve_file_in_folder(folder, path)
    return FileResponse(path=target, filename=target.name, media_type="application/octet-stream")


@router.get("/runs/{run_id}/steps/{step_id}/output-folder/export")
def export_agent_step_output_folder(
    run_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> Response:
    _, step = _ensure_step_for_run(db, user, run_id, step_id)
    folder, reason = _load_step_output_folder(step)
    if folder is None or reason:
        raise HTTPException(status_code=404, detail=reason or "output folder is not available")
    payload, filename = build_output_folder_zip(folder)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type="application/zip", headers=headers)


@router.post("/runs/{run_id}/continue-step-gated", response_model=AgentRunRead)
async def continue_step_gated(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> AgentRun:
    row = db.get(AgentRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_engagement_write_access(db, user, row.engagement_id)
    if row.session_id is None:
        raise HTTPException(status_code=400, detail="Step-gated mode requires workflow session linkage on this run")
    if row.status != "paused":
        raise HTTPException(status_code=400, detail="Run is not paused for step review")
    conflict = (
        db.query(AgentRun)
        .filter(
            AgentRun.session_id == row.session_id,
            AgentRun.status == "running",
            AgentRun.id != row.id,
        )
        .first()
    )
    if conflict is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Another attempt is executing in this session ({conflict.id}).",
        )

    engagement = db.get(Engagement, row.engagement_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Engagement not found")

    dispatch_ctx = build_agent_dispatch_context(engagement)
    completed_steps_payload = completed_slice_for_agent_service(db, run_id)

    row.status = "running"
    db.commit()

    resume_ix = len(completed_steps_payload)
    attempt_ix = getattr(row, "attempt_index", 1) or 1
    sess_id = row.session_id
    owner_user_id = row.started_by_user_id or user.id
    background_tasks.add_task(
        dispatch_agent_background,
        row.engagement_id,
        run_id,
        owner_user_id,
        dispatch_ctx.company_config,
        dispatch_ctx.workflow_snapshot,
        workflow_session_id=sess_id,
        attempt_index=int(attempt_ix),
        continuation_context=None,
        pause_after_each_step=True,
        resume_from_step_index=resume_ix,
        completed_steps=completed_steps_payload,
    )

    loaded = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.report))
        .filter(AgentRun.id == run_id)
        .first()
    )
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to reload run")
    return loaded


@router.post("/runs/{run_id}/steps/{step_id}/review-chat", response_model=StepReviewChatOut)
def agent_step_review_chat(
    run_id: str,
    step_id: str,
    body: StepReviewChatIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> StepReviewChatOut:
    msg = body.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")
    row = db.get(AgentRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_engagement_write_access(db, user, row.engagement_id)
    if row.status not in {"paused", "running"}:
        raise HTTPException(
            status_code=400,
            detail="Review chat is available while the run is running or paused for review",
        )

    step = db.get(AgentStep, step_id)
    if step is None or step.run_id != row.id:
        raise HTTPException(status_code=404, detail="Step not found for this run")

    engagement = db.get(Engagement, row.engagement_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Engagement not found")

    dispatch_ctx = build_agent_dispatch_context(engagement)

    append_agent_step_chat_message(db, step_id=step_id, role="user", content=msg)

    turn_rows = (
        db.query(AgentStepChatMessage)
        .filter(AgentStepChatMessage.step_id == step_id)
        .order_by(AgentStepChatMessage.created_at.asc(), AgentStepChatMessage.id.asc())
        .all()
    )
    if not turn_rows or turn_rows[-1].role != "user":
        raise HTTPException(status_code=500, detail="Failed to persist user chat turn")
    prior = [{"role": m.role, "content": m.content} for m in turn_rows[:-1]]

    current_step_payload = {
        "id": step.id,
        "agent": step.agent,
        "status": step.status,
        "summary": step.summary or "",
        "result": step.result if isinstance(step.result, dict) and step.result else None,
    }

    payload = {
        "engagement_id": row.engagement_id,
        "user_id": str(row.started_by_user_id or user.id),
        "workflow_session_id": row.session_id,
        "company_config": dispatch_ctx.company_config,
        "workflow_snapshot": dispatch_ctx.workflow_snapshot,
        "agent_name": step.agent,
        "previous_results": previous_results_before_step(db, row.id, step_id),
        "current_step": current_step_payload,
        "chat_messages": prior,
        "user_message": turn_rows[-1].content,
    }

    client = AgentServiceClient()
    try:
        out = asyncio.run(client.assist_step_review_chat(payload))
    except AgentServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    assistant_text = (out.get("reply") if isinstance(out, dict) else None) or ""
    append_agent_step_chat_message(db, step_id=step_id, role="assistant", content=assistant_text)

    final_rows = (
        db.query(AgentStepChatMessage)
        .filter(AgentStepChatMessage.step_id == step_id)
        .order_by(AgentStepChatMessage.created_at.asc(), AgentStepChatMessage.id.asc())
        .all()
    )
    turns_out = [StepReviewChatTurnRead.model_validate(r) for r in final_rows]
    return StepReviewChatOut(reply=assistant_text, turns=turns_out)


@router.get("/runs/{run_id}/steps/{step_id}/review-chat-turns", response_model=list[StepReviewChatTurnRead])
def list_step_review_chat_turns(
    run_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[StepReviewChatTurnRead]:
    row = db.get(AgentRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_engagement_access(db, user, row.engagement_id)
    step = db.get(AgentStep, step_id)
    if step is None or step.run_id != row.id:
        raise HTTPException(status_code=404, detail="Step not found for this run")
    turn_rows = (
        db.query(AgentStepChatMessage)
        .filter(AgentStepChatMessage.step_id == step_id)
        .order_by(AgentStepChatMessage.created_at.asc(), AgentStepChatMessage.id.asc())
        .all()
    )
    return [StepReviewChatTurnRead.model_validate(r) for r in turn_rows]


@router.post("/runs/{run_id}/retry", response_model=AgentRunRead)
async def retry_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    retry_body = StartAgentRunBody()
    if run.session_id:
        retry_body = StartAgentRunBody(session_mode="continue", workflow_session_id=run.session_id)
    return await _execute_start_agent_run(
        engagement_id=run.engagement_id,
        db=db,
        user=user,
        background_tasks=background_tasks,
        body=retry_body,
    )
