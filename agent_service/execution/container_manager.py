from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from agent_service.execution.context import RunExecutionContext, user_workflow_tree_host_path
from agent_service.execution.path_translator import CONTAINER_WORKFLOW_ROOT

logger = logging.getLogger(__name__)

try:
    import docker
    from docker.errors import DockerException, ImageNotFound, NotFound
except ImportError:  # pragma: no cover - tested via mocks
    docker = None  # type: ignore[assignment]

    class DockerException(Exception):
        pass

    class ImageNotFound(Exception):
        pass

    class NotFound(Exception):
        pass


@dataclass
class ContainerManager:
    """Ensure per-user workflow execution containers with a single workflow-tree bind mount."""

    _last_activity: dict[str, float] = field(default_factory=dict)

    def ensure_container(self, ctx: RunExecutionContext) -> str:
        if not ctx.is_docker:
            return ctx.container_name
        if docker is None:
            raise RuntimeError(
                "Docker execution requires the 'docker' Python package. Install agent_service/requirements.txt."
            )
        client = docker.from_env()
        host_mount = user_workflow_tree_host_path(ctx.user_id, ctx.workflow_template_id)
        container = self._get_running(client, ctx.container_name)
        if container is None:
            container = self._create(client, ctx, host_mount)
        else:
            self._ensure_mount_compatible(container, host_mount)
            if container.status != "running":
                container.start()
        self._last_activity[ctx.container_name] = time.time()
        return ctx.container_name

    def touch_activity(self, container_name: str) -> None:
        self._last_activity[container_name] = time.time()

    def stop_idle_containers(self, *, idle_ttl_seconds: int) -> list[str]:
        if docker is None:
            return []
        client = docker.from_env()
        stopped: list[str] = []
        now = time.time()
        for name, last in list(self._last_activity.items()):
            if now - last < idle_ttl_seconds:
                continue
            try:
                container = client.containers.get(name)
            except NotFound:
                self._last_activity.pop(name, None)
                continue
            if container.status == "running":
                container.stop(timeout=10)
                stopped.append(name)
            self._last_activity.pop(name, None)
        return stopped

    def _get_running(self, client: Any, name: str) -> Any | None:
        try:
            return client.containers.get(name)
        except NotFound:
            return None

    def _create(self, client: Any, ctx: RunExecutionContext, host_mount: str) -> Any:
        from pathlib import Path

        Path(host_mount).mkdir(parents=True, exist_ok=True)
        try:
            client.images.get(ctx.docker_image)
        except ImageNotFound as exc:
            raise RuntimeError(
                f"Docker image {ctx.docker_image!r} not found. "
                f"Build it with: bash scripts/build_harness_exec_image.sh"
            ) from exc
        return client.containers.run(
            ctx.docker_image,
            command=["sleep", "infinity"],
            name=ctx.container_name,
            detach=True,
            working_dir=CONTAINER_WORKFLOW_ROOT,
            volumes={host_mount: {"bind": CONTAINER_WORKFLOW_ROOT, "mode": "rw"}},
            labels={
                "harness.role": "workflow-exec",
                "harness.user_id": ctx.user_id,
                "harness.workflow_template_id": ctx.workflow_template_id,
            },
        )

    def _ensure_mount_compatible(self, container: Any, host_mount: str) -> None:
        mounts = container.attrs.get("Mounts") or []
        for mount in mounts:
            if mount.get("Destination") == CONTAINER_WORKFLOW_ROOT:
                if mount.get("Source") == host_mount:
                    return
                raise RuntimeError(
                    f"Container {container.name} has incompatible mount for {CONTAINER_WORKFLOW_ROOT}. "
                    "Remove the container and retry."
                )
        raise RuntimeError(f"Container {container.name} is missing workflow bind mount.")
