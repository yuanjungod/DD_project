"""Backward-compatible re-exports; prefer subject_identity."""

from __future__ import annotations

from app.services.subject_identity import normalize_application_id, subject_key_from_name

company_key_from_name = subject_key_from_name

__all__ = ["company_key_from_name", "normalize_application_id", "subject_key_from_name"]
