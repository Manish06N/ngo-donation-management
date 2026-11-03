from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import DonationStatus, DonorStatus, ReceiptStatus, Role
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.domain.rules import apply_donation_total, money, normalize_reference
from app.domain.transitions import ACCEPTING_DONATIONS, DONATION_TRANSITIONS, MONEY_LEAVING, ensure_transition
from app.models.fundraising import Campaign, Donation, DonationReceipt, Donor
from app.models.identity import User
from app.repositories.common import apply_sort, get_for_update, get_or_404, next_code, paginate
from app.schemas.fundraising import DonationCreate, DonationUpdate
from app.services.access import audit, authorize, donor_for_user
from app.utils.time import utcnow


def _scoped(db: Session, actor: User):
    stmt = select(Donation)
    if actor.role == Role.DONOR.value:
        own = donor_for_user(db, actor)
        if own is None:
            return stmt.where(Donation.id == -1)
        return stmt.where(Donation.donor_id == own.id)
    authorize(actor, Permission.READ_DONATIONS)
    return stmt


def create_donation(db: Session, actor: User, payload: DonationCreate) -> Donation:
    authorize(actor, Permission.WRITE_DONATIONS)
    donor = get_or_404(db, Donor, payload.donor_id, "Donor")
    if donor.status != DonorStatus.ACTIVE.value:
        raise AppError("Inactive or blocked donors cannot make donations", 409, "donor_inactive")
    campaign = get_for_update(db, Campaign, payload.campaign_id, "Campaign")
    if campaign.status not in ACCEPTING_DONATIONS:
        raise AppError("Only active campaigns can accept new donations", 409, "campaign_not_accepting")
    reference = normalize_reference(payload.reference_number)
    if db.scalar(select(Donation.id).where(Donation.reference_number == reference)):
        raise AppError("Donation reference already exists", 409, "duplicate_reference")
    amount = money(payload.amount)
    if amount <= 0:
        raise AppError("Donation amount must be positive", 422, "invalid_amount")
    donation = Donation(
        donor_id=donor.id,
        campaign_id=campaign.id,
        amount=amount,
        donation_date=payload.donation_date,
        method=payload.method.value if hasattr(payload.method, "value") else payload.method,
        reference_number=reference,
        status=DonationStatus.PENDING.value,
        notes=payload.notes,
        recorded_by=actor.id,
    )
    db.add(donation)
    db.flush()
    audit(
        db,
        actor.id,
        "donation.created",
        "donation",
        donation.id,
        {"amount": str(amount), "reference": reference, "campaign_id": campaign.id, "donor_id": donor.id},
    )
    return donation


def update_donation(db: Session, actor: User, donation_id: int, payload: DonationUpdate) -> Donation:
    authorize(actor, Permission.WRITE_DONATIONS)
    donation = get_or_404(db, Donation, donation_id, "Donation")
    changes = payload.model_dump(exclude_unset=True)
    if donation.status != DonationStatus.PENDING.value:
        locked = set(changes) - {"notes"}
        if locked:
            raise AppError("Only notes can change after a donation leaves pending", 409, "donation_locked")
    if "method" in changes and changes["method"] is not None:
        changes["method"] = changes["method"].value if hasattr(changes["method"], "value") else changes["method"]
    if "amount" in changes and changes["amount"] is not None:
        changes["amount"] = money(changes["amount"])
        if changes["amount"] <= 0:
            raise AppError("Donation amount must be positive", 422, "invalid_amount")
    for key, value in changes.items():
        setattr(donation, key, value)
    audit(db, actor.id, "donation.updated", "donation", donation.id, {"fields": list(changes)})
    db.flush()
    return donation


def change_status(db: Session, actor: User, donation_id: int, new_status: str) -> Donation:
    authorize(actor, Permission.CONFIRM_DONATIONS)
    donation = db.scalar(select(Donation).options(selectinload(Donation.receipt)).where(Donation.id == donation_id))
    if donation is None:
        raise AppError("Donation not found", 404, "not_found")
    ensure_transition(donation.status, new_status, DONATION_TRANSITIONS, "Donation")
    campaign = get_for_update(db, Campaign, donation.campaign_id, "Campaign")
    previous = donation.status
    if new_status == DonationStatus.CONFIRMED.value:
        if campaign.status not in ACCEPTING_DONATIONS:
            raise AppError("Only active campaigns can accept donations", 409, "campaign_not_accepting")
        donor = get_or_404(db, Donor, donation.donor_id, "Donor")
        if donor.status != DonorStatus.ACTIVE.value:
            raise AppError("Inactive or blocked donors cannot confirm donations", 409, "donor_inactive")
        campaign.raised_amount = apply_donation_total(campaign.raised_amount, donation.amount, leaving=False)
    elif new_status in MONEY_LEAVING:
        campaign.raised_amount = apply_donation_total(campaign.raised_amount, donation.amount, leaving=True)
        _void_receipt(db, actor, donation, new_status)
    donation.status = new_status
    audit(
        db,
        actor.id,
        "donation.status_changed",
        "donation",
        donation.id,
        {"from": previous, "to": new_status, "amount": str(donation.amount), "campaign_id": campaign.id},
    )
    db.flush()
    return donation


