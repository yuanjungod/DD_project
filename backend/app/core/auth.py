from __future__ import annotations

from collections.abc import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
import yaml

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token, hash_password
from app.models.entities import Engagement, EngagementAccess, User
from app.services.fs_layout import default_users_config_path


bearer_scheme = HTTPBearer(auto_error=False)
VALID_USER_ROLES = {"admin", "analyst", "viewer"}


def _load_default_user_seeds() -> list[dict[str, str]]:
    path = default_users_config_path()
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = raw.get("users") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise ValueError(f"Default users config must contain a users list: {path}")

    seeds: list[dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Default user #{idx} must be an object: {path}")
        email = str(row.get("email", "")).strip()
        name = str(row.get("name", "")).strip()
        password = str(row.get("password", ""))
        role = str(row.get("role", "analyst")).strip()
        if not email or not name or not password:
            raise ValueError(f"Default user #{idx} must include email, name, and password: {path}")
        if role not in VALID_USER_ROLES:
            raise ValueError(f"Default user #{idx} has invalid role {role!r}: {path}")
        seeds.append({"email": email, "name": name, "password": password, "role": role})
    return seeds


def seed_default_users(db: Session) -> None:
    if not settings.seed_default_users:
        return
    if db.query(User).count() > 0:
        return
    users = [
        User(
            email=seed["email"],
            name=seed["name"],
            password_hash=hash_password(seed["password"]),
            role=seed["role"],
        )
        for seed in _load_default_user_seeds()
    ]
    if not users:
        return
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


def can_access_engagement(db: Session, user: User, engagement_id: str) -> bool:
    if user.role == "admin":
        return db.get(Engagement, engagement_id) is not None
    return (
        db.query(EngagementAccess)
        .filter(EngagementAccess.engagement_id == engagement_id, EngagementAccess.user_id == user.id)
        .first()
        is not None
    )


def ensure_engagement_access(db: Session, user: User, engagement_id: str) -> Engagement:
    engagement = db.get(Engagement, engagement_id)
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    if not can_access_engagement(db, user, engagement_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engagement access denied")
    return engagement


def ensure_engagement_write_access(db: Session, user: User, engagement_id: str) -> Engagement:
    engagement = ensure_engagement_access(db, user, engagement_id)
    if user.role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only users cannot modify engagements")
    return engagement


def accessible_engagement_ids(db: Session, user: User) -> Iterable[str] | None:
    if user.role == "admin":
        return None
    rows = db.query(EngagementAccess.engagement_id).filter(EngagementAccess.user_id == user.id).all()
    return [row[0] for row in rows]
