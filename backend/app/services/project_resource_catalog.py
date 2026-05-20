"""Company-scoped connector resources: YAML under data/projects/<id>/resource_configs/."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.models.entities import new_id
from app.schemas import ResourceConfigCreate, ResourceConfigRead, ResourceConfigUpdate
from app.services.fs_layout import project_resource_configs_dir, project_tree_dir
from app.services.project_uploads_store import unlink_upload_blob

_ID_SAFE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,126}$")


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _load_yaml_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return raw if isinstance(raw, dict) else None


def _coerce_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            pass
    return _utc_now_naive()


def _iter_project_config_files(project_id: str) -> list[Path]:
    root = project_resource_configs_dir(project_id)
    return sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml"))


def _row_to_read(data: dict[str, Any]) -> ResourceConfigRead:
    rid = str(data["id"])
    return ResourceConfigRead(
        id=rid,
        name=str(data.get("name", rid)),
        type=str(data.get("type", "web")),
        description=str(data.get("description", "")),
        connection_config=data.get("connection_config") if isinstance(data.get("connection_config"), dict) else {},
        enabled=bool(data.get("enabled", True)),
        created_at=_coerce_dt(data.get("created_at")),
        updated_at=_coerce_dt(data.get("updated_at")),
        deletable=True,
        builtin_base=False,
    )


def merged_project_resource_index(project_id: str) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for path in _iter_project_config_files(project_id):
        data = _load_yaml_file(path)
        if not data or not data.get("id"):
            continue
        merged[str(data["id"])] = data
    return merged


def list_project_resource_config_reads(project_id: str, *, only_enabled: bool) -> list[ResourceConfigRead]:
    idx = merged_project_resource_index(project_id)
    rows = [_row_to_read(idx[k]) for k in sorted(idx.keys())]
    if only_enabled:
        rows = [r for r in rows if r.enabled]
    return sorted(rows, key=lambda r: r.name.lower())


def load_project_resource_configs_by_ids(project_id: str, resource_ids: list[str]) -> list[ResourceConfigRead]:
    idx = merged_project_resource_index(project_id)
    want = {i for i in resource_ids if i}
    out: list[ResourceConfigRead] = []
    for rid in sorted(want):
        if rid in idx and bool(idx[rid].get("enabled", True)):
            out.append(_row_to_read(idx[rid]))
    return out


def _write_project_config(project_id: str, data: dict[str, Any]) -> None:
    rid = str(data["id"])
    root = project_resource_configs_dir(project_id)
    path = root / f"{rid}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def create_project_resource_config(project_id: str, payload: ResourceConfigCreate) -> ResourceConfigRead:
    rid = (payload.id or "").strip()
    if not rid:
        rid = new_id("cres")
    elif not _ID_SAFE.match(rid):
        raise ValueError("id must match ^[a-zA-Z][a-zA-Z0-9_-]{0,126}$")
    overlay_file = project_resource_configs_dir(project_id) / f"{rid}.yaml"
    if overlay_file.is_file():
        raise FileExistsError(rid)
    now = _utc_now_naive()
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
    _write_project_config(project_id, doc)
    return _row_to_read(doc)


def _maybe_delete_linked_project_file(project_id: str, data: dict[str, Any]) -> None:
    if str(data.get("type")) != "file_store":
        return
    conn = data.get("connection_config")
    if not isinstance(conn, dict):
        return
    fid = str(conn.get("file_id") or "").strip()
    if not fid:
        return
    unlink_upload_blob(project_id, fid)
    from app.services.project_resources_store import delete_file_references_by_file_id  # noqa: PLC0415

    delete_file_references_by_file_id(project_id, fid)


def update_project_resource_config(
    project_id: str, resource_id: str, payload: ResourceConfigUpdate
) -> ResourceConfigRead:
    idx = merged_project_resource_index(project_id)
    if resource_id not in idx:
        raise KeyError(resource_id)
    base = dict(idx[resource_id])
    old_conn = base.get("connection_config") if isinstance(base.get("connection_config"), dict) else {}
    old_file_id = str(old_conn.get("file_id") or "").strip()
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        if k in {"id"}:
            continue
        base[k] = v
    base["updated_at"] = _utc_now_naive()
    base.setdefault("created_at", base.get("created_at", _utc_now_naive()))
    _write_project_config(project_id, base)
    if str(base.get("type")) == "file_store":
        new_conn = base.get("connection_config") if isinstance(base.get("connection_config"), dict) else {}
        new_file_id = str(new_conn.get("file_id") or "").strip()
        if old_file_id and new_file_id and old_file_id != new_file_id:
            unlink_upload_blob(project_id, old_file_id)
            from app.services.project_resources_store import delete_file_references_by_file_id  # noqa: PLC0415

            delete_file_references_by_file_id(project_id, old_file_id)
    return _row_to_read(base)


def delete_project_resource_config(project_id: str, resource_id: str) -> None:
    idx = merged_project_resource_index(project_id)
    if resource_id not in idx:
        raise KeyError(resource_id)
    _maybe_delete_linked_project_file(project_id, idx[resource_id])
    path = project_resource_configs_dir(project_id) / f"{resource_id}.yaml"
    if not path.is_file():
        alt = project_resource_configs_dir(project_id) / f"{resource_id}.yml"
        path = alt if alt.is_file() else path
    try:
        path.unlink()
    except OSError:
        raise


def copy_project_resource_configs_tree(source_project_id: str, target_project_id: str) -> None:
    src = project_resource_configs_dir(source_project_id)
    dst = project_resource_configs_dir(target_project_id)
    if not src.is_dir():
        return
    for path in src.iterdir():
        if path.suffix not in {".yaml", ".yml"}:
            continue
        shutil.copy2(path, dst / path.name)
