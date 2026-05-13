from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import ensure_project_access, require_roles
from app.core.database import get_db
from app.models.entities import Report, User
from app.schemas import ReportRead


router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])


@router.get("", response_model=list[ReportRead])
def list_reports(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> list[Report]:
    ensure_project_access(db, user, project_id)
    return db.query(Report).filter(Report.project_id == project_id).order_by(Report.created_at.desc()).all()


@router.get("/{report_id}", response_model=ReportRead)
def get_report(
    project_id: str,
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "viewer")),
) -> Report:
    ensure_project_access(db, user, project_id)
    report = db.query(Report).filter(Report.project_id == project_id, Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
