"""Tests for InstanceConfig normalization."""

from __future__ import annotations

import unittest

from shared.instance_config import (
    instance_config_view,
    materialize_stored_config,
    migrate_legacy_agent_wire_config,
    require_workflow_task,
    resolve_subject_name,
    to_agent_run_config,
)


class InstanceConfigTests(unittest.TestCase):
    def test_legacy_target_company_migrates_to_subject_on_view(self) -> None:
        stored = {
            "target_company": {"name": "Acme Corp", "aliases": ["Acme"]},
            "workflow_template_id": "workflow_research_demo",
            "resources": {"uploaded_files": []},
        }
        view = instance_config_view(stored)
        self.assertNotIn("target_company", view)
        self.assertNotIn("due_diligence", view.get("extensions", {}))
        self.assertEqual(view["extensions"]["subject"]["name"], "Acme Corp")

    def test_workflow_task_round_trip_and_agent_injection(self) -> None:
        task = "Analyze growth drivers for Example Robotics and deliver a memo."
        payload = {
            "workflow_template_id": "workflow_research_demo",
            "resources": {"uploaded_files": []},
            "extensions": {"workflow_task": {"description": task}},
        }
        stored = materialize_stored_config(payload)
        self.assertEqual(stored["extensions"]["workflow_task"]["description"], task)
        self.assertEqual(stored["extensions"]["subject"]["name"], "Analyze growth drivers for Example Robotics and deliver a memo.")
        self.assertEqual(resolve_subject_name(stored), "Analyze growth drivers for Example Robotics and deliver a memo.")
        agent_cfg = to_agent_run_config(stored)
        self.assertEqual(agent_cfg["workflow_task"], task)
        self.assertIn("Example Robotics", agent_cfg["subject"]["name"])

    def test_subject_extension_round_trip(self) -> None:
        payload = {
            "workflow_template_id": "workflow_research_demo",
            "resources": {"uploaded_files": ["file_a"]},
            "extensions": {
                "subject": {"name": "Market Scan Q1", "aliases": [], "kind": "research_topic"},
                "workflow_task": {"description": "Market Scan Q1"},
            },
        }
        stored = materialize_stored_config(payload)
        self.assertNotIn("target_company", stored)
        self.assertEqual(resolve_subject_name(stored), "Market Scan Q1")
        agent_cfg = to_agent_run_config(stored)
        self.assertEqual(agent_cfg["subject"]["name"], "Market Scan Q1")

    def test_require_workflow_task_rejects_empty_payload(self) -> None:
        with self.assertRaises(ValueError):
            require_workflow_task(
                {"workflow_template_id": "workflow_research_demo", "extensions": {}},
            )

    def test_migrate_legacy_agent_wire_config(self) -> None:
        wire = {
            "target_company": {"name": "Legacy Subject", "aliases": []},
            "workflow_template_id": "workflow_research_demo",
            "workflow_task": "Already normalized task.",
            "resources": {},
        }
        migrated = migrate_legacy_agent_wire_config(wire)
        self.assertEqual(migrated["workflow_task"], "Already normalized task.")
        self.assertEqual(migrated["subject"]["name"], "Legacy Subject")


if __name__ == "__main__":
    unittest.main()
