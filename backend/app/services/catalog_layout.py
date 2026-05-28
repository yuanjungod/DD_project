"""Filesystem layout for the global agent library and per-scenario folders."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.services.fs_layout import dd_flow_home_dir

_SCENARIO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

_BUILTIN_SCENARIO_IDS = frozenset(
    {
        "standard_due_diligence",
        "financial_investment_due_diligence",
        "legal_compliance_due_diligence",
        "market_entry_due_diligence",
    }
)


def repo_root() -> Path:
    return settings.repo_root


def data_root() -> Path:
    return settings.resolved_data_root


def assert_safe_scenario_id(scenario_id: str) -> str:
    if not scenario_id or not _SCENARIO_ID_PATTERN.fullmatch(scenario_id):
        raise ValueError("Invalid scenario id; use alphanumeric, hyphen, underscore only")
    return scenario_id


def global_agents_dir() -> Path:
    directory = repo_root() / "catalog" / "agents"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def global_agent_path(agent_id: str) -> Path:
    assert_safe_scenario_id(agent_id)
    return global_agents_dir() / f"{agent_id}.yaml"


def builtin_scenarios_root() -> Path:
    directory = repo_root() / "catalog" / "scenarios"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def data_scenarios_root() -> Path:
    directory = dd_flow_home_dir() / "_shared" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def is_protected_scenario(scenario_id: str) -> bool:
    return scenario_id in _BUILTIN_SCENARIO_IDS


def scenario_is_builtin(scenario_id: str) -> bool:
    assert_safe_scenario_id(scenario_id)
    return (builtin_scenarios_root() / scenario_id / "scenario.yaml").is_file()


def scenario_config_root(scenario_id: str) -> Path | None:
    assert_safe_scenario_id(scenario_id)
    try:
        return scenario_home(scenario_id)
    except FileNotFoundError:
        return None


def scenario_home(scenario_id: str) -> Path:
    """Canonical scenario folder containing scenario.yaml, agents/, and runs/."""
    assert_safe_scenario_id(scenario_id)
    data_dir = data_scenarios_root() / scenario_id
    catalog_dir = builtin_scenarios_root() / scenario_id
    if (data_dir / "scenario.yaml").is_file():
        return data_dir
    if (catalog_dir / "scenario.yaml").is_file():
        return catalog_dir
    raise FileNotFoundError(scenario_id)


def scenario_config_write_root(scenario_id: str) -> Path:
    """Directory for scenario.yaml and agents/ when creating or updating."""
    assert_safe_scenario_id(scenario_id)
    if is_protected_scenario(scenario_id) or scenario_is_builtin(scenario_id):
        directory = builtin_scenarios_root() / scenario_id
    else:
        directory = data_scenarios_root() / scenario_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def scenario_yaml_path(scenario_id: str) -> Path:
    root = scenario_config_root(scenario_id)
    if root is None:
        raise FileNotFoundError(scenario_id)
    return root / "scenario.yaml"


def scenario_agents_dir(scenario_id: str) -> Path:
    root = scenario_config_root(scenario_id)
    if root is None:
        raise FileNotFoundError(scenario_id)
    directory = root / "agents"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def scenario_agents_write_dir(scenario_id: str) -> Path:
    directory = scenario_config_write_root(scenario_id) / "agents"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def scenario_agent_path(scenario_id: str, agent_id: str) -> Path:
    assert_safe_scenario_id(agent_id)
    return scenario_agents_dir(scenario_id) / f"{agent_id}.yaml"


def scenario_runs_root(scenario_id: str, user_id: str) -> Path:
    assert_safe_scenario_id(scenario_id)
    assert_safe_scenario_id(user_id)
    directory = repo_root() / ".dd_project" / "projects"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def list_scenario_config_dirs() -> list[Path]:
    seen: dict[str, Path] = {}
    for root in (builtin_scenarios_root(), data_scenarios_root()):
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if not _SCENARIO_ID_PATTERN.fullmatch(child.name):
                continue
            if (child / "scenario.yaml").is_file():
                seen[child.name] = child
    return sorted(seen.values(), key=lambda path: path.stat().st_mtime, reverse=True)


def protected_scenario_ids() -> frozenset[str]:
    return _BUILTIN_SCENARIO_IDS
