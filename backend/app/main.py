from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.core.auth import seed_default_users
from app.core.config import settings
from app.core.config_seed import seed_configuration_catalog
from app.core.database import Base, SessionLocal, engine, ensure_schema_patches
from app.models.entities import Engagement
from app.services.company_identity import company_key_from_name, normalize_application_id
from shared.instance_config import resolve_subject_name


def create_app() -> FastAPI:
    ensure_schema_patches(engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)
        _backfill_engagement_identity(db)
    seed_configuration_catalog()
    app = FastAPI(title=settings.app_name, version="0.1.0")
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
    changed = False
    for engagement in db.query(Engagement).all():
        cfg = engagement.company_config if isinstance(engagement.company_config, dict) else {}
        name = resolve_subject_name(cfg) or str(engagement.name or "company")
        key = company_key_from_name(name)
        if engagement.company_key != key:
            engagement.company_key = key
            changed = True
        if not getattr(engagement, "application_id", None) or engagement.application_id in ("default", ""):
            short_id = engagement.id
            if short_id.startswith("eng_"):
                short_id = short_id.replace("eng_", "", 1)
            engagement.application_id = f"app-{short_id[:20]}"
            changed = True
        if not getattr(engagement, "version", None) or engagement.version < 1:
            engagement.version = 1
            changed = True
    if changed:
        db.commit()


app = create_app()
