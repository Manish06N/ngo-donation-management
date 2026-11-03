from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import Listing, as_page, get_current_user, get_db
from app.core.config import settings
from app.models.identity import User
from app.schemas.auth import (
    ActivationRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.schemas.common import Message
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/users", tags=["Authentication"])

RESET_MESSAGE = "If an account exists for that email, password reset instructions have been issued."


def _pair(user: User, access: str, refresh: str) -> TokenPair:
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Open a donor or volunteer account. Staff roles are created by an administrator."""
    return auth_service.register(db, payload)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Exchange an email and password for an access token and a rotating refresh token."""
    user, access, refresh = auth_service.authenticate(db, payload.email, payload.password)
    return _pair(user, access, refresh)


@router.post("/token", response_model=TokenPair)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Form login used by the Swagger Authorize button. The username is the email."""
    user, access, refresh = auth_service.authenticate(db, form.username, form.password)
    return _pair(user, access, refresh)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Rotate a refresh token. The previous refresh token stops working."""
    user, access, refresh_token = auth_service.refresh_session(db, payload.refresh_token)
    return _pair(user, access, refresh_token)


@router.post("/logout", response_model=Message)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Revoke one refresh token."""
    auth_service.logout(db, payload.refresh_token)
    return Message(message="Signed out")


@router.get("/me", response_model=UserRead)
def me(actor: User = Depends(get_current_user)):
    """The account attached to the current access token."""
    return actor


@router.patch("/me", response_model=UserRead)
def update_me(payload: UserUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return auth_service.update_me(db, actor, payload.model_dump(exclude_unset=True))


@router.post("/change-password", response_model=Message)
def change_password(payload: ChangePasswordRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Changing a password revokes every refresh token for the account."""
    auth_service.change_password(db, actor, payload.current_password, payload.new_password)
    return Message(message="Password updated")


@router.post("/forgot-password", response_model=Message)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Start a reset. The token is returned only when DEBUG is on, so local demos need no mail server."""
    raw = auth_service.request_password_reset(db, payload.email)
    return Message(message=RESET_MESSAGE, reset_token=raw if settings.debug else None)


@router.post("/reset-password", response_model=Message)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Set a new password from a reset token. The token can be used once."""
    auth_service.reset_password(db, payload.token, payload.new_password)
    return Message(message="Password has been reset")


@users_router.get("", response_model=dict)
def list_users(
    listing: Listing = Depends(),
    role: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = auth_service.list_users(db, actor, listing.page, listing.page_size, role)
    return as_page([UserRead.model_validate(row) for row in rows], total, listing)


@users_router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a staff, donor, or volunteer account. Public registration cannot do this."""
    return auth_service.create_user(db, actor, payload)


@users_router.patch("/{user_id}/activation", response_model=UserRead)
def activation(user_id: int, payload: ActivationRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Activate or deactivate an account. You cannot deactivate yourself."""
    return auth_service.set_active(db, actor, user_id, payload.is_active)
