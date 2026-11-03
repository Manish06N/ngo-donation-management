from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.identity import User
from app.schemas.fundraising import CampaignCreate, CampaignRead, CampaignStatusChange, CampaignUpdate
from app.services import campaign_service

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a draft campaign. It cannot take donations until it is activated."""
    return campaign_service.present(campaign_service.create_campaign(db, actor, payload))


@router.get("", response_model=dict)
def list_campaigns(
    listing: Listing = Depends(),
    q: str | None = None,
    status: str | None = None,
    category: str | None = None,
    manager_id: int | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = campaign_service.list_campaigns(
        db,
        actor,
        page=listing.page,
        page_size=listing.page_size,
        sort_by=listing.sort_by,
        sort_dir=listing.sort_dir,
        q=q,
        status=status,
        category=category,
        manager_id=manager_id,
    )
    return as_page(rows, total, listing)


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return campaign_service.present(campaign_service.get_campaign(db, actor, campaign_id))


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return campaign_service.present(campaign_service.update_campaign(db, actor, campaign_id, payload))


@router.post("/{campaign_id}/status", response_model=CampaignRead)
def change_status(
    campaign_id: int,
    payload: CampaignStatusChange,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move a campaign between draft, active, paused, completed, and cancelled."""
    return campaign_service.present(campaign_service.change_status(db, actor, campaign_id, payload.status))
