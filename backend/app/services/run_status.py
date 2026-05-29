"""Resolve effective agent run status for API display and stale-run reconciliation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

STALE_RUNNING_AFTER = timedelta(minutes=30)


def _step_statuses(steps: list[Any]) -> list[str]:
    out: list[str] = []
    for step in steps:
        if isinstance(step, dict):
            out.append(str(step.get("status") or ""))
        else:
            out.append(str(getattr(step, "status", "") or ""))
    return out


def _started_age(started_at: datetime) -> timedelta:
    now = datetime.now(timezone.utc)
    started = started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return now - started


def resolve_effective_run_status(
    *,
    status: str,
    steps: list[Any],
    started_at: datetime,
    raw_result: dict[str, Any] | None = None,
) -> str:
    """Derive a user-visible status when the stored row was never finalized."""
    stored = str(status or "").strip() or "pending"
    if stored in {"completed", "failed", "paused"}:
        return stored

    raw = raw_result if isinstance(raw_result, dict) else {}
    if raw.get("error"):
        return "failed"

    step_statuses = [s for s in _step_statuses(steps) if s]
    if step_statuses:
        if any(s == "failed" for s in step_statuses):
            return "failed"
        if any(s == "running" for s in step_statuses):
            return "running"
        if all(s == "completed" for s in step_statuses):
            return "completed"

    if stored == "running" and _started_age(started_at) > STALE_RUNNING_AFTER:
        return "failed"

    return stored
