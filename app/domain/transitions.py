"""Allowed status changes.

If a change is not in the map, it is refused. Callers cannot invent a shortcut
by writing the column directly.
"""

from app.domain.enums import (
    CampaignStatus,
    DonationStatus,
    ExpenseStatus,
    ProjectStatus,
)
from app.domain.errors import AppError

CAMPAIGN_TRANSITIONS: dict[str, set[str]] = {
    CampaignStatus.DRAFT.value: {CampaignStatus.ACTIVE.value, CampaignStatus.CANCELLED.value},
    CampaignStatus.ACTIVE.value: {
        CampaignStatus.PAUSED.value,
        CampaignStatus.COMPLETED.value,
        CampaignStatus.CANCELLED.value,
    },
    CampaignStatus.PAUSED.value: {
        CampaignStatus.ACTIVE.value,
        CampaignStatus.COMPLETED.value,
        CampaignStatus.CANCELLED.value,
    },
    CampaignStatus.COMPLETED.value: set(),
    CampaignStatus.CANCELLED.value: set(),
}

DONATION_TRANSITIONS: dict[str, set[str]] = {
    DonationStatus.PENDING.value: {DonationStatus.CONFIRMED.value, DonationStatus.CANCELLED.value},
    DonationStatus.CONFIRMED.value: {DonationStatus.REVERSED.value, DonationStatus.REFUNDED.value},
    DonationStatus.CANCELLED.value: set(),
    DonationStatus.REVERSED.value: set(),
    DonationStatus.REFUNDED.value: set(),
}

# Planning becomes Approved only through the approval decision, not this map.
PROJECT_TRANSITIONS: dict[str, set[str]] = {
    ProjectStatus.PLANNING.value: {ProjectStatus.CANCELLED.value},
    ProjectStatus.APPROVED.value: {ProjectStatus.ACTIVE.value, ProjectStatus.CANCELLED.value},
    ProjectStatus.ACTIVE.value: {
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.COMPLETED.value,
        ProjectStatus.CANCELLED.value,
    },
    ProjectStatus.ON_HOLD.value: {ProjectStatus.ACTIVE.value, ProjectStatus.CANCELLED.value},
    ProjectStatus.COMPLETED.value: set(),
    ProjectStatus.CANCELLED.value: set(),
}

EXPENSE_TRANSITIONS: dict[str, set[str]] = {
    ExpenseStatus.SUBMITTED.value: {ExpenseStatus.APPROVED.value, ExpenseStatus.REJECTED.value},
    ExpenseStatus.APPROVED.value: {ExpenseStatus.REIMBURSED.value},
    ExpenseStatus.REJECTED.value: set(),
    ExpenseStatus.REIMBURSED.value: set(),
}

ACCEPTING_DONATIONS = {CampaignStatus.ACTIVE.value}
CONFIRMED_MONEY = {DonationStatus.CONFIRMED.value}
MONEY_LEAVING = {DonationStatus.REVERSED.value, DonationStatus.REFUNDED.value}
SPENT_EXPENSE = {ExpenseStatus.APPROVED.value, ExpenseStatus.REIMBURSED.value}
OPEN_ASSIGNMENT = {"assigned", "active"}


def ensure_transition(current: str, new: str, graph: dict[str, set[str]], label: str) -> None:
    if new not in graph.get(current, set()):
        raise AppError(
            f"{label} cannot move from '{current}' to '{new}'",
            409,
            "invalid_transition",
        )
