from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    ApprovalAction,
    ApprovalState,
    MilestoneStatus,
    NotificationCategory,
    ProjectStatus,
    Role,
    TaskStatus,
)
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.domain.rules import ensure_date_order, money
from app.domain.transitions import PROJECT_TRANSITIONS, ensure_transition
from app.models.identity import User
from app.models.projects import ImpactUpdate, Milestone, Project, ProjectApproval, Task
from app.models.volunteering import Volunteer
from app.repositories.common import apply_sort, get_or_404, next_code, paginate
from app.schemas.projects import (
    ImpactCreate,
    MilestoneCreate,
    MilestoneUpdate,
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.services.access import (
    PROJECT_MANAGER_ROLES,
    assert_project_visible,
    assigned_project_ids,
    audit,
    authorize,
    notify,
    touch,
    users_with_roles,
    volunteer_for_user,
)
from app.utils.time import utcnow


def _value(item):
    return item.value if hasattr(item, "value") else item


def _manager(db: Session, user_id: int) -> User:
    user = get_or_404(db, User, user_id, "Project manager")
    if not user.is_active or user.role not in PROJECT_MANAGER_ROLES:
        raise AppError("Project manager must be an active NGO manager", 422, "invalid_manager")
    return user


def create_project(db: Session, actor: User, payload: ProjectCreate) -> Project:
    authorize(actor, Permission.WRITE_PROJECTS)
    ensure_date_order(payload.start_date, payload.end_date)
    _manager(db, payload.manager_id)
    project = Project(
        code=next_code(db, "project", "PRJ"),
        title=payload.title,
        objectives=payload.objectives,
        description=payload.description,
        location=payload.location,
        start_date=payload.start_date,
        end_date=payload.end_date,
        budget_amount=money(payload.budget_amount),
        status=ProjectStatus.PLANNING.value,
        approval_state=ApprovalState.NOT_SUBMITTED.value,
        manager_id=payload.manager_id,
        created_by=actor.id,
    )
    db.add(project)
    db.flush()
    audit(db, actor.id, "project.created", "project", project.id, {"code": project.code, "title": project.title})
    return project


def update_project(db: Session, actor: User, project_id: int, payload: ProjectUpdate) -> Project:
    authorize(actor, Permission.WRITE_PROJECTS)
    project = get_or_404(db, Project, project_id, "Project")
    if project.status in {ProjectStatus.COMPLETED.value, ProjectStatus.CANCELLED.value}:
        raise AppError("Closed projects cannot be edited", 409, "project_closed")
    changes = payload.model_dump(exclude_unset=True)
    if "budget_amount" in changes and changes["budget_amount"] is not None:
        if actor.role not in PROJECT_MANAGER_ROLES and actor.role != Role.FINANCE_OFFICER.value:
            raise AppError("Only managers or finance can change a project budget", 403, "forbidden")
        changes["budget_amount"] = money(changes["budget_amount"])
    if "manager_id" in changes and changes["manager_id"] is not None:
        _manager(db, changes["manager_id"])
    start = changes.get("start_date", project.start_date)
    end = changes.get("end_date", project.end_date)
    ensure_date_order(start, end)
    for key, value in changes.items():
        setattr(project, key, value)
    touch(project)
    audit(db, actor.id, "project.updated", "project", project.id, {"fields": list(changes)})
    db.flush()
    return project


def get_project(db: Session, actor: User, project_id: int) -> Project:
    project = get_or_404(db, Project, project_id, "Project")
    assert_project_visible(db, actor, project.id)
    return project


def list_projects(db, actor, *, page, page_size, sort_by, sort_dir, q, status, manager_id):
    if actor.role == Role.VOLUNTEER.value:
        ids = assigned_project_ids(db, actor) or [-1]
        stmt = select(Project).where(Project.id.in_(ids))
    elif actor.role == Role.DONOR.value:
        raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
    else:
        authorize(actor, Permission.READ_PROJECTS)
        stmt = select(Project)
    if q:
        stmt = stmt.where(Project.title.ilike(f"%{q}%") | Project.code.ilike(f"%{q}%") | Project.location.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Project.status == status)
    if manager_id:
        stmt = stmt.where(Project.manager_id == manager_id)
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {"id": Project.id, "title": Project.title, "start_date": Project.start_date, "end_date": Project.end_date, "created_at": Project.created_at},
    )
    return paginate(db, stmt, page, page_size)


