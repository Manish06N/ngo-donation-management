"""Import every model so Base.metadata knows the full schema."""

from app.models.beneficiaries import Beneficiary, BeneficiaryAssistance, beneficiary_projects
from app.models.engagement import AuditLog, Notification
from app.models.finance import Expense, ExpenseAction
from app.models.fundraising import Campaign, Donation, DonationReceipt, Donor, DonorContact
from app.models.identity import PasswordResetToken, RefreshToken, Sequence, User
from app.models.inventory import Resource, ResourceTransaction
from app.models.projects import ImpactUpdate, Milestone, Project, ProjectApproval, Task
from app.models.volunteering import Attendance, Volunteer, VolunteerAssignment

__all__ = [
    "AuditLog",
    "Attendance",
    "Beneficiary",
    "BeneficiaryAssistance",
    "Campaign",
    "Donation",
    "DonationReceipt",
    "Donor",
    "DonorContact",
    "Expense",
    "ExpenseAction",
    "ImpactUpdate",
    "Milestone",
    "Notification",
    "PasswordResetToken",
    "Project",
    "ProjectApproval",
    "RefreshToken",
    "Resource",
    "ResourceTransaction",
    "Sequence",
    "Task",
    "User",
    "Volunteer",
    "VolunteerAssignment",
    "beneficiary_projects",
]
