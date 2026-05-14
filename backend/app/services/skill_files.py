from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from app.models.entities import SkillPackage


ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = ROOT / "agent_service" / "skills"


def sync_skill_package_to_disk(
    skill_package: SkillPackage,
    previous_directory_name: str | None = None,
) -> Path:
    """Write a skill package from the DB catalog into the project skills dir."""

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_dir = _safe_skill_dir(skill_package.directory_name)

    if previous_directory_name and previous_directory_name != skill_package.directory_name:
        previous_dir = _safe_skill_dir(previous_directory_name)
        if previous_dir.exists():
            shutil.rmtree(previous_dir)

    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True, exist_ok=True)

    _write_skill_file(skill_dir, "SKILL.md", skill_package.skill_md)
    for file_name, content in (skill_package.package_files or {}).items():
        if file_name != "SKILL.md":
            _write_skill_file(skill_dir, file_name, content)

    return skill_dir


def sync_all_skill_packages_to_disk(skill_packages: list[SkillPackage]) -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for skill_package in skill_packages:
        sync_skill_package_to_disk(skill_package)


def load_skill_packages_from_disk() -> list[SkillPackage]:
    """Load checked-in skill packages from agent_service/skills as the bootstrap source."""

    if not SKILLS_DIR.is_dir():
        return []

    packages: list[SkillPackage] = []
    for skill_md_path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill_dir = skill_md_path.parent
        skill_md = skill_md_path.read_text(encoding="utf-8")
        metadata = _frontmatter_metadata(skill_md)
        directory_name = skill_dir.name
        name = str(metadata.get("name") or directory_name)
        package_id = str(metadata.get("id") or f"skill_{name.replace('-', '_')}")
        package_files: dict[str, str] = {}
        file_names = ["SKILL.md"]
        for child in sorted(skill_dir.rglob("*")):
            if not child.is_file() or child.name == "SKILL.md":
                continue
            rel = child.relative_to(skill_dir).as_posix()
            file_names.append(rel)
            package_files[rel] = child.read_text(encoding="utf-8")
        packages.append(
            SkillPackage(
                id=package_id,
                name=name,
                description=str(metadata.get("description") or ""),
                directory_name=directory_name,
                skill_md=skill_md,
                package_files=package_files,
                resources_manifest={
                    "files": sorted(file_names),
                    "references": [],
                    "scripts": [],
                    "assets": [],
                },
                enabled=bool(metadata.get("enabled", True)),
            )
        )
    return packages


def skill_package_disk_path(directory_name: str) -> str:
    return str(_safe_skill_dir(directory_name))


def _safe_skill_dir(directory_name: str) -> Path:
    target = (SKILLS_DIR / directory_name).resolve()
    if not target.is_relative_to(SKILLS_DIR.resolve()):
        raise ValueError(f"Skill directory escapes skills root: {directory_name}")
    return target


def _write_skill_file(skill_dir: Path, file_name: str, content: str) -> None:
    target = (skill_dir / file_name).resolve()
    if not target.is_relative_to(skill_dir.resolve()):
        raise ValueError(f"Skill file path escapes skill directory: {file_name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(content), encoding="utf-8")


def _frontmatter_metadata(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    try:
        _, raw, _ = text.split("---", 2)
    except ValueError:
        return {}
    loaded = yaml.safe_load(raw)
    return loaded if isinstance(loaded, dict) else {}
