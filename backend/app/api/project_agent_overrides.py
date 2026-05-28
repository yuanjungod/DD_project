from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import get_db
from app.models.entities import User
from app.schemas import ProjectAgentOverrideRead, ProjectAgentOverrideUpsert
from app.services.project_agent_overrides_store import (
    delete_project_agent_override,
    list_project_agent_overrides,
    upsert_project_agent_override,
)

router = APIRouter(prefix="/engagements/{engagement_id}/agent-overrides", tags=["engagement-agent-overrides"])


@router.get("", response_model=list[ProjectAgentOverrideRead])
def list_agent_overrides(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[ProjectAgentOverrideRead]:
    ensure_project_access(db, user, engagement_id)
    return list_project_agent_overrides(engagement_id)


@router.put("/{agent_id}", response_model=ProjectAgentOverrideRead)
def put_agent_override(
    engagement_id: str,
    agent_id: str,
    payload: ProjectAgentOverrideUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> ProjectAgentOverrideRead:
    ensure_project_write_access(db, user, engagement_id)
    if payload.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="Path agent_id must match payload.agent_id")
    return upsert_project_agent_override(engagement_id, payload)


@router.delete("/{agent_id}", status_code=204)
def delete_agent_override(
    engagement_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> None:
    ensure_project_write_access(db, user, engagement_id)
    if not delete_project_agent_override(engagement_id, agent_id):
        raise HTTPException(status_code=404, detail="Agent override not found")
