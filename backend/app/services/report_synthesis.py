"""Synthesize a minimal report from completed agent steps when RunResult omits report."""

from __future__ import annotations

from typing import Any


def synthesize_report_from_steps(steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    completed = [step for step in steps if str(step.get("status")) == "completed"]
    if not completed:
        return None

    last = completed[-1]
    agent = str(last.get("agent") or "ReportWriterAgent")
    summary = str(last.get("summary") or "").strip()
    result = last.get("result") if isinstance(last.get("result"), dict) else {}
    readme_path = str(result.get("output_readme_path") or result.get("output_dir") or "").strip()

    executive = summary or (f"See step output at {readme_path}" if readme_path else f"Final step completed by {agent}.")
    section_summary = summary or executive

    return {
        "title": f"Due Diligence Report — {agent}",
        "executive_summary": executive,
        "overall_risk": "unknown",
        "sections": [
            {
                "title": agent,
                "summary": section_summary,
                "risk_level": "unknown",
            }
        ],
    }
