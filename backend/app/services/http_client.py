"""Shared httpx.AsyncClient for outbound agent_service calls."""

from __future__ import annotations

import httpx

from app.core.config import settings

_client: httpx.AsyncClient | None = None


def get_async_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        headers: dict[str, str] = {}
        key = settings.agent_api_key.strip()
        if key:
            headers["X-Agent-Api-Key"] = key
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(3600.0),
            headers=headers,
        )
    return _client


async def close_async_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
