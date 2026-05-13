from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[1]


class AgentDefinition(BaseModel):
    name: str
    role: str
    prompt: str
    tools: list[str]
    output_schema: str


class WorkflowDefinition(BaseModel):
    coordinator: str
    research_agents: list[str]
    analysis_agents: list[str]
    verifier: str
    reporter: str


class AgentConfig(BaseModel):
    agents: list[AgentDefinition]
    workflow: WorkflowDefinition

    def get_agent(self, name: str) -> AgentDefinition:
        for agent in self.agents:
            if agent.name == name:
                return agent
        raise KeyError(f"Unknown agent: {name}")


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
def load_tool_config() -> ToolConfig:
    data = _load_yaml(ROOT / "configs" / "tools.yaml")
    return ToolConfig.model_validate(data)


@lru_cache
def load_prompt(prompt_name: str) -> str:
    return (ROOT / "prompts" / prompt_name).read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)
