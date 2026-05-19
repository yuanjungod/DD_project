from __future__ import annotations

from agent_service.api.schemas import DueDiligenceReport


class ReportStoreTool:
    def __init__(self) -> None:
        self._report: DueDiligenceReport | None = None

    def save(self, report: DueDiligenceReport) -> DueDiligenceReport:
        self._report = report
        return report

    def get(self) -> DueDiligenceReport | None:
        return self._report
