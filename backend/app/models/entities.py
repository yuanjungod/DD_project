from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Engagement(Base):
    __tablename__ = "engagements"
    __table_args__ = (
        UniqueConstraint("company_key", "application_id", "version", name="uq_engagement_company_app_version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("eng"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    company_key: Mapped[str] = mapped_column(String, nullable=False, default="company")
    application_id: Mapped[str] = mapped_column(String, nullable=False, default="default")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    company_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    runs: Mapped[list["AgentRun"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    access_entries: Mapped[list["EngagementAccess"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    diligence_sessions: Mapped[list["DiligenceSession"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )


class DiligenceSession(Base):
    """One product-level diligence session: may contain multiple run attempts (AgentRun)."""

    __tablename__ = "diligence_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("sess"))
    engagement_id: Mapped[str] = mapped_column(ForeignKey("engagements.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    engagement: Mapped["Engagement"] = relationship(back_populates="diligence_sessions")
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="diligence_session")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("user"))
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="analyst")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    engagement_access: Mapped[list["EngagementAccess"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class EngagementAccess(Base):
    __tablename__ = "engagement_access"
    __table_args__ = (UniqueConstraint("engagement_id", "user_id", name="uq_engagement_user_access"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("access"))
    engagement_id: Mapped[str] = mapped_column(ForeignKey("engagements.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    access_role: Mapped[str] = mapped_column(String, nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    engagement: Mapped[Engagement] = relationship(back_populates="access_entries")
    user: Mapped[User] = relationship(back_populates="engagement_access")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("engagements.id"), nullable=False)
    started_by_user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, ForeignKey("diligence_sessions.id"), nullable=True)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_result: Mapped[dict] = mapped_column(JSON, default=dict)

    engagement: Mapped[Engagement] = relationship(back_populates="runs")
    diligence_session: Mapped["DiligenceSession | None"] = relationship(back_populates="runs")
    steps: Mapped[list["AgentStep"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    report: Mapped["Report | None"] = relationship(back_populates="run", cascade="all, delete-orphan")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    agent: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)

    run: Mapped[AgentRun] = relationship(back_populates="steps")
    chat_messages: Mapped[list["AgentStepChatMessage"]] = relationship(
        back_populates="step", cascade="all, delete-orphan"
    )


class AgentStepChatMessage(Base):
    __tablename__ = "agent_step_chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("stch"))
    step_id: Mapped[str] = mapped_column(ForeignKey("agent_steps.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    step: Mapped["AgentStep"] = relationship(back_populates="chat_messages")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("report"))
    engagement_id: Mapped[str] = mapped_column(ForeignKey("engagements.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    overall_risk: Mapped[str] = mapped_column(String, nullable=False)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    engagement: Mapped[Engagement] = relationship(back_populates="reports")
    run: Mapped[AgentRun] = relationship(back_populates="report")
