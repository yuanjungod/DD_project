"""Agent template files: user drafts under .dd_project/users/* and published under catalog/agents/."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.entities import new_id
from app.schemas.dto import AgentTemplateBase, AgentTemplateCreate, AgentTemplateRead, AgentTemplateUpdate
from app.services.agent_record_utils import normalize_agent_record
from app.services.catalog_layout import (
    assert_safe_workflow_template_id,
    global_agent_path,
    global_agents_dir,
    list_user_agent_template_paths,
    user_agent_template_path,
)
from app.services.catalog_yaml_utils import load_yaml, utc_from_mtime


def _load_yaml(path: Path) -> dict[str, Any]:
    return load_yaml(path)


def _utc_from_mtime(path: Path):
    return utc_from_mtime(path)


def _write_agent_file(path: Path, payload: dict[str, Any]) -> None:
    norm = normalize_agent_record(copy.deepcopy(payload))
    try:
        AgentTemplateBase.model_validate({k: v for k, v in norm.items() if k != "id"})
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc.errors()[0]["msg"])) from exc
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


def _list_agent_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        doc = _load_yaml(path)
        if not doc:
            continue
        rows.append(normalize_agent_record(copy.deepcopy(doc)))
    return rows


def _agent_read(path: Path, row: dict[str, Any]) -> AgentTemplateRead:
    mt = _utc_from_mtime(path)
    nas = mt.replace(tzinfo=None)
    base = AgentTemplateBase.model_validate({k: v for k, v in row.items() if k != "id"})
    return AgentTemplateRead(
        id=row["id"],
        created_at=nas,
        updated_at=nas,
        **base.model_dump(),
    )


def list_global_agent_rows() -> list[dict[str, Any]]:
    paths = [path for path in sorted(global_agents_dir().glob("*.yaml")) if not path.name.startswith("_")]
    return _list_agent_rows(paths)


def list_user_agent_rows(user_id: str) -> list[dict[str, Any]]:
    return _list_agent_rows(list_user_agent_template_paths(user_id))


def global_agent_by_id(*, user_id: str | None = None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {row["id"]: row for row in list_global_agent_rows()}
    if user_id:
        for row in list_user_agent_rows(user_id):
            rows[row["id"]] = row
    return rows


def load_agent(agent_id: str, *, user_id: str) -> tuple[dict[str, Any], Path]:
    assert_safe_workflow_template_id(agent_id)
    draft_path = user_agent_template_path(user_id, agent_id)
    path = draft_path if draft_path.is_file() else global_agent_path(agent_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Agent template not found")
    return normalize_agent_record(copy.deepcopy(_load_yaml(path))), path


def save_user_agent(payload: dict[str, Any], *, user_id: str) -> dict[str, Any]:
    norm = normalize_agent_record(copy.deepcopy(payload))
    _write_agent_file(user_agent_template_path(user_id, norm["id"]), norm)
    return norm


def list_agent_reads(*, only_enabled_non_admin: bool, user_id: str | None = None) -> list[AgentTemplateRead]:
    path_by_id: dict[str, Path] = {}
    for path in sorted(global_agents_dir().glob("*.yaml"), key=lambda item: item.name.lower()):
        if path.name.startswith("_"):
            continue
        path_by_id[path.stem] = path
    if user_id:
        for path in list_user_agent_template_paths(user_id):
            path_by_id[path.stem] = path

    reads: list[AgentTemplateRead] = []
    for path in sorted(path_by_id.values(), key=lambda item: item.name.lower()):
        row = normalize_agent_record(copy.deepcopy(_load_yaml(path)))
        if only_enabled_non_admin and not row.get("enabled", True):
            continue
        reads.append(_agent_read(path, row))
    reads.sort(key=lambda item: item.name.lower())
    return reads


def create_agent(payload: AgentTemplateCreate, *, user_id: str) -> AgentTemplateRead:
    data = payload.model_dump()
    if not data.get("id"):
        data["id"] = new_id("agent_tpl")
    norm_id = data["id"]
    assert_safe_workflow_template_id(norm_id)
    pool = global_agent_by_id(user_id=user_id)
    if norm_id in pool:
        raise HTTPException(status_code=409, detail=f"Agent id already exists: {norm_id}")
    names = {row["name"] for row in pool.values()}
    if data.get("name") in names:
        raise HTTPException(status_code=409, detail=f"Agent name already exists: {data.get('name')}")
    norm = save_user_agent(data, user_id=user_id)
    path = user_agent_template_path(user_id, norm["id"])
    return _agent_read(path, norm)


def update_agent(agent_id: str, payload: AgentTemplateUpdate, *, user_id: str) -> AgentTemplateRead:
    current, _ = load_agent(agent_id, user_id=user_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        current[key] = value
    current["id"] = agent_id
    norm = save_user_agent(current, user_id=user_id)
    return _agent_read(user_agent_template_path(user_id, agent_id), norm)


def publish_agent(agent_id: str, *, user_id: str) -> AgentTemplateRead:
    row, _ = load_agent(agent_id, user_id=user_id)
    target = global_agent_path(agent_id)
    _write_agent_file(target, row)
    return _agent_read(target, row)


def copy_global_agents_to_workflow_template(workflow_template_id: str, agent_ids: list[str], *, user_id: str) -> None:
    from app.services.catalog_layout import workflow_template_agents_write_dir

    target_dir = workflow_template_agents_write_dir(workflow_template_id, user_id=user_id)
    pool = global_agent_by_id(user_id=user_id)
    missing = [aid for aid in agent_ids if aid not in pool]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown agent ids: {missing}")
    for agent_id in agent_ids:
        _write_agent_file(target_dir / f"{agent_id}.yaml", pool[agent_id])
