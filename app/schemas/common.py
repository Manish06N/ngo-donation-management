from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


def normalize_email(value: str) -> str:
    cleaned = value.strip().lower()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@") or " " in cleaned:
        raise ValueError("value is not a valid email address")
    return cleaned


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def check_password(value: str) -> str:
    if not 8 <= len(value) <= 72:
        raise ValueError("Password must be 8 to 72 characters")
    if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
        raise ValueError("Password must include a letter and a number")
    return value


class Message(APIModel):
    message: str
    reset_token: str | None = None


class StatusChange(APIModel):
    status: str


class CommentDecision(APIModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    comments: str | None = None
