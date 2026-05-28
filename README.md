# Due Diligence Platform

An MVP due diligence platform with:

- React frontend workbench.
- FastAPI backend for engagements, resources, runs, and reports.
- AgentScope-oriented Python agent service with configurable agents, tools, prompts, and workflows.

## Terminology

- `Workflow Template` (formerly `Scenario`): defines **how** the diligence is executed (graph/stages/agent composition).
- `Engagement` (formerly `Project`): defines **what/who** is being analyzed for one business instance (company, app id, version, resources, runs).

In API and UI, `engagement` is the runtime/business object and `workflow template` is the reusable process template.

## Layout

```text
backend/        FastAPI application
agent_service/  AgentScope workflow service (+ configs/tools.yaml, skills/)
catalog/        Global agent library (catalog/agents/) and built-in workflow template folders (catalog/scenarios/)
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
  scenarios/
    {scenario_id}/
      scenario.yaml                     # Workflow metadata + graph
      agents/
        {agent_id}.yaml                 # Scenario-local agent copies
  resource_configs/
    {resource_id}.yaml                  # Built-in platform resource connectors
  default_users.yaml                    # Development seed users
```

### `.dd_project/` (runtime/engagement state)

```text
.dd_project/
  projects/
    {engagement_id}/
      meta/
        agent_overrides.json            # Engagement-scoped Agent override manifest
      shared/
        resources/manifest.json         # Engagement resource metadata
        resource_configs/*.yaml         # Engagement resource config overrides
        uploads/{file_id}               # Engagement-shared uploaded binaries
      users/{user_id}/sessions/{session_id}/
        runs/{scenario_id}/{run_id}.json
        runs/{scenario_id}/outputs/{run_id}_outputs/{step}_{agent}/
  data/
    platform/                           # Platform-level DB/config/upload storage
  channels/                             # Reserved for channel mapping expansion
  users/                                # Reserved for user-global expansion
```

## Documentation

- **[docs/architecture.md](docs/architecture.md)** — services, async run lifecycle, incremental callbacks, ports, Vite `/api` proxy.
- **[docs/agent_flow.md](docs/agent_flow.md)** — agents, workflow snapshots, `run_id` handoff, observability.
- **[docs/config_schema.md](docs/config_schema.md)** — JSON shapes, environment variables, UTC timestamps for runs.

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

Writable runtime data defaults to `.dd_project/data/` from the repository root:

- SQLite: `.dd_project/data/platform/dd_platform.db` (set `DATABASE_URL` to use PostgreSQL or another explicit database).
- Engagement resources: `.dd_project/projects/<engagement_id>/shared/resources` + `.dd_project/projects/<engagement_id>/shared/resource_configs`.
- Engagement uploads (binary blobs): `.dd_project/projects/<engagement_id>/shared/uploads/<file_id>`.
- Engagement-local copied skills: `.dd_project/projects/<engagement_id>/shared/skills/<directory_name>`.
- Platform uploads (binary blobs): `.dd_project/data/platform/uploads/<file_id>`.
- Platform upload manifest: `.dd_project/data/platform/uploads_manifest.json`.
- Agent run sessions and per-step outputs: `.dd_project/projects/<engagement_id>/users/<user_id>/sessions/<session_id>/runs/<workflow_template_id>/...`.
- Engagement runtime config home: `.dd_project/projects/<engagement_id>/meta/agent_overrides.json`.

Set `DD_DATA_ROOT` to move all writable file data together.

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

After upgrading from a build that used the removed Evidence model, reset local SQLite under `.dd_project/data/platform/` (delete `dd_platform.db` and restart the backend) so `create_all` rebuilds the schema.
