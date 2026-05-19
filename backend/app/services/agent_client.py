from __future__ import annotations

import httpx

from app.core.config import settings


class AgentServiceError(RuntimeError):
    pass


class AgentServiceClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.agent_service_url).rstrip("/")

    async def start_run(
        self,
        project_id: str,
        company_config: dict,
        workflow_snapshot: dict | None = None,
        *,
        client_run_id: str | None = None,
        diligence_session_id: str | None = None,
        attempt_index: int | None = None,
        continuation_context: dict | None = None,
        pause_after_each_step: bool = False,
        resume_from_step_index: int = 0,
        completed_steps: list[dict] | None = None,
    ) -> dict:
        payload: dict = {
            "project_id": project_id,
            "company_config": company_config,
            "workflow_snapshot": workflow_snapshot,
            "pause_after_each_step": pause_after_each_step,
            "resume_from_step_index": resume_from_step_index,
        }
        if client_run_id:
            payload["run_id"] = client_run_id
        if diligence_session_id:
            payload["diligence_session_id"] = diligence_session_id
        if attempt_index is not None:
            payload["attempt_index"] = attempt_index
        if continuation_context is not None:
            payload["continuation_context"] = continuation_context
        if completed_steps:
            payload["completed_steps"] = completed_steps

        async with httpx.AsyncClient(timeout=3600) as client:
            try:
                response = await client.post(f"{self.base_url}/runs", json=payload)
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
                response = await client.post(f"{self.base_url}/assist/step-review-chat", json=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise AgentServiceError(f"Agent assist chat failed: {exc}") from exc
        return response.json()

    async def get_config(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(f"{self.base_url}/config")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise AgentServiceError(f"Agent service config request failed: {exc}") from exc
        return response.json()
