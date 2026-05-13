from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Due Diligence Backend"
    database_url: str = "sqlite:///./dd_platform.db"
    agent_service_url: str = "http://127.0.0.1:8001"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
