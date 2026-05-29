import unittest
from unittest.mock import MagicMock, patch

from agent_service.execution.context import RunExecutionContext
from agent_service.execution.runtime_config import WorkflowRuntimeConfig
from agent_service.execution.router import ExecutionRouter


class ExecutionRouterTests(unittest.TestCase):
    def test_host_mode_uses_host_executor(self) -> None:
        ctx = RunExecutionContext(
            runtime=WorkflowRuntimeConfig(command_execution="host"),
            user_id="user_a",
            workflow_template_id="tpl_x",
            engagement_id="eng_1",
            session_id="sess_1",
        )
        router = ExecutionRouter(ctx)
        host = MagicMock()
        host.run_shell_sync.return_value = {"ok": True}
        router._host = host
        result = router.execute_shell("echo hi")
        host.run_shell_sync.assert_called_once_with("echo hi")
        self.assertEqual(result, {"ok": True})

    def test_docker_mode_uses_docker_executor(self) -> None:
        ctx = RunExecutionContext(
            runtime=WorkflowRuntimeConfig(command_execution="docker"),
            user_id="user_a",
            workflow_template_id="tpl_x",
            engagement_id="eng_1",
            session_id="sess_1",
        )
        with patch("agent_service.execution.router.DockerExecutor") as docker_cls:
            docker = docker_cls.return_value
            docker.execute_shell.return_value = {"returncode": 0, "stdout": "hi"}
            router = ExecutionRouter(ctx)
            result = router.execute_shell("echo hi")
            docker.execute_shell.assert_called_once_with("echo hi")
            self.assertEqual(result["stdout"], "hi")


if __name__ == "__main__":
    unittest.main()
