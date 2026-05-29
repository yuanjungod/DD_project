"""Display-name normalization and duplicate checks for catalog entities."""

from __future__ import annotations


def normalize_catalog_name(value: str) -> str:
    return str(value or "").strip()


def catalog_name_key(value: str) -> str:
    return normalize_catalog_name(value).casefold()


def names_conflict(existing_name: str, candidate_name: str) -> bool:
    left = catalog_name_key(existing_name)
    right = catalog_name_key(candidate_name)
    return bool(left) and left == right
