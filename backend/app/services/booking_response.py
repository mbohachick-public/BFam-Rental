from datetime import date
from decimal import Decimal

from supabase import Client

from app.config import get_settings
from app.schemas import BookingRequestOut, BookingRequestStatus, RentalPaymentStatus
from app.services.booking_storage import admin_document_view_urls


def _dec(v: object | None) -> Decimal | None:
    if v is None:
        return None
    return Decimal(str(v))


def _str_opt(v: object | None) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _rental_payment_status(row: dict) -> RentalPaymentStatus:
    raw = row.get("rental_payment_status")
    if raw is not None and str(raw).strip():
        try:
            return RentalPaymentStatus(str(raw).strip())
        except ValueError:
            pass
    return RentalPaymentStatus.paid if row.get("rental_paid_at") else RentalPaymentStatus.unpaid


def booking_out_from_row(
    client: Client,
    row: dict,
    *,
    sign_document_urls: bool,
    decline_email_sent: bool | None = None,
    signing_url: str | None = None,
) -> BookingRequestOut:
    dl_url = lp_url = None
    if sign_document_urls:
        dl_url, lp_url = admin_document_view_urls(get_settings(), client, row)
    hb = row.get("has_brake_controller")
    has_brake = bool(hb) if hb is not None else None
    return BookingRequestOut(
        id=row["id"],
        item_id=row["item_id"],
        start_date=date.fromisoformat(str(row["start_date"])),
        end_date=date.fromisoformat(str(row["end_date"])),
        status=BookingRequestStatus(row["status"]),
        customer_email=row.get("customer_email"),
        customer_phone=row.get("customer_phone"),
        customer_first_name=row.get("customer_first_name"),
        customer_last_name=row.get("customer_last_name"),
        customer_address=row.get("customer_address"),
        notes=row.get("notes"),
        decline_reason=row.get("decline_reason"),
        base_amount=_dec(row.get("base_amount")),
        discount_percent=_dec(row.get("discount_percent")),
        discounted_subtotal=_dec(row.get("discounted_subtotal")),
        deposit_amount=_dec(row.get("deposit_amount")),
        sales_tax_rate_percent=_dec(row.get("sales_tax_rate_percent")),
        sales_tax_amount=_dec(row.get("sales_tax_amount")),
        rental_total_with_tax=_dec(row.get("rental_total_with_tax")),
        sales_tax_source=row.get("sales_tax_source"),
        drivers_license_url=dl_url,
        license_plate_url=lp_url,
        decline_email_sent=decline_email_sent,
        company_name=_str_opt(row.get("company_name")),
        delivery_address=_str_opt(row.get("delivery_address")),
        delivery_requested=(
            None
            if row.get("delivery_requested") is None
            else bool(row.get("delivery_requested"))
        ),
        delivery_fee=_dec(row.get("delivery_fee")),
        delivery_distance_miles=_dec(row.get("delivery_distance_miles")),
        payment_method_preference=_str_opt(row.get("payment_method_preference")),
        is_repeat_contractor=row.get("is_repeat_contractor")
        if row.get("is_repeat_contractor") is not None
        else None,
        tow_vehicle_year=row.get("tow_vehicle_year"),
        tow_vehicle_make=_str_opt(row.get("tow_vehicle_make")),
        tow_vehicle_model=_str_opt(row.get("tow_vehicle_model")),
        tow_vehicle_tow_rating_lbs=row.get("tow_vehicle_tow_rating_lbs"),
        has_brake_controller=has_brake,
        request_not_confirmed_ack=row.get("request_not_confirmed_ack")
        if row.get("request_not_confirmed_ack") is not None
        else None,
        payment_path=_str_opt(row.get("payment_path")),
        payment_collection_url=_str_opt(row.get("payment_collection_url")),
        approved_at=_str_opt(row.get("approved_at")),
        rental_paid_at=_str_opt(row.get("rental_paid_at")),
        deposit_secured_at=_str_opt(row.get("deposit_secured_at")),
        agreement_signed_at=_str_opt(row.get("agreement_signed_at")),
        stripe_invoice_id=_str_opt(row.get("stripe_invoice_id")),
        stripe_checkout_session_id=_str_opt(row.get("stripe_checkout_session_id")),
        stripe_checkout_url=_str_opt(row.get("stripe_checkout_url")),
        stripe_payment_intent_id=_str_opt(row.get("stripe_payment_intent_id")),
        stripe_deposit_captured_cents=(
            int(row["stripe_deposit_captured_cents"])
            if row.get("stripe_deposit_captured_cents") is not None
            else None
        ),
        deposit_refunded_at=_str_opt(row.get("deposit_refunded_at")),
        stripe_deposit_refund_id=_str_opt(row.get("stripe_deposit_refund_id")),
        rental_payment_status=_rental_payment_status(row),
        stripe_checkout_created_at=_str_opt(row.get("stripe_checkout_created_at")),
        stripe_deposit_checkout_session_id=_str_opt(row.get("stripe_deposit_checkout_session_id")),
        stripe_deposit_checkout_url=_str_opt(row.get("stripe_deposit_checkout_url")),
        stripe_deposit_checkout_created_at=_str_opt(row.get("stripe_deposit_checkout_created_at")),
        stripe_deposit_payment_intent_id=_str_opt(row.get("stripe_deposit_payment_intent_id")),
        signing_url=signing_url,
    )
