"""Shared helpers for platform and project resource config catalogs."""

from __future__ import annotations

from typing import Any

from app.schemas import ResourceConfigRead
from app.services.catalog_yaml_utils import coerce_dt


def resource_config_read_from_dict(
    data: dict[str, Any],
    *,
    deletable: bool,
    builtin_base: bool,
) -> ResourceConfigRead:
    rid = str(data["id"])
    return ResourceConfigRead(
        id=rid,
        name=str(data.get("name", rid)),
        type=str(data.get("type", "web")),
        description=str(data.get("description", "")),
        connection_config=data.get("connection_config") if isinstance(data.get("connection_config"), dict) else {},
        enabled=bool(data.get("enabled", True)),
        created_at=coerce_dt(data.get("created_at")),
        updated_at=coerce_dt(data.get("updated_at")),
        deletable=deletable,
        builtin_base=builtin_base,
    )
