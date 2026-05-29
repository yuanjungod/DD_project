"""Run/session storage under .harness_project/users/{user}/workflows/{workflow_template}/{engagement}/."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from agent_service.settings import get_agent_settings

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.harness_paths import runtime_project_home

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


def harness_project_root() -> Path:
    return runtime_project_home(_repo_root())


def dd_project_root() -> Path:
    """Deprecated alias for harness_project_root()."""
    return harness_project_root()


def users_root() -> Path:
    base = dd_project_root() / "users"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _engagement_root(engagement_id: str, user_id: str, workflow_template_id: str) -> Path:
    safe_engagement = _validate_id(engagement_id, "engagement_id")
    safe_user = _validate_id(user_id, "user_id")
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    base = users_root() / safe_user / "workflows" / safe_workflow_template / safe_engagement
    base.mkdir(parents=True, exist_ok=True)
    return base


def _session_runs_root(engagement_id: str, user_id: str, workflow_template_id: str, session_id: str) -> Path:
    safe_session = _validate_id(session_id, "session_id")
    base = _engagement_root(engagement_id, user_id, workflow_template_id) / "sessions" / safe_session / "runs"
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
    users_root_path = workflow_templates_root()
    catalog_dir = builtin_workflow_templates_root() / safe
    for user_dir in users_root_path.iterdir():
        if not user_dir.is_dir():
            continue
        candidate = user_dir / "workflows" / safe
        if _workflow_template_yaml_in(candidate) is not None:
            return candidate
    if _workflow_template_yaml_in(catalog_dir) is not None:
        return catalog_dir
    raise FileNotFoundError(workflow_template_id)


def workflow_template_runs_root(
    workflow_template_id: str,
    user_id: str,
    engagement_id: str,
    session_id: str,
) -> Path:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    directory = _session_runs_root(engagement_id, user_id, safe_workflow_template, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def session_json_path(
    workflow_template_id: str,
    user_id: str,
    engagement_id: str,
    run_id: str,
    session_id: str,
) -> Path:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    safe_run = _validate_id(run_id, "run_id")
    return workflow_template_runs_root(safe_workflow_template, user_id, engagement_id, session_id) / f"{safe_run}.json"


def _collect_run_ids_from_runs_dir(runs_dir: Path, workflow_template_id: str) -> set[str]:
    """Collect run_id stems from canonical runs/*.json and legacy runs/{workflow_template_id}/*.json."""
    out: set[str] = set()
    if not runs_dir.is_dir():
        return out
    for path in runs_dir.glob("*.json"):
        if path.is_file():
            out.add(path.stem)
    legacy = runs_dir / _validate_workflow_template_id(workflow_template_id)
    if legacy.is_dir():
        for path in legacy.glob("*.json"):
            if path.is_file():
                out.add(path.stem)
    return out


def list_session_files(workflow_template_id: str, user_id: str, engagement_id: str) -> list[str]:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_engagement = _validate_id(engagement_id, "engagement_id")
    root = users_root() / safe_user / "workflows" / safe_workflow_template / safe_engagement / "sessions"
    if not root.is_dir():
        return []
    out: set[str] = set()
    for session_dir in root.iterdir():
        out.update(_collect_run_ids_from_runs_dir(session_dir / "runs", safe_workflow_template))
    return sorted(out)


def list_session_engagement_ids(workflow_template_id: str, user_id: str) -> list[str]:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    safe_user = _validate_id(user_id, "user_id")
    out: set[str] = set()
    engagements_root = users_root() / safe_user / "workflows" / safe_workflow_template
    if not engagements_root.is_dir():
        return []
    for engagement_dir in engagements_root.iterdir():
        if not engagement_dir.is_dir():
            continue
        sessions_root = engagement_dir / "sessions"
        if not sessions_root.is_dir():
            continue
        for session_dir in sessions_root.iterdir():
            if (session_dir / "runs").is_dir():
                out.add(engagement_dir.name)
                break
    return sorted(out)


def list_session_user_ids(workflow_template_id: str) -> list[str]:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    out: set[str] = set()
    for user_dir in users_root().iterdir():
        if not user_dir.is_dir():
            continue
        engagements_root = user_dir / "workflows" / safe_workflow_template
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
    for user_dir in users_root().iterdir():
        workflow_root = user_dir / "workflows"
        if not workflow_root.is_dir():
            continue
        for workflow_dir in workflow_root.iterdir():
            if not workflow_dir.is_dir():
                continue
            name = workflow_dir.name
            if _WORKFLOW_TEMPLATE_ID_PATTERN.fullmatch(name):
                ids.add(name)
    return sorted(ids)


def find_session_json_path(workflow_template_id: str, user_id: str, engagement_id: str, run_id: str) -> Path | None:
    safe_workflow_template = _validate_workflow_template_id(workflow_template_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_engagement = _validate_id(engagement_id, "engagement_id")
    safe_run = _validate_id(run_id, "run_id")
    root = users_root() / safe_user / "workflows" / safe_workflow_template / safe_engagement / "sessions"
    if not root.is_dir():
        return None
    for session_dir in root.iterdir():
        runs_dir = session_dir / "runs"
        candidate = runs_dir / f"{safe_run}.json"
        if candidate.is_file():
            return candidate
        legacy = runs_dir / safe_workflow_template / f"{safe_run}.json"
        if legacy.is_file():
            return legacy
    return None
