from __future__ import annotations

import httpx

from app.core.config import settings


class AgentServiceError(RuntimeError):
    pass


class AgentServiceClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.agent_service_url).rstrip("/")

    async def start_run(self, project_id: str, company_config: dict) -> dict:
        payload = {"project_id": project_id, "company_config": company_config}
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(f"{self.base_url}/runs", json=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise AgentServiceError(f"Agent service request failed: {exc}") from exc
        return response.json()
