"""Accounts, sessions, and password reset.

Self-registration can only create a donor or a volunteer. Staff accounts are
created by someone who already has manage-users permission.
"""

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    safe_decode,
    verify_password,
)
from app.domain.enums import DonorStatus, DonorType, Role, VolunteerStatus
from app.domain.errors import AppError
from app.domain.permissions import Permission
from app.models.fundraising import Donor, DonorContact
from app.models.identity import PasswordResetToken, RefreshToken, User
from app.models.volunteering import Volunteer
from app.repositories.common import get_or_404, paginate
from app.repositories.users import by_email
from app.schemas.auth import RegisterRequest, UserCreate
from app.services.access import audit, authorize
from app.utils.time import utcnow


def _value(item) -> str:
    return item.value if hasattr(item, "value") else item


def _tokens(db: Session, user: User) -> tuple[str, str]:
    access = create_access_token(user.id, user.role)
    refresh, expires = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(refresh), expires_at=expires))
    db.flush()
    return access, refresh


def _revoke_all(db: Session, user_id: int) -> None:
    rows = db.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    ).all()
    now = utcnow()
    for row in rows:
        row.revoked_at = now


def _donor_profile(db: Session, user: User, donor_type: str, organization_name: str | None) -> None:
    if donor_type == DonorType.ORGANIZATION.value and not organization_name:
        raise AppError("Organization donors need an organization name", 422, "organization_name_required")
    if db.scalar(select(Donor.id).where(Donor.email == user.email)):
        raise AppError("A donor with this email already exists", 409, "email_taken")
    donor = Donor(
        user_id=user.id,
        donor_type=donor_type,
        name=user.full_name,
        organization_name=organization_name,
        email=user.email,
        phone=user.phone,
        status=DonorStatus.ACTIVE.value,
        created_by=user.id,
    )
    db.add(donor)
    db.flush()
    db.add(
        DonorContact(
            donor_id=donor.id,
            name=user.full_name,
            email=user.email,
            phone=user.phone,
            role_label="primary",
            is_primary=True,
        )
    )


def _volunteer_profile(db: Session, user: User, emergency_name: str | None, emergency_phone: str | None, status: str) -> None:
    if not emergency_name or not emergency_phone:
        raise AppError("Volunteers must provide an emergency contact", 422, "emergency_contact_required")
    if db.scalar(select(Volunteer.id).where(Volunteer.email == user.email)):
        raise AppError("A volunteer with this email already exists", 409, "email_taken")
    db.add(
        Volunteer(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            skills=[],
            status=status,
            emergency_contact_name=emergency_name,
            emergency_contact_phone=emergency_phone,
            created_by=user.id,
        )
    )


def register(db: Session, payload: RegisterRequest) -> User:
    role = _value(payload.role)
    if by_email(db, payload.email):
        raise AppError("An account with this email already exists", 409, "email_taken")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    if role == Role.DONOR.value:
        _donor_profile(db, user, _value(payload.donor_type), payload.organization_name)
    else:
        _volunteer_profile(
            db,
            user,
            payload.emergency_contact_name,
            payload.emergency_contact_phone,
            VolunteerStatus.APPLIED.value,
        )
    audit(db, user.id, "user.registered", "user", user.id, {"role": role})
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> tuple[User, str, str]:
    user = by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AppError("Incorrect email or password", 401, "invalid_credentials")
    if not user.is_active:
        raise AppError("This account is deactivated", 403, "account_inactive")
    access, refresh = _tokens(db, user)
    return user, access, refresh


def refresh_session(db: Session, raw_token: str) -> tuple[User, str, str]:
    try:
        payload = safe_decode(raw_token)
    except ValueError as exc:
        raise AppError("Refresh token is invalid or expired", 401, "invalid_token") from exc
    if payload.get("type") != "refresh":
        raise AppError("Refresh token is invalid or expired", 401, "invalid_token")
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if row is None or row.revoked_at is not None or row.expires_at < utcnow():
        raise AppError("Refresh token is invalid or expired", 401, "invalid_token")
    user = db.get(User, row.user_id)
    if user is None or str(user.id) != str(payload.get("sub")) or not user.is_active:
        raise AppError("Refresh token is invalid or expired", 401, "invalid_token")
    row.revoked_at = utcnow()
    access, refresh = _tokens(db, user)
    return user, access, refresh


def logout(db: Session, raw_token: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = utcnow()
        db.flush()


def request_password_reset(db: Session, email: str) -> str | None:
    user = by_email(db, email)
    if user is None or not user.is_active:
        return None
    raw = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    db.flush()
    return raw


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token)))
    if row is None or row.used_at is not None or row.expires_at < utcnow():
        raise AppError("Reset token is invalid or expired", 400, "invalid_token")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AppError("Reset token is invalid or expired", 400, "invalid_token")
    user.hashed_password = hash_password(new_password)
    row.used_at = utcnow()
    _revoke_all(db, user.id)
    audit(db, user.id, "user.password_reset", "user", user.id, {})
    db.flush()


def change_password(db: Session, actor: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, actor.hashed_password):
        raise AppError("Current password is incorrect", 400, "invalid_credentials")
    actor.hashed_password = hash_password(new_password)
    _revoke_all(db, actor.id)
    audit(db, actor.id, "user.password_changed", "user", actor.id, {})
    db.flush()


def update_me(db: Session, actor: User, changes: dict) -> User:
    for field in ("full_name", "phone"):
        if field in changes and changes[field] is not None:
            setattr(actor, field, changes[field])
    db.flush()
    return actor


def create_user(db: Session, actor: User, payload: UserCreate) -> User:
    authorize(actor, Permission.MANAGE_USERS)
    if by_email(db, payload.email):
        raise AppError("An account with this email already exists", 409, "email_taken")
    role = _value(payload.role)
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    if role == Role.DONOR.value:
        _donor_profile(db, user, DonorType.INDIVIDUAL.value, None)
    elif role == Role.VOLUNTEER.value:
        _volunteer_profile(
            db,
            user,
            payload.emergency_contact_name,
            payload.emergency_contact_phone,
            VolunteerStatus.APPLIED.value,
        )
    audit(db, actor.id, "user.created", "user", user.id, {"role": role, "email": user.email})
    db.flush()
    return user


def set_active(db: Session, actor: User, user_id: int, is_active: bool) -> User:
    authorize(actor, Permission.MANAGE_USERS)
    user = get_or_404(db, User, user_id, "User")
    if user.id == actor.id and not is_active:
        raise AppError("You cannot deactivate your own account", 409, "self_deactivation")
    user.is_active = is_active
    if not is_active:
        _revoke_all(db, user.id)
    audit(
        db,
        actor.id,
        "user.activated" if is_active else "user.deactivated",
        "user",
        user.id,
        {"is_active": is_active},
    )
    db.flush()
    return user


def list_users(db: Session, actor: User, page: int, page_size: int, role: str | None):
    authorize(actor, Permission.MANAGE_USERS)
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.id.desc())
    return paginate(db, stmt, page, page_size)
