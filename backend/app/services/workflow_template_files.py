from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException

from app.models.entities import new_id
from app.schemas.dto import (
    AgentTemplateBase,
    AgentTemplateCreate,
    AgentTemplateRead,
    AgentTemplateUpdate,
    WorkflowTemplateCreate,
    WorkflowTemplateRead,
    WorkflowTemplateUpdate,
)

ROOT = Path(__file__).resolve().parents[3]
AGENT_CONFIG_DIR = ROOT / "agent_service" / "configs"
SCENARIO_TEMPLATES_DIR = AGENT_CONFIG_DIR / "scenario_templates"
AGENT_TEMPLATES_PATH = AGENT_CONFIG_DIR / "agent_templates.yaml"

_WORKFLOW_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# Shipped scenario templates under agent_service/configs/scenario_templates — must not be removed via API.
_PROTECTED_WORKFLOW_TEMPLATE_IDS = frozenset(
    {
        "standard_due_diligence",
        "financial_investment_due_diligence",
        "legal_compliance_due_diligence",
        "market_entry_due_diligence",
    }
)


def workflow_templates_dir() -> Path:
    return SCENARIO_TEMPLATES_DIR


def _utc_from_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded if isinstance(loaded, dict) else {}


def _default_react_config() -> dict[str, Any]:
    return {
        "max_iters": 6,
        "parallel_tool_calls": False,
        "model": {
            "baseUrl": "http://127.0.0.1:8081/v1",
            "apiKey": "yuanjun",
            "api": "anthropic-messages",
            "models": [
                {
                    "id": "kimi-code",
                    "name": "kimi-code(Custom Provider)",
                    "reasoning": True,
                    "input": ["text", "image"],
                    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                    "contextWindow": 128000,
                    "maxTokens": 4096,
                }
            ],
        },
    }


def _merge_react_config(existing: dict[str, Any]) -> dict[str, Any]:
    merged = _default_react_config()
    merged.update(existing)
    merged["model"] = existing.get("model") or merged["model"]
    return merged


def _resource_ids_for_tools(tool_ids: list[str]) -> list[str]:
    resource_ids: list[str] = []
    if any(tool in tool_ids for tool in ("search", "web_fetch")):
        resource_ids.append("resource_public_web")
    if "file_reader" in tool_ids:
        resource_ids.append("resource_uploaded_files")
    if "vector_retrieval" in tool_ids:
        resource_ids.append("resource_vector_store")
    return resource_ids


def _normalize_agent_record(raw: dict[str, Any]) -> dict[str, Any]:
    if "id" not in raw:
        raise HTTPException(status_code=400, detail="Each agent requires an id")
    data = dict(raw)
    data.pop("output_schema", None)
    tid = data["id"]
    data.setdefault("name", tid)
    data.setdefault("role", "")
    data.setdefault("prompt", "")
    data.setdefault("skill_package_ids", [])
    tool_ids = data.get("tool_ids") or data.get("skill_ids") or []
    data["tool_ids"] = list(tool_ids)
    data["skill_ids"] = list(data.get("skill_ids") or tool_ids)
    if not data.get("resource_ids"):
        data["resource_ids"] = _resource_ids_for_tools(data["tool_ids"])
    puf = data.get("platform_upload_file_ids")
    data["platform_upload_file_ids"] = [str(x).strip() for x in (puf or []) if str(x).strip()]
    rc = data.get("react_config")
    if not rc or not isinstance(rc, dict) or "model" not in rc:
        data["react_config"] = _merge_react_config(rc if isinstance(rc, dict) else {})
    else:
        data["react_config"] = rc
    data.setdefault("enabled", True)
    return data


