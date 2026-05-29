"""Tests for skill package id persistence across disk sync and reload."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastapi import HTTPException

from app.schemas.dto import SkillPackageCreate
from app.services.skill_catalog import create_skill_package, delete_skill_package, get_skill_package, list_skill_packages
from app.services import skill_files


@pytest.fixture
def isolated_skills_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    skills = tmp_path / "agent_service" / "skills"
    skills.mkdir(parents=True)
    monkeypatch.setattr(skill_files, "SKILLS_DIR", skills)
    monkeypatch.setattr(skill_files, "ROOT", tmp_path)
    return skills


def test_create_skill_package_get_by_id_roundtrip(isolated_skills_dir: Path) -> None:
    payload = SkillPackageCreate(
        name="cashflow",
        description="Cashflow analysis skill",
        directory_name="cashflow",
        skill_md="---\nname: cashflow\ndescription: Cashflow analysis skill\n---\n\n# Cashflow\n",
        package_files={"tests/test_contract.py": "def test_ok():\n    assert True\n"},
        resources_manifest={"files": ["SKILL.md", "tests/test_contract.py"]},
        enabled=True,
    )
    created = create_skill_package(payload)
    assert created.id.startswith("skill_pkg_")

    loaded = get_skill_package(created.id)
    assert loaded.id == created.id
    assert loaded.directory_name == "cashflow"

    skill_md = (isolated_skills_dir / "cashflow" / "SKILL.md").read_text(encoding="utf-8")
    assert f"id: {created.id}" in skill_md

    listed = list_skill_packages()
    assert any(row.id == created.id for row in listed)


def test_get_skill_package_falls_back_to_directory_name(isolated_skills_dir: Path) -> None:
    skill_dir = isolated_skills_dir / "legacy-skill"
    skill_dir.mkdir()
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: legacy-skill\ndescription: legacy\n---\n\n# Legacy\n",
        encoding="utf-8",
    )

    loaded = get_skill_package("legacy-skill")
    assert loaded.directory_name == "legacy-skill"
    assert loaded.id == "skill_legacy_skill"


def test_delete_skill_package_removes_directory(isolated_skills_dir: Path) -> None:
    payload = SkillPackageCreate(
        name="temp-skill",
        description="temporary",
        directory_name="temp-skill",
        skill_md="---\nname: temp-skill\ndescription: temporary\n---\n\n# Temp\n",
        package_files={},
        resources_manifest={"files": ["SKILL.md"]},
        enabled=True,
    )
    created = create_skill_package(payload)
    assert (isolated_skills_dir / "temp-skill" / "SKILL.md").is_file()

    delete_skill_package(created.id)
    assert not (isolated_skills_dir / "temp-skill").exists()

    with pytest.raises(HTTPException) as exc:
        get_skill_package(created.id)
    assert exc.value.status_code == 404
