import uuid

from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import safe_decode
from app.db.session import get_db
from app.domain.errors import AppError
from app.models.identity import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """The token says who you claim to be. The user row says whether you still may."""
    try:
        payload = safe_decode(token)
    except ValueError as exc:
        raise AppError("Invalid or expired token", 401, "invalid_token") from exc
    if payload.get("type") != "access":
        raise AppError("Access token required", 401, "invalid_token")
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError("Invalid or expired token", 401, "invalid_token") from exc
    user = db.get(User, user_id)
    if user is None:
        raise AppError("Invalid or expired token", 401, "invalid_token")
    if not user.is_active:
        raise AppError("This account is deactivated", 403, "account_inactive")
    return user


class Listing:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        sort_by: str = Query("created_at"),
        sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    ):
        self.page = page
        self.page_size = page_size
        self.sort_by = sort_by
        self.sort_dir = sort_dir


def as_page(items, total: int, listing: Listing) -> dict:
    return {"items": items, "total": total, "page": listing.page, "page_size": listing.page_size}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
