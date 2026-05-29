from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agent_service.execution.context import RunExecutionContext, user_workflow_tree_host_path
from agent_service.execution.path_translator import CONTAINER_WORKFLOW_ROOT
from agent_service.execution.runtime_config import DEFAULT_IDLE_TTL_SECONDS

logger = logging.getLogger(__name__)

HARNESS_EXEC_ROLE_LABEL = "harness.role=workflow-exec"


def _docker_bin() -> str:
    path = shutil.which("docker")
    if not path:
        raise RuntimeError(
            "Docker CLI not found. Install Docker Desktop / Docker Engine, or set workflow runtime to Host."
        )
    return path


def _run_docker(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [_docker_bin(), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _container_inspect(name: str) -> dict | None:
    result = _run_docker(["inspect", name])
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not payload:
        return None
    return payload[0] if isinstance(payload[0], dict) else None


def _image_exists(image: str) -> bool:
    result = _run_docker(["image", "inspect", image])
    return result.returncode == 0


def _parse_docker_timestamp(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _label_value(inspect: dict, key: str) -> str:
    config = inspect.get("Config") or {}
    labels = config.get("Labels") or {}
    if not isinstance(labels, dict):
        return ""
    return str(labels.get(key) or "").strip()


def _idle_ttl_from_inspect(inspect: dict) -> int:
    raw = _label_value(inspect, "harness.idle_ttl_seconds")
    try:
        ttl = int(raw) if raw else DEFAULT_IDLE_TTL_SECONDS
    except (TypeError, ValueError):
        ttl = DEFAULT_IDLE_TTL_SECONDS
    return max(60, ttl)


def _list_harness_exec_container_names() -> list[str]:
    result = _run_docker(["ps", "-a", "--filter", f"label={HARNESS_EXEC_ROLE_LABEL}", "--format", "{{.Names}}"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


@dataclass
class ContainerManager:
    """Ensure per-user workflow execution containers with a single workflow-tree bind mount."""

    _last_activity: dict[str, float] = field(default_factory=dict)
    _idle_ttl_by_container: dict[str, int] = field(default_factory=dict)

    def ensure_container(self, ctx: RunExecutionContext) -> str:
        if not ctx.is_docker:
            return ctx.container_name
        self.prune_idle_containers()
        host_mount = user_workflow_tree_host_path(ctx.user_id, ctx.workflow_template_id)
        Path(host_mount).mkdir(parents=True, exist_ok=True)
        self._idle_ttl_by_container[ctx.container_name] = ctx.runtime.idle_ttl_seconds
        inspect = _container_inspect(ctx.container_name)
        if inspect is None:
            self._create(ctx, host_mount)
        else:
            self._ensure_mount_compatible(inspect, host_mount, ctx.container_name)
            if not inspect.get("State", {}).get("Running"):
                started = _run_docker(["start", ctx.container_name])
                if started.returncode != 0:
                    detail = (started.stderr or started.stdout or "").strip()
                    raise RuntimeError(f"Failed to start container {ctx.container_name}: {detail}")
        self.touch_activity(ctx.container_name)
        return ctx.container_name

    def touch_activity(self, container_name: str) -> None:
        self._last_activity[container_name] = time.time()

    def prune_idle_containers(self) -> list[str]:
        """Stop workflow-exec containers that exceeded their idle TTL."""
        stopped: list[str] = []
        now = time.time()
        for name in _list_harness_exec_container_names():
            inspect = _container_inspect(name)
            if inspect is None or not inspect.get("State", {}).get("Running"):
                self._forget_container(name)
                continue
            ttl = self._idle_ttl_by_container.get(name) or _idle_ttl_from_inspect(inspect)
            last = self._last_activity.get(name)
            if last is None:
                started_raw = str((inspect.get("State") or {}).get("StartedAt") or "")
                last = _parse_docker_timestamp(started_raw) or now
            if now - last < ttl:
                continue
            result = _run_docker(["stop", "-t", "10", name])
            if result.returncode == 0:
                stopped.append(name)
                logger.info("Stopped idle workflow container %s after %ss without activity", name, ttl)
            self._forget_container(name)
        return stopped

    def _forget_container(self, name: str) -> None:
        self._last_activity.pop(name, None)
        self._idle_ttl_by_container.pop(name, None)

    def _create(self, ctx: RunExecutionContext, host_mount: str) -> None:
        if not _image_exists(ctx.docker_image):
            raise RuntimeError(
                f"Docker image {ctx.docker_image!r} not found. "
                "Build it with: bash scripts/build_harness_exec_image.sh"
            )
        ttl = ctx.runtime.idle_ttl_seconds
        result = _run_docker(
            [
                "run",
                "-d",
                "--name",
                ctx.container_name,
                "-w",
                CONTAINER_WORKFLOW_ROOT,
                "-v",
                f"{host_mount}:{CONTAINER_WORKFLOW_ROOT}:rw",
                "--label",
                "harness.role=workflow-exec",
                "--label",
                f"harness.user_id={ctx.user_id}",
                "--label",
                f"harness.workflow_template_id={ctx.workflow_template_id}",
                "--label",
                f"harness.idle_ttl_seconds={ttl}",
                ctx.docker_image,
                "sleep",
                "infinity",
            ]
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"Failed to create container {ctx.container_name}: {detail}")

    def _ensure_mount_compatible(self, inspect: dict, host_mount: str, container_name: str) -> None:
        mounts = inspect.get("Mounts") or []
        for mount in mounts:
            if mount.get("Destination") == CONTAINER_WORKFLOW_ROOT:
                if mount.get("Source") == host_mount:
                    return
                raise RuntimeError(
                    f"Container {container_name} has incompatible mount for {CONTAINER_WORKFLOW_ROOT}. "
                    f"Remove it with: docker rm -f {container_name}"
                )
        raise RuntimeError(
            f"Container {container_name} is missing workflow bind mount. "
            f"Remove it with: docker rm -f {container_name}"
        )


_shared_manager = ContainerManager()


def get_container_manager() -> ContainerManager:
    return _shared_manager
