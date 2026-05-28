from __future__ import annotations

from typing import Any


def _collect_node_agent_ids(node: dict[str, Any]) -> list[str]:
    """Collect execution agent ids from one graph node.

    Supports legacy `agent_template_id` and hierarchical master/sub-agent config:
    - `agent_template_id`: "CoordinatorAgent"
    - `agent_template_id`: "MasterAgent", `sub_agent_template_ids`: ["SubA", "SubB"]
    """

    ids: list[str] = []
    master_id = str(node.get("agent_template_id") or "").strip()
    if master_id:
        ids.append(master_id)
    for sub_agent_id in node.get("sub_agent_template_ids") or []:
        sub = str(sub_agent_id or "").strip()
        if sub:
            ids.append(sub)
    return ids


def resolve_graph_node_ids(graph: dict[str, Any]) -> list[str]:
    """Return workflow node ids in execution order (entry_node + edges, then unreachable nodes)."""

    nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
    if not nodes:
        return []

    by_node_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    ordered_node_ids: list[str] = []
    current = str(graph.get("entry_node") or nodes[0].get("id") or "")
    outgoing: dict[str, str] = {}
    for edge in graph.get("edges", []):
        if isinstance(edge, dict) and edge.get("from") and edge.get("to"):
            outgoing[str(edge["from"])] = str(edge["to"])

    seen: set[str] = set()
    while current and current in by_node_id and current not in seen:
        ordered_node_ids.append(current)
        seen.add(current)
        current = outgoing.get(current, "")

    for node in nodes:
        node_id = str(node.get("id") or "")
        if node_id and node_id not in seen:
            ordered_node_ids.append(node_id)

    return ordered_node_ids


def resolve_graph_agent_order(graph: dict[str, Any]) -> list[str]:
    """Return agent_template_id values in workflow execution order."""

    nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
    if not nodes:
        return []

    by_node_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    agent_ids: list[str] = []
    for node_id in resolve_graph_node_ids(graph):
        node = by_node_id.get(node_id)
        if not isinstance(node, dict):
            continue
        agent_ids.extend(_collect_node_agent_ids(node))
    return agent_ids
