from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.auth import accessible_project_ids, ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import get_db
from app.models.entities import AgentRun, AgentStep, User
from app.schemas import AgentRunRead, AgentStepRead
from app.services.agent_client import AgentServiceClient, AgentServiceError
from app.services.persistence import persist_run_result
from app.services.workflow_snapshots import build_workflow_snapshot


router = APIRouter(tags=["runs"])


@router.post("/projects/{project_id}/runs", response_model=AgentRunRead)
async def start_run(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> AgentRun:
    project = ensure_project_write_access(db, user, project_id)
    workflow_snapshot = build_workflow_snapshot(db, project.company_config)
    client = AgentServiceClient()
    try:
        result = await client.start_run(project.id, project.company_config, workflow_snapshot=workflow_snapshot)
    except AgentServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    result["workflow_snapshot"] = workflow_snapshot
    return persist_run_result(db, project_id=project.id, result=result)


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
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    ensure_project_write_access(db, user, run.project_id)
    return await start_run(project_id=run.project_id, db=db, user=user)
