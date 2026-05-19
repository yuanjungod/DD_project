# ADR-0001: File-backed skill and tool catalog (no DB mirror)

## Status

Accepted (2026-05-19)

## Context

Skill packages and tool configs were mirrored in SQLite (`skill_packages`, `tool_configs`) and on disk (`agent_service/skills/`, `tools.yaml`). Startup synced disk → DB → disk, which caused drift risk and duplicated interfaces.

## Decision

- **Source of truth**: `agent_service/skills/` and `agent_service/configs/tools.yaml` only.
- **Backend**: `skill_catalog` and `tool_catalog` services read/write files; HTTP APIs do not use SQLAlchemy for these entities.
- **Workflow snapshots**: load skill/tool payloads from disk at snapshot build time.
- **Removed**: `SkillPackage` and `ToolConfig` ORM models and DB seed/sync for them.

## Consequences

- Existing SQLite DBs may retain unused `skill_packages` / `tool_configs` tables; safe to ignore or drop on manual reset.
- Admin edits through the UI write directly to repo paths (or deployed `agent_service/` tree).
- Resource configs remain file + overlay (unchanged).
