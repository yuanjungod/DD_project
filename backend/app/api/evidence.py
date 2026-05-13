from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import ensure_project_access, require_roles
from app.core.database import get_db
from app.models.entities import Evidence, User
from app.schemas import EvidenceRead


router = APIRouter(prefix="/projects/{project_id}/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceRead])
def list_evidence(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[Evidence]:
    ensure_project_access(db, user, project_id)
    return db.query(Evidence).filter(Evidence.project_id == project_id).all()
