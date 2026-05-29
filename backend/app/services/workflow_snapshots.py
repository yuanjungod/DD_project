from __future__ import annotations

from fastapi import HTTPException

from app.services.agent_record_utils import MAX_REACT_ITERS, normalize_tool_ids
from app.services.engagement_agent_overrides_store import engagement_agent_override_records
from app.services.engagement_resource_catalog import load_engagement_resource_configs_by_ids
from app.services.platform_resource_catalog import load_resource_configs_by_ids
from app.services.workflow_graph import resolve_graph_agent_order
from app.services.skill_catalog import load_skill_packages_by_ids
from app.services.tool_catalog import load_tool_configs_by_ids
from app.services.workflow_template_files import get_published_workflow_bundle, resolve_agents_for_snapshot


def _load_snapshot_resources(resource_ids: list[str], engagement_id: str | None) -> list:
    by_id: dict[str, object] = {}
    for row in load_resource_configs_by_ids(resource_ids):
        by_id[row.id] = row
    if engagement_id:
        for row in load_engagement_resource_configs_by_ids(engagement_id, resource_ids):
            by_id[row.id] = row
    return [by_id[k] for k in sorted(by_id.keys())]


def build_workflow_snapshot(company_config: dict, *, engagement_id: str | None = None) -> dict:
    workflow_template_id = _workflow_template_id_from_config(company_config)
    bundle = get_published_workflow_bundle(workflow_template_id)
    workflow_section = bundle["workflow"]

    agent_ids = resolve_graph_agent_order(workflow_section.get("graph") or {})
    agents, missing_agents = resolve_agents_for_snapshot(bundle, agent_ids)
    if missing_agents:
        raise HTTPException(status_code=400, detail=f"Workflow has missing or disabled agents: {missing_agents}")
    if engagement_id:
        agents = _apply_engagement_agent_overrides(agents, engagement_agent_override_records(engagement_id))

    skill_package_ids = sorted({skill_id for agent in agents for skill_id in (agent.get("skill_package_ids") or [])})
    tool_ids = sorted({tool_id for agent in agents for tool_id in normalize_tool_ids(agent)})
    resource_ids = sorted({resource_id for agent in agents for resource_id in (agent.get("resource_ids") or [])})
    skill_packages = load_skill_packages_by_ids(skill_package_ids)
    tools = load_tool_configs_by_ids(tool_ids)
    disk_resources = _load_snapshot_resources(resource_ids, engagement_id)

    return {
        "workflow": {
            "id": workflow_section["id"],
            "name": workflow_section["name"],
            "description": workflow_section.get("description", ""),
            "workflow_template": workflow_section.get("workflow_template", "standard"),
            "version": workflow_section.get("version", 1),
            "graph": workflow_section["graph"],
            "runtime": workflow_section.get("runtime")
            if isinstance(workflow_section.get("runtime"), dict)
            else {"command_execution": "host"},
        },
        "agent_templates": [
            {
                "id": agent["id"],
                "name": agent["name"],
                "role": agent["role"],
                "prompt": agent["prompt"],
                "sub_agent_ids": agent.get("sub_agent_ids") or [],
                "skill_package_ids": agent.get("skill_package_ids") or [],
                "tool_ids": normalize_tool_ids(agent),
                "resource_ids": agent.get("resource_ids") or [],
                "platform_upload_file_ids": agent.get("platform_upload_file_ids") or [],
                "react_config": agent.get("react_config")
                or {"max_iters": MAX_REACT_ITERS, "parallel_tool_calls": False},
            }
            for agent in sorted(agents, key=lambda row: agent_ids.index(row["id"]))
        ],
        "skill_packages": [
            {
                "id": skill_package.id,
                "name": skill_package.name,
                "description": skill_package.description,
                "directory_name": skill_package.directory_name,
                "skill_md": skill_package.skill_md,
                "package_files": skill_package.package_files or {},
                "resources_manifest": skill_package.resources_manifest,
            }
            for skill_package in skill_packages
        ],
        "tools": [
            {
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "implementation": tool.implementation,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
                "requires_api_key": tool.requires_api_key,
            }
            for tool in tools
        ],
        "resources": [
            {
                "id": resource.id,
                "name": resource.name,
                "type": resource.type,
                "description": resource.description,
                "connection_config": dict(resource.connection_config or {}),
            }
            for resource in disk_resources
        ],
    }


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _apply_id_delta(base: list[str], add: list[str], remove: list[str]) -> list[str]:
    remove_set = set(_unique(remove))
    return _unique([item for item in base if item not in remove_set] + add)


def _merge_dict(base: dict | None, override: dict | None) -> dict:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_engagement_agent_overrides(agents: list[dict], overrides: list[dict]) -> list[dict]:
    by_agent = {str(row.get("agent_id")): row for row in overrides if row.get("enabled", True)}
    out: list[dict] = []
    for agent in agents:
        row = dict(agent)
        override = by_agent.get(str(row.get("id")))
        if not override:
            out.append(row)
            continue

        prompt_override = str(override.get("prompt_override") or "").strip()
        prompt_append = str(override.get("prompt_append") or "").strip()
        if prompt_override:
            row["prompt"] = prompt_override
        elif prompt_append:
            inherited = str(row.get("prompt") or "").rstrip()
            row["prompt"] = f"{inherited}\n\n# 应用级补充提示词\n{prompt_append}".strip()

        row["skill_package_ids"] = _apply_id_delta(
            list(row.get("skill_package_ids") or []),
            list(override.get("skill_package_ids_add") or []),
            list(override.get("skill_package_ids_remove") or []),
        )
        row["tool_ids"] = _apply_id_delta(
            normalize_tool_ids(row),
            list(override.get("tool_ids_add") or []),
            list(override.get("tool_ids_remove") or []),
        )
        row["resource_ids"] = _apply_id_delta(
            list(row.get("resource_ids") or []),
            list(override.get("resource_ids_add") or []),
            list(override.get("resource_ids_remove") or []),
        )
        platform_files = _unique(list(override.get("platform_upload_file_ids") or []))
        if platform_files:
            row["platform_upload_file_ids"] = platform_files
        react_override = override.get("react_config_override")
        if isinstance(react_override, dict) and react_override:
            row["react_config"] = _merge_dict(row.get("react_config"), react_override)
        row["app_override"] = {
            "engagement_scoped": True,
            "prompt_mode": "override" if prompt_override else "append" if prompt_append else "inherit",
        }
        out.append(row)
    return out


def _workflow_template_id_from_config(company_config: dict) -> str:
    """Resolve published workflow template id from company_config."""
    if not company_config:
        raise HTTPException(status_code=400, detail="company_config.workflow_template_id is required")
    template_id = company_config.get("workflow_template_id")
    if isinstance(template_id, str) and template_id.strip():
        return template_id.strip()
    raise HTTPException(status_code=400, detail="company_config.workflow_template_id is required")
