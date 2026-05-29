# ADR-0006: Single-node Docker with shared filesystem

## Status

Accepted (2026-05-29)

## Context

The backend writes skill packages and tool configs into `agent_service/` paths and reads agent step `output_dir` from disk. Both services default to repository-relative **`.harness_project/`** (via `HARNESS_DATA_ROOT`; historically `.dd_project/` — see ADR-0008).

## Decision

- **MVP deployment target**: single-node Docker Compose with a **shared volume** mounted at `/data` (or repo root) for `.harness_project/` and `agent_service/skills/`.
- Kubernetes/multi-node deployment requires follow-up work (object storage, agent-side APIs for config writes).
- `docker-compose.yml` provides Postgres plus optional full-stack services documented in `docs/deployment.md`.

## Consequences

- Fast local and demo deployments with one `docker compose up`.
- Production at scale needs ADR follow-up for filesystem decoupling.
- `HARNESS_DATA_ROOT` must point at the shared mount in containerized runs.
