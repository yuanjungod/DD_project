from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import get_db
from app.models.entities import Resource, User
from app.schemas import ResourceCreate, ResourceRead


router = APIRouter(prefix="/projects/{project_id}/resources", tags=["resources"])


@router.post("", response_model=ResourceRead)
def create_resource(
    project_id: str,
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> Resource:
    ensure_project_write_access(db, user, project_id)
    resource = Resource(
        project_id=project_id,
        type=payload.type,
        value=payload.value,
        metadata_json=payload.metadata_json,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.get("", response_model=list[ResourceRead])
def list_resources(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[Resource]:
    ensure_project_access(db, user, project_id)
    return db.query(Resource).filter(Resource.project_id == project_id).order_by(Resource.created_at.desc()).all()
