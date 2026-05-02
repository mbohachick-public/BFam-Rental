from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class DayStatus(str, Enum):
    out_for_use = "out_for_use"
    booked = "booked"
    open_for_booking = "open_for_booking"
    readying_for_use = "readying_for_use"
    pending_request = "pending_request"


class BookingRequestStatus(str, Enum):
    """Lifecycle for booking_requests; includes legacy values for existing rows."""

    pending = "pending"
    requested = "requested"
    under_review = "under_review"
    approved_awaiting_signature = "approved_awaiting_signature"
    approved_pending_payment = "approved_pending_payment"
    approved_pending_check_clearance = "approved_pending_check_clearance"
    confirmed = "confirmed"
    ready_for_pickup = "ready_for_pickup"
    checked_out = "checked_out"
    returned_pending_inspection = "returned_pending_inspection"
    completed = "completed"
    completed_with_charges = "completed_with_charges"
    cancelled = "cancelled"
    declined = "declined"
    accepted = "accepted"
    rejected = "rejected"


class PaymentPath(str, Enum):
    """Collection path when approving — product is card (Stripe) only."""

    card = "card"


def payment_path_from_stored(value: object) -> PaymentPath:
    """Normalize a DB ``payment_path`` for API use. Legacy non-card values map to ``card``."""
    raw = str(value or "").strip().lower()
    if not raw:
        raise ValueError("payment_path is empty")
    return PaymentPath.card


class RentalPaymentStatus(str, Enum):
    """Rental line (not deposit) — Stripe webhook or admin mark."""

    unpaid = "unpaid"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


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
    delivery_available: bool = True
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
    delivery_fee: Decimal = Decimal("0")
    delivery_distance_miles: Decimal | None = None
    sales_tax_rate_percent: Decimal
    sales_tax_amount: Decimal
    rental_total_with_tax: Decimal
    email_sent: bool = False


class BookingQuoteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    item_id: str
    start_date: date
    end_date: date
    customer_email: EmailStr
    tax_postal_code: str | None = Field(default=None, max_length=16)
    delivery_requested: bool = False
    delivery_address: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _delivery_address_when_requested(self) -> Self:
        if self.delivery_requested and not (self.delivery_address or "").strip():
            raise ValueError("delivery_address is required when delivery_requested is true.")
        return self


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
    insurance_card_content_type: str | None = Field(default=None, max_length=80)
    company_name: str | None = Field(default=None, max_length=200)
    is_repeat_contractor: bool = False
    tow_vehicle_year: int | None = Field(default=None, ge=1950, le=2100)
    tow_vehicle_make: str | None = Field(default=None, max_length=80)
    tow_vehicle_model: str | None = Field(default=None, max_length=80)
    tow_vehicle_tow_rating_lbs: int | None = Field(default=None, ge=1)
    has_brake_controller: bool | None = None
    request_not_confirmed_ack: bool = False
    delivery_requested: bool = False
    delivery_address: str | None = Field(default=None, max_length=500)

    @field_validator("request_not_confirmed_ack")
    @classmethod
    def _must_ack_request_not_confirmed(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must acknowledge that this is a request, not a confirmed reservation.")
        return v

    @model_validator(mode="after")
    def _delivery_address_when_requested_presign(self) -> Self:
        if self.delivery_requested and not (self.delivery_address or "").strip():
            raise ValueError("delivery_address is required when delivery_requested is true.")
        return self


class BookingPresignResponse(BaseModel):
    booking_id: str
    drivers_license: BookingUploadSlot
    license_plate: BookingUploadSlot | None = None
    insurance_card: BookingUploadSlot | None = None
    expires_in: int


class BookingCompleteBody(BaseModel):
    """Paths returned from presign; must belong to this booking and match expected prefixes."""

    model_config = ConfigDict(str_strip_whitespace=True)

    drivers_license_path: str = Field(..., min_length=8, max_length=500)
    license_plate_path: str | None = Field(default=None, max_length=500)
    insurance_card_path: str | None = Field(default=None, max_length=500)


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
    payment_collection_url: str | None = None
    # Populated when admin generated Stripe Checkout (card path); same row as admin UI.
    stripe_checkout_url: str | None = None
    stripe_deposit_checkout_url: str | None = None


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
    #: Set on GET /admin/booking-requests/{id} for display; omitted on list responses.
    item_title: str | None = None
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
    insurance_card_url: str | None = None
    decline_email_sent: bool | None = None
    company_name: str | None = None
    delivery_address: str | None = None
    delivery_requested: bool | None = None
    delivery_fee: Decimal | None = None
    delivery_distance_miles: Decimal | None = None
    payment_method_preference: str | None = None
    is_repeat_contractor: bool | None = None
    tow_vehicle_year: int | None = None
    tow_vehicle_make: str | None = None
    tow_vehicle_model: str | None = None
    tow_vehicle_tow_rating_lbs: int | None = None
    has_brake_controller: bool | None = None
    request_not_confirmed_ack: bool | None = None
    payment_path: str | None = None
    payment_collection_url: str | None = None
    approved_at: str | None = None
    rental_paid_at: str | None = None
    deposit_secured_at: str | None = None
    agreement_signed_at: str | None = None
    stripe_invoice_id: str | None = None
    stripe_checkout_session_id: str | None = None
    stripe_checkout_url: str | None = None
    stripe_payment_intent_id: str | None = None
    rental_payment_status: RentalPaymentStatus | None = None
    stripe_checkout_created_at: str | None = None
    stripe_deposit_captured_cents: int | None = None
    deposit_refunded_at: str | None = None
    stripe_deposit_refund_id: str | None = None
    stripe_deposit_checkout_session_id: str | None = None
    stripe_deposit_checkout_url: str | None = None
    stripe_deposit_checkout_created_at: str | None = None
    stripe_deposit_payment_intent_id: str | None = None
    # Populated only on admin approve/resend for copy to customer (not stored on row).
    signing_url: str | None = None


class StripeCheckoutSessionOut(BaseModel):
    """URLs from the latest generate call; either side may be null if already paid/secured."""

    stripe_checkout_session_id: str | None = None
    stripe_checkout_url: str | None = None
    stripe_checkout_created_at: str | None = None
    stripe_deposit_checkout_session_id: str | None = None
    stripe_deposit_checkout_url: str | None = None
    stripe_deposit_checkout_created_at: str | None = None
    #: ``sent`` | ``skipped_no_smtp`` | ``skipped_no_customer_email`` | ``skipped_no_payment_links`` |
    #: ``skipped_payment_links_in_approval_email`` (awaiting signature — use resend signing email) | ``failed_smtp:…``
    stripe_checkout_email_status: str | None = None


class StripeCheckoutSyncOut(BaseModel):
    """Result of POST …/sync-stripe-checkout (pull paid Checkout sessions into the booking row)."""

    actions: list[str]
    booking: BookingRequestOut


class BookingPaymentStatusPublic(BaseModel):
    """Minimal fields for post-checkout thank-you page (no auth)."""

    booking_id: str
    status: str
    rental_paid: bool
    rental_payment_status: str | None = None
    item_title: str
    deposit_secured: bool = False
    requires_deposit: bool = False


class BookingApproveBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    payment_path: PaymentPath = PaymentPath.card


class BookingSignAcknowledgments(BaseModel):
    rental_agreement: bool = False
    damage_fee_schedule: bool = False
    responsibility_fees: bool = False
    payment_deposit_gate: bool = False


class BookingSignSubmit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    signer_name: str = Field(..., min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    #: Omitted or empty → use ``customer_email`` on the booking (signing link is already secret).
    signer_email: EmailStr | None = None
    typed_signature: str = Field(..., min_length=1, max_length=200)
    acknowledgments: BookingSignAcknowledgments

    @model_validator(mode="after")
    def _all_acks(self) -> Self:
        a = self.acknowledgments
        if not (
            a.rental_agreement
            and a.damage_fee_schedule
            and a.responsibility_fees
            and a.payment_deposit_gate
        ):
            raise ValueError("All acknowledgment checkboxes must be accepted.")
        return self


class BookingSignPageOut(BaseModel):
    item_title: str
    start_date: str
    end_date: str
    delivery_address: str | None
    rental_total_with_tax: str | None
    deposit_amount: str | None
    payment_path: str | None
    customer_first_name: str | None = None
    customer_last_name: str | None = None
    customer_email: str | None = None
    company_name: str | None = None
    agreement_html: str
    damage_html: str
    expires_at: str


class BookingSignResultOut(BaseModel):
    ok: bool
    next_status: str
    next_url: str


class BookingSignCompleteOut(BaseModel):
    ok: bool
    message: str
    booking_id: str
    booking_status: str | None = None
    payment_path: str | None = None
    stripe_checkout_url: str | None = None
    stripe_deposit_checkout_url: str | None = None
    rental_balance_paid: bool = False
    deposit_secured: bool = False


class ResendSignatureOut(BaseModel):
    signing_url: str


class DeliverySettingsOut(BaseModel):
    """Singleton delivery pricing (id=1). Maps API key is configured via env only."""

    id: int = 1
    enabled: bool
    origin_address: str
    price_per_mile: Decimal
    minimum_fee: Decimal
    free_miles: Decimal
    max_delivery_miles: Decimal | None = None
    google_maps_configured: bool = False


class DeliverySettingsUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    enabled: bool | None = None
    origin_address: str | None = Field(default=None, max_length=500)
    price_per_mile: Decimal | None = Field(default=None, ge=0)
    minimum_fee: Decimal | None = Field(default=None, ge=0)
    free_miles: Decimal | None = Field(default=None, ge=0)
    max_delivery_miles: Decimal | None = Field(default=None, ge=0)


class ItemCreate(BaseModel):
    title: str
    description: str = ""
    category: str = "general"
    cost_per_day: Decimal
    minimum_day_rental: int = 1
    deposit_amount: Decimal = Decimal("0")
    user_requirements: str = ""
    towable: bool = False
    delivery_available: bool = True
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
    delivery_available: bool | None = None
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
