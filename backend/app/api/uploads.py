"""Multipart uploads for project file library (stored under .dd_project/data + manifest file_reference)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import ensure_project_write_access, require_roles
from app.core.database import get_db
from app.models.entities import User
from app.schemas import ResourceRead
from app.services.project_uploads_store import save_project_upload

router = APIRouter(prefix="/projects/{project_id}/uploads", tags=["uploads"])


@router.post("", response_model=ResourceRead)
async def upload_project_file(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> ResourceRead:
    ensure_project_write_access(db, user, project_id)
    body = await file.read()
    filename = file.filename or "upload.bin"
    try:
        return save_project_upload(
            project_id,
            filename=filename,
            content_type=file.content_type,
            body=body,
        )
    except ValueError as exc:
        msg = str(exc)
        if "exceeds maximum" in msg:
            raise HTTPException(status_code=413, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
