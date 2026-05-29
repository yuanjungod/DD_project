"""Stable subject / application identifiers for engagement versioning."""

from __future__ import annotations

import re
import unicodedata

_SLUG_SAFE = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")


def subject_key_from_name(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return "subject"
    normalized = unicodedata.normalize("NFKC", text).lower()
    slug = re.sub(r"[^\w\-]+", "-", normalized, flags=re.UNICODE).strip("-")
    return slug[:64] or "subject"


def normalize_application_id(raw: str) -> str:
    app_id = (raw or "").strip().lower()
    app_id = re.sub(r"[^a-z0-9_-]+", "-", app_id).strip("-")
    if not app_id or not _SLUG_SAFE.match(app_id):
        raise ValueError("application_id must match ^[a-z][a-z0-9_-]{0,62}$")
    return app_id


__all__ = ["normalize_application_id", "subject_key_from_name"]
