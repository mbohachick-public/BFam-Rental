from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


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


class BookingRequestCreate(BaseModel):
    item_id: str
    start_date: date
    end_date: date
    customer_email: str | None = None
    notes: str | None = None


class BookingRequestOut(BaseModel):
    id: str
    item_id: str
    start_date: date
    end_date: date
    status: BookingRequestStatus
    customer_email: str | None
    notes: str | None
    base_amount: Decimal | None
    discount_percent: Decimal | None
    discounted_subtotal: Decimal | None
    deposit_amount: Decimal | None
    drivers_license_url: str | None = None
    license_plate_url: str | None = None


class ItemCreate(BaseModel):
    title: str
    description: str = ""
    category: str = "general"
    cost_per_day: Decimal
    minimum_day_rental: int = 1
    deposit_amount: Decimal = Decimal("0")
    user_requirements: str = ""
    towable: bool = False
    image_urls: list[str] = Field(default_factory=list)


class ItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    cost_per_day: Decimal | None = None
    minimum_day_rental: int | None = None
    deposit_amount: Decimal | None = None
    user_requirements: str | None = None
    towable: bool | None = None
    image_urls: list[str] | None = None


class DayStatusUpdate(BaseModel):
    day: date
    status: DayStatus


class AvailabilityBulkUpdate(BaseModel):
    days: list[DayStatusUpdate]
