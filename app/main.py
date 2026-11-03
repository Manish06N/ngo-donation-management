"""The front door.

A request comes in here, passes middleware, then a route. The route calls a service.
The service decides. The database session commits only if the service did not raise.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.api.deps import RequestContextMiddleware, get_db
from app.api.router import router as api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.base import Base
from app.db.seed import seed
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ngo")

OPENAPI_TAGS = [
    {"name": "Authentication", "description": "Registration, login, refresh tokens, password reset, and account activation."},
    {"name": "Donors", "description": "Donor profiles, contacts, and donation history."},
    {"name": "Campaigns", "description": "Fundraising campaigns and their status lifecycle."},
    {"name": "Donations", "description": "Donations, confirmation, and campaign totals."},
    {"name": "Receipts", "description": "One receipt per confirmed donation, including a PDF copy."},
    {"name": "Volunteers", "description": "Volunteer profiles, skills, and availability."},
    {"name": "Volunteer assignments", "description": "Project assignments, conflicts, and attendance."},
    {"name": "Projects", "description": "Community projects and the approval workflow."},
    {"name": "Milestones", "description": "Milestones and the tasks that complete them."},
    {"name": "Tasks", "description": "Task status, priority, progress, and overdue work."},
    {"name": "Expenses", "description": "Expense submission and finance approval."},
    {"name": "Budgets", "description": "Remaining budget and overrun checks."},
    {"name": "Resources", "description": "Inventory, stock movements, and low-stock alerts."},
    {"name": "Beneficiaries", "description": "Beneficiary records and assistance. Sensitive fields are role-gated."},
    {"name": "Dashboard", "description": "Totals calculated from database rows."},
    {"name": "Notifications", "description": "In-app notices with a read state."},
    {"name": "Reports", "description": "Filtered reports and CSV export."},
    {"name": "Audit", "description": "Who changed what, and when."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.secret_key in {"change-me", "dev-only-change-me"} and not settings.debug:
        raise RuntimeError("Set a unique SECRET_KEY when DEBUG is false")
    if settings.auto_seed:
        db = SessionLocal()
        try:
            if settings.debug:
                Base.metadata.create_all(bind=db.get_bind())
            seed(db)
            db.commit()
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        summary="Donors, campaigns, volunteers, projects, stock, and impact for an NGO.",
        description=(
            "Staff, volunteers, and donors share one API. What you can do depends on your role. "
            "Money and stock changes run in one database transaction. "
            "Status changes follow a fixed map: a closed campaign cannot take a donation, "
            "and a project cannot go live before it is approved."
        ),
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=origins != ["*"] and "*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", tags=["Dashboard"])
    def root():
        return {"name": settings.app_name, "docs": "/docs", "health": "/health"}

    @app.get("/health", tags=["Dashboard"])
    def health(db: Session = Depends(get_db)):
        db.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app


app = create_app()
