from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.entities import AgentRun, AgentStep, Project
from app.schemas import AgentRunRead, AgentStepRead
from app.services.agent_client import AgentServiceClient, AgentServiceError
from app.services.persistence import persist_run_result


router = APIRouter(tags=["runs"])


@router.post("/projects/{project_id}/runs", response_model=AgentRunRead)
async def start_run(project_id: str, db: Session = Depends(get_db)) -> AgentRun:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client = AgentServiceClient()
    try:
        result = await client.start_run(project.id, project.company_config)
    except AgentServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return persist_run_result(db, project_id=project.id, result=result)


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_run(run_id: str, db: Session = Depends(get_db)) -> AgentRun:
    run = (
        db.query(AgentRun)
        .options(joinedload(AgentRun.steps), joinedload(AgentRun.evidence), joinedload(AgentRun.report))
        .filter(AgentRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/steps", response_model=list[AgentStepRead])
def list_run_steps(run_id: str, db: Session = Depends(get_db)) -> list[AgentStep]:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return db.query(AgentStep).filter(AgentStep.run_id == run_id).all()


@router.post("/runs/{run_id}/retry", response_model=AgentRunRead)
async def retry_run(run_id: str, db: Session = Depends(get_db)) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return await start_run(project_id=run.project_id, db=db)
