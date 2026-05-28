# Configuration Schema

This document describes the configuration contract shared by the frontend, backend, and agent service, plus **local runtime environment** defaults that override easily in development.

## Local runtime environment

| Variable | Service | Role |
| --- | --- | --- |
| `DD_DATA_ROOT` | backend + agent | Shared writable file-data root. Defaults to `.dd_project/data` resolved from the repository root. |
| `DATABASE_URL` | backend | SQLAlchemy URL. If unset, SQLite is stored at `DD_DATA_ROOT/platform/dd_platform.db`. Relative SQLite URLs are resolved from the repository root. |
| `AGENT_SERVICE_URL` | backend | Base URL for **`POST /runs`** (default `http://127.0.0.1:8011`). |
| `AGENT_CALLBACK_SECRET` | backend + agent | Shared secret for **`X-Agent-Callback-Secret`** on **`POST /internal/agent-runs/.../progress`**. |
| `PLATFORM_CALLBACK_BASE_URL` | agent | Backend base URL for incremental progress (default `http://127.0.0.1:8010`). Set empty or unreachable to disable callbacks (UI then only updates after finalization). |
| `DD_SESSION_HISTORY_DIR` | agent | Optional legacy override (deprecated). Session JSON lives under `.dd_project/runs/<scenario_id>/<user_id>/<project>/<run>.json`. |
| `DD_SEED_DEFAULT_USERS` | backend | Seed development users on startup when the users table is empty (default `true`). |
| `DD_DEFAULT_USERS_CONFIG` | backend | Optional path to the seed user YAML. Defaults to `catalog/default_users.yaml`; relative paths are resolved from the repository root. |
| `VITE_API_BASE_URL` | frontend | When set, all `fetch` calls use this absolute base (skips the dev proxy). |
| `VITE_DEV_PROXY_TARGET` | frontend (Vite config only) | Override proxy target for **`/api` → backend** during `npm run dev` (default `http://127.0.0.1:8010`). |
| `VITE_DEFAULT_LOGIN_EMAIL` / `VITE_DEFAULT_LOGIN_PASSWORD` | frontend | Optional login form prefill values for local development. |

Backend and agent service both read environment overrides from the repository-root **`.env`** file, independent of the process working directory. Conventions in README: **backend listening on `8010`**, **agent_service on `8011`**, **Vite on `5173`**. In development, the UI defaults to relative **`/api`**, which Vite proxies to the backend so the browser does not open cross-origin requests to `8010`.

## File-backed runtime catalogs

### `catalog/` (built-in template catalog)

```text
catalog/
  agents/
    {agent_id}.yaml                     # Reusable global agent templates
  scenarios/
    {scenario_id}/
      scenario.yaml                     # Workflow metadata + graph
      agents/
        {agent_id}.yaml                 # Agents referenced by this scenario
  resource_configs/
    {resource_id}.yaml                  # Built-in resource connector definitions
  default_users.yaml                    # Development seed users
```

**Unified runtime home:** runtime config/state is organized under project root **`.dd_project/`** for clearer separation of config, users, channels, and data.

```text
.dd_project/
  config/                  # global/project config manifests
    projects/{project_id}/agent_overrides.json
  users/                   # user-isolated state roots (future expansion)
  channels/                # chat/channel id mapping store (future expansion)
  data/                    # sqlite/db artifacts when needed (future expansion)
```

**Scenario folders:** each scenario has its own directory:

```text
catalog/scenarios/{scenario_id}/          # built-in scenarios (in repo)
  scenario.yaml                           # workflow metadata + graph
  agents/
    {agent_id}.yaml                       # agents used by this scenario

.dd_project/data/scenarios/{scenario_id}/ # user-created scenarios
  scenario.yaml
  agents/
    {agent_id}.yaml

.dd_project/runs/{scenario_id}/           # runtime sessions + outputs
  {user_id}/
    {project_id}/
      {run_id}.json
      outputs/{run_id}_outputs/{step}_{agent}/
```

Built-in scenarios and user-created scenarios only store templates (`scenario.yaml` + `agents/`). Runtime run/session artifacts are centralized under **`.dd_project/runs/`**.

Skill packages are file-backed under **`agent_service/skills/<directory_name>/`**. Tool configs are mirrored through **`agent_service/configs/tools.yaml`**. Resource configs are file-backed through **`catalog/resource_configs/`** plus **`DD_DATA_ROOT/platform/resource_configs/`** overlays. Development seed users are file-backed through **`catalog/default_users.yaml`** unless **`DD_DEFAULT_USERS_CONFIG`** points elsewhere.

Project-scoped uploaded files (PDFs, Excel, etc.) have two layers:

- Resource metadata rows live in the database as `Resource(type=\"file_reference\", value=<file_id>)`.
- Binary blobs are stored under `.dd_project/data/projects/{project_id}/uploads/{file_id}`.

Platform-wide library uploads share the same pattern:

