# Deployment

Single-node Docker Compose deployment with a **shared filesystem** for `.dd_project/` and `agent_service/skills/`. See [ADR-0006](../docs/adr/0006-docker-shared-filesystem.md).

## Prerequisites

- Docker and Docker Compose
- Copy [.env.example](../.env.example) to `.env` and set production secrets when `ENV=production`

## Quick start (Postgres only)

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg2://dd_user:dd_password@localhost:5432/dd_platform
# Run backend, agent, and frontend locally (see README)
```

## Full stack (Compose)

```bash
cp .env.example .env
docker compose --profile full up --build
```

Services (profile `full`):

| Service | Port | Notes |
| --- | --- | --- |
| postgres | 5432 | Optional; set `DATABASE_URL` for backend |
| agent | 8011 | AgentScope workflow service |
| backend | 8010 | FastAPI platform API |
| frontend | 5173 | Static preview via nginx (production build) |

Shared volume `dd_runtime` mounts at `/data` inside containers. Set `DD_DATA_ROOT=/data` so backend and agent_service share session output paths.

## Environment (production checklist)

- `ENV=production`
- `AUTH_SECRET_KEY` — non-default JWT secret
- `AGENT_API_KEY` — shared between backend and agent_service
- `AGENT_CALLBACK_SECRET` — progress callback HMAC
- `DD_SEED_DEFAULT_USERS=false` — disable default passwords
- Model provider URLs via `DD_MODEL_BASE_URL` / `DD_MODEL_API_KEY` on agent host

## Health checks

- Backend: `GET http://localhost:8010/health`
- Agent: `GET http://localhost:8011/health` (no API key required)

## Limitations (MVP)

- Runs are **blocking HTTP** from backend to agent (no job queue yet).
- Backend reads agent step folders from shared disk; multi-node K8s needs object storage follow-up.
- Workflow graph execution is **linear only** ([ADR-0005](../docs/adr/0005-linear-workflow-graph.md)).
