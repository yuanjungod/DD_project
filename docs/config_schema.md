# Configuration Schema

This document describes the configuration contract shared by the frontend, backend, and agent service, plus **local runtime environment** defaults that override easily in development.

## Terminology

- `workflow_template` (formerly `scenario`): reusable process definition; it answers "how the due diligence runs".
- `engagement` (formerly `project`): concrete business instance bound to a company/application/version/resources; it answers "what this run is for".
- API routes now use `/engagements/*` for engagement resources and execution state.

## Local runtime environment

| Variable | Service | Role |
| --- | --- | --- |
| `DD_DATA_ROOT` | backend + agent | Shared writable file-data root. Defaults to `.dd_project/data` resolved from the repository root. |
| `DATABASE_URL` | backend | SQLAlchemy URL. If unset, SQLite is stored at `DD_DATA_ROOT/platform/dd_platform.db`. Relative SQLite URLs are resolved from the repository root. |
| `AGENT_SERVICE_URL` | backend | Base URL for **`POST /runs`** (default `http://127.0.0.1:8011`). |
| `AGENT_CALLBACK_SECRET` | backend + agent | Shared secret for **`X-Agent-Callback-Secret`** on **`POST /internal/agent-runs/.../progress`**. |
| `PLATFORM_CALLBACK_BASE_URL` | agent | Backend base URL for incremental progress (default `http://127.0.0.1:8010`). Set empty or unreachable to disable callbacks (UI then only updates after finalization). |
| `DD_SESSION_HISTORY_DIR` | agent | Optional legacy override (deprecated). Session JSON lives under `.dd_project/projects/<engagement>/users/<user>/sessions/<session>/runs/<workflow_template>/<run>.json`. |
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
    {workflow_template_id}/
      scenario.yaml                     # Workflow metadata + graph
      agents/
        {agent_id}.yaml                 # Agents referenced by this workflow template
  resource_configs/
    {resource_id}.yaml                  # Built-in resource connector definitions
  default_users.yaml                    # Development seed users
