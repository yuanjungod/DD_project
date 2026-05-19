from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DATA_ROOT = "data/dd_store"
_ENV_FILE = _REPO_ROOT / ".env"


def _resolve_repo_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path.resolve()


def _resolve_sqlite_url(raw_url: str) -> str:
    if raw_url == "sqlite:///:memory:" or not raw_url.startswith("sqlite:///"):
        return raw_url
    raw_path = raw_url.removeprefix("sqlite:///")
    db_path = Path(raw_path).expanduser()
    if not db_path.is_absolute():
        db_path = _REPO_ROOT / db_path
    return f"sqlite:///{db_path.resolve().as_posix()}"


class Settings(BaseSettings):
    app_name: str = "Due Diligence Backend"
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    agent_service_url: str = "http://127.0.0.1:8011"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    auth_secret_key: str = "dev-secret-change-me"
    token_ttl_seconds: int = 60 * 60 * 8
    # Verified by POST /internal/agent-runs/*/progress — must match agent service AGENT_CALLBACK_SECRET
    agent_callback_secret: str = "local-dd-agent-callback"
    # Project + platform connector resources (YAML/JSON), not SQLite tables.
    filesystem_data_root: str = Field(
        default=_DEFAULT_DATA_ROOT,
        validation_alias=AliasChoices("DD_DATA_ROOT", "FILESYSTEM_DATA_ROOT"),
    )
    seed_default_users: bool = Field(default=True, validation_alias="DD_SEED_DEFAULT_USERS")
    default_users_config_path: str = Field(default="", validation_alias="DD_DEFAULT_USERS_CONFIG")

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT

    @property
    def resolved_data_root(self) -> Path:
        return _resolve_repo_path(self.filesystem_data_root)

    @property
    def resolved_database_url(self) -> str:
        configured = self.database_url.strip()
        if configured:
            return _resolve_sqlite_url(configured)
        db_path = self.resolved_data_root / "platform" / "dd_platform.db"
        return f"sqlite:///{db_path.as_posix()}"


settings = Settings()
