"""Company-scoped connector resources: YAML under engagement shared/resource_configs/."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from app.models.entities import new_id
from app.schemas import ResourceConfigCreate, ResourceConfigRead, ResourceConfigUpdate
from app.services.catalog_yaml_utils import load_yaml_file, utc_now_naive, write_yaml_file
from app.services.fs_layout import engagement_resource_configs_dir
from app.services.engagement_uploads_store import unlink_upload_blob
from app.services.resource_catalog_common import resource_config_read_from_dict
from shared.platform_resource_types import validate_platform_resource_type

_ID_SAFE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,126}$")


def _iter_engagement_config_files(engagement_id: str) -> list[Path]:
    root = engagement_resource_configs_dir(engagement_id)
    return sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml"))


def _row_to_read(data: dict[str, Any]) -> ResourceConfigRead:
    return resource_config_read_from_dict(data, deletable=True, builtin_base=False)


def merged_engagement_resource_index(engagement_id: str) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for path in _iter_engagement_config_files(engagement_id):
        data = load_yaml_file(path)
        if not data or not data.get("id"):
            continue
        merged[str(data["id"])] = data
    return merged


def list_engagement_resource_config_reads(engagement_id: str, *, only_enabled: bool) -> list[ResourceConfigRead]:
    idx = merged_engagement_resource_index(engagement_id)
    rows = [_row_to_read(idx[k]) for k in sorted(idx.keys())]
    if only_enabled:
        rows = [r for r in rows if r.enabled]
    return sorted(rows, key=lambda r: r.name.lower())


def load_engagement_resource_configs_by_ids(engagement_id: str, resource_ids: list[str]) -> list[ResourceConfigRead]:
    idx = merged_engagement_resource_index(engagement_id)
    want = {i for i in resource_ids if i}
    out: list[ResourceConfigRead] = []
    for rid in sorted(want):
        if rid in idx and bool(idx[rid].get("enabled", True)):
            out.append(_row_to_read(idx[rid]))
    return out


def _write_engagement_config(engagement_id: str, data: dict[str, Any]) -> None:
    rid = str(data["id"])
    write_yaml_file(engagement_resource_configs_dir(engagement_id) / f"{rid}.yaml", data)


def create_engagement_resource_config(engagement_id: str, payload: ResourceConfigCreate) -> ResourceConfigRead:
    validate_platform_resource_type(payload.type)
    rid = (payload.id or "").strip()
    if not rid:
        rid = new_id("cres")
    elif not _ID_SAFE.match(rid):
        raise ValueError("id must match ^[a-zA-Z][a-zA-Z0-9_-]{0,126}$")
    overlay_file = engagement_resource_configs_dir(engagement_id) / f"{rid}.yaml"
    if overlay_file.is_file():
        raise FileExistsError(rid)
    now = utc_now_naive()
    doc = {
        "id": rid,
        "name": payload.name,
        "type": payload.type,
        "description": payload.description,
        "connection_config": dict(payload.connection_config or {}),
        "enabled": payload.enabled,
        "created_at": now,
        "updated_at": now,
    }
    _write_engagement_config(engagement_id, doc)
    return _row_to_read(doc)


def _maybe_delete_linked_engagement_file(engagement_id: str, data: dict[str, Any]) -> None:
    if str(data.get("type")) != "file_store":
        return
    conn = data.get("connection_config")
    if not isinstance(conn, dict):
        return
    fid = str(conn.get("file_id") or "").strip()
    if not fid:
        return
    unlink_upload_blob(engagement_id, fid)
    from app.services.engagement_resources_store import delete_file_references_by_file_id  # noqa: PLC0415

    delete_file_references_by_file_id(engagement_id, fid)


def update_engagement_resource_config(
    engagement_id: str, resource_id: str, payload: ResourceConfigUpdate
) -> ResourceConfigRead:
    idx = merged_engagement_resource_index(engagement_id)
    if resource_id not in idx:
        raise KeyError(resource_id)
    base = dict(idx[resource_id])
    old_conn = base.get("connection_config") if isinstance(base.get("connection_config"), dict) else {}
    old_file_id = str(old_conn.get("file_id") or "").strip()
    updates = payload.model_dump(exclude_unset=True)
    if "type" in updates and updates["type"] is not None:
        validate_platform_resource_type(str(updates["type"]))
    for k, v in updates.items():
        if k in {"id"}:
            continue
        base[k] = v
    base["updated_at"] = utc_now_naive()
    base.setdefault("created_at", base.get("created_at", utc_now_naive()))
    _write_engagement_config(engagement_id, base)
    if str(base.get("type")) == "file_store":
        new_conn = base.get("connection_config") if isinstance(base.get("connection_config"), dict) else {}
        new_file_id = str(new_conn.get("file_id") or "").strip()
        if old_file_id and new_file_id and old_file_id != new_file_id:
            unlink_upload_blob(engagement_id, old_file_id)
            from app.services.engagement_resources_store import delete_file_references_by_file_id  # noqa: PLC0415

            delete_file_references_by_file_id(engagement_id, old_file_id)
    return _row_to_read(base)


def delete_engagement_resource_config(engagement_id: str, resource_id: str) -> None:
    idx = merged_engagement_resource_index(engagement_id)
    if resource_id not in idx:
        raise KeyError(resource_id)
    _maybe_delete_linked_engagement_file(engagement_id, idx[resource_id])
    path = engagement_resource_configs_dir(engagement_id) / f"{resource_id}.yaml"
    if not path.is_file():
        alt = engagement_resource_configs_dir(engagement_id) / f"{resource_id}.yml"
        path = alt if alt.is_file() else path
    try:
        path.unlink()
    except OSError:
        raise


def copy_engagement_resource_configs_tree(source_engagement_id: str, target_engagement_id: str) -> None:
    src = engagement_resource_configs_dir(source_engagement_id)
    dst = engagement_resource_configs_dir(target_engagement_id)
    if not src.is_dir():
        return
    for path in src.iterdir():
        if path.suffix not in {".yaml", ".yml"}:
            continue
        shutil.copy2(path, dst / path.name)
