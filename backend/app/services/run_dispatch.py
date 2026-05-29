"""Background agent run dispatch and blocking pipeline execution."""

from __future__ import annotations

import asyncio

from app.core.database import SessionLocal
from app.services.agent_client import AgentServiceClient
from app.services.persistence import finalize_agent_run, mark_agent_run_failed


async def dispatch_agent_background(
    engagement_id: str,
    run_id: str,
    user_id: str,
    company_config: dict,
    workflow_snapshot: dict,
    *,
    diligence_session_id: str,
    attempt_index: int,
    continuation_context: dict | None,
    pause_after_each_step: bool,
    resume_from_step_index: int,
    completed_steps: list[dict],
) -> None:
    await asyncio.to_thread(
        execute_agent_pipeline_blocking,
        engagement_id,
        run_id,
        user_id,
        company_config,
        workflow_snapshot,
        diligence_session_id=diligence_session_id,
        attempt_index=attempt_index,
        continuation_context=continuation_context,
        pause_after_each_step=pause_after_each_step,
        resume_from_step_index=resume_from_step_index,
        completed_steps=completed_steps,
    )


def execute_agent_pipeline_blocking(
    engagement_id: str,
    run_id: str,
    user_id: str,
    company_config: dict,
    workflow_snapshot: dict,
    *,
    diligence_session_id: str,
    attempt_index: int,
    continuation_context: dict | None,
    pause_after_each_step: bool,
    resume_from_step_index: int,
    completed_steps: list[dict],
) -> None:
    db = SessionLocal()
    client = AgentServiceClient()
    try:
        try:
            result = asyncio.run(
                client.start_run(
                    engagement_id,
                    company_config,
                    workflow_snapshot=workflow_snapshot,
                    user_id=user_id,
                    client_run_id=run_id,
                    diligence_session_id=diligence_session_id,
                    attempt_index=attempt_index,
                    continuation_context=continuation_context,
                    pause_after_each_step=pause_after_each_step,
                    resume_from_step_index=resume_from_step_index,
                    completed_steps=completed_steps,
                )
            )
        except Exception as exc:  # noqa: BLE001
            mark_agent_run_failed(db, run_id, str(exc))
            return
        if result.get("run_id") != run_id:
            mark_agent_run_failed(db, run_id, "Agent returned mismatched run_id")
            return
        finalize_agent_run(db, engagement_id=engagement_id, run_id=run_id, result=result)
    finally:
        db.close()
