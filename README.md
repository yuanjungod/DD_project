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
uvicorn agent_service.api.main:app --reload --port 8001
```

```bash
cd backend
../.venv/bin/pip install -r requirements.txt
../.venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

The backend defaults to SQLite at `backend/dd_platform.db`. Set `DATABASE_URL` to use PostgreSQL.

## MVP Flow

1. Create a project in the frontend.
2. Add company scope and resources.
3. Start a due diligence run.
4. Watch agent steps complete.
5. Review evidence and the generated report.
