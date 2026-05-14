"""Project-scoped diligence resources as JSON under data/projects/<id>/resources/."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.entities import new_id
from app.schemas import ResourceCreate, ResourceRead
from app.services.fs_layout import project_resources_manifest_path

_MANIFEST_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_created_at(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _load_raw(project_id: str) -> dict[str, Any]:
    path = project_resources_manifest_path(project_id)
    if not path.is_file():
        return {"version": _MANIFEST_VERSION, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": _MANIFEST_VERSION, "items": []}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"version": _MANIFEST_VERSION, "items": []}
    return data


def _atomic_write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".manifest_", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(text)
        Path(tmp).replace(path)
    except Exception:
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def list_project_resources(project_id: str) -> list[ResourceRead]:
    raw = _load_raw(project_id)
    out: list[ResourceRead] = []
    for row in raw["items"]:
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                ResourceRead(
                    id=str(row["id"]),
                    project_id=str(row["project_id"]),
                    type=str(row["type"]),
                    value=str(row.get("value", "")),
                    metadata_json=row.get("metadata_json") if isinstance(row.get("metadata_json"), dict) else {},
                    created_at=_parse_created_at(str(row["created_at"])),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda r: r.created_at, reverse=True)
    return out


def project_resource_records_for_merge(project_id: str) -> list[dict[str, Any]]:
    """Plain dicts for company_config_merge (compatible with prior ORM row access)."""
    raw = _load_raw(project_id)
    items: list[dict[str, Any]] = []
    for row in raw.get("items", []):
        if isinstance(row, dict) and row.get("id"):
            items.append(
                {
                    "id": str(row["id"]),
                    "type": str(row.get("type", "")),
                    "value": str(row.get("value", "")),
                    "metadata_json": row.get("metadata_json") if isinstance(row.get("metadata_json"), dict) else {},
                    "created_at": row.get("created_at", ""),
                }
            )
    items.sort(key=lambda r: str(r.get("created_at", "")))
    return items


def add_resource(project_id: str, payload: ResourceCreate) -> ResourceRead:
    raw = _load_raw(project_id)
    items = list(raw.get("items", []))
    rid = new_id("res")
    now = _utc_now_iso()
    row = {
        "id": rid,
        "project_id": project_id,
        "type": payload.type,
        "value": payload.value,
        "metadata_json": dict(payload.metadata_json or {}),
        "created_at": now,
    }
    items.append(row)
    path = project_resources_manifest_path(project_id)
    blob = {"version": _MANIFEST_VERSION, "items": items}
    _atomic_write(path, json.dumps(blob, ensure_ascii=False, indent=2) + "\n")
    return ResourceRead(
        id=rid,
        project_id=project_id,
        type=payload.type,
        value=payload.value,
        metadata_json=row["metadata_json"],
        created_at=_parse_created_at(now),
    )


def append_resources(project_id: str, payloads: list[ResourceCreate]) -> None:
    if not payloads:
        return
    raw = _load_raw(project_id)
    items = list(raw.get("items", []))
    for payload in payloads:
        rid = new_id("res")
        items.append(
            {
                "id": rid,
                "project_id": project_id,
                "type": payload.type,
                "value": payload.value,
                "metadata_json": dict(payload.metadata_json or {}),
                "created_at": _utc_now_iso(),
            }
        )
    path = project_resources_manifest_path(project_id)
    blob = {"version": _MANIFEST_VERSION, "items": items}
    _atomic_write(path, json.dumps(blob, ensure_ascii=False, indent=2) + "\n")


def delete_resource(project_id: str, resource_id: str) -> bool:
    raw = _load_raw(project_id)
    items_all = raw.get("items", [])
    removed: dict[str, Any] | None = None
    items: list[Any] = []
    for i in items_all:
        if isinstance(i, dict) and str(i.get("id")) == resource_id:
            removed = i
        else:
            items.append(i)
    if removed is None:
        return False
    if str(removed.get("type")) == "file_reference":
        meta = removed.get("metadata_json")
        if isinstance(meta, dict) and meta.get("uploaded_via_platform") is True:
            from app.services.project_uploads_store import unlink_upload_blob  # noqa: PLC0415

            fid = str(removed.get("value") or "").strip()
            if fid:
                unlink_upload_blob(project_id, fid)
    path = project_resources_manifest_path(project_id)
    blob = {"version": _MANIFEST_VERSION, "items": items}
    _atomic_write(path, json.dumps(blob, ensure_ascii=False, indent=2) + "\n")
    return True


def delete_project_resources_tree(project_id: str) -> None:
    """Remove entire project subtree under data/projects/<id>/."""
    base = project_resources_manifest_path(project_id).parent.parent
    try:
        if base.is_dir():
            import shutil

            shutil.rmtree(base, ignore_errors=True)
    except OSError:
        pass
