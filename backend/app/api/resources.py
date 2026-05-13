from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Project, Resource
from app.schemas import ResourceCreate, ResourceRead


router = APIRouter(prefix="/projects/{project_id}/resources", tags=["resources"])


@router.post("", response_model=ResourceRead)
def create_resource(project_id: str, payload: ResourceCreate, db: Session = Depends(get_db)) -> Resource:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
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
def list_resources(project_id: str, db: Session = Depends(get_db)) -> list[Resource]:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(Resource).filter(Resource.project_id == project_id).order_by(Resource.created_at.desc()).all()
