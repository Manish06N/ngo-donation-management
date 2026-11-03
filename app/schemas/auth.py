from datetime import datetime

from pydantic import Field, field_validator

from app.domain.enums import DonorType, Role
from app.schemas.common import APIModel, check_password, normalize_email


class RegisterRequest(APIModel):
    email: str
    password: str
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    role: Role = Role.DONOR
    donor_type: DonorType = DonorType.INDIVIDUAL
    organization_name: str | None = Field(default=None, max_length=200)
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return check_password(value)

    @field_validator("role")
    @classmethod
    def public_roles(cls, value: Role) -> Role:
        if value not in {Role.DONOR, Role.VOLUNTEER}:
            raise ValueError("Public registration is limited to donor and volunteer accounts")
        return value


class LoginRequest(APIModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class RefreshRequest(APIModel):
    refresh_token: str = Field(min_length=20)


class ForgotPasswordRequest(APIModel):
    email: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class ResetPasswordRequest(APIModel):
    token: str = Field(min_length=20)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return check_password(value)


class ChangePasswordRequest(APIModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return check_password(value)


class UserCreate(APIModel):
    email: str
    password: str
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = None
    role: Role
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return check_password(value)


class UserUpdate(APIModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)


class ActivationRequest(APIModel):
    is_active: bool


class UserRead(APIModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime


class TokenPair(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
