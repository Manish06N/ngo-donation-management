from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.domain.enums import MilestoneStatus, ProjectStatus, TaskPriority, TaskStatus
from app.schemas.common import APIModel


class ProjectCreate(APIModel):
    title: str = Field(min_length=3, max_length=180)
    objectives: str = Field(min_length=3)
    description: str | None = None
    location: str = Field(min_length=2, max_length=180)
    start_date: date
    end_date: date
    budget_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    manager_id: int


class ProjectUpdate(APIModel):
    title: str | None = None
    objectives: str | None = None
    description: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    manager_id: int | None = None


class ProjectRead(APIModel):
    id: int
    code: str
    title: str
    objectives: str
    description: str | None
    location: str
    start_date: date
    end_date: date
    budget_amount: Decimal
    status: str
    approval_state: str
    manager_id: int
    created_at: datetime


class ProjectStatusChange(APIModel):
    status: ProjectStatus


class SubmitProject(APIModel):
    comments: str | None = None


class ApprovalRead(APIModel):
    id: int
    project_id: int
    action: str
    comments: str | None
    actor_id: int
    created_at: datetime


class MilestoneCreate(APIModel):
    title: str = Field(min_length=2, max_length=180)
    description: str | None = None
    due_date: date


class MilestoneUpdate(APIModel):
    title: str | None = None
    description: str | None = None
    due_date: date | None = None
    status: MilestoneStatus | None = None
    completion_percent: int | None = Field(default=None, ge=0, le=100)


class MilestoneRead(APIModel):
    id: int
    project_id: int
    title: str
    description: str | None
    due_date: date
    status: str
    completion_percent: int
    completed_at: datetime | None
    overdue: bool = False


class TaskCreate(APIModel):
    title: str = Field(min_length=2, max_length=180)
    description: str | None = None
    assignee_id: int | None = None
    deadline: date
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskUpdate(APIModel):
    title: str | None = None
    description: str | None = None
    assignee_id: int | None = None
    deadline: date | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)


class TaskRead(APIModel):
    id: int
    project_id: int
    milestone_id: int
    title: str
    description: str | None
    assignee_id: int | None
    deadline: date
    priority: str
    status: str
    progress_percent: int
    overdue: bool = False


class ImpactCreate(APIModel):
    beneficiaries_served: int = Field(ge=0)
    volunteer_hours: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    resources_distributed: int = Field(ge=0)
    funds_utilized: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    milestones_achieved: int = Field(ge=0)
    narrative: str = Field(min_length=3)


class ImpactRead(APIModel):
    id: int
    project_id: int
    beneficiaries_served: int
    volunteer_hours: Decimal
    resources_distributed: int
    funds_utilized: Decimal
    milestones_achieved: int
    narrative: str
    submitted_by: int
    created_at: datetime
