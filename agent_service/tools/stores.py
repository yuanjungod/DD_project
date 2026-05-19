from __future__ import annotations

from typing import Any

from agent_service.api.schemas import DueDiligenceReport
from agent_service.tools.base import ToolExecutionContext


class ReportStoreTool:
    def __init__(self) -> None:
        self._report: DueDiligenceReport | None = None

    def save(self, report: DueDiligenceReport) -> DueDiligenceReport:
        self._report = report
        return report

    def get(self) -> DueDiligenceReport | None:
        return self._report

    def execute(self, payload: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        return {"message": "Report store is used after all agents finish."}
