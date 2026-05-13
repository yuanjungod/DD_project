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
