from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.identity import User
from app.schemas.insights import AuditRead, DashboardRead, NotificationRead
from app.services import insight_service
from app.utils.csv_export import to_csv

router = APIRouter(prefix="/reports", tags=["Reports"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
notifications = APIRouter(prefix="/notifications", tags=["Notifications"])
audit = APIRouter(prefix="/audit-logs", tags=["Audit"])


def _export(payload: dict, filename: str, export_format: str):
    if export_format == "csv":
        return Response(
            content=to_csv(payload["headers"], payload["rows"]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return {
        "summary": payload["summary"],
        "items": payload["items"],
        "total": payload["total"],
        "page": payload["page"],
        "page_size": payload["page_size"],
    }


@dashboard_router.get("", response_model=DashboardRead)
def dashboard(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Organisation totals. Every figure is aggregated from stored rows."""
    return insight_service.dashboard(db, actor)


@notifications.get("", response_model=dict)
def list_notifications(
    listing: Listing = Depends(),
    is_read: bool | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = insight_service.list_notifications(db, actor, page=listing.page, page_size=listing.page_size, is_read=is_read)
    return as_page([NotificationRead.model_validate(row) for row in rows], total, listing)


@notifications.post("/read-all")
def read_all(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"updated": insight_service.mark_all_read(db, actor)}


@notifications.post("/scan")
def scan(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create in-app notices for overdue work, closing campaigns, low stock, and budget overruns."""
    return insight_service.scan_notifications(db, actor)


@notifications.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(notification_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return insight_service.mark_read(db, actor, notification_id)


@audit.get("", response_model=dict)
def list_audit(
    listing: Listing = Depends(),
    entity_type: str | None = None,
    action: str | None = None,
    actor_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = insight_service.list_audit(
        db,
        actor,
        page=listing.page,
        page_size=listing.page_size,
        sort_by=listing.sort_by,
        sort_dir=listing.sort_dir,
        entity_type=entity_type,
        action=action,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )
    return as_page([AuditRead.model_validate(row) for row in rows], total, listing)


def _report_args(listing: Listing):
    return {"page": listing.page, "page_size": listing.page_size, "sort_by": listing.sort_by, "sort_dir": listing.sort_dir}


@router.get("/donations")
def donations(
    listing: Listing = Depends(),
    export_format: str = Query("json", alias="format", pattern="^(json|csv)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    campaign_id: int | None = None,
    status: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = insight_service.donation_report(
        db, actor, date_from=date_from, date_to=date_to, campaign_id=campaign_id, status=status, **_report_args(listing)
    )
    return _export(payload, "donations.csv", export_format)


@router.get("/campaigns")
def campaigns(
    listing: Listing = Depends(),
    export_format: str = Query("json", alias="format", pattern="^(json|csv)$"),
    status: str | None = None,
    category: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = insight_service.campaign_report(db, actor, status=status, category=category, **_report_args(listing))
    return _export(payload, "campaigns.csv", export_format)


@router.get("/volunteers")
def volunteers(
    listing: Listing = Depends(),
    export_format: str = Query("json", alias="format", pattern="^(json|csv)$"),
    status: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = insight_service.volunteer_report(db, actor, status=status, **_report_args(listing))
    return _export(payload, "volunteers.csv", export_format)


@router.get("/projects")
def projects(
    listing: Listing = Depends(),
    export_format: str = Query("json", alias="format", pattern="^(json|csv)$"),
    status: str | None = None,
    project_id: int | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = insight_service.project_report(db, actor, status=status, project_id=project_id, **_report_args(listing))
    return _export(payload, "projects.csv", export_format)


@router.get("/expenses")
def expenses(
    listing: Listing = Depends(),
    export_format: str = Query("json", alias="format", pattern="^(json|csv)$"),
    status: str | None = None,
    project_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = insight_service.expense_report(
        db, actor, status=status, project_id=project_id, date_from=date_from, date_to=date_to, **_report_args(listing)
    )
    return _export(payload, "expenses.csv", export_format)


@router.get("/resources")
def resources(
    listing: Listing = Depends(),
    export_format: str = Query("json", alias="format", pattern="^(json|csv)$"),
    project_id: int | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = insight_service.resource_report(db, actor, project_id=project_id, **_report_args(listing))
    return _export(payload, "resources.csv", export_format)


@router.get("/beneficiaries")
def beneficiaries(
    listing: Listing = Depends(),
    export_format: str = Query("json", alias="format", pattern="^(json|csv)$"),
    project_id: int | None = None,
    category: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = insight_service.beneficiary_report(db, actor, project_id=project_id, category=category, **_report_args(listing))
    return _export(payload, "beneficiaries.csv", export_format)
