from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Type

from agentscope.agent import ReActAgent
from agentscope.formatter import AnthropicChatFormatter, DeepSeekChatFormatter, OpenAIChatFormatter
from agentscope.message import Msg
from agentscope.model import AnthropicChatModel, OpenAIChatModel
from agentscope.tool import (
    ToolResponse,
    Toolkit,
    execute_python_code,
    execute_shell_command,
    view_text_file,
)
from pydantic import BaseModel

from agent_service.api.schemas import AgentResult, CompanyConfig
from agent_service.workflows.agent_outputs import build_previous_agent_handoff_context, load_handoff_readme
from agent_service.workflows.config_loader import AgentDefinition


class StepReviewChatModel(BaseModel):
    reply: str


ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


DEFAULT_MAX_REACT_ITERS = 50

DEFAULT_MODEL_CONFIG = {
    "base_url": os.getenv("HARNESS_MODEL_BASE_URL") or os.getenv("DD_MODEL_BASE_URL", "http://127.0.0.1:8080/v1"),
    "api_key": os.getenv("HARNESS_MODEL_API_KEY") or os.getenv("DD_MODEL_API_KEY", "yuanjun"),
    "api": os.getenv("HARNESS_MODEL_API") or os.getenv("DD_MODEL_API", "openai-completions"),
    "model_id": os.getenv("HARNESS_MODEL_ID") or os.getenv("DD_MODEL_ID", "deepseek-v4-flash"),
    "model_name": os.getenv("HARNESS_MODEL_NAME") or os.getenv("DD_MODEL_NAME", "deepseek-v4-flash"),
    "reasoning": False,
    "context_window": int(os.getenv("HARNESS_MODEL_CONTEXT_WINDOW") or os.getenv("DD_MODEL_CONTEXT_WINDOW", "128000")),
    "max_tokens": int(os.getenv("HARNESS_MODEL_MAX_TOKENS") or os.getenv("DD_MODEL_MAX_TOKENS", "4096")),
    "timeout_seconds": float(os.getenv("HARNESS_MODEL_TIMEOUT_SECONDS") or os.getenv("DD_MODEL_TIMEOUT_SECONDS", "120")),
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
        *,
        continuation_context: dict[str, Any] | None = None,
        agent_output_dir: str | None = None,
    ) -> None:
        asyncio.run(
            self._run_model_async(
                company_config,
                previous_results,
                continuation_context=continuation_context,
                agent_output_dir=agent_output_dir,
            )
        )

    async def _run_model_async(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        *,
        continuation_context: dict[str, Any] | None = None,
        agent_output_dir: str | None = None,
    ) -> None:
        agent = self._build_agent()
        await agent.reply(
            Msg(
                name="user",
                content=self._build_task_message(
                    company_config,
                    previous_results,
                    continuation_context=continuation_context,
                    agent_output_dir=agent_output_dir,
                ),
                role="user",
            ),
        )

    def _materialize_skill_packages(self) -> list[str]:
        skill_dirs: list[str] = []
        root = Path(self._temp_dir.name)
        for package in self.definition.skill_packages:
            directory_name = package.get("directory_name") or package.get("name") or package["id"]
            safe_name = _safe_dir_name(directory_name)
            skill_dir = root / safe_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(package.get("skill_md", ""), encoding="utf-8")
            for file_name, content in package.get("package_files", {}).items():
                if file_name != "SKILL.md":
                    _write_skill_file(skill_dir, file_name, content)
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

    def _register_agentscope_builtin_tools(self) -> None:
        for tool_fn in (execute_shell_command, execute_python_code, view_text_file):
            self.toolkit.register_tool_function(tool_fn, namesake_strategy="skip")

    def _register_tools(self) -> None:
        self._register_agentscope_builtin_tools()
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
        model, formatter = _create_model_and_formatter(self.model_config)
        return ReActAgent(
            name=self.definition.name,
            sys_prompt=self.sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=self.toolkit,
            max_iters=self.definition.react_config.get("max_iters", DEFAULT_MAX_REACT_ITERS),
            parallel_tool_calls=self.definition.react_config.get("parallel_tool_calls", False),
            enable_rewrite_query=False,
        )

    def _build_task_message(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        *,
        continuation_context: dict[str, Any] | None = None,
        agent_output_dir: str | None = None,
    ) -> str:
        handoff = build_previous_agent_handoff_context(previous_results)
        readme_by_agent = {
            entry["agent"]: entry.get("readme", "")
            for entry in handoff.get("previous_agent_handoff_readmes", [])
        }
        sections: list[str] = [
            "## 任务说明",
            "",
            "请使用已配置的 AgentScope ReAct 工具、技能与资源完成本步骤。",
            "需要额外来源材料时请调用工具。",
            "上游 Agent 通过 **output_dir** 交接产物；可用 `view_text_file`、`execute_shell_command`",
            "完成后请用简短中文总结你所写或所做的工作,总结工作和产出都写在README.md中。",
            "",
        ]
        sections.extend(
            _markdown_json_section(
                "target_company（目标公司）",
                company_config.target_company.model_dump(mode="json"),
            )
        )
        sections.extend(
            _markdown_json_section(
                "project_resources（项目资源）",
                company_config.resources.model_dump(mode="json"),
            )
        )
        sections.extend(_markdown_previous_agent_results(previous_results, readme_by_agent))
        sections.extend(_markdown_agent_output_dir(agent_output_dir, self.definition.name))
        if continuation_context:
            sections.extend(
                _markdown_json_section(
                    "continuation_from_previous_session_attempt（续跑上下文）",
                    continuation_context,
                )
            )
        return "\n".join(sections).rstrip() + "\n"

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
        return asyncio.run(
            self._run_step_review_chat_async(
                company_config,
                previous_results,
                current_step_summary=current_step_summary,
                current_output_dir=current_output_dir,
                chat_messages=chat_messages,
                user_message=user_message,
            )
        )

    async def _run_step_review_chat_async(
        self,
        company_config: CompanyConfig,
        previous_results: list[AgentResult],
        *,
        current_step_summary: str,
        current_output_dir: str,
        chat_messages: list[dict[str, str]],
        user_message: str,
    ) -> str:
        agent = self._build_agent()
        payload: dict[str, Any] = {
            "review_chat": True,
            "instruction_zh": (
                "尽调复核对话：用户对当前这一步 Agent 的输出进行校验或要求修订。"
                "用清晰中文回复（除非用户用其他语言）。可指出逻辑/来源缺口、建议如何修订输出目录中的内容，不要编造未出现的来源。"
            ),
            "target_company": company_config.target_company.model_dump(mode="json"),
            "previous_agent_results": [
                {
                    "agent": result.agent,
                    "status": result.status,
                    "output_dir": result.output_dir,
                    "output_readme_path": result.output_readme_path,
                }
                for result in previous_results
            ],
            "current_agent_step_summary": current_step_summary,
            "current_agent_output_dir": current_output_dir,
            "prior_turns": chat_messages,
            "user_message": user_message,
        }
        payload.update(build_previous_agent_handoff_context(previous_results))
        if current_output_dir:
            current_readme = load_handoff_readme(str(Path(current_output_dir) / "README.md"))
            if current_readme:
                payload["current_agent_handoff_readme"] = current_readme
        reply = await agent.reply(
            Msg(
                name="user",
                content=json.dumps(payload, ensure_ascii=False, indent=2),
                role="user",
            ),
            structured_model=StepReviewChatModel,
        )
        if not reply.metadata:
            raise RuntimeError(f"{self.definition.name} did not return structured review chat output")
        return StepReviewChatModel.model_validate(reply.metadata).reply

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
                "max_iters": self.definition.react_config.get("max_iters", DEFAULT_MAX_REACT_ITERS),
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
        from agent_service.tools.registry import ToolRegistry

        return ToolRegistry.for_agent_definition(self.definition).tool_configs


