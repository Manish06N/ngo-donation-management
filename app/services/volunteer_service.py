from decimal import Decimal

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.domain.enums import AssignmentStatus, Role, VolunteerStatus
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.domain.rules import ensure_date_order, money, ranges_overlap
from app.domain.transitions import OPEN_ASSIGNMENT
from app.models.identity import User
from app.models.projects import Project
from app.models.volunteering import Attendance, Volunteer, VolunteerAssignment
from app.repositories.common import apply_sort, get_for_update, get_or_404, paginate
from app.schemas.volunteers import AssignmentCreate, AssignmentUpdate, AttendanceCreate, VolunteerCreate, VolunteerUpdate
from app.services.access import (
    assert_project_visible,
    audit,
    authorize,
    notify,
    touch,
    users_with_roles,
    volunteer_for_user,
)
from app.domain.enums import NotificationCategory, ProjectStatus


ASSIGNABLE_PROJECTS = {ProjectStatus.APPROVED.value, ProjectStatus.ACTIVE.value}


def _value(item):
    return item.value if hasattr(item, "value") else item


def create_volunteer(db: Session, actor: User, payload: VolunteerCreate) -> Volunteer:
    authorize(actor, Permission.WRITE_VOLUNTEERS)
    if db.scalar(select(Volunteer.id).where(Volunteer.email == payload.email)):
        raise AppError("A volunteer with this email already exists", 409, "email_taken")
    if payload.user_id is not None:
        user = get_or_404(db, User, payload.user_id, "User")
        if user.role != Role.VOLUNTEER.value:
            raise AppError("Linked user must have the volunteer role", 422, "invalid_user")
        if db.scalar(select(Volunteer.id).where(Volunteer.user_id == user.id)):
            raise AppError("That user already has a volunteer profile", 409, "already_linked")
    volunteer = Volunteer(
        user_id=payload.user_id,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        address=payload.address,
        skills=payload.skills,
        experience=payload.experience,
        availability=payload.availability,
        status=_value(payload.status),
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
        created_by=actor.id,
    )
    db.add(volunteer)
    db.flush()
    audit(db, actor.id, "volunteer.created", "volunteer", volunteer.id, {"email": volunteer.email})
    return volunteer


def update_volunteer(db: Session, actor: User, volunteer_id: int, payload: VolunteerUpdate) -> Volunteer:
    volunteer = get_volunteer(db, actor, volunteer_id)
    changes = payload.model_dump(exclude_unset=True)
    if actor.role == Role.VOLUNTEER.value:
        if "status" in changes:
            raise AppError("Volunteers cannot change their own status", 403, "forbidden")
    else:
        authorize(actor, Permission.WRITE_VOLUNTEERS)
    if "status" in changes and changes["status"] is not None:
        changes["status"] = _value(changes["status"])
    for key, value in changes.items():
        setattr(volunteer, key, value)
    touch(volunteer)
    audit(db, actor.id, "volunteer.updated", "volunteer", volunteer.id, {"fields": list(changes)})
    db.flush()
    return volunteer


def get_volunteer(db: Session, actor: User, volunteer_id: int) -> Volunteer:
    volunteer = get_or_404(db, Volunteer, volunteer_id, "Volunteer")
    if actor.role == Role.VOLUNTEER.value:
        own = volunteer_for_user(db, actor)
        if own is None or own.id != volunteer.id:
            raise AppError("Role 'volunteer' cannot perform this action", 403, "forbidden")
        return volunteer
    authorize(actor, Permission.READ_VOLUNTEERS)
    return volunteer


def list_volunteers(db, actor, *, page, page_size, sort_by, sort_dir, q, status, skill):
    authorize(actor, Permission.READ_VOLUNTEERS)
    stmt = select(Volunteer)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Volunteer.full_name.ilike(like) | Volunteer.email.ilike(like) | Volunteer.phone.ilike(like))
    if status:
        stmt = stmt.where(Volunteer.status == status)
    if skill:
        stmt = stmt.where(cast(Volunteer.skills, String).ilike(f"%{skill}%"))
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {"id": Volunteer.id, "full_name": Volunteer.full_name, "email": Volunteer.email, "created_at": Volunteer.created_at},
    )
    return paginate(db, stmt, page, page_size)


def create_assignment(db: Session, actor: User, payload: AssignmentCreate) -> VolunteerAssignment:
    authorize(actor, Permission.ASSIGN_VOLUNTEERS)
    ensure_date_order(payload.start_date, payload.end_date)
    volunteer = get_for_update(db, Volunteer, payload.volunteer_id, "Volunteer")
    if volunteer.status != VolunteerStatus.ACTIVE.value:
        raise AppError("Only active volunteers can be assigned", 409, "volunteer_not_active")
    project = get_or_404(db, Project, payload.project_id, "Project")
    if project.status not in ASSIGNABLE_PROJECTS:
        raise AppError("Volunteers can be assigned only to approved or active projects", 409, "project_not_assignable")
    _reject_overlap(db, volunteer.id, payload.start_date, payload.end_date, None)
    assignment = VolunteerAssignment(
        volunteer_id=volunteer.id,
        project_id=project.id,
        responsibility=payload.responsibility,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=AssignmentStatus.ASSIGNED.value,
        hours_completed=Decimal("0.00"),
        notes=payload.notes,
        assigned_by=actor.id,
    )
    db.add(assignment)
    db.flush()
    recipients = users_with_roles(db, {Role.VOLUNTEER_COORDINATOR.value, Role.NGO_MANAGER.value})
    recipients.append(volunteer.user_id)
    notify(
        db,
        recipients,
        title="New volunteer assignment",
        message=f"{volunteer.full_name} was assigned to {project.title} as {payload.responsibility}.",
        category=NotificationCategory.ASSIGNMENT.value,
        entity_type="assignment",
        entity_id=assignment.id,
    )
    audit(
        db,
        actor.id,
        "assignment.created",
        "assignment",
        assignment.id,
        {"volunteer_id": volunteer.id, "project_id": project.id, "responsibility": payload.responsibility},
    )
    return assignment


