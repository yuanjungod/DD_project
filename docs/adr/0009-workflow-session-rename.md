# ADR-0009: WorkflowSession rename (Phase D)

## Status

Accepted

## Context

Phase B–C introduced `WorkflowEngine` and `.harness_project/` runtime storage. Product sessions were still named **DiligenceSession** / `diligence_session_id`, which reads as due-diligence-specific even though sessions are generic workflow run containers.

## Decision

Adopt **`WorkflowSession`** as the canonical name:

| Layer | New | Legacy (compat) |
|-------|-----|-----------------|
| ORM / table | `WorkflowSession` / `workflow_sessions` | read old table name via startup patch + Alembic `002` |
| API route | `GET /engagements/{id}/workflow-sessions` | `GET .../diligence-sessions` (deprecated alias) |
| Request field | `workflow_session_id` | `diligence_session_id` (accepted on read/write) |
| Session JSON on disk | writes both fields | reads either field |

Disk path layout under `.harness_project/users/.../sessions/` is unchanged.

## Consequences

- Frontend and OpenAPI use WorkflowSession naming; legacy clients may keep sending `diligence_session_id` one release.
- Phase E (`InstanceConfig` / `company_config` generalization) remains separate.
