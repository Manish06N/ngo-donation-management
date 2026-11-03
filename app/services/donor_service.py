from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import DonorStatus, DonorType, Role
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.domain.rules import money
from app.models.fundraising import Donation, Donor, DonorContact
from app.models.identity import User
from app.repositories.common import apply_sort, get_or_404, paginate
from app.schemas.fundraising import DonorCreate, DonorRead, DonorUpdate
from app.services.access import audit, authorize, donor_for_user, touch


def _value(item):
    return item.value if hasattr(item, "value") else item


def _require_org(donor_type: str, organization_name: str | None) -> None:
    if donor_type == DonorType.ORGANIZATION.value and not organization_name:
        raise AppError("Organization donors need an organization name", 422, "organization_name_required")


def _stats(db: Session, donor_ids: list[int]) -> dict[int, tuple[int, object]]:
    if not donor_ids:
        return {}
    confirmed = Donation.status == "confirmed"
    rows = db.execute(
        select(
            Donation.donor_id,
            func.count(Donation.id),
            func.coalesce(func.sum(case((confirmed, Donation.amount), else_=0)), 0),
        )
        .where(Donation.donor_id.in_(donor_ids))
        .group_by(Donation.donor_id)
    ).all()
    return {row[0]: (int(row[1]), money(row[2])) for row in rows}


def present(db: Session, donor: Donor, stats: tuple | None = None) -> DonorRead:
    count, total = stats if stats is not None else _stats(db, [donor.id]).get(donor.id, (0, money(0)))
    data = DonorRead.model_validate(donor)
    return data.model_copy(update={"donation_count": count, "total_donated": total})


def _scoped_stmt(db: Session, actor: User):
    if actor.role == Role.DONOR.value:
        own = donor_for_user(db, actor)
        if own is None:
            return select(Donor).where(Donor.id == -1)
        return select(Donor).where(Donor.id == own.id)
    authorize(actor, Permission.READ_DONORS)
    return select(Donor)


def create_donor(db: Session, actor: User, payload: DonorCreate) -> Donor:
    authorize(actor, Permission.WRITE_DONORS)
    donor_type = _value(payload.donor_type)
    _require_org(donor_type, payload.organization_name)
    if db.scalar(select(Donor.id).where(Donor.email == payload.email)):
        raise AppError("A donor with this email already exists", 409, "email_taken")
    if payload.user_id is not None:
        user = get_or_404(db, User, payload.user_id, "User")
        if user.role != Role.DONOR.value:
            raise AppError("Linked user must have the donor role", 422, "invalid_user")
        if db.scalar(select(Donor.id).where(Donor.user_id == user.id)):
            raise AppError("That user already has a donor profile", 409, "already_linked")
    donor = Donor(
        user_id=payload.user_id,
        donor_type=donor_type,
        name=payload.name,
        organization_name=payload.organization_name,
        email=payload.email,
        phone=payload.phone,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        postal_code=payload.postal_code,
        notes=payload.notes,
        status=DonorStatus.ACTIVE.value,
        created_by=actor.id,
    )
    db.add(donor)
    db.flush()
    db.add(
        DonorContact(
            donor_id=donor.id,
            name=payload.contact_name or payload.name,
            email=payload.email,
            phone=payload.contact_phone or payload.phone,
            role_label="primary",
            is_primary=True,
        )
    )
    audit(db, actor.id, "donor.created", "donor", donor.id, {"email": donor.email, "type": donor.donor_type})
    db.flush()
    return donor


def update_donor(db: Session, actor: User, donor_id: int, payload: DonorUpdate) -> Donor:
    donor = get_donor(db, actor, donor_id)
    changes = payload.model_dump(exclude_unset=True)
    if actor.role == Role.DONOR.value:
        blocked = {"status", "donor_type", "organization_name"} & set(changes)
        if blocked:
            raise AppError("Donors cannot change their type or status", 403, "forbidden")
    else:
        authorize(actor, Permission.WRITE_DONORS)
    if "donor_type" in changes:
        changes["donor_type"] = _value(changes["donor_type"])
    if "status" in changes:
        changes["status"] = _value(changes["status"])
    donor_type = changes.get("donor_type", donor.donor_type)
    organization_name = changes.get("organization_name", donor.organization_name)
    _require_org(donor_type, organization_name)
    for key, value in changes.items():
        setattr(donor, key, value)
    primary = next((contact for contact in donor.contacts if contact.is_primary), None)
    if primary is not None:
        primary.name = donor.name
        primary.phone = donor.phone
    touch(donor)
    audit(db, actor.id, "donor.updated", "donor", donor.id, {"fields": list(changes)})
    db.flush()
    return donor


def get_donor(db: Session, actor: User, donor_id: int) -> Donor:
    donor = db.scalar(select(Donor).options(selectinload(Donor.contacts)).where(Donor.id == donor_id))
    if donor is None:
        raise AppError("Donor not found", 404, "not_found")
    if actor.role == Role.DONOR.value:
        own = donor_for_user(db, actor)
        if own is None or own.id != donor.id:
            raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
        return donor
    authorize(actor, Permission.READ_DONORS)
    return donor


def list_donors(db: Session, actor: User, *, page, page_size, sort_by, sort_dir, q, donor_type, status, city):
    stmt = _scoped_stmt(db, actor).options(selectinload(Donor.contacts))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Donor.name.ilike(like)
            | Donor.organization_name.ilike(like)
            | Donor.email.ilike(like)
            | Donor.phone.ilike(like)
        )
    if donor_type:
        stmt = stmt.where(Donor.donor_type == donor_type)
    if status:
        stmt = stmt.where(Donor.status == status)
    if city:
        stmt = stmt.where(Donor.city.ilike(city))
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {"id": Donor.id, "name": Donor.name, "email": Donor.email, "created_at": Donor.created_at, "city": Donor.city},
    )
    rows, total = paginate(db, stmt, page, page_size)
    stats = _stats(db, [row.id for row in rows])
    return [present(db, row, stats.get(row.id, (0, money(0)))) for row in rows], total