- Rows are exposed via `/library/uploads` and merged into `company_config.resources.uploaded_files`.
- Binary blobs live under `.dd_project/data/platform/uploads/{file_id}` with manifest `.dd_project/data/platform/uploads_manifest.json`.

## Company Configuration

```json
{
  "target_company": {
    "name": "Example Robotics",
    "aliases": ["ExampleBot"]
  },
  "workflow_id": "standard_due_diligence",
  "workflow_template_id": "standard_due_diligence",
  "workflow_template_version": 1,
  "resources": {
    "uploaded_files": [],
    "trusted_sources": ["official website", "exchange filings"],
    "blocked_sources": [],
    "competitors": ["Peer Robotics"]
  }
}
```

`workflow_template_id` selects the published scenario template for runs; `workflow_id` remains a compatibility alias. The backend builds the run snapshot from the published scenario file and the separate agent catalog on disk.

## Configuration Catalog

Reusable workflows are managed through the backend configuration catalog:

- `SkillPackage` (file-backed): Anthropic/Cursor-style skill package with `SKILL.md`, directory name, editable package files, and optional bundled resources such as references, scripts, and assets. Skill packages live under `agent_service/skills/<directory_name>/`. Admins may **`POST /skills/import-zip`** (`multipart/form-data`: **`file`** = single-skill `.zip` with one top-level folder containing `SKILL.md`; optional **`directory_name`** form field overrides the disk directory slug).
- `ToolConfig` (file-backed): optional executable platform capabilities; persisted under `agent_service/configs/tools.yaml`.
- `ResourceConfig`: data resource available to agents, such as public web, uploaded files, vector stores, databases, or external APIs.
- `AgentTemplate` (file-backed): definitions are stored in **`catalog/agents/{agent_id}.yaml`**. Each record has `id`, `name`, `role`, inline `prompt`, optional `sub_agent_ids`, `skill_package_ids`, `tool_ids`, `skill_ids`, `resource_ids`, `react_config`, and `enabled`. The Admin UI uses **`GET/POST/PATCH /agent-templates`**; **`POST`** and **`PATCH`** write the global library.
- `WorkflowTemplate` (file-backed scenario): one folder per scenario under **`catalog/scenarios/{workflow_id}/`** (built-in) or **`.dd_project/data/scenarios/{workflow_id}/`** (user-created). Each folder contains **`scenario.yaml`** (workflow graph and metadata) and an **`agents/`** subdirectory with the agents referenced by that scenario. **`GET/POST/PATCH /workflow-templates`** and publish/clone operate on these folders; only **`published`** templates are listed for non-admin callers and for run snapshots.

Only **`published`** workflow templates should be selected by downstream company projects. When a run starts, the backend creates a **workflow snapshot** from the current file-backed scenario, agent catalog, and DB/file-backed skill/tool/resource mirrors. The snapshot sent to the agent service includes `skill_packages` (with `package_files`), executable `tools`, `resources`, and each agent's `react_config`. By default, `react_config.model` uses the local Anthropic Messages-compatible `kimi-code` provider at `http://127.0.0.1:8081/v1`.

Workflow graph nodes support both flat and hierarchical execution definitions:

- Flat (existing): `agent_template_id: CoordinatorAgent`
- Master/Sub (new): `agent_template_id: CoordinatorAgent`, `sub_agent_template_ids: [CompanyProfileAgent, WebResearchAgent]`

Execution order stays graph-driven by node order; within one node, the `agent_template_id` (master) runs first, then each `sub_agent_template_ids` entry in list order.

## Run and time fields

- **`AgentRun.started_at` / `completed_at`** are persisted as **UTC** in the database. JSON responses serialize these fields as **RFC 3339 UTC strings ending with `Z`** (`AgentRunRead`) so browsers interpret offsets correctly.

## Agent Result

```json
{
  "agent": "LegalRiskAgent",
  "status": "completed",
  "output_dir": "/path/to/.dd_project/runs/standard_due_diligence/user_x/proj_x/outputs/run_y_outputs/run_y_step_003_LegalRiskAgent",
  "output_readme_path": "/path/to/.dd_project/runs/standard_due_diligence/user_x/proj_x/outputs/run_y_outputs/run_y_step_003_LegalRiskAgent/README.md"
}
```

Each completed agent step also writes a filesystem handoff folder next to the run session JSON. The folder contains **`README.md`** (step metadata) and **`result.json`** (structured `AgentResult`). Downstream agents receive prior folder paths in `previous_agent_output_folders`, with README text inlined in `previous_agent_handoff_readmes`; they read further files via AgentScope `view_text_file`.

## Report Section

```json
{
  "title": "Legal and Compliance Risk",
  "summary": "Available sources indicate low legal risk, subject to registry verification.",
  "risk_level": "low"
}
```

## Confidence Levels

- `0.80-1.00`: Strong source coverage.
- `0.60-0.79`: Useful but incomplete source coverage.
- `0.40-0.59`: Weak source coverage, requires manual review.
- `<0.40`: Treat as unverified.
