"""Reject duplicate catalog display names (case-insensitive, trimmed)."""

from __future__ import annotations

from typing import Any

from app.exceptions import ConflictError
from shared.catalog_names import catalog_name_key, normalize_catalog_name


def assert_unique_name_in_index(
    index: dict[str, dict[str, Any]],
    name: str,
    *,
    exclude_id: str | None = None,
    label: str = "Name",
) -> None:
    candidate = catalog_name_key(name)
    if not candidate:
        raise ValueError(f"{label} is required")
    for rid, row in index.items():
        if exclude_id and rid == exclude_id:
            continue
        existing = catalog_name_key(str(row.get("name") or ""))
        if existing and existing == candidate:
            raise ConflictError(f"{label} already exists: {normalize_catalog_name(name)}")
