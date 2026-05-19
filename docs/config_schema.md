# Configuration Schema

This document describes the configuration contract shared by the frontend, backend, and agent service, plus **local runtime environment** defaults that override easily in development.

## Local runtime environment

| Variable | Service | Role |
| --- | --- | --- |
| `DD_DATA_ROOT` | backend + agent | Shared writable file-data root. Defaults to `data/dd_store` resolved from the repository root. |
| `DATABASE_URL` | backend | SQLAlchemy URL. If unset, SQLite is stored at `DD_DATA_ROOT/platform/dd_platform.db`. Relative SQLite URLs are resolved from the repository root. |
| `AGENT_SERVICE_URL` | backend | Base URL for **`POST /runs`** (default `http://127.0.0.1:8011`). |
| `AGENT_CALLBACK_SECRET` | backend + agent | Shared secret for **`X-Agent-Callback-Secret`** on **`POST /internal/agent-runs/.../progress`**. |
| `PLATFORM_CALLBACK_BASE_URL` | agent | Backend base URL for incremental progress (default `http://127.0.0.1:8010`). Set empty or unreachable to disable callbacks (UI then only updates after finalization). |
| `DD_SESSION_HISTORY_DIR` | agent | Optional session/output root. If unset, sessions live under `DD_DATA_ROOT/agent_service/sessions`. Relative paths are resolved from the repository root. |
| `DD_SEED_DEFAULT_USERS` | backend | Seed development users on startup when the users table is empty (default `true`). |
| `DD_DEFAULT_USERS_CONFIG` | backend | Optional path to the seed user YAML. Defaults to `catalog/default_users.yaml`; relative paths are resolved from the repository root. |
| `VITE_API_BASE_URL` | frontend | When set, all `fetch` calls use this absolute base (skips the dev proxy). |
| `VITE_DEV_PROXY_TARGET` | frontend (Vite config only) | Override proxy target for **`/api` → backend** during `npm run dev` (default `http://127.0.0.1:8010`). |
| `VITE_DEFAULT_LOGIN_EMAIL` / `VITE_DEFAULT_LOGIN_PASSWORD` | frontend | Optional login form prefill values for local development. |

Backend and agent service both read environment overrides from the repository-root **`.env`** file, independent of the process working directory. Conventions in README: **backend listening on `8010`**, **agent_service on `8011`**, **Vite on `5173`**. In development, the UI defaults to relative **`/api`**, which Vite proxies to the backend so the browser does not open cross-origin requests to `8010`.

## File-backed runtime catalogs

Authoritative scenario/workflow definitions live in **`agent_service/configs/scenario_templates/{workflow_id}.yaml`**. Each scenario file contains only workflow metadata and the graph of `agent_template_id` references. Reusable agent definitions live separately in **`agent_service/configs/agent_templates.yaml`**.

Skill packages are file-backed under **`agent_service/skills/<directory_name>/`**. The backend mirrors those files into the DB catalog at startup and writes API edits back to the same directory. Tool configs are mirrored through **`agent_service/configs/tools.yaml`**. Resource configs are already file-backed through **`catalog/resource_configs/`** plus **`DD_DATA_ROOT/platform/resource_configs/`** overlays. Development seed users are file-backed through **`catalog/default_users.yaml`** unless **`DD_DEFAULT_USERS_CONFIG`** points elsewhere.

## Company Configuration

```json
{
  "target_company": {
    "name": "Example Robotics",
    "aliases": ["ExampleBot"],
    "website": "https://example.com",
    "jurisdiction": "China",
    "industry": "Robotics",
    "keywords": ["warehouse automation", "robot arm"]
  },
  "scope": {
    "workflow_id": "standard_due_diligence",
    "workflow_template_id": null,
    "workflow_template_version": null,
    "scenario": "standard",
    "time_range": "last 5 years",
    "focus_areas": ["business", "financial", "legal", "ownership", "public_opinion", "compliance"],
    "report_language": "zh-CN"
  },
  "resources": {
    "uploaded_files": [],
    "trusted_sources": ["official website", "exchange filings"],
    "blocked_sources": [],
    "competitors": ["Peer Robotics"]
  }
}
```

