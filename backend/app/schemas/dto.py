from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TargetCompany(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    website: str = ""
    jurisdiction: str = ""
    industry: str = ""
    keywords: list[str] = Field(default_factory=list)


class Scope(BaseModel):
    workflow_id: str = "standard_due_diligence"
    workflow_template_id: str | None = None
    workflow_template_version: int | None = None
    scenario: str = "standard"
    time_range: str = "近5年"
    focus_areas: list[str] = Field(
        default_factory=lambda: ["业务", "财务", "法律", "股权", "舆情", "合规"]
    )
    report_language: str = "zh-CN"


class Resources(BaseModel):
    uploaded_files: list[str] = Field(default_factory=list)
    trusted_sources: list[str] = Field(default_factory=list)
    blocked_sources: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)


class CompanyConfig(BaseModel):
    target_company: TargetCompany
    scope: Scope = Field(default_factory=Scope)
    resources: Resources = Field(default_factory=Resources)


class ProjectCreate(BaseModel):
    name: str
    company_config: CompanyConfig


class ProjectUpdate(BaseModel):
    name: str | None = None
    company_config: CompanyConfig | None = None


class ProjectRead(BaseModel):
    id: str
    name: str
    company_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserRead"


class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "analyst"


class UserRead(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScenarioRead(BaseModel):
    id: str
    name: str
    description: str
    scenario: str
    agents: list[str]


class SkillPackageBase(BaseModel):
    name: str
    description: str = ""
    directory_name: str
    skill_md: str
    package_files: dict[str, str] = Field(default_factory=dict)
    resources_manifest: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class SkillPackageCreate(SkillPackageBase):
    id: str | None = None


class SkillPackageUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    directory_name: str | None = None
    skill_md: str | None = None
    package_files: dict[str, str] | None = None
    resources_manifest: dict[str, Any] | None = None
    enabled: bool | None = None


class SkillPackageRead(SkillPackageBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SkillDebugRead(BaseModel):
    valid: bool
    checks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    agent_skill_prompt: str | None = None
    errors: list[str] = Field(default_factory=list)


class ToolConfigBase(BaseModel):
    name: str
    description: str = ""
    implementation: str
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    requires_api_key: bool = False
    enabled: bool = True


class ToolConfigCreate(ToolConfigBase):
    id: str | None = None


class ToolConfigUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    implementation: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    requires_api_key: bool | None = None
    enabled: bool | None = None


class ToolConfigRead(ToolConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceConfigBase(BaseModel):
    name: str
    type: str
    description: str = ""
    connection_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ResourceConfigCreate(ResourceConfigBase):
    id: str | None = None


class ResourceConfigUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    description: str | None = None
    connection_config: dict[str, Any] | None = None
    enabled: bool | None = None


class ResourceConfigRead(ResourceConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _default_react_config() -> dict[str, Any]:
    return {
        "max_iters": 6,
        "parallel_tool_calls": False,
        "model": {
            "baseUrl": "http://127.0.0.1:8081/v1",
            "apiKey": "yuanjun",
            "api": "anthropic-messages",
            "models": [
                {
                    "id": "kimi-code",
                    "name": "kimi-code(Custom Provider)",
                    "reasoning": True,
                    "input": ["text", "image"],
                    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                    "contextWindow": 128000,
                    "maxTokens": 4096,
                }
            ],
        },
    }


class AgentTemplateBase(BaseModel):
    name: str
    role: str
    prompt: str
    skill_package_ids: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    react_config: dict[str, Any] = Field(default_factory=_default_react_config)
    output_schema: str = "agent_result"
    enabled: bool = True


class AgentTemplateCreate(AgentTemplateBase):
    id: str | None = None


class AgentTemplateUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    prompt: str | None = None
    skill_package_ids: list[str] | None = None
    tool_ids: list[str] | None = None
    skill_ids: list[str] | None = None
    resource_ids: list[str] | None = None
    react_config: dict[str, Any] | None = None
    output_schema: str | None = None
    enabled: bool | None = None


class AgentTemplateRead(AgentTemplateBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowTemplateBase(BaseModel):
    name: str
    description: str = ""
    scenario: str = "standard"
    graph: dict[str, Any]
    status: str = "draft"
    version: int = 1


class WorkflowTemplateCreate(WorkflowTemplateBase):
    id: str | None = None


class WorkflowTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scenario: str | None = None
    graph: dict[str, Any] | None = None
    status: str | None = None
    version: int | None = None


class WorkflowTemplateRead(WorkflowTemplateBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceCreate(BaseModel):
    type: str
    value: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ResourceRead(BaseModel):
    id: str
    project_id: str
    type: str
    value: str
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentStepRead(BaseModel):
    id: str
    run_id: str
    agent: str
    status: str
    summary: str
    result: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class EvidenceRead(BaseModel):
    id: str
    run_id: str
    project_id: str
    title: str
    source_type: str
    source_url: str | None
    file_id: str | None
    excerpt: str
    confidence: float
    collected_by: str
    metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class ReportRead(BaseModel):
    id: str
    project_id: str
    run_id: str
    title: str
    executive_summary: str
    overall_risk: str
    sections: list[dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentRunRead(BaseModel):
    id: str
    project_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    raw_result: dict[str, Any]
    steps: list[AgentStepRead] = Field(default_factory=list)
    evidence: list[EvidenceRead] = Field(default_factory=list)
    report: ReportRead | None = None

    model_config = ConfigDict(from_attributes=True)


AgentRunRead.model_rebuild()
TokenResponse.model_rebuild()
