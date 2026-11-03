from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.utils.time import utcnow


class Resource(IdMixin, TimestampMixin, Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="stock_non_negative"),
        CheckConstraint("reorder_level >= 0", name="reorder_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(30), default="unit", nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    movements: Mapped[list["ResourceTransaction"]] = relationship(back_populates="resource")


class ResourceTransaction(IdMixin, Base):
    __tablename__ = "resource_transactions"
    __table_args__ = (CheckConstraint("quantity > 0", name="movement_quantity_positive"),)

    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"), index=True, nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    resource: Mapped[Resource] = relationship(back_populates="movements")
