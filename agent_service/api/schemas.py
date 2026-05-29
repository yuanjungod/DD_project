from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from shared.session_fields import coalesce_workflow_session_id


RunStatus = Literal["pending", "running", "completed", "failed", "paused"]
RiskLevel = Literal["low", "medium", "high", "unknown"]


class TargetCompany(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)


class Resources(BaseModel):
    uploaded_files: list[str] = Field(default_factory=list)
    trusted_sources: list[str] = Field(default_factory=list)
    blocked_sources: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    external_clues: list[dict[str, Any]] = Field(default_factory=list)
    agent_resource_scopes: list[dict[str, Any]] = Field(default_factory=list)


class CompanyConfig(BaseModel):
    target_company: TargetCompany
    workflow_template_id: str
    workflow_template_version: int | None = None
    resources: Resources = Field(default_factory=Resources)


class AgentResult(BaseModel):
    agent: str
    status: RunStatus
    output_dir: str = Field(
        default="",
        description="Filesystem handoff folder for this agent step. Contains README.md and result.json.",
    )
    output_readme_path: str = Field(default="", description="README.md inside output_dir.")


class ReportSection(BaseModel):
    title: str
    summary: str
    risk_level: RiskLevel


class DueDiligenceReport(BaseModel):
    title: str
    executive_summary: str
    overall_risk: RiskLevel
    sections: list[ReportSection] = Field(default_factory=list)


class AgentStep(BaseModel):
    id: str
    agent: str
    status: RunStatus
    summary: str = ""
    result: AgentResult | None = None


class RunRequest(BaseModel):
    engagement_id: str
    user_id: str = Field(description="User id for session filesystem isolation.")
    company_config: CompanyConfig
    workflow_snapshot: dict[str, Any] | None = None
    run_id: str | None = Field(
        default=None,
        description="Optional id to correlate with backend-persisted AgentRun.",
    )
    workflow_session_id: str | None = Field(
        default=None,
        description="Product workflow session container (pairs with backend WorkflowSession).",
    )
    diligence_session_id: str | None = Field(
        default=None,
        deprecated=True,
        description="Deprecated alias for workflow_session_id.",
    )
    attempt_index: int | None = Field(default=None, description="1-based attempt number within workflow_session_id.")
    continuation_context: dict[str, Any] | None = Field(
        default=None,
        description="Digest from the previous attempt in this session; injected into the first agent prompt.",
    )
    pause_after_each_step: bool = Field(
        default=False,
        description="If true, return status=paused after each agent except the last (human review + chat).",
    )
    resume_from_step_index: int = Field(
        default=0,
        ge=0,
        description="Skip the first N agents; pass completed_steps of length N when resuming.",
    )
    completed_steps: list[AgentStep] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coalesce_session_id(cls, data: object) -> object:
        if isinstance(data, dict):
            resolved = coalesce_workflow_session_id(data)
            if resolved:
                data["workflow_session_id"] = resolved
        return data

    @property
    def resolved_workflow_session_id(self) -> str | None:
        return self.workflow_session_id


class RunResult(BaseModel):
    run_id: str
    engagement_id: str
    status: RunStatus
    steps: list[AgentStep] = Field(default_factory=list)


class StepReviewChatRequest(BaseModel):
    engagement_id: str
    company_config: CompanyConfig
    workflow_snapshot: dict[str, Any] | None = None
    agent_name: str
    previous_results: list[AgentResult] = Field(default_factory=list)
    current_step: AgentStep
    chat_messages: list[dict[str, str]] = Field(
        default_factory=list,
        description="Prior turns [{role: user|assistant, content: str}]",
    )
    user_message: str


class StepReviewChatResponse(BaseModel):
    reply: str
