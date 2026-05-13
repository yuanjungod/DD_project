from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from agentscope.tool import Toolkit
import frontmatter

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.entities import AgentTemplate, ResourceConfig, SkillPackage, ToolConfig, User, WorkflowTemplate, new_id
from app.schemas import (
    AgentTemplateCreate,
    AgentTemplateRead,
    AgentTemplateUpdate,
    ResourceConfigCreate,
    ResourceConfigRead,
    ResourceConfigUpdate,
    SkillDebugRead,
    SkillPackageCreate,
    SkillPackageRead,
    SkillPackageUpdate,
    ToolConfigCreate,
    ToolConfigRead,
    ToolConfigUpdate,
    WorkflowTemplateCreate,
    WorkflowTemplateRead,
    WorkflowTemplateUpdate,
)


router = APIRouter(tags=["configuration"])


@router.get("/skills", response_model=list[SkillPackageRead])
def list_skills(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[SkillPackage]:
    query = db.query(SkillPackage)
    if user.role != "admin":
        query = query.filter(SkillPackage.enabled.is_(True))
    return query.order_by(SkillPackage.name).all()


@router.post("/skills/debug", response_model=SkillDebugRead)
def debug_skill_draft(
    payload: SkillPackageCreate,
    _: User = Depends(require_roles("admin")),
) -> SkillDebugRead:
    return _debug_skill_package(
        directory_name=payload.directory_name,
        skill_md=payload.skill_md,
        resources_manifest=payload.resources_manifest,
    )


@router.get("/skills/{skill_id}", response_model=SkillPackageRead)
def get_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> SkillPackage:
    return _get_or_404(db, SkillPackage, skill_id, "Skill package")


@router.post("/skills", response_model=SkillPackageRead)
def create_skill(
    payload: SkillPackageCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> SkillPackage:
    item = SkillPackage(**_create_payload(payload))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/skills/{skill_id}", response_model=SkillPackageRead)
def update_skill(
    skill_id: str,
    payload: SkillPackageUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> SkillPackage:
    item = _get_or_404(db, SkillPackage, skill_id, "Skill package")
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.post("/skills/{skill_id}/debug", response_model=SkillDebugRead)
def debug_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> SkillDebugRead:
    item = _get_or_404(db, SkillPackage, skill_id, "Skill package")
    return _debug_skill_package(
        directory_name=item.directory_name,
        skill_md=item.skill_md,
        resources_manifest=item.resources_manifest,
    )


@router.get("/tools/configs", response_model=list[ToolConfigRead])
def list_tool_configs(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[ToolConfig]:
    query = db.query(ToolConfig)
    if user.role != "admin":
        query = query.filter(ToolConfig.enabled.is_(True))
    return query.order_by(ToolConfig.name).all()


@router.post("/tools/configs", response_model=ToolConfigRead)
def create_tool_config(
    payload: ToolConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> ToolConfig:
    item = ToolConfig(**_create_payload(payload))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/tools/configs/{tool_id}", response_model=ToolConfigRead)
def update_tool_config(
    tool_id: str,
    payload: ToolConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> ToolConfig:
    item = _get_or_404(db, ToolConfig, tool_id, "Tool config")
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.get("/resources/configs", response_model=list[ResourceConfigRead])
def list_resource_configs(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[ResourceConfig]:
    query = db.query(ResourceConfig)
    if user.role != "admin":
        query = query.filter(ResourceConfig.enabled.is_(True))
    return query.order_by(ResourceConfig.name).all()


@router.post("/resources/configs", response_model=ResourceConfigRead)
def create_resource_config(
    payload: ResourceConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> ResourceConfig:
    item = ResourceConfig(**_create_payload(payload))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/resources/configs/{resource_id}", response_model=ResourceConfigRead)
def update_resource_config(
    resource_id: str,
    payload: ResourceConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> ResourceConfig:
    item = _get_or_404(db, ResourceConfig, resource_id, "Resource config")
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.get("/agent-templates", response_model=list[AgentTemplateRead])
def list_agent_templates(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[AgentTemplate]:
    query = db.query(AgentTemplate)
    if user.role != "admin":
        query = query.filter(AgentTemplate.enabled.is_(True))
    return query.order_by(AgentTemplate.name).all()


@router.post("/agent-templates", response_model=AgentTemplateRead)
def create_agent_template(
    payload: AgentTemplateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> AgentTemplate:
    item = AgentTemplate(**_create_payload(payload))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/agent-templates/{agent_id}", response_model=AgentTemplateRead)
def update_agent_template(
    agent_id: str,
    payload: AgentTemplateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> AgentTemplate:
    item = _get_or_404(db, AgentTemplate, agent_id, "Agent template")
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.get("/workflow-templates", response_model=list[WorkflowTemplateRead])
def list_workflow_templates(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[WorkflowTemplate]:
    query = db.query(WorkflowTemplate)
    if user.role != "admin":
        query = query.filter(WorkflowTemplate.status == "published")
    return query.order_by(WorkflowTemplate.updated_at.desc()).all()


@router.post("/workflow-templates", response_model=WorkflowTemplateRead)
def create_workflow_template(
    payload: WorkflowTemplateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> WorkflowTemplate:
    data = _create_payload(payload)
    data["status"] = data.get("status") or "draft"
    item = WorkflowTemplate(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/workflow-templates/{workflow_id}", response_model=WorkflowTemplateRead)
def update_workflow_template(
    workflow_id: str,
    payload: WorkflowTemplateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> WorkflowTemplate:
    item = _get_or_404(db, WorkflowTemplate, workflow_id, "Workflow template")
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.post("/workflow-templates/{workflow_id}/publish", response_model=WorkflowTemplateRead)
def publish_workflow_template(
    workflow_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> WorkflowTemplate:
    item = _get_or_404(db, WorkflowTemplate, workflow_id, "Workflow template")
    item.status = "published"
    item.version += 1
    db.commit()
    db.refresh(item)
    return item


@router.post("/workflow-templates/{workflow_id}/clone", response_model=WorkflowTemplateRead)
def clone_workflow_template(
    workflow_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> WorkflowTemplate:
    source = _get_or_404(db, WorkflowTemplate, workflow_id, "Workflow template")
    clone = WorkflowTemplate(
        id=new_id("workflow_tpl"),
        name=f"{source.name} Copy",
        description=source.description,
        scenario=source.scenario,
        graph=source.graph,
        status="draft",
        version=1,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


def _create_payload(payload):
    data = payload.model_dump(exclude_none=True)
    return data


def _apply_updates(item, payload) -> None:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)


def _get_or_404(db: Session, model, item_id: str, label: str):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return item


def _debug_skill_package(
    directory_name: str,
    skill_md: str,
    resources_manifest: dict,
) -> SkillDebugRead:
    checks: list[str] = []
    errors: list[str] = []
    metadata: dict = {}
    agent_skill_prompt: str | None = None

    try:
        post = frontmatter.loads(skill_md)
        metadata = dict(post.metadata)
        checks.append("SKILL.md frontmatter parsed")
        if metadata.get("name"):
            checks.append("frontmatter.name present")
        else:
            errors.append("SKILL.md frontmatter must include name")
        if metadata.get("description"):
            checks.append("frontmatter.description present")
        else:
            errors.append("SKILL.md frontmatter must include description")
    except Exception as exc:
        errors.append(f"Failed to parse SKILL.md frontmatter: {exc}")

    try:
        with tempfile.TemporaryDirectory(prefix="skill_debug_") as temp_dir:
            skill_dir = Path(temp_dir) / directory_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
            for file_name in resources_manifest.get("files", []):
                if file_name != "SKILL.md":
                    target = skill_dir / str(file_name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("", encoding="utf-8")
            toolkit = Toolkit()
            toolkit.register_agent_skill(str(skill_dir))
            agent_skill_prompt = toolkit.get_agent_skill_prompt()
            checks.append("AgentScope Toolkit registered skill")
    except Exception as exc:
        errors.append(f"AgentScope skill registration failed: {exc}")

    return SkillDebugRead(
        valid=not errors,
        checks=checks,
        metadata=metadata,
        agent_skill_prompt=agent_skill_prompt,
        errors=errors,
    )
