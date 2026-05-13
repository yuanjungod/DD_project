from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Evidence, Project
from app.schemas import EvidenceRead


router = APIRouter(prefix="/projects/{project_id}/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceRead])
def list_evidence(project_id: str, db: Session = Depends(get_db)) -> list[Evidence]:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(Evidence).filter(Evidence.project_id == project_id).all()
