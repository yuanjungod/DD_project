from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Runtime config for the standalone agent service."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    platform_callback_base_url: str = Field(
        default="http://127.0.0.1:8010",
        validation_alias="PLATFORM_CALLBACK_BASE_URL",
        description="Backend base URL for incremental progress. Override in Docker (e.g. http://backend:8010) or set empty to disable.",
    )
    agent_callback_secret: str = Field(
        default="local-dd-agent-callback",
        validation_alias="AGENT_CALLBACK_SECRET",
        description="Must match backend AGENT_CALLBACK_SECRET for /internal/agent-runs callbacks.",
    )
    session_history_enabled: bool = Field(
        default=True,
        validation_alias="DD_SESSION_HISTORY_ENABLED",
        description="Persist each POST /runs execution as agent_service/sessions/<project>/<run>.json",
    )
    session_history_dir: str = Field(
        default="",
        validation_alias="DD_SESSION_HISTORY_DIR",
        description="Optional absolute path for session JSON files (default: <agent_service>/sessions).",
    )


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
