from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[1]


class AgentDefinition(BaseModel):
    name: str
    role: str
    prompt: str
    prompt_text: str | None = None
    tools: list[str]
    skill_package_ids: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    skill_packages: list[dict[str, Any]] = Field(default_factory=list)
    tool_configs: list[dict[str, Any]] = Field(default_factory=list)
    resource_configs: list[dict[str, Any]] = Field(default_factory=list)
    react_config: dict[str, Any] = Field(default_factory=dict)
    output_schema: str


class WorkflowDefinition(BaseModel):
    id: str = "standard_due_diligence"
    name: str = "标准完整尽调"
    description: str = ""
    scenario: str = "standard"
    coordinator: str
    research_agents: list[str]
    analysis_agents: list[str]
    verifier: str
    reporter: str


class AgentConfig(BaseModel):
    agents: list[AgentDefinition]

    def get_agent(self, name: str) -> AgentDefinition:
        for agent in self.agents:
            if agent.name == name:
                return agent
        raise KeyError(f"Unknown agent: {name}")


class WorkflowConfig(BaseModel):
    default_workflow_id: str
    workflows: list[WorkflowDefinition]

    def get_workflow(self, workflow_id: str | None = None) -> WorkflowDefinition:
        selected_id = workflow_id or self.default_workflow_id
        for workflow in self.workflows:
            if workflow.id == selected_id:
                return workflow
        raise KeyError(f"Unknown workflow template: {selected_id}")


class ToolDefinition(BaseModel):
    description: str
    implementation: str
    requires_api_key: bool = False


class ToolConfig(BaseModel):
    tools: dict[str, ToolDefinition]


@lru_cache
def load_agent_config() -> AgentConfig:
    data = _load_yaml(ROOT / "configs" / "agents.yaml")
    return AgentConfig.model_validate(data)


@lru_cache
def load_workflow_config() -> WorkflowConfig:
    data = _load_yaml(ROOT / "configs" / "workflows.yaml")
    return WorkflowConfig.model_validate(data)


@lru_cache
def load_tool_config() -> ToolConfig:
    data = _load_yaml(ROOT / "configs" / "tools.yaml")
    return ToolConfig.model_validate(data)


@lru_cache
def load_prompt(prompt_name: str) -> str:
    return (ROOT / "prompts" / prompt_name).read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)
