from datetime import date
from decimal import Decimal

from supabase import Client

from app.config import get_settings
from app.schemas import BookingRequestOut, BookingRequestStatus
from app.services.booking_storage import admin_document_view_urls


def _dec(v: object | None) -> Decimal | None:
    if v is None:
        return None
    return Decimal(str(v))


def booking_out_from_row(
    client: Client,
    row: dict,
    *,
    sign_document_urls: bool,
    decline_email_sent: bool | None = None,
) -> BookingRequestOut:
    dl_url = lp_url = None
    if sign_document_urls:
        dl_url, lp_url = admin_document_view_urls(get_settings(), client, row)
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
    )
