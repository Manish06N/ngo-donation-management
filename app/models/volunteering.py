from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import AssignmentStatus, VolunteerStatus
from app.utils.time import utcnow


class Volunteer(IdMixin, TimestampMixin, Base):
    __tablename__ = "volunteers"

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    experience: Mapped[Optional[str]] = mapped_column(Text)
    availability: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default=VolunteerStatus.APPLIED.value, nullable=False, index=True
    )
    emergency_contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    emergency_contact_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    user: Mapped[Optional["User"]] = relationship(back_populates="volunteer_profile", foreign_keys=[user_id])
    assignments: Mapped[list["VolunteerAssignment"]] = relationship(back_populates="volunteer")


class VolunteerAssignment(IdMixin, TimestampMixin, Base):
    __tablename__ = "volunteer_assignments"
    __table_args__ = (Index("ix_assignments_volunteer_status", "volunteer_id", "status"),)

    volunteer_id: Mapped[int] = mapped_column(ForeignKey("volunteers.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    responsibility: Mapped[str] = mapped_column(String(180), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20), default=AssignmentStatus.ASSIGNED.value, nullable=False, index=True
    )
    hours_completed: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    assigned_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    volunteer: Mapped[Volunteer] = relationship(back_populates="assignments")
    project: Mapped["Project"] = relationship(back_populates="assignments")
    attendance: Mapped[list["Attendance"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class Attendance(IdMixin, Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("assignment_id", "attended_on", name="uq_attendance_day"),)

    assignment_id: Mapped[int] = mapped_column(ForeignKey("volunteer_assignments.id"), index=True, nullable=False)
    attended_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255))
    recorded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    assignment: Mapped[VolunteerAssignment] = relationship(back_populates="attendance")
