# ADR-0010: InstanceConfig generalization (Phase E)

## Status

Accepted

## Context

Engagement configuration was modeled as `company_config` with a required `target_company`, which fits due-diligence templates but not generic workflow scenarios.

## Decision

- Introduce **`InstanceConfig`** as the canonical API/config name (`instance_config` on create/update/read).
- Keep DB column **`engagements.company_config`** unchanged; stored JSON is dual-read via `shared/instance_config.py`.
- Due-diligence templates continue to use root **`target_company`** in stored JSON (legacy shape).
- Non-diligence templates store **`extensions.subject`** (and optional template-specific blocks). Task-first creates send **`extensions.workflow_task`** only; `materialize_stored_config` fills **`extensions.subject`** from the first line of the task.
- New creates require a non-empty **`extensions.workflow_task`** (or legacy subject/target_company when `allow_legacy=True` on read/patch).
- Agent runs still receive **`company_config`** with **`target_company`** and **`workflow_task`** synthesized at dispatch time (`to_agent_company_config`).

## Consequences

- Frontend labels are neutral unless a due-diligence template is selected.
- `company_config` request/response fields remain as deprecated aliases for one release cycle.
