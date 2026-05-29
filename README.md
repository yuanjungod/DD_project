# Harness_Project (Agent Orchestration Platform)

An MVP **Agent orchestration platform** (Harness) with due-diligence and other workflow templates:

- React frontend workbench.
- FastAPI backend for engagements, resources, runs, and reports.
- AgentScope-oriented Python agent service with configurable agents, tools, prompts, and DAG workflows.

## Terminology

- `Workflow Template`: defines **how** the diligence is executed (graph/stages/agent composition).
- `Engagement`: defines **what/who** is being analyzed for one business instance (company, app id, version, resources, runs).

See [CONTEXT.md](CONTEXT.md) and [docs/adr/README.md](docs/adr/README.md) for domain vocabulary and architecture decisions.

## Layout

```text
backend/        FastAPI application
agent_service/  AgentScope workflow service (+ configs/tools.yaml, skills/)
catalog/        Global agent library (catalog/agents/) and built-in workflow template folders (catalog/workflow_templates/)
frontend/       React + Vite workbench
shared/         Shared JSON schemas and example payloads
docs/           Architecture, agent flow, configuration schema
```

## Config Storage Layout

### `catalog/` (built-in templates, versioned with repo)

```text
catalog/
  agents/
    {agent_id}.yaml                     # Global Agent templates
  workflow_templates/
    {workflow_template_id}/
      workflow_template.yaml            # Workflow metadata + graph
      agents/
        {agent_id}.yaml                 # Workflow-template-local agent copies
  resource_configs/
    {resource_id}.yaml                  # Built-in platform resource connectors
  default_users.yaml                    # Development seed users
```

### `.harness_project/` (runtime/engagement state)

Preferred runtime root. Legacy installs may still use `.dd_project/` (see ADR-0008).

```text
.harness_project/
  engagement_index.json
  users/
    {user_id}/
      workflows/
        {workflow_template_id}/         # User-owned workflow template drafts
          workflow_template.yaml
          agents/
        {workflow_template_id}/
          {engagement_id}/
            meta/agent_overrides.json
            shared/
              resources/manifest.json
              resource_configs/*.yaml
              uploads/{file_id}
              skills/{directory_name}/
            sessions/{session_id}/runs/
              {run_id}.json
              outputs/{run_id}_outputs/{step}_{agent}/
  data/platform/                        # SQLite, platform overlays, library uploads
  channels/                             # Reserved for channel mapping expansion
```

See **[docs/harness_runtime_storage.md](docs/harness_runtime_storage.md)** for the full runtime storage guide. Legacy **`.dd_project/`** installs keep working until you migrate (ADR-0008).

### Migrating from `.dd_project/`

```bash
python scripts/migrate_dd_project_to_harness_project.py --dry-run
python scripts/migrate_dd_project_to_harness_project.py
```

The script copies the runtime tree into `.harness_project/` and renames `dd_platform.db` when safe. Use `--merge` if `.harness_project/` already exists.

## Documentation

- **[CONTEXT.md](CONTEXT.md)** — domain vocabulary (skill package, workflow snapshot, tool config).
- **[docs/architecture.md](docs/architecture.md)** — services, async run lifecycle, incremental callbacks, ports, Vite `/api` proxy.
- **[docs/agent_flow.md](docs/agent_flow.md)** — agents, workflow snapshots, `run_id` handoff, observability.
- **[docs/config_schema.md](docs/config_schema.md)** — JSON shapes, environment variables, UTC timestamps for runs.
- **[docs/deployment.md](docs/deployment.md)** — Docker Compose and environment setup.
- **[docs/adr/README.md](docs/adr/README.md)** — architecture decision records.
- **[catalog/README.md](catalog/README.md)** — built-in template catalog layout.

Copy **[.env.example](.env.example)** to `.env` at the repository root for local configuration.

## Local Development

Start the services in separate terminals:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r agent_service/requirements.txt
uvicorn agent_service.api.main:app --reload --port 8011
```

```bash
cd backend
../.venv/bin/pip install -r requirements.txt
../.venv/bin/uvicorn app.main:app --reload --port 8010
```

```bash
cd frontend
npm install
npm run dev
```

开发模式下请求默认走 **`http://127.0.0.1:5173/api/*`**，由 Vite **代理到** `http://127.0.0.1:8010`，避免浏览器直连跨域端口失败。若要改后端地址，可在启动前设置 **`VITE_DEV_PROXY_TARGET`**（仅 dev 代理目标），或设置 **`VITE_API_BASE_URL`** 为完整后端 URL（将跳过 `/api` 代理）。

Writable runtime data defaults to `.harness_project/data/` from the repository root (legacy: `.dd_project/data/`):

- SQLite: `.harness_project/data/platform/harness_platform.db` (set `DATABASE_URL` to use PostgreSQL or another explicit database).
- Engagement resources: `.harness_project/users/<user_id>/workflows/<workflow_template_id>/<engagement_id>/shared/resources` + `.../shared/resource_configs`.
- Engagement uploads (binary blobs): `.harness_project/users/<user_id>/workflows/<workflow_template_id>/<engagement_id>/shared/uploads/<file_id>`.
- Engagement-local copied skills: `.harness_project/users/<user_id>/workflows/<workflow_template_id>/<engagement_id>/shared/skills/<directory_name>`.
- Platform uploads (binary blobs): `.harness_project/data/platform/uploads/<file_id>`.
- Platform upload manifest: `.harness_project/data/platform/uploads_manifest.json`.
- Agent run sessions and per-step outputs: `.harness_project/users/<user_id>/workflows/<workflow_template_id>/<engagement_id>/sessions/<session_id>/runs/<run_id>.json` and `.../runs/outputs/{run_id}_outputs/...`.
- Engagement runtime config home: `.harness_project/users/<user_id>/workflows/<workflow_template_id>/<engagement_id>/meta/agent_overrides.json`.

Set `HARNESS_DATA_ROOT` to move all writable file data together (legacy alias: `DD_DATA_ROOT`).

## Docker (optional)

```bash
cp .env.example .env
docker compose --profile full up --build
```

See **[docs/deployment.md](docs/deployment.md)** for production checklist and shared-volume layout.

## MVP Flow

Development users are loaded from `catalog/default_users.yaml` and created on backend startup only when the users table is empty:

- Admin: `admin@example.com` / `admin123`
- Analyst: `analyst@example.com` / `analyst123`
- Viewer: `viewer@example.com` / `viewer123`

MVP flow:

1. Log in.
2. Configure Anthropic-style skill packages, executable tools, data resources, agent templates, and workflow templates as an admin.
3. Publish a workflow template.
4. Apply a published workflow template to a specific company engagement.
5. Add engagement resources.
6. Start a due diligence run from the engagement detail page.
7. Review agent steps, per-step output folders, report, workflow snapshot, and run history.

After upgrading schema, reset local SQLite under `.harness_project/data/platform/` (delete `harness_platform.db` or legacy `dd_platform.db` and restart the backend) if automatic migration does not apply.

## Tests

```bash
# Shared workflow graph tests
python -m unittest shared/test_workflow_graph.py shared/test_harness_paths.py

# Agent tool registry tests
python -m unittest agent_service/tools/test_registry.py

# Backend tests (from repo root)
python -m unittest discover -s backend/tests -p 'test_*.py'
```
