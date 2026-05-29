import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_service.execution.context import RunExecutionContext
from agent_service.execution.docker_executor import DockerExecutor
from agent_service.execution.runtime_config import WorkflowRuntimeConfig


class DockerExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = RunExecutionContext(
            runtime=WorkflowRuntimeConfig(command_execution="docker"),
            user_id="user_a",
            workflow_template_id="tpl_x",
            engagement_id="eng_1",
            session_id="sess_1",
        )

    @patch("agent_service.execution.docker_executor.subprocess.run")
    @patch("agent_service.execution.docker_executor.ContainerManager")
    def test_execute_shell_invokes_docker_exec(self, mgr_cls: MagicMock, run_mock: MagicMock) -> None:
        mgr_cls.return_value.ensure_container.return_value = self.ctx.container_name
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = "hello\n"
        completed.stderr = ""
        run_mock.return_value = completed

        executor = DockerExecutor(self.ctx, container_manager=mgr_cls.return_value)
        result = executor.execute_shell("echo hello")

        self.assertEqual(result["returncode"], 0)
        self.assertIn("hello", result["stdout"])
        cmd = run_mock.call_args[0][0]
        self.assertEqual(cmd[0], "docker")
        self.assertEqual(cmd[1], "exec")
        self.assertIn(self.ctx.container_name, cmd)

    @patch("agent_service.execution.docker_executor.subprocess.run")
    @patch("agent_service.execution.docker_executor.ContainerManager")
    def test_view_text_file_uses_cat(self, mgr_cls: MagicMock, run_mock: MagicMock) -> None:
        mgr_cls.return_value.ensure_container.return_value = self.ctx.container_name
        host_file = (
            Path(self.ctx.host_workflow_root) / "eng_1" / "sessions" / "sess_1" / "runs" / "readme.txt"
        )
        host_file.parent.mkdir(parents=True, exist_ok=True)
        host_file.write_text("content", encoding="utf-8")

        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = "content"
        completed.stderr = ""
        run_mock.return_value = completed

        executor = DockerExecutor(self.ctx, container_manager=mgr_cls.return_value)
        container_path = self.ctx.path_translator.host_to_container(str(host_file))
        result = executor.view_text_file(container_path)
        self.assertEqual(result["stdout"], "content")
        self.assertEqual(run_mock.call_args[0][0][-2:], ["cat", container_path])


if __name__ == "__main__":
    unittest.main()
