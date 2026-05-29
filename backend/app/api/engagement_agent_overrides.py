from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import ensure_engagement_access, ensure_engagement_write_access, require_roles
from app.core.database import get_db
from app.models.entities import User
from app.schemas import EngagementAgentOverrideRead, EngagementAgentOverrideUpsert
from app.services.engagement_agent_overrides_store import (
    delete_engagement_agent_override,
    list_engagement_agent_overrides,
    upsert_engagement_agent_override,
)

router = APIRouter(prefix="/engagements/{engagement_id}/agent-overrides", tags=["engagement-agent-overrides"])


@router.get("", response_model=list[EngagementAgentOverrideRead])
def list_agent_overrides(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[EngagementAgentOverrideRead]:
    ensure_engagement_access(db, user, engagement_id)
    return list_engagement_agent_overrides(engagement_id)


@router.put("/{agent_id}", response_model=EngagementAgentOverrideRead)
def put_agent_override(
    engagement_id: str,
    agent_id: str,
    payload: EngagementAgentOverrideUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> EngagementAgentOverrideRead:
    ensure_engagement_write_access(db, user, engagement_id)
    if payload.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="Path agent_id must match payload.agent_id")
    return upsert_engagement_agent_override(engagement_id, payload)


@router.delete("/{agent_id}", status_code=204)
def delete_agent_override(
    engagement_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> None:
    ensure_engagement_write_access(db, user, engagement_id)
    if not delete_engagement_agent_override(engagement_id, agent_id):
        raise HTTPException(status_code=404, detail="Agent override not found")
