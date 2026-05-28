from __future__ import annotations

import copy
import shutil
from datetime import datetime, timezone
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
from app.services.agent_catalog_files import copy_global_agents_to_scenario, global_agent_by_id
from app.services.agent_record_utils import normalize_agent_record
from app.services.catalog_layout import (
    assert_safe_scenario_id,
    data_scenarios_root,
    is_protected_scenario,
    list_scenario_config_dirs,
    protected_scenario_ids,
    scenario_agents_dir,
    scenario_config_root,
    scenario_config_write_root,
    scenario_yaml_path,
)
from app.services.workflow_graph import resolve_graph_agent_order


def workflow_templates_dir() -> Path:
    """Legacy helper — returns builtin scenarios root for compatibility."""
    from app.services.catalog_layout import builtin_scenarios_root

    return builtin_scenarios_root()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded if isinstance(loaded, dict) else {}


def _utc_from_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def ensure_scenario_templates_dir() -> None:
    from app.services.catalog_layout import builtin_scenarios_root, global_agents_dir

    builtin_scenarios_root()
    global_agents_dir()
    data_scenarios_root()


def _assert_safe_workflow_id(workflow_id: str) -> None:
    try:
        assert_safe_scenario_id(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def workflow_bundle_path(workflow_id: str) -> Path:
    _assert_safe_workflow_id(workflow_id)
    return scenario_yaml_path(workflow_id)


def _normalize_bundle(doc: dict[str, Any]) -> dict[str, Any]:
    wf = doc.get("workflow")
    if not isinstance(wf, dict):
        raise HTTPException(status_code=400, detail="Scenario template missing workflow section")
    wf.setdefault("description", "")
    wf.setdefault("scenario", "standard")
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


def _write_scenario_yaml(scenario_id: str, bundle: dict[str, Any]) -> Path:
    root = scenario_config_write_root(scenario_id)
    path = root / "scenario.yaml"
    wf = bundle.get("workflow", {})
    if wf.get("id") != scenario_id:
        wf["id"] = scenario_id
    document = {"version": bundle.get("version", 1), "workflow": wf}
    text = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    )
    header = (
        "# Scenario folder — workflow graph and metadata. "
        "Agent definitions for this scenario live in ./agents/.\n\n"
    )
    path.write_text(header + text, encoding="utf-8")
    return path


def load_workflow_bundle(workflow_id: str) -> dict[str, Any]:
    _assert_safe_workflow_id(workflow_id)
    if scenario_config_root(workflow_id) is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    path = scenario_yaml_path(workflow_id)
    return _normalize_bundle(copy.deepcopy(_load_yaml(path)))


def save_workflow_bundle(workflow_id: str, bundle: dict[str, Any], *, validate_agent_refs: bool = True) -> Path:
    _assert_safe_workflow_id(workflow_id)
    wf = bundle.get("workflow", {})
    graph_ids = resolve_graph_agent_order(wf.get("graph") or {})
    if validate_agent_refs:
        pool = union_agent_by_id()
        missing = [aid for aid in graph_ids if aid and aid not in pool]
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown agents referenced by scenario graph: {missing}")
    path = _write_scenario_yaml(workflow_id, bundle)
    copy_global_agents_to_scenario(workflow_id, [aid for aid in graph_ids if aid])
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
        scenario=wf.get("scenario", "standard"),
        graph=wf["graph"],
        status=wf.get("status", "draft"),
        version=int(wf.get("version", 1)),
    )


def list_workflow_bundle_paths() -> list[Path]:
    ensure_scenario_templates_dir()
    return [path / "scenario.yaml" for path in list_scenario_config_dirs()]


def list_workflow_reads_for_api(*, include_drafts: bool) -> list[WorkflowTemplateRead]:
    items: list[tuple[Path, WorkflowTemplateRead]] = []
    for path in list_workflow_bundle_paths():
        bundle = _normalize_bundle(copy.deepcopy(_load_yaml(path)))
        wf = bundle["workflow"]
        if not include_drafts and wf.get("status") != "published":
            continue
        items.append((path, _bundle_to_read(path, bundle)))
    items.sort(key=lambda pair: pair[0].stat().st_mtime, reverse=True)
    return [read for _, read in items]


def _load_scenario_agent_rows(scenario_id: str) -> list[dict[str, Any]]:
    directory = scenario_agents_dir(scenario_id)
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        doc = _load_yaml(path)
        if doc:
            rows.append(normalize_agent_record(copy.deepcopy(doc)))
    return rows


def scenario_agent_by_id(scenario_id: str) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in _load_scenario_agent_rows(scenario_id)}


def union_agent_by_id() -> dict[str, dict[str, Any]]:
    """Global agent library used when validating graph references."""
    return global_agent_by_id()


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


