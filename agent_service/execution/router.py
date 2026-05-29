from __future__ import annotations

from typing import Any

from agent_service.execution.context import RunExecutionContext
from agent_service.execution.docker_executor import DockerExecutor
from agent_service.execution.host_executor import HostExecutor


class ExecutionRouter:
    def __init__(self, ctx: RunExecutionContext | None) -> None:
        self.ctx = ctx
        self._host = HostExecutor()
        self._docker: DockerExecutor | None = None
        if ctx is not None and ctx.is_docker:
            self._docker = DockerExecutor(ctx)

    @property
    def is_docker(self) -> bool:
        return self.ctx is not None and self.ctx.is_docker

    def execute_shell(self, command: str, **kwargs: Any) -> Any:
        if self._docker is not None:
            return self._docker.execute_shell(command, **kwargs)
        return self._host.run_shell_sync(command, **kwargs)

    def execute_python(self, code: str, **kwargs: Any) -> Any:
        if self._docker is not None:
            return self._docker.execute_python(code, **kwargs)
        return self._host.run_python_sync(code, **kwargs)

    def view_text_file(self, file_path: str, **kwargs: Any) -> Any:
        if self._docker is not None:
            return self._docker.view_text_file(file_path, **kwargs)
        return self._host.run_view_text_sync(file_path, **kwargs)
