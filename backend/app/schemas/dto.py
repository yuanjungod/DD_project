from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.services.company_config_merge_constants import PROJECT_RESOURCE_TYPES


class TargetCompany(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)


class Resources(BaseModel):
    uploaded_files: list[str] = Field(default_factory=list)
    trusted_sources: list[str] = Field(default_factory=list)
    blocked_sources: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    # Optional structured entries merged from project Resource library at run time / stored in config.
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    external_clues: list[dict[str, Any]] = Field(default_factory=list)
    agent_resource_scopes: list[dict[str, Any]] = Field(default_factory=list)


class CompanyConfig(BaseModel):
    """Legacy API alias for due-diligence-shaped engagement input; prefer InstanceConfig on create/update."""

    target_company: TargetCompany
    workflow_template_id: str
    workflow_template_version: int | None = None
    resources: Resources = Field(default_factory=Resources)


class InstanceConfig(BaseModel):
    workflow_template_id: str
    workflow_template_version: int | None = None
    resources: Resources = Field(default_factory=Resources)
    extensions: dict[str, Any] = Field(default_factory=dict)
    target_company: TargetCompany | None = Field(
        default=None,
        deprecated="Legacy due-diligence field; prefer extensions.due_diligence.target_company.",
    )


class EngagementCreate(BaseModel):
    name: str
    instance_config: InstanceConfig | None = None
    company_config: CompanyConfig | None = Field(
        default=None,
        deprecated="Use instance_config instead.",
    )
    application_id: str
    version: int = 1
    initial_resources: list["ResourceCreate"] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_config(self) -> EngagementCreate:
        if self.instance_config is None and self.company_config is None:
            raise ValueError("instance_config or company_config is required")
        return self


class EngagementUpdate(BaseModel):
    name: str | None = None
    instance_config: InstanceConfig | None = None
    company_config: CompanyConfig | None = Field(
        default=None,
        deprecated="Use instance_config instead.",
    )
    application_id: str | None = None


