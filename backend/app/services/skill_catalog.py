from __future__ import annotations

from datetime import datetime

from app.exceptions import ConflictError, NotFoundError
from shared.catalog_names import names_conflict
from app.models.entities import new_id
from app.schemas.dto import SkillPackageCreate, SkillPackageUpdate
from app.services.catalog_records import SkillPackageRecord
from app.services.skill_files import (
    delete_skill_package_directory,
    load_skill_packages_from_disk,
    sync_skill_package_to_disk,
)


def list_skill_packages(*, only_enabled: bool = False) -> list[SkillPackageRecord]:
    rows = load_skill_packages_from_disk()
    if only_enabled:
        rows = [row for row in rows if row.enabled]
    return sorted(rows, key=lambda row: row.name.lower())


def get_skill_package(skill_id: str) -> SkillPackageRecord:
    needle = skill_id.strip()
    for row in load_skill_packages_from_disk():
        if row.id == needle or row.directory_name == needle:
            return row
    raise NotFoundError("Skill package not found")


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
    if updates.get("name") is not None:
        ensure_unique_skill_name(str(updates["name"]), exclude_id=record.id)
    for key, value in updates.items():
        setattr(record, key, value)
    record.updated_at = datetime.utcnow()
    sync_skill_package_to_disk(record, previous_directory_name=previous_directory_name)
    return record


def delete_skill_package(skill_id: str) -> None:
    record = get_skill_package(skill_id)
    if not delete_skill_package_directory(record.directory_name):
        raise NotFoundError("Skill package not found")


def ensure_unique_skill_name(name: str, *, exclude_id: str | None = None) -> None:
    for row in load_skill_packages_from_disk():
        if exclude_id and row.id == exclude_id:
            continue
        if names_conflict(row.name, name):
            raise ConflictError(f"Skill name already exists: {name.strip()}")


def _allocate_directory_name(requested: str, *, exclude_id: str | None = None) -> str:
    base = str(requested or "").strip() or "skill"
    directories = {
        row.directory_name
        for row in load_skill_packages_from_disk()
        if not exclude_id or row.id != exclude_id
    }
    candidate = base
    suffix = 2
    while candidate in directories:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def ensure_unique_skill_catalog_fields(payload: SkillPackageCreate) -> SkillPackageCreate:
    ensure_unique_skill_name(payload.name)
    directory_name = _allocate_directory_name(payload.directory_name or payload.name)
    if directory_name == payload.directory_name:
        return payload
    return payload.model_copy(update={"directory_name": directory_name})


def load_skill_packages_by_ids(skill_package_ids: list[str], *, only_enabled: bool = True) -> list[SkillPackageRecord]:
    wanted = {str(item).strip() for item in skill_package_ids if str(item or "").strip()}
    rows = [
        row
        for row in load_skill_packages_from_disk()
        if row.id in wanted or row.directory_name in wanted
    ]
    if only_enabled:
        rows = [row for row in rows if row.enabled]
    return rows
