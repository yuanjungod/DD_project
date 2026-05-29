from __future__ import annotations

import unittest

from app.services.report_synthesis import synthesize_report_from_steps


class ReportSynthesisTests(unittest.TestCase):
    def test_synthesize_from_last_completed_step(self) -> None:
        report = synthesize_report_from_steps(
            [
                {"agent": "CoordinatorAgent", "status": "completed", "summary": "Plan ready"},
                {
                    "agent": "ReportWriterAgent",
                    "status": "completed",
                    "summary": "Final findings documented",
                    "result": {"output_readme_path": "/tmp/README.md"},
                },
            ]
        )
        self.assertIsNotNone(report)
        assert report is not None
        self.assertIn("ReportWriterAgent", report["title"])
        self.assertEqual(report["executive_summary"], "Final findings documented")

    def test_returns_none_without_completed_steps(self) -> None:
        self.assertIsNone(synthesize_report_from_steps([{"agent": "A", "status": "running"}]))


if __name__ == "__main__":
    unittest.main()
