from __future__ import annotations

import unittest

from app.services.workflow_snapshots import build_workflow_snapshot, _workflow_template_id_from_config


class WorkflowSnapshotTests(unittest.TestCase):
    def test_workflow_template_id_from_config_uses_template_id(self) -> None:
        config = {"workflow_template_id": "legal_compliance_due_diligence"}
        self.assertEqual(_workflow_template_id_from_config(config), "legal_compliance_due_diligence")

    def test_workflow_template_id_defaults_when_missing(self) -> None:
        self.assertEqual(_workflow_template_id_from_config({}), "standard_due_diligence")

    def test_build_standard_workflow_snapshot(self) -> None:
        snapshot = build_workflow_snapshot(
            {"workflow_template_id": "standard_due_diligence"},
        )
        self.assertEqual(snapshot["workflow"]["id"], "standard_due_diligence")
        self.assertGreater(len(snapshot["agent_templates"]), 0)
        self.assertIn("graph", snapshot["workflow"])
        agent_ids = [agent["id"] for agent in snapshot["agent_templates"]]
        self.assertEqual(agent_ids[0], "CoordinatorAgent")
        for agent in snapshot["agent_templates"]:
            self.assertIn("tool_ids", agent)
            self.assertNotIn("skill_ids", agent)

    def test_workflow_template_id_ignores_legacy_scope(self) -> None:
        config = {
            "workflow_template_id": "standard_due_diligence",
            "scope": {"workflow_id": "market_entry_due_diligence"},
        }
        self.assertEqual(_workflow_template_id_from_config(config), "standard_due_diligence")


if __name__ == "__main__":
    unittest.main()
