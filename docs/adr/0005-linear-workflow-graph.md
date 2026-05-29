# ADR-0005: Linear workflow graph execution (MVP)

## Status

**Superseded** (2026-05-29) — runtime now executes **DAG levels** with parallelism within each level (`WorkflowEngine` + `shared/workflow_graph.py`). Kept for historical context.

## Context

Early MVP documentation described strictly sequential execution. The platform later added level-based DAG execution so independent branches at the same depth can run concurrently.

## Decision (historical)

- Original MVP was sequential along resolved graph order only.
- Parallel fan-out was deferred.

## Current behavior (supersedes this ADR)

- **`resolve_graph_execution_levels`** builds topological levels from `entry_node` and `edges`.
- **`WorkflowEngine`** runs all nodes in a level concurrently (thread pool), then advances to the next level.
- Within one graph node, **`agent_template_id`** (master) runs first, then each **`sub_agent_template_ids`** entry in list order.
- Handoff to downstream nodes uses completed predecessor **`AgentResult`** rows (`output_dir`, README).

## Consequences

- Diagrams that show only a single chain are illustrative; templates may use parallel branches when edges permit.
- Ordering within a node (master → subs) is unchanged.
