from __future__ import annotations

import unittest

from app.services.subject_identity import allocate_application_id, normalize_application_id


class SubjectIdentityTests(unittest.TestCase):
    def test_allocate_application_id_matches_slug_pattern(self) -> None:
        app_id = allocate_application_id()
        self.assertEqual(app_id, normalize_application_id(app_id))
        self.assertTrue(app_id.startswith("app_"))


if __name__ == "__main__":
    unittest.main()
