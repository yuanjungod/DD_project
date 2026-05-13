# Due Diligence Platform

An MVP due diligence platform with:

- React frontend workbench.
- FastAPI backend for projects, resources, runs, evidence, and reports.
- AgentScope-oriented Python agent service with configurable agents, tools, prompts, and workflows.

## Layout

```text
backend/        FastAPI application
agent_service/  AgentScope workflow service
frontend/       React + Vite workbench
shared/         Shared JSON schemas and example payloads
docs/           Architecture and configuration documentation
```

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

The backend defaults to SQLite at `backend/dd_platform.db`. Set `DATABASE_URL` to use PostgreSQL.

## MVP Flow

Default users are created on backend startup:

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
7. Review agent steps, evidence, report, workflow snapshot, and run history.
