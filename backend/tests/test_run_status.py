"""Tests for effective run status resolution."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.run_status import resolve_effective_run_status


def test_stale_running_without_steps_becomes_failed() -> None:
    started = datetime.utcnow() - timedelta(hours=2)
    assert (
        resolve_effective_run_status(status="running", steps=[], started_at=started, raw_result={})
        == "failed"
    )


def test_all_completed_steps_resolve_to_completed() -> None:
    started = datetime.utcnow()
    steps = [{"status": "completed"}, {"status": "completed"}]
    assert (
        resolve_effective_run_status(status="running", steps=steps, started_at=started, raw_result={})
        == "completed"
    )


def test_explicit_paused_is_preserved() -> None:
    started = datetime.utcnow()
    assert resolve_effective_run_status(status="paused", steps=[], started_at=started) == "paused"
