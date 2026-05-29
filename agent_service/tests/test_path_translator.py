import unittest
from pathlib import Path

from agent_service.execution.path_translator import CONTAINER_WORKFLOW_ROOT, PathTranslator


class PathTranslatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.host_root = Path("/tmp/harness-test/users/user_a/workflows/tpl_x").resolve()
        self.translator = PathTranslator(str(self.host_root))

    def test_host_to_container(self) -> None:
        host = self.host_root / "eng_1" / "sessions" / "sess_1" / "runs" / "out"
        container = self.translator.host_to_container(str(host))
        self.assertEqual(
            container,
            f"{CONTAINER_WORKFLOW_ROOT}/eng_1/sessions/sess_1/runs/out",
        )

    def test_rejects_outside_workspace(self) -> None:
        with self.assertRaises(ValueError):
            self.translator.host_to_container("/etc/passwd")

    def test_container_to_host(self) -> None:
        host = self.translator.container_to_host(f"{CONTAINER_WORKFLOW_ROOT}/eng_1/shared")
        self.assertEqual(host, str((self.host_root / "eng_1" / "shared").resolve()))


if __name__ == "__main__":
    unittest.main()
