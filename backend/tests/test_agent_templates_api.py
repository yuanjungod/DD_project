"""Tests for agent template API validation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from app.models.entities import User


def _admin_user() -> User:
    return User(
        id="user_admin_test",
        email="admin@example.com",
        name="Admin",
        password_hash="x",
        role="admin",
    )


def test_create_agent_template_rejects_invalid_id() -> None:
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        client = TestClient(app)
        response = client.post(
            "/agent-templates",
            json={
                "id": "bad id",
                "name": "Bad Agent",
                "role": "test",
                "prompt": "hello",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
