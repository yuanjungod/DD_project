"""One-shot export from legacy SQLite tables resources / resource_configs into filesystem layout."""

from __future__ import annotations

import json
from typing import Any

import yaml
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.services.fs_layout import legacy_migration_sentinel_path, platform_resource_configs_overlay_dir
from app.services.project_resources_store import _atomic_write, project_resources_manifest_path


def migrate_if_needed(engine, db: Session) -> None:
    sentinel = legacy_migration_sentinel_path()
    if sentinel.exists():
        return
    sentinel.parent.mkdir(parents=True, exist_ok=True)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "resources" in tables:
        try:
            rows = db.execute(
                text("SELECT id, project_id, type, value, metadata_json, created_at FROM resources")
            ).mappings().all()
        except Exception:
            rows = []

        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            pid = str(r["project_id"])
            meta = r.get("metadata_json")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            elif meta is None:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}

            ct = r.get("created_at")
            if ct is not None and hasattr(ct, "isoformat"):
                created_iso = ct.isoformat() + ("Z" if getattr(ct, "tzinfo", None) is None else "")
            else:
                created_iso = str(ct or "").replace("+00:00", "Z") if ct else ""

            grouped.setdefault(pid, []).append(
                {
                    "id": str(r["id"]),
                    "project_id": pid,
                    "type": str(r.get("type", "")),
                    "value": str(r.get("value", "")),
                    "metadata_json": meta,
                    "created_at": created_iso or "1970-01-01T00:00:00Z",
                }
            )

        for pid, items in grouped.items():
            items.sort(key=lambda x: x["created_at"])
            path = project_resources_manifest_path(pid)
            blob = {"version": 1, "items": items}
            _atomic_write(path, json.dumps(blob, ensure_ascii=False, indent=2) + "\n")

    if "resource_configs" in tables:
        try:
            rows = db.execute(
                text(
                    "SELECT id, name, type, description, connection_config, enabled, created_at, updated_at "
                    "FROM resource_configs"
                )
            ).mappings().all()
        except Exception:
            rows = []
        overlay_dir = platform_resource_configs_overlay_dir()
        for r in rows:
            rid = str(r["id"])
            cfg = r.get("connection_config")
            if isinstance(cfg, str):
                try:
                    cfg = json.loads(cfg)
                except json.JSONDecodeError:
                    cfg = {}
            elif cfg is None:
                cfg = {}
            if not isinstance(cfg, dict):
                cfg = {}
            doc: dict[str, Any] = {
                "id": rid,
                "name": str(r.get("name", rid)),
                "type": str(r.get("type", "web")),
                "description": str(r.get("description", "")),
                "connection_config": cfg,
                "enabled": bool(r.get("enabled", True)),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
            }
            path = overlay_dir / f"{rid}.yaml"
            if not path.exists():
                path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    try:
        sentinel.write_text(
            "Migrated SQLite resources/resource_configs once. Delete this file to force re-run export.\n",
            encoding="utf-8",
        )
    except OSError:
        pass
