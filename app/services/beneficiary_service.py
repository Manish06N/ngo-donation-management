from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import MovementType, Role
from app.domain.errors import AppError
from app.domain.permissions import Permission, role_has
from app.models.beneficiaries import Beneficiary, BeneficiaryAssistance
from app.models.identity import User
from app.models.projects import Project
from app.repositories.common import apply_sort, get_or_404, paginate
from app.schemas.insights import AssistanceCreate, BeneficiaryCreate, BeneficiaryRead, BeneficiaryUpdate
from app.services.access import assert_project_visible, assigned_project_ids, audit, authorize
from app.services.resource_service import apply_movement


def _value(item):
    return item.value if hasattr(item, "value") else item


def present(actor: User, row: Beneficiary) -> BeneficiaryRead:
    data = BeneficiaryRead(
        id=row.id,
        full_name=row.full_name,
        category=row.category,
        contact=row.contact,
        address=row.address,
        notes=row.notes,
        project_ids=[project.id for project in row.projects],
        created_at=row.created_at,
    )
    if not role_has(actor.role, Permission.READ_BENEFICIARY_SENSITIVE):
        return data.model_copy(update={"contact": None, "address": None, "notes": None})
    return data


def _load(db: Session, beneficiary_id: int) -> Beneficiary:
    row = db.scalar(
        select(Beneficiary).options(selectinload(Beneficiary.projects)).where(Beneficiary.id == beneficiary_id)
    )
    if row is None:
        raise AppError("Beneficiary not found", 404, "not_found")
    return row


def _link(db: Session, beneficiary: Beneficiary, project_ids: list[int]) -> None:
    projects = []
    for project_id in project_ids:
        projects.append(get_or_404(db, Project, project_id, "Project"))
    beneficiary.projects = projects


def create_beneficiary(db: Session, actor: User, payload: BeneficiaryCreate) -> Beneficiary:
    authorize(actor, Permission.WRITE_BENEFICIARIES)
    row = Beneficiary(
        full_name=payload.full_name,
        category=_value(payload.category),
        contact=payload.contact,
        address=payload.address,
        notes=payload.notes,
        created_by=actor.id,
    )
    db.add(row)
    db.flush()
    if payload.project_ids:
        _link(db, row, payload.project_ids)
    audit(db, actor.id, "beneficiary.created", "beneficiary", row.id, {"category": row.category})
    db.flush()
    return _load(db, row.id)


def update_beneficiary(db: Session, actor: User, beneficiary_id: int, payload: BeneficiaryUpdate) -> Beneficiary:
    authorize(actor, Permission.WRITE_BENEFICIARIES)
    row = _load(db, beneficiary_id)
    changes = payload.model_dump(exclude_unset=True)
    project_ids = changes.pop("project_ids", None)
    if "category" in changes and changes["category"] is not None:
        changes["category"] = _value(changes["category"])
    for key, value in changes.items():
        setattr(row, key, value)
    if project_ids is not None:
        _link(db, row, project_ids)
    audit(db, actor.id, "beneficiary.updated", "beneficiary", row.id, {"fields": list(changes)})
    db.flush()
    return _load(db, row.id)


def get_beneficiary(db: Session, actor: User, beneficiary_id: int) -> Beneficiary:
    row = _load(db, beneficiary_id)
    if actor.role == Role.VOLUNTEER.value:
        allowed = set(assigned_project_ids(db, actor))
        if not allowed.intersection({project.id for project in row.projects}):
            raise AppError("Role 'volunteer' cannot perform this action", 403, "forbidden")
        return row
    authorize(actor, Permission.READ_BENEFICIARIES)
    return row


def list_beneficiaries(db, actor, *, page, page_size, sort_by, sort_dir, q, category, project_id):
    if actor.role == Role.VOLUNTEER.value:
        allowed = assigned_project_ids(db, actor) or [-1]
        stmt = select(Beneficiary).join(Beneficiary.projects).where(Project.id.in_(allowed)).options(selectinload(Beneficiary.projects))
    elif actor.role == Role.DONOR.value:
        raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
    else:
        authorize(actor, Permission.READ_BENEFICIARIES)
        stmt = select(Beneficiary).options(selectinload(Beneficiary.projects))
    if q:
        stmt = stmt.where(Beneficiary.full_name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Beneficiary.category == category)
    if project_id:
        stmt = stmt.where(Beneficiary.projects.any(Project.id == project_id))
    stmt = apply_sort(stmt, sort_by, sort_dir, {"id": Beneficiary.id, "full_name": Beneficiary.full_name, "created_at": Beneficiary.created_at})
    rows, total = paginate(db, stmt, page, page_size)
    return [present(actor, row) for row in rows], total


def record_assistance(db: Session, actor: User, beneficiary_id: int, payload: AssistanceCreate) -> BeneficiaryAssistance:
    beneficiary = _load(db, beneficiary_id)
    if actor.role == Role.VOLUNTEER.value:
        assert_project_visible(db, actor, payload.project_id)
    else:
        authorize(actor, Permission.RECORD_ASSISTANCE)
    if payload.resource_id is not None:
        if payload.quantity is None:
            raise AppError("Resource assistance needs a quantity", 422, "invalid_quantity")
        apply_movement(
            db,
            actor,
            payload.resource_id,
            MovementType.ALLOCATION.value,
            payload.quantity,
            payload.project_id,
            f"Assistance for {beneficiary.full_name}",
            check_permission=False,
        )
    if payload.project_id not in {project.id for project in beneficiary.projects}:
        project = get_or_404(db, Project, payload.project_id, "Project")
        beneficiary.projects.append(project)
    row = BeneficiaryAssistance(
        beneficiary_id=beneficiary.id,
        project_id=payload.project_id,
        assistance_type=payload.assistance_type,
        description=payload.description,
        quantity=payload.quantity,
        distribution_date=payload.distribution_date,
        resource_id=payload.resource_id,
        recorded_by=actor.id,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        actor.id,
        "assistance.recorded",
        "beneficiary",
        beneficiary.id,
        {"project_id": payload.project_id, "type": payload.assistance_type, "assistance_id": row.id},
    )
    return row


def list_assistance(db: Session, actor: User, beneficiary_id: int):
    get_beneficiary(db, actor, beneficiary_id)
    return list(
        db.scalars(
            select(BeneficiaryAssistance)
            .where(BeneficiaryAssistance.beneficiary_id == beneficiary_id)
            .order_by(BeneficiaryAssistance.distribution_date.desc())
        ).all()
    )