def _markdown_json_section(heading: str, data: Any) -> list[str]:
    return [
        f"## {heading}",
        "",
        "```json",
        json.dumps(data, ensure_ascii=False, indent=2),
        "```",
        "",
    ]


def _markdown_previous_agent_results(
    previous_results: list[AgentResult],
    readme_by_agent: dict[str, str],
) -> list[str]:
    lines = [
        "## previous_agent_results（上游 Agent 结果）",
        "",
    ]
    if not previous_results:
        lines.extend(["（无上游步骤）", ""])
        return lines

    for result in previous_results:
        lines.append(f"### {result.agent}")
        lines.append("")
        lines.append(f"- **status**: `{result.status}`")
        if result.output_dir:
            lines.append(f"- **output_dir**: `{result.output_dir}`")
        if result.output_readme_path:
            lines.append(f"- **output_readme_path**: `{result.output_readme_path}`")
        readme = (readme_by_agent.get(result.agent) or "").strip()
        if readme:
            lines.extend(["", "#### README.md（交接摘要）", "", readme])
        lines.append("")
    return lines


def _markdown_agent_output_dir(agent_output_dir: str | None, agent_name: str) -> list[str]:
    lines = [
        "## agent_output_dir（本 Agent 输出目录）",
        "",
    ]
    if agent_output_dir:
        lines.extend(
            [
                f"- **agent**: `{agent_name}`",
                f"- **output_dir**: `{agent_output_dir}`",
                "",
                "请将本步骤产出写入该目录（至少包含 `README.md`，"
                "可使用 `execute_shell_command` / `execute_python_code` 创建与更新文件）。",
            ]
        )
    else:
        lines.append("（路径将在工作流步骤完成后由平台写入 `AgentResult.output_dir`）")
    lines.append("")
    return lines


