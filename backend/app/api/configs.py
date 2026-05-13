from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.entities import AgentTemplate, ResourceConfig, SkillConfig, User, WorkflowTemplate, new_id
from app.schemas import (
    AgentTemplateCreate,
    AgentTemplateRead,
    AgentTemplateUpdate,
    ResourceConfigCreate,
    ResourceConfigRead,
    ResourceConfigUpdate,
    SkillConfigCreate,
    SkillConfigRead,
    SkillConfigUpdate,
    WorkflowTemplateCreate,
    WorkflowTemplateRead,
    WorkflowTemplateUpdate,
)


router = APIRouter(tags=["configuration"])


@router.get("/skills", response_model=list[SkillConfigRead])
def list_skills(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[SkillConfig]:
    query = db.query(SkillConfig)
    if user.role != "admin":
        query = query.filter(SkillConfig.enabled.is_(True))
    return query.order_by(SkillConfig.name).all()


@router.post("/skills", response_model=SkillConfigRead)
def create_skill(
    payload: SkillConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> SkillConfig:
    item = SkillConfig(**_create_payload(payload))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/skills/{skill_id}", response_model=SkillConfigRead)
def update_skill(
    skill_id: str,
    payload: SkillConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> SkillConfig:
    item = _get_or_404(db, SkillConfig, skill_id, "Skill")
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
