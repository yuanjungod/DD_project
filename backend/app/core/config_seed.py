from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

import yaml

from app.models.entities import SkillPackage, ToolConfig
from app.services.skill_files import sync_all_skill_packages_to_disk
from app.services.workflow_template_files import ensure_workflow_template_bundles_migrated


ROOT = Path(__file__).resolve().parents[3]
AGENT_CONFIG_DIR = ROOT / "agent_service" / "configs"


def seed_configuration_catalog(db: Session) -> None:
    """Seed DB-backed catalog entries. Workflow + embedded agent defs live under workflow_templates/*.yaml."""
    ensure_configuration_schema(db)
    ensure_workflow_template_bundles_migrated()

    tools = _load_yaml(AGENT_CONFIG_DIR / "tools.yaml").get("tools", {})

    if db.query(ToolConfig).count() == 0:
        for tool_id, config in tools.items():
            db.add(
                ToolConfig(
                    id=tool_id,
                    name=tool_id,
                    description=config.get("description", ""),
                    implementation=config.get("implementation", ""),
                    input_schema={},
                    output_schema={},
                    requires_api_key=config.get("requires_api_key", False),
                    enabled=True,
                )
            )

    if db.query(SkillPackage).count() == 0:
        db.add_all(_default_skill_packages())

    db.commit()
    sync_all_skill_packages_to_disk(db.query(SkillPackage).all())

    from app.services.resource_fs_migration import migrate_if_needed

    migrate_if_needed(db.get_bind(), db)


def ensure_configuration_schema(db: Session) -> None:
    skill_columns = _table_columns(db, "skill_packages")
    if skill_columns and "package_files" not in skill_columns:
        try:
            db.execute(text("ALTER TABLE skill_packages ADD COLUMN package_files JSON DEFAULT '{}'"))
            db.commit()
        except Exception:
            db.rollback()


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def _default_skill_packages() -> list[SkillPackage]:
    packages = [
        (
            "skill_due_diligence_core",
            "due-diligence-core",
            "Guides evidence-first due diligence work with source-backed claims, confidence, conflicts, and report-ready findings.",
            "# Due Diligence Core\n\nAlways ground material claims in evidence IDs. Mark uncertainty explicitly. Preserve conflicts instead of hiding them.",
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
            "# Financial Signal Analysis\n\nSeparate facts from estimates. Do not infer precise numbers unless evidence provides them. Highlight missing disclosure.",
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
            "Guides concise due diligence report writing with executive summaries, risk levels, evidence IDs, and open diligence gaps.",
            "# Due Diligence Report Writing\n\nEvery section must include evidence IDs. Do not hide uncertainty. Use the requested report language.",
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
