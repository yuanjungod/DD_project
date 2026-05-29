from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

from agentscope.tool import execute_python_code, execute_shell_command, view_text_file


class HostExecutor:
    """Delegate to AgentScope built-in tool implementations on the host."""

    async def execute_shell(self, command: str, **kwargs: Any) -> Any:
        return await self._call_builtin(execute_shell_command, command=command, **kwargs)

    async def execute_python(self, code: str, **kwargs: Any) -> Any:
        return await self._call_builtin(execute_python_code, code=code, **kwargs)

    async def view_text_file(self, file_path: str, **kwargs: Any) -> Any:
        return await self._call_builtin(view_text_file, file_path=file_path, **kwargs)

    async def _call_builtin(self, fn: Callable[..., Any], **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(fn):
            return await fn(**kwargs)
        result = fn(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def run_shell_sync(self, command: str, **kwargs: Any) -> Any:
        return asyncio.run(self.execute_shell(command, **kwargs))

    def run_python_sync(self, code: str, **kwargs: Any) -> Any:
        return asyncio.run(self.execute_python(code, **kwargs))

    def run_view_text_sync(self, file_path: str, **kwargs: Any) -> Any:
        return asyncio.run(self.view_text_file(file_path, **kwargs))