def update_assignment(db: Session, actor: User, assignment_id: int, payload: AssignmentUpdate) -> VolunteerAssignment:
    authorize(actor, Permission.ASSIGN_VOLUNTEERS)
    assignment = get_or_404(db, VolunteerAssignment, assignment_id, "Assignment")
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        changes["status"] = _value(changes["status"])
    start = changes.get("start_date", assignment.start_date)
    end = changes.get("end_date", assignment.end_date)
    ensure_date_order(start, end)
    status = changes.get("status", assignment.status)
    if status in OPEN_ASSIGNMENT:
        _reject_overlap(db, assignment.volunteer_id, start, end, assignment.id)
    previous = assignment.status
    for key, value in changes.items():
        setattr(assignment, key, value)
    touch(assignment)
    audit(
        db,
        actor.id,
        "assignment.updated",
        "assignment",
        assignment.id,
        {"fields": list(changes), "from": previous, "to": assignment.status},
    )
    db.flush()
    return assignment


def _reject_overlap(db, volunteer_id, start, end, ignore_id):
    existing = db.scalars(
        select(VolunteerAssignment).where(
            VolunteerAssignment.volunteer_id == volunteer_id,
            VolunteerAssignment.status.in_(list(OPEN_ASSIGNMENT)),
        )
    ).all()
    for row in existing:
        if ignore_id is not None and row.id == ignore_id:
            continue
        if ranges_overlap(start, end, row.start_date, row.end_date):
            raise AppError(
                f"Volunteer already has overlapping assignment {row.id}",
                409,
                "assignment_conflict",
            )


def list_assignments(db, actor, *, page, page_size, sort_by, sort_dir, volunteer_id, project_id, status):
    if actor.role == Role.VOLUNTEER.value:
        own = volunteer_for_user(db, actor)
        stmt = select(VolunteerAssignment).where(VolunteerAssignment.volunteer_id == (own.id if own else -1))
    else:
        authorize(actor, Permission.READ_VOLUNTEERS)
        stmt = select(VolunteerAssignment)
    if volunteer_id:
        stmt = stmt.where(VolunteerAssignment.volunteer_id == volunteer_id)
    if project_id:
        stmt = stmt.where(VolunteerAssignment.project_id == project_id)
    if status:
        stmt = stmt.where(VolunteerAssignment.status == status)
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {"id": VolunteerAssignment.id, "start_date": VolunteerAssignment.start_date, "created_at": VolunteerAssignment.created_at},
    )
    return paginate(db, stmt, page, page_size)


def record_attendance(db: Session, actor: User, assignment_id: int, payload: AttendanceCreate) -> Attendance:
    assignment = get_or_404(db, VolunteerAssignment, assignment_id, "Assignment")
    if actor.role == Role.VOLUNTEER.value:
        own = volunteer_for_user(db, actor)
        if own is None or own.id != assignment.volunteer_id:
            raise AppError("Role 'volunteer' cannot perform this action", 403, "forbidden")
    else:
        authorize(actor, Permission.ASSIGN_VOLUNTEERS)
    if assignment.status == AssignmentStatus.CANCELLED.value:
        raise AppError("Cancelled assignments do not take attendance", 409, "assignment_cancelled")
    existing = db.scalar(
        select(Attendance).where(
            Attendance.assignment_id == assignment.id,
            Attendance.attended_on == payload.attended_on,
        )
    )
    status = _value(payload.status)
    hours = money(payload.hours)
    if existing is None:
        existing = Attendance(
            assignment_id=assignment.id,
            attended_on=payload.attended_on,
            status=status,
            hours=hours,
            notes=payload.notes,
            recorded_by=actor.id,
        )
        db.add(existing)
    else:
        existing.status = status
        existing.hours = hours
        existing.notes = payload.notes
        existing.recorded_by = actor.id
    db.flush()
    total = db.scalar(
        select(func.coalesce(func.sum(Attendance.hours), 0)).where(Attendance.assignment_id == assignment.id)
    )
    assignment.hours_completed = money(total)
    audit(
        db,
        actor.id,
        "attendance.recorded",
        "assignment",
        assignment.id,
        {"date": str(payload.attended_on), "hours": str(hours), "status": status},
    )
    db.flush()
    return existing


def list_attendance(db: Session, actor: User, assignment_id: int):
    assignment = get_or_404(db, VolunteerAssignment, assignment_id, "Assignment")
    if actor.role == Role.VOLUNTEER.value:
        assert_project_visible(db, actor, assignment.project_id)
    else:
        authorize(actor, Permission.READ_VOLUNTEERS)
    return list(
        db.scalars(select(Attendance).where(Attendance.assignment_id == assignment.id).order_by(Attendance.attended_on)).all()
    )
