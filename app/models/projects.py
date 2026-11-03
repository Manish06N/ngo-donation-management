from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import ApprovalState, MilestoneStatus, ProjectStatus, TaskPriority, TaskStatus
from app.utils.time import utcnow


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("budget_amount >= 0", name="project_budget_non_negative"),)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    objectives: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ProjectStatus.PLANNING.value, nullable=False, index=True
    )
    approval_state: Mapped[str] = mapped_column(
        String(20), default=ApprovalState.NOT_SUBMITTED.value, nullable=False, index=True
    )
    manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    approvals: Mapped[list["ProjectApproval"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectApproval.id"
    )
    milestones: Mapped[list["Milestone"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
    assignments: Mapped[list["VolunteerAssignment"]] = relationship(back_populates="project")
    impact_updates: Mapped[list["ImpactUpdate"]] = relationship(back_populates="project")


class ProjectApproval(IdMixin, Base):
    __tablename__ = "project_approvals"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="approvals")


class Milestone(IdMixin, TimestampMixin, Base):
    __tablename__ = "milestones"
    __table_args__ = (
        CheckConstraint("completion_percent >= 0 AND completion_percent <= 100", name="milestone_percent"),
    )

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=MilestoneStatus.PENDING.value, nullable=False)
    completion_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    project: Mapped[Project] = relationship(back_populates="milestones")
    tasks: Mapped[list["Task"]] = relationship(back_populates="milestone", cascade="all, delete-orphan")


class Task(IdMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="task_percent"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestones.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("volunteers.id"), index=True)
    deadline: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default=TaskPriority.MEDIUM.value, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.TODO.value, nullable=False, index=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped[Project] = relationship(back_populates="tasks")
    milestone: Mapped[Milestone] = relationship(back_populates="tasks")


class ImpactUpdate(IdMixin, Base):
    __tablename__ = "impact_updates"
    __table_args__ = (
        CheckConstraint("beneficiaries_served >= 0", name="impact_beneficiaries_non_negative"),
        CheckConstraint("volunteer_hours >= 0", name="impact_hours_non_negative"),
        CheckConstraint("resources_distributed >= 0", name="impact_resources_non_negative"),
        CheckConstraint("funds_utilized >= 0", name="impact_funds_non_negative"),
        CheckConstraint("milestones_achieved >= 0", name="impact_milestones_non_negative"),
    )

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    beneficiaries_served: Mapped[int] = mapped_column(Integer, nullable=False)
    volunteer_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    resources_distributed: Mapped[int] = mapped_column(Integer, nullable=False)
    funds_utilized: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    milestones_achieved: Mapped[int] = mapped_column(Integer, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="impact_updates")
