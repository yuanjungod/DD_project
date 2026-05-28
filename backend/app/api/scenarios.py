from __future__ import annotations

from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.models.entities import User
from app.schemas import WorkflowTemplateSummaryRead
from app.services.workflow_graph import resolve_graph_agent_order
from app.services.workflow_template_files import list_workflow_reads_for_api, workflow_template_agent_display_names


router = APIRouter(prefix="/workflow-templates/published", tags=["workflow_templates"])


@router.get("", response_model=list[WorkflowTemplateSummaryRead])
async def list_published_workflow_templates(user: User = Depends(get_current_user)) -> list[WorkflowTemplateSummaryRead]:
    workflows = list_workflow_reads_for_api(include_drafts=False, user_id=user.id)
    return [
        WorkflowTemplateSummaryRead(
            id=w.id,
            name=w.name,
            description=w.description,
            workflow_template=w.workflow_template,
            agents=_agents_from_graph(w.graph),
        )
        for w in workflows
    ]


def _agents_from_graph(graph: dict) -> list[str]:
    agent_ids = resolve_graph_agent_order(graph)
    mapping = workflow_template_agent_display_names(agent_ids)
    return [mapping.get(aid, aid) for aid in agent_ids]

