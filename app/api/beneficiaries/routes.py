from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.identity import User
from app.schemas.insights import AssistanceCreate, AssistanceRead, BeneficiaryCreate, BeneficiaryRead, BeneficiaryUpdate
from app.services import beneficiary_service

router = APIRouter(prefix="/beneficiaries", tags=["Beneficiaries"])


@router.post("", response_model=BeneficiaryRead, status_code=status.HTTP_201_CREATED)
def create_beneficiary(payload: BeneficiaryCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Register a beneficiary. Contact and address are hidden from roles without sensitive access."""
    return beneficiary_service.present(actor, beneficiary_service.create_beneficiary(db, actor, payload))


@router.get("", response_model=dict)
def list_beneficiaries(
    listing: Listing = Depends(),
    q: str | None = None,
    category: str | None = None,
    project_id: int | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = beneficiary_service.list_beneficiaries(
        db, actor, page=listing.page, page_size=listing.page_size, sort_by=listing.sort_by, sort_dir=listing.sort_dir, q=q, category=category, project_id=project_id
    )
    return as_page(rows, total, listing)


@router.get("/{beneficiary_id}", response_model=BeneficiaryRead)
def get_beneficiary(beneficiary_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return beneficiary_service.present(actor, beneficiary_service.get_beneficiary(db, actor, beneficiary_id))


@router.patch("/{beneficiary_id}", response_model=BeneficiaryRead)
def update_beneficiary(
    beneficiary_id: int,
    payload: BeneficiaryUpdate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return beneficiary_service.present(actor, beneficiary_service.update_beneficiary(db, actor, beneficiary_id, payload))


@router.post("/{beneficiary_id}/assistance", response_model=AssistanceRead, status_code=status.HTTP_201_CREATED)
def record_assistance(
    beneficiary_id: int,
    payload: AssistanceCreate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record help given. If a resource is named, stock is allocated in the same transaction."""
    return beneficiary_service.record_assistance(db, actor, beneficiary_id, payload)


@router.get("/{beneficiary_id}/assistance", response_model=list[AssistanceRead])
def list_assistance(beneficiary_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return beneficiary_service.list_assistance(db, actor, beneficiary_id)
