from __future__ import annotations

from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.models.entities import User
from app.schemas import ScenarioRead
from app.services.workflow_graph import resolve_graph_agent_order
from app.services.workflow_template_files import list_workflow_reads_for_api, scenario_agent_display_names


router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioRead])
async def list_scenarios(_: User = Depends(get_current_user)) -> list[ScenarioRead]:
    workflows = list_workflow_reads_for_api(include_drafts=False)
    return [
        ScenarioRead(
            id=w.id,
            name=w.name,
            description=w.description,
            scenario=w.scenario,
            agents=_agents_from_graph(w.graph),
        )
        for w in workflows
    ]


def _agents_from_graph(graph: dict) -> list[str]:
    agent_ids = resolve_graph_agent_order(graph)
    mapping = scenario_agent_display_names(agent_ids)
    return [mapping.get(aid, aid) for aid in agent_ids]

