# ADR-0007: Engagement in API, Project in database

## Status

Accepted (2026-05-29)

## Context

Renaming the SQLAlchemy `Project` table and all `project_id` foreign keys to `Engagement` would touch migrations, queries, and filesystem helpers across backend and agent_service.

## Decision

- Keep **`Project` model and `project_id` columns** in the database for MVP stability.
- Expose **`engagement_id`** in all public JSON via Pydantic field aliases.
- Defer a full DB rename until migration tooling and downtime budget are available.

## Consequences

- Internal code continues to use `project_id`; API consumers see `engagement_id`.
- New code should prefer "engagement" in user-facing strings and route names.
- A future migration can rename tables/columns with a single Alembic revision.
