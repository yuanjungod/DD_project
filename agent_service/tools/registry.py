from __future__ import annotations

import importlib
from typing import Any

from agent_service.tools.base import ExecutableTool, ToolExecutionContext
from agent_service.workflows.agent_outputs import read_agent_output_folder
from agent_service.workflows.config_loader import AgentDefinition, load_tool_config

# Built-in handoff tool when absent from snapshot / catalog.
AGENT_OUTPUT_READER_CONFIG: dict[str, Any] = {
    "id": "agent_output_reader",
    "name": "agent_output_reader",
    "description": (
        "Read a previous agent handoff folder by folder_path and return README, result, and resource index."
    ),
    "implementation": "agent_service.workflows.agent_outputs.read_agent_output_folder",
    "enabled": True,
}


def resolve_callable(implementation: str) -> Any:
    module_path, _, attr = implementation.rpartition(".")
    if not module_path or not attr:
        raise ValueError(f"Invalid tool implementation path: {implementation}")
    module = importlib.import_module(module_path)
    return getattr(module, attr)


class ToolRegistry:
    """Execute tools using each catalog entry's implementation path."""

    def __init__(self, tool_configs: list[dict[str, Any]]) -> None:
        self._configs: dict[str, dict[str, Any]] = {}
        for raw in _ensure_handoff_tool(tool_configs):
            tool_id = str(raw.get("id") or "").strip()
            if tool_id:
                self._configs[tool_id] = raw
        self._instances: dict[str, Any] = {}

    @classmethod
    def for_agent_definition(cls, definition: AgentDefinition) -> ToolRegistry:
        configs = list(definition.tool_configs or [])
        if not configs:
            configs = _tool_configs_from_catalog(definition.tool_ids or definition.tools)
        return cls(configs)

    @property
    def tool_configs(self) -> list[dict[str, Any]]:
        return list(self._configs.values())

    def execute(self, tool_id: str, payload: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        config = self._configs.get(tool_id)
        if config is None:
            return {"message": f"Tool {tool_id} is not registered for this agent."}
        if config.get("enabled") is False:
            return {"message": f"Tool {tool_id} is disabled."}

        implementation = str(config.get("implementation") or "").strip()
        if not implementation:
            return {"message": f"Tool {tool_id} has no implementation."}

        try:
            target = resolve_callable(implementation)
        except Exception as exc:
            return {"message": f"Tool {tool_id} failed to load {implementation}: {exc}"}

        try:
            return self._invoke(target, tool_id, payload, context, implementation)
        except Exception as exc:
            return {"message": f"Tool {tool_id} execution failed: {exc}"}

    def _invoke(
        self,
        target: Any,
        tool_id: str,
        payload: dict[str, Any],
        context: ToolExecutionContext,
        implementation: str,
    ) -> dict[str, Any]:
        if isinstance(target, type):
            instance = self._instance(implementation, target)
            if hasattr(instance, "execute"):
                return instance.execute(payload, context)
            raise TypeError(f"{implementation} has no execute(payload, context) method")

        if hasattr(target, "execute"):
            return target.execute(payload, context)

        if callable(target):
            folder_path = payload.get("folder_path") or payload.get("query") or ""
            if target is read_agent_output_folder or getattr(target, "__name__", "") == "read_agent_output_folder":
                return read_agent_output_folder(str(folder_path))
            raise TypeError(f"Callable implementation {implementation} is not supported")

        raise TypeError(f"Unsupported implementation for {tool_id}: {implementation}")

    def _instance(self, implementation: str, cls: type) -> Any:
        if implementation not in self._instances:
            self._instances[implementation] = cls()
        return self._instances[implementation]


def _tool_configs_from_catalog(tool_ids: list[str]) -> list[dict[str, Any]]:
    catalog = load_tool_config()
    configs: list[dict[str, Any]] = []
    for tool_id in tool_ids:
        entry = catalog.tools.get(tool_id)
        if entry is None:
            continue
        configs.append(
            {
                "id": tool_id,
                "name": tool_id,
                "description": entry.description,
                "implementation": entry.implementation,
                "requires_api_key": entry.requires_api_key,
                "enabled": True,
            }
        )
    return configs


def _ensure_handoff_tool(configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if any(str(c.get("id")) == "agent_output_reader" for c in configs):
        return configs
    return [*configs, dict(AGENT_OUTPUT_READER_CONFIG)]


def verify_catalog_implementations(tool_configs: list[dict[str, Any]] | None = None) -> list[str]:
    """Return error strings for tools whose implementation cannot be loaded."""
    configs = tool_configs if tool_configs is not None else _all_catalog_configs()
    errors: list[str] = []
    for config in configs:
        tool_id = str(config.get("id") or "")
        implementation = str(config.get("implementation") or "").strip()
        if not tool_id or not implementation:
            errors.append(f"{tool_id or '?'}: missing id or implementation")
            continue
        try:
            resolve_callable(implementation)
        except Exception as exc:
            errors.append(f"{tool_id}: {implementation} — {exc}")
    return errors


def _all_catalog_configs() -> list[dict[str, Any]]:
    catalog = load_tool_config()
    return [
        {
            "id": tool_id,
            "implementation": entry.implementation,
            "enabled": True,
        }
        for tool_id, entry in catalog.tools.items()
    ] + [dict(AGENT_OUTPUT_READER_CONFIG)]
