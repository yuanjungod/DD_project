"""HTTP ingress for agent-service run progress callbacks (no user JWT auth)."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.persistence import upsert_incremental_run_progress

router = APIRouter(prefix="/internal/agent-runs", tags=["internal"], include_in_schema=False)


class RunProgressPayload(BaseModel):
    engagement_id: str
    step: dict[str, Any]


def _verify_callback_secret(secret_header: str | None) -> None:
    configured = settings.agent_callback_secret.strip()
    if not configured:
        raise HTTPException(status_code=503, detail="Agent callbacks are disabled (missing AGENT_CALLBACK_SECRET)")
    offered = secret_header or ""
    if not hmac.compare_digest(offered.encode(), configured.encode()):
        raise HTTPException(status_code=403, detail="Invalid callback credential")


@router.post("/{run_id}/progress")
def receive_run_progress(
    run_id: str,
    body: RunProgressPayload,
    x_agent_callback_secret: str | None = Header(default=None, alias="X-Agent-Callback-Secret"),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _verify_callback_secret(x_agent_callback_secret)
    keys = {"id", "agent", "status"}
    if not keys.issubset(body.step.keys()):
        raise HTTPException(status_code=400, detail="step payload must include id, agent, status")

    try:
        upsert_incremental_run_progress(
            db,
            run_id=run_id,
            project_id=body.engagement_id,
            step_payload=body.step,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "ok"}
