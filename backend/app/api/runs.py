from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from app.core.auth import accessible_project_ids, ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import SessionLocal, get_db
from app.models.entities import AgentRun, AgentStep, AgentStepChatMessage, DiligenceSession, Project, User
from app.schemas import (
    AgentRunBriefRead,
    AgentRunRead,
    AgentStepRead,
    DiligenceSessionRead,
    StartAgentRunBody,
    StepReviewChatIn,
    StepReviewChatOut,
    StepReviewChatTurnRead,
)
from app.services.agent_client import AgentServiceClient, AgentServiceError
from app.services.agent_run_resume import completed_slice_for_agent_service, previous_results_before_step
from app.services.company_config_merge import merged_company_config_with_project_resources
from app.services.persistence import append_agent_step_chat_message, create_pending_agent_run, finalize_agent_run, mark_agent_run_failed
from app.services.project_resources_store import project_resource_records_for_merge
from app.services.session_context import build_continuation_context, latest_attempt_in_session, next_attempt_index
from app.services.workflow_snapshots import build_workflow_snapshot


router = APIRouter(tags=["runs"])


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


def _read_text_if_exists(path: Path, *, max_chars: int = 20000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...(truncated)"
    return text


def _read_json_if_exists(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_error": f"Invalid JSON file: {path.name}"}


async def _dispatch_agent_background(
    project_id: str,
    run_id: str,
    company_config: dict,
    workflow_snapshot: dict,
    *,
    diligence_session_id: str,
    attempt_index: int,
    continuation_context: dict | None,
    pause_after_each_step: bool,
    resume_from_step_index: int,
    completed_steps: list[dict],
) -> None:
    await asyncio.to_thread(
        _execute_agent_pipeline_blocking,
        project_id,
        run_id,
        company_config,
        workflow_snapshot,
        diligence_session_id=diligence_session_id,
        attempt_index=attempt_index,
        continuation_context=continuation_context,
        pause_after_each_step=pause_after_each_step,
        resume_from_step_index=resume_from_step_index,
        completed_steps=completed_steps,
    )


def _execute_agent_pipeline_blocking(
    project_id: str,
    run_id: str,
    company_config: dict,
    workflow_snapshot: dict,
    *,
    diligence_session_id: str,
    attempt_index: int,
    continuation_context: dict | None,
    pause_after_each_step: bool,
    resume_from_step_index: int,
    completed_steps: list[dict],
) -> None:
    db = SessionLocal()
    client = AgentServiceClient()
    try:
        try:
            result = asyncio.run(
                client.start_run(
                    project_id,
                    company_config,
                    workflow_snapshot=workflow_snapshot,
                    client_run_id=run_id,
                    diligence_session_id=diligence_session_id,
                    attempt_index=attempt_index,
                    continuation_context=continuation_context,
                    pause_after_each_step=pause_after_each_step,
                    resume_from_step_index=resume_from_step_index,
                    completed_steps=completed_steps,
                )
            )
        except Exception as exc:  # noqa: BLE001
            mark_agent_run_failed(db, run_id, str(exc))
            return
        if result.get("run_id") != run_id:
            mark_agent_run_failed(db, run_id, "Agent returned mismatched run_id")
            return
        finalize_agent_run(db, project_id=project_id, run_id=run_id, result=result)
    finally:
        db.close()


@router.get("/projects/{project_id}/diligence-sessions", response_model=list[DiligenceSessionRead])
def list_diligence_sessions(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[DiligenceSessionRead]:
    ensure_project_access(db, user, project_id)
    sessions = (
        db.query(DiligenceSession)
        .options(joinedload(DiligenceSession.runs))
        .filter(DiligenceSession.project_id == project_id)
        .order_by(DiligenceSession.created_at.desc())
        .all()
    )
    out: list[DiligenceSessionRead] = []
    for sess in sessions:
        runs_sorted = sorted(sess.runs, key=lambda r: (r.attempt_index or 1, r.started_at))
        briefs = [AgentRunBriefRead.model_validate(r) for r in runs_sorted]
        out.append(
            DiligenceSessionRead(
                id=sess.id,
                project_id=sess.project_id,
                status=sess.status,
                created_at=sess.created_at,
                updated_at=sess.updated_at,
                runs=briefs,
            )
        )
    return out


async def _execute_start_agent_run(
    *,
    project_id: str,
    db: Session,
    user: User,
    background_tasks: BackgroundTasks,
    body: StartAgentRunBody,
) -> AgentRun:
    """Create session + pending run row and enqueue agent dispatch."""
    project = ensure_project_write_access(db, user, project_id)
    workflow_snapshot = build_workflow_snapshot(project.company_config, project_id=project.id)
    run_id = f"run_{uuid4().hex[:12]}"

    continuation_context: dict | None = None
    diligence_sess: DiligenceSession
    attempt_ix: int

    if body.session_mode == "continue":
        if not body.diligence_session_id:
            raise HTTPException(status_code=400, detail="diligence_session_id required when session_mode is continue")
        diligence_sess = db.get(DiligenceSession, body.diligence_session_id)
        if diligence_sess is None or diligence_sess.project_id != project.id:
            raise HTTPException(status_code=404, detail="Diligence session not found for this project")
        inflight = (
            db.query(AgentRun)
            .filter(AgentRun.session_id == diligence_sess.id, AgentRun.status == "running")
            .first()
        )
        if inflight is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Another attempt is already running for this session ({inflight.id}).",
            )
        prev_run = latest_attempt_in_session(db, diligence_sess.id)
        if prev_run is None:
            raise HTTPException(status_code=400, detail="Session has no previous attempt to continue from")
        continuation_context = build_continuation_context(db, prev_run.id)
        attempt_ix = next_attempt_index(db, diligence_sess.id)
        diligence_sess.updated_at = datetime.utcnow()
        db.add(diligence_sess)
        db.flush()
    else:
        diligence_sess = DiligenceSession(project_id=project.id)
        db.add(diligence_sess)
        db.flush()
        attempt_ix = 1

    create_pending_agent_run(
        db,
        project.id,
        run_id,
        session_id=diligence_sess.id,
        attempt_index=attempt_ix,
    )

    snapshot_dict = dict(workflow_snapshot)
    proj_records = project_resource_records_for_merge(project.id)
    company_dict = merged_company_config_with_project_resources(dict(project.company_config), proj_records)

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
        _dispatch_agent_background,
        project.id,
        run_id,
        company_dict,
        snapshot_dict,
        diligence_session_id=diligence_sess.id,
        attempt_index=attempt_ix,
        continuation_context=continuation_context,
        pause_after_each_step=pause_gate,
        resume_from_step_index=0,
        completed_steps=[],
    )
    return loaded


@router.post("/projects/{project_id}/runs", response_model=AgentRunRead)
async def start_run(
    project_id: str,
    background_tasks: BackgroundTasks,
    body: Annotated[StartAgentRunBody, Depends(parse_start_run_body)],
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> AgentRun:
    return await _execute_start_agent_run(
        project_id=project_id,
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
    project_ids = accessible_project_ids(db, user)
    if project_ids is not None:
        query = query.filter(AgentRun.project_id.in_(project_ids))
    return query.all()


@router.get("/projects/{project_id}/runs", response_model=list[AgentRunRead])
def list_project_runs(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[AgentRun]:
    ensure_project_access(db, user, project_id)
    return (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.report))
        .filter(AgentRun.project_id == project_id)
        .order_by(AgentRun.started_at.desc())
        .all()
    )


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
    ensure_project_access(db, user, run.project_id)
    return run


@router.get("/runs/{run_id}/steps", response_model=list[AgentStepRead])
def list_run_steps(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[AgentStep]:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_project_access(db, user, run.project_id)
    return db.query(AgentStep).filter(AgentStep.run_id == run_id).all()


@router.get("/runs/{run_id}/steps/{step_id}/output-folder")
def get_agent_step_output_folder(
    run_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_project_access(db, user, run.project_id)
    step = db.get(AgentStep, step_id)
    if step is None or step.run_id != run.id:
        raise HTTPException(status_code=404, detail="Step not found for this run")

    result = step.result if isinstance(step.result, dict) else {}
    output_dir = str(result.get("output_dir") or "").strip()
    if not output_dir:
        return {"available": False, "step_id": step.id, "agent": step.agent, "reason": "output_dir is not ready"}

    folder = Path(output_dir).expanduser().resolve()
    if not folder.is_dir():
        return {
            "available": False,
            "step_id": step.id,
            "agent": step.agent,
            "folder_path": str(folder),
            "reason": "output folder does not exist on backend filesystem",
        }

    return {
        "available": True,
        "step_id": step.id,
        "agent": step.agent,
        "folder_path": str(folder),
        "readme_path": str(folder / "README.md"),
        "readme": _read_text_if_exists(folder / "README.md"),
        "result": _read_json_if_exists(folder / "result.json"),
        "resources": _read_json_if_exists(folder / "resources" / "index.json") or {},
        "findings": [
            {"name": path.name, "path": str(path), "content": _read_text_if_exists(path)}
            for path in sorted((folder / "findings").glob("*.md"))
        ],
    }


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
    ensure_project_write_access(db, user, row.project_id)
    if row.session_id is None:
        raise HTTPException(status_code=400, detail="Step-gated mode requires diligence session linkage on this run")
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

    project = db.get(Project, row.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    snapshot = dict(build_workflow_snapshot(project.company_config, project_id=project.id))
    completed_steps_payload = completed_slice_for_agent_service(db, run_id)

    row.status = "running"
    db.commit()

    resume_ix = len(completed_steps_payload)
    attempt_ix = getattr(row, "attempt_index", 1) or 1
    sess_id = row.session_id
    proj_records = project_resource_records_for_merge(project.id)
    company_merged = merged_company_config_with_project_resources(dict(project.company_config), proj_records)
    background_tasks.add_task(
        _dispatch_agent_background,
        row.project_id,
        run_id,
        company_merged,
        snapshot,
        diligence_session_id=sess_id,
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
    ensure_project_write_access(db, user, row.project_id)
    if row.status not in {"paused", "running"}:
        raise HTTPException(
            status_code=400,
            detail="Review chat is available while the run is running or paused for review",
        )

    step = db.get(AgentStep, step_id)
    if step is None or step.run_id != row.id:
        raise HTTPException(status_code=404, detail="Step not found for this run")

    project = db.get(Project, row.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    proj_records = project_resource_records_for_merge(project.id)
    merged_cfg = merged_company_config_with_project_resources(dict(project.company_config), proj_records)

    snapshot = dict(build_workflow_snapshot(project.company_config, project_id=project.id))

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
        "project_id": row.project_id,
        "company_config": merged_cfg,
        "workflow_snapshot": snapshot,
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
    ensure_project_access(db, user, row.project_id)
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
        retry_body = StartAgentRunBody(session_mode="continue", diligence_session_id=run.session_id)
    return await _execute_start_agent_run(
        project_id=run.project_id,
        db=db,
        user=user,
        background_tasks=background_tasks,
        body=retry_body,
    )
