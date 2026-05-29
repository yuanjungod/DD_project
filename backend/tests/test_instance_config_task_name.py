from __future__ import annotations

import unittest

from shared.instance_config import materialize_stored_config, require_task_name, resolve_subject_name, resolve_task_name


class InstanceConfigTaskNameTests(unittest.TestCase):
    def test_require_task_name(self) -> None:
        with self.assertRaises(ValueError):
            require_task_name({"extensions": {"workflow_task": {"description": "Do work"}}})
        require_task_name(
            {
                "extensions": {
                    "task_name": "成长能力分析",
                    "workflow_task": {"description": "Analyze growth."},
                }
            }
        )

    def test_resolve_subject_name_prefers_task_name(self) -> None:
        stored = materialize_stored_config(
            {
                "workflow_template_id": "wf",
                "extensions": {
                    "task_name": "展示名称",
                    "workflow_task": {"description": "第一行不应作为标题\n第二行"},
                },
            }
        )
        self.assertEqual(resolve_task_name(stored), "展示名称")
        self.assertEqual(resolve_subject_name(stored), "展示名称")


if __name__ == "__main__":
    unittest.main()
