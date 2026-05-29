"""Shared assembly of workflow snapshot + agent wire config for dispatch."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.entities import Engagement
from app.services.company_config_merge import merged_company_config_with_engagement_resources
from app.services.engagement_resources_store import engagement_resource_records_for_merge
from app.services.workflow_snapshots import build_workflow_snapshot
from shared.instance_config import to_agent_company_config


@dataclass(frozen=True)
class AgentDispatchContext:
    workflow_snapshot: dict
    company_config: dict


def build_agent_dispatch_context(
    engagement: Engagement,
    *,
    engagement_id: str | None = None,
) -> AgentDispatchContext:
    eid = engagement_id or engagement.id
    snapshot = build_workflow_snapshot(engagement.company_config, engagement_id=eid)
    stored = engagement.company_config if isinstance(engagement.company_config, dict) else {}
    eng_records = engagement_resource_records_for_merge(eid)
    company = merged_company_config_with_engagement_resources(
        to_agent_company_config(stored),
        eng_records,
    )
    return AgentDispatchContext(workflow_snapshot=dict(snapshot), company_config=company)
