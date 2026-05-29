"""Allowed platform resource connector types (file-backed catalog + UI)."""

from __future__ import annotations

PLATFORM_RESOURCE_TYPES: tuple[str, ...] = (
    "file_store",
    "mcp",
    "metrics_platform",
)


def is_allowed_platform_resource_type(value: str) -> bool:
    return str(value or "").strip() in PLATFORM_RESOURCE_TYPES


def validate_platform_resource_type(value: str, *, field: str = "type") -> str:
    normalized = str(value or "").strip()
    if not is_allowed_platform_resource_type(normalized):
        allowed = ", ".join(PLATFORM_RESOURCE_TYPES)
        raise ValueError(f"{field} must be one of: {allowed}")
    return normalized
