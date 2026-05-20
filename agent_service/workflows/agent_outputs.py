from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent_service.api.schemas import AgentResult
from agent_service.session_history import session_json_path

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


def agent_step_output_dir(*, project_id: str, run_id: str, step_id: str, agent_name: str) -> Path:
    session_path = session_json_path(project_id, run_id)
    folder_name = f"{_safe_segment(step_id)}_{_safe_segment(agent_name)}"
    return session_path.parent / f"{_safe_segment(run_id)}_outputs" / folder_name


def _safe_segment(value: str) -> str:
    cleaned = _SAFE_SEGMENT.sub("_", str(value).strip()).strip("_")
    return cleaned[:120] or "item"
