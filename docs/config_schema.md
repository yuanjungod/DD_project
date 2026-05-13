# Configuration Schema

This document describes the configuration contract shared by the frontend, backend, and agent service, plus **local runtime environment** defaults that override easily in development.

## Local runtime environment

| Variable | Service | Role |
| --- | --- | --- |
| `DATABASE_URL` | backend | SQLAlchemy URL (defaults to SQLite under the backend working directory if unset). |
| `AGENT_SERVICE_URL` | backend | Base URL for **`POST /runs`** (default `http://127.0.0.1:8011`). |
| `AGENT_CALLBACK_SECRET` | backend + agent | Shared secret for **`X-Agent-Callback-Secret`** on **`POST /internal/agent-runs/.../progress`**. |
| `PLATFORM_CALLBACK_BASE_URL` | agent | Backend base URL for incremental progress (default `http://127.0.0.1:8010`). Set empty or unreachable to disable callbacks (UI then only updates after finalization). |
| `VITE_API_BASE_URL` | frontend | When set, all `fetch` calls use this absolute base (skips the dev proxy). |
| `VITE_DEV_PROXY_TARGET` | frontend (Vite config only) | Override proxy target for **`/api` → backend** during `npm run dev` (default `http://127.0.0.1:8010`). |

Conventions in README: **backend listening on `8010`**, **agent_service on `8011`**, **Vite on `5173`**. In development, the UI defaults to relative **`/api`**, which Vite proxies to the backend so the browser does not open cross-origin requests to `8010`.

## Agent templates on disk

Authoritative agent definitions: **`agent_service/configs/agent_templates.yaml`**. On first backend startup, if the file is missing, it is generated from **`agent_service/configs/agents.yaml`** (tool lists) plus prompt bodies under **`agent_service/prompts/`**. Older SQLite files may still contain an unused **`agent_templates`** table; the application no longer reads or writes agent definitions there.

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

`workflow_id` still points at a reusable workflow key in `agent_service/configs/workflows.yaml` for legacy paths. **Published company projects** should set **`workflow_template_id`** (and version when applicable) so the backend snapshot drives the graph.

## Evidence

Example evidence item as returned by the agent and stored on the backend (metadata column in the database is **`metadata_json`**):

```json
{
  "id": "ev_001",
  "title": "Official website states product line",
  "source_type": "web",
  "source_url": "https://example.com/products",
  "excerpt": "Example Robotics provides warehouse automation robots.",
  "confidence": 0.82,
  "collected_by": "WebResearchAgent",
  "metadata": {
    "published_at": "2026-01-01"
  }
}
```

## Configuration Catalog

Reusable workflows are managed through the backend configuration catalog:

- `SkillPackage`: Anthropic/Cursor-style skill package with `SKILL.md`, directory name, editable package files, and optional bundled resources such as references, scripts, and assets. Skill packages are synchronized to `agent_service/skills/<directory_name>/`. Admins may **`POST /skills/import-zip`** (`multipart/form-data`: **`file`** = single-skill `.zip` with one top-level folder containing `SKILL.md`; optional **`directory_name`** form field overrides the disk directory slug).
- `ToolConfig`: executable capability such as search, web fetch, file reading, vector retrieval, evidence storage, or report storage.
- `ResourceConfig`: data resource available to agents, such as public web, uploaded files, vector stores, databases, or external APIs.
- `AgentTemplate` (file-backed): **definitions** are embedded in each workflow bundle (`workflow_templates/<id>.yaml`) and optionally in **`workflow_templates/_shared_agents.yaml`**. Each record has `id`, `name`, `role`, inline `prompt`, `skill_package_ids`, `tool_ids`, `skill_ids`, `resource_ids`, `react_config`, `output_schema`, and `enabled`. Workflow graphs reference agents by **`id`**. The Admin UI uses **`GET/POST/PATCH /agent-templates`**; **`GET`** returns the union across bundles + shared file, **`POST`** appends to **`_shared_agents.yaml`**, and **`PATCH`** updates every file that contains that agent id.
- `WorkflowTemplate` (file-backed): one bundle per workflow under **`agent_service/configs/workflow_templates/{workflow_id}.yaml`**. Each file has a `workflow` object (ordered `graph`, `scenario`, `status`, `version`, etc.) plus the `agents` array used for that graph. **`GET/POST/PATCH /workflow-templates`** and publish/clone operate on these files; only **`published`** templates are listed for non-admin callers and for run snapshots.

Only **`published`** workflow templates should be selected by downstream company projects. When a run starts, the backend creates a **workflow snapshot** so historical runs remain auditable even if the template changes later. The snapshot includes `skill_packages` (with `package_files`), executable `tools`, `resources`, and each agent's `react_config`. By default, `react_config.model` uses the local Anthropic Messages-compatible `kimi-code` provider at `http://127.0.0.1:8081/v1`.

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
      "title": "No sanctions evidence found",
      "description": "Configured MVP sources did not return sanction matches.",
      "risk_level": "low",
      "confidence": 0.65,
      "evidence_ids": ["ev_003"]
    }
  ],
  "evidence": []
}
```

## Report Section

```json
{
  "title": "Legal and Compliance Risk",
  "summary": "The available evidence indicates low legal risk, subject to registry verification.",
  "risk_level": "low",
  "evidence_ids": ["ev_003"]
}
```

## Confidence Levels

- `0.80-1.00`: Strong source coverage.
- `0.60-0.79`: Useful but incomplete source coverage.
- `0.40-0.59`: Weak source coverage, requires manual review.
- `<0.40`: Treat as unverified.
