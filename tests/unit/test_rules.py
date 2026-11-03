from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import CampaignStatus, DonationStatus, ExpenseStatus, ProjectStatus
from app.domain.errors import AppError
from app.domain.rules import (
    apply_donation_total,
    is_overrun,
    money,
    ranges_overlap,
    remaining_budget,
    stock_after,
    utilization_percent,
)
from app.domain.transitions import (
    CAMPAIGN_TRANSITIONS,
    DONATION_TRANSITIONS,
    EXPENSE_TRANSITIONS,
    PROJECT_TRANSITIONS,
    ensure_transition,
)


def test_money_and_budget_math():
    assert money("10.005") == Decimal("10.01")
    assert remaining_budget("1000", "250.50") == Decimal("749.50")
    assert utilization_percent("200", "50") == Decimal("25.00")
    assert utilization_percent("0", "0") is None
    assert is_overrun("100", "100.01") is True
    assert is_overrun("100", "100") is False


def test_donation_total_moves_only_by_the_amount():
    assert apply_donation_total("0", "25.50", leaving=False) == Decimal("25.50")
    assert apply_donation_total("25.50", "10", leaving=True) == Decimal("15.50")


def test_donation_total_refuses_a_negative_result():
    try:
        apply_donation_total("5", "10", leaving=True)
    except AppError as exc:
        assert exc.code == "inconsistent_total"
    else:
        raise AssertionError("expected a refusal")


def test_stock_cannot_go_negative():
    assert stock_after(5, 2, inbound=True) == 7
    try:
        stock_after(1, 2, inbound=False)
    except AppError as exc:
        assert exc.code == "insufficient_stock"
    else:
        raise AssertionError("expected a refusal")


def test_open_ended_assignments_overlap():
    start = date(2026, 1, 1)
    assert ranges_overlap(start, None, date(2026, 6, 1), date(2026, 6, 2)) is True
    assert ranges_overlap(start, date(2026, 1, 10), date(2026, 1, 11), date(2026, 1, 12)) is False


def test_closed_statuses_have_no_way_back():
    assert CAMPAIGN_TRANSITIONS[CampaignStatus.COMPLETED.value] == set()
    assert CAMPAIGN_TRANSITIONS[CampaignStatus.CANCELLED.value] == set()
    assert DONATION_TRANSITIONS[DonationStatus.REFUNDED.value] == set()
    assert PROJECT_TRANSITIONS[ProjectStatus.PLANNING.value] == {ProjectStatus.CANCELLED.value}
    assert ExpenseStatus.APPROVED.value in EXPENSE_TRANSITIONS[ExpenseStatus.SUBMITTED.value]
    try:
        ensure_transition("completed", "active", CAMPAIGN_TRANSITIONS, "Campaign")
    except AppError as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("expected a refusal")


def test_date_window_used_by_overlap_helper():
    today = date.today()
    assert ranges_overlap(today, today + timedelta(days=3), today + timedelta(days=3), today + timedelta(days=4))
