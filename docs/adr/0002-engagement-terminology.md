# ADR-0002: Engagement vs Project naming

## Status

Accepted (2026-05-29)

## Context

The product domain object was originally named "Project" in the database and early APIs. The UI and public API now use "Engagement" to reflect a due diligence business instance (company, application, version, resources).

## Decision

- **Public API and UI** use `engagement` / `engagement_id`.
- **Database and internal Python modules** may retain `Project` / `project_id` until a dedicated migration is justified.
- **Workflow templates** replace the former "scenario" terminology in API routes and YAML (`workflow_template_id`).

## Consequences

- DTOs expose `engagement_id` via Pydantic aliases while SQLAlchemy models stay `Project`.
- Legacy module names (`scenarios.py`, `scenario_layout.py`) remain as compatibility shims; rename incrementally.
- Documentation must use Engagement / Workflow Template consistently in user-facing sections.
