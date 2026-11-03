from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import ExpenseStatus, NotificationCategory, ProjectStatus, Role
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.domain.rules import is_overrun, money, remaining_budget, utilization_percent
from app.domain.transitions import EXPENSE_TRANSITIONS, SPENT_EXPENSE, ensure_transition
from app.models.finance import Expense, ExpenseAction
from app.models.fundraising import Campaign
from app.models.identity import User
from app.models.projects import Project
from app.repositories.common import apply_sort, get_for_update, get_or_404, paginate
from app.schemas.operations import BudgetRead, ExpenseCreate, ExpenseUpdate
from app.services.access import audit, authorize, notify, touch, users_with_roles

OPEN_FOR_EXPENSES = {ProjectStatus.APPROVED.value, ProjectStatus.ACTIVE.value, ProjectStatus.ON_HOLD.value}


def _value(item):
    return item.value if hasattr(item, "value") else item


def spent_for_project(db: Session, project_id: int):
    total = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.project_id == project_id,
            Expense.status.in_(list(SPENT_EXPENSE)),
        )
    )
    return money(total)


def spent_for_campaign(db: Session, campaign_id: int):
    total = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.campaign_id == campaign_id,
            Expense.status.in_(list(SPENT_EXPENSE)),
        )
    )
    return money(total)


def create_expense(db: Session, actor: User, payload: ExpenseCreate) -> Expense:
    authorize(actor, Permission.SUBMIT_EXPENSES)
    project = get_or_404(db, Project, payload.project_id, "Project")
    if project.status not in OPEN_FOR_EXPENSES:
        raise AppError("Expenses can be recorded only on approved, active, or on-hold projects", 409, "project_not_open")
    if payload.campaign_id is not None:
        get_or_404(db, Campaign, payload.campaign_id, "Campaign")
    expense = Expense(
        project_id=project.id,
        campaign_id=payload.campaign_id,
        category=_value(payload.category),
        amount=money(payload.amount),
        expense_date=payload.expense_date,
        description=payload.description,
        receipt_reference=payload.receipt_reference,
        attachment_url=payload.attachment_url,
        status=ExpenseStatus.SUBMITTED.value,
        submitted_by=actor.id,
    )
    db.add(expense)
    db.flush()
    db.add(ExpenseAction(expense_id=expense.id, action=ExpenseStatus.SUBMITTED.value, comments=None, actor_id=actor.id))
    notify(
        db,
        users_with_roles(db, {Role.FINANCE_OFFICER.value, Role.SUPER_ADMIN.value}),
        title="Expense waiting for approval",
        message=f"{expense.amount} {expense.category} expense on project {project.code} needs a decision.",
        category=NotificationCategory.EXPENSE.value,
        entity_type="expense",
        entity_id=expense.id,
    )
    audit(
        db,
        actor.id,
        "expense.created",
        "expense",
        expense.id,
        {"amount": str(expense.amount), "project_id": project.id, "category": expense.category},
    )
    db.flush()
    return expense


def update_expense(db: Session, actor: User, expense_id: int, payload: ExpenseUpdate) -> Expense:
    authorize(actor, Permission.SUBMIT_EXPENSES)
    expense = get_or_404(db, Expense, expense_id, "Expense")
    if expense.status != ExpenseStatus.SUBMITTED.value:
        raise AppError("Only submitted expenses can be edited", 409, "expense_locked")
    changes = payload.model_dump(exclude_unset=True)
    if "category" in changes and changes["category"] is not None:
        changes["category"] = _value(changes["category"])
    if "amount" in changes and changes["amount"] is not None:
        changes["amount"] = money(changes["amount"])
    if changes.get("campaign_id"):
        get_or_404(db, Campaign, changes["campaign_id"], "Campaign")
    for key, value in changes.items():
        setattr(expense, key, value)
    touch(expense)
    audit(db, actor.id, "expense.updated", "expense", expense.id, {"fields": list(changes)})
    db.flush()
    return expense