def build_react_system_prompt(definition: AgentDefinition, base_prompt: str) -> str:
    sections = [
        f"# Agent Role\n{definition.role}",
        "# Task Prompt\n" + base_prompt,
    ]
    catalog = _format_bound_resources_for_sys_prompt(definition.resource_configs)
    if catalog:
        sections.append("# 绑定的平台资源（登记详情）\n" + catalog)
    allow_files = [str(x).strip() for x in (definition.platform_upload_file_ids or []) if str(x).strip()]
    if allow_files:
        lines = [
            "下列为本 Agent **限定可见**的平台共享上传文件 `file_id`。调用文件相关工具时请优先基于这些 ID：",
            "",
            *[f"- `{fid}`" for fid in allow_files],
        ]
        sections.append("# 平台共享文件限定\n" + "\n".join(lines))
    return "\n\n".join(sections)


def _connection_config_sys_text(cfg: dict[str, Any], *, max_chars: int = 8000) -> str:
    if not cfg:
        return "(无额外登记字段)"
    try:
        text = json.dumps(cfg, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        text = str(cfg)
    if len(text) > max_chars:
        return text[:max_chars] + "\n…(已截断)"
    return text


def _format_bound_resources_for_sys_prompt(resources: list[dict[str, Any]]) -> str:
    """Human-readable catalog text injected into the agent system prompt."""
    if not resources:
        return ""
    lines = [
        "以下为编排中为当前 Agent 勾选的平台资源条目。**名称、描述与登记字段**均来自平台配置，",
        "请在分析与选用工具时以此为上下文（不要求背诵 ID，但要遵守描述中的约束与用途说明）。",
        "",
    ]
    for idx, r in enumerate(resources, start=1):
        rid = str(r.get("id", "") or "").strip() or "(no-id)"
        name = str(r.get("name", "") or "").strip()
        rtype = str(r.get("type", "") or "").strip()
        desc = str(r.get("description", "") or "").strip()
        conn = r.get("connection_config")
        conn_dict = conn if isinstance(conn, dict) else {}

        lines.append(f"## {idx}. `{rid}`")
        lines.append(f"- **名称**: {name or '—'}")
        lines.append(f"- **类型**: {rtype or '—'}")
        lines.append(f"- **描述**: {desc or '—'}")
        lines.append("- **登记详情 (connection_config)**:")
        lines.append("```json")
        lines.append(_connection_config_sys_text(conn_dict))
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip()


def _make_tool_function(
    tool_id: str,
    description: str,
    tool_executor: ToolExecutor | None,
) -> Callable[..., ToolResponse]:
    def tool_function(query: str = "", url: str = "", file_id: str = "", folder_path: str = "") -> ToolResponse:
        """Execute a configured due diligence tool."""

        payload = {
            "query": query,
            "url": url,
            "file_id": file_id,
            "folder_path": folder_path,
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
                    "folder_path": {"type": "string"},
                },
                "required": [],
            },
        },
    }


