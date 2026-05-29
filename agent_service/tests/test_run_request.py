from __future__ import annotations

import unittest

from agent_service.api.schemas import RunInstanceConfig, RunRequest, Subject


class RunRequestTests(unittest.TestCase):
    def test_instance_config_normalized(self) -> None:
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
        cfg = request.resolved_instance_config
        self.assertIsInstance(cfg, RunInstanceConfig)
        self.assertEqual(cfg.workflow_task, "Deliver a market scan report.")
        self.assertEqual(cfg.subject.name, "Deliver a market scan report.")

    def test_legacy_company_config_wire_migrated(self) -> None:
        wire = {
            "target_company": {"name": "Subject", "aliases": []},
            "workflow_template_id": "workflow_research_demo",
            "workflow_task": "Already normalized task.",
            "resources": {},
        }
        request = RunRequest.model_validate(
            {
                "engagement_id": "eng_1",
                "user_id": "user_1",
                "company_config": wire,
            }
        )
        self.assertEqual(request.resolved_instance_config.workflow_task, "Already normalized task.")
        self.assertEqual(request.resolved_instance_config.subject.name, "Subject")


if __name__ == "__main__":
    unittest.main()