def _void_receipt(db: Session, actor: User, donation: Donation, reason: str) -> None:
    receipt = donation.receipt
    if receipt is None or receipt.status != ReceiptStatus.ISSUED.value:
        return
    receipt.status = ReceiptStatus.VOID.value
    receipt.voided_at = utcnow()
    receipt.void_reason = reason
    audit(db, actor.id, "receipt.voided", "receipt", receipt.id, {"donation_id": donation.id, "reason": reason})


def get_donation(db: Session, actor: User, donation_id: int) -> Donation:
    donation = get_or_404(db, Donation, donation_id, "Donation")
    if actor.role == Role.DONOR.value:
        own = donor_for_user(db, actor)
        if own is None or donation.donor_id != own.id:
            raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
        return donation
    authorize(actor, Permission.READ_DONATIONS)
    return donation


def list_donations(
    db, actor, *, page, page_size, sort_by, sort_dir, status, campaign_id, donor_id, method, date_from, date_to
):
    stmt = _scoped(db, actor)
    if status:
        stmt = stmt.where(Donation.status == status)
    if campaign_id:
        stmt = stmt.where(Donation.campaign_id == campaign_id)
    if donor_id:
        if actor.role == Role.DONOR.value:
            own = donor_for_user(db, actor)
            if own is None or own.id != donor_id:
                raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
        stmt = stmt.where(Donation.donor_id == donor_id)
    if method:
        stmt = stmt.where(Donation.method == method)
    if date_from:
        stmt = stmt.where(Donation.donation_date >= date_from)
    if date_to:
        stmt = stmt.where(Donation.donation_date <= date_to)
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {
            "id": Donation.id,
            "amount": Donation.amount,
            "donation_date": Donation.donation_date,
            "created_at": Donation.created_at,
            "status": Donation.status,
        },
    )
    return paginate(db, stmt, page, page_size)


def issue_receipt(db: Session, actor: User, donation_id: int) -> DonationReceipt:
    authorize(actor, Permission.ISSUE_RECEIPTS)
    donation = db.scalar(select(Donation).options(selectinload(Donation.receipt)).where(Donation.id == donation_id))
    if donation is None:
        raise AppError("Donation not found", 404, "not_found")
    if donation.status != DonationStatus.CONFIRMED.value:
        raise AppError("Receipts are issued only for confirmed donations", 409, "donation_not_confirmed")
    if donation.receipt is not None:
        raise AppError("A receipt already exists for this donation", 409, "duplicate_receipt")
    receipt = DonationReceipt(
        donation_id=donation.id,
        receipt_number=next_code(db, "receipt", "RCP"),
        status=ReceiptStatus.ISSUED.value,
        issued_by=actor.id,
    )
    db.add(receipt)
    db.flush()
    audit(
        db,
        actor.id,
        "receipt.issued",
        "receipt",
        receipt.id,
        {"number": receipt.receipt_number, "donation_id": donation.id},
    )
    return receipt


def get_receipt(db: Session, actor: User, receipt_id: int) -> DonationReceipt:
    receipt = db.scalar(
        select(DonationReceipt).options(selectinload(DonationReceipt.donation)).where(DonationReceipt.id == receipt_id)
    )
    if receipt is None:
        raise AppError("Receipt not found", 404, "not_found")
    _assert_can_see_donation(db, actor, receipt.donation)
    return receipt


def list_donor_receipts(db: Session, actor: User, donor_id: int):
    donor = get_or_404(db, Donor, donor_id, "Donor")
    if actor.role == Role.DONOR.value:
        own = donor_for_user(db, actor)
        if own is None or own.id != donor.id:
            raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
    else:
        authorize(actor, Permission.READ_DONATIONS)
    return list(
        db.scalars(
            select(DonationReceipt)
            .join(Donation, Donation.id == DonationReceipt.donation_id)
            .where(Donation.donor_id == donor.id)
            .order_by(DonationReceipt.id.desc())
        ).all()
    )


def _assert_can_see_donation(db: Session, actor: User, donation: Donation) -> None:
    if actor.role == Role.DONOR.value:
        own = donor_for_user(db, actor)
        if own is None or donation.donor_id != own.id:
            raise AppError("Role 'donor' cannot perform this action", 403, "forbidden")
        return
    authorize(actor, Permission.READ_DONATIONS)
