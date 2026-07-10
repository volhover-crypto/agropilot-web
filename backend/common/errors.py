# backend/common/errors.py -- AgroPILOT shared error handling
#
# USAGE (in main.py, called ONCE at startup):
#   from backend.common.errors import register_error_handlers
#   register_error_handlers(app)
#
# USAGE (in routers, instead of HTTPException):
#   from backend.common.errors import NotFoundError, ForbiddenError
#   raise NotFoundError("Event not found")
#
# All error responses conform to CONTRACTS.md §0 Error Contract:
#   {"ok": false, "error": {"code": "NOT_FOUND", "message": "..."}}

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


# ---------------------------------------------------------------------------
# Base custom exception
# ---------------------------------------------------------------------------

class APIError(HTTPException):
    """Base class for all AgroPILOT API errors.

    Attributes:
        status_code: HTTP status code (e.g. 404).
        code:        Machine-readable error code (e.g. "NOT_FOUND").
        message:     Human-readable error message.
    """

    code: str = "INTERNAL_ERROR"
    _default_status: int = 500  # safe fallback: direct APIError() -> 500 INTERNAL_ERROR

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.code = self.__class__.code
        super().__init__(
            status_code=status_code or self.__class__._default_status,
            detail=message,
        )


# ---------------------------------------------------------------------------
# Ready-made subclasses for common cases
# ---------------------------------------------------------------------------

class NotFoundError(APIError):
    """404 -- resource not found."""
    code = "NOT_FOUND"
    _default_status = 404


class ForbiddenError(APIError):
    """403 -- caller is not the owner / lacks permission."""
    code = "FORBIDDEN"
    _default_status = 403


class UnauthorizedError(APIError):
    """401 -- missing or invalid authentication."""
    code = "UNAUTHORIZED"
    _default_status = 401


class ConflictError(APIError):
    """409 -- resource already exists or state conflict."""
    code = "CONFLICT"
    _default_status = 409


class ValidationError(APIError):
    """422 -- business-level validation failure (not Pydantic schema)."""
    code = "VALIDATION_ERROR"
    _default_status = 422


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _error_body(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handler for custom APIError (and all its subclasses)."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message),
    )


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Fallback for plain HTTPException still used in third-party libs or old code.

    Maps status_code to uppercase code string; keeps response format consistent.
    """
    _STATUS_CODES: dict[int, str] = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE",
        500: "INTERNAL_ERROR",
    }
    code = _STATUS_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = str(exc.detail) if exc.detail else code
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, message),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler for Pydantic / FastAPI RequestValidationError (HTTP 422).

    Flattens validation errors into a single readable message:
    "body -> title: field required; body -> start_at: field required"
    """
    errors = exc.errors()
    parts = []
    for e in errors:
        loc = " -> ".join(str(x) for x in e.get("loc", []) if x != "body")
        msg = e.get("msg", "invalid")
        parts.append(f"{loc}: {msg}" if loc else msg)
    message = "; ".join(parts) if parts else "Validation error"
    return JSONResponse(
        status_code=422,
        content=_error_body("VALIDATION_ERROR", message),
    )


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_error_handlers(app) -> None:
    """Register all AgroPILOT error handlers on a FastAPI app instance.

    Call exactly ONCE during app startup in main.py:

        from backend.common.errors import register_error_handlers
        register_error_handlers(app)

    Order matters: APIError is registered before HTTPException so FastAPI
    resolves the more specific handler first.
    """
    # 1. Custom APIError subclasses (most specific -- register first)
    app.add_exception_handler(APIError, api_error_handler)
    # 2. Plain HTTPException (FastAPI + Starlette fallback)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    # 3. Pydantic / schema validation errors (422)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
