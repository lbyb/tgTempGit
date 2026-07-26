from __future__ import annotations

from typing import Callable, Awaitable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.config import get_settings

settings = get_settings()

SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path

        if path in SKIP_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        token = request.query_params.get("token", "")
        if token != settings.TOKEN:
            return Response(
                content='{"detail":"Forbidden: invalid token"}',
                status_code=403,
                media_type="application/json",
            )

        return await call_next(request)
