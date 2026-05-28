"""Resolve repository root and writable data directory for filesystem-backed resources."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings


def repo_root() -> Path:
    return settings.repo_root


def data_root() -> Path:
    return settings.resolved_data_root


def dd_flow_home_dir() -> Path:
    """Unified runtime home for file-backed config/state management."""
    d = repo_root() / ".dd_project"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dd_flow_config_dir() -> Path:
    d = dd_flow_home_dir() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dd_flow_users_dir() -> Path:
    d = dd_flow_home_dir() / "users"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dd_flow_channels_dir() -> Path:
    d = dd_flow_home_dir() / "channels"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dd_flow_sqlite_dir() -> Path:
    d = dd_flow_home_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dd_project_projects_dir() -> Path:
    d = dd_flow_home_dir() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dd_project_project_home(project_id: str) -> Path:
    d = dd_project_projects_dir() / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def builtin_resource_configs_dir() -> Path:
    return repo_root() / "catalog" / "resource_configs"


def default_users_config_path() -> Path:
    configured = settings.default_users_config_path.strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = repo_root() / path
        return path.resolve()
    return repo_root() / "catalog" / "default_users.yaml"


def platform_resource_configs_overlay_dir() -> Path:
    d = data_root() / "platform" / "resource_configs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_tree_dir(project_id: str) -> Path:
    d = dd_project_project_home(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_resources_manifest_path(project_id: str) -> Path:
    p = project_tree_dir(project_id) / "shared" / "resources" / "manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def project_agent_overrides_manifest_path(project_id: str) -> Path:
    p = project_tree_dir(project_id) / "meta" / "agent_overrides.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def project_resource_configs_dir(project_id: str) -> Path:
    d = project_tree_dir(project_id) / "shared" / "resource_configs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_uploads_dir(project_id: str) -> Path:
    """Binary blobs for uploaded files (file_id → single file under this directory)."""
    d = project_tree_dir(project_id) / "shared" / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_skills_dir(project_id: str) -> Path:
    """Project-local copied skill packages used by mounted runtime."""
    d = project_tree_dir(project_id) / "shared" / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


def platform_uploads_dir() -> Path:
    """Shared library blobs (not tied to a single project application)."""
    d = dd_flow_sqlite_dir() / "platform" / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def platform_uploads_manifest_path() -> Path:
    p = dd_flow_sqlite_dir() / "platform" / "uploads_manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
