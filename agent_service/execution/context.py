from __future__ import annotations

import re

from agent_service.engagement_layout import harness_project_root
from agent_service.execution.path_translator import PathTranslator
from agent_service.execution.runtime_config import WorkflowRuntimeConfig, parse_workflow_runtime

_CONTAINER_NAME_SAFE = re.compile(r"[^a-z0-9-]+")
_CONTAINER_PREFIX = "harness-exec"


def _sanitize_container_segment(value: str, *, max_len: int = 40) -> str:
    lowered = value.strip().lower()
    safe = _CONTAINER_NAME_SAFE.sub("-", lowered).strip("-")
    if not safe:
        safe = "x"
    return safe[:max_len]


def container_name_for(user_id: str, workflow_template_id: str) -> str:
    user_part = _sanitize_container_segment(user_id)
    template_part = _sanitize_container_segment(workflow_template_id)
    name = f"{_CONTAINER_PREFIX}-{user_part}-{template_part}"
    return name[:128]


def user_workflow_tree_host_path(user_id: str, workflow_template_id: str) -> str:
    root = harness_project_root()
    return str((root / "users" / user_id.strip() / "workflows" / workflow_template_id.strip()).resolve())


class RunExecutionContext:
    def __init__(
        self,
        *,
        runtime: WorkflowRuntimeConfig,
        user_id: str,
        workflow_template_id: str,
        engagement_id: str,
        session_id: str,
        container_name: str | None = None,
    ) -> None:
        self.runtime = runtime
        self.user_id = user_id.strip()
        self.workflow_template_id = workflow_template_id.strip()
        self.engagement_id = engagement_id.strip()
        self.session_id = session_id.strip()
        self.host_workflow_root = user_workflow_tree_host_path(self.user_id, self.workflow_template_id)
        self.path_translator = PathTranslator(self.host_workflow_root)
        self.container_name = container_name or container_name_for(self.user_id, self.workflow_template_id)

    @property
    def is_docker(self) -> bool:
        return self.runtime.is_docker

    @property
    def docker_image(self) -> str:
        return self.runtime.docker_image

    def display_path(self, host_path: str | None) -> str | None:
        if not host_path:
            return host_path
        if not self.is_docker:
            return host_path
        return self.path_translator.host_to_container(host_path)


def build_run_execution_context(
    *,
    workflow_runtime: dict | None,
    user_id: str,
    workflow_template_id: str,
    engagement_id: str,
    session_id: str,
) -> RunExecutionContext:
    runtime = parse_workflow_runtime(workflow_runtime)
    return RunExecutionContext(
        runtime=runtime,
        user_id=user_id,
        workflow_template_id=workflow_template_id,
        engagement_id=engagement_id,
        session_id=session_id,
    )


def runtime_from_workflow_dict(workflow: dict) -> WorkflowRuntimeConfig:
    return parse_workflow_runtime(workflow.get("runtime"))
