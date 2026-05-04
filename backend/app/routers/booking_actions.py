"""Tokenized customer actions (contract signing) — no auth; token is the secret."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import Client

from app.branding import LEGAL_BUSINESS_NAME
from app.config import get_settings
from app.deps import get_supabase_client
from app.schemas import (
    BookingSignCompleteOut,
    BookingSignPageOut,
    BookingSignResultOut,
    BookingSignSubmit,
)
from app.services.contract_signing import (
    complete_customer_signature,
    load_signing_page_payload,
    load_token_row_by_raw,
    resolve_sign_token,
)
router = APIRouter(prefix="/booking-actions", tags=["booking-actions"])


def _client_ip(request: Request) -> str | None:
    xf = request.headers.get("x-forwarded-for")
    if xf:
        return xf.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None


@router.get("/{token}/sign", response_model=BookingSignPageOut)
def get_sign_page(token: str, client: Client = Depends(get_supabase_client)) -> BookingSignPageOut:
    resolved = resolve_sign_token(client, token)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signing link.")
    if resolved.get("error") == "expired":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"This signing link has expired. Contact {LEGAL_BUSINESS_NAME} for a new link.",
        )
    if resolved.get("error") == "used":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This signing link was already used.",
        )
    tok = resolved["token_row"]
    booking_id = str(tok["booking_id"])
    payload = load_signing_page_payload(client, booking_id)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This booking is not awaiting signature.",
        )
    b = payload["booking"]
    def _str_opt(v: object | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    return BookingSignPageOut(
        item_title=payload["item_title"],
        start_date=str(b.get("start_date") or ""),
        end_date=str(b.get("end_date") or ""),
        delivery_address=b.get("delivery_address"),
        rental_total_with_tax=str(b.get("rental_total_with_tax") or "") or None,
        deposit_amount=str(b.get("deposit_amount") or "") or None,
        payment_path=str(b.get("payment_path") or "") or None,
        customer_first_name=_str_opt(b.get("customer_first_name")),
        customer_last_name=_str_opt(b.get("customer_last_name")),
        customer_email=_str_opt(b.get("customer_email")),
        company_name=_str_opt(b.get("company_name")),
        agreement_html=payload["agreement_html"],
        damage_html=payload["damage_html"],
        expires_at=str(tok.get("expires_at") or ""),
    )


@router.post("/{token}/sign", response_model=BookingSignResultOut)
def post_sign_page(
    token: str,
    body: BookingSignSubmit,
    request: Request,
    client: Client = Depends(get_supabase_client),
) -> BookingSignResultOut:
    settings = get_settings()
    ua = request.headers.get("user-agent")
    result = complete_customer_signature(
        client,
        settings,
        raw_token=token,
        signer_name=body.signer_name,
        signer_email=body.signer_email,
        company_name=body.company_name,
        typed_signature=body.typed_signature,
        acknowledgments=body.acknowledgments.model_dump(),
        ip_address=_client_ip(request),
        user_agent=ua,
    )
    err = result.get("error")
    if err == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signing link.")
    if err == "expired":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This signing link has expired.")
    if err == "used":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This signing link was already used.")
    if err == "email_mismatch":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must match the address on the booking request.",
        )
    if err == "email_required":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This booking has no email on file; contact the rental office to add one before signing.",
        )
    if err == "invalid_state":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This booking is not awaiting signature.",
        )
    if err == "already_signed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This booking was already signed.")
    if not result.get("ok"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not record signature.")
    return BookingSignResultOut(
        ok=True,
        next_status=str(result.get("next_status") or ""),
        next_url=f"/booking-actions/{token}/complete",
    )


@router.get("/{token}/complete", response_model=BookingSignCompleteOut)
def get_sign_complete(token: str, client: Client = Depends(get_supabase_client)) -> BookingSignCompleteOut:
    tok = load_token_row_by_raw(client, token)
    if not tok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid link.")
    if not tok.get("used_at"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete this page after signing the agreement.",
        )
    booking_id = str(tok["booking_id"])
    br = (
        client.table("booking_requests")
        .select(
            "status,payment_path,stripe_checkout_url,stripe_deposit_checkout_url,rental_paid_at,deposit_secured_at"
        )
        .eq("id", booking_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    row = br[0] if br else {}
    st = str(row.get("status") or "") or None
    paid = bool(row.get("rental_paid_at"))
    dep_secured = bool(row.get("deposit_secured_at"))
    raw_stripe = row.get("stripe_checkout_url")
    stripe_url = None
    if not paid and raw_stripe:
        stripe_url = str(raw_stripe).strip() or None
    raw_dep = row.get("stripe_deposit_checkout_url")
    dep_url = None
    if not dep_secured and raw_dep:
        dep_url = str(raw_dep).strip() or None
    pp = row.get("payment_path")
    payment_path = str(pp).strip() if pp else None
    return BookingSignCompleteOut(
        ok=True,
        message="Your signed rental agreement has been recorded. Complete payment and deposit steps to confirm your booking.",
        booking_id=booking_id,
        booking_status=st,
        payment_path=payment_path,
        stripe_checkout_url=stripe_url,
        stripe_deposit_checkout_url=dep_url,
        rental_balance_paid=paid,
        deposit_secured=dep_secured,
    )
