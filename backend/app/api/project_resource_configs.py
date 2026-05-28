from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import get_db
from app.models.entities import User
from app.schemas import ResourceConfigCreate, ResourceConfigRead, ResourceConfigUpdate
from app.services.project_resource_catalog import (
    create_project_resource_config,
    delete_project_resource_config,
    list_project_resource_config_reads,
    update_project_resource_config,
)

router = APIRouter(prefix="/engagements/{engagement_id}/resource-configs", tags=["engagement-resource-configs"])


@router.get("", response_model=list[ResourceConfigRead])
def list_project_resource_configs(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[ResourceConfigRead]:
    ensure_project_access(db, user, engagement_id)
    return list_project_resource_config_reads(engagement_id, only_enabled=user.role != "admin")


@router.post("", response_model=ResourceConfigRead)
def create_project_resource_config_route(
    engagement_id: str,
    payload: ResourceConfigCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> ResourceConfigRead:
    ensure_project_write_access(db, user, engagement_id)
    try:
        return create_project_resource_config(engagement_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Resource config id already exists for this application") from exc


@router.patch("/{resource_id}", response_model=ResourceConfigRead)
def update_project_resource_config_route(
    engagement_id: str,
    resource_id: str,
    payload: ResourceConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> ResourceConfigRead:
    ensure_project_write_access(db, user, engagement_id)
    try:
        return update_project_resource_config(engagement_id, resource_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Resource config not found") from exc


@router.delete("/{resource_id}", status_code=204)
def delete_project_resource_config_route(
    engagement_id: str,
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> None:
    ensure_project_write_access(db, user, engagement_id)
    try:
        delete_project_resource_config(engagement_id, resource_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Resource config not found") from exc
