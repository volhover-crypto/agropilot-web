# backend/common/errors.py -- AgroPILOT shared HTTP error handler
# Usage:
#   from backend.common.errors import register_error_handlers
#   register_error_handlers(app)  # call once in main.py / app factory
#
# All HTTPException responses are returned in the unified contract format:
#   {"ok": false, "error": {"code": "<CODE>", "message": "<text>"}}

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

# Mapping of HTTP status codes to short uppercase error codes
_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE",
    500: "INTERNAL_ERROR",
}


def _error_code(status: int) -> str:
    return _CODE_MAP.get(status, f"HTTP_{status}")


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Replaces FastAPI default HTTPException handler.

    Converts any HTTPException into the AgroPILOT contract error envelope:
        {"ok": false, "error": {"code": "NOT_FOUND", "message": "..."}}
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": _error_code(exc.status_code),
                "message": str(exc.detail),
            },
        },
    )


def register_error_handlers(app) -> None:
    """Register all shared error handlers on a FastAPI app instance.

    Call once during app startup:
        from backend.common.errors import register_error_handlers
        register_error_handlers(app)
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
