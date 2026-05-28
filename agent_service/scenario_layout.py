"""Run/session storage under repository .dd_project/projects/{project}/users/{user}/sessions/{session}/runs/."""

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
    base = dd_project_root() / "projects"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _project_root(project_id: str) -> Path:
    safe_proj = _validate_id(project_id, "project_id")
    base = projects_root() / safe_proj
    base.mkdir(parents=True, exist_ok=True)
    return base


def _session_runs_root(project_id: str, user_id: str, session_id: str) -> Path:
    safe_user = _validate_id(user_id, "user_id")
    safe_session = _validate_id(session_id, "session_id")
    base = _project_root(project_id) / "users" / safe_user / "sessions" / safe_session / "runs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def data_scenarios_root() -> Path:
    base = get_agent_settings().resolved_data_root / "scenarios"
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
    directory = _session_runs_root(project_id, user_id, session_id) / safe_scenario
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
    root = _project_root(safe_proj) / "users" / safe_user / "sessions"
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
    for project_dir in projects_root().iterdir():
        if not project_dir.is_dir():
            continue
        sessions_root = project_dir / "users" / safe_user / "sessions"
        if not sessions_root.is_dir():
            continue
        for session_dir in sessions_root.iterdir():
            if (session_dir / "runs" / safe_scenario).is_dir():
                out.add(project_dir.name)
                break
    return sorted(out)


def list_session_user_ids(scenario_id: str) -> list[str]:
    safe_scenario = _validate_scenario_id(scenario_id)
    out: set[str] = set()
    for project_dir in projects_root().iterdir():
        users_root = project_dir / "users"
        if not users_root.is_dir():
            continue
        for user_dir in users_root.iterdir():
            sessions_root = user_dir / "sessions"
            if not sessions_root.is_dir():
                continue
            for session_dir in sessions_root.iterdir():
                if (session_dir / "runs" / safe_scenario).is_dir():
                    out.add(user_dir.name)
                    break
    return sorted(out)


def list_session_scenario_ids() -> list[str]:
    ids: set[str] = set()
    for project_dir in projects_root().iterdir():
        users_root = project_dir / "users"
        if not users_root.is_dir():
            continue
        for user_dir in users_root.iterdir():
            sessions_root = user_dir / "sessions"
            if not sessions_root.is_dir():
                continue
            for session_dir in sessions_root.iterdir():
                runs_root = session_dir / "runs"
                if not runs_root.is_dir():
                    continue
                for scenario_dir in runs_root.iterdir():
                    name = scenario_dir.name
                    if scenario_dir.is_dir() and _SCENARIO_ID_PATTERN.fullmatch(name):
                        ids.add(name)
    return sorted(ids)


def find_session_json_path(scenario_id: str, user_id: str, project_id: str, run_id: str) -> Path | None:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_proj = _validate_id(project_id, "project_id")
    safe_run = _validate_id(run_id, "run_id")
    root = _project_root(safe_proj) / "users" / safe_user / "sessions"
    if not root.is_dir():
        return None
    for session_dir in root.iterdir():
        candidate = session_dir / "runs" / safe_scenario / f"{safe_run}.json"
        if candidate.is_file():
            return candidate
    return None
