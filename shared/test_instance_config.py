"""Tests for InstanceConfig normalization."""

from __future__ import annotations

import unittest

from shared.instance_config import (
    instance_config_view,
    materialize_stored_config,
    resolve_subject_name,
    to_agent_company_config,
)


class InstanceConfigTests(unittest.TestCase):
    def test_legacy_due_diligence_shape_unchanged_on_view(self) -> None:
        stored = {
            "target_company": {"name": "Acme Corp", "aliases": ["Acme"]},
            "workflow_template_id": "standard_due_diligence",
            "resources": {"uploaded_files": []},
        }
        view = instance_config_view(stored)
        self.assertEqual(view["target_company"]["name"], "Acme Corp")
        self.assertEqual(view["extensions"]["due_diligence"]["target_company"]["name"], "Acme Corp")

    def test_workflow_task_round_trip_and_agent_injection(self) -> None:
        task = "对 Acme Robotics 完成全面尽职调查，并输出投资备忘录与主要风险清单。"
        payload = {
            "workflow_template_id": "workflow_research_demo",
            "resources": {"uploaded_files": []},
            "extensions": {"workflow_task": {"description": task}},
        }
        stored = materialize_stored_config(payload)
        self.assertEqual(stored["extensions"]["workflow_task"]["description"], task)
        self.assertEqual(resolve_subject_name(stored), "对 Acme Robotics 完成全面尽职调查，并输出投资备忘录与主要风险清单。")
        agent_cfg = to_agent_company_config(stored)
        self.assertEqual(agent_cfg["workflow_task"], task)
        self.assertIn("Acme Robotics", agent_cfg["target_company"]["name"])

    def test_legacy_subject_becomes_workflow_task_fallback(self) -> None:
        payload = {
            "workflow_template_id": "workflow_research_demo",
            "resources": {"uploaded_files": ["file_a"]},
            "extensions": {
                "subject": {"name": "Market Scan Q1", "aliases": [], "kind": "research_topic"},
            },
        }
        stored = materialize_stored_config(payload)
        self.assertNotIn("target_company", stored)
        self.assertEqual(resolve_subject_name(stored), "Market Scan Q1")
        agent_cfg = to_agent_company_config(stored)
        self.assertEqual(agent_cfg["target_company"]["name"], "Market Scan Q1")

    def test_materialize_promotes_due_diligence_target_to_root(self) -> None:
        payload = {
            "workflow_template_id": "legal_compliance_due_diligence",
            "resources": {},
            "extensions": {
                "due_diligence": {"target_company": {"name": "LegalCo", "aliases": []}},
            },
        }
        stored = materialize_stored_config(payload)
        self.assertEqual(stored["target_company"]["name"], "LegalCo")


if __name__ == "__main__":
    unittest.main()
