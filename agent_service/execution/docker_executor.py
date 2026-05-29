from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from agent_service.execution.context import RunExecutionContext
from agent_service.execution.container_manager import ContainerManager
from agent_service.execution.path_translator import CONTAINER_WORKFLOW_ROOT

DEFAULT_TIMEOUT_SECONDS = 300
_MAX_OUTPUT_CHARS = 100_000


class DockerExecutor:
    def __init__(
        self,
        ctx: RunExecutionContext,
        *,
        container_manager: ContainerManager | None = None,
    ) -> None:
        self.ctx = ctx
        self.container_manager = container_manager or ContainerManager()
        self.container_manager.ensure_container(ctx)

    def execute_shell(self, command: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
        cwd = self._default_cwd_container()
        return self._exec(
            ["bash", "-lc", command],
            workdir=cwd,
            timeout=timeout,
        )

    def execute_python(self, code: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
        tmp_dir = (
            Path(self.ctx.host_workflow_root)
            / self.ctx.engagement_id
            / "sessions"
            / self.ctx.session_id
            / "runs"
            / ".tmp"
        )
        tmp_dir.mkdir(parents=True, exist_ok=True)
        script_name = f"exec_{uuid.uuid4().hex[:12]}.py"
        host_script = tmp_dir / script_name
        host_script.write_text(code, encoding="utf-8")
        container_script = self.ctx.path_translator.host_to_container(str(host_script))
        return self._exec(
            ["python", container_script],
            workdir=str(Path(container_script).parent),
            timeout=timeout,
        )

    def view_text_file(self, file_path: str, *, max_chars: int = _MAX_OUTPUT_CHARS) -> dict[str, Any]:
        container_path = self._resolve_readable_path(file_path)
        result = self._exec(["cat", container_path], workdir=CONTAINER_WORKFLOW_ROOT, timeout=60)
        if result.get("returncode", 1) != 0:
            return result
        text = str(result.get("stdout") or "")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n…(truncated)"
        result["stdout"] = text
        return result

    def _default_cwd_container(self) -> str:
        host_cwd = (
            Path(self.ctx.host_workflow_root)
            / self.ctx.engagement_id
            / "sessions"
            / self.ctx.session_id
            / "runs"
        )
        host_cwd.mkdir(parents=True, exist_ok=True)
        return self.ctx.path_translator.host_to_container(str(host_cwd.resolve()))

    def _resolve_readable_path(self, file_path: str) -> str:
        raw = file_path.strip()
        translator = self.ctx.path_translator
        if raw.startswith(CONTAINER_WORKFLOW_ROOT + "/") or raw == CONTAINER_WORKFLOW_ROOT:
            return raw
        if translator.is_host_under_workspace(raw):
            return translator.host_to_container(raw)
        raise ValueError(
            f"File path must be under workflow workspace ({CONTAINER_WORKFLOW_ROOT} or {translator.host_root}): {file_path}"
        )

    def _exec(self, cmd: list[str], *, workdir: str, timeout: int) -> dict[str, Any]:
        self.container_manager.touch_activity(self.ctx.container_name)
        full_cmd = [
            "docker",
            "exec",
            "-w",
            workdir,
            self.ctx.container_name,
            *cmd,
        ]
        try:
            completed = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "returncode": 124,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "command": " ".join(full_cmd),
            }
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if len(stdout) > _MAX_OUTPUT_CHARS:
            stdout = stdout[:_MAX_OUTPUT_CHARS] + "\n…(truncated)"
        if len(stderr) > _MAX_OUTPUT_CHARS:
            stderr = stderr[:_MAX_OUTPUT_CHARS] + "\n…(truncated)"
        return {
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "command": " ".join(full_cmd),
        }

    def as_tool_response_text(self, result: dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False)
