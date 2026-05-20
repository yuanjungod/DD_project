from __future__ import annotations

from typing import Any

from agent_service.api.schemas import AgentResult, CompanyConfig
from agent_service.agents.react_runtime import AgentScopeReActRuntime, build_react_system_prompt
from agent_service.tools.base import ToolExecutionContext
from agent_service.tools.registry import ToolRegistry
from agent_service.workflows.config_loader import AgentDefinition


class ConfiguredAgentRunner:
    def __init__(self, definition: AgentDefinition) -> None:
        self.definition = definition
        self.prompt = (definition.prompt_text or definition.prompt or "").strip()
        if not self.prompt:
            raise ValueError(f"Agent {definition.name} is missing prompt content")
        self.current_company_config: CompanyConfig | None = None
        self.tool_registry = ToolRegistry.for_agent_definition(definition)
        self.react_runtime = AgentScopeReActRuntime(
            definition,
            sys_prompt=build_react_system_prompt(definition, self.prompt),
            tool_executor=self._execute_react_tool,
        )

    def run(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        *,
        continuation_context: dict[str, Any] | None = None,
        agent_output_dir: str | None = None,
    ) -> AgentResult:
        try:
            self.current_company_config = company_config
            agent_name = self.definition.name
            self.react_runtime.run_model(
                company_config=company_config,
                previous_results=previous_results,
                continuation_context=continuation_context,
                agent_output_dir=agent_output_dir,
            )
            return AgentResult(
                agent=agent_name,
                status="completed",
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
        current_output_dir: str,
        chat_messages: list[dict[str, str]],
        user_message: str,
    ) -> str:
        try:
            self.current_company_config = company_config
            return self.react_runtime.run_step_review_chat(
                company_config,
                previous_results,
                current_step_summary=current_step_summary,
                current_output_dir=current_output_dir,
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

        context = ToolExecutionContext(
            company_config=company_config,
            agent_name=self.definition.name,
            definition=self.definition,
        )
        return self.tool_registry.execute(tool_id, payload, context)
