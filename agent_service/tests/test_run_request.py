"""Tests for agent run request config coalescing."""

from __future__ import annotations

import unittest

from agent_service.api.schemas import CompanyConfig, RunRequest


class RunRequestConfigTests(unittest.TestCase):
    def test_instance_config_coalesced_to_company_config(self) -> None:
        request = RunRequest.model_validate(
            {
                "engagement_id": "eng_1",
                "user_id": "user_1",
                "instance_config": {
                    "workflow_template_id": "workflow_research_demo",
                    "resources": {},
                    "extensions": {
                        "workflow_task": {"description": "Deliver a market scan report."},
                    },
                },
            }
        )
        cfg = request.resolved_company_config
        self.assertIsInstance(cfg, CompanyConfig)
        self.assertEqual(cfg.workflow_task, "Deliver a market scan report.")
        self.assertEqual(cfg.target_company.name, "Deliver a market scan report.")

    def test_company_config_wire_shape_not_renormalized(self) -> None:
        wire = {
            "target_company": {"name": "Subject", "aliases": []},
            "workflow_template_id": "workflow_research_demo",
            "resources": {},
            "workflow_task": "Already normalized task.",
        }
        request = RunRequest.model_validate(
            {
                "engagement_id": "eng_1",
                "user_id": "user_1",
                "company_config": wire,
            }
        )
        self.assertEqual(request.resolved_company_config.workflow_task, "Already normalized task.")


if __name__ == "__main__":
    unittest.main()