def create_workflow_template(payload: WorkflowTemplateCreate) -> WorkflowTemplateRead:
    ensure_scenario_templates_dir()
    data = payload.model_dump(exclude_none=True)
    wf_id = data.get("id") or new_id("workflow_tpl")
    _assert_safe_workflow_id(wf_id)
    if scenario_config_root(wf_id) is not None:
        raise HTTPException(status_code=409, detail=f"Workflow id already exists: {wf_id}")
    graph = data["graph"]
    agent_ids = resolve_graph_agent_order(graph)
    pool = union_agent_by_id()
    _pick_agents_for_graph(agent_ids, pool)
    bundle = {
        "version": 1,
        "workflow": {
            "id": wf_id,
            "name": data["name"],
            "description": data.get("description", ""),
            "scenario": data.get("scenario", "standard"),
            "graph": graph,
            "status": data.get("status") or "draft",
            "version": int(data.get("version") or 1),
        },
    }
    path = save_workflow_bundle(wf_id, bundle)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def update_workflow_template(workflow_id: str, payload: WorkflowTemplateUpdate) -> WorkflowTemplateRead:
    bundle = load_workflow_bundle(workflow_id)
    wf = bundle["workflow"]
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "version" and value is not None:
            wf[key] = int(value)
        elif value is not None:
            wf[key] = value
    if "graph" in updates and updates["graph"] is not None:
        agent_ids = resolve_graph_agent_order(updates["graph"])
        pool = union_agent_by_id()
        _pick_agents_for_graph(agent_ids, pool)
    path = save_workflow_bundle(workflow_id, bundle)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def delete_workflow_template(workflow_id: str) -> None:
    _assert_safe_workflow_id(workflow_id)
    if is_protected_scenario(workflow_id):
        raise HTTPException(status_code=403, detail="内置工作流模板不可删除")
    root = scenario_config_root(workflow_id)
    if root is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    shutil.rmtree(root)


def publish_workflow_template(workflow_id: str) -> WorkflowTemplateRead:
    bundle = load_workflow_bundle(workflow_id)
    wf = bundle["workflow"]
    wf["status"] = "published"
    wf["version"] = int(wf.get("version", 1)) + 1
    path = save_workflow_bundle(workflow_id, bundle)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def clone_workflow_template(workflow_id: str) -> WorkflowTemplateRead:
    source = load_workflow_bundle(workflow_id)
    new_id_str = new_id("workflow_tpl")
    _assert_safe_workflow_id(new_id_str)
    wf = copy.deepcopy(source["workflow"])
    wf["id"] = new_id_str
    wf["name"] = f"{wf.get('name', workflow_id)} Copy"
    wf["status"] = "draft"
    wf["version"] = 1
    bundle = {"version": 1, "workflow": wf}
    path = save_workflow_bundle(new_id_str, bundle, validate_agent_refs=False)
    source_agents = scenario_agents_dir(workflow_id)
    target_agents = scenario_agents_write_dir(new_id_str)
    for agent_path in source_agents.glob("*.yaml"):
        if agent_path.name.startswith("_"):
            continue
        shutil.copy2(agent_path, target_agents / agent_path.name)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def get_published_workflow_bundle(workflow_id: str) -> dict[str, Any]:
    if scenario_config_root(workflow_id) is None:
        raise HTTPException(status_code=404, detail=f"Workflow template not found: {workflow_id}")
    bundle = _normalize_bundle(copy.deepcopy(_load_yaml(scenario_yaml_path(workflow_id))))
    if bundle["workflow"].get("status") != "published":
        raise HTTPException(status_code=400, detail="Workflow template must be published before running")
    return bundle


def resolve_agents_for_snapshot(bundle: dict[str, Any], agent_ids: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    scenario_id = bundle["workflow"]["id"]
    by_id = scenario_agent_by_id(scenario_id)
    found: list[dict[str, Any]] = []
    missing: list[str] = []
    for aid in agent_ids:
        row = by_id.get(aid)
        if row is None or not row.get("enabled", True):
            missing.append(aid)
        else:
            found.append(copy.deepcopy(row))
    return found, missing


def scenario_agent_display_names(agent_ids: list[str]) -> dict[str, str]:
    pool = union_agent_by_id()
    return {aid: pool.get(aid, {}).get("name", aid) for aid in agent_ids}


def list_union_agent_reads(*, only_enabled_non_admin: bool):
    from app.services.agent_catalog_files import list_global_agent_reads

    return list_global_agent_reads(only_enabled_non_admin=only_enabled_non_admin)


def create_agent(payload):
    from app.services.agent_catalog_files import create_global_agent

    return create_global_agent(payload)


def update_agent(agent_id: str, payload):
    from app.services.agent_catalog_files import update_global_agent

    return update_global_agent(agent_id, payload)


__all__ = [
    "clone_workflow_template",
    "create_agent",
    "create_workflow_template",
    "delete_workflow_template",
    "ensure_scenario_templates_dir",
    "get_published_workflow_bundle",
    "list_union_agent_reads",
    "list_workflow_reads_for_api",
    "load_workflow_bundle",
    "protected_scenario_ids",
    "publish_workflow_template",
    "resolve_agents_for_snapshot",
    "scenario_agent_display_names",
    "union_agent_by_id",
    "update_agent",
    "update_workflow_template",
    "workflow_bundle_path",
    "workflow_templates_dir",
]
