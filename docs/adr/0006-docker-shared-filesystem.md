# ADR-0006: Single-node Docker with shared filesystem

## Status

Accepted (2026-05-29)

## Context

The backend writes skill packages and tool configs into `agent_service/` paths and reads agent step `output_dir` from disk. Both services default to repository-relative `.dd_project/`.

## Decision

- **MVP deployment target**: single-node Docker Compose with a **shared volume** mounted at `/data` (or repo root) for `.dd_project/` and `agent_service/skills/`.
- Kubernetes/multi-node deployment requires follow-up work (object storage, agent-side APIs for config writes).
- `docker-compose.yml` provides Postgres plus optional full-stack services documented in `docs/deployment.md`.

## Consequences

- Fast local and demo deployments with one `docker compose up`.
- Production at scale needs ADR follow-up for filesystem decoupling.
- `DD_DATA_ROOT` must point at the shared mount in containerized runs.