def submit_project(db: Session, actor: User, project_id: int, comments: str | None) -> Project:
    authorize(actor, Permission.WRITE_PROJECTS)
    project = get_or_404(db, Project, project_id, "Project")
    if project.status != ProjectStatus.PLANNING.value:
        raise AppError("Only projects in planning can be submitted", 409, "invalid_transition")
    if project.approval_state == ApprovalState.PENDING.value:
        raise AppError("This project is already waiting for approval", 409, "already_submitted")
    project.approval_state = ApprovalState.PENDING.value
    touch(project)
    db.add(ProjectApproval(project_id=project.id, action=ApprovalAction.SUBMITTED.value, comments=comments, actor_id=actor.id))
    notify(
        db,
        users_with_roles(db, {Role.SUPER_ADMIN.value, Role.NGO_MANAGER.value}),
        title="Project submitted for approval",
        message=f"{project.title} is waiting for a decision.",
        category=NotificationCategory.APPROVAL.value,
        entity_type="project",
        entity_id=project.id,
    )
    audit(db, actor.id, "project.submitted", "project", project.id, {"comments": comments})
    db.flush()
    return project


def decide_project(db: Session, actor: User, project_id: int, decision: str, comments: str | None) -> Project:
    authorize(actor, Permission.APPROVE_PROJECTS)
    project = get_or_404(db, Project, project_id, "Project")
    if project.approval_state != ApprovalState.PENDING.value:
        raise AppError("This project is not waiting for approval", 409, "not_pending")
    if decision == ApprovalAction.REJECTED.value and not (comments and comments.strip()):
        raise AppError("A rejection needs a comment", 422, "comment_required")
    if decision == ApprovalAction.APPROVED.value:
        project.approval_state = ApprovalState.APPROVED.value
        project.status = ProjectStatus.APPROVED.value
        action = "project.approved"
    elif decision == ApprovalAction.REJECTED.value:
        project.approval_state = ApprovalState.REJECTED.value
        project.status = ProjectStatus.PLANNING.value
        action = "project.rejected"
    else:
        raise AppError("Decision must be approved or rejected", 422, "invalid_decision")
    touch(project)
    db.add(ProjectApproval(project_id=project.id, action=decision, comments=comments, actor_id=actor.id))
    notify(
        db,
        [project.manager_id],
        title="Project approval decision",
        message=f"{project.title} was {decision}.",
        category=NotificationCategory.APPROVAL.value,
        entity_type="project",
        entity_id=project.id,
    )
    audit(db, actor.id, action, "project", project.id, {"comments": comments})
    db.flush()
    return project


def list_approvals(db: Session, actor: User, project_id: int):
    get_project(db, actor, project_id)
    return list(
        db.scalars(select(ProjectApproval).where(ProjectApproval.project_id == project_id).order_by(ProjectApproval.id)).all()
    )


def change_status(db: Session, actor: User, project_id: int, new_status: str) -> Project:
    authorize(actor, Permission.WRITE_PROJECTS)
    project = get_or_404(db, Project, project_id, "Project")
    new_status = _value(new_status)
    ensure_transition(project.status, new_status, PROJECT_TRANSITIONS, "Project")
    if new_status == ProjectStatus.ACTIVE.value and project.approval_state != ApprovalState.APPROVED.value:
        raise AppError("A project cannot be activated until it is approved", 409, "approval_required")
    if new_status == ProjectStatus.COMPLETED.value:
        open_count = db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(Milestone.project_id == project.id, Milestone.status != MilestoneStatus.COMPLETED.value)
        )
        if open_count:
            raise AppError("Complete every milestone before completing the project", 409, "milestones_open")
    previous = project.status
    project.status = new_status
    touch(project)
    audit(db, actor.id, "project.status_changed", "project", project.id, {"from": previous, "to": new_status})
    db.flush()
    return project


