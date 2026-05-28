"""Platform-wide uploaded files (shared across workflows and project runs)."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.entities import new_id
from app.schemas.dto import LibraryFileRead
from app.services.fs_layout import platform_uploads_dir, platform_uploads_manifest_path, project_uploads_dir
from app.services.project_uploads_store import UPLOAD_MAX_BYTES

_MANIFEST_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_created_at(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".plib_manifest_", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(text)
        Path(tmp).replace(path)
    except Exception:
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _load_raw() -> dict[str, Any]:
    path = platform_uploads_manifest_path()
    if not path.is_file():
        return {"version": _MANIFEST_VERSION, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": _MANIFEST_VERSION, "items": []}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"version": _MANIFEST_VERSION, "items": []}
    return data


def blob_path(file_id: str) -> Path:
    return platform_uploads_dir() / file_id


def iter_platform_upload_file_ids() -> list[str]:
    """Stable ids for merging into company_config.resources.uploaded_files."""
    raw = _load_raw()
    out: list[str] = []
    for row in raw.get("items", []):
        if isinstance(row, dict) and row.get("id"):
            s = str(row["id"]).strip()
            if s:
                out.append(s)
    return sorted(set(out))


def list_library_reads() -> list[LibraryFileRead]:
    raw = _load_raw()
    out: list[LibraryFileRead] = []
    for row in raw.get("items", []):
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                LibraryFileRead(
                    id=str(row["id"]),
                    original_filename=str(row.get("original_filename", row["id"])),
                    content_type=str(row.get("content_type", "")),
                    size_bytes=int(row.get("size_bytes", 0)),
                    created_at=_parse_created_at(str(row["created_at"])),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda r: r.created_at, reverse=True)
    return out


def save_platform_upload(*, filename: str, content_type: str | None, body: bytes) -> LibraryFileRead:
    if not body:
        raise ValueError("文件为空，无法上传")
    if len(body) > UPLOAD_MAX_BYTES:
        raise ValueError(f"file exceeds maximum size ({UPLOAD_MAX_BYTES // (1024 * 1024)} MiB)")

    safe_name = Path(filename or "upload").name.strip() or "upload.bin"
    file_id = new_id("fil")
    path = blob_path(file_id)
    now = _utc_now_iso()
    row = {
        "id": file_id,
        "original_filename": safe_name,
        "content_type": (content_type or "").strip(),
        "size_bytes": len(body),
        "created_at": now,
    }
    try:
        path.write_bytes(body)
        raw = _load_raw()
        items = list(raw.get("items", []))
        items.append(row)
        mpath = platform_uploads_manifest_path()
        blob = {"version": _MANIFEST_VERSION, "items": items}
        _atomic_write(mpath, json.dumps(blob, ensure_ascii=False, indent=2) + "\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise

    return LibraryFileRead(
        id=file_id,
        original_filename=safe_name,
        content_type=row["content_type"],
        size_bytes=len(body),
        created_at=_parse_created_at(now),
    )


def delete_platform_upload(file_id: str) -> bool:
    raw = _load_raw()
    items_all = raw.get("items", [])
    kept: list[Any] = []
    found = False
    for i in items_all:
        if isinstance(i, dict) and str(i.get("id")) == file_id:
            found = True
        else:
            kept.append(i)
    if not found:
        return False
    blob_path(file_id).unlink(missing_ok=True)
    mpath = platform_uploads_manifest_path()
    _atomic_write(mpath, json.dumps({"version": _MANIFEST_VERSION, "items": kept}, ensure_ascii=False, indent=2) + "\n")
    return True


def copy_platform_uploads_to_project(project_id: str, file_ids: list[str]) -> int:
    """Copy selected platform file-library blobs into the project's shared upload directory."""
    copied = 0
    target_dir = project_uploads_dir(project_id)
    seen: set[str] = set()
    for raw in file_ids:
        file_id = str(raw or "").strip()
        if not file_id or file_id in seen:
            continue
        seen.add(file_id)
        src = blob_path(file_id)
        if not src.is_file():
            continue
        dst = target_dir / file_id
        if dst.exists():
            continue
        dst.write_bytes(src.read_bytes())
        copied += 1
    return copied
