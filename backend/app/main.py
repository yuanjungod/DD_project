from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    configs,
    internal_agent,
    library_uploads,
    project_agent_overrides,
    project_resource_configs,
    projects,
    reports,
    resources,
    runs,
    scenarios,
    uploads,
)
from app.core.auth import seed_default_users
from app.core.config import settings
from app.core.config_seed import seed_configuration_catalog
from app.core.database import Base, SessionLocal, engine, ensure_schema_patches
from app.models.entities import Project
from app.services.company_identity import company_key_from_name, normalize_application_id


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    ensure_schema_patches(engine)
    with SessionLocal() as db:
        seed_default_users(db)
        _backfill_project_identity(db)
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
    app.include_router(projects.router)
    app.include_router(project_resource_configs.router)
    app.include_router(project_agent_overrides.router)
    app.include_router(resources.router)
    app.include_router(uploads.router)
    app.include_router(runs.router)
    app.include_router(reports.router)
    app.include_router(scenarios.router)
    app.include_router(internal_agent.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _backfill_project_identity(db) -> None:
    changed = False
    for project in db.query(Project).all():
        cfg = project.company_config if isinstance(project.company_config, dict) else {}
        target = cfg.get("target_company") if isinstance(cfg.get("target_company"), dict) else {}
        name = str(target.get("name") or project.name or "company")
        key = company_key_from_name(name)
        if project.company_key != key:
            project.company_key = key
            changed = True
        if not getattr(project, "application_id", None) or project.application_id in ("default", ""):
            project.application_id = f"app-{project.id.replace('proj_', '')[:20]}"
            changed = True
        if not getattr(project, "version", None) or project.version < 1:
            project.version = 1
            changed = True
    if changed:
        db.commit()


app = create_app()
