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
BUILTIN_WORKFLOW_TEMPLATES_DIR = REPO_ROOT / "catalog" / "workflow_templates"
WORKFLOW_TEMPLATE_FILENAMES = ("workflow_template.yaml",)


def _workflow_template_yaml_in(directory: Path) -> Path | None:
    for filename in WORKFLOW_TEMPLATE_FILENAMES:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def _data_workflow_template_dirs() -> list[Path]:
    users_root = get_agent_settings().repo_root / ".dd_project" / "users"
    if not users_root.is_dir():
        return []
    roots: list[Path] = []
    for user_dir in users_root.iterdir():
        if not user_dir.is_dir():
            continue
        wf_root = user_dir / "_workflows"
        if wf_root.is_dir():
            roots.append(wf_root)
    return roots


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
    workflow_template: str = "standard"
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


def _workflow_template_config_root(workflow_template_id: str) -> Path | None:
    for root in _data_workflow_template_dirs():
        data_dir = root / workflow_template_id
        if _workflow_template_yaml_in(data_dir) is not None:
            return data_dir
    builtin_dir = BUILTIN_WORKFLOW_TEMPLATES_DIR / workflow_template_id
    if _workflow_template_yaml_in(builtin_dir) is not None:
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
def load_workflow_template_catalog() -> tuple[list[dict[str, Any]], str]:
    workflows: list[dict[str, Any]] = []
    seen: set[str] = set()
    roots: list[Path] = [BUILTIN_WORKFLOW_TEMPLATES_DIR, *_data_workflow_template_dirs()]
    for root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            workflow_template_yaml = _workflow_template_yaml_in(child)
            if workflow_template_yaml is None or child.name in seen:
                continue
            doc = _load_yaml(workflow_template_yaml)
            workflow = doc.get("workflow")
            if isinstance(workflow, dict):
                workflows.append(workflow)
                seen.add(child.name)
    default_id = workflows[0]["id"] if workflows else "standard_due_diligence"
    return workflows, default_id


def load_workflow_template_agents(workflow_template_id: str) -> list[dict[str, Any]]:
    root = _workflow_template_config_root(workflow_template_id)
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
