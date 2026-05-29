from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException

from app.models.entities import new_id
from app.schemas.dto import (
    WorkflowTemplateCreate,
    WorkflowTemplateRead,
    WorkflowTemplateUpdate,
)
from app.services.agent_catalog_files import copy_global_agents_to_workflow_template, global_agent_by_id
from app.services.agent_record_utils import normalize_agent_record
from app.services.catalog_layout import (
    assert_safe_workflow_template_id,
    builtin_workflow_templates_root,
    data_workflow_templates_root,
    is_protected_workflow_template,
    list_workflow_template_config_dirs,
    protected_workflow_template_ids,
    workflow_template_agents_dir,
    workflow_template_agents_write_dir,
    workflow_template_config_root,
    workflow_template_config_write_root,
    workflow_template_yaml_path,
)
from app.services.catalog_yaml_utils import load_yaml, utc_from_mtime
from app.services.workflow_graph import (
    WorkflowGraphError,
    infer_entry_and_report_nodes,
    resolve_graph_agent_order,
    validate_workflow_graph,
)


def workflow_templates_dir() -> Path:
    """Legacy helper — returns builtin workflow templates root for compatibility."""
    from app.services.catalog_layout import builtin_workflow_templates_root

    return builtin_workflow_templates_root()


def _load_yaml(path: Path) -> dict[str, Any]:
    return load_yaml(path)


def _utc_from_mtime(path: Path):
    return utc_from_mtime(path)


def ensure_workflow_templates_dir() -> None:
    from app.services.catalog_layout import builtin_workflow_templates_root, global_agents_dir

    builtin_workflow_templates_root()
    global_agents_dir()


def _assert_safe_workflow_id(workflow_id: str) -> None:
    try:
        assert_safe_workflow_template_id(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def workflow_bundle_path(workflow_id: str, user_id: str | None = None) -> Path:
    _assert_safe_workflow_id(workflow_id)
    return workflow_template_yaml_path(workflow_id, user_id=user_id)


def _normalize_bundle(doc: dict[str, Any]) -> dict[str, Any]:
    wf = doc.get("workflow")
    if not isinstance(wf, dict):
        raise HTTPException(status_code=400, detail="Workflow template missing workflow section")
    wf.setdefault("description", "")
    discriminator = str(wf.get("workflow_template") or "").strip()
    if not discriminator:
        raise HTTPException(status_code=400, detail="Workflow missing workflow_template discriminator")
    wf["workflow_template"] = discriminator
    wf.setdefault("status", "draft")
    wf.setdefault("version", 1)
    if "graph" not in wf or not wf["graph"]:
        raise HTTPException(status_code=400, detail="Workflow missing graph")
    if "id" not in wf or not wf["id"]:
        raise HTTPException(status_code=400, detail="Workflow missing id")
    if "name" not in wf or not wf["name"]:
        raise HTTPException(status_code=400, detail="Workflow missing name")
    doc["agents"] = []
    return doc


def _write_workflow_template_yaml(workflow_template_id: str, bundle: dict[str, Any], *, user_id: str) -> Path:
    root = workflow_template_config_write_root(workflow_template_id, user_id=user_id)
    path = root / "workflow_template.yaml"
    wf = bundle.get("workflow", {})
    if wf.get("id") != workflow_template_id:
        wf["id"] = workflow_template_id
    document = {"version": bundle.get("version", 1), "workflow": wf}
    text = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    )
    header = (
        "# Workflow template folder — workflow graph and metadata. "
        "Agent definitions for this workflow template live in ./agents/.\n\n"
    )
    path.write_text(header + text, encoding="utf-8")
    return path


