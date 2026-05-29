"""Tests for workflow task injection in agent prompts."""

from __future__ import annotations

import unittest

from agent_service.agents.react_runtime import AgentScopeReActRuntime
from agent_service.api.schemas import CompanyConfig, TargetCompany
from agent_service.workflows.config_loader import AgentDefinition


class ReactRuntimeTaskMessageTests(unittest.TestCase):
    def test_task_message_includes_workflow_goal_without_run_subject(self) -> None:
        runtime = AgentScopeReActRuntime(
            AgentDefinition(
                name="DemoAgent",
                role="demo",
                prompt="Do the work.",
            ),
            sys_prompt="System",
            tool_executor=lambda _tool_id, _payload: {},
        )
        company_config = CompanyConfig(
            target_company=TargetCompany(name="Example", aliases=[]),
            workflow_template_id="workflow_research_demo",
            workflow_task="Analyze growth drivers for Example Robotics.",
        )
        message = runtime._build_task_message(company_config, [])
        self.assertIn("## 本次工作流最终目标", message)
        self.assertIn("Analyze growth drivers for Example Robotics.", message)
        self.assertNotIn("run_subject（运行主体）", message)

    def test_task_message_keeps_run_subject_when_task_missing(self) -> None:
        runtime = AgentScopeReActRuntime(
            AgentDefinition(
                name="DemoAgent",
                role="demo",
                prompt="Do the work.",
            ),
            sys_prompt="System",
            tool_executor=lambda _tool_id, _payload: {},
        )
        company_config = CompanyConfig(
            target_company=TargetCompany(name="Legacy Subject", aliases=[]),
            workflow_template_id="workflow_research_demo",
        )
        message = runtime._build_task_message(company_config, [])
        self.assertIn("run_subject（运行主体）", message)
        self.assertNotIn("## 本次工作流最终目标", message)


if __name__ == "__main__":
    unittest.main()
