"""Tests for workflow session id field compatibility."""

from __future__ import annotations

import unittest

from shared.session_fields import (
    LEGACY_DILIGENCE_SESSION_ID_FIELD,
    WORKFLOW_SESSION_ID_FIELD,
    coalesce_workflow_session_id,
    dual_write_session_id_fields,
)


class SessionFieldsTests(unittest.TestCase):
    def test_coalesce_prefers_workflow_session_id(self) -> None:
        value = coalesce_workflow_session_id(
            {WORKFLOW_SESSION_ID_FIELD: "sess_a", LEGACY_DILIGENCE_SESSION_ID_FIELD: "sess_b"}
        )
        self.assertEqual(value, "sess_a")

    def test_coalesce_reads_legacy_field(self) -> None:
        value = coalesce_workflow_session_id({LEGACY_DILIGENCE_SESSION_ID_FIELD: "sess_legacy"})
        self.assertEqual(value, "sess_legacy")

    def test_dual_write_emits_both_fields(self) -> None:
        payload = dual_write_session_id_fields("sess_1")
        self.assertEqual(payload[WORKFLOW_SESSION_ID_FIELD], "sess_1")
        self.assertEqual(payload[LEGACY_DILIGENCE_SESSION_ID_FIELD], "sess_1")


if __name__ == "__main__":
    unittest.main()
