from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from agentscope.tool import Toolkit
import frontmatter

from app.core.auth import require_roles
from app.models.entities import User
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
from app.services.workflow_template_files import clone_workflow_template as clone_workflow_on_disk
from app.services.workflow_template_files import create_agent as create_agent_on_disk
from app.services.workflow_template_files import create_workflow_template as create_workflow_on_disk
from app.services.workflow_template_files import delete_workflow_template as delete_workflow_on_disk
from app.services.workflow_template_files import list_union_agent_reads as list_agent_template_reads_from_disk
from app.services.workflow_template_files import list_workflow_reads_for_api as list_workflow_reads_from_disk
from app.services.workflow_template_files import publish_agent as publish_agent_on_disk
from app.services.workflow_template_files import publish_workflow_template as publish_workflow_on_disk
from app.services.workflow_template_files import update_agent as update_agent_on_disk
from app.services.workflow_template_files import update_workflow_template as update_workflow_on_disk
from app.services.skill_files import skill_package_disk_path
from app.services.skill_zip_import import skill_package_create_from_zip
from app.services.skill_catalog import (
    create_skill_package,
    ensure_unique_skill_catalog_fields,
    get_skill_package,
    list_skill_packages,
    update_skill_package,
)
from app.services.tool_catalog import create_tool_config, list_tool_configs, update_tool_config
from app.services.platform_resource_catalog import (
    BuiltinOnlyResourceConfigError,
    create_resource_config_overlay,
    delete_resource_config_overlay,
    list_resource_config_reads,
    update_resource_config_overlay,
)


router = APIRouter(tags=["configuration"])


def _skill_read(record) -> SkillPackageRead:
    return SkillPackageRead.model_validate(record)


def _tool_read(record) -> ToolConfigRead:
    return ToolConfigRead.model_validate(record)


@router.get("/skills", response_model=list[SkillPackageRead])
def list_skills(
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[SkillPackageRead]:
    return [_skill_read(row) for row in list_skill_packages(only_enabled=user.role != "admin")]


@router.post("/skills/debug", response_model=SkillDebugRead)
def debug_skill_draft(
    payload: SkillPackageCreate,
    _: User = Depends(require_roles("admin")),
) -> SkillDebugRead:
    return _debug_skill_package(
        directory_name=payload.directory_name,
        skill_md=payload.skill_md,
        package_files=payload.package_files,
        resources_manifest=payload.resources_manifest,
    )


@router.post("/skills/import-zip", response_model=SkillPackageRead)
async def import_skill_zip(
    file: UploadFile = File(...),
    directory_name: str | None = Form(None),
    _: User = Depends(require_roles("admin")),
) -> SkillPackageRead:
    fname = file.filename or ""
    if not fname.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传扩展名为 .zip 的 Skill 压缩包（单包内含 SKILL.md）")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")
    override = directory_name.strip() if directory_name and directory_name.strip() else None
    payload = skill_package_create_from_zip(raw, directory_name_override=override)
    payload = ensure_unique_skill_catalog_fields(payload)
    return _skill_read(create_skill_package(payload))


