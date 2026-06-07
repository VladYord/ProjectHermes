"""Authentication middleware — API key check for non-localhost requests."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from hermes.config import get_config
from hermes.log_setup import get_logger

logger = get_logger("auth")

_LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}


class AuthMiddleware(BaseHTTPMiddleware):
    """API key authentication middleware.

    - Skipped entirely if auth is disabled in config.
    - Skipped for localhost requests (same-machine access).
    - Requires X-API-Key header for non-localhost requests.
    """

    async def dispatch(self, request: Request, call_next):
        cfg = get_config().server.auth

        if not cfg.enabled:
            return await call_next(request)

        # Allow localhost without auth
        client_host = request.client.host if request.client else ""
        if client_host in _LOCALHOST_HOSTS:
            return await call_next(request)

        # Check API key for non-localhost
        api_key = request.headers.get("X-API-Key", "")
        if not api_key or api_key != cfg.api_key:
            logger.warning("Unauthorized request from %s", client_host)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
