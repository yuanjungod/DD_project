from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Type

from agentscope.agent import ReActAgent
from agentscope.formatter import AnthropicChatFormatter
from agentscope.message import Msg
from agentscope.model import AnthropicChatModel
from agentscope.tool import ToolResponse, Toolkit
from pydantic import BaseModel

from agent_service.api.schemas import AgentResult, CompanyConfig, Evidence
from agent_service.workflows.config_loader import AgentDefinition

ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


DEFAULT_MODEL_CONFIG = {
    "base_url": os.getenv("DD_MODEL_BASE_URL", "http://127.0.0.1:8081/v1"),
    "api_key": os.getenv("DD_MODEL_API_KEY", "yuanjun"),
    "api": os.getenv("DD_MODEL_API", "anthropic-messages"),
    "model_id": os.getenv("DD_MODEL_ID", "kimi-code"),
    "model_name": os.getenv("DD_MODEL_NAME", "kimi-code(Custom Provider)"),
    "reasoning": True,
    "context_window": int(os.getenv("DD_MODEL_CONTEXT_WINDOW", "128000")),
    "max_tokens": int(os.getenv("DD_MODEL_MAX_TOKENS", "4096")),
    "timeout_seconds": float(os.getenv("DD_MODEL_TIMEOUT_SECONDS", "120")),
}