```

**Unified runtime home:** runtime config/state is organized under repository root **`.dd_project/`** for clearer separation of config, users, channels, and data.

```text
.dd_project/
  projects/
    {engagement_id}/
      meta/agent_overrides.json
      shared/resources/manifest.json
      shared/resource_configs/*.yaml
      shared/uploads/{file_id}
      users/{user_id}/sessions/{session_id}/runs/{workflow_template_id}/{run_id}.json
      users/{user_id}/sessions/{session_id}/runs/{workflow_template_id}/outputs/{run_id}_outputs/{step}_{agent}/
  data/platform/           # sqlite/db + platform-level overlays/uploads
  channels/                # chat/channel id mapping store (future expansion)
  users/                   # user-global state roots (future expansion)
```

**Workflow template folders:** each template has its own directory:

```text
catalog/scenarios/{workflow_template_id}/ # built-in workflow templates (in repo)
  scenario.yaml                           # workflow metadata + graph
  agents/
    {agent_id}.yaml                       # agents used by this workflow template

.dd_project/data/scenarios/{workflow_template_id}/ # user-created workflow templates
  scenario.yaml
  agents/
    {agent_id}.yaml

.dd_project/projects/{engagement_id}/users/{user_id}/sessions/{session_id}/runs/{workflow_template_id}/
  {run_id}.json
  outputs/{run_id}_outputs/{step}_{agent}/
```

Built-in workflow templates and user-created workflow templates only store templates (`scenario.yaml` + `agents/`). Runtime run/session artifacts are centralized under **`.dd_project/projects/.../users/.../sessions/.../runs/`**.

Skill packages are file-backed under **`agent_service/skills/<directory_name>/`**. Tool configs are mirrored through **`agent_service/configs/tools.yaml`**. Resource configs are file-backed through **`catalog/resource_configs/`** plus **`DD_DATA_ROOT/platform/resource_configs/`** overlays. Development seed users are file-backed through **`catalog/default_users.yaml`** unless **`DD_DEFAULT_USERS_CONFIG`** points elsewhere.

Engagement-scoped uploaded files (PDFs, Excel, etc.) have two layers:

- Resource metadata rows live in the database as `Resource(type=\"file_reference\", value=<file_id>)`.
- Binary blobs are stored under `.dd_project/projects/{engagement_id}/shared/uploads/{file_id}`.

Platform-wide library uploads share the same pattern:

- Rows are exposed via `/library/uploads` and merged into `company_config.resources.uploaded_files`.
- Binary blobs live under `.dd_project/data/platform/uploads/{file_id}` with manifest `.dd_project/data/platform/uploads_manifest.json`.
- On engagement creation, only platform blobs explicitly selected in `company_config.resources.uploaded_files` (and `agent_resource_scopes.*.uploaded_file_ids`) are copied into `.dd_project/projects/{engagement_id}/shared/uploads/` so engagement-only mounts (e.g., Docker bind mount for one engagement) can access the same `file_id` files locally.
- On engagement updates (`PATCH /engagements/{engagement_id}` with `company_config`), the backend incrementally copies any newly selected platform blobs into the same engagement-local uploads directory.

Skill packages follow the same engagement-localization principle:

- Agent skill packages are still defined globally under `agent_service/skills/{directory_name}`.
- On engagement creation, only skill packages referenced by the selected workflow snapshot are copied into `.dd_project/projects/{engagement_id}/shared/skills/{directory_name}`.
- On engagement updates (`PATCH /engagements/{engagement_id}` with `company_config`), the backend incrementally copies newly referenced skill package directories into the same engagement-local skills directory.

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

`workflow_template_id` selects the published workflow template for runs; `workflow_id` remains a compatibility alias. The backend builds the run snapshot from the published `scenario.yaml` and the separate agent catalog on disk.

## Configuration Catalog

Reusable workflows are managed through the backend configuration catalog:

- `SkillPackage` (file-backed): Anthropic/Cursor-style skill package with `SKILL.md`, directory name, editable package files, and optional bundled resources such as references, scripts, and assets. Skill packages live under `agent_service/skills/<directory_name>/`. Admins may **`POST /skills/import-zip`** (`multipart/form-data`: **`file`** = single-skill `.zip` with one top-level folder containing `SKILL.md`; optional **`directory_name`** form field overrides the disk directory slug).
- `ToolConfig` (file-backed): optional executable platform capabilities; persisted under `agent_service/configs/tools.yaml`.
- `ResourceConfig`: data resource available to agents, such as public web, uploaded files, vector stores, databases, or external APIs.
- `AgentTemplate` (file-backed): definitions are stored in **`catalog/agents/{agent_id}.yaml`**. Each record has `id`, `name`, `role`, inline `prompt`, optional `sub_agent_ids`, `skill_package_ids`, `tool_ids`, `skill_ids`, `resource_ids`, `react_config`, and `enabled`. The Admin UI uses **`GET/POST/PATCH /agent-templates`**; **`POST`** and **`PATCH`** write the global library.
- `WorkflowTemplate` (file-backed template): one folder per workflow template under **`catalog/scenarios/{workflow_id}/`** (built-in) or **`.dd_project/data/scenarios/{workflow_id}/`** (user-created). Each folder contains **`scenario.yaml`** (workflow graph and metadata) and an **`agents/`** subdirectory with the agents referenced by that template. **`GET/POST/PATCH /workflow-templates`** and publish/clone operate on these folders; only **`published`** templates are listed for non-admin callers and for run snapshots.

Only **`published`** workflow templates should be selected by downstream engagements. When a run starts, the backend creates a **workflow snapshot** from the current file-backed template, agent catalog, and DB/file-backed skill/tool/resource mirrors. The snapshot sent to the agent service includes `skill_packages` (with `package_files`), executable `tools`, `resources`, and each agent's `react_config`. By default, `react_config.model` uses the local Anthropic Messages-compatible `kimi-code` provider at `http://127.0.0.1:8081/v1`.

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
  "output_dir": "/path/to/.dd_project/projects/eng_x/users/user_x/sessions/sess_x/runs/standard_due_diligence/outputs/run_y_outputs/run_y_step_003_LegalRiskAgent",
  "output_readme_path": "/path/to/.dd_project/projects/eng_x/users/user_x/sessions/sess_x/runs/standard_due_diligence/outputs/run_y_outputs/run_y_step_003_LegalRiskAgent/README.md"
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
