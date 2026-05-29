# ADR-0002: Engagement vs Project naming

## Status

Accepted (2026-05-29, superseded by ADR-0007 full rename)

## Context

The product domain object was originally named "Project" in the database and early APIs. The UI and public API now use "Engagement" to reflect a due diligence business instance.

## Decision

- **Public API, UI, ORM, and database** use `engagement` / `engagement_id` exclusively.
- **Workflow templates** replace the former "scenario" terminology (`workflow_template_id`).
- Legacy module names (`scenarios.py`, `project_*` services) have been renamed.

## Consequences

- See [ADR-0007](0007-engagement-api-project-db.md) for database table/column renames.
- Documentation uses Engagement / Workflow Template consistently.