def _safe_dir_name(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in value.lower())
    return f"{safe}-{digest}"


def _write_skill_file(skill_dir: Path, file_name: str, content: str) -> None:
    target = (skill_dir / file_name).resolve()
    if not target.is_relative_to(skill_dir.resolve()):
        raise ValueError(f"Skill file path escapes skill directory: {file_name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(content), encoding="utf-8")


def _create_model_and_formatter(model_config: dict[str, Any]):
    api = str(model_config.get("api") or "openai-completions").lower()
    if api in {"openai-completions", "openai", "openai_chat", "openai-chat", "deepseek-completions", "deepseek"}:
        model = OpenAIChatModel(
            model_name=model_config["model_id"],
            api_key=model_config["api_key"],
            stream=False,
            client_kwargs={
                "base_url": _openai_sdk_base_url(model_config["base_url"]),
                "timeout": model_config["timeout_seconds"],
                "max_retries": 0,
            },
            generate_kwargs={"max_tokens": model_config["max_tokens"]},
        )
        formatter_cls = (
            DeepSeekChatFormatter
            if _uses_deepseek_reasoning_formatter(model_config, api)
            else OpenAIChatFormatter
        )
        formatter = formatter_cls(max_tokens=model_config["context_window"])
        return model, formatter

    model = AnthropicChatModel(
        model_name=model_config["model_id"],
        api_key=model_config["api_key"],
        max_tokens=model_config["max_tokens"],
        stream=False,
        client_kwargs={
            "base_url": _anthropic_sdk_base_url(model_config["base_url"]),
            "timeout": model_config["timeout_seconds"],
            "max_retries": 0,
        },
    )
    formatter = AnthropicChatFormatter(max_tokens=model_config["context_window"])
    return model, formatter


def _normalize_model_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    model_config = dict(DEFAULT_MODEL_CONFIG)
    if not raw_config:
        return model_config

    api_mode = raw_config.get("api_mode") or raw_config.get("apiMode")
    top_level_model = raw_config.get("model")
    if isinstance(top_level_model, str) and top_level_model.strip():
        model_config["model_id"] = top_level_model.strip()
        model_config["model_name"] = top_level_model.strip()

    model_config.update(
        {
            "base_url": raw_config.get(
                "base_url",
                raw_config.get("baseUrl", raw_config.get("apibase", model_config["base_url"])),
            ),
            "api_key": raw_config.get("api_key", raw_config.get("apiKey", model_config["api_key"])),
            "api": api_mode or raw_config.get("api", model_config["api"]),
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


def _uses_deepseek_reasoning_formatter(model_config: dict[str, Any], api: str) -> bool:
    if api in {"deepseek-completions", "deepseek"}:
        return True
    model_id = str(model_config.get("model_id") or "").lower()
    return "deepseek" in model_id


def _openai_sdk_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _anthropic_sdk_base_url(base_url: str) -> str:
    # The UI/provider config uses `/v1`; Anthropic's SDK appends `/v1/messages`.
    normalized = base_url.rstrip("/")
    return normalized.removesuffix("/v1")
