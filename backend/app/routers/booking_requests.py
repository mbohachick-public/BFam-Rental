from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from supabase import Client

from app.config import get_settings
from app.deps import get_supabase_client
from app.schemas import BookingQuote, BookingRequestCreate, BookingRequestOut, BookingRequestStatus, DayStatus
from app.services.booking import compute_rental_amounts, validate_booking_dates
from app.services.booking_documents import ext_for_content_type, validate_image_upload
from app.services.booking_storage import save_booking_document
from app.services.booking_response import booking_out_from_row
from app.services.dates import iter_days_inclusive

router = APIRouter(prefix="/booking-requests", tags=["booking-requests"])


def _decimal(v: object) -> Decimal:
    return Decimal(str(v))


def _today_utc() -> date:
    return date.today()


def _read_upload(upload: UploadFile) -> tuple[bytes, str | None]:
    raw = upload.file.read()
    return raw, upload.content_type


@router.post("", response_model=BookingRequestOut, status_code=status.HTTP_201_CREATED)
def create_booking_request(
    item_id: str = Form(),
    start_date: date = Form(),
    end_date: date = Form(),
    customer_email: str | None = Form(None),
    notes: str | None = Form(None),
    drivers_license: UploadFile = File(),
    license_plate: UploadFile | None = File(default=None),
    client: Client = Depends(get_supabase_client),
) -> BookingRequestOut:
    settings = get_settings()
    item_res = (
        client.table("items")
        .select("id,cost_per_day,minimum_day_rental,deposit_amount,towable")
        .eq("id", item_id)
        .limit(1)
        .execute()
    )
    rows = item_res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item = rows[0]
    towable = bool(item.get("towable", False))
    clean_email = (customer_email or "").strip() or None
    clean_notes = (notes or "").strip() or None
    cost = _decimal(item["cost_per_day"])
    min_days = int(item["minimum_day_rental"])
    deposit = _decimal(item["deposit_amount"])

    if not drivers_license.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A driver's license image is required.",
        )

    lp_has_file = bool(license_plate and license_plate.filename)
    if towable and not lp_has_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A license plate image is required for towable items.",
        )
    if not towable and lp_has_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License plate image is only allowed for towable items.",
        )

    today = _today_utc()
    days = iter_days_inclusive(start_date, end_date)

    status_res = (
        client.table("item_day_status")
        .select("day,status")
        .eq("item_id", item_id)
        .gte("day", min(days).isoformat())
        .lte("day", max(days).isoformat())
        .execute()
    )
    open_dates: set[date] = set()
    for r in status_res.data or []:
        d = date.fromisoformat(str(r["day"]))
        if r["status"] == DayStatus.open_for_booking.value:
            open_dates.add(d)

    err = validate_booking_dates(today, start_date, end_date, min_days, open_dates)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    num_days = len(days)
    base, disc_pct, disc_sub, dep = compute_rental_amounts(cost, num_days, deposit)

    insert_res = (
        client.table("booking_requests")
        .insert(
            {
                "item_id": item_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "status": BookingRequestStatus.pending.value,
                "customer_email": clean_email,
                "notes": clean_notes,
                "base_amount": float(base),
                "discount_percent": float(disc_pct),
                "discounted_subtotal": float(disc_sub),
                "deposit_amount": float(dep),
            }
        )
        .execute()
    )
    data = insert_res.data
    if not data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    row = data[0]
    bid = row["id"]

    try:
        dl_raw, dl_ct = _read_upload(drivers_license)
        try:
            dl_type = validate_image_upload(dl_ct, len(dl_raw), "Driver's license")
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        dl_ext = ext_for_content_type(dl_type)
        path_dl = f"{bid}/drivers_license{dl_ext}"
        save_booking_document(settings, client, path_dl, dl_raw, dl_type)

        path_lp_val = None
        if towable and license_plate is not None:
            lp_raw, lp_ct = _read_upload(license_plate)
            try:
                lp_type = validate_image_upload(lp_ct, len(lp_raw), "License plate")
            except ValueError as e:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
            lp_ext = ext_for_content_type(lp_type)
            path_lp_val = f"{bid}/license_plate{lp_ext}"
            save_booking_document(settings, client, path_lp_val, lp_raw, lp_type)

        client.table("booking_requests").update(
            {"drivers_license_path": path_dl, "license_plate_path": path_lp_val}
        ).eq("id", bid).execute()
    except HTTPException:
        client.table("booking_requests").delete().eq("id", bid).execute()
        raise
    except Exception as exc:
        client.table("booking_requests").delete().eq("id", bid).execute()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_booking_store_error_detail(settings),
        ) from exc

    res2 = client.table("booking_requests").select("*").eq("id", bid).limit(1).execute()
    final = res2.data[0]
    return booking_out_from_row(client, final, sign_document_urls=False)


def _booking_store_error_detail(settings) -> str:
    if settings.booking_documents_storage == "local":
        return (
            "Could not save booking documents to disk. Check that "
            f"BOOKING_DOCUMENTS_LOCAL_DIR ({settings.booking_documents_local_dir}) is writable."
        )
    return (
        "Could not store booking documents in Supabase Storage. Ensure the "
        "'booking-documents' bucket exists and BOOKING_DOCUMENTS_STORAGE=supabase is set for production."
    )


@router.post("/quote", response_model=BookingQuote)
def quote_booking(
    body: BookingRequestCreate,
    client: Client = Depends(get_supabase_client),
) -> BookingQuote:
    """Preview pricing without persisting (same validation as create)."""
    item_res = (
        client.table("items")
        .select("id,cost_per_day,minimum_day_rental,deposit_amount")
        .eq("id", body.item_id)
        .limit(1)
        .execute()
    )
    rows = item_res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item = rows[0]
    cost = _decimal(item["cost_per_day"])
    min_days = int(item["minimum_day_rental"])
    deposit = _decimal(item["deposit_amount"])

    today = _today_utc()
    days = iter_days_inclusive(body.start_date, body.end_date)
    status_res = (
        client.table("item_day_status")
        .select("day,status")
        .eq("item_id", body.item_id)
        .gte("day", min(days).isoformat())
        .lte("day", max(days).isoformat())
        .execute()
    )
    open_dates: set[date] = set()
    for r in status_res.data or []:
        d = date.fromisoformat(str(r["day"]))
        if r["status"] == DayStatus.open_for_booking.value:
            open_dates.add(d)

    err = validate_booking_dates(today, body.start_date, body.end_date, min_days, open_dates)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    num_days = len(days)
    base, disc_pct, disc_sub, dep = compute_rental_amounts(cost, num_days, deposit)
    return BookingQuote(
        num_days=num_days,
        base_amount=base,
        discount_percent=disc_pct,
        discounted_subtotal=disc_sub,
        deposit_amount=dep,
    )
