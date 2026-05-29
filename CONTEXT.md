# Harness_Project (Agent Orchestration Platform)

MVP workspace for configuring Agent workflow templates, running graph-orchestrated agents, and reviewing outputs. Due-diligence templates remain available as published scenarios.

## Language

**Skill package**:
An Anthropic-style skill directory under `agent_service/skills/` with a `SKILL.md` frontmatter and optional bundled files.
_Avoid_: Skill row, skill DB record.

**Tool config**:
A named executable tool entry in `agent_service/configs/tools.yaml` referenced by agent templates via `tool_ids`. Runtime loads the `implementation` dotted path through the **tool registry** (`agent_service/tools/registry.py`).
_Avoid_: Tool DB row, hardcoded `if tool_id ==` dispatch in the runner.

**Workflow snapshot**:
The immutable JSON bundle assembled per run (workflow graph, agent templates, skill packages, tools, resources).
_Avoid_: Live catalog, cached workflow.

**Workflow graph order**:
Agent execution order derived from `entry_node` and `edges` via `shared/workflow_graph.resolve_graph_agent_order` (not raw `nodes` array order).
_Avoid_: Sorting agents by YAML node list index alone.

**Resource config**:
A typed data-source definition from shipped `catalog/resource_configs/` plus optional platform overlays under `HARNESS_DATA_ROOT`.

**Engagement**:
A concrete business instance (company/subject, application id, version, resources, runs). Persisted in the `engagements` table.

**Workflow template**:
Reusable process definition (`workflow_template_id`) with graph and agent templates under `catalog/workflow_templates/`.

**WorkflowEngine**:
Graph orchestration runtime in `agent_service/workflows/workflow_engine.py` (executes agents by DAG levels, parallel within a level).

See [docs/adr/0008-harness-platform-rename.md](docs/adr/0008-harness-platform-rename.md) for platform rename decisions.
