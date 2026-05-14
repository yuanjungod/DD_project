"""Platform library file uploads (not scoped to a single project application)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import require_roles
from app.models.entities import User
from app.schemas import LibraryFileRead
from app.services.platform_uploads_store import (
    delete_platform_upload,
    list_library_reads,
    save_platform_upload,
)

router = APIRouter(prefix="/library/uploads", tags=["library"])


@router.get("", response_model=list[LibraryFileRead])
def list_platform_uploads(
    _: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[LibraryFileRead]:
    return list_library_reads()


@router.post("", response_model=LibraryFileRead)
async def create_platform_upload(
    file: UploadFile = File(...),
    _: User = Depends(require_roles("admin", "analyst")),
) -> LibraryFileRead:
    body = await file.read()
    filename = file.filename or "upload.bin"
    try:
        return save_platform_upload(
            filename=filename,
            content_type=file.content_type,
            body=body,
        )
    except ValueError as exc:
        msg = str(exc)
        if "exceeds maximum" in msg:
            raise HTTPException(status_code=413, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc


@router.delete("/{file_id}", status_code=204)
def remove_platform_upload(
    file_id: str,
    _: User = Depends(require_roles("admin", "analyst")),
) -> None:
    if not delete_platform_upload(file_id):
        raise HTTPException(status_code=404, detail="Library file not found")
