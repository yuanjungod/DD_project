from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_service.api.schemas import AgentResult, CompanyConfig, Evidence, Finding
from agent_service.agents.react_runtime import AgentScopeReActRuntime, build_react_system_prompt
from agent_service.tools.research import (
    MockFileReaderTool,
    MockSearchTool,
    MockVectorRetrievalTool,
    MockWebFetchTool,
)
from agent_service.tools.stores import EvidenceStoreTool
from agent_service.workflows.config_loader import AgentDefinition, load_prompt
from agent_service.workflows.agent_outputs import read_agent_output_folder


class ModelAgentOutput(BaseModel):
    summary: str
    findings: list[Finding] = Field(default_factory=list)


class ConfiguredAgentRunner:
    def __init__(self, definition: AgentDefinition, evidence_store: EvidenceStoreTool) -> None:
        self.definition = definition
        self.prompt = definition.prompt_text or load_prompt(definition.prompt)
        self.evidence_store = evidence_store
        self.search = MockSearchTool()
        self.web_fetch = MockWebFetchTool()
        self.file_reader = MockFileReaderTool()
        self.vector_retrieval = MockVectorRetrievalTool()
        self.current_company_config: CompanyConfig | None = None
        self.react_runtime = AgentScopeReActRuntime(
            definition,
            sys_prompt=build_react_system_prompt(definition, self.prompt),
            tool_executor=self._execute_react_tool,
        )

    def _visible_uploaded_file_ids(self, company_config: CompanyConfig) -> list[str]:
        full = list(company_config.resources.uploaded_files or [])
        allow = [x.strip() for x in (self.definition.platform_upload_file_ids or []) if x and str(x).strip()]
        scoped = self._project_scoped_file_ids(company_config)
        if scoped:
            allow = [*allow, *scoped] if allow else scoped
        if not allow:
            return full
        allow_set = set(allow)
        return [fid for fid in full if fid in allow_set]

    def _project_scoped_file_ids(self, company_config: CompanyConfig) -> list[str]:
        scopes = company_config.resources.agent_resource_scopes or []
        selected: list[str] = []
        for scope in scopes:
            if not isinstance(scope, dict) or scope.get("agent_id") != self.definition.name:
                continue
            raw_ids = scope.get("uploaded_file_ids") or scope.get("file_ids") or []
            if isinstance(raw_ids, str):
                raw_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
            if isinstance(raw_ids, list):
                selected.extend(str(x).strip() for x in raw_ids if str(x).strip())
        return selected

    def run(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        *,
        continuation_context: dict[str, Any] | None = None,
    ) -> AgentResult:
        try:
            self.current_company_config = company_config
            agent_name = self.definition.name
            evidence = self._collect_evidence(company_config)
            model_output = self.react_runtime.run_model(
                company_config=company_config,
                previous_results=previous_results,
                evidence=evidence,
                structured_model=ModelAgentOutput,
                continuation_context=continuation_context,
            )
            evidence = self._agent_evidence(agent_name)
            findings = self._normalize_findings(model_output.findings, evidence)
            return AgentResult(
                agent=agent_name,
                status="completed",
                summary=model_output.summary,
                findings=findings,
                evidence=evidence,
            )
        finally:
            self.current_company_config = None
            self.react_runtime.close()

    def run_step_review_chat(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        *,
        current_step_summary: str,
        current_findings: list[dict[str, Any]],
        chat_messages: list[dict[str, str]],
        user_message: str,
    ) -> str:
        try:
            self.current_company_config = company_config
            evidence = self._collect_evidence(company_config)
            return self.react_runtime.run_step_review_chat(
                company_config,
                previous_results,
                evidence,
                current_step_summary=current_step_summary,
                current_findings=current_findings,
                chat_messages=chat_messages,
                user_message=user_message,
            )
        finally:
            self.current_company_config = None
            self.react_runtime.close()

    def _execute_react_tool(self, tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        company_config = self.current_company_config
        if company_config is None:
            raise RuntimeError("Tool execution requires an active company config")

        agent_name = self.definition.name
        if tool_id == "search":
            query = payload.get("query") or f"{company_config.target_company.name} {self.definition.role}"
            evidence = self.evidence_store.add(self.search.run(str(query), company_config, agent_name))
            return {"evidence": evidence.model_dump(mode="json")}
        if tool_id == "web_fetch":
            url = payload.get("url") or company_config.target_company.website
            evidence = self.evidence_store.add(self.web_fetch.run(str(url), company_config, agent_name))
            return {"evidence": evidence.model_dump(mode="json")}
        if tool_id == "file_reader":
            visible = self._visible_uploaded_file_ids(company_config)
            file_id = payload.get("file_id") or next(iter(visible), "")
            evidence = self.evidence_store.add(self.file_reader.run(str(file_id), company_config, agent_name))
            return {"evidence": evidence.model_dump(mode="json")}
        if tool_id == "vector_retrieval":
            query = payload.get("query") or f"{company_config.target_company.name} {' '.join(company_config.scope.focus_areas)}"
            evidence = self.evidence_store.add(self.vector_retrieval.run(str(query), company_config, agent_name))
            return {"evidence": evidence.model_dump(mode="json")}
        if tool_id == "evidence_store":
            return {"stored_evidence_count": len(self.evidence_store.all())}
        if tool_id == "report_store":
            return {"message": "Report store is used after all agents finish."}
        if tool_id == "agent_output_reader":
            folder_path = payload.get("folder_path") or payload.get("query") or ""
            return read_agent_output_folder(str(folder_path))
        return {"message": f"Tool {tool_id} is configured but has no local executor yet."}

    def _collect_evidence(self, company_config: CompanyConfig) -> list[Evidence]:
        company = company_config.target_company
        agent_name = self.definition.name
        evidence: list[Evidence] = []

        if "search" in self.definition.tools:
            query = f"{company.name} {self.definition.role}"
            evidence.append(self.evidence_store.add(self.search.run(query, company_config, agent_name)))

        if "web_fetch" in self.definition.tools and company.website:
            evidence.append(self.evidence_store.add(self.web_fetch.run(company.website, company_config, agent_name)))

        if "file_reader" in self.definition.tools:
            visible = self._visible_uploaded_file_ids(company_config)
            for file_id in visible[:2]:
                evidence.append(self.evidence_store.add(self.file_reader.run(file_id, company_config, agent_name)))

        if "vector_retrieval" in self.definition.tools:
            query = f"{company.name} {' '.join(company_config.scope.focus_areas)}"
            evidence.append(self.evidence_store.add(self.vector_retrieval.run(query, company_config, agent_name)))

        if not evidence:
            fallback = Evidence(
                id="",
                title=f"{agent_name} run note",
                source_type="mock",
                excerpt=f"{agent_name} processed the configured due diligence scope.",
                confidence=0.6,
                collected_by=agent_name,
                metadata={
                    "prompt_excerpt": self.prompt[:120],
                    "agentscope_react": self.react_runtime.config,
                },
            )
            evidence.append(self.evidence_store.add(fallback))

        return evidence

    def _normalize_findings(self, findings: list[Finding], evidence: list[Evidence]) -> list[Finding]:
        evidence_ids = [item.id for item in evidence]
        normalized: list[Finding] = []
        for finding in findings:
            if not finding.evidence_ids and evidence_ids:
                finding.evidence_ids = evidence_ids[:3]
            normalized.append(finding)
        return normalized

    def _agent_evidence(self, agent_name: str) -> list[Evidence]:
        return [item for item in self.evidence_store.all() if item.collected_by == agent_name]

    def _build_findings(
        self,
        company_config: CompanyConfig,
        evidence: list[Evidence],
        previous_results: list[AgentResult],
    ) -> list[Finding]:
        company = company_config.target_company
        evidence_ids = [item.id for item in evidence]
        risk_level = self._risk_level(company_config)

        if self.definition.name == "CoordinatorAgent":
            description = (
                f"Created a diligence plan for {company.name} covering "
                f"{', '.join(company_config.scope.focus_areas)}."
            )
            title = "Diligence plan created"
        elif self.definition.name == "EvidenceVerifierAgent":
            unsupported = sum(1 for result in previous_results for finding in result.findings if not finding.evidence_ids)
            description = (
                f"Verified {len(previous_results)} prior agent results. "
                f"Unsupported findings: {unsupported}."
            )
            title = "Evidence coverage reviewed"
            risk_level = "low" if unsupported == 0 else "medium"
        else:
            description = (
                f"{self.definition.role} reviewed {company.name} using configured "
                f"scope and available resources. Manual validation is recommended for production use."
            )
            title = f"{self.definition.role.replace('_', ' ').title()} finding"

        return [
            Finding(
                title=title,
                description=description,
                risk_level=risk_level,
                confidence=min(0.86, max(item.confidence for item in evidence)),
                evidence_ids=evidence_ids,
            )
        ]

    def _risk_level(self, company_config: CompanyConfig) -> str:
        focus_text = " ".join(company_config.scope.focus_areas).lower()
        if "法律" in focus_text or "legal" in focus_text or "合规" in focus_text:
            return "medium" if self.definition.name == "LegalRiskAgent" else "low"
        return "low"

    def _build_summary(self, company_config: CompanyConfig, findings: list[Finding]) -> str:
        company = company_config.target_company
        risk_levels = ", ".join({finding.risk_level for finding in findings})
        return (
            f"{self.definition.name} completed for {company.name} with AgentScope ReAct config. "
            f"Risk signal: {risk_levels}."
        )
