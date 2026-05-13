from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Project, Report
from app.schemas import ReportRead


router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])


@router.get("", response_model=list[ReportRead])
def list_reports(project_id: str, db: Session = Depends(get_db)) -> list[Report]:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(Report).filter(Report.project_id == project_id).order_by(Report.created_at.desc()).all()


@router.get("/{report_id}", response_model=ReportRead)
def get_report(project_id: str, report_id: str, db: Session = Depends(get_db)) -> Report:
    report = db.query(Report).filter(Report.project_id == project_id, Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
