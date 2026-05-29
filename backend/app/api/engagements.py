from __future__ import annotations

import copy
import shutil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import accessible_engagement_ids, ensure_engagement_access, ensure_engagement_write_access, require_roles
from app.core.database import get_db
from app.models.entities import Engagement, EngagementAccess, User
from app.schemas import EngagementCreate, EngagementRead, EngagementUpdate
from app.services.subject_identity import allocate_application_id, normalize_application_id, subject_key_from_name
from app.services.engagement_resource_catalog import copy_engagement_resource_configs_tree
from app.services.engagement_access import engagement_owner_user_id
from app.services.engagement_resources_store import append_resources as append_engagement_resources_fs
from app.services.fs_layout import (
    delete_engagement_filesystem_tree,
    engagement_agent_overrides_manifest_path,
    engagement_resources_manifest_path,
    engagement_uploads_dir,
    register_engagement_tree,
)
from app.services.platform_uploads_store import copy_platform_uploads_to_engagement
from app.services.skill_files import copy_skill_directories_to_engagement
from app.services.instance_config_store import (
    stored_config_from_create,
    stored_config_from_update,
    subject_name_from_stored,
    workflow_template_id_from_stored,
)
from app.services.workflow_snapshots import build_workflow_snapshot


router = APIRouter(prefix="/engagements", tags=["engagements"])


def _selected_platform_file_ids_from_instance_config(instance_config: dict) -> list[str]:
    resources = instance_config.get("resources", {}) if isinstance(instance_config, dict) else {}
    selected: list[str] = []
    selected.extend(resources.get("uploaded_files") or [])
    for scope in resources.get("agent_resource_scopes") or []:
        if not isinstance(scope, dict):
            continue
        raw_ids = scope.get("uploaded_file_ids") or []
        if isinstance(raw_ids, str):
            selected.extend(x.strip() for x in raw_ids.split(","))
        elif isinstance(raw_ids, list):
            selected.extend(str(x).strip() for x in raw_ids)
    out: list[str] = []
    seen: set[str] = set()
    for file_id in selected:
        fid = str(file_id or "").strip()
        if fid and fid not in seen:
            out.append(fid)
            seen.add(fid)
    return out


def _selected_platform_file_ids_for_engagement_create(payload: EngagementCreate) -> list[str]:
    return _selected_platform_file_ids_from_instance_config(stored_config_from_create(payload))


def _selected_skill_directories_from_instance_config(instance_config: dict) -> list[str]:
    snapshot = build_workflow_snapshot(instance_config, engagement_id=None)
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
    return _selected_skill_directories_from_instance_config(stored_config_from_create(payload))


def _next_version(db: Session, subject_key: str, application_id: str) -> int:
    current = (
        db.query(func.max(Engagement.version))
        .filter(Engagement.subject_key == subject_key, Engagement.application_id == application_id)
        .scalar()
    )
    return int(current or 0) + 1


