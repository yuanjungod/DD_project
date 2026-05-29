from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_service.api.schemas import AgentStep
from agent_service.settings import get_agent_settings

logger = logging.getLogger(__name__)


def notify_run_progress(
    engagement_id: str,
    run_id: str,
    step: AgentStep,
) -> None:
    settings = get_agent_settings()
    base = settings.platform_callback_base_url.strip()
    if not base:
        return

    url = f"{base.rstrip('/')}/internal/agent-runs/{run_id}/progress"
    payload: dict[str, Any] = {
        "engagement_id": engagement_id,
        "step": step.model_dump(mode="json"),
    }

    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"X-Agent-Callback-Secret": settings.agent_callback_secret},
            timeout=30.0,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — never fail the workflow run on callback issues
        logger.warning("Platform progress callback failed (%s): %s", url, exc)
