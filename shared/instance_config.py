"""Normalize engagement instance configuration (generic InstanceConfig + legacy company_config)."""

from __future__ import annotations

import copy
from typing import Any

INSTANCE_CONFIG_FIELD = "instance_config"
LEGACY_COMPANY_CONFIG_FIELD = "company_config"
EXTENSIONS_FIELD = "extensions"
DUE_DILIGENCE_EXTENSION = "due_diligence"
SUBJECT_EXTENSION = "subject"
WORKFLOW_TASK_EXTENSION = "workflow_task"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def resolve_target_company(stored: dict[str, Any]) -> dict[str, Any] | None:
    root = _as_dict(stored.get("target_company"))
    if root.get("name"):
        return {"name": str(root["name"]).strip(), "aliases": list(root.get("aliases") or [])}

    extensions = _as_dict(stored.get(EXTENSIONS_FIELD))
    dd = _as_dict(extensions.get(DUE_DILIGENCE_EXTENSION))
    nested = _as_dict(dd.get("target_company"))
    if nested.get("name"):
        return {"name": str(nested["name"]).strip(), "aliases": list(nested.get("aliases") or [])}

    subject = _as_dict(extensions.get(SUBJECT_EXTENSION))
    if subject.get("name"):
        return {"name": str(subject["name"]).strip(), "aliases": list(subject.get("aliases") or [])}
    return None


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
    target = resolve_target_company(stored)
    if target and target.get("name"):
        return str(target["name"]).strip()
    return ""


def resolve_subject_name(stored: dict[str, Any]) -> str:
    task = resolve_workflow_task(stored)
    if task:
        first_line = task.splitlines()[0].strip()
        return first_line[:120] if first_line else task[:120]
    target = resolve_target_company(stored)
    if target and target.get("name"):
        return str(target["name"]).strip()
    return ""


def resolve_workflow_template_id(stored: dict[str, Any]) -> str:
    return str(stored.get("workflow_template_id") or "").strip()


def is_due_diligence_template_id(template_id: str) -> bool:
    return "due_diligence" in str(template_id or "").strip()


def instance_config_view(stored: dict[str, Any]) -> dict[str, Any]:
    """Canonical API view; enriches legacy root target_company into extensions when missing."""

    if not stored:
        return {}
    view = copy.deepcopy(stored)
    extensions = _as_dict(view.get(EXTENSIONS_FIELD))
    task = resolve_workflow_task(view)
    if task:
        extensions.setdefault(WORKFLOW_TASK_EXTENSION, {"description": task})
    target = resolve_target_company(view)
    if target:
        dd = _as_dict(extensions.get(DUE_DILIGENCE_EXTENSION))
        dd.setdefault("target_company", target)
        extensions[DUE_DILIGENCE_EXTENSION] = dd
        if is_due_diligence_template_id(resolve_workflow_template_id(view)):
            view.setdefault("target_company", target)
        elif SUBJECT_EXTENSION not in extensions:
            extensions[SUBJECT_EXTENSION] = {
                "name": target["name"],
                "aliases": target.get("aliases") or [],
                "kind": "generic",
            }
    if extensions:
        view[EXTENSIONS_FIELD] = extensions
    view.setdefault("resources", _as_dict(view.get("resources")))
    return view


def materialize_stored_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Persistable JSON for engagements.company_config (legacy-safe)."""

    stored = copy.deepcopy(payload)
    extensions = _as_dict(stored.get(EXTENSIONS_FIELD))
    task = resolve_workflow_task(stored)
    if task:
        extensions[WORKFLOW_TASK_EXTENSION] = {"description": task}
    stored[EXTENSIONS_FIELD] = extensions
    target = resolve_target_company(stored)
    template_id = resolve_workflow_template_id(stored)
    if target and is_due_diligence_template_id(template_id):
        stored["target_company"] = target
    elif target:
        extensions = _as_dict(stored.get(EXTENSIONS_FIELD))
        subject = _as_dict(extensions.get(SUBJECT_EXTENSION))
        if not subject.get("name"):
            extensions[SUBJECT_EXTENSION] = {
                "name": target["name"],
                "aliases": target.get("aliases") or [],
                "kind": subject.get("kind") or "generic",
            }
        stored[EXTENSIONS_FIELD] = extensions
        stored.pop("target_company", None)
    stored.setdefault("resources", _as_dict(stored.get("resources")))
    return stored


def to_agent_company_config(stored: dict[str, Any]) -> dict[str, Any]:
    """Legacy agent wire shape (company_config with target_company)."""

    cfg = copy.deepcopy(stored) if stored else {}
    task = resolve_workflow_task(cfg)
    target = resolve_target_company(cfg)
    if not target:
        label = (task.splitlines()[0].strip() if task else "") or "Workflow Task"
        target = {"name": label[:120], "aliases": []}
    cfg["target_company"] = target
    cfg["workflow_task"] = task
    cfg.setdefault("resources", _as_dict(cfg.get("resources")))
    return cfg


def coalesce_config_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Read instance_config or legacy company_config from an API body."""

    if INSTANCE_CONFIG_FIELD in data and isinstance(data[INSTANCE_CONFIG_FIELD], dict):
        return copy.deepcopy(data[INSTANCE_CONFIG_FIELD])
    if LEGACY_COMPANY_CONFIG_FIELD in data and isinstance(data[LEGACY_COMPANY_CONFIG_FIELD], dict):
        return copy.deepcopy(data[LEGACY_COMPANY_CONFIG_FIELD])
    return copy.deepcopy(data)
