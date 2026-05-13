from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RunStatus = Literal["pending", "running", "completed", "failed", "paused"]
RiskLevel = Literal["low", "medium", "high", "unknown"]


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
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    external_clues: list[dict[str, Any]] = Field(default_factory=list)
    target_company: TargetCompany
    scope: Scope = Field(default_factory=Scope)
    resources: Resources = Field(default_factory=Resources)


class Evidence(BaseModel):
    id: str
    title: str
    source_type: Literal["web", "file", "database", "manual", "mock"] = "mock"
    source_url: str | None = None
    file_id: str | None = None
    excerpt: str
    confidence: float = Field(ge=0, le=1)
    collected_by: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    title: str
    description: str
    risk_level: RiskLevel = "unknown"
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent: str
    status: RunStatus
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class ReportSection(BaseModel):
    title: str
    summary: str
    risk_level: RiskLevel
    evidence_ids: list[str] = Field(default_factory=list)


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
    project_id: str
    company_config: CompanyConfig
    workflow_snapshot: dict[str, Any] | None = None
    run_id: str | None = Field(
        default=None,
        description="Optional id to correlate with backend-persisted AgentRun.",
    )
    diligence_session_id: str | None = Field(
        default=None,
        description="Product diligence session container (pairs with backend DiligenceSession).",
    )
    attempt_index: int | None = Field(default=None, description="1-based attempt number within diligence_session_id.")
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
        description="Skip the first N agents; pass completed_steps/evidence of length N when resuming.",
    )
    completed_steps: list[AgentStep] = Field(default_factory=list)
    completed_evidence: list[Evidence] = Field(default_factory=list)


class RunResult(BaseModel):
    run_id: str
    project_id: str
    status: RunStatus
    steps: list[AgentStep] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    report: DueDiligenceReport | None = None


class StepReviewChatRequest(BaseModel):
    project_id: str
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
