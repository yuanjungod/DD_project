"""Engagement-scoped Agent override overlays.

These records belong to one concrete application. They are applied to run
snapshots after the workflow template is copied, and never mutate templates.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import EngagementAgentOverrideRead, EngagementAgentOverrideUpsert
from app.services.fs_layout import engagement_agent_overrides_manifest_path

_MANIFEST_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".agent_overrides_", suffix=".tmp")
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


def _load_raw(engagement_id: str) -> dict[str, Any]:
    path = engagement_agent_overrides_manifest_path(engagement_id)
    if not path.is_file():
        return {"version": _MANIFEST_VERSION, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": _MANIFEST_VERSION, "items": []}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"version": _MANIFEST_VERSION, "items": []}
    return data


def _row_to_read(row: dict[str, Any]) -> EngagementAgentOverrideRead:
    payload = {k: v for k, v in row.items() if k != "updated_at"}
    return EngagementAgentOverrideRead(**payload, updated_at=_parse_dt(str(row.get("updated_at") or "")))


def list_engagement_agent_overrides(engagement_id: str) -> list[EngagementAgentOverrideRead]:
    out: list[EngagementAgentOverrideRead] = []
    for row in _load_raw(engagement_id).get("items", []):
        if not isinstance(row, dict):
            continue
        try:
            out.append(_row_to_read(row))
        except (TypeError, ValueError):
            continue
    return sorted(out, key=lambda item: item.agent_id)


def engagement_agent_override_records(engagement_id: str) -> list[dict[str, Any]]:
    return [row.model_dump(mode="json") for row in list_engagement_agent_overrides(engagement_id)]


def upsert_engagement_agent_override(
    engagement_id: str, payload: EngagementAgentOverrideUpsert
) -> EngagementAgentOverrideRead:
    raw = _load_raw(engagement_id)
    now = _utc_now_iso()
    next_row = payload.model_dump(mode="json")
    next_row["updated_at"] = now
    items: list[dict[str, Any]] = []
    replaced = False
    for row in raw.get("items", []):
        if not isinstance(row, dict):
            continue
        if str(row.get("agent_id")) == payload.agent_id:
            items.append(next_row)
            replaced = True
        else:
            items.append(row)
    if not replaced:
        items.append(next_row)
    _atomic_write(
        engagement_agent_overrides_manifest_path(engagement_id),
        json.dumps({"version": _MANIFEST_VERSION, "items": items}, ensure_ascii=False, indent=2) + "\n",
    )
    return _row_to_read(next_row)


def delete_engagement_agent_override(engagement_id: str, agent_id: str) -> bool:
    raw = _load_raw(engagement_id)
    items: list[dict[str, Any]] = []
    removed = False
    for row in raw.get("items", []):
        if not isinstance(row, dict):
            continue
        if str(row.get("agent_id")) == agent_id:
            removed = True
            continue
        items.append(row)
    if not removed:
        return False
    _atomic_write(
        engagement_agent_overrides_manifest_path(engagement_id),
        json.dumps({"version": _MANIFEST_VERSION, "items": items}, ensure_ascii=False, indent=2) + "\n",
    )
    return True
