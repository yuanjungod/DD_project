"""Run/session storage under repository .dd_project/runs/."""

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


def runs_root() -> Path:
    base = dd_project_root() / "runs"
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


def scenario_runs_root(scenario_id: str, user_id: str) -> Path:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_user = _validate_id(user_id, "user_id")
    directory = runs_root() / safe_scenario / safe_user
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def session_json_path(scenario_id: str, user_id: str, project_id: str, run_id: str) -> Path:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_proj = _validate_id(project_id, "project_id")
    safe_run = _validate_id(run_id, "run_id")
    return scenario_runs_root(safe_scenario, safe_user) / safe_proj / f"{safe_run}.json"


def list_session_files(scenario_id: str, user_id: str, project_id: str) -> list[str]:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_user = _validate_id(user_id, "user_id")
    safe_proj = _validate_id(project_id, "project_id")
    folder = scenario_runs_root(safe_scenario, safe_user) / safe_proj
    if not folder.is_dir():
        return []
    return sorted(path.stem for path in folder.glob("*.json"))


def list_session_project_ids(scenario_id: str, user_id: str) -> list[str]:
    safe_scenario = _validate_scenario_id(scenario_id)
    safe_user = _validate_id(user_id, "user_id")
    root = scenario_runs_root(safe_scenario, safe_user)
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def list_session_user_ids(scenario_id: str) -> list[str]:
    safe_scenario = _validate_scenario_id(scenario_id)
    runs_root = scenario_home(safe_scenario) / "runs"
    if not runs_root.is_dir():
        return []
    return sorted(path.name for path in runs_root.iterdir() if path.is_dir())


def list_session_scenario_ids() -> list[str]:
    root = runs_root()
    if not root.is_dir():
        return []
    ids: list[str] = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if not _SCENARIO_ID_PATTERN.fullmatch(child.name):
            continue
        ids.append(child.name)
    return sorted(ids)
