"""Authorization, audit, and in-app notifications used by every workflow."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import AssignmentStatus, Role
from app.domain.errors import AppError
from app.domain.permissions import role_has
from app.models.engagement import AuditLog, Notification
from app.models.fundraising import Donor
from app.models.identity import User
from app.models.volunteering import Volunteer, VolunteerAssignment
from app.utils.time import utcnow

STAFF_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.NGO_MANAGER.value,
    Role.FINANCE_OFFICER.value,
    Role.VOLUNTEER_COORDINATOR.value,
}
PROJECT_MANAGER_ROLES = {Role.SUPER_ADMIN.value, Role.NGO_MANAGER.value}


def authorize(actor: User, permission: str) -> None:
    if not role_has(actor.role, permission):
        raise AppError(f"Role '{actor.role}' cannot perform this action", 403, "forbidden")


def audit(db: Session, actor_id: int | None, action: str, entity_type: str, entity_id: int | None, details: dict | None = None) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )


def users_with_roles(db: Session, roles: set[str]) -> list[int]:
    return list(db.scalars(select(User.id).where(User.role.in_(roles), User.is_active.is_(True))).all())


def notify(
    db: Session,
    user_ids: list[int | None],
    *,
    title: str,
    message: str,
    category: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> None:
    for user_id in {item for item in user_ids if item}:
        existing = db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.category == category,
                Notification.entity_type == entity_type,
                Notification.entity_id == entity_id,
                Notification.is_read.is_(False),
            )
        )
        if existing:
            continue
        db.add(
            Notification(
                user_id=user_id,
                title=title,
                message=message,
                category=category,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )


def donor_for_user(db: Session, user: User) -> Donor | None:
    return db.scalar(select(Donor).where(Donor.user_id == user.id))


def volunteer_for_user(db: Session, user: User) -> Volunteer | None:
    return db.scalar(select(Volunteer).where(Volunteer.user_id == user.id))


def touch(row) -> None:
    row.updated_at = utcnow()


def assigned_project_ids(db: Session, actor: User) -> list[int]:
    volunteer = volunteer_for_user(db, actor)
    if volunteer is None:
        return []
    return list(
        db.scalars(
            select(VolunteerAssignment.project_id).where(
                VolunteerAssignment.volunteer_id == volunteer.id,
                VolunteerAssignment.status != AssignmentStatus.CANCELLED.value,
            )
        ).all()
    )


def assert_project_visible(db: Session, actor: User, project_id: int) -> None:
    if actor.role == Role.VOLUNTEER.value:
        if project_id not in assigned_project_ids(db, actor):
            raise AppError("You are not assigned to this project", 403, "forbidden")
        return
    if actor.role == Role.DONOR.value:
        raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
    authorize(actor, "read_projects")
