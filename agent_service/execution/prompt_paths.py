from __future__ import annotations

import copy
from typing import Any

from agent_service.api.schemas import AgentResult
from agent_service.execution.context import RunExecutionContext


def translate_handoff_for_prompt(handoff: dict[str, Any], ctx: RunExecutionContext | None) -> dict[str, Any]:
    if ctx is None or not ctx.is_docker:
        return handoff
    payload = copy.deepcopy(handoff)
    for key in ("previous_agent_output_folders", "previous_agent_handoff_readmes"):
        entries = payload.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for field in ("output_dir", "readme_path"):
                value = entry.get(field)
                if isinstance(value, str) and value.strip():
                    entry[field] = ctx.display_path(value)
    return payload


def display_agent_results_for_prompt(
    previous_results: list[AgentResult],
    ctx: RunExecutionContext | None,
) -> list[tuple[str, str | None, str | None, str]]:
    """Return tuples of (agent, status, output_dir, readme_path display, readme text)."""
    rows: list[tuple[str, str | None, str | None, str]] = []
    for result in previous_results:
        output_dir = ctx.display_path(result.output_dir) if result.output_dir else None
        readme_path = ctx.display_path(result.output_readme_path) if result.output_readme_path else None
        rows.append((result.agent, result.status, output_dir, readme_path))
    return rows
