from __future__ import annotations

import unittest

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


class SecurityTests(unittest.TestCase):
    def test_password_hash_roundtrip(self) -> None:
        hashed = hash_password("secret-pass")
        self.assertTrue(verify_password("secret-pass", hashed))
        self.assertFalse(verify_password("wrong-pass", hashed))

    def test_access_token_roundtrip(self) -> None:
        token = create_access_token("user-1", "admin")
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["role"], "admin")


if __name__ == "__main__":
    unittest.main()
