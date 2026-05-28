from __future__ import annotations

import json
from pathlib import Path
from sys import path

import yaml


ROOT = Path(__file__).resolve().parents[1]
path.insert(0, str(ROOT))

from agent_service.api.schemas import CompanyConfig  # noqa: E402
from agent_service.workflows.due_diligence import DueDiligenceWorkflow  # noqa: E402


def main() -> None:
    config_path = ROOT / "shared" / "schemas" / "example_company_config.json"
    config = CompanyConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    result = DueDiligenceWorkflow().run("proj_demo", config, workflow_snapshot=_load_workflow_snapshot(config))
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": result.status,
                "steps": len(result.steps),
                "output_dirs": [
                    step.result.output_dir
                    for step in result.steps
                    if step.result and step.result.output_dir
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _workflow_template_root(workflow_template_id: str) -> Path | None:
    for base in (ROOT / "catalog" / "workflow_templates", ROOT / "data" / "dd_store" / "workflow_templates"):
        candidate = base / workflow_template_id
        if (candidate / "workflow_template.yaml").is_file():
            return candidate
    return None


def _load_workflow_snapshot(company_config: CompanyConfig) -> dict:
    workflow_id = company_config.workflow_template_id or company_config.workflow_id
    workflow_template_root = _workflow_template_root(workflow_id)
    if workflow_template_root is None:
        raise FileNotFoundError(f"Workflow template not found: {workflow_id}")
    workflow_doc = _load_yaml(workflow_template_root / "workflow_template.yaml")
    workflow = workflow_doc["workflow"]
    agents_dir = workflow_template_root / "agents"
    agent_catalog = {
        row["id"]: row
        for row in (
            _load_yaml(agent_path)
            for agent_path in sorted(agents_dir.glob("*.yaml"))
            if not agent_path.name.startswith("_")
        )
        if isinstance(row, dict) and row.get("id")
    }
    agent_ids = [node.get("agent_template_id", "") for node in workflow["graph"].get("nodes", [])]
    agents = [agent_catalog[agent_id] for agent_id in agent_ids if agent_id in agent_catalog]
    skill_package_ids = sorted({skill_id for agent in agents for skill_id in (agent.get("skill_package_ids") or [])})
    tool_ids = sorted({tool_id for agent in agents for tool_id in (agent.get("tool_ids") or agent.get("skill_ids") or [])})
    return {
        "workflow": {
            "id": workflow["id"],
            "name": workflow["name"],
            "description": workflow.get("description", ""),
            "workflow_template": workflow.get("workflow_template", "standard"),
            "version": workflow.get("version", 1),
            "graph": workflow["graph"],
        },
        "agent_templates": agents,
        "skill_packages": _load_skill_packages(skill_package_ids),
        "tools": _load_tools(tool_ids),
        "resources": [],
    }


def _load_tools(tool_ids: list[str]) -> list[dict]:
    raw_tools = _load_yaml(ROOT / "agent_service" / "configs" / "tools.yaml").get("tools", {})
    return [
        {
            "id": tool_id,
            "name": raw_tools.get(tool_id, {}).get("name") or tool_id,
            "description": raw_tools.get(tool_id, {}).get("description", ""),
            "implementation": raw_tools.get(tool_id, {}).get("implementation", ""),
            "input_schema": raw_tools.get(tool_id, {}).get("input_schema") or {},
            "output_schema": raw_tools.get(tool_id, {}).get("output_schema") or {},
            "requires_api_key": bool(raw_tools.get(tool_id, {}).get("requires_api_key", False)),
        }
        for tool_id in tool_ids
        if tool_id in raw_tools
    ]


def _load_skill_packages(skill_package_ids: list[str]) -> list[dict]:
    rows: list[dict] = []
    for skill_md_path in sorted((ROOT / "agent_service" / "skills").glob("*/SKILL.md")):
        skill_md = skill_md_path.read_text(encoding="utf-8")
        metadata = _frontmatter_metadata(skill_md)
        skill_id = metadata.get("id")
        if skill_id not in skill_package_ids:
            continue
        rows.append(
            {
                "id": skill_id,
                "name": metadata.get("name") or skill_md_path.parent.name,
                "description": metadata.get("description") or "",
                "directory_name": skill_md_path.parent.name,
                "skill_md": skill_md,
                "package_files": {},
                "resources_manifest": {"files": ["SKILL.md"], "references": [], "scripts": [], "assets": []},
            }
        )
    return rows


def _frontmatter_metadata(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    try:
        _, raw, _ = text.split("---", 2)
    except ValueError:
        return {}
    loaded = yaml.safe_load(raw)
    return loaded if isinstance(loaded, dict) else {}


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


if __name__ == "__main__":
    main()
