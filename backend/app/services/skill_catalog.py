from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from app.models.entities import new_id
from app.schemas.dto import SkillPackageCreate, SkillPackageUpdate
from app.services.catalog_records import SkillPackageRecord
from app.services.skill_files import load_skill_packages_from_disk, sync_skill_package_to_disk


def list_skill_packages(*, only_enabled: bool = False) -> list[SkillPackageRecord]:
    rows = load_skill_packages_from_disk()
    if only_enabled:
        rows = [row for row in rows if row.enabled]
    return sorted(rows, key=lambda row: row.name.lower())


def get_skill_package(skill_id: str) -> SkillPackageRecord:
    for row in load_skill_packages_from_disk():
        if row.id == skill_id:
            return row
    raise HTTPException(status_code=404, detail="Skill package not found")


def create_skill_package(payload: SkillPackageCreate) -> SkillPackageRecord:
    payload = ensure_unique_skill_catalog_fields(payload)
    now = datetime.utcnow()
    record = SkillPackageRecord(
        id=payload.id or new_id("skill_pkg"),
        name=payload.name,
        description=payload.description,
        directory_name=payload.directory_name,
        skill_md=payload.skill_md,
        package_files=dict(payload.package_files or {}),
        resources_manifest=dict(payload.resources_manifest or {}),
        enabled=payload.enabled,
        created_at=now,
        updated_at=now,
    )
    sync_skill_package_to_disk(record)
    return record


def update_skill_package(skill_id: str, payload: SkillPackageUpdate) -> SkillPackageRecord:
    record = get_skill_package(skill_id)
    previous_directory_name = record.directory_name
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(record, key, value)
    record.updated_at = datetime.utcnow()
    sync_skill_package_to_disk(record, previous_directory_name=previous_directory_name)
    return record


def ensure_unique_skill_catalog_fields(payload: SkillPackageCreate) -> SkillPackageCreate:
    existing = load_skill_packages_from_disk()
    names = {row.name for row in existing}
    directories = {row.directory_name for row in existing}

    name = payload.name
    base_name = name
    suffix = 2
    while name in names:
        name = f"{base_name}-{suffix}"
        suffix += 1

    dname = payload.directory_name
    base_d = dname
    suffix = 2
    while dname in directories:
        dname = f"{base_d}-{suffix}"
        suffix += 1

    if name == payload.name and dname == payload.directory_name:
        return payload
    return payload.model_copy(update={"name": name, "directory_name": dname})


def load_skill_packages_by_ids(skill_package_ids: list[str], *, only_enabled: bool = True) -> list[SkillPackageRecord]:
    wanted = set(skill_package_ids)
    rows = [row for row in load_skill_packages_from_disk() if row.id in wanted]
    if only_enabled:
        rows = [row for row in rows if row.enabled]
    return rows
