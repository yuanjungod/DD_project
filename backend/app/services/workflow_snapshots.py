from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import AgentTemplate, ResourceConfig, SkillConfig, WorkflowTemplate


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

    skill_ids = sorted({skill_id for agent in agents for skill_id in agent.skill_ids})
    resource_ids = sorted({resource_id for agent in agents for resource_id in agent.resource_ids})
    skills = db.query(SkillConfig).filter(SkillConfig.id.in_(skill_ids), SkillConfig.enabled.is_(True)).all()
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
                "skill_ids": agent.skill_ids,
                "resource_ids": agent.resource_ids,
                "output_schema": agent.output_schema,
            }
            for agent in sorted(agents, key=lambda item: agent_ids.index(item.id))
        ],
        "skills": [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "implementation": skill.implementation,
                "input_schema": skill.input_schema,
                "output_schema": skill.output_schema,
                "requires_api_key": skill.requires_api_key,
            }
            for skill in skills
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
