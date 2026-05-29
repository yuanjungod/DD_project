"""Persist each agent run as a JSON session file under workflow template folders."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from agent_service.engagement_layout import (
    find_session_json_path,
    list_session_engagement_ids as _list_session_engagement_ids,
    list_session_files as _list_session_files,
    list_session_workflow_template_ids,
    list_session_user_ids as _list_session_user_ids,
    session_json_path,
)

_SESSION_VERSION = 1


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RunSessionRecorder(Protocol):
    def start(self, payload: dict[str, Any]) -> None: ...
    def append_event(self, event: dict[str, Any]) -> None: ...
    def mark_paused(self, partial_result: dict[str, Any]) -> None: ...
    def finalize_success(self, result_payload: dict[str, Any]) -> None: ...
    def finalize_failure(self, message: str, partial_result: dict[str, Any] | None = None) -> None: ...


class _NoopRecorder:
    def start(self, payload: dict[str, Any]) -> None:
        pass

    def append_event(self, event: dict[str, Any]) -> None:
        pass

    def mark_paused(self, partial_result: dict[str, Any]) -> None:
        pass

    def finalize_success(self, result_payload: dict[str, Any]) -> None:
        pass

    def finalize_failure(self, message: str, partial_result: dict[str, Any] | None = None) -> None:
        pass


NOOP_SESSION_RECORDER: RunSessionRecorder = _NoopRecorder()


class JsonSessionRecorder:
    """Writes run session JSON with incremental events."""

    __slots__ = ("_document", "_path")

    def __init__(
        self,
        workflow_template_id: str,
        user_id: str,
        engagement_id: str,
        run_id: str,
        session_id: str,
    ) -> None:
        self._path = session_json_path(workflow_template_id, user_id, engagement_id, run_id, session_id)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._document: dict[str, Any] | None = None

    @classmethod
    def open_for_resume(
        cls,
        workflow_template_id: str,
        user_id: str,
        engagement_id: str,
        run_id: str,
        session_id: str | None = None,
    ) -> "JsonSessionRecorder":
        path = (
            session_json_path(workflow_template_id, user_id, engagement_id, run_id, session_id)
            if session_id
            else find_session_json_path(workflow_template_id, user_id, engagement_id, run_id)
        )
        if path is None:
            raise FileNotFoundError(run_id)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        obj = object.__new__(cls)
        obj._path = path
        obj._document = json.loads(path.read_text(encoding="utf-8"))
        return obj

    def start(self, payload: dict[str, Any]) -> None:
        now = _utc_iso()
        self._document = {
            "session_format_version": _SESSION_VERSION,
            "started_at": now,
            "updated_at": now,
            "status": "running",
            "events": [{"type": "run_started", "ts": now}],
            **payload,
        }
        self._flush()

    def append_event(self, event: dict[str, Any]) -> None:
        if self._document is None:
            return
        entry = dict(event)
        entry.setdefault("ts", _utc_iso())
        self._document.setdefault("events", []).append(entry)
        self._document["updated_at"] = entry["ts"]
        self._flush()

    def mark_paused(self, partial_result: dict[str, Any]) -> None:
        if self._document is None:
            return
        now = _utc_iso()
        self._document["status"] = "paused"
        self._document["updated_at"] = now
        self._document["partial_result"] = partial_result
        self._document.setdefault("events", []).append({"type": "run_paused", "ts": now})
        self._flush()

    def finalize_success(self, result_payload: dict[str, Any]) -> None:
        if self._document is None:
            return
        now = _utc_iso()
        self._document["status"] = "completed"
        self._document["updated_at"] = now
        self._document["result"] = result_payload
        self._document.setdefault("events", []).append({"type": "run_completed", "ts": now})
        self._flush()

    def finalize_failure(self, message: str, partial_result: dict[str, Any] | None = None) -> None:
        if self._document is None:
            return
        now = _utc_iso()
        self._document["status"] = "failed"
        self._document["updated_at"] = now
        self._document["error_message"] = message
        if partial_result is not None:
            self._document["partial_result"] = partial_result
        self._document.setdefault("events", []).append(
            {"type": "run_failed", "ts": now, "message": message[:4000]},
        )
        self._flush()

    def _flush(self) -> None:
        if self._document is None:
            return
        text = json.dumps(self._document, ensure_ascii=False, indent=2) + "\n"
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self._path)


def build_session_recorder(
    workflow_template_id: str,
    user_id: str,
    engagement_id: str,
    run_id: str,
    session_id: str,
) -> RunSessionRecorder:
    from agent_service.settings import get_agent_settings

    if not getattr(get_agent_settings(), "session_history_enabled", True):
        return NOOP_SESSION_RECORDER
    return JsonSessionRecorder(workflow_template_id, user_id, engagement_id, run_id, session_id)


def open_session_recorder_for_resume(
    workflow_template_id: str,
    user_id: str,
    engagement_id: str,
    run_id: str,
    session_id: str | None = None,
) -> RunSessionRecorder | None:
    from agent_service.settings import get_agent_settings

    if not getattr(get_agent_settings(), "session_history_enabled", True):
        return None
    try:
        return JsonSessionRecorder.open_for_resume(
            workflow_template_id,
            user_id,
            engagement_id,
            run_id,
            session_id=session_id,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
        return None


def read_session_document(
    workflow_template_id: str, user_id: str, engagement_id: str, run_id: str
) -> dict[str, Any] | None:
    path = find_session_json_path(workflow_template_id, user_id, engagement_id, run_id)
    if path is None:
        return None
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_session_files(workflow_template_id: str, user_id: str, engagement_id: str) -> list[str]:
    return _list_session_files(workflow_template_id, user_id, engagement_id)


def list_session_engagement_ids(workflow_template_id: str, user_id: str) -> list[str]:
    return _list_session_engagement_ids(workflow_template_id, user_id)


def list_session_user_ids(workflow_template_id: str) -> list[str]:
    return _list_session_user_ids(workflow_template_id)


def list_all_session_workflow_template_ids() -> list[str]:
    return list_session_workflow_template_ids()
