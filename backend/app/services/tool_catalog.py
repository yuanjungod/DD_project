from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from app.models.entities import new_id
from app.schemas.dto import ToolConfigCreate, ToolConfigUpdate
from app.services.catalog_records import ToolConfigRecord
from app.services.tool_files import load_tool_configs_from_disk, sync_tool_configs_to_disk


def list_tool_configs(*, only_enabled: bool = False) -> list[ToolConfigRecord]:
    rows = load_tool_configs_from_disk()
    if only_enabled:
        rows = [row for row in rows if row.enabled]
    return sorted(rows, key=lambda row: row.name.lower())


def get_tool_config(tool_id: str) -> ToolConfigRecord:
    for row in load_tool_configs_from_disk():
        if row.id == tool_id:
            return row
    raise HTTPException(status_code=404, detail="Tool config not found")


def create_tool_config(payload: ToolConfigCreate) -> ToolConfigRecord:
    rows = load_tool_configs_from_disk()
    tool_id = payload.id or new_id("tool")
    if any(row.id == tool_id for row in rows):
        raise HTTPException(status_code=409, detail="Tool config id already exists")
    if any(row.name == payload.name for row in rows):
        raise HTTPException(status_code=409, detail="Tool config name already exists")
    now = datetime.utcnow()
    record = ToolConfigRecord(
        id=tool_id,
        name=payload.name,
        description=payload.description,
        implementation=payload.implementation,
        input_schema=dict(payload.input_schema or {}),
        output_schema=dict(payload.output_schema or {}),
        requires_api_key=payload.requires_api_key,
        enabled=payload.enabled,
        created_at=now,
        updated_at=now,
    )
    rows.append(record)
    sync_tool_configs_to_disk(rows)
    return record


def update_tool_config(tool_id: str, payload: ToolConfigUpdate) -> ToolConfigRecord:
    rows = load_tool_configs_from_disk()
    record = next((row for row in rows if row.id == tool_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Tool config not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and any(row.name == updates["name"] and row.id != tool_id for row in rows):
        raise HTTPException(status_code=409, detail="Tool config name already exists")
    for key, value in updates.items():
        setattr(record, key, value)
    record.updated_at = datetime.utcnow()
    sync_tool_configs_to_disk(rows)
    return record


def load_tool_configs_by_ids(tool_ids: list[str], *, only_enabled: bool = True) -> list[ToolConfigRecord]:
    wanted = set(tool_ids)
    rows = [row for row in load_tool_configs_from_disk() if row.id in wanted]
    if only_enabled:
        rows = [row for row in rows if row.enabled]
    return rows
