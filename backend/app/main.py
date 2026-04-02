import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import admin, booking_requests, items

app = FastAPI(title="BFam Rental API", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router)
app.include_router(booking_requests.router)
app.include_router(admin.router)


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
