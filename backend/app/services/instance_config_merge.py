"""Merge filesystem-backed engagement resource records into instance_config.resources for agent runs."""

from __future__ import annotations

import copy
from typing import Any

from app.services.platform_uploads_store import iter_platform_upload_file_ids


def merged_instance_config_with_engagement_resources(
    instance_config: dict[str, Any],
    resource_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deep-copy instance_config and fold resource manifests into resources.* lists."""
    merged: dict[str, Any] = copy.deepcopy(instance_config) if instance_config else {}
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

    agent_scopes: list[dict[str, Any]] = []
    seen_scope_rows: set[str] = set()
    for scope in resources.get("agent_resource_scopes") or []:
        if isinstance(scope, dict):
            agent_scopes.append(scope)
            rid = scope.get("resource_id")
            if isinstance(rid, str):
                seen_scope_rows.add(rid)

    for row in sorted(resource_records, key=lambda r: str(r.get("created_at", ""))):
        meta = row["metadata_json"] if isinstance(row.get("metadata_json"), dict) else {}
        val = (str(row.get("value") or "")).strip()
        rtype = str(row.get("type", ""))
        rid = str(row.get("id", ""))
        if rtype == "trusted_source" and val:
            trusted[val] = None
        elif rtype == "blocked_source" and val:
            blocked[val] = None
        elif rtype == "competitor" and val:
            competitors[val] = None
        elif rtype == "file_reference" and val:
            files[val] = None
        elif rtype == "external_clue":
            if rid not in seen_clue_rows:
                clues.append(
                    {
                        "resource_id": rid,
                        "summary": val,
                        "category": meta.get("category") or "",
                        "priority": meta.get("priority") or "normal",
                        "source_label": meta.get("source_label") or "",
                        "notes": meta.get("notes") or "",
                    }
                )
                seen_clue_rows.add(rid)
        elif rtype == "metric":
            if rid not in seen_metric_rows:
                metrics.append(
                    {
                        "resource_id": rid,
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
                seen_metric_rows.add(rid)
        elif rtype == "agent_resource_scope":
            if rid not in seen_scope_rows:
                file_ids = meta.get("uploaded_file_ids") or []
                if isinstance(file_ids, str):
                    file_ids = [x.strip() for x in file_ids.split(",") if x.strip()]
                agent_scopes.append(
                    {
                        "resource_id": rid,
                        "agent_id": val,
                        "uploaded_file_ids": [str(x).strip() for x in file_ids if str(x).strip()],
                        "notes": meta.get("notes") or "",
                    }
                )
                seen_scope_rows.add(rid)

    resources["trusted_sources"] = list(trusted.keys())
    resources["blocked_sources"] = list(blocked.keys())
    resources["competitors"] = list(competitors.keys())
    for fid in iter_platform_upload_file_ids():
        files[fid] = None
    resources["uploaded_files"] = sorted(files.keys())
    resources["metrics"] = metrics
    resources["external_clues"] = clues
    resources["agent_resource_scopes"] = agent_scopes
    return merged


__all__ = ["merged_instance_config_with_engagement_resources"]
