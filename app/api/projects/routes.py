from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.identity import User
from app.schemas.common import CommentDecision
from app.schemas.projects import (
    ApprovalRead,
    ImpactCreate,
    ImpactRead,
    MilestoneCreate,
    MilestoneRead,
    MilestoneUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectStatusChange,
    ProjectUpdate,
    SubmitProject,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])
milestones = APIRouter(prefix="/milestones", tags=["Milestones"])
tasks = APIRouter(prefix="/tasks", tags=["Tasks"])


def _milestone(row) -> MilestoneRead:
    data = MilestoneRead.model_validate(row)
    overdue = row.due_date < date.today() and row.status != "completed"
    return data.model_copy(update={"overdue": overdue})


def _task(row) -> TaskRead:
    data = TaskRead.model_validate(row)
    overdue = row.deadline < date.today() and row.status != "done"
    return data.model_copy(update={"overdue": overdue})


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a project in planning. It cannot be activated until it is approved."""
    return project_service.create_project(db, actor, payload)


@router.get("", response_model=dict)
def list_projects(
    listing: Listing = Depends(),
    q: str | None = None,
    status: str | None = None,
    manager_id: int | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = project_service.list_projects(
        db, actor, page=listing.page, page_size=listing.page_size, sort_by=listing.sort_by, sort_dir=listing.sort_dir, q=q, status=status, manager_id=manager_id
    )
    return as_page([ProjectRead.model_validate(row) for row in rows], total, listing)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.get_project(db, actor, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.update_project(db, actor, project_id, payload)


@router.post("/{project_id}/submit", response_model=ProjectRead)
def submit_project(project_id: int, payload: SubmitProject, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send a planning project for approval. A second submit is refused while a decision is open."""
    return project_service.submit_project(db, actor, project_id, payload.comments)


@router.post("/{project_id}/decision", response_model=ProjectRead)
def decide_project(project_id: int, payload: CommentDecision, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Approve or reject. Rejection requires a comment and keeps the project in planning."""
    return project_service.decide_project(db, actor, project_id, payload.decision, payload.comments)


@router.get("/{project_id}/approvals", response_model=list[ApprovalRead])
def approvals(project_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.list_approvals(db, actor, project_id)


@router.post("/{project_id}/status", response_model=ProjectRead)
def change_status(project_id: int, payload: ProjectStatusChange, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Activate, hold, complete, or cancel. Activation is refused until the project is approved."""
    return project_service.change_status(db, actor, project_id, payload.status)


@router.post("/{project_id}/milestones", response_model=MilestoneRead, status_code=status.HTTP_201_CREATED)
def create_milestone(project_id: int, payload: MilestoneCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _milestone(project_service.create_milestone(db, actor, project_id, payload))


@router.get("/{project_id}/milestones", response_model=list[MilestoneRead])
def list_milestones(project_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_milestone(row) for row in project_service.list_milestones(db, actor, project_id)]


@router.post("/{project_id}/impact", response_model=ImpactRead, status_code=status.HTTP_201_CREATED)
def submit_impact(project_id: int, payload: ImpactCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Append an impact update. Earlier updates stay in the history."""
    return project_service.submit_impact(db, actor, project_id, payload)


@router.get("/{project_id}/impact", response_model=list[ImpactRead])
def list_impact(project_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.list_impact(db, actor, project_id)


@milestones.patch("/{milestone_id}", response_model=MilestoneRead)
def update_milestone(milestone_id: int, payload: MilestoneUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _milestone(project_service.update_milestone(db, actor, milestone_id, payload))


@milestones.post("/{milestone_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(milestone_id: int, payload: TaskCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _task(project_service.create_task(db, actor, milestone_id, payload))


@tasks.get("", response_model=dict)
def list_tasks(
    listing: Listing = Depends(),
    project_id: int | None = None,
    milestone_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    overdue: bool = False,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List tasks. Pass overdue=true to see work past its deadline that is not done."""
    rows, total = project_service.list_tasks(
        db,
        actor,
        page=listing.page,
        page_size=listing.page_size,
        sort_by=listing.sort_by,
        sort_dir=listing.sort_dir,
        project_id=project_id,
        milestone_id=milestone_id,
        assignee_id=assignee_id,
        status=status,
        priority=priority,
        overdue=overdue,
    )
    return as_page([_task(row) for row in rows], total, listing)


@tasks.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _task(project_service.update_task(db, actor, task_id, payload))
