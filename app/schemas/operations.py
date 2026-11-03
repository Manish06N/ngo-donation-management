from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.domain.enums import ExpenseCategory, MovementType, ResourceCategory
from app.schemas.common import APIModel


class ExpenseCreate(APIModel):
    project_id: int
    campaign_id: int | None = None
    category: ExpenseCategory
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    expense_date: date
    description: str = Field(min_length=3)
    receipt_reference: str | None = Field(default=None, max_length=80)
    attachment_url: str | None = Field(default=None, max_length=500)


class ExpenseUpdate(APIModel):
    campaign_id: int | None = None
    category: ExpenseCategory | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    expense_date: date | None = None
    description: str | None = None
    receipt_reference: str | None = None
    attachment_url: str | None = None


class ExpenseDecision(APIModel):
    status: str = Field(pattern="^(approved|rejected|reimbursed)$")
    comments: str | None = None


class ExpenseActionRead(APIModel):
    id: int
    action: str
    comments: str | None
    actor_id: int
    created_at: datetime


class ExpenseRead(APIModel):
    id: int
    project_id: int
    campaign_id: int | None
    category: str
    amount: Decimal
    expense_date: date
    description: str
    receipt_reference: str | None
    attachment_url: str | None
    status: str
    submitted_by: int
    reviewed_by: int | None
    created_at: datetime
    actions: list[ExpenseActionRead] = []


class BudgetRead(APIModel):
    owner_type: str
    owner_id: int
    owner_name: str
    budget_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    utilization_percent: Decimal | None
    overrun: bool


class ResourceCreate(APIModel):
    name: str = Field(min_length=2, max_length=150)
    category: ResourceCategory
    unit: str = Field(default="unit", min_length=1, max_length=30)
    quantity_on_hand: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=10, ge=0)
    description: str | None = None


class ResourceUpdate(APIModel):
    name: str | None = None
    reorder_level: int | None = Field(default=None, ge=0)
    description: str | None = None


class MovementCreate(APIModel):
    movement_type: MovementType
    quantity: int = Field(gt=0)
    project_id: int | None = None
    notes: str | None = None


class ResourceRead(APIModel):
    id: int
    name: str
    category: str
    unit: str
    quantity_on_hand: int
    reorder_level: int
    description: str | None
    is_low_stock: bool = False


class MovementRead(APIModel):
    id: int
    resource_id: int
    project_id: int | None
    movement_type: str
    quantity: int
    balance_after: int
    notes: str | None
    actor_id: int
    created_at: datetime
