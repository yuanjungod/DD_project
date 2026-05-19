from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.models.entities import SkillPackage, ToolConfig
from app.services.skill_files import load_skill_packages_from_disk, sync_all_skill_packages_to_disk
from app.services.tool_files import load_tool_configs_from_disk, sync_tool_configs_to_disk
from app.services.workflow_template_files import ensure_scenario_templates_dir

def seed_configuration_catalog(db: Session) -> None:
    """Seed DB-backed mirrors. Scenario graphs and agent definitions are separate file-backed catalogs."""
    ensure_configuration_schema(db)
    ensure_scenario_templates_dir()

    disk_tools = load_tool_configs_from_disk()
    if disk_tools:
        _upsert_tool_configs(db, disk_tools)

    disk_skill_packages = load_skill_packages_from_disk()
    if disk_skill_packages:
        _upsert_skill_packages(db, disk_skill_packages)
    elif db.query(SkillPackage).count() == 0:
        db.add_all(_default_skill_packages())

    db.commit()
    sync_tool_configs_to_disk(db.query(ToolConfig).all())
    sync_all_skill_packages_to_disk(db.query(SkillPackage).all())


def ensure_configuration_schema(db: Session) -> None:
    skill_columns = _table_columns(db, "skill_packages")
    if skill_columns and "package_files" not in skill_columns:
        try:
            db.execute(text("ALTER TABLE skill_packages ADD COLUMN package_files JSON DEFAULT '{}'"))
            db.commit()
        except Exception:
            db.rollback()


def _upsert_tool_configs(db: Session, disk_tools: list[ToolConfig]) -> None:
    for disk_tool in disk_tools:
        existing = db.get(ToolConfig, disk_tool.id)
        if existing is None:
            db.add(disk_tool)
            continue
        existing.name = disk_tool.name
        existing.description = disk_tool.description
        existing.implementation = disk_tool.implementation
        existing.input_schema = disk_tool.input_schema or {}
        existing.output_schema = disk_tool.output_schema or {}
        existing.requires_api_key = disk_tool.requires_api_key
        existing.enabled = disk_tool.enabled


def _upsert_skill_packages(db: Session, disk_skill_packages: list[SkillPackage]) -> None:
    for disk_package in disk_skill_packages:
        existing = db.get(SkillPackage, disk_package.id) or (
            db.query(SkillPackage).filter(SkillPackage.name == disk_package.name).first()
        )
        if existing is None:
            db.add(disk_package)
            continue
        existing.id = disk_package.id
        existing.name = disk_package.name
        existing.description = disk_package.description
        existing.directory_name = disk_package.directory_name
        existing.skill_md = disk_package.skill_md
        existing.package_files = disk_package.package_files or {}
        existing.resources_manifest = disk_package.resources_manifest or {}
        existing.enabled = disk_package.enabled


def _default_skill_packages() -> list[SkillPackage]:
    packages = [
        (
            "skill_due_diligence_core",
            "due-diligence-core",
            "Guides source-backed due diligence work with confidence, conflicts, and report-ready findings.",
            "# Due Diligence Core\n\nGround material claims in tool results or prior agent output folders. Mark uncertainty explicitly. Preserve conflicts instead of hiding them.",
        ),
        (
            "skill_legal_risk_review",
            "legal-risk-review",
            "Guides review of litigation, sanctions, penalties, intellectual property, compliance, and regulatory risks.",
            "# Legal Risk Review\n\nCheck litigation, administrative penalties, sanctions, IP disputes, data compliance, employment disputes, and regulatory exposure.",
        ),
        (
            "skill_financial_signal_analysis",
            "financial-signal-analysis",
            "Guides financial diligence over funding, revenue signals, cash flow hints, disclosure gaps, and business model quality.",
            "# Financial Signal Analysis\n\nSeparate facts from estimates. Do not infer precise numbers unless sources provide them. Highlight missing disclosure.",
        ),
        (
            "skill_market_competition_analysis",
            "market-competition-analysis",
            "Guides market, competitor, product positioning, defensibility, and industry risk analysis.",
            "# Market Competition Analysis\n\nUse configured competitors and public sources. Separate company-specific risks from industry-level risks.",
        ),
        (
            "skill_report_writing",
            "due-diligence-report-writing",
            "Guides concise due diligence report writing with executive summaries, risk levels, and open diligence gaps.",
            "# Due Diligence Report Writing\n\nReference prior agent output folders where relevant. Do not hide uncertainty. Use the requested report language.",
        ),
    ]
    return [
        SkillPackage(
            id=package_id,
            name=directory_name,
            description=description,
            directory_name=directory_name,
            skill_md=_skill_md(directory_name, description, body),
            package_files={},
            resources_manifest={"files": ["SKILL.md"], "references": [], "scripts": [], "assets": []},
            enabled=True,
        )
        for package_id, directory_name, description, body in packages
    ]


def _skill_md(name: str, description: str, body: str) -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def _table_columns(db: Session, table_name: str) -> set[str]:
    try:
        return {column["name"] for column in inspect(db.bind).get_columns(table_name)}
    except Exception:
        return set()