def create_milestone(db: Session, actor: User, project_id: int, payload: MilestoneCreate) -> Milestone:
    authorize(actor, Permission.MANAGE_TASKS)
    project = get_or_404(db, Project, project_id, "Project")
    if project.status in {ProjectStatus.CANCELLED.value, ProjectStatus.COMPLETED.value}:
        raise AppError("Closed projects cannot take new milestones", 409, "project_closed")
    milestone = Milestone(
        project_id=project.id,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        status=MilestoneStatus.PENDING.value,
        completion_percent=0,
    )
    db.add(milestone)
    db.flush()
    audit(db, actor.id, "milestone.created", "milestone", milestone.id, {"project_id": project.id, "title": milestone.title})
    return milestone


def update_milestone(db: Session, actor: User, milestone_id: int, payload: MilestoneUpdate) -> Milestone:
    authorize(actor, Permission.MANAGE_TASKS)
    milestone = get_or_404(db, Milestone, milestone_id, "Milestone")
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        changes["status"] = _value(changes["status"])
    for key, value in changes.items():
        setattr(milestone, key, value)
    _sync_milestone_flags(milestone)
    touch(milestone)
    audit(db, actor.id, "milestone.updated", "milestone", milestone.id, {"fields": list(changes)})
    db.flush()
    return milestone


def list_milestones(db: Session, actor: User, project_id: int):
    get_project(db, actor, project_id)
    return list(db.scalars(select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.due_date)).all())


def create_task(db: Session, actor: User, milestone_id: int, payload: TaskCreate) -> Task:
    authorize(actor, Permission.MANAGE_TASKS)
    milestone = get_or_404(db, Milestone, milestone_id, "Milestone")
    if payload.assignee_id is not None:
        get_or_404(db, Volunteer, payload.assignee_id, "Volunteer")
    task = Task(
        project_id=milestone.project_id,
        milestone_id=milestone.id,
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        deadline=payload.deadline,
        priority=_value(payload.priority),
        status=TaskStatus.TODO.value,
        progress_percent=0,
    )
    db.add(task)
    db.flush()
    audit(db, actor.id, "task.created", "task", task.id, {"milestone_id": milestone.id, "title": task.title})
    return task


def update_task(db: Session, actor: User, task_id: int, payload: TaskUpdate) -> Task:
    task = get_or_404(db, Task, task_id, "Task")
    changes = payload.model_dump(exclude_unset=True)
    if actor.role == Role.VOLUNTEER.value:
        own = volunteer_for_user(db, actor)
        if own is None or task.assignee_id != own.id:
            raise AppError("Volunteers can update only their own tasks", 403, "forbidden")
        allowed = {"status", "progress_percent"}
        if set(changes) - allowed:
            raise AppError("Volunteers can update only status and progress", 403, "forbidden")
    else:
        authorize(actor, Permission.MANAGE_TASKS)
    if "status" in changes and changes["status"] is not None:
        changes["status"] = _value(changes["status"])
    if "priority" in changes and changes["priority"] is not None:
        changes["priority"] = _value(changes["priority"])
    if changes.get("assignee_id"):
        get_or_404(db, Volunteer, changes["assignee_id"], "Volunteer")
    for key, value in changes.items():
        setattr(task, key, value)
    if task.status == TaskStatus.DONE.value:
        task.progress_percent = 100
    elif task.progress_percent == 100:
        task.status = TaskStatus.DONE.value
    touch(task)
    milestone = get_or_404(db, Milestone, task.milestone_id, "Milestone")
    _refresh_milestone_from_tasks(db, milestone)
    audit(db, actor.id, "task.updated", "task", task.id, {"fields": list(changes), "status": task.status})
    db.flush()
    return task


