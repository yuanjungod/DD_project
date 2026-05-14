from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_service.api.schemas import AgentResult
from agent_service.session_history import session_json_path

_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9_-]+")
_MARKER_FILE = ".agent-output.json"


def write_agent_step_output_folder(
    *,
    project_id: str,
    run_id: str,
    step_id: str,
    result: AgentResult,
) -> tuple[str, str]:
    """Persist one agent's handoff folder and return (folder, README path)."""

    folder = agent_step_output_dir(project_id=project_id, run_id=run_id, step_id=step_id, agent_name=result.agent)
    evidence_dir = folder / "resources" / "evidence"
    findings_dir = folder / "findings"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    findings_dir.mkdir(parents=True, exist_ok=True)

    for evidence in result.evidence:
        evidence_path = evidence_dir / f"{_safe_segment(evidence.id or 'evidence')}.json"
        evidence_path.write_text(
            json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    for index, finding in enumerate(result.findings, start=1):
        finding_path = findings_dir / f"{index:02d}_{_safe_segment(finding.title or 'finding')}.md"
        finding_path.write_text(_finding_markdown(index, finding.model_dump(mode="json")), encoding="utf-8")

    readme_path = folder / "README.md"
    result.output_dir = str(folder)
    result.output_readme_path = str(readme_path)
    (folder / "result.json").write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (folder / "resources" / "index.json").write_text(
        json.dumps(
            {
                "evidence": [
                    {
                        "id": evidence.id,
                        "title": evidence.title,
                        "path": str(evidence_dir / f"{_safe_segment(evidence.id or 'evidence')}.json"),
                    }
                    for evidence in result.evidence
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (folder / _MARKER_FILE).write_text(
        json.dumps(
            {
                "agent": result.agent,
                "step_id": step_id,
                "run_id": run_id,
                "project_id": project_id,
                "readme_path": str(readme_path),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    readme_path.write_text(_readme_markdown(step_id, result), encoding="utf-8")
    return str(folder), str(readme_path)


def read_agent_output_folder(folder_path: str) -> dict[str, Any]:
    """Read a prior agent handoff folder by address for downstream agents."""

    folder = Path(folder_path).expanduser().resolve()
    marker = folder / _MARKER_FILE
    if not folder.is_dir() or not marker.is_file():
        return {"error": f"Invalid agent output folder: {folder_path}"}
    readme = folder / "README.md"
    result = folder / "result.json"
    payload: dict[str, Any] = {
        "folder_path": str(folder),
        "readme_path": str(readme),
        "readme": readme.read_text(encoding="utf-8") if readme.is_file() else "",
    }
    if result.is_file():
        payload["result"] = json.loads(result.read_text(encoding="utf-8"))
    resource_index = folder / "resources" / "index.json"
    if resource_index.is_file():
        payload["resources"] = json.loads(resource_index.read_text(encoding="utf-8"))
    return payload


def agent_step_output_dir(*, project_id: str, run_id: str, step_id: str, agent_name: str) -> Path:
    session_path = session_json_path(project_id, run_id)
    folder_name = f"{_safe_segment(step_id)}_{_safe_segment(agent_name)}"
    return session_path.parent / f"{_safe_segment(run_id)}_outputs" / folder_name


def _safe_segment(value: str) -> str:
    cleaned = _SAFE_SEGMENT.sub("_", str(value).strip()).strip("_")
    return cleaned[:120] or "item"


def _readme_markdown(step_id: str, result: AgentResult) -> str:
    lines = [
        f"# {result.agent} 输出",
        "",
        f"- Step ID: `{step_id}`",
        f"- Status: `{result.status}`",
        f"- Result JSON: `result.json`",
        f"- Evidence resources: `resources/evidence/`",
        f"- Findings: `findings/`",
        "",
        "## Summary",
        "",
        result.summary or "(empty)",
        "",
        "## Findings",
        "",
    ]
    if result.findings:
        for index, finding in enumerate(result.findings, start=1):
            lines.append(f"{index}. **{finding.title}** [{finding.risk_level}, confidence={finding.confidence}]")
            lines.append(f"   - {finding.description}")
            if finding.evidence_ids:
                lines.append(f"   - Evidence IDs: {', '.join(finding.evidence_ids)}")
    else:
        lines.append("(no findings)")
    lines.extend(["", "## Resources", ""])
    if result.evidence:
        for evidence in result.evidence:
            lines.append(f"- `{evidence.id}` {evidence.title} -> `resources/evidence/{_safe_segment(evidence.id)}.json`")
    else:
        lines.append("(no evidence resources)")
    lines.append("")
    return "\n".join(lines)


def _finding_markdown(index: int, finding: dict[str, Any]) -> str:
    evidence_ids = finding.get("evidence_ids") or []
    return "\n".join(
        [
            f"# Finding {index}: {finding.get('title', '')}",
            "",
            f"- Risk level: `{finding.get('risk_level', 'unknown')}`",
            f"- Confidence: `{finding.get('confidence', '')}`",
            f"- Evidence IDs: {', '.join(evidence_ids) if evidence_ids else '(none)'}",
            "",
            finding.get("description", ""),
            "",
        ]
    )
