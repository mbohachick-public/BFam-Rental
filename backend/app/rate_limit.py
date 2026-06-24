"""Shared SlowAPI limiter + path-prefix rate limiting for routes without per-handler decorators."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, status
from slowapi import Limiter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


def _client_ip(request: Request) -> str:
    """Prefer the first X-Forwarded-For hop when behind Render / CDN."""
    xf = (request.headers.get("x-forwarded-for") or "").strip()
    if xf:
        return xf.split(",")[0].strip()
    xr = (request.headers.get("x-real-ip") or "").strip()
    if xr:
        return xr
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    if request.client:
        return request.client.host
    return "unknown"


limiter = Limiter(key_func=_client_ip)

# (max_requests, window_seconds) per URL prefix — checked longest-prefix first.
_PREFIX_LIMITS: list[tuple[str, int, int]] = [
    ("/admin", 120, 60),
    ("/booking-actions", 30, 60),
    ("/items", 120, 60),
    ("/trailer-match/requests", 30, 60),
]


class _SlidingWindowCounter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        q = self._buckets[key]
        cutoff = now - window_seconds
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= max_requests:
            return False
        q.append(now)
        return True


_prefix_counter = _SlidingWindowCounter()


def _prefix_limit_for_path(path: str) -> tuple[int, int] | None:
    for prefix, max_req, window in sorted(_PREFIX_LIMITS, key=lambda x: -len(x[0])):
        if path == prefix or path.startswith(prefix + "/"):
            return max_req, window
    return None


class PrefixRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate-limit un-decorated routes (admin catalog, signing GET, etc.) by path prefix."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        limit = _prefix_limit_for_path(request.url.path)
        if limit is not None:
            max_req, window = limit
            ip = _client_ip(request)
            key = f"{request.url.path.split('/')[1]}:{ip}"
            if not _prefix_counter.allow(key, max_requests=max_req, window_seconds=window):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Please try again shortly."},
                )
        return await call_next(request)


def install_rate_limit_middleware(app: ASGIApp) -> None:
    app.add_middleware(PrefixRateLimitMiddleware)
