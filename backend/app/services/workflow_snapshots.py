from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import AgentTemplate, ResourceConfig, SkillPackage, ToolConfig, WorkflowTemplate


def build_workflow_snapshot(db: Session, company_config: dict) -> dict:
    scope = company_config.get("scope", {})
    workflow_id = scope.get("workflow_template_id") or scope.get("workflow_id") or "standard_due_diligence"
    workflow = db.get(WorkflowTemplate, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow template not found: {workflow_id}")
    if workflow.status != "published":
        raise HTTPException(status_code=400, detail="Workflow template must be published before running")

    agent_ids = [node.get("agent_template_id", "") for node in workflow.graph.get("nodes", [])]
    agents = db.query(AgentTemplate).filter(AgentTemplate.id.in_(agent_ids), AgentTemplate.enabled.is_(True)).all()
    agent_by_id = {agent.id: agent for agent in agents}
    missing_agents = [agent_id for agent_id in agent_ids if agent_id not in agent_by_id]
    if missing_agents:
        raise HTTPException(status_code=400, detail=f"Workflow has missing or disabled agents: {missing_agents}")

    skill_package_ids = sorted({skill_id for agent in agents for skill_id in (agent.skill_package_ids or [])})
    tool_ids = sorted({tool_id for agent in agents for tool_id in (agent.tool_ids or agent.skill_ids or [])})
    resource_ids = sorted({resource_id for agent in agents for resource_id in agent.resource_ids})
    skill_packages = db.query(SkillPackage).filter(SkillPackage.id.in_(skill_package_ids), SkillPackage.enabled.is_(True)).all()
    tools = db.query(ToolConfig).filter(ToolConfig.id.in_(tool_ids), ToolConfig.enabled.is_(True)).all()
    resources = db.query(ResourceConfig).filter(ResourceConfig.id.in_(resource_ids), ResourceConfig.enabled.is_(True)).all()

    return {
        "workflow": {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "scenario": workflow.scenario,
            "version": workflow.version,
            "graph": workflow.graph,
        },
        "agent_templates": [
            {
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "prompt": agent.prompt,
                "skill_package_ids": agent.skill_package_ids or [],
                "tool_ids": agent.tool_ids or agent.skill_ids or [],
                "skill_ids": agent.tool_ids or agent.skill_ids or [],
                "resource_ids": agent.resource_ids,
                "react_config": agent.react_config or {"max_iters": 6, "parallel_tool_calls": False},
                "output_schema": agent.output_schema,
            }
            for agent in sorted(agents, key=lambda item: agent_ids.index(item.id))
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
                "connection_config": resource.connection_config,
            }
            for resource in resources
        ],
    }
