from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.identity import User
from app.schemas.fundraising import DonorCreate, DonorRead, DonorUpdate
from app.services import donor_service

router = APIRouter(prefix="/donors", tags=["Donors"])


@router.post("", response_model=DonorRead, status_code=status.HTTP_201_CREATED)
def create_donor(payload: DonorCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a donor profile. Organization donors must include an organization name."""
    donor = donor_service.create_donor(db, actor, payload)
    return donor_service.present(db, donor)


@router.get("", response_model=dict)
def list_donors(
    listing: Listing = Depends(),
    q: str | None = None,
    donor_type: str | None = None,
    status: str | None = None,
    city: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search donors by name, email, phone, type, status, or city. Donors only see themselves."""
    rows, total = donor_service.list_donors(
        db,
        actor,
        page=listing.page,
        page_size=listing.page_size,
        sort_by=listing.sort_by,
        sort_dir=listing.sort_dir,
        q=q,
        donor_type=donor_type,
        status=status,
        city=city,
    )
    return as_page(rows, total, listing)


@router.get("/me", response_model=DonorRead)
def my_donor(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.access import donor_for_user
    from app.domain.errors import AppError

    donor = donor_for_user(db, actor)
    if donor is None:
        raise AppError("Donor profile not found", 404, "not_found")
    return donor_service.present(db, donor_service.get_donor(db, actor, donor.id))


@router.get("/{donor_id}", response_model=DonorRead)
def get_donor(donor_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return donor_service.present(db, donor_service.get_donor(db, actor, donor_id))


@router.patch("/{donor_id}", response_model=DonorRead)
def update_donor(donor_id: int, payload: DonorUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return donor_service.present(db, donor_service.update_donor(db, actor, donor_id, payload))


@router.get("/{donor_id}/donations", response_model=dict)
def donor_donations(
    donor_id: int,
    listing: Listing = Depends(),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import donation_service

    rows, total = donation_service.list_donations(
        db,
        actor,
        page=listing.page,
        page_size=listing.page_size,
        sort_by=listing.sort_by,
        sort_dir=listing.sort_dir,
        status=None,
        campaign_id=None,
        donor_id=donor_id,
        method=None,
        date_from=None,
        date_to=None,
    )
    from app.schemas.fundraising import DonationRead

    return as_page([DonationRead.model_validate(row) for row in rows], total, listing)


@router.get("/{donor_id}/receipts")
def donor_receipts(donor_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.schemas.fundraising import ReceiptRead
    from app.services import donation_service

    rows = donation_service.list_donor_receipts(db, actor, donor_id)
    return [ReceiptRead.model_validate(row) for row in rows]
