from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Due Diligence Backend"
    database_url: str = "sqlite:///./dd_platform.db"
    agent_service_url: str = "http://127.0.0.1:8011"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    auth_secret_key: str = "dev-secret-change-me"
    token_ttl_seconds: int = 60 * 60 * 8
    # Verified by POST /internal/agent-runs/*/progress — must match agent service AGENT_CALLBACK_SECRET
    agent_callback_secret: str = "local-dd-agent-callback"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
