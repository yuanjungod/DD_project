from __future__ import annotations

import unittest

from agent_service.agents.react_runtime import AgentScopeReActRuntime
from agent_service.api.schemas import RunInstanceConfig, Subject
from agent_service.workflows.config_loader import AgentDefinition


class ReactTaskMessageTests(unittest.TestCase):
    def _runtime(self) -> AgentScopeReActRuntime:
        definition = AgentDefinition(
            name="agent_a",
            role="analyst",
            prompt="Do work",
            skill_packages=[],
            tools=[],
            react_config={},
        )
        return AgentScopeReActRuntime(definition, sys_prompt="sys", tool_executor=None)

    def test_workflow_task_block_when_present(self) -> None:
        runtime = self._runtime()
        instance_config = RunInstanceConfig(
            workflow_template_id="workflow_research_demo",
            workflow_task="Complete the market scan for Example Corp.",
            subject=Subject(name="Example Corp", aliases=[]),
        )
        message = runtime._build_task_message(instance_config, [])
        self.assertIn("本次工作流最终目标", message)
        self.assertIn("Complete the market scan for Example Corp.", message)
        self.assertNotIn("run_subject", message)

    def test_subject_block_when_task_missing(self) -> None:
        runtime = self._runtime()
        instance_config = RunInstanceConfig(
            workflow_template_id="workflow_research_demo",
            workflow_task="",
            subject=Subject(name="Legacy Subject", aliases=[]),
        )
        message = runtime._build_task_message(instance_config, [])
        self.assertIn("run_subject", message)
        self.assertIn("Legacy Subject", message)


if __name__ == "__main__":
    unittest.main()
