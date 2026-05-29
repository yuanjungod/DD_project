from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_

from app.api import (
    auth,
    configs,
    engagement_agent_overrides,
    engagement_resource_configs,
    engagements,
    internal_agent,
    library_uploads,
    published_workflow_templates,
    reports,
    resources,
    runs,
    uploads,
)
from app.api.exception_handlers import register_exception_handlers
from app.core.auth import seed_default_users
from app.core.config import settings
from app.core.config_seed import seed_configuration_catalog
from app.core.database import Base, SessionLocal, engine, ensure_schema_patches
from app.models.entities import Engagement
from app.services.subject_identity import subject_key_from_name
from app.services.http_client import close_async_http_client
from shared.instance_config import resolve_subject_name


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_async_http_client()


def create_app() -> FastAPI:
    ensure_schema_patches(engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)
        _backfill_engagement_identity(db)
    seed_configuration_catalog()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(configs.router)
    app.include_router(library_uploads.router)
    app.include_router(engagements.router)
    app.include_router(engagement_resource_configs.router)
    app.include_router(engagement_agent_overrides.router)
    app.include_router(resources.router)
    app.include_router(uploads.router)
    app.include_router(runs.router)
    app.include_router(reports.router)
    app.include_router(published_workflow_templates.router)
    app.include_router(internal_agent.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _backfill_engagement_identity(db) -> None:
    if not settings.backfill_engagement_identity_on_startup:
        return
    candidates = (
        db.query(Engagement)
        .filter(
            or_(
                Engagement.application_id.in_(["", "default"]),
                Engagement.version < 1,
            )
        )
        .all()
    )
    if not candidates:
        return
    changed = False
    for engagement in candidates:
        cfg = engagement.instance_config if isinstance(engagement.instance_config, dict) else {}
        name = resolve_subject_name(cfg) or str(engagement.name or "subject")
        key = subject_key_from_name(name)
        if engagement.subject_key != key:
            engagement.subject_key = key
            changed = True
        if not engagement.application_id or engagement.application_id in ("default", ""):
            short_id = engagement.id
            if short_id.startswith("eng_"):
                short_id = short_id.replace("eng_", "", 1)
            engagement.application_id = f"app-{short_id[:20]}"
            changed = True
        if not engagement.version or engagement.version < 1:
            engagement.version = 1
            changed = True
    if changed:
        db.commit()


app = create_app()
