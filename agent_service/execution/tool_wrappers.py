from __future__ import annotations

import json
from typing import Any, Callable

from agentscope.tool import ToolResponse

from agent_service.execution.router import ExecutionRouter


def _tool_response_from_result(result: Any) -> ToolResponse:
    if isinstance(result, ToolResponse):
        return result
    if isinstance(result, dict):
        text = json.dumps(result, ensure_ascii=False)
    else:
        text = str(result)
    return ToolResponse(
        content=[{"type": "text", "text": text}],
        metadata={"execution_backend": "docker"},
    )


def build_docker_builtin_tools(router: ExecutionRouter) -> list[tuple[str, Callable[..., ToolResponse], str]]:
    """Return (name, callable, description) tuples for docker-mode builtins."""

    def execute_shell_command(command: str = "", **kwargs: Any) -> ToolResponse:
        """Execute a shell command inside the workflow Docker container."""
        _ = kwargs
        return _tool_response_from_result(router.execute_shell(command))

    def execute_python_code(code: str = "", **kwargs: Any) -> ToolResponse:
        """Execute Python code inside the workflow Docker container."""
        _ = kwargs
        return _tool_response_from_result(router.execute_python(code))

    def view_text_file(file_path: str = "", **kwargs: Any) -> ToolResponse:
        """Read a text file from the workflow Docker container mount."""
        _ = kwargs
        return _tool_response_from_result(router.view_text_file(file_path))

    execute_shell_command.__name__ = "execute_shell_command"
    execute_python_code.__name__ = "execute_python_code"
    view_text_file.__name__ = "view_text_file"

    return [
        (
            "execute_shell_command",
            execute_shell_command,
            "Execute a shell command in the isolated workflow container.",
        ),
        (
            "execute_python_code",
            execute_python_code,
            "Execute Python code in the isolated workflow container.",
        ),
        (
            "view_text_file",
            view_text_file,
            "Read a text file under the workflow container mount.",
        ),
    ]
