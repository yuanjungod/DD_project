from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agent_service.api.schemas import CompanyConfig
from agent_service.workflows.config_loader import AgentDefinition


@dataclass
class ToolExecutionContext:
    company_config: CompanyConfig
    agent_name: str
    definition: AgentDefinition

    @property
    def agent_role(self) -> str:
        return self.definition.role

    def visible_uploaded_file_ids(self) -> list[str]:
        full = list(self.company_config.resources.uploaded_files or [])
        allow = [x.strip() for x in (self.definition.platform_upload_file_ids or []) if x and str(x).strip()]
        scoped = self._project_scoped_file_ids()
        if scoped:
            allow = [*allow, *scoped] if allow else scoped
        if not allow:
            return full
        allow_set = set(allow)
        return [fid for fid in full if fid in allow_set]

    def _project_scoped_file_ids(self) -> list[str]:
        scopes = self.company_config.resources.agent_resource_scopes or []
        selected: list[str] = []
        for scope in scopes:
            if not isinstance(scope, dict) or scope.get("agent_id") != self.definition.name:
                continue
            raw_ids = scope.get("uploaded_file_ids") or scope.get("file_ids") or []
            if isinstance(raw_ids, str):
                raw_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
            if isinstance(raw_ids, list):
                selected.extend(str(x).strip() for x in raw_ids if str(x).strip())
        return selected


class ExecutableTool(Protocol):
    def execute(self, payload: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]: ...
