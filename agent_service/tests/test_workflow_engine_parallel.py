from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agent_service.api.schemas import AgentResult, RunInstanceConfig, Subject
from agent_service.workflows.workflow_engine import WorkflowEngine


def _minimal_snapshot(*, graph: dict) -> dict:
    return {
        "workflow": {
            "id": "wf_test",
            "name": "Test",
            "graph": graph,
            "runtime": {"command_execution": "host"},
        },
        "agent_templates": [
            {
                "id": "AgentA",
                "role": "a",
                "prompt": "do a",
                "skill_package_ids": [],
                "tool_ids": [],
                "resource_ids": [],
                "react_config": {},
            },
            {
                "id": "AgentB",
                "role": "b",
                "prompt": "do b",
                "skill_package_ids": [],
                "tool_ids": [],
                "resource_ids": [],
                "react_config": {},
            },
        ],
        "skill_packages": [],
        "tools": [],
        "resources": [],
    }


class WorkflowEngineParallelTests(unittest.TestCase):
    @patch("agent_service.workflows.workflow_engine.build_session_recorder")
    @patch("agent_service.workflows.workflow_engine.notify_run_progress")
    @patch("agent_service.workflows.workflow_engine.ConfiguredAgentRunner")
    def test_parallel_level_assigns_unique_step_ids(
        self,
        runner_cls: MagicMock,
        _notify: MagicMock,
        recorder_factory: MagicMock,
    ) -> None:
        recorder_factory.return_value = MagicMock()
        runner = MagicMock()
        runner.run.return_value = AgentResult(agent="x", status="completed")
        runner_cls.return_value = runner

        graph = {
            "nodes": [
                {"id": "n1", "agent_template_id": "AgentA"},
                {"id": "n2", "agent_template_id": "AgentB"},
            ],
            "edges": [],
            "entry_node": "n1",
            "report_node": "n2",
        }
        snapshot = _minimal_snapshot(graph=graph)
        instance_config = RunInstanceConfig(
            subject=Subject(name="Co"),
            workflow_template_id="wf_test",
            workflow_task="task",
        )
        engine = WorkflowEngine()
        result = engine.run(
            "eng_1",
            instance_config,
            workflow_snapshot=snapshot,
            user_id="user_1",
            run_id_override="run_parallel_test",
        )
        self.assertEqual(result.status, "completed")
        step_ids = [s.id for s in result.steps]
        self.assertEqual(len(step_ids), 2)
        self.assertEqual(len(set(step_ids)), 2)


if __name__ == "__main__":
    unittest.main()
