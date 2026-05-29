"""Normalize engagement instance configuration for storage and agent runs."""

from __future__ import annotations

import copy
from typing import Any

INSTANCE_CONFIG_FIELD = "instance_config"
EXTENSIONS_FIELD = "extensions"
SUBJECT_EXTENSION = "subject"
WORKFLOW_TASK_EXTENSION = "workflow_task"
TASK_NAME_EXTENSION = "task_name"

# Legacy keys accepted on read-only migration paths.
_LEGACY_TARGET_COMPANY_FIELD = "target_company"
_LEGACY_DUE_DILIGENCE_EXTENSION = "due_diligence"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def resolve_subject(stored: dict[str, Any]) -> dict[str, Any] | None:
    extensions = _as_dict(stored.get(EXTENSIONS_FIELD))
    subject = _as_dict(extensions.get(SUBJECT_EXTENSION))
    if subject.get("name"):
        return {
            "name": str(subject["name"]).strip(),
            "aliases": list(subject.get("aliases") or []),
            "kind": str(subject.get("kind") or "generic"),
        }

    root = _as_dict(stored.get(_LEGACY_TARGET_COMPANY_FIELD))
    if root.get("name"):
        return {
            "name": str(root["name"]).strip(),
            "aliases": list(root.get("aliases") or []),
            "kind": "generic",
        }

    legacy_dd = _as_dict(extensions.get(_LEGACY_DUE_DILIGENCE_EXTENSION))
    nested = _as_dict(legacy_dd.get(_LEGACY_TARGET_COMPANY_FIELD))
    if nested.get("name"):
        return {
            "name": str(nested["name"]).strip(),
            "aliases": list(nested.get("aliases") or []),
            "kind": "generic",
        }
    return None


def resolve_task_name(stored: dict[str, Any]) -> str:
    direct = str(stored.get("task_name") or "").strip()
    if direct:
        return direct[:120]
    extensions = _as_dict(stored.get(EXTENSIONS_FIELD))
    name = str(extensions.get(TASK_NAME_EXTENSION) or "").strip()
    return name[:120] if name else ""


def resolve_workflow_task(stored: dict[str, Any]) -> str:
    direct = str(stored.get("workflow_task") or "").strip()
    if direct:
        return direct
    extensions = _as_dict(stored.get(EXTENSIONS_FIELD))
    task_block = _as_dict(extensions.get(WORKFLOW_TASK_EXTENSION))
    for key in ("description", "task", "goal"):
        text = str(task_block.get(key) or "").strip()
        if text:
            return text
    subject = resolve_subject(stored)
    if subject and subject.get("name"):
        return str(subject["name"]).strip()
    return ""


def resolve_subject_name(stored: dict[str, Any]) -> str:
    task_name = resolve_task_name(stored)
    if task_name:
        return task_name
    task = resolve_workflow_task(stored)
    if task:
        first_line = task.splitlines()[0].strip()
        return first_line[:120] if first_line else task[:120]
    subject = resolve_subject(stored)
    if subject and subject.get("name"):
        return str(subject["name"]).strip()
    return ""


def resolve_workflow_template_id(stored: dict[str, Any]) -> str:
    return str(stored.get("workflow_template_id") or "").strip()


def instance_config_view(stored: dict[str, Any]) -> dict[str, Any]:
    """Canonical API view without legacy due-diligence fields."""

    if not stored:
        return {}
    view = copy.deepcopy(stored)
    view.pop(_LEGACY_TARGET_COMPANY_FIELD, None)
    view.pop("workflow_task", None)
    extensions = _as_dict(view.get(EXTENSIONS_FIELD))
    extensions.pop(_LEGACY_DUE_DILIGENCE_EXTENSION, None)
    task_name = resolve_task_name(stored)
    if task_name:
        extensions[TASK_NAME_EXTENSION] = task_name
    task = resolve_workflow_task(stored)
    if task:
        extensions[WORKFLOW_TASK_EXTENSION] = {"description": task}
    subject = resolve_subject(stored)
    if subject:
        extensions[SUBJECT_EXTENSION] = subject
    if extensions:
        view[EXTENSIONS_FIELD] = extensions
    else:
        view.pop(EXTENSIONS_FIELD, None)
    view.setdefault("resources", _as_dict(view.get("resources")))
    return view


def materialize_stored_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Persistable JSON for engagements.instance_config."""

    stored = copy.deepcopy(payload)
    stored.pop(_LEGACY_TARGET_COMPANY_FIELD, None)
    stored.pop("workflow_task", None)
    extensions = _as_dict(stored.get(EXTENSIONS_FIELD))
    extensions.pop(_LEGACY_DUE_DILIGENCE_EXTENSION, None)
    task_name = resolve_task_name(payload)
    if task_name:
        extensions[TASK_NAME_EXTENSION] = task_name
    task = resolve_workflow_task(payload)
    if task:
        extensions[WORKFLOW_TASK_EXTENSION] = {"description": task}
    subject = resolve_subject(payload)
    if not subject:
        label = task_name
        if not label and task:
            first_line = task.splitlines()[0].strip()
            label = (first_line or task)[:120]
        if label:
            subject = {"name": label, "aliases": [], "kind": "generic"}
    if subject:
        extensions[SUBJECT_EXTENSION] = subject
    if extensions:
        stored[EXTENSIONS_FIELD] = extensions
    else:
        stored.pop(EXTENSIONS_FIELD, None)
    stored.setdefault("resources", _as_dict(stored.get("resources")))
    return stored


def require_workflow_task(stored: dict[str, Any]) -> None:
    if resolve_workflow_task(stored):
        return
    raise ValueError("extensions.workflow_task.description is required")


def require_task_name(stored: dict[str, Any]) -> None:
    if resolve_task_name(stored):
        return
    raise ValueError("extensions.task_name is required")


def to_agent_run_config(stored: dict[str, Any]) -> dict[str, Any]:
    """Normalized dict for agent_service RunInstanceConfig."""

    cfg = copy.deepcopy(stored) if stored else {}
    task = resolve_workflow_task(cfg)
    subject = resolve_subject(cfg)
    if not subject:
        label = (task.splitlines()[0].strip() if task else "") or "Workflow Task"
        subject = {"name": label[:120], "aliases": [], "kind": "generic"}
    return {
        "workflow_template_id": resolve_workflow_template_id(cfg),
        "workflow_template_version": cfg.get("workflow_template_version"),
        "workflow_task": task,
        "subject": subject,
        "resources": _as_dict(cfg.get("resources")),
    }


def migrate_legacy_agent_wire_config(wire: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy agent payloads that used company_config/target_company."""

    if not wire:
        return {}
    merged = copy.deepcopy(wire)
    if "subject" not in merged and merged.get(_LEGACY_TARGET_COMPANY_FIELD):
        merged["subject"] = merged.pop(_LEGACY_TARGET_COMPANY_FIELD)
    return to_agent_run_config(
        {
            "workflow_template_id": merged.get("workflow_template_id", ""),
            "workflow_template_version": merged.get("workflow_template_version"),
            "workflow_task": merged.get("workflow_task", ""),
            "resources": merged.get("resources", {}),
            "extensions": {
                SUBJECT_EXTENSION: merged.get("subject") or {},
                WORKFLOW_TASK_EXTENSION: {"description": merged.get("workflow_task", "")},
            },
        }
    )
