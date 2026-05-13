from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, configs, evidence, internal_agent, projects, reports, resources, runs, scenarios
from app.core.auth import seed_default_users
from app.core.config import settings
from app.core.config_seed import seed_configuration_catalog
from app.core.database import Base, SessionLocal, engine


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)
        seed_configuration_catalog(db)
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
    app.include_router(projects.router)
    app.include_router(resources.router)
    app.include_router(runs.router)
    app.include_router(evidence.router)
    app.include_router(reports.router)
    app.include_router(scenarios.router)
    app.include_router(internal_agent.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