def load_workflow_bundle(workflow_id: str, *, user_id: str | None = None) -> dict[str, Any]:
    _assert_safe_workflow_id(workflow_id)
    if workflow_template_config_root(workflow_id, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    path = workflow_template_yaml_path(workflow_id, user_id=user_id)
    return _normalize_bundle(copy.deepcopy(_load_yaml(path)))


def save_workflow_bundle(
    workflow_id: str,
    bundle: dict[str, Any],
    *,
    validate_agent_refs: bool = True,
    user_id: str,
) -> Path:
    _assert_safe_workflow_id(workflow_id)
    wf = bundle.get("workflow", {})
    graph_ids = resolve_graph_agent_order(wf.get("graph") or {})
    if validate_agent_refs:
        pool = union_agent_by_id(user_id=user_id)
        missing = [aid for aid in graph_ids if aid and aid not in pool]
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown agents referenced by workflow template graph: {missing}")
    path = _write_workflow_template_yaml(workflow_id, bundle, user_id=user_id)
    copy_global_agents_to_workflow_template(workflow_id, [aid for aid in graph_ids if aid], user_id=user_id)
    return path


def _bundle_to_read(path: Path, bundle: dict[str, Any]) -> WorkflowTemplateRead:
    wf = bundle["workflow"]
    mt = _utc_from_mtime(path)
    nas = mt.replace(tzinfo=None)
    return WorkflowTemplateRead(
        id=wf["id"],
        created_at=nas,
        updated_at=nas,
        name=wf["name"],
        description=wf.get("description", ""),
        workflow_template=wf.get("workflow_template", "standard"),
        graph=wf["graph"],
        status=wf.get("status", "draft"),
        version=int(wf.get("version", 1)),
    )


def list_workflow_bundle_paths(*, user_id: str | None = None) -> list[Path]:
    ensure_workflow_templates_dir()
    return [workflow_template_yaml_path(path.name, user_id=user_id) for path in list_workflow_template_config_dirs(user_id=user_id)]


def list_workflow_reads_for_api(*, include_drafts: bool, user_id: str | None = None) -> list[WorkflowTemplateRead]:
    items: list[tuple[Path, WorkflowTemplateRead]] = []
    for path in list_workflow_bundle_paths(user_id=user_id):
        bundle = _normalize_bundle(copy.deepcopy(_load_yaml(path)))
        wf = bundle["workflow"]
        if not include_drafts and wf.get("status") != "published":
            continue
        items.append((path, _bundle_to_read(path, bundle)))
    items.sort(key=lambda pair: pair[0].stat().st_mtime, reverse=True)
    return [read for _, read in items]


def _load_workflow_template_agent_rows(workflow_template_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
    directory = workflow_template_agents_dir(workflow_template_id, user_id=user_id)
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        doc = _load_yaml(path)
        if doc:
            rows.append(normalize_agent_record(copy.deepcopy(doc)))
    return rows


def workflow_template_agent_by_id(workflow_template_id: str, *, user_id: str | None = None) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in _load_workflow_template_agent_rows(workflow_template_id, user_id=user_id)}


def union_agent_by_id(*, user_id: str | None = None) -> dict[str, dict[str, Any]]:
    """Global agent library used when validating graph references."""
    return global_agent_by_id(user_id=user_id)


def _pick_agents_for_graph(agent_ids: list[str], pool: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    missing: list[str] = []
    for aid in agent_ids:
        row = pool.get(aid)
        if row is None:
            missing.append(aid)
        else:
            picked.append(copy.deepcopy(row))
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown agent ids: {missing}")
    return picked


def _prepare_graph(graph: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(graph)
    try:
        validate_workflow_graph(prepared)
    except WorkflowGraphError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    entry_node, report_node = infer_entry_and_report_nodes(prepared)
    prepared["entry_node"] = entry_node
    prepared["report_node"] = report_node
    return prepared


def create_workflow_template(payload: WorkflowTemplateCreate, *, user_id: str) -> WorkflowTemplateRead:
    ensure_workflow_templates_dir()
    data = payload.model_dump(exclude_none=True)
    wf_id = data.get("id") or new_id("workflow_tpl")
    _assert_safe_workflow_id(wf_id)
    if workflow_template_config_root(wf_id, user_id=user_id) is not None:
        raise HTTPException(status_code=409, detail=f"Workflow id already exists: {wf_id}")
    graph = _prepare_graph(data["graph"])
    agent_ids = resolve_graph_agent_order(graph)
    pool = union_agent_by_id(user_id=user_id)
    _pick_agents_for_graph(agent_ids, pool)
    bundle = {
        "version": 1,
        "workflow": {
            "id": wf_id,
            "name": data["name"],
            "description": data.get("description", ""),
            "workflow_template": data.get("workflow_template", "standard"),
            "graph": graph,
            "status": data.get("status") or "draft",
            "version": int(data.get("version") or 1),
        },
    }
    path = save_workflow_bundle(wf_id, bundle, user_id=user_id)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def update_workflow_template(workflow_id: str, payload: WorkflowTemplateUpdate, *, user_id: str) -> WorkflowTemplateRead:
    bundle = load_workflow_bundle(workflow_id, user_id=user_id)
    wf = bundle["workflow"]
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "version" and value is not None:
            wf[key] = int(value)
        elif value is not None:
            wf[key] = value
    if "graph" in updates and updates["graph"] is not None:
        wf["graph"] = _prepare_graph(updates["graph"])
        agent_ids = resolve_graph_agent_order(wf["graph"])
        pool = union_agent_by_id(user_id=user_id)
        _pick_agents_for_graph(agent_ids, pool)
    path = save_workflow_bundle(workflow_id, bundle, user_id=user_id)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def delete_workflow_template(workflow_id: str, *, user_id: str) -> None:
    _assert_safe_workflow_id(workflow_id)
    if is_protected_workflow_template(workflow_id):
        raise HTTPException(status_code=403, detail="内置工作流模板不可删除")
    root = workflow_template_config_root(workflow_id, user_id=user_id)
    if root is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    shutil.rmtree(root)


def publish_workflow_template(workflow_id: str, *, user_id: str) -> WorkflowTemplateRead:
    source_root = data_workflow_templates_root(user_id) / workflow_id
    source_yaml = source_root / "workflow_template.yaml"
    if not source_yaml.is_file():
        raise HTTPException(status_code=404, detail="Workflow draft not found under user workflows")
    bundle = _normalize_bundle(copy.deepcopy(_load_yaml(source_yaml)))
    wf = bundle["workflow"]
    wf["status"] = "published"
    wf["version"] = int(wf.get("version", 1)) + 1
    target_root = builtin_workflow_templates_root() / workflow_id
    target_root.mkdir(parents=True, exist_ok=True)
    target_workflow_yaml = target_root / "workflow_template.yaml"
    document = {"version": bundle.get("version", 1), "workflow": wf}
    text = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    )
    header = (
        "# Workflow template folder — workflow graph and metadata. "
        "Agent definitions for this workflow template live in ./agents/.\n\n"
    )
    target_workflow_yaml.write_text(header + text, encoding="utf-8")

    source_agents = source_root / "agents"
    target_agents = target_root / "agents"
    target_agents.mkdir(parents=True, exist_ok=True)
    for stale in target_agents.glob("*.yaml"):
        if stale.name.startswith("_"):
            continue
        stale.unlink(missing_ok=True)
    if source_agents.is_dir():
        for agent_path in source_agents.glob("*.yaml"):
            if agent_path.name.startswith("_"):
                continue
            shutil.copy2(agent_path, target_agents / agent_path.name)

    # Keep user draft status/version in sync with the published state.
    _write_workflow_template_yaml(workflow_id, bundle, user_id=user_id)
    return _bundle_to_read(target_workflow_yaml, _normalize_bundle(copy.deepcopy(_load_yaml(target_workflow_yaml))))


def clone_workflow_template(workflow_id: str, *, user_id: str) -> WorkflowTemplateRead:
    source = load_workflow_bundle(workflow_id, user_id=user_id)
    new_id_str = new_id("workflow_tpl")
    _assert_safe_workflow_id(new_id_str)
    wf = copy.deepcopy(source["workflow"])
    wf["id"] = new_id_str
    wf["name"] = f"{wf.get('name', workflow_id)} Copy"
    wf["status"] = "draft"
    wf["version"] = 1
    bundle = {"version": 1, "workflow": wf}
    path = save_workflow_bundle(new_id_str, bundle, validate_agent_refs=False, user_id=user_id)
    source_agents = workflow_template_agents_dir(workflow_id, user_id=user_id)
    target_agents = workflow_template_agents_write_dir(new_id_str, user_id=user_id)
    for agent_path in source_agents.glob("*.yaml"):
        if agent_path.name.startswith("_"):
            continue
        shutil.copy2(agent_path, target_agents / agent_path.name)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def get_published_workflow_bundle(workflow_id: str, *, user_id: str | None = None) -> dict[str, Any]:
    if workflow_template_config_root(workflow_id, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail=f"Workflow template not found: {workflow_id}")
    bundle = _normalize_bundle(copy.deepcopy(_load_yaml(workflow_template_yaml_path(workflow_id, user_id=user_id))))
    if bundle["workflow"].get("status") != "published":
        raise HTTPException(status_code=400, detail="Workflow template must be published before running")
    return bundle


def resolve_agents_for_snapshot(
    bundle: dict[str, Any], agent_ids: list[str], *, user_id: str | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    workflow_template_id = bundle["workflow"]["id"]
    by_id = workflow_template_agent_by_id(workflow_template_id, user_id=user_id)
    found: list[dict[str, Any]] = []
    missing: list[str] = []
    for aid in agent_ids:
        row = by_id.get(aid)
        if row is None or not row.get("enabled", True):
            missing.append(aid)
        else:
            found.append(copy.deepcopy(row))
    return found, missing


def workflow_template_agent_display_names(agent_ids: list[str]) -> dict[str, str]:
    pool = union_agent_by_id()
    return {aid: pool.get(aid, {}).get("name", aid) for aid in agent_ids}


def list_union_agent_reads(*, only_enabled_non_admin: bool, user_id: str | None = None):
    from app.services.agent_catalog_files import list_agent_reads

    return list_agent_reads(only_enabled_non_admin=only_enabled_non_admin, user_id=user_id)


def create_agent(payload, *, user_id: str):
    from app.services.agent_catalog_files import create_agent as create_user_agent

    return create_user_agent(payload, user_id=user_id)


def update_agent(agent_id: str, payload, *, user_id: str):
    from app.services.agent_catalog_files import update_agent as update_user_agent

    return update_user_agent(agent_id, payload, user_id=user_id)


def publish_agent(agent_id: str, *, user_id: str):
    from app.services.agent_catalog_files import publish_agent as publish_user_agent

    return publish_user_agent(agent_id, user_id=user_id)


__all__ = [
    "clone_workflow_template",
    "create_agent",
    "create_workflow_template",
    "delete_workflow_template",
    "ensure_workflow_templates_dir",
    "get_published_workflow_bundle",
    "list_union_agent_reads",
    "list_workflow_reads_for_api",
    "load_workflow_bundle",
    "publish_agent",
    "protected_workflow_template_ids",
    "publish_workflow_template",
    "resolve_agents_for_snapshot",
    "workflow_template_agent_display_names",
    "union_agent_by_id",
    "update_agent",
    "update_workflow_template",
    "workflow_bundle_path",
    "workflow_templates_dir",
]
