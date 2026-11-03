from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.models.identity import User
from app.schemas.operations import BudgetRead, ExpenseCreate, ExpenseDecision, ExpenseRead, ExpenseUpdate
from app.services import expense_service

router = APIRouter(prefix="/expenses", tags=["Expenses"])
budgets = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Submit an expense. It does not reduce the remaining budget until finance approves it."""
    return expense_service.create_expense(db, actor, payload)


@router.get("", response_model=dict)
def list_expenses(
    listing: Listing = Depends(),
    status: str | None = None,
    project_id: int | None = None,
    campaign_id: int | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = expense_service.list_expenses(
        db,
        actor,
        page=listing.page,
        page_size=listing.page_size,
        sort_by=listing.sort_by,
        sort_dir=listing.sort_dir,
        status=status,
        project_id=project_id,
        campaign_id=campaign_id,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )
    return as_page([ExpenseRead.model_validate(row) for row in rows], total, listing)


@router.get("/{expense_id}", response_model=ExpenseRead)
def get_expense(expense_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return expense_service.get_expense(db, actor, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update_expense(expense_id: int, payload: ExpenseUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return expense_service.update_expense(db, actor, expense_id, payload)


@router.post("/{expense_id}/decision", response_model=ExpenseRead)
def decide_expense(expense_id: int, payload: ExpenseDecision, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Approve, reject, or reimburse. Only finance can do this, and not on their own expense."""
    return expense_service.decide_expense(db, actor, expense_id, payload.status, payload.comments)


@budgets.get("/projects/{project_id}", response_model=BudgetRead)
def project_budget(project_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return expense_service.project_budget(db, actor, project_id)


@budgets.get("/campaigns/{campaign_id}", response_model=BudgetRead)
def campaign_budget(campaign_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return expense_service.campaign_budget(db, actor, campaign_id)


@budgets.get("/utilization", response_model=list[BudgetRead])
def utilization(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remaining budget and overrun flag for every project, calculated from approved expenses."""
    return expense_service.budget_report(db, actor)