class AgentScopeReActRuntime:
    """Builds AgentScope ReAct configuration for one configured agent.

    The runtime materializes configured `SKILL.md` packages, registers the
    selected tools with an AgentScope Toolkit, and executes an AgentScope
    ReActAgent against the configured Anthropic Messages-compatible model.
    """

    def __init__(
        self,
        definition: AgentDefinition,
        sys_prompt: str,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.definition = definition
        self.sys_prompt = sys_prompt
        self.tool_executor = tool_executor
        self.model_config = _normalize_model_config(definition.react_config.get("model", definition.react_config))
        self._temp_dir = tempfile.TemporaryDirectory(prefix=f"dd_{definition.name}_")
        self.toolkit = Toolkit()
        self.skill_dirs = self._materialize_skill_packages()
        self._register_skill_packages()
        self._register_tools()
        self.config = self._build_config()

    def close(self) -> None:
        self._temp_dir.cleanup()

    def run_model(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        evidence: list[Evidence],
        structured_model: Type[BaseModel],
    ) -> BaseModel:
        return asyncio.run(
            self._run_model_async(company_config, previous_results, evidence, structured_model)
        )

    async def _run_model_async(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        evidence: list[Evidence],
        structured_model: Type[BaseModel],
    ) -> BaseModel:
        agent = self._build_agent()
        reply = await agent.reply(
            Msg(
                name="user",
                content=self._build_task_message(company_config, previous_results, evidence),
                role="user",
            ),
            structured_model=structured_model,
        )
        if not reply.metadata:
            raise RuntimeError(f"{self.definition.name} did not return structured model output")
        return structured_model.model_validate(reply.metadata)

    def _materialize_skill_packages(self) -> list[str]:
        skill_dirs: list[str] = []
        root = Path(self._temp_dir.name)
        for package in self.definition.skill_packages:
            directory_name = package.get("directory_name") or package.get("name") or package["id"]
            safe_name = _safe_dir_name(directory_name)
            skill_dir = root / safe_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(package.get("skill_md", ""), encoding="utf-8")
            skill_dirs.append(str(skill_dir))
        return skill_dirs

    def _register_skill_packages(self) -> None:
        for skill_dir in self.skill_dirs:
            try:
                self.toolkit.register_agent_skill(skill_dir)
            except Exception:
                # Invalid skill packages are still exposed in config for audit,
                # but they should not break deterministic local runs.
                continue

    def _register_tools(self) -> None:
        for tool in self._tool_configs():
            tool_id = tool["id"]
            self.toolkit.register_tool_function(
                _make_tool_function(tool_id, tool.get("description", ""), self.tool_executor),
                func_name=tool_id,
                func_description=tool.get("description", ""),
                json_schema=_tool_json_schema(tool_id, tool.get("description", "")),
                namesake_strategy="skip",
            )

    def _build_agent(self) -> ReActAgent:
        model = AnthropicChatModel(
            model_name=self.model_config["model_id"],
            api_key=self.model_config["api_key"],
            max_tokens=self.model_config["max_tokens"],
            stream=False,
            client_kwargs={
                "base_url": _anthropic_sdk_base_url(self.model_config["base_url"]),
                "timeout": self.model_config["timeout_seconds"],
                "max_retries": 0,
            },
        )
        formatter = AnthropicChatFormatter(max_tokens=self.model_config["context_window"])
        return ReActAgent(
            name=self.definition.name,
            sys_prompt=self.sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=self.toolkit,
            max_iters=self.definition.react_config.get("max_iters", 6),
            parallel_tool_calls=self.definition.react_config.get("parallel_tool_calls", False),
            enable_rewrite_query=False,
        )

    def _build_task_message(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        evidence: list[Evidence],
    ) -> str:
        payload = {
            "target_company": company_config.target_company.model_dump(mode="json"),
            "scope": company_config.scope.model_dump(mode="json"),
            "project_resources": company_config.resources.model_dump(mode="json"),
            "available_evidence": [item.model_dump(mode="json") for item in evidence],
            "previous_agent_results": [
                {
                    "agent": result.agent,
                    "summary": result.summary,
                    "findings": [finding.model_dump(mode="json") for finding in result.findings],
                }
                for result in previous_results
            ],
        }
        return (
            "Run this due diligence agent with the configured AgentScope ReAct tools, "
            "skills, and resources. Use tools if you need more evidence. "
            "When finished, call generate_response with a concise summary and "
            "source-backed findings. Use only risk_level values low, medium, high, or unknown. "
            "Use evidence IDs from available_evidence whenever possible.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _build_config(self) -> dict[str, Any]:
        return {
            "agent_type": "agentscope.agent.ReActAgent",
            "name": self.definition.name,
            "role": self.definition.role,
            "sys_prompt": self.sys_prompt,
            "toolkit": {
                "tool_ids": [tool["id"] for tool in self._tool_configs()],
                "json_schemas": self.toolkit.get_json_schemas(),
                "agent_skill_prompt": self.toolkit.get_agent_skill_prompt(),
            },
            "skills": [
                {
                    "id": package["id"],
                    "directory_name": package.get("directory_name"),
                    "description": package.get("description", ""),
                }
                for package in self.definition.skill_packages
            ],
            "resources": self.definition.resource_configs,
            "react": {
                "max_iters": self.definition.react_config.get("max_iters", 6),
                "parallel_tool_calls": self.definition.react_config.get("parallel_tool_calls", False),
                "model_configured": True,
                "execution_mode": "agentscope_react_real_model",
                "model": {
                    "base_url": self.model_config["base_url"],
                    "api": self.model_config["api"],
                    "id": self.model_config["model_id"],
                    "name": self.model_config["model_name"],
                    "reasoning": self.model_config["reasoning"],
                    "context_window": self.model_config["context_window"],
                    "max_tokens": self.model_config["max_tokens"],
                    "api_key_configured": bool(self.model_config["api_key"]),
                },
            },
        }

    def _tool_configs(self) -> list[dict[str, Any]]:
        if self.definition.tool_configs:
            return self.definition.tool_configs
        return [
            {
                "id": tool_id,
                "name": tool_id,
                "description": f"Configured due diligence tool {tool_id}",
                "implementation": f"agent_service.tools.{tool_id}",
            }
            for tool_id in self.definition.tools
        ]


def build_react_system_prompt(definition: AgentDefinition, base_prompt: str) -> str:
    sections = [
        f"# Agent Role\n{definition.role}",
        "# Task Prompt\n" + base_prompt,
    ]
    if definition.resource_configs:
        resources = "\n".join(
            f"- {resource['id']}: {resource.get('name', '')} ({resource.get('type', '')})"
            for resource in definition.resource_configs
        )
        sections.append("# Bound Resources\n" + resources)
    return "\n\n".join(sections)


def _make_tool_function(
    tool_id: str,
    description: str,
    tool_executor: ToolExecutor | None,
) -> Callable[..., ToolResponse]:
    def tool_function(query: str = "", url: str = "", file_id: str = "") -> ToolResponse:
        """Execute a configured due diligence tool."""

        payload = {
            "query": query,
            "url": url,
            "file_id": file_id,
        }
        result = (
            tool_executor(tool_id, payload)
            if tool_executor
            else {"tool_id": tool_id, "description": description, **payload}
        )
        return ToolResponse(
            content=[{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            metadata={"tool_id": tool_id, "result": result},
        )

    return tool_function


def _tool_json_schema(tool_id: str, description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool_id,
            "description": description or f"Configured due diligence tool {tool_id}",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "url": {"type": "string"},
                    "file_id": {"type": "string"},
                },
                "required": [],
            },
        },
    }


def _safe_dir_name(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in value.lower())
    return f"{safe}-{digest}"


def _normalize_model_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    model_config = dict(DEFAULT_MODEL_CONFIG)
    if not raw_config:
        return model_config

    model_config.update(
        {
            "base_url": raw_config.get("base_url", raw_config.get("baseUrl", model_config["base_url"])),
            "api_key": raw_config.get("api_key", raw_config.get("apiKey", model_config["api_key"])),
            "api": raw_config.get("api", model_config["api"]),
            "model_id": raw_config.get("model_id", raw_config.get("id", model_config["model_id"])),
            "model_name": raw_config.get("model_name", raw_config.get("name", model_config["model_name"])),
            "reasoning": raw_config.get("reasoning", model_config["reasoning"]),
            "context_window": raw_config.get(
                "context_window",
                raw_config.get("contextWindow", model_config["context_window"]),
            ),
            "max_tokens": raw_config.get("max_tokens", raw_config.get("maxTokens", model_config["max_tokens"])),
        }
    )

    models = raw_config.get("models") or []
    if models:
        selected = models[0]
        model_config.update(
            {
                "model_id": selected.get("id", model_config["model_id"]),
                "model_name": selected.get("name", model_config["model_name"]),
                "reasoning": selected.get("reasoning", model_config["reasoning"]),
                "context_window": selected.get("contextWindow", model_config["context_window"]),
                "max_tokens": selected.get("maxTokens", model_config["max_tokens"]),
            }
        )
    return model_config


def _anthropic_sdk_base_url(base_url: str) -> str:
    # The UI/provider config uses `/v1`; Anthropic's SDK appends `/v1/messages`.
    normalized = base_url.rstrip("/")
    return normalized.removesuffix("/v1")
