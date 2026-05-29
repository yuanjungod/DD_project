import unittest

from app.services.workflow_snapshots import build_workflow_snapshot


class WorkflowSnapshotRuntimeTests(unittest.TestCase):
    def test_snapshot_includes_runtime_from_published_bundle(self) -> None:
        company_config = {
            "workflow_template_id": "standard_due_diligence",
            "resources": {"uploaded_files": []},
            "extensions": {
                "workflow_task": {"description": "Analyze Example Corp"},
            },
        }
        snapshot = build_workflow_snapshot(company_config)
        runtime = snapshot["workflow"].get("runtime")
        self.assertIsInstance(runtime, dict)
        self.assertIn(runtime.get("command_execution", "host"), ("host", "docker"))


if __name__ == "__main__":
    unittest.main()
