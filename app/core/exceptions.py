import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.domain.errors import AppError

logger = logging.getLogger("ngo")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        headers = {}
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", []) if part not in {"body", "query"}]
            errors.append({"field": ".".join(loc), "message": err.get("msg", "invalid")})
        return JSONResponse(
            status_code=422,
            content={"detail": "Request validation failed", "code": "validation_error", "errors": errors},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_handler(_request: Request, exc: IntegrityError):
        text = str(getattr(exc, "orig", exc)).lower()
        detail = "That value is already in use or refers to a missing record"
        code = "integrity_error"
        if "reference_number" in text or "donation reference" in text:
            detail = "Donation reference already exists"
            code = "duplicate_reference"
        elif "receipt_number" in text or "donation_id" in text and "receipt" in text:
            detail = "A receipt already exists for this donation"
            code = "duplicate_receipt"
        return JSONResponse(status_code=409, content={"detail": detail, "code": code})

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception):
        logger.exception("Unhandled error")
        detail = "Internal server error"
        if settings.debug:
            detail = f"{exc.__class__.__name__}: {exc}"
        return JSONResponse(status_code=500, content={"detail": detail, "code": "internal_error"})