@router.post("", response_model=EngagementRead)
def create_engagement(
    payload: EngagementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> Engagement:
    stored_config = stored_config_from_create(payload)
    subject_name = subject_name_from_stored(stored_config) or payload.name
    subject_key = subject_key_from_name(subject_name)
    if payload.application_id:
        try:
            application_id = normalize_application_id(payload.application_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        application_id = allocate_application_id()
    version = payload.version if payload.version and payload.version > 0 else _next_version(db, subject_key, application_id)

    exists = (
        db.query(Engagement.id)
        .filter(
            Engagement.subject_key == subject_key,
            Engagement.application_id == application_id,
            Engagement.version == version,
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail=f"Application already exists: {subject_name} · {application_id} · v{version}",
        )

    engagement = Engagement(
        name=payload.name,
        subject_key=subject_key,
        application_id=application_id,
        version=version,
        instance_config=stored_config,
    )
    db.add(engagement)
    db.flush()
    workflow_template_id = workflow_template_id_from_stored(stored_config) or "_default_workflow"
    register_engagement_tree(engagement.id, user.id, workflow_template_id)
    db.add(EngagementAccess(engagement_id=engagement.id, user_id=user.id, access_role="owner"))
    db.commit()
    append_engagement_resources_fs(engagement.id, payload.initial_resources)
    copy_platform_uploads_to_engagement(engagement.id, _selected_platform_file_ids_for_engagement_create(payload))
    copy_skill_directories_to_engagement(engagement.id, _selected_skill_directories_for_engagement_create(payload))
    db.refresh(engagement)
    return engagement


@router.get("", response_model=list[EngagementRead])
def list_engagements(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Engagement]:
    query = db.query(Engagement)
    engagement_ids = accessible_engagement_ids(db, user)
    if engagement_ids is not None:
        query = query.filter(Engagement.id.in_(engagement_ids))
    return query.order_by(Engagement.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{engagement_id}", response_model=EngagementRead)
def get_engagement(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> Engagement:
    return ensure_engagement_access(db, user, engagement_id)


@router.patch("/{engagement_id}", response_model=EngagementRead)
def update_engagement(
    engagement_id: str,
    payload: EngagementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> Engagement:
    engagement = ensure_engagement_write_access(db, user, engagement_id)
    cfg0 = engagement.instance_config if isinstance(engagement.instance_config, dict) else {}
    owner_id = engagement_owner_user_id(db, engagement.id) or user.id
    register_engagement_tree(
        engagement.id,
        owner_id,
        str(cfg0.get("workflow_template_id") or "_default_workflow"),
    )
    if payload.name is not None:
        engagement.name = payload.name
    if payload.instance_config is not None:
        instance_config = stored_config_from_update(payload)
        if instance_config is None:
            raise HTTPException(status_code=400, detail="instance_config required")
        register_engagement_tree(
            engagement.id,
            owner_id,
            str(instance_config.get("workflow_template_id") or "_default_workflow"),
        )
        engagement.instance_config = instance_config
        subject_name = subject_name_from_stored(instance_config)
        if subject_name:
            engagement.subject_key = subject_key_from_name(subject_name)
        copy_platform_uploads_to_engagement(
            engagement.id,
            _selected_platform_file_ids_from_instance_config(instance_config),
        )
        copy_skill_directories_to_engagement(
            engagement.id,
            _selected_skill_directories_from_instance_config(instance_config),
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
) -> Engagement:
    source = ensure_engagement_write_access(db, user, engagement_id)
    version = _next_version(db, source.subject_key, source.application_id)
    subject_name = subject_name_from_stored(source.instance_config if isinstance(source.instance_config, dict) else {}) or source.name
    clone = Engagement(
        name=f"{subject_name} · v{version}",
        subject_key=source.subject_key,
        application_id=source.application_id,
        version=version,
        instance_config=copy.deepcopy(source.instance_config),
    )
    db.add(clone)
    db.flush()
    source_cfg = source.instance_config if isinstance(source.instance_config, dict) else {}
    register_engagement_tree(
        clone.id,
        user.id,
        str(source_cfg.get("workflow_template_id") or "_default_workflow"),
    )
    db.add(EngagementAccess(engagement_id=clone.id, user_id=user.id, access_role="owner"))
    db.commit()
    db.refresh(clone)

    copy_engagement_resource_configs_tree(source.id, clone.id)
    src_manifest = engagement_resources_manifest_path(source.id)
    if src_manifest.is_file():
        dst_manifest = engagement_resources_manifest_path(clone.id)
        dst_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_manifest, dst_manifest)
    src_uploads = engagement_uploads_dir(source.id)
    dst_uploads = engagement_uploads_dir(clone.id)
    if src_uploads.is_dir():
        shutil.copytree(src_uploads, dst_uploads, dirs_exist_ok=True)
    src_overrides = engagement_agent_overrides_manifest_path(source.id)
    if src_overrides.is_file():
        shutil.copy2(src_overrides, engagement_agent_overrides_manifest_path(clone.id))
    return clone


@router.delete("/{engagement_id}", status_code=204)
def delete_engagement(
    engagement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> None:
    engagement = ensure_engagement_write_access(db, user, engagement_id)
    eid = engagement.id
    db.delete(engagement)
    db.commit()
    delete_engagement_filesystem_tree(eid)
