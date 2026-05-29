"""Shared normalization helpers for agent template records."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


MAX_REACT_ITERS = 50


def default_model_config() -> dict[str, Any]:
    return {
        "baseUrl": "http://127.0.0.1:8080/v1",
        "apiKey": "yuanjun",
        "api": "openai-completions",
        "models": [
            {
                "id": "deepseek-v4-flash",
                "name": "deepseek-v4-flash",
                "reasoning": False,
                "input": ["text"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 128000,
                "maxTokens": 4096,
            }
        ],
    }


def default_react_config() -> dict[str, Any]:
    return {
        "max_iters": MAX_REACT_ITERS,
        "parallel_tool_calls": False,
        "model": default_model_config(),
    }


def normalize_max_iters(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = MAX_REACT_ITERS
    if parsed < 1:
        raise HTTPException(status_code=400, detail="react_config.max_iters must be at least 1")
    if parsed > MAX_REACT_ITERS:
        raise HTTPException(
            status_code=400,
            detail=f"react_config.max_iters must be at most {MAX_REACT_ITERS}",
        )
    return parsed


def merge_react_config(existing: dict[str, Any]) -> dict[str, Any]:
    merged = default_react_config()
    merged.update(existing)
    merged["model"] = existing.get("model") or merged["model"]
    return merged


def normalize_tool_ids(raw: dict[str, Any]) -> list[str]:
    """Resolve tool config ids from agent record."""
    tool_ids = raw.get("tool_ids") or []
    return [str(x).strip() for x in tool_ids if str(x).strip()]


def normalize_agent_record(raw: dict[str, Any]) -> dict[str, Any]:
    if "id" not in raw:
        raise HTTPException(status_code=400, detail="Each agent requires an id")
    data = dict(raw)
    data.pop("output_schema", None)
    data.pop("skill_ids", None)
    tid = data["id"]
    data.setdefault("name", tid)
    data.setdefault("role", "")
    data.setdefault("prompt", "")
    data["sub_agent_ids"] = [str(x).strip() for x in (data.get("sub_agent_ids") or []) if str(x).strip()]
    data.setdefault("skill_package_ids", [])
    data["tool_ids"] = normalize_tool_ids(data)
    if not data.get("resource_ids"):
        data["resource_ids"] = []
    puf = data.get("platform_upload_file_ids")
    data["platform_upload_file_ids"] = [str(x).strip() for x in (puf or []) if str(x).strip()]
    rc = data.get("react_config")
    if not rc or not isinstance(rc, dict) or "model" not in rc:
        data["react_config"] = merge_react_config(rc if isinstance(rc, dict) else {})
    else:
        data["react_config"] = rc
    data["react_config"]["max_iters"] = normalize_max_iters(data["react_config"].get("max_iters"))
    data.setdefault("enabled", True)
    return data
