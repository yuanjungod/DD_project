from __future__ import annotations

from collections import defaultdict
from typing import Any


class WorkflowGraphError(ValueError):
    """Invalid workflow graph (cycle, missing node, etc.)."""


def _graph_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in graph.get("nodes", []) if isinstance(node, dict) and node.get("id")]


def _build_adjacency(graph: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, list[str]]]:
    nodes = _graph_nodes(graph)
    by_node_id = {str(node["id"]): node for node in nodes}
    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("from") or "").strip()
        target = str(edge.get("to") or "").strip()
        if not source or not target:
            continue
        if source not in by_node_id or target not in by_node_id:
            raise WorkflowGraphError(f"Edge references unknown node: {source!r} -> {target!r}")
        outgoing[source].append(target)
        incoming[target].append(source)
    for node_id in by_node_id:
        outgoing[node_id].sort()
        incoming[node_id].sort()
    return by_node_id, incoming, outgoing


def _execution_levels(graph: dict[str, Any], *, validate_agents: bool) -> list[list[str]]:
    if validate_agents:
        for node_id, node in _build_adjacency(graph)[0].items():
            agent_id = str(node.get("agent_template_id") or "").strip()
            if not agent_id:
                raise WorkflowGraphError(f"Graph node {node_id!r} is missing agent_template_id")

    by_node_id, incoming, outgoing = _build_adjacency(graph)
    if not by_node_id:
        raise WorkflowGraphError("Workflow graph must include at least one node")

    in_degree = {node_id: len(incoming[node_id]) for node_id in by_node_id}
    levels: list[list[str]] = []
    current = sorted(node_id for node_id, degree in in_degree.items() if degree == 0)

    while current:
        levels.append(current)
        next_level: list[str] = []
        for node_id in current:
            for target in outgoing[node_id]:
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    next_level.append(target)
        current = sorted(next_level)

    if sum(len(level) for level in levels) != len(by_node_id):
        raise WorkflowGraphError("Workflow graph contains a cycle")
    return levels


def validate_workflow_graph(graph: dict[str, Any]) -> None:
    """Ensure graph is a non-empty DAG with agent ids on every node."""
    _execution_levels(graph, validate_agents=True)


def _topological_node_ids(graph: dict[str, Any]) -> list[str]:
    try:
        return [node_id for level in _execution_levels(graph, validate_agents=False) for node_id in level]
    except WorkflowGraphError:
        return []


def resolve_graph_execution_levels(graph: dict[str, Any]) -> list[list[str]]:
    """Return node ids grouped by dependency depth; each level may run in parallel."""

    validate_workflow_graph(graph)
    return _execution_levels(graph, validate_agents=False)


def resolve_graph_node_ids(graph: dict[str, Any]) -> list[str]:
    """Return workflow node ids in topological execution order."""

    if not _graph_nodes(graph):
        return []
    try:
        return _topological_node_ids(graph)
    except WorkflowGraphError:
        return []


def resolve_graph_predecessors(graph: dict[str, Any]) -> dict[str, list[str]]:
    """Direct predecessor node ids for each graph node."""

    _, incoming, _ = _build_adjacency(graph)
    return {node_id: list(incoming[node_id]) for node_id in incoming}


def infer_entry_and_report_nodes(graph: dict[str, Any]) -> tuple[str, str]:
    """Pick entry/report nodes from topology (roots / sinks)."""

    by_node_id, incoming, outgoing = _build_adjacency(graph)
    if not by_node_id:
        return "", ""

    explicit_entry = str(graph.get("entry_node") or "").strip()
    explicit_report = str(graph.get("report_node") or "").strip()
    roots = sorted(node_id for node_id in by_node_id if not incoming[node_id])
    sinks = sorted(node_id for node_id in by_node_id if not outgoing[node_id])

    entry = explicit_entry if explicit_entry in by_node_id else (roots[0] if roots else next(iter(by_node_id)))
    report = explicit_report if explicit_report in by_node_id else (sinks[-1] if sinks else entry)
    return entry, report


def _collect_node_agent_ids(node: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    master_id = str(node.get("agent_template_id") or "").strip()
    if master_id:
        ids.append(master_id)
    for sub_agent_id in node.get("sub_agent_template_ids") or []:
        sub = str(sub_agent_id or "").strip()
        if sub:
            ids.append(sub)
    return ids


def resolve_graph_agent_order(graph: dict[str, Any]) -> list[str]:
    """Return agent_template_id values in topological node order."""

    nodes = _graph_nodes(graph)
    if not nodes:
        return []

    by_node_id = {str(node["id"]): node for node in nodes if node.get("id")}
    agent_ids: list[str] = []
    for node_id in resolve_graph_node_ids(graph):
        node = by_node_id.get(node_id)
        if isinstance(node, dict):
            agent_ids.extend(_collect_node_agent_ids(node))
    return agent_ids


def resolve_graph_node_agent_plan(graph: dict[str, Any]) -> list[tuple[str, str]]:
    """Flatten graph into sequential agent steps as (node_id, agent_template_id)."""

    nodes = _graph_nodes(graph)
    if not nodes:
        return []

    by_node_id = {str(node["id"]): node for node in nodes if node.get("id")}
    plan: list[tuple[str, str]] = []
    for node_id in resolve_graph_node_ids(graph):
        node = by_node_id.get(node_id)
        if not isinstance(node, dict):
            continue
        for agent_id in _collect_node_agent_ids(node):
            plan.append((node_id, agent_id))
    return plan
