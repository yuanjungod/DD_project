from __future__ import annotations

import sys
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.harness_paths import default_data_root_relative, platform_db_path, resolve_repo_path

_ENV_FILE = _REPO_ROOT / ".env"
_DEV_AUTH_SECRET = "dev-secret-change-me"
_DEV_CALLBACK_SECRET = "local-harness-agent-callback"
_DEV_AGENT_API_KEY = "local-harness-agent-api-key"


def _resolve_sqlite_url(raw_url: str) -> str:
    if raw_url == "sqlite:///:memory:" or not raw_url.startswith("sqlite:///"):
        return raw_url
    raw_path = raw_url.removeprefix("sqlite:///")
    db_path = Path(raw_path).expanduser()
    if not db_path.is_absolute():
        db_path = _REPO_ROOT / db_path
    return f"sqlite:///{db_path.resolve().as_posix()}"


class Settings(BaseSettings):
    app_name: str = "Harness Backend"
    env: str = Field(default="development", validation_alias="ENV")
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    agent_service_url: str = "http://127.0.0.1:8011"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    auth_secret_key: str = _DEV_AUTH_SECRET
    token_ttl_seconds: int = 60 * 60 * 8
    agent_callback_secret: str = _DEV_CALLBACK_SECRET
    agent_api_key: str = Field(default=_DEV_AGENT_API_KEY, validation_alias="AGENT_API_KEY")
    filesystem_data_root: str = Field(
        default_factory=lambda: default_data_root_relative(_REPO_ROOT),
        validation_alias=AliasChoices("HARNESS_DATA_ROOT", "DD_DATA_ROOT"),
    )
    seed_default_users: bool = Field(
        default=True,
        validation_alias=AliasChoices("HARNESS_SEED_DEFAULT_USERS", "DD_SEED_DEFAULT_USERS"),
    )
    default_users_config_path: str = Field(
        default="",
        validation_alias=AliasChoices("HARNESS_DEFAULT_USERS_CONFIG", "DD_DEFAULT_USERS_CONFIG"),
    )

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.env.strip().lower() == "production"

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Settings:
        if not self.is_production:
            return self
        if self.auth_secret_key == _DEV_AUTH_SECRET:
            raise ValueError("AUTH_SECRET_KEY must be set to a non-default value when ENV=production")
        if self.agent_callback_secret == _DEV_CALLBACK_SECRET:
            raise ValueError("AGENT_CALLBACK_SECRET must be set to a non-default value when ENV=production")
        if self.agent_api_key == _DEV_AGENT_API_KEY:
            raise ValueError("AGENT_API_KEY must be set to a non-default value when ENV=production")
        return self

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT

    @property
    def resolved_data_root(self) -> Path:
        return resolve_repo_path(self.repo_root, self.filesystem_data_root)

    @property
    def resolved_database_url(self) -> str:
        configured = self.database_url.strip()
        if configured:
            return _resolve_sqlite_url(configured)
        db_path = platform_db_path(self.resolved_data_root)
        return f"sqlite:///{db_path.as_posix()}"


settings = Settings()
