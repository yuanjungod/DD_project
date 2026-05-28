from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATA_ROOT = ".dd_project/data"
_ENV_FILE = _REPO_ROOT / ".env"


def _resolve_repo_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path.resolve()


class AgentSettings(BaseSettings):
    """Runtime config for the standalone agent service."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

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
        description="Persist each POST /runs execution under .dd_project/users/<user>/<workflow>/<engagement>/sessions/<session>/runs/<workflow>/<run>.json",
    )
    session_history_dir: str = Field(
        default="",
        validation_alias="DD_SESSION_HISTORY_DIR",
        description="Deprecated legacy override for session JSON root.",
    )
    data_root: str = Field(
        default=_DEFAULT_DATA_ROOT,
        validation_alias=AliasChoices("DD_DATA_ROOT", "FILESYSTEM_DATA_ROOT"),
        description="Shared writable data root used when DD_SESSION_HISTORY_DIR is not set.",
    )

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT

    @property
    def resolved_data_root(self) -> Path:
        return _resolve_repo_path(self.data_root)

    @property
    def resolved_session_history_dir(self) -> Path:
        """Deprecated legacy root; runtime uses repository .dd_project/users/<user>/<workflow>/<engagement>/... by default."""
        configured = self.session_history_dir.strip()
        if configured:
            return _resolve_repo_path(configured)
        return self.repo_root / ".dd_project"


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
