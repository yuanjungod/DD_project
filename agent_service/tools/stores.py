from __future__ import annotations

from agent_service.api.schemas import DueDiligenceReport, Evidence


class EvidenceStoreTool:
    def __init__(self, id_prefix: str = "") -> None:
        self.id_prefix = id_prefix
        self._evidence: list[Evidence] = []

    def add(self, evidence: Evidence) -> Evidence:
        if not evidence.id:
            prefix = f"{self.id_prefix}_" if self.id_prefix else ""
            evidence.id = f"{prefix}ev_{len(self._evidence) + 1:03d}"
        self._evidence.append(evidence)
        return evidence

    def all(self) -> list[Evidence]:
        return list(self._evidence)


class ReportStoreTool:
    def __init__(self) -> None:
        self._report: DueDiligenceReport | None = None

    def save(self, report: DueDiligenceReport) -> DueDiligenceReport:
        self._report = report
        return report

    def get(self) -> DueDiligenceReport | None:
        return self._report
