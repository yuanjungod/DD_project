"""Run/session storage under repository .dd_project/users/{user}/{workflow_template}/{engagement}/."""

from __future__ import annotations

import re
from pathlib import Path

from agent_service.settings import get_agent_settings

_WORKFLOW_TEMPLATE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_ID_SAFE = re.compile(r"^[a-zA-Z0-9_-]{1,160}$")
_WORKFLOW_TEMPLATE_FILENAMES = ("workflow_template.yaml",)


def _workflow_template_yaml_in(directory: Path) -> Path | None:
    for filename in _WORKFLOW_TEMPLATE_FILENAMES:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def _validate_id(seg: str, label: str) -> str:
    if not _ID_SAFE.fullmatch(seg):
        raise ValueError(f"Invalid {label} for session storage (only [a-zA-Z0-9_-], max 160 chars)")
    return seg


def _validate_workflow_template_id(workflow_template_id: str) -> str:
    if not _WORKFLOW_TEMPLATE_ID_PATTERN.fullmatch(workflow_template_id):
        raise ValueError("Invalid workflow_template_id for session storage")
    return workflow_template_id


def _repo_root() -> Path:
    return get_agent_settings().repo_root


def dd_project_root() -> Path:
    base = _repo_root() / ".dd_project"
    base.mkdir(parents=True, exist_ok=True)
    return base


def projects_root() -> Path:
    # Compatibility helper name: returns user-root under runtime.
    base = dd_project_root() / "users"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _engagement_root(project_id: str, user_id: str, workflow_template_id: str) -> Path:
    safe_proj = _validate_id(project_id, "project_id")
    safe_user = _validate_id(user_id, "user_id")
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    base = projects_root() / safe_user / safe_workflow_template / safe_proj
    base.mkdir(parents=True, exist_ok=True)
    return base


def _session_runs_root(project_id: str, user_id: str, workflow_template_id: str, session_id: str) -> Path:
    safe_session = _validate_id(session_id, "session_id")
    base = _engagement_root(project_id, user_id, workflow_template_id) / "sessions" / safe_session / "runs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def workflow_templates_root() -> Path:
    base = dd_project_root() / "users"
    base.mkdir(parents=True, exist_ok=True)
    return base


def builtin_workflow_templates_root() -> Path:
    base = _repo_root() / "catalog" / "workflow_templates"
    base.mkdir(parents=True, exist_ok=True)
    return base


def workflow_template_home(workflow_template_id: str) -> Path:
    """Canonical workflow template folder containing workflow YAML and agents/."""
    safe = _validate_workflow_template_id(workflow_template_id)
    users_root = workflow_templates_root()
    catalog_dir = builtin_workflow_templates_root() / safe
    for user_dir in users_root.iterdir():
        if not user_dir.is_dir():
            continue
        data_dir = user_dir / "_workflows" / safe
        if _workflow_template_yaml_in(data_dir) is not None:
            return data_dir
    if _workflow_template_yaml_in(catalog_dir) is not None:
        return catalog_dir
    raise FileNotFoundError(workflow_template_id)


def workflow_template_runs_root(
    workflow_template_id: str,
    user_id: str,
    project_id: str,
    session_id: str,
) -> Path:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    directory = _session_runs_root(project_id, user_id, safe_workflow_template, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def session_json_path(
    workflow_template_id: str,
    user_id: str,
    project_id: str,
    run_id: str,
    session_id: str,
) -> Path:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    safe_run = _validate_id(run_id, "run_id")
    return workflow_template_runs_root(safe_workflow_template, user_id, project_id, session_id) / f"{safe_run}.json"


def list_session_files(workflow_template_id: str, user_id: str, project_id: str) -> list[str]:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_proj = _validate_id(project_id, "project_id")
    root = projects_root() / safe_user / safe_workflow_template / safe_proj / "sessions"
    if not root.is_dir():
        return []
    out: set[str] = set()
    for session_dir in root.iterdir():
        folder = session_dir / "runs" / safe_workflow_template
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            out.add(path.stem)
    return sorted(out)


def list_session_project_ids(workflow_template_id: str, user_id: str) -> list[str]:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    safe_user = _validate_id(user_id, "user_id")
    out: set[str] = set()
    engagements_root = projects_root() / safe_user / safe_workflow_template
    if not engagements_root.is_dir():
        return []
    for project_dir in engagements_root.iterdir():
        if not project_dir.is_dir():
            continue
        sessions_root = project_dir / "sessions"
        if not sessions_root.is_dir():
            continue
        for session_dir in sessions_root.iterdir():
            if (session_dir / "runs").is_dir():
                out.add(project_dir.name)
                break
    return sorted(out)


def list_session_user_ids(workflow_template_id: str) -> list[str]:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    out: set[str] = set()
    for user_dir in projects_root().iterdir():
        if not user_dir.is_dir():
            continue
        engagements_root = user_dir / safe_workflow_template
        if not engagements_root.is_dir():
            continue
        for engagement_dir in engagements_root.iterdir():
            sessions_root = engagement_dir / "sessions"
            if sessions_root.is_dir() and any((s / "runs").is_dir() for s in sessions_root.iterdir()):
                out.add(user_dir.name)
                break
    return sorted(out)


def list_session_workflow_template_ids() -> list[str]:
    ids: set[str] = set()
    for user_dir in projects_root().iterdir():
        for workflow_dir in user_dir.iterdir():
            if not workflow_dir.is_dir():
                continue
            name = workflow_dir.name
            if _WORKFLOW_TEMPLATE_ID_PATTERN.fullmatch(name):
                ids.add(name)
    return sorted(ids)


def find_session_json_path(workflow_template_id: str, user_id: str, project_id: str, run_id: str) -> Path | None:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_proj = _validate_id(project_id, "project_id")
    safe_run = _validate_id(run_id, "run_id")
    root = projects_root() / safe_user / safe_workflow_template / safe_proj / "sessions"
    if not root.is_dir():
        return None
    for session_dir in root.iterdir():
        candidate = session_dir / "runs" / safe_workflow_template / f"{safe_run}.json"
        if candidate.is_file():
            return candidate
    return None
