import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.rate_limit import install_rate_limit_middleware, limiter
from app.routers import admin, booking_actions, booking_requests, items, stripe_webhook, trailer_match
from app.services.quote_email import smtp_configured

_log = logging.getLogger(__name__)

_CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
_CORS_HEADERS = [
    "Authorization",
    "Content-Type",
    "X-Booking-Step-Token",
    "X-Booking-Sign-Token",
    "Accept",
]

app = FastAPI(title="BFam Rental API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
install_rate_limit_middleware(app)

settings = get_settings()
if smtp_configured(settings):
    _log.info(
        "SMTP enabled host=%s port=%s timeout_s=%s starttls=%s debug=%s",
        settings.smtp_host.strip(),
        int(settings.smtp_port),
        int(settings.smtp_timeout_seconds),
        settings.smtp_use_tls,
        settings.smtp_debug,
    )

origins = settings.cors_origin_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=_CORS_METHODS,
    allow_headers=_CORS_HEADERS,
)

app.include_router(items.router)
app.include_router(booking_requests.router)
app.include_router(booking_actions.router)
app.include_router(admin.router)
app.include_router(stripe_webhook.router)
app.include_router(trailer_match.router)


@app.on_event("startup")
def _validate_production_security() -> None:
    s = get_settings()
    if not s.is_production:
        return
    if not (s.auth0_domain or "").strip() or not (s.auth0_audience or "").strip():
        raise RuntimeError(
            "ENVIRONMENT=production requires AUTH0_DOMAIN and AUTH0_AUDIENCE to be set on the API."
        )
    if not (s.auth0_admin_subs or "").strip() and not (s.auth0_admin_emails or "").strip():
        _log.warning(
            "AUTH0_ADMIN_SUBS and AUTH0_ADMIN_EMAILS are both unset in production; "
            "admin access relies on AUTH0_ADMIN_ROLES (%s) only.",
            (s.auth0_admin_roles or "admin").strip() or "admin",
        )
    if not s.cors_origin_list:
        raise RuntimeError("ENVIRONMENT=production requires CORS_ORIGINS to list allowed browser origins.")


@app.get("/")
def root() -> dict[str, str]:
    # Render may probe HEAD / during deploy; ensure a 200 response.
    return {"status": "ok"}


@app.exception_handler(httpx.ConnectError)
async def supabase_unreachable(_request: Request, _exc: httpx.ConnectError) -> JSONResponse:
    """Supabase hostname failed DNS / TCP (bad SUPABASE_URL, offline, typo)."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Cannot reach Supabase. In backend/.env set SUPABASE_URL to your Project URL "
                "(Supabase → Project Settings → API). It must look like https://abcdefghij.supabase.co "
                "with no angle brackets or placeholder text. Then restart uvicorn."
            )
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
