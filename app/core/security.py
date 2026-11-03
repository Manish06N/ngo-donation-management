"""Passwords are stored as hashes. Tokens are signed so we can trust them without a lookup.

The access token is not stored. The refresh token is stored only as a SHA-256 hash,
so a database leak does not hand out live sessions.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=settings.password_hash_rounds))
    return hashed.decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": expire,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, expire.replace(tzinfo=None)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def safe_decode(token: str) -> dict:
    try:
        return decode_token(token)
    except InvalidTokenError as exc:
        raise ValueError("invalid token") from exc
