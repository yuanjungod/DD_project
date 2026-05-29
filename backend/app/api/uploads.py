"""Multipart uploads for engagement file library (stored under .dd_project/data + manifest file_reference)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import ensure_engagement_write_access, require_roles
from app.core.database import get_db
from app.models.entities import User
from app.schemas import ResourceRead
from app.services.engagement_uploads_store import save_engagement_upload

router = APIRouter(prefix="/engagements/{engagement_id}/uploads", tags=["uploads"])


@router.post("", response_model=ResourceRead)
async def upload_engagement_file(
    engagement_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> ResourceRead:
    ensure_engagement_write_access(db, user, engagement_id)
    body = await file.read()
    filename = file.filename or "upload.bin"
    try:
        return save_engagement_upload(
            engagement_id,
            filename=filename,
            content_type=file.content_type,
            body=body,
        )
    except ValueError as exc:
        msg = str(exc)
        if "exceeds maximum" in msg:
            raise HTTPException(status_code=413, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
