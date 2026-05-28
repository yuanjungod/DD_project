"""Run/session storage under repository .dd_project/users/{user}/{workflow}/{engagement}/."""

from __future__ import annotations

import re
from pathlib import Path

from agent_service.settings import get_agent_settings

_SCENARIO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_ID_SAFE = re.compile(r"^[a-zA-Z0-9_-]{1,160}$")


def _validate_id(seg: str, label: str) -> str:
    if not _ID_SAFE.fullmatch(seg):
        raise ValueError(f"Invalid {label} for session storage (only [a-zA-Z0-9_-], max 160 chars)")
    return seg


def _validate_scenario_id(scenario_id: str) -> str:
    if not _SCENARIO_ID_PATTERN.fullmatch(scenario_id):
        raise ValueError("Invalid scenario_id for session storage")
    return scenario_id


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


def _engagement_root(project_id: str, user_id: str, scenario_id: str) -> Path:
    safe_proj = _validate_id(project_id, "project_id")
    safe_user = _validate_id(user_id, "user_id")
    safe_scenario = _validate_scenario_id(scenario_id)
    base = projects_root() / safe_user / safe_scenario / safe_proj
    base.mkdir(parents=True, exist_ok=True)
    return base


def _session_runs_root(project_id: str, user_id: str, scenario_id: str, session_id: str) -> Path:
    safe_session = _validate_id(session_id, "session_id")
    base = _engagement_root(project_id, user_id, scenario_id) / "sessions" / safe_session / "runs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def data_scenarios_root() -> Path:
    base = dd_project_root() / "_shared" / "workflows"
    base.mkdir(parents=True, exist_ok=True)
    return base


def builtin_scenarios_root() -> Path:
    base = _repo_root() / "catalog" / "scenarios"
    base.mkdir(parents=True, exist_ok=True)
    return base


def scenario_home(scenario_id: str) -> Path:
    """Canonical scenario folder containing scenario.yaml, agents/, and runs/."""
    safe = _validate_scenario_id(scenario_id)
    data_dir = data_scenarios_root() / safe
    catalog_dir = builtin_scenarios_root() / safe
    if (data_dir / "scenario.yaml").is_file():
        return data_dir
    if (catalog_dir / "scenario.yaml").is_file():
        return catalog_dir
    raise FileNotFoundError(scenario_id)


def scenario_runs_root(scenario_id: str, user_id: str, project_id: str, session_id: str) -> Path:
    safe_scenario = _validate_scenario_id(scenario_id)
    directory = _session_runs_root(project_id, user_id, safe_scenario, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def session_json_path(scenario_id: str, user_id: str, project_id: str, run_id: str, session_id: str) -> Path:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_run = _validate_id(run_id, "run_id")
    return scenario_runs_root(safe_scenario, user_id, project_id, session_id) / f"{safe_run}.json"


def list_session_files(scenario_id: str, user_id: str, project_id: str) -> list[str]:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_proj = _validate_id(project_id, "project_id")
    root = projects_root() / safe_user / safe_scenario / safe_proj / "sessions"
    if not root.is_dir():
        return []
    out: set[str] = set()
    for session_dir in root.iterdir():
        folder = session_dir / "runs" / safe_scenario
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            out.add(path.stem)
    return sorted(out)


def list_session_project_ids(scenario_id: str, user_id: str) -> list[str]:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_user = _validate_id(user_id, "user_id")
    out: set[str] = set()
    engagements_root = projects_root() / safe_user / safe_scenario
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


def list_session_user_ids(scenario_id: str) -> list[str]:
    safe_scenario = _validate_scenario_id(scenario_id)
    out: set[str] = set()
    for user_dir in projects_root().iterdir():
        if not user_dir.is_dir():
            continue
        engagements_root = user_dir / safe_scenario
        if not engagements_root.is_dir():
            continue
        for engagement_dir in engagements_root.iterdir():
            sessions_root = engagement_dir / "sessions"
            if sessions_root.is_dir() and any((s / "runs").is_dir() for s in sessions_root.iterdir()):
                out.add(user_dir.name)
                break
    return sorted(out)


def list_session_scenario_ids() -> list[str]:
    ids: set[str] = set()
    for user_dir in projects_root().iterdir():
        for workflow_dir in user_dir.iterdir():
            if not workflow_dir.is_dir():
                continue
            name = workflow_dir.name
            if _SCENARIO_ID_PATTERN.fullmatch(name):
                ids.add(name)
    return sorted(ids)


def find_session_json_path(scenario_id: str, user_id: str, project_id: str, run_id: str) -> Path | None:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_proj = _validate_id(project_id, "project_id")
    safe_run = _validate_id(run_id, "run_id")
    root = projects_root() / safe_user / safe_scenario / safe_proj / "sessions"
    if not root.is_dir():
        return None
    for session_dir in root.iterdir():
        candidate = session_dir / "runs" / safe_scenario / f"{safe_run}.json"
        if candidate.is_file():
            return candidate
    return None
