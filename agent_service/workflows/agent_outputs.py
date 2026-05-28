from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_service.api.schemas import AgentResult
from agent_service.scenario_layout import session_json_path

_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9_-]+")

_MAX_README_IN_PROMPT = 12_000


def load_handoff_readme(readme_path: str) -> str:
    """Load README.md for prompt injection; empty string if missing."""
    path = Path(readme_path).expanduser()
    if path.is_dir():
        path = path / "README.md"
    elif path.name != "README.md":
        path = path.parent / "README.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) > _MAX_README_IN_PROMPT:
        return text[:_MAX_README_IN_PROMPT] + "\n…(truncated)"
    return text


def build_previous_agent_handoff_context(previous_results: list[AgentResult]) -> dict[str, Any]:
    """Output folder paths plus inlined README content for downstream agent prompts."""
    folders: list[dict[str, str]] = []
    readmes: list[dict[str, str]] = []
    for result in previous_results:
        if not result.output_dir:
            continue
        readme_path = result.output_readme_path or str(Path(result.output_dir) / "README.md")
        entry = {
            "agent": result.agent,
            "output_dir": result.output_dir,
            "readme_path": readme_path,
        }
        folders.append(entry)
        readme = load_handoff_readme(readme_path)
        if readme:
            readmes.append({**entry, "readme": readme})
    payload: dict[str, Any] = {}
    if folders:
        payload["previous_agent_output_folders"] = folders
    if readmes:
        payload["previous_agent_handoff_readmes"] = readmes
    return payload


def agent_step_output_dir(
    *,
    workflow_template_id: str,
    user_id: str,
    project_id: str,
    session_id: str,
    run_id: str,
    step_id: str,
    agent_name: str,
) -> Path:
    session_path = session_json_path(workflow_template_id, user_id, project_id, run_id, session_id)
    folder_name = f"{_safe_segment(step_id)}_{_safe_segment(agent_name)}"
    return session_path.parent / "outputs" / f"{_safe_segment(run_id)}_outputs" / folder_name


def ensure_step_output_handoff(
    output_dir: str,
    *,
    agent: str,
    step_id: str,
    status: str,
    summary: str = "",
) -> tuple[str, str]:
    """Create the step output folder and README if the agent did not write them."""
    folder = Path(output_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    readme_path = folder / "README.md"
    if not readme_path.is_file():
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        body = summary.strip() or "（Agent 未写入步骤总结；以下为平台自动生成的占位 README。）"
        readme_path.write_text(
            "\n".join(
                [
                    f"# {agent} — {step_id}",
                    "",
                    f"- **status**: `{status}`",
                    f"- **completed_at**: {now}",
                    f"- **output_dir**: `{folder}`",
                    "",
                    "## 步骤总结",
                    "",
                    body,
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return str(folder.resolve()), str(readme_path.resolve())


def _safe_segment(value: str) -> str:
    cleaned = _SAFE_SEGMENT.sub("_", str(value).strip()).strip("_")
    return cleaned[:120] or "item"
