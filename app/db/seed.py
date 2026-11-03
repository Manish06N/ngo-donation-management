"""Create the first super admin from the environment. Never from a hardcoded password."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.domain.enums import Role
from app.models.identity import User


def seed(db: Session) -> None:
    if not settings.admin_password:
        return
    email = settings.admin_email.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        return
    db.add(
        User(
            email=email,
            hashed_password=hash_password(settings.admin_password),
            full_name=settings.admin_name,
            role=Role.SUPER_ADMIN.value,
            is_active=True,
            is_verified=True,
        )
    )
    db.flush()
