from __future__ import annotations

import unittest

from app.schemas.dto import EngagementCreate, InstanceConfig, Resources


class InstanceConfigApiTests(unittest.TestCase):
    def test_create_requires_instance_config(self) -> None:
        payload = EngagementCreate(
            name="Acme run",
            instance_config=InstanceConfig(
                workflow_template_id="workflow_research_demo",
                resources=Resources(),
                extensions={
                    "task_name": "Acme quarterly review",
                    "workflow_task": {"description": "Analyze Acme quarterly results."},
                },
            ),
        )
        self.assertEqual(payload.instance_config.workflow_template_id, "workflow_research_demo")


if __name__ == "__main__":
    unittest.main()
