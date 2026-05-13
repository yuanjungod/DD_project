from __future__ import annotations

from uuid import uuid4

from agent_service.agents.runner import ConfiguredAgentRunner
from agent_service.api.schemas import (
    AgentResult,
    AgentStep,
    CompanyConfig,
    DueDiligenceReport,
    ReportSection,
    RunResult,
)
from agent_service.tools.stores import EvidenceStoreTool, ReportStoreTool
from agent_service.workflows.config_loader import load_agent_config


class DueDiligenceWorkflow:
    def __init__(self) -> None:
        self.config = load_agent_config()

    def run(self, project_id: str, company_config: CompanyConfig) -> RunResult:
        run_id = f"run_{uuid4().hex[:12]}"
        evidence_store = EvidenceStoreTool()
        report_store = ReportStoreTool()
        steps: list[AgentStep] = []
        results: list[AgentResult] = []

        ordered_agents = self._ordered_agents()
        for agent_name in ordered_agents:
            definition = self.config.get_agent(agent_name)
            runner = ConfiguredAgentRunner(definition, evidence_store)
            step = AgentStep(id=f"step_{len(steps) + 1:03d}", agent=agent_name, status="running")
            steps.append(step)
            result = runner.run(company_config, results)
            step.status = result.status
            step.summary = result.summary
            step.result = result
            results.append(result)

        report = self._build_report(company_config, results)
        report_store.save(report)

        return RunResult(
            run_id=run_id,
            project_id=project_id,
            status="completed",
            steps=steps,
            evidence=evidence_store.all(),
            report=report_store.get(),
        )

    def _ordered_agents(self) -> list[str]:
        workflow = self.config.workflow
        return [
            workflow.coordinator,
            *workflow.research_agents,
            *workflow.analysis_agents,
            workflow.verifier,
            workflow.reporter,
        ]

    def _build_report(
        self,
        company_config: CompanyConfig,
        results: list[AgentResult],
    ) -> DueDiligenceReport:
        company = company_config.target_company
        sections: list[ReportSection] = []

        for result in results:
            if result.agent == self.config.workflow.reporter:
                continue
            evidence_ids = [evidence.id for evidence in result.evidence]
            risk_level = self._highest_risk([finding.risk_level for finding in result.findings])
            sections.append(
                ReportSection(
                    title=result.agent.replace("Agent", ""),
                    summary=result.summary,
                    risk_level=risk_level,
                    evidence_ids=evidence_ids,
                )
            )

        overall_risk = self._highest_risk([section.risk_level for section in sections])
        return DueDiligenceReport(
            title=f"{company.name} 尽调报告",
            executive_summary=(
                f"本报告基于配置化 AgentScope 尽调流程生成，覆盖 "
                f"{', '.join(company_config.scope.focus_areas)}。MVP 使用可替换的本地工具，"
                "生产使用前应接入真实数据源并进行人工复核。"
            ),
            overall_risk=overall_risk,
            sections=sections,
        )

    def _highest_risk(self, risk_levels: list[str]) -> str:
        rank = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
        if not risk_levels:
            return "unknown"
        return max(risk_levels, key=lambda risk: rank.get(risk, 0))
