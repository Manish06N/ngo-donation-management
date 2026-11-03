from datetime import date, datetime

from pydantic import Field

from app.domain.enums import BeneficiaryCategory
from app.schemas.common import APIModel


class BeneficiaryCreate(APIModel):
    full_name: str = Field(min_length=2, max_length=150)
    category: BeneficiaryCategory
    contact: str | None = Field(default=None, max_length=80)
    address: str | None = None
    notes: str | None = None
    project_ids: list[int] = Field(default_factory=list)


class BeneficiaryUpdate(APIModel):
    full_name: str | None = None
    category: BeneficiaryCategory | None = None
    contact: str | None = None
    address: str | None = None
    notes: str | None = None
    project_ids: list[int] | None = None


class AssistanceCreate(APIModel):
    project_id: int
    assistance_type: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=3)
    quantity: int | None = Field(default=None, gt=0)
    distribution_date: date
    resource_id: int | None = None


class AssistanceRead(APIModel):
    id: int
    beneficiary_id: int
    project_id: int
    assistance_type: str
    description: str
    quantity: int | None
    distribution_date: date
    resource_id: int | None
    recorded_by: int
    created_at: datetime


class BeneficiaryRead(APIModel):
    id: int
    full_name: str
    category: str
    contact: str | None = None
    address: str | None = None
    notes: str | None = None
    project_ids: list[int] = []
    created_at: datetime


class NotificationRead(APIModel):
    id: int
    title: str
    message: str
    category: str
    is_read: bool
    read_at: datetime | None
    entity_type: str | None
    entity_id: int | None
    created_at: datetime


class AuditRead(APIModel):
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    details: dict
    created_at: datetime


class StockLevel(APIModel):
    id: int
    name: str
    category: str
    quantity_on_hand: int
    reorder_level: int
    is_low_stock: bool


class BudgetUtilization(APIModel):
    total_budget: str
    total_spent: str
    remaining: str
    utilization_percent: str | None
    overrun_count: int


class GoalAchievement(APIModel):
    total_goal: str
    total_raised: str
    achievement_percent: str | None


class DashboardRead(APIModel):
    total_donations: int
    confirmed_donations: int
    confirmed_amount: str
    active_fundraising_campaigns: int
    campaign_goal_achievement: GoalAchievement
    total_volunteers: int
    active_community_projects: int
    projects_completed: int
    pending_project_approvals: int
    pending_expense_approvals: int
    total_beneficiaries_served: int
    volunteer_hours: str
    milestones_achieved: int
    funds_utilized: str
    project_budget_utilization: BudgetUtilization
    resource_stock_levels: list[StockLevel]