def _migration_agent_catalog() -> dict[str, dict[str, Any]]:
    if not AGENT_TEMPLATES_PATH.exists():
        return {}
    loaded = yaml.safe_load(AGENT_TEMPLATES_PATH.read_text(encoding="utf-8"))
    raw_list: Any = loaded.get("agents", []) if isinstance(loaded, dict) else []
    rows = [dict(item) for item in raw_list] if isinstance(raw_list, list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        norm = _normalize_agent_record(copy.deepcopy(dict(raw)))
        by_id[norm["id"]] = norm
    return by_id


def ensure_scenario_templates_dir() -> None:
    SCENARIO_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def _assert_safe_workflow_id(workflow_id: str) -> None:
    if not workflow_id or not _WORKFLOW_ID_PATTERN.fullmatch(workflow_id):
        raise HTTPException(status_code=400, detail="Invalid workflow id; use alphanumeric, hyphen, underscore only")


def workflow_bundle_path(workflow_id: str) -> Path:
    _assert_safe_workflow_id(workflow_id)
    return SCENARIO_TEMPLATES_DIR / f"{workflow_id}.yaml"


def load_workflow_bundle(workflow_id: str) -> dict[str, Any]:
    path = workflow_bundle_path(workflow_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return _normalize_bundle(copy.deepcopy(_load_yaml(path)))


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


def save_workflow_bundle(workflow_id: str, bundle: dict[str, Any], *, validate_agent_refs: bool = True) -> Path:
    _assert_safe_workflow_id(workflow_id)
    path = workflow_bundle_path(workflow_id)
    wf = bundle.get("workflow", {})
    if wf.get("id") != workflow_id:
        wf["id"] = workflow_id
    graph_ids = _agent_ids_from_graph(wf.get("graph") or {})
    if validate_agent_refs:
        pool = union_agent_by_id()
        missing = [aid for aid in graph_ids if aid and aid not in pool]
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown agents referenced by scenario graph: {missing}")
    document = {"version": bundle.get("version", 1), "workflow": wf}
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    )
    header = "# Scenario template — workflow graph only. Agent definitions live in agent_service/configs/agent_templates.yaml.\n\n"
    path.write_text(header + text, encoding="utf-8")
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
    if not SCENARIO_TEMPLATES_DIR.is_dir():
        return []
    return sorted(
        p
        for p in SCENARIO_TEMPLATES_DIR.glob("*.yaml")
        if not p.name.startswith("_") and _load_yaml(p).get("workflow")
    )


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


def _load_agent_catalog_rows() -> list[dict[str, Any]]:
    if not AGENT_TEMPLATES_PATH.exists():
        return []
    doc = _load_yaml(AGENT_TEMPLATES_PATH)
    raw = doc.get("agents", [])
    return [dict(x) for x in raw] if isinstance(raw, list) else []


def _save_agent_catalog_rows(rows: list[dict[str, Any]]) -> None:
    AGENT_TEMPLATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payloads = [_normalize_agent_record(copy.deepcopy(row)) for row in rows]
    for row in payloads:
        AgentTemplateBase.model_validate({k: v for k, v in row.items() if k != "id"})
    ids = [row["id"] for row in payloads]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Duplicate agent ids in agent catalog")
    document = {"version": 1, "agents": payloads}
    text = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    )
    header = "# Agent templates — reusable agent definitions. Scenario templates reference these by id.\n\n"
    AGENT_TEMPLATES_PATH.write_text(header + text, encoding="utf-8")


def union_agent_by_id() -> dict[str, dict[str, Any]]:
    ensure_scenario_templates_dir()
    merged: dict[str, dict[str, Any]] = {}
    for row in _load_agent_catalog_rows():
        norm = _normalize_agent_record(copy.deepcopy(row))
        merged[norm["id"]] = norm
    return merged


