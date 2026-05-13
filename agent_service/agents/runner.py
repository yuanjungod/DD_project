from __future__ import annotations

from agent_service.api.schemas import AgentResult, CompanyConfig, Evidence, Finding
from agent_service.tools.research import (
    MockFileReaderTool,
    MockSearchTool,
    MockVectorRetrievalTool,
    MockWebFetchTool,
)
from agent_service.tools.stores import EvidenceStoreTool
from agent_service.workflows.config_loader import AgentDefinition, load_prompt


class ConfiguredAgentRunner:
    def __init__(self, definition: AgentDefinition, evidence_store: EvidenceStoreTool) -> None:
        self.definition = definition
        self.prompt = definition.prompt_text or load_prompt(definition.prompt)
        self.evidence_store = evidence_store
        self.search = MockSearchTool()
        self.web_fetch = MockWebFetchTool()
        self.file_reader = MockFileReaderTool()
        self.vector_retrieval = MockVectorRetrievalTool()

    def run(self, company_config: CompanyConfig, previous_results: list[AgentResult]) -> AgentResult:
        agent_name = self.definition.name
        evidence = self._collect_evidence(company_config)
        findings = self._build_findings(company_config, evidence, previous_results)
        summary = self._build_summary(company_config, findings)
        return AgentResult(
            agent=agent_name,
            status="completed",
            summary=summary,
            findings=findings,
            evidence=evidence,
        )

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
            for file_id in company_config.resources.uploaded_files[:2]:
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
                metadata={"prompt_excerpt": self.prompt[:120]},
            )
            evidence.append(self.evidence_store.add(fallback))

        return evidence

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
        return f"{self.definition.name} completed for {company.name}. Risk signal: {risk_levels}."
