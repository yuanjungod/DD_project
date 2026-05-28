"""Resolve repository root and writable data directory for filesystem-backed resources."""

from __future__ import annotations

import json
import tempfile
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


def dd_project_project_home(project_id: str) -> Path:
    d = engagement_tree_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _engagement_index_path() -> Path:
    p = dd_flow_home_dir() / "engagement_index.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".eng_index_", suffix=".tmp")
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


def _load_engagement_index() -> dict[str, dict[str, str]]:
    p = _engagement_index_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for eid, row in data.items():
        if not isinstance(eid, str) or not isinstance(row, dict):
            continue
        uid = str(row.get("user_id") or "").strip()
        wid = str(row.get("workflow_id") or "").strip()
        if uid and wid:
            out[eid] = {"user_id": uid, "workflow_id": wid}
    return out


def _save_engagement_index(index: dict[str, dict[str, str]]) -> None:
    _atomic_write(_engagement_index_path(), json.dumps(index, ensure_ascii=False, indent=2) + "\n")


def register_engagement_tree(engagement_id: str, user_id: str, workflow_id: str) -> None:
    eid = str(engagement_id or "").strip()
    uid = str(user_id or "").strip()
    wid = str(workflow_id or "").strip() or "_default_workflow"
    if not eid or not uid:
        return
    idx = _load_engagement_index()
    idx[eid] = {"user_id": uid, "workflow_id": wid}
    _save_engagement_index(idx)


def _lookup_engagement_tree(engagement_id: str) -> tuple[str, str]:
    idx = _load_engagement_index()
    row = idx.get(engagement_id)
    if row:
        return row["user_id"], row["workflow_id"]
    # Legacy fallback keeps existing operations working for old rows.
    return "_unknown_user", "_unknown_workflow"


def engagement_tree_dir(engagement_id: str) -> Path:
    uid, wid = _lookup_engagement_tree(engagement_id)
    d = dd_flow_users_dir() / uid / wid / engagement_id
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
