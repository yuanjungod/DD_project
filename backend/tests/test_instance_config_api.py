"""Tests for InstanceConfig API models and store helpers."""

from __future__ import annotations

import unittest

from app.schemas.dto import EngagementCreate
from app.services.instance_config_store import stored_config_from_create


class InstanceConfigApiTests(unittest.TestCase):
    def test_create_accepts_legacy_company_config(self) -> None:
        body = EngagementCreate.model_validate(
            {
                "name": "DD App",
                "application_id": "app-dd",
                "company_config": {
                    "target_company": {"name": "Acme", "aliases": []},
                    "workflow_template_id": "standard_due_diligence",
                    "resources": {},
                },
            }
        )
        self.assertEqual(body.company_config.target_company.name, "Acme")

    def test_create_accepts_instance_config_subject(self) -> None:
        body = EngagementCreate.model_validate(
            {
                "name": "Research App",
                "application_id": "app-research",
                "instance_config": {
                    "workflow_template_id": "workflow_research_demo",
                    "resources": {},
                    "extensions": {
                        "subject": {"name": "Market Scan", "aliases": [], "kind": "research_topic"},
                    },
                },
            }
        )
        self.assertEqual(body.instance_config.workflow_template_id, "workflow_research_demo")

    def test_create_instance_config_requires_workflow_task(self) -> None:
        body = EngagementCreate.model_validate(
            {
                "name": "Research App",
                "application_id": "app-research",
                "instance_config": {
                    "workflow_template_id": "workflow_research_demo",
                    "resources": {},
                    "extensions": {},
                },
            }
        )
        with self.assertRaises(ValueError):
            stored_config_from_create(body)

    def test_create_task_first_round_trip(self) -> None:
        body = EngagementCreate.model_validate(
            {
                "name": "Research App",
                "application_id": "app-research",
                "instance_config": {
                    "workflow_template_id": "workflow_research_demo",
                    "resources": {},
                    "extensions": {
                        "workflow_task": {
                            "description": "Analyze growth drivers for Example Robotics.",
                        },
                    },
                },
            }
        )
        stored = stored_config_from_create(body)
        self.assertEqual(
            stored["extensions"]["workflow_task"]["description"],
            "Analyze growth drivers for Example Robotics.",
        )
        self.assertEqual(stored["extensions"]["subject"]["name"], "Analyze growth drivers for Example Robotics.")


if __name__ == "__main__":
    unittest.main()
