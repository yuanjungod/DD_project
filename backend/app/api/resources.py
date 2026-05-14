from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import get_db
from app.models.entities import User
from app.schemas import ResourceCreate, ResourceRead
from app.services.project_resources_store import (
    add_resource as add_project_resource_fs,
)
from app.services.project_resources_store import (
    delete_resource as delete_project_resource_fs,
)
from app.services.project_resources_store import list_project_resources

router = APIRouter(prefix="/projects/{project_id}/resources", tags=["resources"])

_RESOURCE_NOT_FOUND = HTTPException(status_code=404, detail="Resource not found")


@router.post("", response_model=ResourceRead)
def create_resource(
    project_id: str,
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> ResourceRead:
    ensure_project_write_access(db, user, project_id)
    return add_project_resource_fs(project_id, payload)


@router.get("", response_model=list[ResourceRead])
def list_resources(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[ResourceRead]:
    ensure_project_access(db, user, project_id)
    return list_project_resources(project_id)


@router.delete("/{resource_id}", status_code=204)
def delete_resource(
    project_id: str,
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> None:
    ensure_project_write_access(db, user, project_id)
    if not delete_project_resource_fs(project_id, resource_id):
        raise _RESOURCE_NOT_FOUND
