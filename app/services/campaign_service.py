from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import CampaignStatus, Role
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.domain.rules import ensure_date_order, money, utilization_percent
from app.domain.transitions import CAMPAIGN_TRANSITIONS, ensure_transition
from app.models.fundraising import Campaign
from app.models.identity import User
from app.repositories.common import apply_sort, get_or_404, next_code, paginate
from app.schemas.fundraising import CampaignCreate, CampaignRead, CampaignUpdate
from app.services.access import STAFF_ROLES, audit, authorize, touch


def _value(item):
    return item.value if hasattr(item, "value") else item


def present(row: Campaign) -> CampaignRead:
    data = CampaignRead.model_validate(row)
    return data.model_copy(
        update={"achievement_percent": utilization_percent(row.goal_amount, row.raised_amount)}
    )


def _manager(db: Session, user_id: int) -> User:
    user = get_or_404(db, User, user_id, "Campaign manager")
    if not user.is_active or user.role not in STAFF_ROLES:
        raise AppError("Campaign manager must be an active staff user", 422, "invalid_manager")
    return user


def create_campaign(db: Session, actor: User, payload: CampaignCreate) -> Campaign:
    authorize(actor, Permission.WRITE_CAMPAIGNS)
    ensure_date_order(payload.start_date, payload.end_date)
    _manager(db, payload.manager_id)
    campaign = Campaign(
        code=next_code(db, "campaign", "CAM"),
        title=payload.title,
        description=payload.description,
        goal_amount=money(payload.goal_amount),
        raised_amount=money(0),
        budget_amount=money(payload.budget_amount),
        start_date=payload.start_date,
        end_date=payload.end_date,
        category=_value(payload.category),
        status=CampaignStatus.DRAFT.value,
        manager_id=payload.manager_id,
        created_by=actor.id,
    )
    db.add(campaign)
    db.flush()
    audit(db, actor.id, "campaign.created", "campaign", campaign.id, {"code": campaign.code, "title": campaign.title})
    return campaign


def update_campaign(db: Session, actor: User, campaign_id: int, payload: CampaignUpdate) -> Campaign:
    authorize(actor, Permission.WRITE_CAMPAIGNS)
    campaign = get_or_404(db, Campaign, campaign_id, "Campaign")
    if campaign.status in {CampaignStatus.COMPLETED.value, CampaignStatus.CANCELLED.value}:
        raise AppError("Closed campaigns cannot be edited", 409, "campaign_closed")
    changes = payload.model_dump(exclude_unset=True)
    if "category" in changes and changes["category"] is not None:
        changes["category"] = _value(changes["category"])
    if "goal_amount" in changes and changes["goal_amount"] is not None:
        changes["goal_amount"] = money(changes["goal_amount"])
        if changes["goal_amount"] < money(campaign.raised_amount):
            raise AppError("Goal cannot be lower than the amount already raised", 409, "goal_below_raised")
    if "budget_amount" in changes and changes["budget_amount"] is not None:
        changes["budget_amount"] = money(changes["budget_amount"])
    if "manager_id" in changes and changes["manager_id"] is not None:
        _manager(db, changes["manager_id"])
    start = changes.get("start_date", campaign.start_date)
    end = changes.get("end_date", campaign.end_date)
    ensure_date_order(start, end)
    for key, value in changes.items():
        setattr(campaign, key, value)
    touch(campaign)
    audit(db, actor.id, "campaign.updated", "campaign", campaign.id, {"fields": list(changes)})
    db.flush()
    return campaign


def change_status(db: Session, actor: User, campaign_id: int, new_status: str) -> Campaign:
    authorize(actor, Permission.WRITE_CAMPAIGNS)
    campaign = get_or_404(db, Campaign, campaign_id, "Campaign")
    new_status = _value(new_status)
    ensure_transition(campaign.status, new_status, CAMPAIGN_TRANSITIONS, "Campaign")
    if new_status == CampaignStatus.ACTIVE.value and campaign.end_date < date.today():
        raise AppError("A campaign whose end date has passed cannot be activated", 409, "campaign_expired")
    previous = campaign.status
    campaign.status = new_status
    touch(campaign)
    audit(
        db,
        actor.id,
        "campaign.status_changed",
        "campaign",
        campaign.id,
        {"from": previous, "to": new_status},
    )
    db.flush()
    return campaign


def get_campaign(db: Session, actor: User, campaign_id: int) -> Campaign:
    authorize(actor, Permission.READ_CAMPAIGNS)
    campaign = get_or_404(db, Campaign, campaign_id, "Campaign")
    if actor.role == Role.DONOR.value and campaign.status in {
        CampaignStatus.DRAFT.value,
        CampaignStatus.CANCELLED.value,
    }:
        raise AppError("Campaign not found", 404, "not_found")
    return campaign


def list_campaigns(db, actor, *, page, page_size, sort_by, sort_dir, q, status, category, manager_id):
    authorize(actor, Permission.READ_CAMPAIGNS)
    stmt = select(Campaign)
    if actor.role == Role.DONOR.value:
        stmt = stmt.where(
            Campaign.status.in_(
                [CampaignStatus.ACTIVE.value, CampaignStatus.PAUSED.value, CampaignStatus.COMPLETED.value]
            )
        )
    if q:
        stmt = stmt.where(Campaign.title.ilike(f"%{q}%") | Campaign.code.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Campaign.status == status)
    if category:
        stmt = stmt.where(Campaign.category == category)
    if manager_id:
        stmt = stmt.where(Campaign.manager_id == manager_id)
    stmt = apply_sort(
        stmt,
        sort_by,
        sort_dir,
        {
            "id": Campaign.id,
            "title": Campaign.title,
            "start_date": Campaign.start_date,
            "end_date": Campaign.end_date,
            "goal_amount": Campaign.goal_amount,
            "raised_amount": Campaign.raised_amount,
            "created_at": Campaign.created_at,
        },
    )
    rows, total = paginate(db, stmt, page, page_size)
    return [present(row) for row in rows], total
