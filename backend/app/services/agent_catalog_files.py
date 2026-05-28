"""Global agent template library — one YAML file per agent under catalog/agents/."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException

from app.models.entities import new_id
from app.schemas.dto import AgentTemplateBase, AgentTemplateCreate, AgentTemplateRead, AgentTemplateUpdate
from app.services.agent_record_utils import normalize_agent_record
from app.services.catalog_layout import assert_safe_workflow_template_id, global_agent_path, global_agents_dir


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded if isinstance(loaded, dict) else {}


def _utc_from_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _write_agent_file(path: Path, payload: dict[str, Any]) -> None:
    norm = normalize_agent_record(copy.deepcopy(payload))
    AgentTemplateBase.model_validate({k: v for k, v in norm.items() if k != "id"})
    text = yaml.safe_dump(
        norm,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    )
    header = "# Agent template — global library entry. Scenario folders may copy this into their agents/ directory.\n\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + text, encoding="utf-8")


def list_global_agent_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(global_agents_dir().glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        doc = _load_yaml(path)
        if not doc:
            continue
        rows.append(normalize_agent_record(copy.deepcopy(doc)))
    return rows


def global_agent_by_id() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in list_global_agent_rows()}


def load_global_agent(agent_id: str) -> dict[str, Any]:
    assert_safe_workflow_template_id(agent_id)
    path = global_agent_path(agent_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Agent template not found")
    return normalize_agent_record(copy.deepcopy(_load_yaml(path)))


def save_global_agent(payload: dict[str, Any]) -> dict[str, Any]:
    norm = normalize_agent_record(copy.deepcopy(payload))
    _write_agent_file(global_agent_path(norm["id"]), norm)
    return norm


def list_global_agent_reads(*, only_enabled_non_admin: bool) -> list[AgentTemplateRead]:
    reads: list[AgentTemplateRead] = []
    for path in sorted(global_agents_dir().glob("*.yaml"), key=lambda item: item.name.lower()):
        if path.name.startswith("_"):
            continue
        row = normalize_agent_record(copy.deepcopy(_load_yaml(path)))
        if only_enabled_non_admin and not row.get("enabled", True):
            continue
        mt = _utc_from_mtime(path)
        nas = mt.replace(tzinfo=None)
        base = AgentTemplateBase.model_validate({k: v for k, v in row.items() if k != "id"})
        reads.append(
            AgentTemplateRead(
                id=row["id"],
                created_at=nas,
                updated_at=nas,
                **base.model_dump(),
            )
        )
    reads.sort(key=lambda item: item.name.lower())
    return reads


def create_global_agent(payload: AgentTemplateCreate) -> AgentTemplateRead:
    data = payload.model_dump()
    if not data.get("id"):
        data["id"] = new_id("agent_tpl")
    norm_id = data["id"]
    assert_safe_workflow_template_id(norm_id)
    pool = global_agent_by_id()
    if norm_id in pool:
        raise HTTPException(status_code=409, detail=f"Agent id already exists: {norm_id}")
    names = {row["name"] for row in pool.values()}
    if data.get("name") in names:
        raise HTTPException(status_code=409, detail=f"Agent name already exists: {data.get('name')}")
    norm = save_global_agent(data)
    mt = _utc_from_mtime(global_agent_path(norm["id"]))
    nas = mt.replace(tzinfo=None)
    base_fields = AgentTemplateBase.model_validate({k: v for k, v in norm.items() if k != "id"})
    return AgentTemplateRead(
        id=norm["id"],
        created_at=nas,
        updated_at=nas,
        **base_fields.model_dump(),
    )


def update_global_agent(agent_id: str, payload: AgentTemplateUpdate) -> AgentTemplateRead:
    current = load_global_agent(agent_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        current[key] = value
    current["id"] = agent_id
    norm = save_global_agent(current)
    mt = _utc_from_mtime(global_agent_path(agent_id))
    nas = mt.replace(tzinfo=None)
    base_fields = AgentTemplateBase.model_validate({k: v for k, v in norm.items() if k != "id"})
    return AgentTemplateRead(
        id=agent_id,
        created_at=nas,
        updated_at=nas,
        **base_fields.model_dump(),
    )


def copy_global_agents_to_workflow_template(workflow_template_id: str, agent_ids: list[str], *, user_id: str) -> None:
    from app.services.catalog_layout import workflow_template_agents_write_dir

    target_dir = workflow_template_agents_write_dir(workflow_template_id, user_id=user_id)
    pool = global_agent_by_id()
    missing = [aid for aid in agent_ids if aid not in pool]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown agent ids: {missing}")
    for agent_id in agent_ids:
        _write_agent_file(target_dir / f"{agent_id}.yaml", pool[agent_id])
