"""Backward-compatible re-exports; prefer instance_config_merge."""

from __future__ import annotations

from app.services.instance_config_merge import merged_instance_config_with_engagement_resources

merged_company_config_with_engagement_resources = merged_instance_config_with_engagement_resources

__all__ = ["merged_company_config_with_engagement_resources"]
