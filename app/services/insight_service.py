"""Dashboard numbers are counted from rows. Nothing here is a fixed demo value."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import (
    CampaignStatus,
    DonationStatus,
    ExpenseStatus,
    MilestoneStatus,
    NotificationCategory,
    ProjectStatus,
    Role,
    TaskStatus,
)
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.domain.rules import is_overrun, money, remaining_budget, utilization_percent
from app.domain.transitions import SPENT_EXPENSE
from app.models.beneficiaries import Beneficiary, BeneficiaryAssistance
from app.models.engagement import AuditLog, Notification
from app.models.finance import Expense
from app.models.fundraising import Campaign, Donation, Donor
from app.models.identity import User
from app.models.inventory import Resource, ResourceTransaction
from app.models.projects import Milestone, Project, Task
from app.models.volunteering import Attendance, Volunteer, VolunteerAssignment
from app.repositories.common import apply_sort, get_or_404, paginate
from app.schemas.insights import BudgetUtilization, DashboardRead, GoalAchievement, StockLevel
from app.services.access import authorize, notify, users_with_roles
from app.services.expense_service import spent_for_project
from app.utils.time import utcnow


def _money(value) -> str:
    return f"{money(value):.2f}"


def _percent(value) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


def dashboard(db: Session, actor: User) -> DashboardRead:
    authorize(actor, Permission.READ_DASHBOARD)
    total_donations = int(db.scalar(select(func.count()).select_from(Donation)) or 0)
    confirmed_donations = int(
        db.scalar(select(func.count()).select_from(Donation).where(Donation.status == DonationStatus.CONFIRMED.value))
        or 0
    )
    confirmed_amount = db.scalar(
        select(func.coalesce(func.sum(Donation.amount), 0)).where(Donation.status == DonationStatus.CONFIRMED.value)
    )
    active_campaigns = int(
        db.scalar(
            select(func.count()).select_from(Campaign).where(Campaign.status == CampaignStatus.ACTIVE.value)
        )
        or 0
    )
    counted_campaigns = list(
        db.scalars(
            select(Campaign).where(
                Campaign.status.notin_([CampaignStatus.DRAFT.value, CampaignStatus.CANCELLED.value])
            )
        ).all()
    )
    total_goal = sum((money(row.goal_amount) for row in counted_campaigns), money(0))
    total_raised = sum((money(row.raised_amount) for row in counted_campaigns), money(0))
    counted_projects = list(
        db.scalars(
            select(Project).where(Project.status.notin_([ProjectStatus.PLANNING.value, ProjectStatus.CANCELLED.value]))
        ).all()
    )
    total_budget = sum((money(row.budget_amount) for row in counted_projects), money(0))
    total_spent = sum((spent_for_project(db, row.id) for row in counted_projects), money(0))
    overrun_count = sum(1 for row in counted_projects if is_overrun(row.budget_amount, spent_for_project(db, row.id)))
    funds = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.status.in_(list(SPENT_EXPENSE))))
    hours = db.scalar(select(func.coalesce(func.sum(Attendance.hours), 0)))
    resources = list(db.scalars(select(Resource).order_by(Resource.name)).all())
    achievement = utilization_percent(total_goal, total_raised)
    utilization = utilization_percent(total_budget, total_spent)
    return DashboardRead(
        total_donations=total_donations,
        confirmed_donations=confirmed_donations,
        confirmed_amount=_money(confirmed_amount),
        active_fundraising_campaigns=active_campaigns,
        campaign_goal_achievement=GoalAchievement(
            total_goal=_money(total_goal),
            total_raised=_money(total_raised),
            achievement_percent=_percent(achievement),
        ),
        total_volunteers=int(db.scalar(select(func.count()).select_from(Volunteer)) or 0),
        active_community_projects=int(
            db.scalar(select(func.count()).select_from(Project).where(Project.status == ProjectStatus.ACTIVE.value))
            or 0
        ),
        projects_completed=int(
            db.scalar(
                select(func.count()).select_from(Project).where(Project.status == ProjectStatus.COMPLETED.value)
            )
            or 0
        ),
        pending_project_approvals=int(
            db.scalar(select(func.count()).select_from(Project).where(Project.approval_state == "pending")) or 0
        ),
        pending_expense_approvals=int(
            db.scalar(select(func.count()).select_from(Expense).where(Expense.status == ExpenseStatus.SUBMITTED.value))
            or 0
        ),
        total_beneficiaries_served=int(
            db.scalar(select(func.count(func.distinct(BeneficiaryAssistance.beneficiary_id)))) or 0
        ),
        volunteer_hours=_money(hours),
        milestones_achieved=int(
            db.scalar(
                select(func.count()).select_from(Milestone).where(Milestone.status == MilestoneStatus.COMPLETED.value)
            )
            or 0
        ),
        funds_utilized=_money(funds),
        project_budget_utilization=BudgetUtilization(
            total_budget=_money(total_budget),
            total_spent=_money(total_spent),
            remaining=_money(remaining_budget(total_budget, total_spent)),
            utilization_percent=_percent(utilization),
            overrun_count=overrun_count,
        ),
        resource_stock_levels=[
            StockLevel(
                id=row.id,
                name=row.name,
                category=row.category,
                quantity_on_hand=row.quantity_on_hand,
                reorder_level=row.reorder_level,
                is_low_stock=row.quantity_on_hand <= row.reorder_level,
            )
            for row in resources
        ],
    )


def list_notifications(db, actor, *, page, page_size, is_read):
    stmt = select(Notification).where(Notification.user_id == actor.id)
    if is_read is not None:
        stmt = stmt.where(Notification.is_read.is_(is_read))
    stmt = stmt.order_by(Notification.id.desc())
    return paginate(db, stmt, page, page_size)


def mark_read(db: Session, actor: User, notification_id: int) -> Notification:
    row = get_or_404(db, Notification, notification_id, "Notification")
    if row.user_id != actor.id:
        raise AppError("You can only read your own notifications", 403, "forbidden")
    row.is_read = True
    row.read_at = utcnow()
    db.flush()
    return row


def mark_all_read(db: Session, actor: User) -> int:
    rows = list(
        db.scalars(select(Notification).where(Notification.user_id == actor.id, Notification.is_read.is_(False))).all()
    )
    now = utcnow()
    for row in rows:
        row.is_read = True
        row.read_at = now
    db.flush()
    return len(rows)


def scan_notifications(db: Session, actor: User) -> dict:
    authorize(actor, Permission.SCAN_NOTIFICATIONS)
    today = date.today()
    soon = today + timedelta(days=settings.deadline_warning_days)
    tasks = db.scalars(
        select(Task).where(Task.deadline < today, Task.status != TaskStatus.DONE.value)
    ).all()
    for task in tasks:
        project = db.get(Project, task.project_id)
        notify(
            db,
            [project.manager_id if project else None],
            title="Overdue task",
            message=f"Task '{task.title}' was due on {task.deadline}.",
            category=NotificationCategory.OVERDUE.value,
            entity_type="task",
            entity_id=task.id,
        )
    milestones = db.scalars(
        select(Milestone).where(Milestone.due_date < today, Milestone.status != MilestoneStatus.COMPLETED.value)
    ).all()
    for milestone in milestones:
        project = db.get(Project, milestone.project_id)
        notify(
            db,
            [project.manager_id if project else None],
            title="Overdue milestone",
            message=f"Milestone '{milestone.title}' was due on {milestone.due_date}.",
            category=NotificationCategory.OVERDUE.value,
            entity_type="milestone",
            entity_id=milestone.id,
        )
    projects = db.scalars(
        select(Project).where(
            Project.status == ProjectStatus.ACTIVE.value,
            Project.end_date >= today,
            Project.end_date <= soon,
        )
    ).all()
    for project in projects:
        notify(
            db,
            [project.manager_id],
            title="Project deadline approaching",
            message=f"{project.title} ends on {project.end_date}.",
            category=NotificationCategory.DEADLINE.value,
            entity_type="project",
            entity_id=project.id,
        )
    campaigns = db.scalars(
        select(Campaign).where(
            Campaign.status == CampaignStatus.ACTIVE.value,
            Campaign.end_date >= today,
            Campaign.end_date <= soon,
        )
    ).all()
    for campaign in campaigns:
        notify(
            db,
            [campaign.manager_id],
            title="Campaign closing date",
            message=f"{campaign.title} closes on {campaign.end_date}.",
            category=NotificationCategory.CAMPAIGN.value,
            entity_type="campaign",
            entity_id=campaign.id,
        )
    for resource in db.scalars(select(Resource).where(Resource.quantity_on_hand <= Resource.reorder_level)).all():
        notify(
            db,
            users_with_roles(db, {Role.SUPER_ADMIN.value, Role.NGO_MANAGER.value, Role.VOLUNTEER_COORDINATOR.value}),
            title="Low resource stock",
            message=f"{resource.name} is at {resource.quantity_on_hand} {resource.unit}.",
            category=NotificationCategory.LOW_STOCK.value,
            entity_type="resource",
            entity_id=resource.id,
        )
    pending = int(
        db.scalar(select(func.count()).select_from(Expense).where(Expense.status == ExpenseStatus.SUBMITTED.value))
        or 0
    )
    if pending:
        notify(
            db,
            users_with_roles(db, {Role.FINANCE_OFFICER.value, Role.SUPER_ADMIN.value}),
            title="Pending expense approvals",
            message=f"{pending} expense(s) are still waiting for finance review.",
            category=NotificationCategory.EXPENSE.value,
            entity_type="expense",
            entity_id=None,
        )
    for project in db.scalars(select(Project)).all():
        spent = spent_for_project(db, project.id)
        if is_overrun(project.budget_amount, spent):
            notify(
                db,
                [project.manager_id, *users_with_roles(db, {Role.FINANCE_OFFICER.value})],
                title="Budget overrun",
                message=f"{project.title} has spent {_money(spent)} against a budget of {_money(project.budget_amount)}.",
                category=NotificationCategory.BUDGET.value,
                entity_type="project",
                entity_id=project.id,
            )
    db.flush()
    return {"detail": "Notification scan completed", "code": "scanned"}


def list_audit(db, actor, *, page, page_size, sort_by, sort_dir, entity_type, action, actor_id, date_from, date_to):
    authorize(actor, Permission.READ_AUDIT)
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    stmt = apply_sort(stmt, sort_by, sort_dir, {"id": AuditLog.id, "created_at": AuditLog.created_at, "action": AuditLog.action})
    return paginate(db, stmt, page, page_size)


def _pack(items, total, page, page_size, headers):
    rows = [[item.get(header, "") for header in headers] for item in items]
    return {
        "summary": {},
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "headers": headers,
        "rows": rows,
    }


def donation_report(db, actor, *, page, page_size, sort_by, sort_dir, date_from, date_to, campaign_id, status):
    authorize(actor, Permission.READ_REPORTS)
    stmt = select(Donation)
    if date_from:
        stmt = stmt.where(Donation.donation_date >= date_from)
    if date_to:
        stmt = stmt.where(Donation.donation_date <= date_to)
    if campaign_id:
        stmt = stmt.where(Donation.campaign_id == campaign_id)
    if status:
        stmt = stmt.where(Donation.status == status)
    stmt = apply_sort(
        stmt,
        sort_by if sort_by != "created_at" else "donation_date",
        sort_dir,
        {"id": Donation.id, "donation_date": Donation.donation_date, "amount": Donation.amount, "created_at": Donation.created_at},
    )
    found, total = paginate(db, stmt, page, page_size)
    donor_names = dict(db.execute(select(Donor.id, Donor.name)).all()) if found else {}
    campaign_names = dict(db.execute(select(Campaign.id, Campaign.title)).all()) if found else {}
    confirmed = [row for row in found if row.status == DonationStatus.CONFIRMED.value]
    items = [
        {
            "id": row.id,
            "donation_date": row.donation_date.isoformat(),
            "donor": donor_names.get(row.donor_id, ""),
            "campaign": campaign_names.get(row.campaign_id, ""),
            "amount": _money(row.amount),
            "method": row.method,
            "status": row.status,
            "reference_number": row.reference_number,
        }
        for row in found
    ]
    packed = _pack(items, total, page, page_size, list(items[0].keys()) if items else ["id"])
    packed["summary"] = {
        "rows": len(items),
        "confirmed_amount": _money(sum((money(row.amount) for row in confirmed), money(0))),
    }
    return packed


def campaign_report(db, actor, *, page, page_size, sort_by, sort_dir, status, category):
    authorize(actor, Permission.READ_REPORTS)
    stmt = select(Campaign)
    if status:
        stmt = stmt.where(Campaign.status == status)
    if category:
        stmt = stmt.where(Campaign.category == category)
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {"id": Campaign.id, "title": Campaign.title, "raised_amount": Campaign.raised_amount, "created_at": Campaign.created_at},
    )
    found, total = paginate(db, stmt, page, page_size)
    items = []
    for row in found:
        count = db.scalar(select(func.count()).select_from(Donation).where(Donation.campaign_id == row.id)) or 0
        items.append(
            {
                "id": row.id,
                "code": row.code,
                "title": row.title,
                "status": row.status,
                "category": row.category,
                "goal_amount": _money(row.goal_amount),
                "raised_amount": _money(row.raised_amount),
                "achievement_percent": _percent(utilization_percent(row.goal_amount, row.raised_amount)) or "",
                "donation_count": int(count),
            }
        )
    packed = _pack(items, total, page, page_size, list(items[0].keys()) if items else ["id"])
    packed["summary"] = {"campaigns": len(items)}
    return packed


def volunteer_report(db, actor, *, page, page_size, sort_by, sort_dir, status):
    authorize(actor, Permission.READ_REPORTS)
    stmt = select(Volunteer)
    if status:
        stmt = stmt.where(Volunteer.status == status)
    stmt = apply_sort(stmt, sort_by, sort_dir, {"id": Volunteer.id, "full_name": Volunteer.full_name, "created_at": Volunteer.created_at})
    found, total = paginate(db, stmt, page, page_size)
    items = []
    for row in found:
        assignments = db.scalar(
            select(func.count()).select_from(VolunteerAssignment).where(VolunteerAssignment.volunteer_id == row.id)
        ) or 0
        hours = db.scalar(
            select(func.coalesce(func.sum(VolunteerAssignment.hours_completed), 0)).where(
                VolunteerAssignment.volunteer_id == row.id
            )
        )
        items.append(
            {
                "id": row.id,
                "full_name": row.full_name,
                "email": row.email,
                "status": row.status,
                "assignments": int(assignments),
                "hours_completed": _money(hours),
            }
        )
    packed = _pack(items, total, page, page_size, list(items[0].keys()) if items else ["id"])
    packed["summary"] = {"volunteers": len(items)}
    return packed


def project_report(db, actor, *, page, page_size, sort_by, sort_dir, status, project_id):
    authorize(actor, Permission.READ_REPORTS)
    stmt = select(Project)
    if status:
        stmt = stmt.where(Project.status == status)
    if project_id:
        stmt = stmt.where(Project.id == project_id)
    stmt = apply_sort(stmt, sort_by, sort_dir, {"id": Project.id, "title": Project.title, "end_date": Project.end_date, "created_at": Project.created_at})
    found, total = paginate(db, stmt, page, page_size)
    items = []
    for row in found:
        milestones = db.scalar(select(func.count()).select_from(Milestone).where(Milestone.project_id == row.id)) or 0
        done = db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(Milestone.project_id == row.id, Milestone.status == MilestoneStatus.COMPLETED.value)
        ) or 0
        spent = spent_for_project(db, row.id)
        items.append(
            {
                "id": row.id,
                "code": row.code,
                "title": row.title,
                "status": row.status,
                "approval_state": row.approval_state,
                "location": row.location,
                "milestones": int(milestones),
                "milestones_completed": int(done),
                "budget_amount": _money(row.budget_amount),
                "spent_amount": _money(spent),
            }
        )
    packed = _pack(items, total, page, page_size, list(items[0].keys()) if items else ["id"])
    packed["summary"] = {"projects": len(items)}
    return packed


def expense_report(db, actor, *, page, page_size, sort_by, sort_dir, status, project_id, date_from, date_to):
    authorize(actor, Permission.READ_REPORTS)
    stmt = select(Expense)
    if status:
        stmt = stmt.where(Expense.status == status)
    if project_id:
        stmt = stmt.where(Expense.project_id == project_id)
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
    found, total = paginate(db, stmt, page, page_size)
    items = [
        {
            "id": row.id,
            "project_id": row.project_id,
            "category": row.category,
            "amount": _money(row.amount),
            "expense_date": row.expense_date.isoformat(),
            "status": row.status,
            "description": row.description,
        }
        for row in found
    ]
    packed = _pack(items, total, page, page_size, list(items[0].keys()) if items else ["id"])
    packed["summary"] = {"amount": _money(sum((money(row.amount) for row in found), money(0)))}
    return packed


def resource_report(db, actor, *, page, page_size, sort_by, sort_dir, project_id):
    authorize(actor, Permission.READ_REPORTS)
    stmt = select(ResourceTransaction)
    if project_id:
        stmt = stmt.where(ResourceTransaction.project_id == project_id)
    stmt = apply_sort(stmt, sort_by, sort_dir, {"id": ResourceTransaction.id, "created_at": ResourceTransaction.created_at})
    found, total = paginate(db, stmt, page, page_size)
    names = dict(db.execute(select(Resource.id, Resource.name)).all()) if found else {}
    items = [
        {
            "id": row.id,
            "resource": names.get(row.resource_id, ""),
            "movement_type": row.movement_type,
            "quantity": row.quantity,
            "project_id": row.project_id or "",
            "balance_after": row.balance_after,
            "created_at": row.created_at.isoformat(),
        }
        for row in found
    ]
    packed = _pack(items, total, page, page_size, list(items[0].keys()) if items else ["id"])
    packed["summary"] = {"movements": len(items)}
    return packed


def beneficiary_report(db, actor, *, page, page_size, sort_by, sort_dir, project_id, category):
    authorize(actor, Permission.READ_REPORTS)
    if actor.role not in {Role.SUPER_ADMIN.value, Role.NGO_MANAGER.value, Role.VOLUNTEER_COORDINATOR.value, Role.FINANCE_OFFICER.value}:
        raise AppError("Role cannot export beneficiary information", 403, "forbidden")
    stmt = select(Beneficiary)
    if category:
        stmt = stmt.where(Beneficiary.category == category)
    if project_id:
        stmt = stmt.where(Beneficiary.projects.any(Project.id == project_id))
    stmt = apply_sort(stmt, sort_by, sort_dir, {"id": Beneficiary.id, "full_name": Beneficiary.full_name, "created_at": Beneficiary.created_at})
    found, total = paginate(db, stmt, page, page_size)
    sensitive = actor.role in {Role.SUPER_ADMIN.value, Role.NGO_MANAGER.value, Role.VOLUNTEER_COORDINATOR.value}
    items = []
    for row in found:
        assistance_count = db.scalar(
            select(func.count()).select_from(BeneficiaryAssistance).where(BeneficiaryAssistance.beneficiary_id == row.id)
        ) or 0
        items.append(
            {
                "id": row.id,
                "full_name": row.full_name,
                "category": row.category,
                "contact": row.contact if sensitive else "",
                "address": row.address if sensitive else "",
                "assistance_count": int(assistance_count),
            }
        )
    packed = _pack(items, total, page, page_size, list(items[0].keys()) if items else ["id"])
    packed["summary"] = {"beneficiaries": len(items)}
    return packed
