# ADR-0008: Harness platform rename

## Status

Accepted

## Context

The repository began as a due-diligence MVP (`DD_project`, `.dd_project/`, `DueDiligenceWorkflow`). The product direction is a **generic Agent orchestration platform** while keeping due-diligence workflow templates as selectable scenarios.

## Decisions

| Area | Decision |
|------|----------|
| Product name | **Harness** |
| Legacy repo folder | `DD_project` (historical; GitHub remote may still use this slug) |
| Runtime data home | **`.harness_project/`** at repository root |
| Writable data subdir | **`.harness_project/data/`** via `HARNESS_DATA_ROOT` |
| Platform SQLite default | **`harness_platform.db`** (read legacy `dd_platform.db` if present) |
| Execution engine class | **`WorkflowEngine`** in `agent_service/workflows/workflow_engine.py` |
| Business instance model | **Keep `Engagement`** (ADR-0007) |
| Due-diligence templates | **Keep** `catalog/workflow_templates/*_due_diligence/` and their template ids |

## Compatibility

- Environment variables: **`HARNESS_*` only** (`DD_*` aliases removed in 2026 compat shrink).
- Runtime home: **`.harness_project/`** only at runtime; copy legacy **`.dd_project/`** via `scripts/migrate_dd_project_to_harness_project.py` (not auto-read).
- Auth token (frontend): migrate **`dd_access_token`** → **`harness_access_token`** once on boot.
- Platform must **not** default to `standard_due_diligence`; callers must choose a published workflow template explicitly.
- Platform SQLite: prefer **`harness_platform.db`**; still open **`dd_platform.db`** in the same directory when the new file is absent.

## Migration

Copy legacy runtime data with:

```bash
python scripts/migrate_dd_project_to_harness_project.py --dry-run
python scripts/migrate_dd_project_to_harness_project.py
```

See [docs/harness_runtime_storage.md](../harness_runtime_storage.md).

## Consequences

- Documentation and UI copy use Harness branding; due-diligence wording remains inside DD template content only.
- Phase D (Session rename) complete; Phase E (InstanceConfig) complete per ADR-0010.
