# Due Diligence Platform Architecture

This project is a due diligence workspace with three runtime services:

- `frontend`: React workbench for configuring projects, monitoring agent runs, browsing evidence, and reviewing reports.
- `backend`: FastAPI API for projects, resources, runs, evidence, reports, OAuth-style JWT authentication, and an internal webhook for incremental run progress from the agent process.
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
3. While the workflow executes, **agent_service** may **POST** step and evidence snapshots to **Backend `POST /internal/agent-runs/{run_id}/progress`** (shared secret header). This is optional from a product perspective but enabled by default when `PLATFORM_CALLBACK_BASE_URL` points at the backend so the UI can poll and show incremental steps and evidence.
4. When the agent HTTP call completes, the backend **finalizes** the run: status, `raw_result`, steps, evidence, and report are written. Finalization clears prior derived rows for that run id and re-attaches the authoritative payload from the agent response to avoid duplicate keys after incremental upserts.
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
- Due diligence scope, time range, focus areas, and report language, including optional **`workflow_template_id`** for catalog-backed workflows.
- Uploaded files, trusted sources, blocked sources, competitors, and optional notes.

### Evidence-First Reporting

Agent outputs are structured around evidence. Any conclusion that appears in a report should link back to one or more evidence records with source metadata and confidence.

## Services

### Backend

The backend owns durable entities:

- `Project`
- `Resource`
- `AgentRun`
- `AgentStep`
- `Evidence`
- `Report`

Configuration catalog entities in the **database** include **`SkillPackage`**, **`ToolConfig`**, and **`ResourceConfig`**. **Workflow templates** and the **agent definitions they use** live on disk under **`agent_service/configs/workflow_templates/{workflow_id}.yaml`** (one YAML per workflow: `workflow` metadata + embedded `agents`). On first boot, if that directory has no bundle files yet, the backend materializes them from **`workflows.yaml`** plus **`agent_templates.yaml`** (if present) or **`agents.yaml`** plus prompt files. **Ad-hoc / library agents** created only via **`POST /agent-templates`** are stored in **`workflow_templates/_shared_agents.yaml`**; **`GET /agent-templates`** returns the union of embedded and shared agents (later files override earlier on id conflicts). **`GET/POST/PATCH /workflow-templates`** read and write those bundle files.

For local development the backend defaults to SQLite (**path relative to backend working directory**, often `backend/dd_platform.db`). Set **`DATABASE_URL`** to use PostgreSQL for production-like deployments.

### Agent Service

The agent service exposes HTTP endpoints for runs and executes a configurable workflow. Published templates resolve to an ordered agent graph at run time via the backend-built **workflow snapshot** (nodes may differ from the diagram below).

```mermaid
flowchart TD
  Start[POST_/runs] --> LoadConfig[Load_Snapshot_or_Default_Workflow]
  LoadConfig --> Coordinator[Coordinator]
  Coordinator --> Research[Research_Agents]
  Research --> Analyze[Analysis_Agents]
  Analyze --> Verify[Verifier]
  Verify --> Report[Reporter]
  Report --> Respond[HTTP_RunResult]
```

The MVP ships with deterministic tool implementations so the platform can run without external API keys. Real search, document parsing, vector retrieval, and registry integrations can be added behind the same tool interfaces.

### Frontend

The frontend provides a workbench for:

- Creating and editing company due diligence projects.
- Configuring resources and scope.
- Starting and monitoring runs (polling plus incremental UI when callbacks are configured).
- Reviewing agent steps and evidence with correct **local timestamps** (**API emits UTC timestamps with `Z`** for runs).
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
