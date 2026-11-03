from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import ExpenseStatus
from app.utils.time import utcnow


class Expense(IdMixin, TimestampMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="expense_amount_positive"),
        Index("ix_expenses_project_status", "project_id", "status"),
    )

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id"), index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_reference: Mapped[Optional[str]] = mapped_column(String(80))
    attachment_url: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(20), default=ExpenseStatus.SUBMITTED.value, nullable=False, index=True
    )
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    actions: Mapped[list["ExpenseAction"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan", order_by="ExpenseAction.id"
    )


class ExpenseAction(IdMixin, Base):
    __tablename__ = "expense_actions"

    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    expense: Mapped[Expense] = relationship(back_populates="actions")
