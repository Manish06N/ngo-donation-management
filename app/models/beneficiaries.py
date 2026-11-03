from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin
from app.utils.time import utcnow

beneficiary_projects = Table(
    "beneficiary_projects",
    Base.metadata,
    Column("beneficiary_id", ForeignKey("beneficiaries.id"), primary_key=True),
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
)


class Beneficiary(IdMixin, Base):
    __tablename__ = "beneficiaries"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    contact: Mapped[Optional[str]] = mapped_column(String(80))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    projects: Mapped[list["Project"]] = relationship(secondary=beneficiary_projects)
    assistance: Mapped[list["BeneficiaryAssistance"]] = relationship(back_populates="beneficiary")


class BeneficiaryAssistance(IdMixin, Base):
    __tablename__ = "beneficiary_assistance"

    beneficiary_id: Mapped[int] = mapped_column(ForeignKey("beneficiaries.id"), index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    assistance_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    distribution_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(ForeignKey("resources.id"))
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    beneficiary: Mapped[Beneficiary] = relationship(back_populates="assistance")
