from __future__ import annotations

import unittest

from shared.workflow_graph import resolve_graph_agent_order, resolve_graph_node_ids


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


class WorkflowGraphTests(unittest.TestCase):
    def test_linear_graph_follows_edges(self) -> None:
        self.assertEqual(resolve_graph_node_ids(LINEAR_GRAPH), ["node_01", "node_02", "node_03"])
        self.assertEqual(resolve_graph_agent_order(LINEAR_GRAPH), ["A", "B", "C"])

    def test_shuffled_nodes_still_follow_edges(self) -> None:
        self.assertEqual(resolve_graph_agent_order(SHUFFLED_NODES_GRAPH), ["A", "B", "C"])

    def test_unreachable_nodes_appended(self) -> None:
        self.assertEqual(resolve_graph_agent_order(DISCONNECTED_GRAPH), ["A", "B", "Orphan"])

    def test_empty_graph(self) -> None:
        self.assertEqual(resolve_graph_agent_order({}), [])
        self.assertEqual(resolve_graph_agent_order({"nodes": []}), [])


if __name__ == "__main__":
    unittest.main()
