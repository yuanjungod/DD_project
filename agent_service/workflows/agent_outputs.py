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
    folder.mkdir(parents=True, exist_ok=True)

    readme_path = folder / "README.md"
    result.output_dir = str(folder)
    result.output_readme_path = str(readme_path)
    (folder / "result.json").write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
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
        "",
        "Use `agent_output_reader` or read `result.json` for structured step metadata.",
        "",
    ]
    return "\n".join(lines)
