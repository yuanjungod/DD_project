from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


from agent_service.settings import get_agent_settings


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
GLOBAL_AGENTS_DIR = REPO_ROOT / "catalog" / "agents"
BUILTIN_SCENARIOS_DIR = REPO_ROOT / "catalog" / "scenarios"


def _data_scenarios_dir() -> Path:
    return get_agent_settings().resolved_data_root / "scenarios"


class AgentDefinition(BaseModel):
    name: str
    role: str
    prompt: str
    sub_agent_ids: list[str] = Field(default_factory=list)
    prompt_text: str | None = None
    tools: list[str]
    skill_package_ids: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    platform_upload_file_ids: list[str] = Field(default_factory=list)
    skill_packages: list[dict[str, Any]] = Field(default_factory=list)
    tool_configs: list[dict[str, Any]] = Field(default_factory=list)
    resource_configs: list[dict[str, Any]] = Field(default_factory=list)
    react_config: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    id: str = "standard_due_diligence"
    name: str = "标准完整尽调"
    description: str = ""
    scenario: str = "standard"
    ordered_agents: list[str] = Field(default_factory=list)
    coordinator: str = ""
    research_agents: list[str] = Field(default_factory=list)
    analysis_agents: list[str] = Field(default_factory=list)
    verifier: str = ""
    reporter: str = ""


class ToolDefinition(BaseModel):
    description: str
    implementation: str
    requires_api_key: bool = False


class ToolConfig(BaseModel):
    tools: dict[str, ToolDefinition]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded if isinstance(loaded, dict) else {}


def _scenario_config_root(scenario_id: str) -> Path | None:
    data_dir = _data_scenarios_dir() / scenario_id
    builtin_dir = BUILTIN_SCENARIOS_DIR / scenario_id
    if (data_dir / "scenario.yaml").is_file():
        return data_dir
    if (builtin_dir / "scenario.yaml").is_file():
        return builtin_dir
    return None


@lru_cache
def load_tool_config() -> ToolConfig:
    data = _load_yaml(ROOT / "configs" / "tools.yaml")
    return ToolConfig.model_validate(data)


@lru_cache
def load_agent_template_catalog() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not GLOBAL_AGENTS_DIR.is_dir():
        return rows
    for path in sorted(GLOBAL_AGENTS_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        doc = _load_yaml(path)
        if doc:
            rows.append(dict(doc))
    return rows


@lru_cache
def load_scenario_template_catalog() -> tuple[list[dict[str, Any]], str]:
    workflows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in (BUILTIN_SCENARIOS_DIR, _data_scenarios_dir()):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            scenario_yaml = child / "scenario.yaml"
            if not scenario_yaml.is_file() or child.name in seen:
                continue
            doc = _load_yaml(scenario_yaml)
            workflow = doc.get("workflow")
            if isinstance(workflow, dict):
                workflows.append(workflow)
                seen.add(child.name)
    default_id = workflows[0]["id"] if workflows else "standard_due_diligence"
    return workflows, default_id


def load_scenario_agents(scenario_id: str) -> list[dict[str, Any]]:
    root = _scenario_config_root(scenario_id)
    if root is None:
        return []
    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(agents_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        doc = _load_yaml(path)
        if doc:
            rows.append(dict(doc))
    return rows
