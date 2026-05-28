# Due Diligence Platform Architecture

This project is a due diligence workspace with three runtime services:

- `frontend`: React workbench for configuring projects, monitoring agent runs, and reviewing reports.
- `backend`: FastAPI API for projects, resources, runs, reports, OAuth-style JWT authentication, and an internal webhook for incremental run progress from the agent process.
- `agent_service`: AgentScope-based orchestration service that runs configurable workflows; tool implementations can be deterministic mocks or pluggable integrations.

Generic workflow configuration stays decoupled from company-specific **project configuration** persisted with each `Project`.

## Runtime Flow

```mermaid
flowchart LR
  User[User] --> Frontend[Frontend]
  Frontend --> Backend[Backend_API]
  Backend --> DB[(PostgreSQL_or_SQLite)]
  Backend -->|"long_running_POST"| AgentService[Agent_Service]
  AgentService -->|"optional_progress"| InternalAPI[Backend_internal_/internal/agent-runs]
  InternalAPI --> DB
```

For local development, typical ports are the frontend dev server on **`5173`**, **`backend` on `8010`**, and **`agent_service` on `8011`** (README + code defaults). Override ports and URLs with environment variables (**see docs/config_schema.md**).

The browser usually talks to the backend through the Vite dev **`/api` proxy** (same origin as the UI) so API calls do not depend on cross-origin CORS during `npm run dev`.

## Run lifecycle (high level)

1. The user starts a run from the backend **POST `/projects/{project_id}/runs`**. The backend inserts an `AgentRun` row with status **`running`** and returns immediately.
2. A background task (thread pool) calls **agent_service POST `/runs`**, passing the immutable **workflow snapshot**, company config, and a **client-allocated `run_id`** so the agent result lines up with the pending row.
3. While the workflow executes, **agent_service** may **POST** step snapshots to **Backend `POST /internal/agent-runs/{run_id}/progress`** (shared secret header). This is optional from a product perspective but enabled by default when `PLATFORM_CALLBACK_BASE_URL` points at the backend so the UI can poll and show incremental steps.
4. When the agent HTTP call completes, the backend **finalizes** the run: status, `raw_result`, steps, and report are written. Finalization clears prior derived rows for that run id and re-attaches the authoritative payload from the agent response to avoid duplicate keys after incremental upserts.
5. The frontend **polls `GET /runs/{id}`** (and refreshes project-scoped lists) until the run reaches **`completed`** or **`failed`**.

## Core Concepts

### Generic Agent Configuration

Generic workflow configuration lives under `agent_service/configs`, `agent_service/prompts`, and `shared/schemas`.

It defines:

- Which agents exist.
- Which tools each agent may use.
- Which prompt each agent receives.
- Which output contract each agent must satisfy.
- How the workflow moves from planning to research, analysis, verification, and reporting.

### Company Project Configuration

Company-specific configuration is created through the backend and injected into an agent run.

It defines:

- Target company name, aliases, website, jurisdiction, industry, and keywords.
- Target company identity and optional **`workflow_template_id`** on `company_config` for catalog-backed workflows.
- Uploaded files, trusted sources, blocked sources, competitors, and optional notes.

### Source-Backed Outputs

Agent outputs are persisted as per-step handoff folders. Material claims should be grounded in tool results or prior agent handoff folders (`output_dir`, with README inlined in prompts).

## Services

### Backend

The backend owns durable entities:

- `Project`
- `Resource`
- `AgentRun`
- `AgentStep`
- `Report`

Configuration catalogs are file-first where practical. **Global agent templates** live under **`catalog/agents/{agent_id}.yaml`**. **Scenario folders** live under **`catalog/scenarios/{scenario_id}/`** (built-in) or **`.dd_project/data/scenarios/{scenario_id}/`** (user-created). Each scenario folder contains **`scenario.yaml`** plus an **`agents/`** subdirectory. Run/session/output runtime data is centralized under **`.dd_project/runs/{scenario_id}/{user_id}/{project_id}/`**. **`GET/POST/PATCH /workflow-templates`** read and write scenario folders, while **`GET/POST/PATCH /agent-templates`** read and write the global agent library.

For local development the backend defaults to SQLite at **`DD_DATA_ROOT/platform/dd_platform.db`** (`DD_DATA_ROOT` defaults to repo-root **`.dd_project/data`**). Set **`DATABASE_URL`** to use PostgreSQL or another explicit database.

### Agent Service

The agent service exposes HTTP endpoints for runs and executes a configurable workflow. Published templates resolve to an ordered agent graph at run time via the backend-built **workflow snapshot** (nodes may differ from the diagram below).

```mermaid
flowchart TD
  Start[POST_/runs] --> LoadConfig[Load_Snapshot_or_Default_Workflow]
  LoadConfig --> Coordinator[Coordinator]
  Coordinator --> Research[Research_Agents]
  Research --> Analyze[Analysis_Agents]
  Analyze --> Report[Reporter]
  Report --> Respond[HTTP_RunResult]
```

ReAct agents use AgentScope built-in file and code execution tools; optional platform catalog tools extend the same `ToolRegistry` interface when listed in `tools.yaml`.

### Frontend

The frontend provides a workbench for:

- Creating and editing company due diligence projects.
- Configuring resources and workflow template.
- Starting and monitoring runs (polling plus incremental UI when callbacks are configured).
- Reviewing agent steps and per-step output folders with correct **local timestamps** (**API emits UTC timestamps with `Z`** for runs).
- Reading the generated report.

## Development Layout

```text
DD_project/
  backend/
  agent_service/
  frontend/
  shared/
    schemas/
  docs/
```
