from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from agent_service.api.main import app


class AgentServiceAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_unauthenticated(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_config_requires_api_key(self) -> None:
        response = self.client.get("/config")
        self.assertEqual(response.status_code, 401)

    def test_config_with_valid_api_key(self) -> None:
        response = self.client.get("/config", headers={"X-Agent-Api-Key": "local-dd-agent-api-key"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("agents", body)
        self.assertIn("workflows", body)


if __name__ == "__main__":
    unittest.main()
