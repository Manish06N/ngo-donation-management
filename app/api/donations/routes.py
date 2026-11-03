from datetime import date

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.fundraising import Campaign, Donor
from app.models.identity import User
from app.schemas.fundraising import DonationCreate, DonationRead, DonationStatusChange, DonationUpdate, ReceiptRead
from app.services import donation_service
from app.utils.pdf import build_pdf

router = APIRouter(prefix="/donations", tags=["Donations"])
receipts_router = APIRouter(prefix="/receipts", tags=["Receipts"])


@router.post("", response_model=DonationRead, status_code=status.HTTP_201_CREATED)
def create_donation(payload: DonationCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Record a pending donation. The campaign total changes only when it is confirmed."""
    return donation_service.create_donation(db, actor, payload)


@router.get("", response_model=dict)
def list_donations(
    listing: Listing = Depends(),
    status: str | None = None,
    campaign_id: int | None = None,
    donor_id: int | None = None,
    method: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = donation_service.list_donations(
        db,
        actor,
        page=listing.page,
        page_size=listing.page_size,
        sort_by=listing.sort_by,
        sort_dir=listing.sort_dir,
        status=status,
        campaign_id=campaign_id,
        donor_id=donor_id,
        method=method,
        date_from=date_from,
        date_to=date_to,
    )
    return as_page([DonationRead.model_validate(row) for row in rows], total, listing)


@router.get("/{donation_id}", response_model=DonationRead)
def get_donation(donation_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return donation_service.get_donation(db, actor, donation_id)


@router.patch("/{donation_id}", response_model=DonationRead)
def update_donation(
    donation_id: int,
    payload: DonationUpdate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return donation_service.update_donation(db, actor, donation_id, payload)


@router.post("/{donation_id}/status", response_model=DonationRead)
def change_status(
    donation_id: int,
    payload: DonationStatusChange,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm, cancel, reverse, or refund. Confirmation and reversal update the campaign total together."""
    return donation_service.change_status(db, actor, donation_id, payload.status)


@router.post("/{donation_id}/receipt", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
def issue_receipt(donation_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Issue one receipt for a confirmed donation. A second receipt is refused."""
    return donation_service.issue_receipt(db, actor, donation_id)


@receipts_router.get("/{receipt_id}", response_model=ReceiptRead)
def get_receipt(receipt_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return donation_service.get_receipt(db, actor, receipt_id)


@receipts_router.get("/{receipt_id}/pdf")
def receipt_pdf(receipt_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Optional PDF copy of a receipt. Void receipts stay downloadable and say so."""
    receipt = donation_service.get_receipt(db, actor, receipt_id)
    donation = receipt.donation
    donor = db.get(Donor, donation.donor_id)
    campaign = db.get(Campaign, donation.campaign_id)
    lines = [
        "NGO Donation Receipt",
        f"Receipt number: {receipt.receipt_number}",
        f"Status: {receipt.status}",
        f"Donor: {donor.name if donor else ''}",
        f"Campaign: {campaign.title if campaign else ''}",
        f"Amount: {donation.amount}",
        f"Date: {donation.donation_date.isoformat()}",
        f"Method: {donation.method}",
        f"Reference: {donation.reference_number}",
        f"Issued: {receipt.issued_at.isoformat()}",
    ]
    if receipt.status == "void":
        lines.append(f"Void reason: {receipt.void_reason or ''}")
    content = build_pdf(lines)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{receipt.receipt_number}.pdf"'},
    )
