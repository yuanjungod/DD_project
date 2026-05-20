from __future__ import annotations

from app.services.workflow_template_files import ensure_scenario_templates_dir


def seed_configuration_catalog() -> None:
    """Ensure file-backed configuration catalogs exist on disk."""
    ensure_scenario_templates_dir()
    # Skill packages are user-managed under agent_service/skills/; no built-in seed.