def decide_expense(db: Session, actor: User, expense_id: int, new_status: str, comments: str | None) -> Expense:
    authorize(actor, Permission.APPROVE_EXPENSES)
    expense = db.scalar(select(Expense).options(selectinload(Expense.actions)).where(Expense.id == expense_id))
    if expense is None:
        raise AppError("Expense not found", 404, "not_found")
    ensure_transition(expense.status, new_status, EXPENSE_TRANSITIONS, "Expense")
    if new_status in {ExpenseStatus.APPROVED.value, ExpenseStatus.REJECTED.value}:
        if expense.submitted_by == actor.id and actor.role != Role.SUPER_ADMIN.value:
            raise AppError("You cannot review your own expense", 403, "separation_of_duties")
    if new_status == ExpenseStatus.REJECTED.value and not (comments and comments.strip()):
        raise AppError("A rejection needs a comment", 422, "comment_required")
    if new_status == ExpenseStatus.APPROVED.value:
        project = get_for_update(db, Project, expense.project_id, "Project")
        projected = money(spent_for_project(db, project.id) + money(expense.amount))
        if projected > money(project.budget_amount):
            raise AppError(
                f"Approving this expense would exceed the project budget. Remaining {remaining_budget(project.budget_amount, spent_for_project(db, project.id))}",
                409,
                "budget_exceeded",
            )
        if expense.campaign_id is not None:
            campaign = get_for_update(db, Campaign, expense.campaign_id, "Campaign")
            campaign_projected = money(spent_for_campaign(db, campaign.id) + money(expense.amount))
            if campaign_projected > money(campaign.budget_amount):
                raise AppError("Approving this expense would exceed the campaign budget", 409, "budget_exceeded")
    previous = expense.status
    expense.status = new_status
    expense.reviewed_by = actor.id
    touch(expense)
    db.add(ExpenseAction(expense_id=expense.id, action=new_status, comments=comments, actor_id=actor.id))
    notify(
        db,
        [expense.submitted_by],
        title="Expense decision",
        message=f"Your expense {expense.id} was marked {new_status}.",
        category=NotificationCategory.EXPENSE.value,
        entity_type="expense",
        entity_id=expense.id,
    )
    audit(
        db,
        actor.id,
        f"expense.{new_status}",
        "expense",
        expense.id,
        {"from": previous, "to": new_status, "amount": str(expense.amount), "comments": comments},
    )
    db.flush()
    return expense


def get_expense(db: Session, actor: User, expense_id: int) -> Expense:
    if actor.role not in {Role.SUPER_ADMIN.value, Role.NGO_MANAGER.value, Role.FINANCE_OFFICER.value}:
        authorize(actor, Permission.SUBMIT_EXPENSES)
    expense = db.scalar(select(Expense).options(selectinload(Expense.actions)).where(Expense.id == expense_id))
    if expense is None:
        raise AppError("Expense not found", 404, "not_found")
    return expense


def list_expenses(db, actor, *, page, page_size, sort_by, sort_dir, status, project_id, campaign_id, category, date_from, date_to):
    if not (
        actor.role in {Role.SUPER_ADMIN.value, Role.NGO_MANAGER.value, Role.FINANCE_OFFICER.value}
    ):
        raise AppError(f"Role '{actor.role}' cannot perform this action", 403, "forbidden")
    stmt = select(Expense).options(selectinload(Expense.actions))
    if status:
        stmt = stmt.where(Expense.status == status)
    if project_id:
        stmt = stmt.where(Expense.project_id == project_id)
    if campaign_id:
        stmt = stmt.where(Expense.campaign_id == campaign_id)
    if category:
        stmt = stmt.where(Expense.category == category)
    if date_from:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to:
        stmt = stmt.where(Expense.expense_date <= date_to)
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {"id": Expense.id, "amount": Expense.amount, "expense_date": Expense.expense_date, "created_at": Expense.created_at},
    )
    return paginate(db, stmt, page, page_size)


def project_budget(db: Session, actor: User, project_id: int) -> BudgetRead:
    authorize(actor, Permission.READ_BUDGETS)
    project = get_or_404(db, Project, project_id, "Project")
    spent = spent_for_project(db, project.id)
    return BudgetRead(
        owner_type="project",
        owner_id=project.id,
        owner_name=project.title,
        budget_amount=money(project.budget_amount),
        spent_amount=spent,
        remaining_amount=remaining_budget(project.budget_amount, spent),
        utilization_percent=utilization_percent(project.budget_amount, spent),
        overrun=is_overrun(project.budget_amount, spent),
    )


def campaign_budget(db: Session, actor: User, campaign_id: int) -> BudgetRead:
    authorize(actor, Permission.READ_BUDGETS)
    campaign = get_or_404(db, Campaign, campaign_id, "Campaign")
    spent = spent_for_campaign(db, campaign.id)
    return BudgetRead(
        owner_type="campaign",
        owner_id=campaign.id,
        owner_name=campaign.title,
        budget_amount=money(campaign.budget_amount),
        spent_amount=spent,
        remaining_amount=remaining_budget(campaign.budget_amount, spent),
        utilization_percent=utilization_percent(campaign.budget_amount, spent),
        overrun=is_overrun(campaign.budget_amount, spent),
    )


def budget_report(db: Session, actor: User):
    authorize(actor, Permission.READ_BUDGETS)
    projects = list(db.scalars(select(Project).order_by(Project.id)).all())
    return [project_budget(db, actor, project.id) for project in projects]
