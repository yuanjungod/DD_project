from __future__ import annotations

from collections.abc import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, hash_password
from app.models.entities import Project, ProjectAccess, User


bearer_scheme = HTTPBearer(auto_error=False)


def seed_default_users(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    users = [
        User(
            email="admin@example.com",
            name="Admin",
            password_hash=hash_password("admin123"),
            role="admin",
        ),
        User(
            email="analyst@example.com",
            name="Analyst",
            password_hash=hash_password("analyst123"),
            role="analyst",
        ),
        User(
            email="viewer@example.com",
            name="Viewer",
            password_hash=hash_password("viewer123"),
            role="viewer",
        ),
    ]
    db.add_all(users)
    db.commit()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency


def can_access_project(db: Session, user: User, project_id: str) -> bool:
    if user.role == "admin":
        return db.get(Project, project_id) is not None
    return (
        db.query(ProjectAccess)
        .filter(ProjectAccess.project_id == project_id, ProjectAccess.user_id == user.id)
        .first()
        is not None
    )


def ensure_project_access(db: Session, user: User, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not can_access_project(db, user, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied")
    return project


def ensure_project_write_access(db: Session, user: User, project_id: str) -> Project:
    project = ensure_project_access(db, user, project_id)
    if user.role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only users cannot modify projects")
    return project


def accessible_project_ids(db: Session, user: User) -> Iterable[str] | None:
    if user.role == "admin":
        return None
    rows = db.query(ProjectAccess.project_id).filter(ProjectAccess.user_id == user.id).all()
    return [row[0] for row in rows]
