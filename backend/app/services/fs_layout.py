"""Resolve repository root and writable data directory for filesystem-backed resources."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings

# backend/app/services/fs_layout.py → parents[3] == repository root (contains catalog/)
_REPO_ROOT = Path(__file__).resolve().parents[3]


def repo_root() -> Path:
    return _REPO_ROOT


def data_root() -> Path:
    p = Path(settings.filesystem_data_root)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p.resolve()


def builtin_resource_configs_dir() -> Path:
    return _REPO_ROOT / "catalog" / "resource_configs"


def platform_resource_configs_overlay_dir() -> Path:
    d = data_root() / "platform" / "resource_configs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_tree_dir(project_id: str) -> Path:
    d = data_root() / "projects" / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_resources_manifest_path(project_id: str) -> Path:
    p = project_tree_dir(project_id) / "resources" / "manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def project_uploads_dir(project_id: str) -> Path:
    """Binary blobs for uploaded files (file_id → single file under this directory)."""
    d = project_tree_dir(project_id) / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def legacy_migration_sentinel_path() -> Path:
    return data_root() / ".migrated_resources_from_sqlite_v1"


def platform_uploads_dir() -> Path:
    """Shared library blobs (not tied to a single project application)."""
    d = data_root() / "platform" / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def platform_uploads_manifest_path() -> Path:
    p = data_root() / "platform" / "uploads_manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
