from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[1]
AGENT_TEMPLATES_PATH = ROOT / "configs" / "agent_templates.yaml"
SCENARIO_TEMPLATES_DIR = ROOT / "configs" / "scenario_templates"


class AgentDefinition(BaseModel):
    name: str
    role: str
    prompt: str
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


@lru_cache
def load_tool_config() -> ToolConfig:
    data = _load_yaml(ROOT / "configs" / "tools.yaml")
    return ToolConfig.model_validate(data)


@lru_cache
def load_agent_template_catalog() -> list[dict[str, Any]]:
    if not AGENT_TEMPLATES_PATH.is_file():
        return []
    data = _load_yaml(AGENT_TEMPLATES_PATH)
    raw = data.get("agents", []) if isinstance(data, dict) else []
    return [dict(item) for item in raw] if isinstance(raw, list) else []


@lru_cache
def load_scenario_template_catalog() -> tuple[list[dict[str, Any]], str]:
    if not SCENARIO_TEMPLATES_DIR.is_dir():
        return [], "standard_due_diligence"
    workflows: list[dict[str, Any]] = []
    for path in sorted(SCENARIO_TEMPLATES_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        doc = _load_yaml(path)
        workflow = doc.get("workflow")
        if isinstance(workflow, dict):
            workflows.append(workflow)
    default_id = workflows[0]["id"] if workflows else "standard_due_diligence"
    return workflows, default_id


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded if isinstance(loaded, dict) else {}
