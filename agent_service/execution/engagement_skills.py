from __future__ import annotations

from pathlib import Path

from agent_service.execution.context import RunExecutionContext


def skill_package_directory_name(package: dict) -> str:
    return str(package.get("directory_name") or package.get("name") or package["id"]).strip()


def engagement_shared_skills_root(ctx: RunExecutionContext) -> Path:
    return Path(ctx.host_workflow_root) / ctx.engagement_id / "shared" / "skills"


def engagement_skill_dir(ctx: RunExecutionContext, package: dict) -> Path:
    directory_name = skill_package_directory_name(package)
    if not directory_name:
        raise ValueError("Skill package is missing directory_name")
    skill_dir = engagement_shared_skills_root(ctx) / directory_name
    if not skill_dir.is_relative_to(engagement_shared_skills_root(ctx).resolve()):
        raise ValueError(f"Skill directory escapes engagement skills root: {directory_name}")
    return skill_dir


def load_engagement_skill_md(ctx: RunExecutionContext, directory_name: str) -> str:
    skill_md = engagement_shared_skills_root(ctx) / directory_name / "SKILL.md"
    if not skill_md.is_file():
        root = engagement_shared_skills_root(ctx)
        raise FileNotFoundError(
            f"SKILL.md not found for skill {directory_name!r} under {root} "
            "(Docker mode only uses engagement shared/skills copies)"
        )
    return skill_md.read_text(encoding="utf-8")


def package_instructions_from_engagement(
    ctx: RunExecutionContext,
    agent_skill_packages: list[dict],
) -> str:
    parts = [
        load_engagement_skill_md(ctx, skill_package_directory_name(package))
        for package in agent_skill_packages
    ]
    return "\n\n".join(part for part in parts if part.strip())


def resolve_engagement_skill_dirs(
    ctx: RunExecutionContext,
    skill_packages: list[dict],
) -> list[str]:
    skill_dirs: list[str] = []
    root = engagement_shared_skills_root(ctx)
    for package in skill_packages:
        directory_name = skill_package_directory_name(package)
        skill_dir = root / directory_name
        if not skill_dir.is_dir():
            raise FileNotFoundError(
                f"Skill directory {directory_name!r} not found under {root} "
                "(Docker mode only uses engagement shared/skills copies)"
            )
        if not (skill_dir / "SKILL.md").is_file():
            raise FileNotFoundError(f"SKILL.md missing in engagement skill directory: {skill_dir}")
        skill_dirs.append(str(skill_dir.resolve()))
    return skill_dirs
