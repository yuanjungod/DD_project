"""Merge persisted project Resource rows into company_config.resources for Agent runs."""

from __future__ import annotations

import copy
from typing import Any

from app.models.entities import Resource


PROJECT_RESOURCE_TYPES = frozenset(
    {
        "trusted_source",
        "blocked_source",
        "competitor",
        "file_reference",
        "external_clue",
        "metric",
    }
)


def merged_company_config_with_project_resources(
    company_config: dict[str, Any],
    resource_rows: list[Resource],
) -> dict[str, Any]:
    """Deep-copy company_config and fold Resource ORM rows into resources.* lists."""
    merged: dict[str, Any] = copy.deepcopy(company_config) if company_config else {}
    resources = merged.setdefault("resources", {})
    if not isinstance(resources, dict):
        resources = {}
        merged["resources"] = resources

    trusted: dict[str, None] = {}
    blocked: dict[str, None] = {}
    competitors: dict[str, None] = {}
    files: dict[str, None] = {}
    for v in resources.get("trusted_sources") or []:
        if isinstance(v, str) and v.strip():
            trusted[v.strip()] = None
    for v in resources.get("blocked_sources") or []:
        if isinstance(v, str) and v.strip():
            blocked[v.strip()] = None
    for v in resources.get("competitors") or []:
        if isinstance(v, str) and v.strip():
            competitors[v.strip()] = None
    for v in resources.get("uploaded_files") or []:
        if isinstance(v, str) and v.strip():
            files[v.strip()] = None

    metrics: list[dict[str, Any]] = []
    seen_metric_rows: set[str] = set()
    for m in resources.get("metrics") or []:
        if isinstance(m, dict):
            metrics.append(m)
            rid = m.get("resource_id")
            if isinstance(rid, str):
                seen_metric_rows.add(rid)

    clues: list[dict[str, Any]] = []
    seen_clue_rows: set[str] = set()
    for c in resources.get("external_clues") or []:
        if isinstance(c, dict):
            clues.append(c)
            rid = c.get("resource_id")
            if isinstance(rid, str):
                seen_clue_rows.add(rid)

    for row in sorted(resource_rows, key=lambda r: r.created_at):
        meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        val = (row.value or "").strip()
        if row.type == "trusted_source" and val:
            trusted[val] = None
        elif row.type == "blocked_source" and val:
            blocked[val] = None
        elif row.type == "competitor" and val:
            competitors[val] = None
        elif row.type == "file_reference" and val:
            files[val] = None
        elif row.type == "external_clue":
            if row.id not in seen_clue_rows:
                clues.append(
                    {
                        "resource_id": row.id,
                        "summary": val,
                        "category": meta.get("category") or "",
                        "priority": meta.get("priority") or "normal",
                        "source_label": meta.get("source_label") or "",
                        "notes": meta.get("notes") or "",
                    }
                )
                seen_clue_rows.add(row.id)
        elif row.type == "metric":
            if row.id not in seen_metric_rows:
                metrics.append(
                    {
                        "resource_id": row.id,
                        "metric_code": val,
                        "name": meta.get("name") or val,
                        "unit": meta.get("unit") or "",
                        "description": meta.get("description") or "",
                        "category": meta.get("category") or "general",
                        "source_type": meta.get("source_type") or "manual",
                        "source_ref": meta.get("source_ref") or "",
                        "target_direction": meta.get("target_direction") or "unspecified",
                        "threshold": meta.get("threshold"),
                        "frequency": meta.get("frequency") or "",
                        "baseline_value": meta.get("baseline_value"),
                        "notes": meta.get("notes") or "",
                    }
                )
                seen_metric_rows.add(row.id)

    resources["trusted_sources"] = list(trusted.keys())
    resources["blocked_sources"] = list(blocked.keys())
    resources["competitors"] = list(competitors.keys())
    resources["uploaded_files"] = list(files.keys())
    resources["metrics"] = metrics
    resources["external_clues"] = clues
    return merged
