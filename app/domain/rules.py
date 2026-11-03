"""Pure business rules. These functions do not touch the database, so unit tests
can pin them down without booting FastAPI.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.domain.errors import AppError

TWOPLACES = Decimal("0.01")


def money(value) -> Decimal:
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value))
    return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def remaining_budget(budget, spent) -> Decimal:
    return money(money(budget) - money(spent))


def is_overrun(budget, spent) -> bool:
    return money(spent) > money(budget)


def utilization_percent(budget, spent) -> Decimal | None:
    budget = money(budget)
    spent = money(spent)
    if budget <= 0:
        return None
    return money(spent / budget * Decimal("100"))


def ensure_date_order(start: date | None, end: date | None, label: str = "End date") -> None:
    if start is not None and end is not None and end < start:
        raise AppError(f"{label} cannot be before the start date", 422, "invalid_dates")


def ranges_overlap(start_a: date, end_a: date | None, start_b: date, end_b: date | None) -> bool:
    """Open-ended assignments (no end date) run until the far end of the calendar."""
    end_a = end_a or date.max
    end_b = end_b or date.max
    return start_a <= end_b and start_b <= end_a


def normalize_reference(value: str) -> str:
    cleaned = value.strip().upper()
    if len(cleaned) < 4:
        raise AppError("Donation reference must be at least 4 characters", 422, "invalid_reference")
    return cleaned


def apply_donation_total(raised, amount, leaving: bool):
    """Return the new campaign total after a confirmation or a reversal/refund."""
    raised = money(raised)
    amount = money(amount)
    if amount <= 0:
        raise AppError("Donation amount must be positive", 422, "invalid_amount")
    updated = raised - amount if leaving else raised + amount
    if updated < 0:
        raise AppError("Campaign total would become negative", 409, "inconsistent_total")
    return money(updated)


def stock_after(on_hand: int, quantity: int, inbound: bool) -> int:
    if quantity <= 0:
        raise AppError("Stock quantity must be positive", 422, "invalid_quantity")
    updated = on_hand + quantity if inbound else on_hand - quantity
    if updated < 0:
        raise AppError("That movement would make stock negative", 409, "insufficient_stock")
    return updated
