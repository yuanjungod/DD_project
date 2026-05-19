from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_service.api.schemas import AgentResult, CompanyConfig, Finding
from agent_service.agents.react_runtime import AgentScopeReActRuntime, build_react_system_prompt
from agent_service.tools.research import (
    MockFileReaderTool,
    MockSearchTool,
    MockVectorRetrievalTool,
    MockWebFetchTool,
)
from agent_service.workflows.config_loader import AgentDefinition
from agent_service.workflows.agent_outputs import read_agent_output_folder


class ModelAgentOutput(BaseModel):
    summary: str
    findings: list[Finding] = Field(default_factory=list)


class ConfiguredAgentRunner:
    def __init__(self, definition: AgentDefinition) -> None:
        self.definition = definition
        self.prompt = (definition.prompt_text or definition.prompt or "").strip()
        if not self.prompt:
            raise ValueError(f"Agent {definition.name} is missing prompt content")
        self.search = MockSearchTool()
        self.web_fetch = MockWebFetchTool()
        self.file_reader = MockFileReaderTool()
        self.vector_retrieval = MockVectorRetrievalTool()
        self.current_company_config: CompanyConfig | None = None
        self.react_runtime = AgentScopeReActRuntime(
            definition,
            sys_prompt=build_react_system_prompt(definition, self.prompt),
            tool_executor=self._execute_react_tool,
        )

    def _visible_uploaded_file_ids(self, company_config: CompanyConfig) -> list[str]:
        full = list(company_config.resources.uploaded_files or [])
        allow = [x.strip() for x in (self.definition.platform_upload_file_ids or []) if x and str(x).strip()]
        scoped = self._project_scoped_file_ids(company_config)
        if scoped:
            allow = [*allow, *scoped] if allow else scoped
        if not allow:
            return full
        allow_set = set(allow)
        return [fid for fid in full if fid in allow_set]

    def _project_scoped_file_ids(self, company_config: CompanyConfig) -> list[str]:
        scopes = company_config.resources.agent_resource_scopes or []
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

    def run(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        *,
        continuation_context: dict[str, Any] | None = None,
    ) -> AgentResult:
        try:
            self.current_company_config = company_config
            agent_name = self.definition.name
            model_output = self.react_runtime.run_model(
                company_config=company_config,
                previous_results=previous_results,
                structured_model=ModelAgentOutput,
                continuation_context=continuation_context,
            )
            return AgentResult(
                agent=agent_name,
                status="completed",
                summary=model_output.summary,
                findings=model_output.findings,
            )
        finally:
            self.current_company_config = None
            self.react_runtime.close()

    def run_step_review_chat(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        *,
        current_step_summary: str,
        current_findings: list[dict[str, Any]],
        chat_messages: list[dict[str, str]],
        user_message: str,
    ) -> str:
        try:
            self.current_company_config = company_config
            return self.react_runtime.run_step_review_chat(
                company_config,
                previous_results,
                current_step_summary=current_step_summary,
                current_findings=current_findings,
                chat_messages=chat_messages,
                user_message=user_message,
            )
        finally:
            self.current_company_config = None
            self.react_runtime.close()

    def _execute_react_tool(self, tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        company_config = self.current_company_config
        if company_config is None:
            raise RuntimeError("Tool execution requires an active company config")

        agent_name = self.definition.name
        if tool_id == "search":
            query = payload.get("query") or f"{company_config.target_company.name} {self.definition.role}"
            return {"source": self.search.run(str(query), company_config, agent_name)}
        if tool_id == "web_fetch":
            url = payload.get("url") or company_config.target_company.website
            return {"source": self.web_fetch.run(str(url), company_config, agent_name)}
        if tool_id == "file_reader":
            visible = self._visible_uploaded_file_ids(company_config)
            file_id = payload.get("file_id") or next(iter(visible), "")
            return {"source": self.file_reader.run(str(file_id), company_config, agent_name)}
        if tool_id == "vector_retrieval":
            query = payload.get("query") or f"{company_config.target_company.name} {' '.join(company_config.scope.focus_areas)}"
            return {"source": self.vector_retrieval.run(str(query), company_config, agent_name)}
        if tool_id == "report_store":
            return {"message": "Report store is used after all agents finish."}
        if tool_id == "agent_output_reader":
            folder_path = payload.get("folder_path") or payload.get("query") or ""
            return read_agent_output_folder(str(folder_path))
        return {"message": f"Tool {tool_id} is configured but has no local executor yet."}
