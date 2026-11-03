from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.identity import User
from app.schemas.volunteers import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    AttendanceCreate,
    AttendanceRead,
    VolunteerCreate,
    VolunteerRead,
    VolunteerUpdate,
)
from app.services import volunteer_service
from app.services.access import volunteer_for_user
from app.domain.errors import AppError

router = APIRouter(prefix="/volunteers", tags=["Volunteers"])
assignments = APIRouter(prefix="/assignments", tags=["Volunteer assignments"])


@router.post("", response_model=VolunteerRead, status_code=status.HTTP_201_CREATED)
def create_volunteer(payload: VolunteerCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return volunteer_service.create_volunteer(db, actor, payload)


@router.get("", response_model=dict)
def list_volunteers(
    listing: Listing = Depends(),
    q: str | None = None,
    status: str | None = None,
    skill: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search volunteers by name, email, phone, status, or skill."""
    rows, total = volunteer_service.list_volunteers(
        db, actor, page=listing.page, page_size=listing.page_size, sort_by=listing.sort_by, sort_dir=listing.sort_dir, q=q, status=status, skill=skill
    )
    return as_page([VolunteerRead.model_validate(row) for row in rows], total, listing)


@router.get("/me", response_model=VolunteerRead)
def my_volunteer(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = volunteer_for_user(db, actor)
    if row is None:
        raise AppError("Volunteer profile not found", 404, "not_found")
    return volunteer_service.get_volunteer(db, actor, row.id)


@router.get("/{volunteer_id}", response_model=VolunteerRead)
def get_volunteer(volunteer_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return volunteer_service.get_volunteer(db, actor, volunteer_id)


@router.patch("/{volunteer_id}", response_model=VolunteerRead)
def update_volunteer(
    volunteer_id: int,
    payload: VolunteerUpdate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return volunteer_service.update_volunteer(db, actor, volunteer_id, payload)


@assignments.post("", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def create_assignment(payload: AssignmentCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Assign a volunteer. Overlapping open assignments for the same person are refused."""
    return volunteer_service.create_assignment(db, actor, payload)


@assignments.get("", response_model=dict)
def list_assignments(
    listing: Listing = Depends(),
    volunteer_id: int | None = None,
    project_id: int | None = None,
    status: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = volunteer_service.list_assignments(
        db,
        actor,
        page=listing.page,
        page_size=listing.page_size,
        sort_by=listing.sort_by,
        sort_dir=listing.sort_dir,
        volunteer_id=volunteer_id,
        project_id=project_id,
        status=status,
    )
    return as_page([AssignmentRead.model_validate(row) for row in rows], total, listing)


@assignments.patch("/{assignment_id}", response_model=AssignmentRead)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return volunteer_service.update_assignment(db, actor, assignment_id, payload)


@assignments.post("/{assignment_id}/attendance", response_model=AttendanceRead)
def record_attendance(
    assignment_id: int,
    payload: AttendanceCreate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a day's attendance. Hours roll up onto the assignment."""
    return volunteer_service.record_attendance(db, actor, assignment_id, payload)


@assignments.get("/{assignment_id}/attendance", response_model=list[AttendanceRead])
def list_attendance(assignment_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return volunteer_service.list_attendance(db, actor, assignment_id)
