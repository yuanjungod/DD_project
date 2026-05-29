from __future__ import annotations

import httpx

from app.core.config import settings
from shared.session_fields import dual_write_session_id_fields


class AgentServiceError(RuntimeError):
    pass


class AgentServiceClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.agent_service_url).rstrip("/")

    def _agent_headers(self) -> dict[str, str]:
        key = settings.agent_api_key.strip()
        return {"X-Agent-Api-Key": key} if key else {}

    async def start_run(
        self,
        engagement_id: str,
        company_config: dict,
        workflow_snapshot: dict | None = None,
        *,
        user_id: str,
        client_run_id: str | None = None,
        workflow_session_id: str | None = None,
        diligence_session_id: str | None = None,
        attempt_index: int | None = None,
        continuation_context: dict | None = None,
        pause_after_each_step: bool = False,
        resume_from_step_index: int = 0,
        completed_steps: list[dict] | None = None,
    ) -> dict:
        payload: dict = {
            "engagement_id": engagement_id,
            "user_id": user_id,
            "company_config": company_config,
            "workflow_snapshot": workflow_snapshot,
            "pause_after_each_step": pause_after_each_step,
            "resume_from_step_index": resume_from_step_index,
        }
        if client_run_id:
            payload["run_id"] = client_run_id
        session_id = (workflow_session_id or diligence_session_id or "").strip() or None
        if session_id:
            payload.update(dual_write_session_id_fields(session_id))
        if attempt_index is not None:
            payload["attempt_index"] = attempt_index
        if continuation_context is not None:
            payload["continuation_context"] = continuation_context
        if completed_steps:
            payload["completed_steps"] = completed_steps

        async with httpx.AsyncClient(timeout=3600) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/runs",
                    json=payload,
                    headers=self._agent_headers(),
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = ""
                try:
                    detail = exc.response.text[:2000]
                except Exception:
                    pass
                msg = f"{exc}"
                if detail:
                    msg = f"{msg} body={detail}"
                raise AgentServiceError(f"Agent service request failed: {msg}") from exc
            except httpx.HTTPError as exc:
                raise AgentServiceError(f"Agent service request failed: {exc}") from exc
        return response.json()

    async def assist_step_review_chat(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=900) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/assist/step-review-chat",
                    json=payload,
                    headers=self._agent_headers(),
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise AgentServiceError(f"Agent assist chat failed: {exc}") from exc
        return response.json()

    async def get_config(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(f"{self.base_url}/config", headers=self._agent_headers())
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise AgentServiceError(f"Agent service config request failed: {exc}") from exc
        return response.json()
