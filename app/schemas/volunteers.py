from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.domain.enums import AssignmentStatus, AttendanceStatus, VolunteerStatus
from app.schemas.common import APIModel, normalize_email


class VolunteerCreate(APIModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: str
    phone: str | None = None
    address: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: str | None = None
    availability: str | None = None
    status: VolunteerStatus = VolunteerStatus.APPLIED
    emergency_contact_name: str = Field(min_length=2, max_length=150)
    emergency_contact_phone: str = Field(min_length=7, max_length=30)
    user_id: int | None = None

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class VolunteerUpdate(APIModel):
    full_name: str | None = None
    phone: str | None = None
    address: str | None = None
    skills: list[str] | None = None
    experience: str | None = None
    availability: str | None = None
    status: VolunteerStatus | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class VolunteerRead(APIModel):
    id: int
    user_id: int | None
    full_name: str
    email: str
    phone: str | None
    address: str | None
    skills: list[str]
    experience: str | None
    availability: str | None
    status: str
    emergency_contact_name: str
    emergency_contact_phone: str
    created_at: datetime


class AssignmentCreate(APIModel):
    volunteer_id: int
    project_id: int
    responsibility: str = Field(min_length=2, max_length=180)
    start_date: date
    end_date: date | None = None
    notes: str | None = None


class AssignmentUpdate(APIModel):
    responsibility: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: AssignmentStatus | None = None
    notes: str | None = None


class AssignmentRead(APIModel):
    id: int
    volunteer_id: int
    project_id: int
    responsibility: str
    start_date: date
    end_date: date | None
    status: str
    hours_completed: Decimal
    notes: str | None
    assigned_by: int | None
    created_at: datetime


class AttendanceCreate(APIModel):
    attended_on: date
    status: AttendanceStatus
    hours: Decimal = Field(ge=0, le=24, max_digits=5, decimal_places=2)
    notes: str | None = None


class AttendanceRead(APIModel):
    id: int
    assignment_id: int
    attended_on: date
    status: str
    hours: Decimal
    notes: str | None
    recorded_by: int | None
    created_at: datetime
