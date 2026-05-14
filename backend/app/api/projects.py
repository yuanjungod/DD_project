from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import accessible_project_ids, ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import get_db
from app.models.entities import Project, ProjectAccess, User
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_resources_store import append_resources as append_project_resources_fs
from app.services.project_resources_store import delete_project_resources_tree


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> Project:
    project = Project(name=payload.name, company_config=payload.company_config.model_dump())
    db.add(project)
    db.flush()
    db.add(ProjectAccess(project_id=project.id, user_id=user.id, access_role="owner"))
    db.commit()
    append_project_resources_fs(project.id, payload.initial_resources)
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[Project]:
    query = db.query(Project)
    project_ids = accessible_project_ids(db, user)
    if project_ids is not None:
        query = query.filter(Project.id.in_(project_ids))
    return query.order_by(Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> Project:
    return ensure_project_access(db, user, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> Project:
    project = ensure_project_write_access(db, user, project_id)
    if payload.name is not None:
        project.name = payload.name
    if payload.company_config is not None:
        project.company_config = payload.company_config.model_dump()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> None:
    project = ensure_project_write_access(db, user, project_id)
    pid = project.id
    db.delete(project)
    db.commit()
    delete_project_resources_tree(pid)
