# ADR-0005: Linear workflow graph execution (MVP)

## Status

Accepted (2026-05-29)

## Context

Architecture diagrams show coordinator fan-out to parallel research agents. The execution engine in `shared/workflow_graph.py` and **`WorkflowEngine`** resolve **DAG execution levels** from `entry_node` and `edges` (see ADR-0008; linear MVP described here is superseded).

## Decision

- MVP execution is **strictly sequential** along the resolved graph order.
- Master/sub-agent within one node (`sub_agent_template_ids`) runs master first, then subs in list order.
- Parallel graph branches (fan-out/fan-in) are **not** implemented in the current engine.

## Consequences

- Documentation and diagrams must distinguish template topology from runtime parallelism.
- Workflow templates should use a linear chain (or sequential nodes) for correct ordering.
- Fan-out parallelism requires a future ADR and engine changes to `resolve_graph_node_ids`.
