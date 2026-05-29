"""Engagement ownership helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import EngagementAccess


def engagement_owner_user_id(db: Session, engagement_id: str) -> str | None:
    row = (
        db.query(EngagementAccess)
        .filter(
            EngagementAccess.engagement_id == engagement_id,
            EngagementAccess.access_role == "owner",
        )
        .first()
    )
    return str(row.user_id) if row is not None else None
