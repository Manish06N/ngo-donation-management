from fastapi import APIRouter

from app.api.auth.routes import router as auth_router
from app.api.auth.routes import users_router
from app.api.beneficiaries.routes import router as beneficiaries_router
from app.api.campaigns.routes import router as campaigns_router
from app.api.donations.routes import receipts_router
from app.api.donations.routes import router as donations_router
from app.api.donors.routes import router as donors_router
from app.api.expenses.routes import budgets as budgets_router
from app.api.expenses.routes import router as expenses_router
from app.api.projects.routes import milestones as milestones_router
from app.api.projects.routes import router as projects_router
from app.api.projects.routes import tasks as tasks_router
from app.api.reports.routes import audit as audit_router
from app.api.reports.routes import dashboard_router
from app.api.reports.routes import notifications as notifications_router
from app.api.reports.routes import router as reports_router
from app.api.resources.routes import router as resources_router
from app.api.volunteers.routes import assignments as assignments_router
from app.api.volunteers.routes import router as volunteers_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(donors_router)
router.include_router(campaigns_router)
router.include_router(donations_router)
router.include_router(receipts_router)
router.include_router(volunteers_router)
router.include_router(assignments_router)
router.include_router(projects_router)
router.include_router(milestones_router)
router.include_router(tasks_router)
router.include_router(expenses_router)
router.include_router(budgets_router)
router.include_router(resources_router)
router.include_router(beneficiaries_router)
router.include_router(dashboard_router)
router.include_router(notifications_router)
router.include_router(reports_router)
router.include_router(audit_router)
