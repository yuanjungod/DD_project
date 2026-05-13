from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.auth import accessible_project_ids, ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import SessionLocal, get_db
from app.models.entities import AgentRun, AgentStep, User
from app.schemas import AgentRunRead, AgentStepRead
from app.services.agent_client import AgentServiceClient
from app.services.persistence import create_pending_agent_run, finalize_agent_run, mark_agent_run_failed
from app.services.workflow_snapshots import build_workflow_snapshot


router = APIRouter(tags=["runs"])


async def _dispatch_agent_background(project_id: str, run_id: str, company_config: dict, workflow_snapshot: dict) -> None:
    await asyncio.to_thread(_execute_agent_pipeline_blocking, project_id, run_id, company_config, workflow_snapshot)


def _execute_agent_pipeline_blocking(
    project_id: str,
    run_id: str,
    company_config: dict,
    workflow_snapshot: dict,
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


@router.post("/projects/{project_id}/runs", response_model=AgentRunRead)
async def start_run(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> AgentRun:
    project = ensure_project_write_access(db, user, project_id)
    workflow_snapshot = build_workflow_snapshot(db, project.company_config)
    run_id = f"run_{uuid4().hex[:12]}"
    create_pending_agent_run(db, project.id, run_id)

    snapshot_dict = dict(workflow_snapshot)
    company_dict = dict(project.company_config)

    loaded = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.evidence), joinedload(AgentRun.report))
        .filter(AgentRun.id == run_id)
        .first()
    )
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to create run")

    background_tasks.add_task(_dispatch_agent_background, project.id, run_id, company_dict, snapshot_dict)
    return loaded


@router.get("/runs", response_model=list[AgentRunRead])
def list_runs(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[AgentRun]:
    query = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.evidence), joinedload(AgentRun.report))
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
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.evidence), joinedload(AgentRun.report))
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
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.evidence), joinedload(AgentRun.report))
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
    ensure_project_write_access(db, user, run.project_id)
    return await start_run(
        project_id=run.project_id,
        background_tasks=background_tasks,
        db=db,
        user=user,
    )
