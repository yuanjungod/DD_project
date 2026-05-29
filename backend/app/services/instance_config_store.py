"""Helpers for engagement create/update config payloads."""

from __future__ import annotations

from shared.instance_config import (
    materialize_stored_config,
    require_workflow_task,
    resolve_subject_name,
    resolve_workflow_template_id,
)

from app.schemas.dto import CompanyConfig, EngagementCreate, EngagementUpdate, InstanceConfig


def stored_config_from_instance(instance: InstanceConfig) -> dict:
    raw = instance.model_dump(mode="json")
    require_workflow_task(raw, allow_legacy=False)
    return materialize_stored_config(raw)


def stored_config_from_company(company: CompanyConfig) -> dict:
    raw = company.model_dump(mode="json")
    require_workflow_task(raw, allow_legacy=True)
    return materialize_stored_config(raw)


def stored_config_from_create(payload: EngagementCreate) -> dict:
    if payload.instance_config is not None:
        return stored_config_from_instance(payload.instance_config)
    if payload.company_config is not None:
        return stored_config_from_company(payload.company_config)
    raise ValueError("instance_config or company_config is required")


def stored_config_from_update(payload: EngagementUpdate) -> dict | None:
    if payload.instance_config is not None:
        return stored_config_from_instance(payload.instance_config)
    if payload.company_config is not None:
        return stored_config_from_company(payload.company_config)
    return None


def subject_name_from_stored(stored: dict) -> str:
    return resolve_subject_name(stored)


def workflow_template_id_from_stored(stored: dict) -> str:
    return resolve_workflow_template_id(stored)
