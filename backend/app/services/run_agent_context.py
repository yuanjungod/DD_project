"""Shared assembly of workflow snapshot + agent wire config for dispatch."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.entities import Engagement
from app.services.instance_config_merge import merged_instance_config_with_engagement_resources
from app.services.engagement_resources_store import engagement_resource_records_for_merge
from app.services.workflow_snapshots import build_workflow_snapshot
from shared.instance_config import to_agent_run_config


@dataclass(frozen=True)
class AgentDispatchContext:
    workflow_snapshot: dict
    instance_config: dict


def build_agent_dispatch_context(
    engagement: Engagement,
    *,
    engagement_id: str | None = None,
) -> AgentDispatchContext:
    eid = engagement_id or engagement.id
    snapshot = build_workflow_snapshot(engagement.instance_config, engagement_id=eid)
    stored = engagement.instance_config if isinstance(engagement.instance_config, dict) else {}
    eng_records = engagement_resource_records_for_merge(eid)
    instance = merged_instance_config_with_engagement_resources(
        to_agent_run_config(stored),
        eng_records,
    )
    return AgentDispatchContext(workflow_snapshot=dict(snapshot), instance_config=instance)