def list_tasks(db, actor, *, page, page_size, sort_by, sort_dir, project_id, milestone_id, assignee_id, status, priority, overdue):
    if actor.role == Role.VOLUNTEER.value:
        own = volunteer_for_user(db, actor)
        stmt = select(Task).where(Task.assignee_id == (own.id if own else -1))
    elif actor.role == Role.DONOR.value:
        raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
    else:
        authorize(actor, Permission.READ_PROJECTS)
        stmt = select(Task)
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    if milestone_id:
        stmt = stmt.where(Task.milestone_id == milestone_id)
    if assignee_id:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)
    if overdue:
        stmt = stmt.where(Task.deadline < date.today(), Task.status != TaskStatus.DONE.value)
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {"id": Task.id, "deadline": Task.deadline, "priority": Task.priority, "created_at": Task.created_at},
    )
    return paginate(db, stmt, page, page_size)


def _sync_milestone_flags(milestone: Milestone) -> None:
    if milestone.status == MilestoneStatus.COMPLETED.value or milestone.completion_percent == 100:
        milestone.status = MilestoneStatus.COMPLETED.value
        milestone.completion_percent = 100
        milestone.completed_at = milestone.completed_at or utcnow()
    else:
        milestone.completed_at = None


def _refresh_milestone_from_tasks(db: Session, milestone: Milestone) -> None:
    tasks = list(db.scalars(select(Task).where(Task.milestone_id == milestone.id)).all())
    if not tasks:
        return
    if all(task.status == TaskStatus.DONE.value for task in tasks):
        milestone.status = MilestoneStatus.COMPLETED.value
        milestone.completion_percent = 100
        milestone.completed_at = milestone.completed_at or utcnow()
    else:
        milestone.completion_percent = round(sum(task.progress_percent for task in tasks) / len(tasks))
        if milestone.status == MilestoneStatus.COMPLETED.value:
            milestone.status = MilestoneStatus.IN_PROGRESS.value
            milestone.completed_at = None
        elif any(task.status != TaskStatus.TODO.value for task in tasks):
            milestone.status = MilestoneStatus.IN_PROGRESS.value
    touch(milestone)


def submit_impact(db: Session, actor: User, project_id: int, payload: ImpactCreate) -> ImpactUpdate:
    authorize(actor, Permission.WRITE_IMPACT)
    project = get_or_404(db, Project, project_id, "Project")
    if project.status in {ProjectStatus.PLANNING.value, ProjectStatus.CANCELLED.value}:
        raise AppError("Impact can be recorded only after a project is approved", 409, "project_not_ready")
    update = ImpactUpdate(
        project_id=project.id,
        beneficiaries_served=payload.beneficiaries_served,
        volunteer_hours=money(payload.volunteer_hours),
        resources_distributed=payload.resources_distributed,
        funds_utilized=money(payload.funds_utilized),
        milestones_achieved=payload.milestones_achieved,
        narrative=payload.narrative,
        submitted_by=actor.id,
    )
    db.add(update)
    db.flush()
    audit(db, actor.id, "impact.submitted", "impact", update.id, {"project_id": project.id})
    return update


def list_impact(db: Session, actor: User, project_id: int):
    get_project(db, actor, project_id)
    if actor.role == Role.VOLUNTEER.value:
        raise AppError("Role 'volunteer' cannot perform this action", 403, "forbidden")
    authorize(actor, Permission.READ_PROJECTS)
    return list(
        db.scalars(select(ImpactUpdate).where(ImpactUpdate.project_id == project_id).order_by(ImpactUpdate.id.desc())).all()
    )