`workflow_template_id` is the preferred pointer for company projects; `workflow_id` remains a compatibility alias. The backend builds the run snapshot from the published scenario file and the separate agent catalog on disk.

## Configuration Catalog

Reusable workflows are managed through the backend configuration catalog:

- `SkillPackage` (file-backed, DB-mirrored): Anthropic/Cursor-style skill package with `SKILL.md`, directory name, editable package files, and optional bundled resources such as references, scripts, and assets. Skill packages live under `agent_service/skills/<directory_name>/`. Admins may **`POST /skills/import-zip`** (`multipart/form-data`: **`file`** = single-skill `.zip` with one top-level folder containing `SKILL.md`; optional **`directory_name`** form field overrides the disk directory slug).
- `ToolConfig` (file-backed, DB-mirrored): executable capability such as search, web fetch, file reading, vector retrieval, or report storage; persisted under `agent_service/configs/tools.yaml`.
- `ResourceConfig`: data resource available to agents, such as public web, uploaded files, vector stores, databases, or external APIs.
- `AgentTemplate` (file-backed): definitions are stored in **`agent_service/configs/agent_templates.yaml`**. Each record has `id`, `name`, `role`, inline `prompt`, `skill_package_ids`, `tool_ids`, `skill_ids`, `resource_ids`, `react_config`, and `enabled`. Agent-specific output requirements live in the agent prompt / bound Skills, not in a separate output contract field. Workflow graphs reference agents by **`id`**. The Admin UI uses **`GET/POST/PATCH /agent-templates`**; **`POST`** and **`PATCH`** write this catalog.
- `WorkflowTemplate` (file-backed scenario): one scenario file per workflow under **`agent_service/configs/scenario_templates/{workflow_id}.yaml`**. Each file has a `workflow` object (ordered `graph`, `scenario`, `status`, `version`, etc.) and no embedded agent definitions. **`GET/POST/PATCH /workflow-templates`** and publish/clone operate on these files; only **`published`** templates are listed for non-admin callers and for run snapshots.

Only **`published`** workflow templates should be selected by downstream company projects. When a run starts, the backend creates a **workflow snapshot** from the current file-backed scenario, agent catalog, and DB/file-backed skill/tool/resource mirrors. The snapshot sent to the agent service includes `skill_packages` (with `package_files`), executable `tools`, `resources`, and each agent's `react_config`. By default, `react_config.model` uses the local Anthropic Messages-compatible `kimi-code` provider at `http://127.0.0.1:8081/v1`.

## Run and time fields

- **`AgentRun.started_at` / `completed_at`** are persisted as **UTC** in the database. JSON responses serialize these fields as **RFC 3339 UTC strings ending with `Z`** (`AgentRunRead`) so browsers interpret offsets correctly.

## Agent Result

```json
{
  "agent": "LegalRiskAgent",
  "status": "completed",
  "summary": "No high-severity legal risk found in configured sources.",
  "findings": [
    {
      "title": "No sanctions matches in configured sources",
      "description": "Configured MVP sources did not return sanction matches.",
      "risk_level": "low",
      "confidence": 0.65
    }
  ],
  "output_dir": "/path/to/data/dd_store/agent_service/sessions/proj_x/run_y_outputs/run_y_step_003_LegalRiskAgent",
  "output_readme_path": "/path/to/data/dd_store/agent_service/sessions/proj_x/run_y_outputs/run_y_step_003_LegalRiskAgent/README.md"
}
```

Each completed agent step also writes a filesystem handoff folder next to the run session JSON. The folder contains **`README.md`** (human-readable summary), **`result.json`** (full structured result), and **`findings/`**. Downstream agents receive prior folder addresses in `previous_agent_output_folders` and can call the automatic `agent_output_reader` runtime tool with `folder_path` to read the prior README and structured result.

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