class EngagementRead(BaseModel):
    id: str
    name: str
    company_key: str
    application_id: str
    version: int
    company_config: dict[str, Any] = Field(
        deprecated="Use instance_config instead.",
    )
    instance_config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="wrap")
    @classmethod
    def _enrich_instance_config(cls, data: Any, handler: Any) -> EngagementRead:
        from shared.instance_config import instance_config_view

        if hasattr(data, "company_config"):
            stored = data.company_config if isinstance(data.company_config, dict) else {}
            payload = {
                "id": data.id,
                "name": data.name,
                "company_key": data.company_key,
                "application_id": data.application_id,
                "version": data.version,
                "company_config": stored,
                "instance_config": instance_config_view(stored),
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
            return handler(payload)
        if isinstance(data, dict) and "instance_config" not in data and isinstance(data.get("company_config"), dict):
            enriched = dict(data)
            enriched["instance_config"] = instance_config_view(enriched["company_config"])
            return handler(enriched)
        return handler(data)


class EngagementAgentOverrideBase(BaseModel):
    agent_id: str
    prompt_append: str = ""
    prompt_override: str = ""
    skill_package_ids_add: list[str] = Field(default_factory=list)
    skill_package_ids_remove: list[str] = Field(default_factory=list)
    tool_ids_add: list[str] = Field(default_factory=list)
    tool_ids_remove: list[str] = Field(default_factory=list)
    resource_ids_add: list[str] = Field(default_factory=list)
    resource_ids_remove: list[str] = Field(default_factory=list)
    platform_upload_file_ids: list[str] = Field(default_factory=list)
    react_config_override: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    @field_validator(
        "agent_id",
        "prompt_append",
        "prompt_override",
        mode="before",
    )
    @classmethod
    def coerce_str(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator(
        "skill_package_ids_add",
        "skill_package_ids_remove",
        "tool_ids_add",
        "tool_ids_remove",
        "resource_ids_add",
        "resource_ids_remove",
        "platform_upload_file_ids",
        mode="before",
    )
    @classmethod
    def coerce_str_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.replace("\n", ",").split(",")
        elif isinstance(value, list):
            raw = value
        else:
            return []
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            text = str(item).strip()
            if text and text not in seen:
                out.append(text)
                seen.add(text)
        return out

    @model_validator(mode="after")
    def validate_agent_id(self) -> EngagementAgentOverrideBase:
        if not self.agent_id.strip():
            raise ValueError("agent_id must be non-empty")
        self.agent_id = self.agent_id.strip()
        return self


class EngagementAgentOverrideUpsert(EngagementAgentOverrideBase):
    pass


class EngagementAgentOverrideRead(EngagementAgentOverrideBase):
    updated_at: datetime | None = None


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


class WorkflowTemplateSummaryRead(BaseModel):
    id: str
    name: str
    description: str
    workflow_template: str
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

    @field_validator("id", mode="before")
    @classmethod
    def normalize_optional_resource_config_id(cls, v: Any) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v


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
    deletable: bool = Field(
        default=False,
        description="Overlay YAML exists under data store; DELETE removes that file (may revert to built-in).",
    )
    builtin_base: bool = Field(
        default=False,
        description="True when repo catalog ships a YAML with this id (overlay may override).",
    )

    model_config = ConfigDict(from_attributes=True)


def _default_react_config() -> dict[str, Any]:
    from app.services.agent_record_utils import default_react_config

    return default_react_config()


class AgentTemplateBase(BaseModel):
    name: str
    role: str
    prompt: str
    sub_agent_ids: list[str] = Field(default_factory=list)
    skill_package_ids: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    platform_upload_file_ids: list[str] = Field(
        default_factory=list,
        description="Merged uploaded file_ids visible to this agent; empty means use full merged list.",
    )
    react_config: dict[str, Any] = Field(default_factory=_default_react_config)
    enabled: bool = True


class AgentTemplateCreate(AgentTemplateBase):
    id: str | None = None

    @field_validator("id")
    @classmethod
    def validate_optional_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", text):
            raise ValueError("ID 只能包含字母、数字、连字符和下划线")
        return text


class AgentTemplateUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    prompt: str | None = None
    sub_agent_ids: list[str] | None = None
    skill_package_ids: list[str] | None = None
    tool_ids: list[str] | None = None
    resource_ids: list[str] | None = None
    platform_upload_file_ids: list[str] | None = None
    react_config: dict[str, Any] | None = None
    enabled: bool | None = None


class AgentTemplateRead(AgentTemplateBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowTemplateBase(BaseModel):
    name: str
    description: str = ""
    workflow_template: str = Field(
        default="standard",
        validation_alias=AliasChoices("workflow_template"),
        serialization_alias="workflow_template",
    )
    graph: dict[str, Any]
    status: str = "draft"
    version: int = 1


class WorkflowTemplateCreate(WorkflowTemplateBase):
    id: str | None = None


class WorkflowTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workflow_template: str | None = Field(
        default=None,
        validation_alias=AliasChoices("workflow_template"),
        serialization_alias="workflow_template",
    )
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

    @model_validator(mode="after")
    def validate_project_resource_type(self) -> ResourceCreate:
        if self.type not in PROJECT_RESOURCE_TYPES:
            raise ValueError(
                "type must be one of: " + ", ".join(sorted(PROJECT_RESOURCE_TYPES))
            )
        if not (self.value or "").strip():
            raise ValueError("value must be non-empty")
        return self


class ResourceRead(BaseModel):
    id: str
    engagement_id: str
    type: str
    value: str
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LibraryFileRead(BaseModel):
    """Platform library upload (shared file_id merged into runs' resources.uploaded_files)."""

    id: str
    original_filename: str
    content_type: str = ""
    size_bytes: int = 0
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


class ReportRead(BaseModel):
    id: str
    engagement_id: str
    run_id: str
    title: str
    executive_summary: str
    overall_risk: str
    sections: list[dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def utc_datetime_to_iso_z(v: datetime) -> str:
    """Persisted datetimes are naive UTC; expose as RFC 3339 with Z so clients parse as UTC."""
    aware = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
    frac = aware.strftime("%f")[:3]
    return aware.strftime("%Y-%m-%dT%H:%M:%S") + f".{frac}Z"


class StartAgentRunBody(BaseModel):
    """Start a full-chain agent run attached to a workflow session."""

    session_mode: Literal["new", "continue"] = "new"
    workflow_session_id: str | None = Field(
        default=None,
        description="Existing session id; required when session_mode is continue",
    )
    diligence_session_id: str | None = Field(
        default=None,
        deprecated="Use workflow_session_id instead.",
        description="Deprecated alias for workflow_session_id.",
    )
    interaction_mode: Literal["batch", "step_gated"] = Field(
        default="batch",
        description="step_gated pauses after each agent for human chat + continue",
    )

    @model_validator(mode="before")
    @classmethod
    def _coalesce_session_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            primary = str(data.get("workflow_session_id") or "").strip()
            legacy = str(data.get("diligence_session_id") or "").strip()
            resolved = primary or legacy or None
            data["workflow_session_id"] = resolved
        return data


class StepReviewChatTurnRead(BaseModel):
    id: str
    step_id: str
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", when_used="json")
    def _serialize_created_at(self, v: datetime) -> str:
        return utc_datetime_to_iso_z(v)


class StepReviewChatIn(BaseModel):
    message: str


class StepReviewChatOut(BaseModel):
    reply: str
    turns: list[StepReviewChatTurnRead] = Field(default_factory=list)


class AgentRunBriefRead(BaseModel):
    id: str
    engagement_id: str
    status: str
    attempt_index: int | None = None
    session_id: str | None = None
    started_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", when_used="json")
    def _serialize_started_at(self, v: datetime) -> str:
        return utc_datetime_to_iso_z(v)


class WorkflowSessionRead(BaseModel):
    id: str
    engagement_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    runs: list[AgentRunBriefRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", when_used="json")
    def _serialize_created_at(self, v: datetime) -> str:
        return utc_datetime_to_iso_z(v)

    @field_serializer("updated_at", when_used="json")
    def _serialize_updated_at(self, v: datetime) -> str:
        return utc_datetime_to_iso_z(v)


DiligenceSessionRead = WorkflowSessionRead


class AgentRunRead(BaseModel):
    id: str
    engagement_id: str
    session_id: str | None = None
    attempt_index: int | None = None
    status: str
    started_at: datetime
    completed_at: datetime | None
    raw_result: dict[str, Any]
    steps: list[AgentStepRead] = Field(default_factory=list)
    report: ReportRead | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", when_used="json")
    def _serialize_started_at(self, v: datetime) -> str:
        return utc_datetime_to_iso_z(v)

    @field_serializer("completed_at", when_used="json")
    def _serialize_completed_at(self, v: datetime | None) -> str | None:
        if v is None:
            return None
        return utc_datetime_to_iso_z(v)


AgentRunRead.model_rebuild()
TokenResponse.model_rebuild()
