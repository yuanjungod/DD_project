# Due Diligence Platform

An MVP due diligence platform with:

- React frontend workbench.
- FastAPI backend for projects, resources, runs, and reports.
- AgentScope-oriented Python agent service with configurable agents, tools, prompts, and workflows.

## Layout

```text
backend/        FastAPI application
agent_service/  AgentScope workflow service (+ configs/scenario_templates/, agent_templates.yaml, skills/, tools.yaml)
frontend/       React + Vite workbench
shared/         Shared JSON schemas and example payloads
docs/           Architecture, agent flow, configuration schema
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

Writable runtime data defaults to `data/dd_store/` from the repository root:

- SQLite: `data/dd_store/platform/dd_platform.db` (set `DATABASE_URL` to use PostgreSQL or another explicit database).
- Project resources/uploads: `data/dd_store/projects/<project_id>/...`.
- Platform uploads/config overlays: `data/dd_store/platform/...`.
- Agent run sessions and per-step outputs: `data/dd_store/agent_service/sessions/...`.

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
4. Apply a published scenario to a specific company.
5. Add project resources.
6. Start a due diligence run from the project detail page.
7. Review agent steps, per-step output folders, report, workflow snapshot, and run history.

After upgrading from a build that used the removed Evidence model, reset local SQLite under `data/dd_store/platform/` (delete `dd_platform.db` and restart the backend) so `create_all` rebuilds the schema.
