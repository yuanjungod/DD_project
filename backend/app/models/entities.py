from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("proj"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    company_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


    runs: Mapped[list["AgentRun"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    access_entries: Mapped[list["ProjectAccess"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    diligence_sessions: Mapped[list["DiligenceSession"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class DiligenceSession(Base):
    """One product-level diligence session: may contain multiple run attempts (AgentRun)."""

    __tablename__ = "diligence_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("sess"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="diligence_sessions")
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="diligence_session")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("user"))
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="analyst")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project_access: Mapped[list["ProjectAccess"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ProjectAccess(Base):
    __tablename__ = "project_access"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_user_access"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("access"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    access_role: Mapped[str] = mapped_column(String, nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="access_entries")
    user: Mapped[User] = relationship(back_populates="project_access")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("diligence_sessions.id"), nullable=True
    )
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_result: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="runs")
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
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    overall_risk: Mapped[str] = mapped_column(String, nullable=False)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="reports")
    run: Mapped[AgentRun] = relationship(back_populates="report")
