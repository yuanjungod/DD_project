from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.harness_paths import default_data_root_relative, resolve_repo_path

_ENV_FILE = _REPO_ROOT / ".env"
_DEV_AGENT_API_KEY = "local-harness-agent-api-key"
_DEV_CALLBACK_SECRET = "local-harness-agent-callback"


class AgentSettings(BaseSettings):
    """Runtime config for the standalone agent service."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="development", validation_alias="ENV")
    agent_api_key: str = Field(
        default=_DEV_AGENT_API_KEY,
        validation_alias="AGENT_API_KEY",
        description="Required on all endpoints except /health when set.",
    )
    platform_callback_base_url: str = Field(
        default="http://127.0.0.1:8010",
        validation_alias="PLATFORM_CALLBACK_BASE_URL",
        description="Backend base URL for incremental progress. Override in Docker (e.g. http://backend:8010) or set empty to disable.",
    )
    agent_callback_secret: str = Field(
        default=_DEV_CALLBACK_SECRET,
        validation_alias="AGENT_CALLBACK_SECRET",
        description="Must match backend AGENT_CALLBACK_SECRET for /internal/agent-runs callbacks.",
    )
    session_history_enabled: bool = Field(
        default=True,
        validation_alias="HARNESS_SESSION_HISTORY_ENABLED",
        description="Persist each POST /runs execution under .harness_project/users/<user>/workflows/<workflow>/<engagement>/sessions/<session>/runs/<run>.json",
    )
    data_root: str = Field(
        default_factory=lambda: default_data_root_relative(_REPO_ROOT),
        validation_alias="HARNESS_DATA_ROOT",
        description="Shared writable data root for agent runtime artifacts.",
    )

    @property
    def is_production(self) -> bool:
        return self.env.strip().lower() == "production"

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> AgentSettings:
        if not self.is_production:
            return self
        if self.agent_api_key == _DEV_AGENT_API_KEY:
            raise ValueError("AGENT_API_KEY must be set to a non-default value when ENV=production")
        if self.agent_callback_secret == _DEV_CALLBACK_SECRET:
            raise ValueError("AGENT_CALLBACK_SECRET must be set to a non-default value when ENV=production")
        return self

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT

    @property
    def resolved_data_root(self) -> Path:
        return resolve_repo_path(self.repo_root, self.data_root)


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
