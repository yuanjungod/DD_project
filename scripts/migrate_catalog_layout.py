#!/usr/bin/env python3
"""One-time migration from flat agent/workflow-template YAML files to catalog layout."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OLD_AGENTS = ROOT / "agent_service" / "configs" / "agent_templates.yaml"
OLD_WORKFLOW_TEMPLATES = ROOT / "agent_service" / "configs" / "workflow_template_templates"
NEW_AGENTS = ROOT / "catalog" / "agents"
NEW_BUILTIN_WORKFLOW_TEMPLATES = ROOT / "catalog" / "workflow_templates"
NEW_DATA_WORKFLOW_TEMPLATES = ROOT / "data" / "dd_store" / "workflow_templates"

BUILTIN_IDS = {
    "standard_due_diligence",
    "financial_investment_due_diligence",
    "legal_compliance_due_diligence",
    "market_entry_due_diligence",
}


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded if isinstance(loaded, dict) else {}


def _write_agent(path: Path, payload: dict) -> None:
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False, width=4096)
    header = "# Agent template — global library entry. Scenario folders may copy this into their agents/ directory.\n\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + text, encoding="utf-8")


def _write_workflow_template(path: Path, payload: dict) -> None:
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False, width=4096)
    header = (
        "# Workflow template folder — workflow graph and metadata. "
        "Agent definitions for this workflow template live in ./agents/.\n\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + text, encoding="utf-8")


def migrate() -> None:
    if not OLD_AGENTS.is_file():
        print("No legacy agent_templates.yaml — skipping agent migration")
        agent_catalog = {}
    else:
        doc = _load_yaml(OLD_AGENTS)
        agent_catalog = {row["id"]: row for row in doc.get("agents", []) if isinstance(row, dict) and row.get("id")}
        NEW_AGENTS.mkdir(parents=True, exist_ok=True)
        for agent_id, row in sorted(agent_catalog.items()):
            target = NEW_AGENTS / f"{agent_id}.yaml"
            if not target.exists():
                _write_agent(target, copy.deepcopy(row))
                print(f"  agent -> {target.relative_to(ROOT)}")

    if not OLD_WORKFLOW_TEMPLATES.is_dir():
        print("No legacy workflow_template_templates/ — skipping workflow template migration")
        return

    for path in sorted(OLD_WORKFLOW_TEMPLATES.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        doc = _load_yaml(path)
        workflow = doc.get("workflow")
        if not isinstance(workflow, dict) or not workflow.get("id"):
            continue
        workflow_template_id = workflow["id"]
        if workflow_template_id in BUILTIN_IDS:
            workflow_template_root = NEW_BUILTIN_WORKFLOW_TEMPLATES / workflow_template_id
        else:
            workflow_template_root = NEW_DATA_WORKFLOW_TEMPLATES / workflow_template_id
        workflow_template_yaml = workflow_template_root / "workflow_template.yaml"
        if workflow_template_yaml.exists():
            print(f"  skip existing workflow template {workflow_template_id}")
            continue
        _write_workflow_template(workflow_template_yaml, {"version": doc.get("version", 1), "workflow": workflow})
        print(f"  workflow template -> {workflow_template_yaml.relative_to(ROOT)}")

        agents_dir = workflow_template_root / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        nodes = workflow.get("graph", {}).get("nodes", [])
        agent_ids = [node.get("agent_template_id") for node in nodes if node.get("agent_template_id")]
        for agent_id in agent_ids:
            row = agent_catalog.get(agent_id)
            if not row:
                print(f"    WARN missing agent {agent_id} for {workflow_template_id}")
                continue
            agent_path = agents_dir / f"{agent_id}.yaml"
            if not agent_path.exists():
                _write_agent(agent_path, copy.deepcopy(row))
                print(f"    agent copy -> {agent_path.relative_to(ROOT)}")

    # Move legacy session data into scenario folders when possible
    legacy_sessions = ROOT / "data" / "dd_store" / "agent_service" / "sessions"
    if legacy_sessions.is_dir():
        for project_dir in legacy_sessions.iterdir():
            if not project_dir.is_dir():
                continue
            for session_file in project_dir.glob("*.json"):
                try:
                    payload = json.loads(session_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                workflow_template_id = (
                    (payload.get("workflow_meta") or {}).get("workflow_id")
                    or (payload.get("company_config") or {}).get("workflow_template_id")
                    or (payload.get("company_config") or {}).get("workflow_id")
                    or "standard_due_diligence"
                )
                target_dir = _workflow_template_runs_target(workflow_template_id) / "_legacy" / project_dir.name
                _copy_run_tree(session_file, target_dir, project_dir)


    _migrate_user_scoped_runs()


def _migrate_user_scoped_runs() -> None:
    """Move pre-user-isolation runs/{project}/ into runs/_legacy/{project}/."""
    legacy_user = "_legacy"
    for workflow_templates_root in (NEW_BUILTIN_WORKFLOW_TEMPLATES, NEW_DATA_WORKFLOW_TEMPLATES):
        if not workflow_templates_root.is_dir():
            continue
        for workflow_template_dir in workflow_templates_root.iterdir():
            if not workflow_template_dir.is_dir():
                continue
            runs_root = workflow_template_dir / "runs"
            if not runs_root.is_dir():
                continue
            for child in runs_root.iterdir():
                if not child.is_dir() or child.name == legacy_user:
                    continue
                if not child.name.startswith("eng_"):
                    continue
                target = runs_root / legacy_user / child.name
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(child), str(target))
                print(f"  user-scope -> {target.relative_to(ROOT)}")


def _workflow_template_runs_target(workflow_template_id: str) -> Path:
    data_home = NEW_DATA_WORKFLOW_TEMPLATES / workflow_template_id
    catalog_home = NEW_BUILTIN_WORKFLOW_TEMPLATES / workflow_template_id
    if (data_home / "workflow_template.yaml").is_file():
        return data_home / "runs"
    if (catalog_home / "workflow_template.yaml").is_file():
        return catalog_home / "runs"
    return data_home / "runs"


def _copy_run_tree(session_file: Path, target_dir: Path, project_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / session_file.name
    if not target_file.exists():
        shutil.copy2(session_file, target_file)
        print(f"  session -> {target_file.relative_to(ROOT)}")
    outputs_src = project_dir / f"{session_file.stem}_outputs"
    if outputs_src.is_dir():
        target_outputs = target_dir / "outputs" / f"{session_file.stem}_outputs"
        if not target_outputs.exists():
            shutil.copytree(outputs_src, target_outputs)
            print(f"  outputs -> {target_outputs.relative_to(ROOT)}")
    nested_outputs = project_dir / "outputs"
    if nested_outputs.is_dir():
        for output_tree in nested_outputs.iterdir():
            target_outputs = target_dir / "outputs" / output_tree.name
            if not target_outputs.exists():
                shutil.copytree(output_tree, target_outputs)
                print(f"  outputs -> {target_outputs.relative_to(ROOT)}")


if __name__ == "__main__":
    print("Migrating catalog layout...")
    migrate()
    print("Done.")
