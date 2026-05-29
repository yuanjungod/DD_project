"""Tests for InstanceConfig API models."""

from __future__ import annotations

import unittest

from app.schemas.dto import EngagementCreate


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


if __name__ == "__main__":
    unittest.main()
