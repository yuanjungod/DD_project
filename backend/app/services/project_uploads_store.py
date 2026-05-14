"""Persist uploaded diligence files under the project tree and register them as file_reference resources."""

from __future__ import annotations

from pathlib import Path

from app.models.entities import new_id
from app.schemas import ResourceCreate, ResourceRead
from app.services.fs_layout import project_uploads_dir

# Guardrail for local MVP; adjust via env later if needed.
UPLOAD_MAX_BYTES = 50 * 1024 * 1024


def upload_blob_path(project_id: str, file_id: str) -> Path:
    return project_uploads_dir(project_id) / file_id


def unlink_upload_blob(project_id: str, file_id: str) -> None:
    path = upload_blob_path(project_id, file_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def save_project_upload(
    project_id: str,
    *,
    filename: str,
    content_type: str | None,
    body: bytes,
) -> ResourceRead:
    if not body:
        raise ValueError("empty file")
    if len(body) > UPLOAD_MAX_BYTES:
        raise ValueError(f"file exceeds maximum size ({UPLOAD_MAX_BYTES // (1024 * 1024)} MiB)")

    safe_name = Path(filename or "upload").name.strip() or "upload.bin"
    file_id = new_id("fil")
    path = upload_blob_path(project_id, file_id)
    path.write_bytes(body)

    metadata_json = {
        "original_filename": safe_name,
        "content_type": (content_type or "").strip(),
        "size_bytes": len(body),
        "uploaded_via_platform": True,
        "label": Path(safe_name).stem or safe_name,
    }

    payload = ResourceCreate(
        type="file_reference",
        value=file_id,
        metadata_json=metadata_json,
    )
    try:
        from app.services.project_resources_store import add_resource  # noqa: PLC0415

        return add_resource(project_id, payload)
    except Exception:
        path.unlink(missing_ok=True)
        raise
