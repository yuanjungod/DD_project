from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CommandExecutionMode = Literal["host", "docker"]

DEFAULT_EXEC_IMAGE = "harness-exec:0.1.0"
DEFAULT_IDLE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class WorkflowRuntimeConfig:
    command_execution: CommandExecutionMode = "host"
    docker_image: str = DEFAULT_EXEC_IMAGE
    idle_ttl_seconds: int = DEFAULT_IDLE_TTL_SECONDS

    @property
    def is_docker(self) -> bool:
        return self.command_execution == "docker"


def parse_workflow_runtime(raw: Any) -> WorkflowRuntimeConfig:
    if not isinstance(raw, dict):
        return WorkflowRuntimeConfig()
    mode = str(raw.get("command_execution") or "host").strip().lower()
    if mode not in ("host", "docker"):
        mode = "host"
    docker_block = raw.get("docker") if isinstance(raw.get("docker"), dict) else {}
    image = str(docker_block.get("image") or DEFAULT_EXEC_IMAGE).strip() or DEFAULT_EXEC_IMAGE
    try:
        idle_ttl = int(docker_block.get("idle_ttl_seconds") or DEFAULT_IDLE_TTL_SECONDS)
    except (TypeError, ValueError):
        idle_ttl = DEFAULT_IDLE_TTL_SECONDS
    idle_ttl = max(60, idle_ttl)
    return WorkflowRuntimeConfig(
        command_execution=mode,  # type: ignore[arg-type]
        docker_image=image,
        idle_ttl_seconds=idle_ttl,
    )


def runtime_config_to_dict(config: WorkflowRuntimeConfig) -> dict[str, Any]:
    return {
        "command_execution": config.command_execution,
        "docker": {
            "image": config.docker_image,
            "idle_ttl_seconds": config.idle_ttl_seconds,
            "workspace_mount": "workflow_tree",
        },
    }
