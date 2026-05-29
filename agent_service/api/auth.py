"""API key authentication for agent service endpoints."""

from __future__ import annotations

from fastapi import Header, HTTPException

from agent_service.settings import _DEV_AGENT_API_KEY, get_agent_settings

_DEV_DEFAULT_KEY = _DEV_AGENT_API_KEY


def require_agent_api_key(x_agent_api_key: str | None = Header(default=None, alias="X-Agent-Api-Key")) -> None:
    settings = get_agent_settings()
    expected = settings.agent_api_key.strip()
    if not expected:
        return
    if settings.is_production and expected == _DEV_DEFAULT_KEY:
        raise HTTPException(status_code=500, detail="Agent API key must be configured in production")
    if not x_agent_api_key or x_agent_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing agent API key")
