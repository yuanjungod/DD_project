from __future__ import annotations

import unittest

from shared.workflow_graph import (
    resolve_graph_agent_order,
    resolve_graph_execution_levels,
    resolve_graph_node_ids,
    validate_workflow_graph,
    WorkflowGraphError,
)


LINEAR_GRAPH = {
    "nodes": [
        {"id": "node_01", "agent_template_id": "A"},
        {"id": "node_02", "agent_template_id": "B"},
        {"id": "node_03", "agent_template_id": "C"},
    ],
    "edges": [
        {"from": "node_01", "to": "node_02"},
        {"from": "node_02", "to": "node_03"},
    ],
    "entry_node": "node_01",
}

SHUFFLED_NODES_GRAPH = {
    "nodes": [
        {"id": "node_03", "agent_template_id": "C"},
        {"id": "node_01", "agent_template_id": "A"},
        {"id": "node_02", "agent_template_id": "B"},
    ],
    "edges": [
        {"from": "node_01", "to": "node_02"},
        {"from": "node_02", "to": "node_03"},
    ],
    "entry_node": "node_01",
}

DISCONNECTED_GRAPH = {
    "nodes": [
        {"id": "node_01", "agent_template_id": "A"},
        {"id": "node_02", "agent_template_id": "B"},
        {"id": "node_orphan", "agent_template_id": "Orphan"},
    ],
    "edges": [{"from": "node_01", "to": "node_02"}],
    "entry_node": "node_01",
}

PARALLEL_GRAPH = {
    "nodes": [
        {"id": "node_01", "agent_template_id": "A"},
        {"id": "node_02", "agent_template_id": "B"},
        {"id": "node_03", "agent_template_id": "C"},
        {"id": "node_04", "agent_template_id": "D"},
    ],
    "edges": [
        {"from": "node_01", "to": "node_03"},
        {"from": "node_02", "to": "node_03"},
        {"from": "node_03", "to": "node_04"},
    ],
    "entry_node": "node_01",
}

CYCLE_GRAPH = {
    "nodes": [
        {"id": "node_01", "agent_template_id": "A"},
        {"id": "node_02", "agent_template_id": "B"},
    ],
    "edges": [
        {"from": "node_01", "to": "node_02"},
        {"from": "node_02", "to": "node_01"},
    ],
    "entry_node": "node_01",
}

MASTER_SUB_GRAPH = {
    "nodes": [
        {
            "id": "node_01",
            "agent_template_id": "Master",
            "sub_agent_template_ids": ["SubA", "SubB"],
        },
        {"id": "node_02", "agent_template_id": "Tail"},
    ],
    "edges": [{"from": "node_01", "to": "node_02"}],
    "entry_node": "node_01",
}


class WorkflowGraphTests(unittest.TestCase):
    def test_linear_graph_follows_edges(self) -> None:
        self.assertEqual(resolve_graph_node_ids(LINEAR_GRAPH), ["node_01", "node_02", "node_03"])
        self.assertEqual(resolve_graph_agent_order(LINEAR_GRAPH), ["A", "B", "C"])
        self.assertEqual(resolve_graph_execution_levels(LINEAR_GRAPH), [["node_01"], ["node_02"], ["node_03"]])

    def test_shuffled_nodes_still_follow_edges(self) -> None:
        self.assertEqual(resolve_graph_agent_order(SHUFFLED_NODES_GRAPH), ["A", "B", "C"])

    def test_unreachable_nodes_included_at_roots(self) -> None:
        self.assertEqual(resolve_graph_agent_order(DISCONNECTED_GRAPH), ["A", "Orphan", "B"])
        self.assertEqual(resolve_graph_execution_levels(DISCONNECTED_GRAPH), [["node_01", "node_orphan"], ["node_02"]])

    def test_parallel_levels(self) -> None:
        self.assertEqual(
            resolve_graph_execution_levels(PARALLEL_GRAPH),
            [["node_01", "node_02"], ["node_03"], ["node_04"]],
        )
        self.assertEqual(resolve_graph_agent_order(PARALLEL_GRAPH), ["A", "B", "C", "D"])

    def test_cycle_rejected(self) -> None:
        with self.assertRaises(WorkflowGraphError):
            validate_workflow_graph(CYCLE_GRAPH)

    def test_empty_graph(self) -> None:
        self.assertEqual(resolve_graph_agent_order({}), [])
        self.assertEqual(resolve_graph_agent_order({"nodes": []}), [])

    def test_master_sub_node_expands_in_order(self) -> None:
        self.assertEqual(resolve_graph_agent_order(MASTER_SUB_GRAPH), ["Master", "SubA", "SubB", "Tail"])


if __name__ == "__main__":
    unittest.main()
