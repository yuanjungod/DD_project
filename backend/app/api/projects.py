from __future__ import annotations

import copy
import shutil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import accessible_project_ids, ensure_project_access, ensure_project_write_access, require_roles
from app.core.database import get_db
from app.models.entities import Project, ProjectAccess, User
from app.schemas import EngagementCreate, EngagementRead, EngagementUpdate
from app.services.company_identity import company_key_from_name, normalize_application_id
from app.services.platform_uploads_store import copy_platform_uploads_to_project
from app.services.project_agent_overrides_store import project_agent_override_records
from app.services.project_resource_catalog import copy_project_resource_configs_tree
from app.services.project_resources_store import append_resources as append_project_resources_fs
from app.services.project_resources_store import delete_project_resources_tree
from app.services.skill_files import copy_skill_directories_to_project
from app.services.workflow_snapshots import build_workflow_snapshot
from app.services.fs_layout import project_agent_overrides_manifest_path, project_uploads_dir, register_engagement_tree


router = APIRouter(prefix="/engagements", tags=["engagements"])


def _selected_platform_file_ids_from_company_config(company_config: dict) -> list[str]:
    resources = company_config.get("resources", {}) if isinstance(company_config, dict) else {}
    selected: list[str] = []
    selected.extend(resources.get("uploaded_files") or [])
    for scope in resources.get("agent_resource_scopes") or []:
        if not isinstance(scope, dict):
            continue
        raw_ids = scope.get("uploaded_file_ids") or scope.get("file_ids") or []
        if isinstance(raw_ids, str):
            selected.extend(x.strip() for x in raw_ids.split(","))
        elif isinstance(raw_ids, list):
            selected.extend(str(x).strip() for x in raw_ids)
    # de-duplicate while preserving order
    out: list[str] = []
    seen: set[str] = set()
    for file_id in selected:
        fid = str(file_id or "").strip()
        if fid and fid not in seen:
            out.append(fid)
            seen.add(fid)
    return out


def _selected_platform_file_ids_for_engagement_create(payload: EngagementCreate) -> list[str]:
    return _selected_platform_file_ids_from_company_config(payload.company_config.model_dump())


def _selected_skill_directories_from_company_config(company_config: dict) -> list[str]:
    snapshot = build_workflow_snapshot(company_config, project_id=None)
    rows = snapshot.get("skill_packages", [])
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        directory_name = str(row.get("directory_name") or "").strip()
        if directory_name and directory_name not in seen:
            out.append(directory_name)
            seen.add(directory_name)
    return out


def _selected_skill_directories_for_engagement_create(payload: EngagementCreate) -> list[str]:
    return _selected_skill_directories_from_company_config(payload.company_config.model_dump())


def _next_version(db: Session, company_key: str, application_id: str) -> int:
    current = (
        db.query(func.max(Project.version))
        .filter(Project.company_key == company_key, Project.application_id == application_id)
        .scalar()
    )
    return int(current or 0) + 1


