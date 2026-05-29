# ADR-0007: Engagement naming in API and database

## Status

Accepted (2026-05-29, updated)

## Context

The product domain object was originally named "Project" in the database while the public API used "Engagement". Dual naming added confusion and `AliasChoices` shims in DTOs.

## Decision

- **Public API, UI, ORM, and database** all use `engagement` / `engagement_id`.
- SQLAlchemy model: `Engagement` with `__tablename__ = "engagements"`.
- Access control: `EngagementAccess` / `engagement_access` table.
- Foreign keys on runs, reports, sessions use `engagement_id`.
- Alembic migration `001_rename_projects_to_engagements` renames legacy tables/columns; `ensure_schema_patches` performs the same renames on startup for existing SQLite dev databases.

## Consequences

- No `project_id` JSON aliases on API responses.
- Internal module names use `engagement_*` (not `project_*`).
- Developers with old local SQLite files get automatic table renames on startup, or may delete `.harness_project/data/platform/harness_platform.db` (or legacy `dd_platform.db` in the same directory) for a clean schema.
