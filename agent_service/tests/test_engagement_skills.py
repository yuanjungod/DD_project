import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_service.agents.react_runtime import AgentScopeReActRuntime
from agent_service.execution.context import RunExecutionContext
from agent_service.execution.engagement_skills import (
    load_engagement_skill_md,
    package_instructions_from_engagement,
    resolve_engagement_skill_dirs,
)
from agent_service.execution.runtime_config import WorkflowRuntimeConfig
from agent_service.workflows.config_loader import AgentDefinition


class EngagementSkillsTests(unittest.TestCase):
    def _docker_ctx(self, workflow_root: Path, engagement_id: str = "eng_test") -> RunExecutionContext:
        ctx = RunExecutionContext(
            runtime=WorkflowRuntimeConfig(command_execution="docker"),
            user_id="user_a",
            workflow_template_id="tpl_x",
            engagement_id=engagement_id,
            session_id="sess_1",
        )
        ctx.host_workflow_root = str(workflow_root.resolve())
        ctx.path_translator = ctx.path_translator.__class__(ctx.host_workflow_root)
        return ctx

    def test_resolve_engagement_skill_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engagement_id = "eng_abc"
            skill_dir = root / engagement_id / "shared" / "skills" / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            ctx = self._docker_ctx(root, engagement_id=engagement_id)
            packages = [{"id": "pkg1", "directory_name": "demo-skill", "skill_md": "ignored"}]
            dirs = resolve_engagement_skill_dirs(ctx, packages)
            self.assertEqual(len(dirs), 1)
            self.assertTrue((Path(dirs[0]) / "SKILL.md").is_file())

    def test_package_instructions_reads_disk_not_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engagement_id = "eng_abc"
            skill_dir = root / engagement_id / "shared" / "skills" / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# From disk\n", encoding="utf-8")
            ctx = self._docker_ctx(root, engagement_id=engagement_id)
            text = package_instructions_from_engagement(
                ctx,
                [{"id": "pkg1", "directory_name": "demo-skill", "skill_md": "# From snapshot\n"}],
            )
            self.assertIn("# From disk", text)
            self.assertNotIn("# From snapshot", text)

    def test_load_engagement_skill_md_missing_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._docker_ctx(Path(tmp))
            with self.assertRaises(FileNotFoundError):
                load_engagement_skill_md(ctx, "missing-skill")

    def test_docker_materialize_uses_engagement_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engagement_id = "eng_abc"
            skill_dir = root / engagement_id / "shared" / "skills" / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            ctx = self._docker_ctx(root, engagement_id=engagement_id)
            definition = AgentDefinition(
                name="agent_a",
                role="researcher",
                prompt="do work",
                prompt_text="do work",
                skill_packages=[{"id": "pkg1", "directory_name": "demo-skill", "skill_md": ""}],
            )
            with patch.object(AgentScopeReActRuntime, "_register_skill_packages"), patch.object(
                AgentScopeReActRuntime, "_register_tools"
            ), patch.object(AgentScopeReActRuntime, "_build_config", return_value={}):
                runtime = AgentScopeReActRuntime(
                    definition,
                    sys_prompt="sys",
                    execution_context=ctx,
                )
            self.assertEqual(len(runtime.skill_dirs), 1)
            self.assertTrue(str(skill_dir.resolve()) in runtime.skill_dirs[0])
            runtime.close()


if __name__ == "__main__":
    unittest.main()