@router.post("", response_model=EngagementRead)
def create_engagement(
    payload: EngagementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> Project:
    company_name = payload.company_config.target_company.name
    company_key = company_key_from_name(company_name)
    try:
        application_id = normalize_application_id(payload.application_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    version = payload.version if payload.version and payload.version > 0 else _next_version(db, company_key, application_id)

    exists = (
        db.query(Project.id)
        .filter(
            Project.company_key == company_key,
            Project.application_id == application_id,
            Project.version == version,
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail=f"Application already exists: {company_name} · {application_id} · v{version}",
        )

    engagement = Project(
        name=payload.name,
        company_key=company_key,
        application_id=application_id,
        version=version,
        company_config=payload.company_config.model_dump(),
    )
    db.add(engagement)
    db.flush()
    workflow_id = str(payload.company_config.workflow_template_id or payload.company_config.workflow_id or "").strip() or "_default_workflow"
    register_engagement_tree(engagement.id, user.id, workflow_id)
    db.add(ProjectAccess(project_id=engagement.id, user_id=user.id, access_role="owner"))
    db.commit()
    append_project_resources_fs(engagement.id, payload.initial_resources)
    copy_platform_uploads_to_project(engagement.id, _selected_platform_file_ids_for_engagement_create(payload))
    copy_skill_directories_to_project(engagement.id, _selected_skill_directories_for_engagement_create(payload))
    db.refresh(engagement)
    return engagement


@router.get("", response_model=list[EngagementRead])
def list_engagements(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[Project]:
    query = db.query(Project)
    engagement_ids = accessible_project_ids(db, user)
    if engagement_ids is not None:
        query = query.filter(Project.id.in_(engagement_ids))
    return query.order_by(Project.created_at.desc()).all()


@router.get("/{engagement_id}", response_model=EngagementRead)
def get_engagement(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> Project:
    return ensure_project_access(db, user, engagement_id)


@router.patch("/{engagement_id}", response_model=EngagementRead)
def update_engagement(
    engagement_id: str,
    payload: EngagementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> Project:
    engagement = ensure_project_write_access(db, user, engagement_id)
    cfg0 = engagement.company_config if isinstance(engagement.company_config, dict) else {}
    register_engagement_tree(
        engagement.id,
        user.id,
        str(cfg0.get("workflow_template_id") or cfg0.get("workflow_id") or "_default_workflow"),
    )
    if payload.name is not None:
        engagement.name = payload.name
    if payload.company_config is not None:
        company_config = payload.company_config.model_dump()
        register_engagement_tree(
            engagement.id,
            user.id,
            str(company_config.get("workflow_template_id") or company_config.get("workflow_id") or "_default_workflow"),
        )
        engagement.company_config = company_config
        engagement.company_key = company_key_from_name(payload.company_config.target_company.name)
        copy_platform_uploads_to_project(
            engagement.id,
            _selected_platform_file_ids_from_company_config(company_config),
        )
        copy_skill_directories_to_project(
            engagement.id,
            _selected_skill_directories_from_company_config(company_config),
        )
    if payload.application_id is not None:
        try:
            engagement.application_id = normalize_application_id(payload.application_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(engagement)
    return engagement


@router.post("/{engagement_id}/versions", response_model=EngagementRead)
def clone_engagement_version(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> Project:
    source = ensure_project_write_access(db, user, engagement_id)
    version = _next_version(db, source.company_key, source.application_id)
    company_name = (source.company_config or {}).get("target_company", {}).get("name", source.name)
    clone = Project(
        name=f"{company_name} · {source.application_id} · v{version}",
        company_key=source.company_key,
        application_id=source.application_id,
        version=version,
        company_config=copy.deepcopy(source.company_config),
    )
    db.add(clone)
    db.flush()
    source_cfg = source.company_config if isinstance(source.company_config, dict) else {}
    register_engagement_tree(
        clone.id,
        user.id,
        str(source_cfg.get("workflow_template_id") or source_cfg.get("workflow_id") or "_default_workflow"),
    )
    db.add(ProjectAccess(project_id=clone.id, user_id=user.id, access_role="owner"))
    db.commit()
    db.refresh(clone)

    copy_project_resource_configs_tree(source.id, clone.id)
    src_uploads = project_uploads_dir(source.id)
    dst_uploads = project_uploads_dir(clone.id)
    if src_uploads.is_dir():
        shutil.copytree(src_uploads, dst_uploads, dirs_exist_ok=True)
    src_overrides = project_agent_overrides_manifest_path(source.id)
    if src_overrides.is_file():
        shutil.copy2(src_overrides, project_agent_overrides_manifest_path(clone.id))
    return clone


@router.delete("/{engagement_id}", status_code=204)
def delete_engagement(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> None:
    engagement = ensure_project_write_access(db, user, engagement_id)
    eid = engagement.id
    db.delete(engagement)
    db.commit()
    delete_project_resources_tree(eid)
