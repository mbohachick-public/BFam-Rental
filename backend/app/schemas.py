from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DayStatus(str, Enum):
    out_for_use = "out_for_use"
    booked = "booked"
    open_for_booking = "open_for_booking"
    readying_for_use = "readying_for_use"


class BookingRequestStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class ItemImageOut(BaseModel):
    id: str
    url: str
    sort_order: int


class ItemSummary(BaseModel):
    id: str
    title: str
    category: str
    cost_per_day: Decimal
    minimum_day_rental: int
    deposit_amount: Decimal
    towable: bool = False
    image_urls: list[str] = Field(default_factory=list)
    # True = shown in public catalog; False = admin-only (hidden from customers)
    active: bool = True


class ItemDetail(ItemSummary):
    description: str
    user_requirements: str
    images: list[ItemImageOut] = Field(default_factory=list)


class DayAvailability(BaseModel):
    day: date
    status: DayStatus | None = None


class BookingQuote(BaseModel):
    num_days: int
    base_amount: Decimal
    discount_percent: Decimal
    discounted_subtotal: Decimal
    deposit_amount: Decimal
    sales_tax_rate_percent: Decimal
    sales_tax_amount: Decimal
    rental_total_with_tax: Decimal
    sales_tax_source: str
    email_sent: bool = False


class BookingQuoteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    item_id: str
    start_date: date
    end_date: date
    customer_email: EmailStr
    tax_postal_code: str | None = Field(default=None, max_length=16)


class BookingContactForm(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    customer_email: EmailStr
    customer_phone: str = Field(..., min_length=7, max_length=32)
    customer_first_name: str = Field(..., min_length=1, max_length=100)
    customer_last_name: str = Field(..., min_length=1, max_length=100)
    customer_address: str = Field(..., min_length=1, max_length=500)


class BookingRequestCreate(BookingContactForm):
    item_id: str
    start_date: date
    end_date: date
    notes: str | None = None


class BookingUploadSlot(BaseModel):
    """One signed URL for direct upload to Supabase Storage (booking-documents bucket)."""

    path: str
    signed_url: str
    token: str


class BookingPresignRequest(BookingContactForm):
    """Start a booking with direct-to-storage uploads; same fields as multipart minus file bodies."""

    model_config = ConfigDict(str_strip_whitespace=True)

    item_id: str
    start_date: date
    end_date: date
    notes: str | None = None
    drivers_license_content_type: str = Field(..., min_length=3, max_length=80)
    license_plate_content_type: str | None = Field(default=None, max_length=80)


class BookingPresignResponse(BaseModel):
    booking_id: str
    drivers_license: BookingUploadSlot
    license_plate: BookingUploadSlot | None = None
    expires_in: int


class BookingCompleteBody(BaseModel):
    """Paths returned from presign; must belong to this booking and match expected prefixes."""

    model_config = ConfigDict(str_strip_whitespace=True)

    drivers_license_path: str = Field(..., min_length=8, max_length=500)
    license_plate_path: str | None = Field(default=None, max_length=500)


class BookingDeclineBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(..., min_length=1, max_length=2000)


class CustomerBookingSummary(BaseModel):
    """Customer-facing booking row (no document URLs)."""

    id: str
    item_id: str
    item_title: str
    item_active: bool
    start_date: date
    end_date: date
    status: BookingRequestStatus
    discounted_subtotal: Decimal | None = None
    rental_total_with_tax: Decimal | None = None
    deposit_amount: Decimal | None = None


class CustomerContactProfile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    customer_email: EmailStr
    customer_phone: str
    customer_first_name: str
    customer_last_name: str
    customer_address: str


class BookingRequestOut(BaseModel):
    id: str
    item_id: str
    start_date: date
    end_date: date
    status: BookingRequestStatus
    customer_email: str | None
    customer_phone: str | None = None
    customer_first_name: str | None = None
    customer_last_name: str | None = None
    customer_address: str | None = None
    notes: str | None
    decline_reason: str | None = None
    base_amount: Decimal | None
    discount_percent: Decimal | None
    discounted_subtotal: Decimal | None
    deposit_amount: Decimal | None
    sales_tax_rate_percent: Decimal | None = None
    sales_tax_amount: Decimal | None = None
    rental_total_with_tax: Decimal | None = None
    sales_tax_source: str | None = None
    drivers_license_url: str | None = None
    license_plate_url: str | None = None
    decline_email_sent: bool | None = None


class ItemCreate(BaseModel):
    title: str
    description: str = ""
    category: str = "general"
    cost_per_day: Decimal
    minimum_day_rental: int = 1
    deposit_amount: Decimal = Decimal("0")
    user_requirements: str = ""
    towable: bool = False
    active: bool = True
    image_urls: Annotated[list[str], Field(default_factory=list, max_length=10)]


class ItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    cost_per_day: Decimal | None = None
    minimum_day_rental: int | None = None
    deposit_amount: Decimal | None = None
    user_requirements: str | None = None
    towable: bool | None = None
    active: bool | None = None
    image_urls: Annotated[list[str] | None, Field(default=None, max_length=10)]


class DayStatusUpdate(BaseModel):
    day: date
    status: DayStatus


class AvailabilityBulkUpdate(BaseModel):
    days: list[DayStatusUpdate]


class E2eCleanupBody(BaseModel):
    confirm: bool


class E2eCleanupResult(BaseModel):
    items_deleted: int
    bookings_processed_for_file_cleanup: int
