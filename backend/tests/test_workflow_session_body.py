"""Tests for WorkflowSession API body compatibility."""

from __future__ import annotations

import unittest

from app.schemas.dto import StartAgentRunBody


class StartAgentRunBodyTests(unittest.TestCase):
    def test_accepts_workflow_session_id(self) -> None:
        body = StartAgentRunBody.model_validate(
            {"session_mode": "continue", "workflow_session_id": "sess_abc"}
        )
        self.assertEqual(body.workflow_session_id, "sess_abc")

    def test_coalesces_legacy_diligence_session_id(self) -> None:
        body = StartAgentRunBody.model_validate(
            {"session_mode": "continue", "diligence_session_id": "sess_legacy"}
        )
        self.assertEqual(body.workflow_session_id, "sess_legacy")

    def test_prefers_workflow_session_id_over_legacy(self) -> None:
        body = StartAgentRunBody.model_validate(
            {
                "session_mode": "continue",
                "workflow_session_id": "sess_new",
                "diligence_session_id": "sess_old",
            }
        )
        self.assertEqual(body.workflow_session_id, "sess_new")


if __name__ == "__main__":
    unittest.main()
