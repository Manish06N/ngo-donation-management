from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.domain.enums import CampaignCategory, CampaignStatus, DonationMethod, DonorStatus, DonorType
from app.schemas.common import APIModel, normalize_email


class DonorContactRead(APIModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    role_label: str
    is_primary: bool


class DonorCreate(APIModel):
    donor_type: DonorType
    name: str = Field(min_length=2, max_length=150)
    organization_name: str | None = Field(default=None, max_length=200)
    email: str
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    notes: str | None = None
    user_id: int | None = None
    contact_name: str | None = None
    contact_phone: str | None = None

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class DonorUpdate(APIModel):
    donor_type: DonorType | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    organization_name: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    status: DonorStatus | None = None
    notes: str | None = None


class DonorRead(APIModel):
    id: int
    user_id: int | None
    donor_type: str
    name: str
    organization_name: str | None
    email: str
    phone: str | None
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    status: str
    notes: str | None
    created_at: datetime
    contacts: list[DonorContactRead] = []
    donation_count: int = 0
    total_donated: Decimal = Decimal("0.00")


class CampaignCreate(APIModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=3)
    goal_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    budget_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    start_date: date
    end_date: date
    category: CampaignCategory
    manager_id: int


class CampaignUpdate(APIModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    description: str | None = None
    goal_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    budget_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    start_date: date | None = None
    end_date: date | None = None
    category: CampaignCategory | None = None
    manager_id: int | None = None


class CampaignRead(APIModel):
    id: int
    code: str
    title: str
    description: str
    goal_amount: Decimal
    raised_amount: Decimal
    budget_amount: Decimal
    start_date: date
    end_date: date
    category: str
    status: str
    manager_id: int
    created_at: datetime
    achievement_percent: Decimal | None = None


class CampaignStatusChange(APIModel):
    status: CampaignStatus


class DonationCreate(APIModel):
    donor_id: int
    campaign_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    donation_date: date
    method: DonationMethod
    reference_number: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9\-_/.]*$")
    notes: str | None = None


class DonationUpdate(APIModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    donation_date: date | None = None
    method: DonationMethod | None = None
    notes: str | None = None


class DonationStatusChange(APIModel):
    status: str = Field(pattern="^(confirmed|cancelled|reversed|refunded)$")


class DonationRead(APIModel):
    id: int
    donor_id: int
    campaign_id: int
    amount: Decimal
    donation_date: date
    method: str
    reference_number: str
    status: str
    notes: str | None
    recorded_by: int | None
    created_at: datetime


class ReceiptRead(APIModel):
    id: int
    donation_id: int
    receipt_number: str
    status: str
    issued_at: datetime
    voided_at: datetime | None
    void_reason: str | None
    issued_by: int | None