@router.get("/skills/{skill_id}", response_model=SkillPackageRead)
def get_skill(
    skill_id: str,
    _: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> SkillPackageRead:
    return _skill_read(get_skill_package(skill_id))


@router.post("/skills", response_model=SkillPackageRead)
def create_skill(
    payload: SkillPackageCreate,
    _: User = Depends(require_roles("admin")),
) -> SkillPackageRead:
    return _skill_read(create_skill_package(payload))


@router.patch("/skills/{skill_id}", response_model=SkillPackageRead)
def update_skill(
    skill_id: str,
    payload: SkillPackageUpdate,
    _: User = Depends(require_roles("admin")),
) -> SkillPackageRead:
    return _skill_read(update_skill_package(skill_id, payload))


@router.post("/skills/{skill_id}/debug", response_model=SkillDebugRead)
def debug_skill(
    skill_id: str,
    _: User = Depends(require_roles("admin")),
) -> SkillDebugRead:
    item = get_skill_package(skill_id)
    return _debug_skill_package(
        directory_name=item.directory_name,
        skill_md=item.skill_md,
        package_files=item.package_files or {},
        resources_manifest=item.resources_manifest,
    )


@router.get("/tools/configs", response_model=list[ToolConfigRead])
def list_tool_configs_route(
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[ToolConfigRead]:
    return [_tool_read(row) for row in list_tool_configs(only_enabled=user.role != "admin")]


@router.post("/tools/configs", response_model=ToolConfigRead)
def create_tool_config_route(
    payload: ToolConfigCreate,
    _: User = Depends(require_roles("admin")),
) -> ToolConfigRead:
    return _tool_read(create_tool_config(payload))


@router.patch("/tools/configs/{tool_id}", response_model=ToolConfigRead)
def update_tool_config_route(
    tool_id: str,
    payload: ToolConfigUpdate,
    _: User = Depends(require_roles("admin")),
) -> ToolConfigRead:
    return _tool_read(update_tool_config(tool_id, payload))


@router.get("/resources/configs", response_model=list[ResourceConfigRead])
def list_resource_configs(
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[ResourceConfigRead]:
    return list_resource_config_reads(only_enabled=user.role != "admin")


@router.post("/resources/configs", response_model=ResourceConfigRead)
def create_resource_config(
    payload: ResourceConfigCreate,
    _: User = Depends(require_roles("admin")),
) -> ResourceConfigRead:
    try:
        return create_resource_config_overlay(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Resource config id already exists in data overlay") from exc


@router.patch("/resources/configs/{resource_id}", response_model=ResourceConfigRead)
def update_resource_config(
    resource_id: str,
    payload: ResourceConfigUpdate,
    _: User = Depends(require_roles("admin")),
) -> ResourceConfigRead:
    try:
        return update_resource_config_overlay(resource_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Resource config not found") from exc


@router.delete("/resources/configs/{resource_id}", status_code=204)
def delete_resource_config(
    resource_id: str,
    _: User = Depends(require_roles("admin")),
) -> None:
    try:
        delete_resource_config_overlay(resource_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Resource config not found") from exc
    except BuiltinOnlyResourceConfigError as exc:
        raise HTTPException(
            status_code=403,
            detail="Built-in resource configs cannot be deleted from the API; only data-store overlays can be removed.",
        ) from exc


@router.get("/agent-templates", response_model=list[AgentTemplateRead])
def list_agent_templates(
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[AgentTemplateRead]:
    return list_agent_template_reads_from_disk(only_enabled_non_admin=user.role != "admin", user_id=user.id)


@router.post("/agent-templates", response_model=AgentTemplateRead)
def create_agent_template(
    payload: AgentTemplateCreate,
    user: User = Depends(require_roles("admin")),
) -> AgentTemplateRead:
    return create_agent_on_disk(payload, user_id=user.id)


@router.patch("/agent-templates/{agent_id}", response_model=AgentTemplateRead)
def update_agent_template(
    agent_id: str,
    payload: AgentTemplateUpdate,
    user: User = Depends(require_roles("admin")),
) -> AgentTemplateRead:
    return update_agent_on_disk(agent_id, payload, user_id=user.id)


@router.post("/agent-templates/{agent_id}/publish", response_model=AgentTemplateRead)
def publish_agent_template(
    agent_id: str,
    user: User = Depends(require_roles("admin")),
) -> AgentTemplateRead:
    return publish_agent_on_disk(agent_id, user_id=user.id)


@router.get("/workflow-templates", response_model=list[WorkflowTemplateRead])
def list_workflow_templates(
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[WorkflowTemplateRead]:
    return list_workflow_reads_from_disk(include_drafts=user.role == "admin", user_id=user.id)


@router.post("/workflow-templates", response_model=WorkflowTemplateRead)
def create_workflow_template(
    payload: WorkflowTemplateCreate,
    user: User = Depends(require_roles("admin")),
) -> WorkflowTemplateRead:
    return create_workflow_on_disk(payload, user_id=user.id)


@router.patch("/workflow-templates/{workflow_id}", response_model=WorkflowTemplateRead)
def update_workflow_template(
    workflow_id: str,
    payload: WorkflowTemplateUpdate,
    user: User = Depends(require_roles("admin")),
) -> WorkflowTemplateRead:
    return update_workflow_on_disk(workflow_id, payload, user_id=user.id)


@router.post("/workflow-templates/{workflow_id}/publish", response_model=WorkflowTemplateRead)
def publish_workflow_template(
    workflow_id: str,
    user: User = Depends(require_roles("admin")),
) -> WorkflowTemplateRead:
    return publish_workflow_on_disk(workflow_id, user_id=user.id)


@router.post("/workflow-templates/{workflow_id}/clone", response_model=WorkflowTemplateRead)
def clone_workflow_template(
    workflow_id: str,
    user: User = Depends(require_roles("admin")),
) -> WorkflowTemplateRead:
    return clone_workflow_on_disk(workflow_id, user_id=user.id)


@router.delete("/workflow-templates/{workflow_id}", status_code=204)
def delete_workflow_template(
    workflow_id: str,
    user: User = Depends(require_roles("admin")),
) -> Response:
    delete_workflow_on_disk(workflow_id, user_id=user.id)
    return Response(status_code=204)


def _debug_skill_package(
    directory_name: str,
    skill_md: str,
    package_files: dict[str, str],
    resources_manifest: dict,
) -> SkillDebugRead:
    checks: list[str] = []
    errors: list[str] = []
    metadata: dict = {}
    agent_skill_prompt: str | None = None
    checks.append(f"Fixed project directory: {skill_package_disk_path(directory_name)}")

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
            for file_name, content in package_files.items():
                if file_name != "SKILL.md":
                    _write_skill_file(skill_dir, file_name, content)
            for file_name in resources_manifest.get("files", []):
                if file_name not in {"SKILL.md", *package_files.keys()}:
                    _write_skill_file(skill_dir, str(file_name), "")
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


def _write_skill_file(skill_dir: Path, file_name: str, content: str) -> None:
    target = (skill_dir / file_name).resolve()
    if not target.is_relative_to(skill_dir.resolve()):
        raise ValueError(f"Skill file path escapes skill directory: {file_name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
