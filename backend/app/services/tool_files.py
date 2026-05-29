from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.services.catalog_records import ToolConfigRecord

ROOT = Path(__file__).resolve().parents[3]
TOOLS_YAML = ROOT / "agent_service" / "configs" / "tools.yaml"


def invalidate_tool_configs_disk_cache() -> None:
    _cached_tool_configs.cache_clear()


@lru_cache(maxsize=1)
def _cached_tool_configs() -> tuple[ToolConfigRecord, ...]:
    return tuple(_load_tool_configs_from_disk_uncached())


def load_tool_configs_from_disk() -> list[ToolConfigRecord]:
    """Load tool configs from agent_service/configs/tools.yaml (cached until disk changes)."""
    return list(_cached_tool_configs())


def _load_tool_configs_from_disk_uncached() -> list[ToolConfigRecord]:
    if not TOOLS_YAML.exists():
        return []
    with TOOLS_YAML.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    raw_tools = data.get("tools", {})
    if not isinstance(raw_tools, dict):
        return []
    stat = TOOLS_YAML.stat()
    loaded_at = datetime.utcfromtimestamp(stat.st_mtime)
    rows: list[ToolConfigRecord] = []
    for tool_id, config in sorted(raw_tools.items()):
        cfg = config if isinstance(config, dict) else {}
        rows.append(
            ToolConfigRecord(
                id=str(tool_id),
                name=str(cfg.get("name") or tool_id),
                description=str(cfg.get("description") or ""),
                implementation=str(cfg.get("implementation") or ""),
                input_schema=_dict_or_empty(cfg.get("input_schema")),
                output_schema=_dict_or_empty(cfg.get("output_schema")),
                requires_api_key=bool(cfg.get("requires_api_key", False)),
                enabled=bool(cfg.get("enabled", True)),
                created_at=loaded_at,
                updated_at=loaded_at,
            )
        )
    return rows


def sync_tool_configs_to_disk(tool_configs: list[ToolConfigRecord]) -> Path:
    """Persist tool catalog to agent_service/configs/tools.yaml."""

    TOOLS_YAML.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "tools": {
            tool.id: {
                "name": tool.name,
                "description": tool.description,
                "implementation": tool.implementation,
                "input_schema": tool.input_schema or {},
                "output_schema": tool.output_schema or {},
                "requires_api_key": bool(tool.requires_api_key),
                "enabled": bool(tool.enabled),
            }
            for tool in sorted(tool_configs, key=lambda row: row.id)
        }
    }
    text = yaml.safe_dump(document, sort_keys=False, allow_unicode=True, default_flow_style=False, width=4096)
    header = "# Tool config catalog — file-backed source of truth for the platform.\n\n"
    TOOLS_YAML.write_text(header + text, encoding="utf-8")
    invalidate_tool_configs_disk_cache()
    return TOOLS_YAML


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
