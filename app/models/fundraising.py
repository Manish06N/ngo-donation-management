from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import CampaignStatus, DonationStatus, DonorStatus, ReceiptStatus
from app.utils.time import utcnow


class Donor(IdMixin, TimestampMixin, Base):
    __tablename__ = "donors"

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    donor_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    organization_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    state: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str | None] = mapped_column(String(80))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=DonorStatus.ACTIVE.value, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    user: Mapped[Optional["User"]] = relationship(back_populates="donor_profile", foreign_keys=[user_id])
    contacts: Mapped[list["DonorContact"]] = relationship(back_populates="donor", cascade="all, delete-orphan")
    donations: Mapped[list["Donation"]] = relationship(back_populates="donor")


class DonorContact(IdMixin, Base):
    __tablename__ = "donor_contacts"

    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    role_label: Mapped[str] = mapped_column(String(40), default="primary", nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    donor: Mapped[Donor] = relationship(back_populates="contacts")


class Campaign(IdMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint("goal_amount > 0", name="goal_positive"),
        CheckConstraint("raised_amount >= 0", name="raised_non_negative"),
        CheckConstraint("budget_amount >= 0", name="budget_non_negative"),
    )

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    goal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    raised_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=CampaignStatus.DRAFT.value, nullable=False, index=True
    )
    manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    donations: Mapped[list["Donation"]] = relationship(back_populates="campaign")


class Donation(IdMixin, TimestampMixin, Base):
    __tablename__ = "donations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("reference_number", name="uq_donations_reference_number"),
        Index("ix_donations_date_status", "donation_date", "status"),
    )

    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id"), index=True, nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    donation_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=DonationStatus.PENDING.value, nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    donor: Mapped[Donor] = relationship(back_populates="donations")
    campaign: Mapped[Campaign] = relationship(back_populates="donations")
    receipt: Mapped[Optional["DonationReceipt"]] = relationship(back_populates="donation", uselist=False)


class DonationReceipt(IdMixin, Base):
    __tablename__ = "donation_receipts"

    donation_id: Mapped[int] = mapped_column(ForeignKey("donations.id"), unique=True, nullable=False)
    receipt_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ReceiptStatus.ISSUED.value, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime)
    void_reason: Mapped[str | None] = mapped_column(String(255))
    issued_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    donation: Mapped[Donation] = relationship(back_populates="receipt")
