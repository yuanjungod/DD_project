from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import SkillPackage, ToolConfig
from app.services.platform_resource_catalog import load_resource_configs_by_ids
from app.services.workflow_template_files import get_published_workflow_bundle, resolve_agents_for_snapshot


def build_workflow_snapshot(db: Session, company_config: dict) -> dict:
    scope = company_config.get("scope", {})
    workflow_id = scope.get("workflow_template_id") or scope.get("workflow_id") or "standard_due_diligence"
    bundle = get_published_workflow_bundle(workflow_id)
    workflow_section = bundle["workflow"]

    agent_ids = [node.get("agent_template_id", "") for node in workflow_section["graph"].get("nodes", [])]
    agents, missing_agents = resolve_agents_for_snapshot(bundle, agent_ids)
    if missing_agents:
        raise HTTPException(status_code=400, detail=f"Workflow has missing or disabled agents: {missing_agents}")

    skill_package_ids = sorted({skill_id for agent in agents for skill_id in (agent.get("skill_package_ids") or [])})
    tool_ids = sorted({tool_id for agent in agents for tool_id in (agent.get("tool_ids") or agent.get("skill_ids") or [])})
    resource_ids = sorted({resource_id for agent in agents for resource_id in (agent.get("resource_ids") or [])})
    skill_packages = db.query(SkillPackage).filter(SkillPackage.id.in_(skill_package_ids), SkillPackage.enabled.is_(True)).all()
    tools = db.query(ToolConfig).filter(ToolConfig.id.in_(tool_ids), ToolConfig.enabled.is_(True)).all()
    disk_resources = load_resource_configs_by_ids(resource_ids)

    return {
        "workflow": {
            "id": workflow_section["id"],
            "name": workflow_section["name"],
            "description": workflow_section.get("description", ""),
            "scenario": workflow_section.get("scenario", "standard"),
            "version": workflow_section.get("version", 1),
            "graph": workflow_section["graph"],
        },
        "agent_templates": [
            {
                "id": agent["id"],
                "name": agent["name"],
                "role": agent["role"],
                "prompt": agent["prompt"],
                "skill_package_ids": agent.get("skill_package_ids") or [],
                "tool_ids": agent.get("tool_ids") or agent.get("skill_ids") or [],
                "skill_ids": agent.get("tool_ids") or agent.get("skill_ids") or [],
                "resource_ids": agent.get("resource_ids") or [],
                "platform_upload_file_ids": agent.get("platform_upload_file_ids") or [],
                "react_config": agent.get("react_config")
                or {"max_iters": 6, "parallel_tool_calls": False},
                "output_schema": agent.get("output_schema") or "agent_result",
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
