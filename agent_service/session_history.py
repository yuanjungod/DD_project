"""Persist each agent run as a JSON \"session\" file on disk (auditable timeline + final payload)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from agent_service.settings import get_agent_settings

_SESSION_VERSION = 1
_ID_SAFE = re.compile(r"^[a-zA-Z0-9_-]{1,160}$")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sessions_root() -> Path:
    settings = get_agent_settings()
    base = settings.resolved_session_history_dir
    base.mkdir(parents=True, exist_ok=True)
    return base


def _validate_id(seg: str, label: str) -> str:
    if not _ID_SAFE.fullmatch(seg):
        raise ValueError(f"Invalid {label} for session storage (only [a-zA-Z0-9_-], max 160 chars)")
    return seg


def session_json_path(project_id: str, run_id: str) -> Path:
    safe_proj = _validate_id(project_id, "project_id")
    safe_run = _validate_id(run_id, "run_id")
    return _sessions_root() / safe_proj / f"{safe_run}.json"


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
    """Writes `{project}/{run}.json` with incremental events."""

    __slots__ = ("_document", "_path")

    def __init__(self, project_id: str, run_id: str) -> None:
        self._path = session_json_path(project_id, run_id)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._document: dict[str, Any] | None = None

    @classmethod
    def open_for_resume(cls, project_id: str, run_id: str) -> "JsonSessionRecorder":
        path = session_json_path(project_id, run_id)
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


def build_session_recorder(project_id: str, run_id: str) -> RunSessionRecorder:
    if not getattr(get_agent_settings(), "session_history_enabled", True):
        return NOOP_SESSION_RECORDER
    return JsonSessionRecorder(project_id, run_id)


def open_session_recorder_for_resume(project_id: str, run_id: str) -> RunSessionRecorder | None:
    """Reload an on-disk session file to append events across gated slices. Returns None if disabled or missing."""
    if not getattr(get_agent_settings(), "session_history_enabled", True):
        return None
    try:
        return JsonSessionRecorder.open_for_resume(project_id, run_id)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
        return None


def read_session_document(project_id: str, run_id: str) -> dict[str, Any] | None:
    path = session_json_path(project_id, run_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_session_files(project_id: str) -> list[str]:
    safe_proj = _validate_id(project_id, "project_id")
    folder = _sessions_root() / safe_proj
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.json"))


def list_session_project_ids() -> list[str]:
    root = _sessions_root()
    return sorted(p.name for p in root.iterdir() if p.is_dir())