def _agent_ids_from_graph(graph: dict[str, Any]) -> list[str]:
    return [node.get("agent_template_id", "") for node in graph.get("nodes", [])]


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
    path = workflow_bundle_path(wf_id)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Workflow id already exists: {wf_id}")
    graph = data["graph"]
    agent_ids = _agent_ids_from_graph(graph)
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
        agent_ids = _agent_ids_from_graph(updates["graph"])
        pool = union_agent_by_id()
        _pick_agents_for_graph(agent_ids, pool)
    path = save_workflow_bundle(workflow_id, bundle)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def delete_workflow_template(workflow_id: str) -> None:
    _assert_safe_workflow_id(workflow_id)
    if workflow_id in _PROTECTED_WORKFLOW_TEMPLATE_IDS:
        raise HTTPException(status_code=403, detail="内置工作流模板不可删除")
    path = workflow_bundle_path(workflow_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Workflow template not found")
    path.unlink()


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
    bundle = {
        "version": 1,
        "workflow": wf,
    }
    path = save_workflow_bundle(new_id_str, bundle)
    return _bundle_to_read(path, _normalize_bundle(copy.deepcopy(_load_yaml(path))))


def get_published_workflow_bundle(workflow_id: str) -> dict[str, Any]:
    path = workflow_bundle_path(workflow_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow template not found: {workflow_id}")
    bundle = _normalize_bundle(copy.deepcopy(_load_yaml(path)))
    if bundle["workflow"].get("status") != "published":
        raise HTTPException(status_code=400, detail="Workflow template must be published before running")
    return bundle


def resolve_agents_for_snapshot(bundle: dict[str, Any], agent_ids: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = union_agent_by_id()
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


def _agent_mtime_from_disk(agent_id: str) -> datetime:
    if not AGENT_TEMPLATES_PATH.exists():
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(AGENT_TEMPLATES_PATH.stat().st_mtime, tz=timezone.utc)


def list_union_agent_reads(*, only_enabled_non_admin: bool) -> list[AgentTemplateRead]:
    pool = union_agent_by_id()
    reads: list[AgentTemplateRead] = []
    for aid in sorted(pool.keys(), key=lambda k: pool[k]["name"].lower()):
        row = pool[aid]
        if only_enabled_non_admin and not row.get("enabled", True):
            continue
        mt = _agent_mtime_from_disk(aid)
        nas = mt.replace(tzinfo=None)
        base = AgentTemplateBase.model_validate({k: v for k, v in row.items() if k != "id"})
        reads.append(
            AgentTemplateRead(
                id=aid,
                created_at=nas,
                updated_at=nas,
                **base.model_dump(),
            )
        )
    return reads


def create_agent(payload: AgentTemplateCreate) -> AgentTemplateRead:
    data = payload.model_dump()
    if not data.get("id"):
        data["id"] = new_id("agent_tpl")
    norm = _normalize_agent_record(data)
    pool = union_agent_by_id()
    if norm["id"] in pool:
        raise HTTPException(status_code=409, detail=f"Agent id already exists: {norm['id']}")
    names = {r["name"] for r in pool.values()}
    if norm["name"] in names:
        raise HTTPException(status_code=409, detail=f"Agent name already exists: {norm['name']}")
    rows = _load_agent_catalog_rows()
    rows.append(norm)
    _save_agent_catalog_rows(rows)
    mt = _agent_mtime_from_disk(norm["id"])
    nas = mt.replace(tzinfo=None)
    base_fields = AgentTemplateBase.model_validate({k: v for k, v in norm.items() if k != "id"})
    return AgentTemplateRead(
        id=norm["id"],
        created_at=nas,
        updated_at=nas,
        **base_fields.model_dump(),
    )


def update_agent(agent_id: str, payload: AgentTemplateUpdate) -> AgentTemplateRead:
    updates = payload.model_dump(exclude_unset=True)
    pool = union_agent_by_id()
    if agent_id not in pool:
        raise HTTPException(status_code=404, detail="Agent template not found")

    rows = _load_agent_catalog_rows()
    for i, row in enumerate(rows):
        if row.get("id") == agent_id:
            current = dict(row)
            for key, value in updates.items():
                current[key] = value
            current["id"] = agent_id
            rows[i] = _normalize_agent_record(current)
            _save_agent_catalog_rows(rows)
            break

    pool_after = union_agent_by_id()
    final = pool_after.get(agent_id)
    if final is None:
        raise HTTPException(status_code=404, detail="Agent template not found after update")
    mt = _agent_mtime_from_disk(agent_id)
    nas = mt.replace(tzinfo=None)
    base_fields = AgentTemplateBase.model_validate({k: v for k, v in final.items() if k != "id"})
    return AgentTemplateRead(
        id=agent_id,
        created_at=nas,
        updated_at=nas,
        **base_fields.model_dump(),
    )
