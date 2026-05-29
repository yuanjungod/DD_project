"""Tests for engagement session/run filesystem layout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_service import engagement_layout as layout


@pytest.fixture
def isolated_users_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    users = tmp_path / ".dd_project" / "users"
    users.mkdir(parents=True)

    class _Settings:
        repo_root = tmp_path

    monkeypatch.setattr(layout, "get_agent_settings", lambda: _Settings())
    monkeypatch.setattr(layout, "users_root", lambda: users)
    return users


def test_session_json_path_is_flat_under_runs(isolated_users_root: Path) -> None:
    path = layout.session_json_path(
        "standard_due_diligence",
        "user_a",
        "eng_1",
        "run_abc",
        "sess_1",
    )
    assert path == isolated_users_root / "user_a/workflows/standard_due_diligence/eng_1/sessions/sess_1/runs/run_abc.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    assert path.is_file()


def test_find_session_json_path_canonical(isolated_users_root: Path) -> None:
    run_path = layout.session_json_path(
        "standard_due_diligence",
        "user_a",
        "eng_1",
        "run_abc",
        "sess_1",
    )
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps({"run_id": "run_abc"}), encoding="utf-8")

    found = layout.find_session_json_path("standard_due_diligence", "user_a", "eng_1", "run_abc")
    assert found == run_path


def test_find_session_json_path_legacy_nested_layout(isolated_users_root: Path) -> None:
    legacy = (
        isolated_users_root
        / "user_a/workflows/standard_due_diligence/eng_1/sessions/sess_1/runs/standard_due_diligence/run_legacy.json"
    )
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"run_id": "run_legacy"}), encoding="utf-8")

    found = layout.find_session_json_path("standard_due_diligence", "user_a", "eng_1", "run_legacy")
    assert found == legacy


def test_list_session_files_includes_canonical_and_legacy(isolated_users_root: Path) -> None:
    canonical = layout.session_json_path(
        "standard_due_diligence",
        "user_a",
        "eng_1",
        "run_new",
        "sess_1",
    )
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("{}", encoding="utf-8")

    legacy = (
        isolated_users_root
        / "user_a/workflows/standard_due_diligence/eng_1/sessions/sess_2/runs/standard_due_diligence/run_old.json"
    )
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("{}", encoding="utf-8")

    ids = layout.list_session_files("standard_due_diligence", "user_a", "eng_1")
    assert ids == ["run_new", "run_old"]
