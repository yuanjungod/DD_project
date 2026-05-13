from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import AgentTemplate, User, WorkflowTemplate
from app.schemas import ScenarioRead


router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioRead])
async def list_scenarios(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ScenarioRead]:
    workflows = db.query(WorkflowTemplate).filter(WorkflowTemplate.status == "published").all()
    return [
        ScenarioRead(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            scenario=workflow.scenario,
            agents=_agents_from_graph(db, workflow.graph),
        )
        for workflow in workflows
    ]


def _agents_from_graph(db: Session, graph: dict) -> list[str]:
    agent_ids = [node.get("agent_template_id", "") for node in graph.get("nodes", [])]
    agents = db.query(AgentTemplate).filter(AgentTemplate.id.in_(agent_ids)).all()
    agent_names = {agent.id: agent.name for agent in agents}
    return [agent_names.get(agent_id, agent_id) for agent_id in agent_ids]
