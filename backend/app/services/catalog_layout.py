"""Filesystem layout for the global agent library and per-workflow-template folders."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.services.fs_layout import dd_flow_users_dir

_WORKFLOW_TEMPLATE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_WORKFLOW_TEMPLATE_FILENAMES = ("workflow_template.yaml",)

_BUILTIN_WORKFLOW_TEMPLATE_IDS = frozenset(
    {
        "standard_due_diligence",
        "financial_investment_due_diligence",
        "legal_compliance_due_diligence",
        "market_entry_due_diligence",
    }
)


def repo_root() -> Path:
    return settings.repo_root


def data_root() -> Path:
    return settings.resolved_data_root


def assert_safe_workflow_template_id(workflow_template_id: str) -> str:
    if not workflow_template_id or not _WORKFLOW_TEMPLATE_ID_PATTERN.fullmatch(workflow_template_id):
        raise ValueError("Invalid workflow template id; use alphanumeric, hyphen, underscore only")
    return workflow_template_id


def global_agents_dir() -> Path:
    directory = repo_root() / "catalog" / "agents"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _workflow_template_yaml_in(directory: Path) -> Path | None:
    for filename in _WORKFLOW_TEMPLATE_FILENAMES:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def global_agent_path(agent_id: str) -> Path:
    assert_safe_workflow_template_id(agent_id)
    return global_agents_dir() / f"{agent_id}.yaml"


def builtin_workflow_templates_root() -> Path:
    directory = repo_root() / "catalog" / "workflow_templates"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def data_workflow_templates_root(user_id: str) -> Path:
    safe_user = assert_safe_workflow_template_id(user_id)
    directory = dd_flow_users_dir() / safe_user / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def data_agent_templates_root(user_id: str) -> Path:
    safe_user = assert_safe_workflow_template_id(user_id)
    directory = dd_flow_users_dir() / safe_user / "workflows" / "_agent_templates"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _all_user_workflow_template_roots() -> list[Path]:
    roots: list[Path] = []
    users_root = dd_flow_users_dir()
    if not users_root.is_dir():
        return roots
    for user_dir in users_root.iterdir():
        if not user_dir.is_dir():
            continue
        candidate = user_dir / "workflows"
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def _all_user_agent_template_roots() -> list[Path]:
    roots: list[Path] = []
    users_root = dd_flow_users_dir()
    if not users_root.is_dir():
        return roots
    for user_dir in users_root.iterdir():
        if not user_dir.is_dir():
            continue
        candidate = user_dir / "workflows" / "_agent_templates"
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def is_protected_workflow_template(workflow_template_id: str) -> bool:
    return workflow_template_id in _BUILTIN_WORKFLOW_TEMPLATE_IDS


def workflow_template_is_builtin(workflow_template_id: str) -> bool:
    assert_safe_workflow_template_id(workflow_template_id)
    return _workflow_template_yaml_in(builtin_workflow_templates_root() / workflow_template_id) is not None


def workflow_template_config_root(workflow_template_id: str, user_id: str | None = None) -> Path | None:
    assert_safe_workflow_template_id(workflow_template_id)
    try:
        return workflow_template_home(workflow_template_id, user_id=user_id)
    except FileNotFoundError:
        return None


def workflow_template_home(workflow_template_id: str, user_id: str | None = None) -> Path:
    """Canonical workflow template folder containing workflow_template.yaml and agents/."""
    assert_safe_workflow_template_id(workflow_template_id)
    if user_id:
        data_dir = data_workflow_templates_root(user_id) / workflow_template_id
        if _workflow_template_yaml_in(data_dir) is not None:
            return data_dir
    for root in _all_user_workflow_template_roots():
        data_dir = root / workflow_template_id
        if _workflow_template_yaml_in(data_dir) is not None:
            return data_dir
    catalog_dir = builtin_workflow_templates_root() / workflow_template_id
    if _workflow_template_yaml_in(catalog_dir) is not None:
        return catalog_dir
    raise FileNotFoundError(workflow_template_id)


def workflow_template_config_write_root(workflow_template_id: str, user_id: str) -> Path:
    """Directory for workflow_template.yaml and agents/ when creating or updating."""
    assert_safe_workflow_template_id(workflow_template_id)
    # Save/patch always writes to the caller user's private workflow area.
    # Publishing is responsible for syncing a chosen draft into catalog/.
    directory = data_workflow_templates_root(user_id) / workflow_template_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def workflow_template_yaml_path(workflow_template_id: str, user_id: str | None = None) -> Path:
    root = workflow_template_config_root(workflow_template_id, user_id=user_id)
    if root is None:
        raise FileNotFoundError(workflow_template_id)
    existing = _workflow_template_yaml_in(root)
    return existing or (root / "workflow_template.yaml")


def workflow_template_agents_dir(workflow_template_id: str, user_id: str | None = None) -> Path:
    root = workflow_template_config_root(workflow_template_id, user_id=user_id)
    if root is None:
        raise FileNotFoundError(workflow_template_id)
    directory = root / "agents"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def workflow_template_agents_write_dir(workflow_template_id: str, user_id: str) -> Path:
    directory = workflow_template_config_write_root(workflow_template_id, user_id=user_id) / "agents"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def workflow_template_agent_path(workflow_template_id: str, agent_id: str) -> Path:
    assert_safe_workflow_template_id(agent_id)
    return workflow_template_agents_dir(workflow_template_id) / f"{agent_id}.yaml"


def list_workflow_template_config_dirs(user_id: str | None = None) -> list[Path]:
    seen: dict[str, Path] = {}
    roots: list[Path] = [builtin_workflow_templates_root()]
    if user_id:
        roots.append(data_workflow_templates_root(user_id))
    else:
        roots.extend(_all_user_workflow_template_roots())
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if not _WORKFLOW_TEMPLATE_ID_PATTERN.fullmatch(child.name):
                continue
            if _workflow_template_yaml_in(child) is not None:
                seen[child.name] = child
    return sorted(seen.values(), key=lambda path: path.stat().st_mtime, reverse=True)


def protected_workflow_template_ids() -> frozenset[str]:
    return _BUILTIN_WORKFLOW_TEMPLATE_IDS


def user_agent_template_path(user_id: str, agent_id: str) -> Path:
    assert_safe_workflow_template_id(agent_id)
    return data_agent_templates_root(user_id) / f"{agent_id}.yaml"


def list_user_agent_template_paths(user_id: str | None = None) -> list[Path]:
    roots = [data_agent_templates_root(user_id)] if user_id else _all_user_agent_template_roots()
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.glob("*.yaml"):
            if path.name.startswith("_"):
                continue
            out.append(path)
    return sorted(out, key=lambda p: p.name.lower())
