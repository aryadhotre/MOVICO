"""Request logging and uniform error responses."""

from __future__ import annotations

import logging
import time

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import settings

logger = logging.getLogger("app.api.middleware")

# Requests slower than this are logged at WARNING so latency regressions surface
# without one log line per request drowning the file.
SLOW_REQUEST_MS = 400.0


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Times every request and logs the ones that matter."""

    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - started) * 1000
            logger.exception(
                "%s %s failed after %.1fms", request.method, request.url.path, elapsed
            )
            # Re-raised so the registered exception handlers build the response;
            # returning here would bypass them and lose the uniform error shape.
            raise

        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Process-Time"] = f"{elapsed:.1f}ms"

        if response.status_code >= 500:
            logger.error(
                "%s %s -> %d (%.1fms)",
                request.method, request.url.path, response.status_code, elapsed,
            )
        elif elapsed > SLOW_REQUEST_MS:
            logger.warning(
                "Slow: %s %s -> %d (%.1fms)",
                request.method, request.url.path, response.status_code, elapsed,
            )
        else:
            logger.debug(
                "%s %s -> %d (%.1fms)",
                request.method, request.url.path, response.status_code, elapsed,
            )
        return response


def setup_exception_handlers(app) -> None:
    """Registers handlers that give every error the same JSON shape."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Flattens pydantic errors into one readable sentence.

        The default 422 body is a nested list the frontend rendered as
        "[object Object]"; this gives it something displayable.
        """
        problems = [
            f"{'.'.join(str(part) for part in error['loc'][1:]) or 'body'}: {error['msg']}"
            for error in exc.errors()
        ]
        logger.warning("Validation failed on %s: %s", request.url.path, problems)
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "detail": "; ".join(problems) or "Invalid request",
                "errors": problems,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": "An unexpected error occurred on the server.",
                # The message is only echoed in development; in production it could
                # leak internals to the client.
                "message": str(exc) if settings.DEBUG else None,
            },
        )
