# Due Diligence Platform

MVP workspace for configuring due diligence workflows, running agents, and reviewing reports.

## Language

**Skill package**:
An Anthropic-style skill directory under `agent_service/skills/` with a `SKILL.md` frontmatter and optional bundled files.
_Avoid_: Skill row, skill DB record.

**Tool config**:
A named executable tool entry in `agent_service/configs/tools.yaml` referenced by agent templates via `tool_ids`. Runtime loads the `implementation` dotted path through the **tool registry** (`agent_service/tools/registry.py`).
_Avoid_: Tool DB row, skill_ids (legacy alias for tool_ids on agents only), hardcoded `if tool_id ==` dispatch in the runner.

**Workflow snapshot**:
The immutable JSON bundle assembled per run (workflow graph, agent templates, skill packages, tools, resources).
_Avoid_: Live catalog, cached workflow.

**Workflow graph order**:
Agent execution order derived from `entry_node` and `edges` via `shared/workflow_graph.resolve_graph_agent_order` (not raw `nodes` array order).
_Avoid_: Sorting agents by YAML node list index alone.

**Resource config**:
A typed data-source definition from shipped `catalog/resource_configs/` plus optional platform overlays under `DD_DATA_ROOT`.

## Relationships

- An **Agent template** references zero or more **skill packages** and **tool configs** by id.
- A **Workflow snapshot** embeds the resolved **skill packages** and **tool configs** needed for that run.
- **Skill packages** and **tool configs** are edited only on disk; the backend API is a thin file adapter.

## Example dialogue

> **Dev:** "Where do I add a new mock search tool?"
> **Domain expert:** "Add it to **tools.yaml** and wire the agent template's **tool_ids**. Runs copy it into the **workflow snapshot** — you don't touch the database."

## Flagged ambiguities

- `skill_ids` on agent templates is a legacy name for **tool config** ids; prefer **tool_ids** in new YAML and UI.
