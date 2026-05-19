from __future__ import annotations

from app.services.skill_files import load_skill_packages_from_disk, sync_skill_package_to_disk
from app.services.workflow_template_files import ensure_scenario_templates_dir
from app.services.catalog_records import SkillPackageRecord


def seed_configuration_catalog() -> None:
    """Ensure file-backed configuration catalogs exist on disk."""
    ensure_scenario_templates_dir()
    if not load_skill_packages_from_disk():
        for package in _default_skill_packages():
            sync_skill_package_to_disk(package)


def _default_skill_packages() -> list[SkillPackageRecord]:
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
        SkillPackageRecord(
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
