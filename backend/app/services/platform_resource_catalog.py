"""Platform connector registry: built-in YAML under repo catalog/ + overlays in data/dd_store/platform/."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.models.entities import new_id
from app.schemas import ResourceConfigCreate, ResourceConfigRead, ResourceConfigUpdate
from app.services.fs_layout import builtin_resource_configs_dir, platform_resource_configs_overlay_dir
from app.services.platform_uploads_store import delete_platform_upload

_ID_SAFE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,126}$")


class BuiltinOnlyResourceConfigError(Exception):
    """DELETE refused: config is shipped only from repo catalog (no data-store overlay)."""


def overlay_file_for_resource_id(resource_id: str) -> Path | None:
    """Return overlay path if present (.yaml or .yml under platform overlay dir)."""
    root = platform_resource_configs_overlay_dir()
    for name in (f"{resource_id}.yaml", f"{resource_id}.yml"):
        path = root / name
        if path.is_file():
            return path
    return None


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


def builtin_resource_ids() -> set[str]:
    """IDs defined in shipped catalog YAML (before overlay merge)."""
    out: set[str] = set()
    for path in _iter_builtin_files():
        data = _load_yaml_file(path)
        if data and data.get("id"):
            out.add(str(data["id"]))
    return out


def _row_to_read(data: dict[str, Any], *, builtin_base: bool) -> ResourceConfigRead:
    rid = str(data["id"])
    overlay = overlay_file_for_resource_id(rid)
    return ResourceConfigRead(
        id=rid,
        name=str(data.get("name", rid)),
        type=str(data.get("type", "web")),
        description=str(data.get("description", "")),
        connection_config=data.get("connection_config") if isinstance(data.get("connection_config"), dict) else {},
        enabled=bool(data.get("enabled", True)),
        created_at=_coerce_dt(data.get("created_at")),
        updated_at=_coerce_dt(data.get("updated_at")),
        deletable=overlay is not None,
        builtin_base=builtin_base,
    )


def _iter_builtin_files() -> list[Path]:
    root = builtin_resource_configs_dir()
    if not root.is_dir():
        return []
    return sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml"))


def _iter_overlay_files() -> list[Path]:
    root = platform_resource_configs_overlay_dir()
    return sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml"))


def merged_resource_config_index() -> dict[str, dict[str, Any]]:
    """Later files (overlay) override by id."""
    merged: dict[str, dict[str, Any]] = {}
    for path in _iter_builtin_files():
        data = _load_yaml_file(path)
        if not data or not data.get("id"):
            continue
        merged[str(data["id"])] = data
    for path in _iter_overlay_files():
        data = _load_yaml_file(path)
        if not data or not data.get("id"):
            continue
        merged[str(data["id"])] = data
    return merged


def list_resource_config_reads(*, only_enabled: bool) -> list[ResourceConfigRead]:
    bid = builtin_resource_ids()
    idx = merged_resource_config_index()
    rows = [_row_to_read(idx[k], builtin_base=(k in bid)) for k in sorted(idx.keys())]
    if only_enabled:
        rows = [r for r in rows if r.enabled]
    return sorted(rows, key=lambda r: r.name.lower())


def load_resource_configs_by_ids(resource_ids: list[str]) -> list[ResourceConfigRead]:
    idx = merged_resource_config_index()
    bid = builtin_resource_ids()
    want = {i for i in resource_ids if i}
    out: list[ResourceConfigRead] = []
    for rid in sorted(want):
        if rid in idx and bool(idx[rid].get("enabled", True)):
            out.append(_row_to_read(idx[rid], builtin_base=(rid in bid)))
    return out


def _write_overlay(data: dict[str, Any]) -> None:
    rid = str(data["id"])
    overlay_dir = platform_resource_configs_overlay_dir()
    path = overlay_dir / f"{rid}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def create_resource_config_overlay(payload: ResourceConfigCreate) -> ResourceConfigRead:
    rid = (payload.id or "").strip()
    if not rid:
        rid = new_id("resource_cfg")
    elif not _ID_SAFE.match(rid):
        raise ValueError("id must match ^[a-zA-Z][a-zA-Z0-9_-]{0,126}$")
    overlay_file = platform_resource_configs_overlay_dir() / f"{rid}.yaml"
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
    _write_overlay(doc)
    bid = builtin_resource_ids()
    return _row_to_read(doc, builtin_base=(rid in bid))


def update_resource_config_overlay(resource_id: str, payload: ResourceConfigUpdate) -> ResourceConfigRead:
    idx = merged_resource_config_index()
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
    _write_overlay(base)
    if str(base.get("type")) == "file_store":
        new_conn = base.get("connection_config") if isinstance(base.get("connection_config"), dict) else {}
        new_file_id = str(new_conn.get("file_id") or "").strip()
        if old_file_id and new_file_id and old_file_id != new_file_id:
            delete_platform_upload(old_file_id)
    bid = builtin_resource_ids()
    return _row_to_read(base, builtin_base=(resource_id in bid))


def _maybe_delete_linked_platform_file(data: dict[str, Any]) -> None:
    if str(data.get("type")) != "file_store":
        return
    conn = data.get("connection_config")
    if not isinstance(conn, dict):
        return
    fid = str(conn.get("file_id") or "").strip()
    if fid:
        delete_platform_upload(fid)


def delete_resource_config_overlay(resource_id: str) -> None:
    """Remove overlay YAML only; built-in-only ids raise BuiltinOnlyResourceConfigError."""
    idx = merged_resource_config_index()
    if resource_id not in idx:
        raise KeyError(resource_id)
    overlay = overlay_file_for_resource_id(resource_id)
    if overlay is None:
        raise BuiltinOnlyResourceConfigError(resource_id)
    _maybe_delete_linked_platform_file(idx[resource_id])
    try:
        overlay.unlink()
    except OSError:
        raise

