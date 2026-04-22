# Technical Implementation Spec for Codex
**Project:** BFam Rentals / bohachickrentals.com

## 1. Architecture approach
Preserve the current catalog and request flow. Add:
- booking workflow state machine
- payment objects
- deposit objects
- agreement tracking
- admin approval actions
- notification events

Assume modern web stack with server-rendered or SPA frontend and API backend. Keep implementation stack-agnostic where possible.

## 2. Suggested entities

### Product
```ts
type Product = {
  id: string;
  slug: string;
  name: string;
  category: "dump_trailer" | "car_hauler";
  gvwrLbs: number;
  lengthFeet: number;
  dovetailFeet?: number;
  dailyRateCents: number;
  weekendRateCents?: number;
  weeklyRateCents?: number;
  defaultDepositCents: number;
  deliveryAvailable: boolean;
  active: boolean;
};
```

### BookingRequest / Booking
```ts
type BookingStatus =
  | "requested"
  | "under_review"
  | "approved_pending_payment"
  | "approved_pending_check_clearance"
  | "confirmed"
  | "ready_for_pickup"
  | "checked_out"
  | "returned_pending_inspection"
  | "completed"
  | "completed_with_charges"
  | "declined"
  | "cancelled";

type PaymentMethodPreference = "card" | "ach" | "business_check";

type FulfillmentMethod = "pickup" | "delivery";

type Booking = {
  id: string;
  status: BookingStatus;
  productId: string;

  customerFirstName: string;
  customerLastName: string;
  companyName?: string;
  email: string;
  phone: string;

  startAt: string; // ISO datetime
  endAt: string;   // ISO datetime

  fulfillmentMethod: FulfillmentMethod;
  deliveryAddress?: string;

  paymentMethodPreference: PaymentMethodPreference;
  isRepeatContractorAccount: boolean;

  towVehicleYear?: number;
  towVehicleMake?: string;
  towVehicleModel?: string;
  towVehicleTowRatingLbs?: number;
  hasBrakeController?: boolean;

  approvedRateCents?: number;
  approvedDeliveryFeeCents?: number;
  approvedDepositCents?: number;

  agreementSignedAt?: string;
  approvedAt?: string;
  confirmedAt?: string;
  checkedOutAt?: string;
  returnedAt?: string;

  adminNotes?: string;
  createdAt: string;
  updatedAt: string;
};
```

### Payment
```ts
type PaymentStatus =
  | "not_required"
  | "pending"
  | "invoice_sent"
  | "processing"
  | "paid"
  | "failed"
  | "refunded"
  | "partially_refunded";

type Payment = {
  id: string;
  bookingId: string;
  provider: "stripe" | "manual";
  type: "rental_charge" | "delivery_fee" | "post_rental_charge";
  status: PaymentStatus;
  method: "card" | "ach" | "business_check";
  amountCents: number;
  externalReference?: string;
  paidAt?: string;
  createdAt: string;
  updatedAt: string;
};
```

### Deposit
```ts
type DepositStatus =
  | "not_started"
  | "authorization_pending"
  | "authorized"
  | "captured"
  | "partially_applied"
  | "applied"
  | "released"
  | "refunded"
  | "voided";

type Deposit = {
  id: string;
  bookingId: string;
  status: DepositStatus;
  method: "card";
  amountCents: number;
  externalReference?: string;
  securedAt?: string;
  releasedAt?: string;
  createdAt: string;
  updatedAt: string;
};
```

### Agreement
```ts
type Agreement = {
  id: string;
  bookingId: string;
  version: string;
  signerName?: string;
  signerEmail?: string;
  signedAt?: string;
  ipAddress?: string;
  userAgent?: string;
  documentUrl?: string;
  createdAt: string;
  updatedAt: string;
};
```

### BookingEvent
```ts
type BookingEvent = {
  id: string;
  bookingId: string;
  type: string;
  actorType: "customer" | "admin" | "system";
  actorId?: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
};
```

## 3. State machine rules
### Creation
New requests start as `requested`.

### Review
Admin may move `requested` -> `under_review`.

### Approval
Admin may move:
- `requested` -> `approved_pending_payment`
- `under_review` -> `approved_pending_payment`
- `requested` -> `approved_pending_check_clearance`
- `under_review` -> `approved_pending_check_clearance`

### Confirmation guard
Only allow transition into `confirmed` if:
- approved amount exists
- deposit is secured (`authorized` or `captured`)
- rental payment status is `paid`
- agreement is signed

### Checkout guard
Only allow transition into `checked_out` if:
- status is `confirmed` or `ready_for_pickup`
- agreement signed
- deposit secured
- payment paid

### Completion
`checked_out` -> `returned_pending_inspection` -> `completed` or `completed_with_charges`

### Decline/cancel
Admin may decline from any pre-checkout status.
Customer/admin may cancel from any pre-checkout status.

## 4. API endpoints
Suggested REST-ish endpoints. Equivalent GraphQL mutations are fine.

### Public
- `GET /api/products`
- `GET /api/products/:slug`
- `POST /api/bookings/request`
- `GET /api/bookings/:id/public-status`
- `POST /api/bookings/:id/sign-agreement`
- `POST /api/bookings/:id/payment-intent`
- `POST /api/bookings/:id/payment-webhook-preview` (dev only if helpful)

### Admin
- `GET /api/admin/bookings`
- `GET /api/admin/bookings/:id`
- `POST /api/admin/bookings/:id/approve`
- `POST /api/admin/bookings/:id/decline`
- `POST /api/admin/bookings/:id/mark-check-received`
- `POST /api/admin/bookings/:id/mark-check-cleared`
- `POST /api/admin/bookings/:id/mark-payment-received`
- `POST /api/admin/bookings/:id/secure-deposit`
- `POST /api/admin/bookings/:id/confirm`
- `POST /api/admin/bookings/:id/mark-ready`
- `POST /api/admin/bookings/:id/checkout`
- `POST /api/admin/bookings/:id/return`
- `POST /api/admin/bookings/:id/apply-post-rental-charge`
- `POST /api/admin/bookings/:id/release-deposit`
- `POST /api/admin/bookings/:id/refund-deposit`
- `POST /api/admin/bookings/:id/cancel`

## 5. Request and response shapes
### POST /api/bookings/request
Request:
```json
{
  "productId": "prod_14k_dump_16",
  "startAt": "2026-04-18T08:00:00-05:00",
  "endAt": "2026-04-19T18:00:00-05:00",
  "customerFirstName": "Matt",
  "customerLastName": "B",
  "companyName": "BFam Construction",
  "email": "matt@example.com",
  "phone": "555-555-5555",
  "fulfillmentMethod": "pickup",
  "deliveryAddress": null,
  "paymentMethodPreference": "business_check",
  "isRepeatContractorAccount": false,
  "towVehicleYear": 2021,
  "towVehicleMake": "Ford",
  "towVehicleModel": "F-250",
  "towVehicleTowRatingLbs": 14000,
  "hasBrakeController": true,
  "acknowledgedRequestIsNotConfirmation": true
}
```

Response:
```json
{
  "bookingId": "bk_123",
  "status": "requested",
  "message": "Request received. This is not yet a confirmed booking."
}
```

### POST /api/admin/bookings/:id/approve
Request:
```json
{
  "approvedRateCents": 27500,
  "approvedDeliveryFeeCents": 0,
  "approvedDepositCents": 50000,
  "paymentPath": "card", 
  "adminNotes": "Approved for pickup. Brake controller required."
}
```

Alternative values for `paymentPath`:
- `card`
- `ach`
- `business_check`

Behavior:
- `card` or `ach` -> set `approved_pending_payment`
- `business_check` -> set `approved_pending_check_clearance`

## 6. Payment integration guidance
### Recommended provider
Stripe for:
- payment links
- invoices
- ACH
- storing payment method
- authorization and capture (card holds for deposits, immediate charge for rental balance)

### Card-path Checkout behavior (implemented)
- **Rental / balance (Stripe Checkout, rental line item):** `payment_intent.capture_method = automatic` — the customer is charged as soon as Checkout completes successfully.
- **Security deposit (separate Stripe Checkout when configured):** `payment_intent.capture_method = manual` — only an **authorization (hold)** is placed on the card. No capture and no final charge until you explicitly call capture in Stripe (e.g. for damages) or the hold expires. Admin “release” uses **PaymentIntent cancel** to void the hold, not a Refund, while the PI is in `requires_capture`.
- **Legacy “combined” single Checkout (older metadata `deposit_in_checkout=1`):** one session may still treat rental + deposit as a single charge in Stripe; new bookings should use **separate** checkouts (rental automatic, deposit hold).

### Phase 1 implementation
Keep it simple:
- create Stripe invoice or payment link after approval
- create separate Checkout sessions: rental (immediate) and optional deposit (authorization only)
- store Stripe IDs on Payment/Deposit records
- use Stripe webhooks to mark rental as paid and deposit as **secured** when paid or when the deposit PI is in `requires_capture` (hold)

### Webhooks
At minimum handle:
- invoice.paid
- payment_intent.succeeded
- payment_intent.payment_failed
- charge.refunded
- checkout.session.completed (if used)
- payment_method.attached (optional)

## 7. Business check workflow
Implement admin-first manual steps:
- admin approves booking with `business_check` path
- system emails invoice + instructions
- booking status set to `approved_pending_check_clearance`
- admin marks check received
- admin marks check cleared
- deposit still must be card-backed and secured
- after agreement signed + deposit secured + check cleared, admin may confirm

Do not automate release based solely on "check received".

## 8. UI requirements
### Catalog page
Each product card should display:
- product name
- payload/capacity summary
- daily price
- deposit amount
- pickup/delivery support
- CTA button: `Request Booking`

### Product page
Display:
- rates
- deposit
- accepted payment methods
- short explanation that request is not confirmation
- pickup requirements
- delivery availability

### Request confirmation page
Show:
- request received message
- this is not a confirmed reservation
- next steps
- expected contact timing label can be generic, avoid hard promise in code copy

### Approved payment page
Show:
- booking summary
- rental dates
- product
- rate
- delivery fee if any
- deposit amount
- payment method selected
- agreement step
- pay now or invoice instructions

### Admin booking detail page
Show:
- request data
- approval controls
- agreement status
- payment status
- deposit status
- event timeline
- operational notes

## 9. Validation rules
- endAt must be after startAt
- delivery address required when fulfillmentMethod = delivery
- tow vehicle fields required when fulfillmentMethod = pickup
- business_check allowed only when companyName is present
- checkout disallowed until payment + deposit + agreement complete
- deposit amount must be positive
- approved rate must be non-negative
- request submission must not create a confirmed booking

## 10. Security/audit requirements
- write BookingEvent for every admin status change
- log payment and deposit state transitions
- store agreement version used
- store signer metadata
- protect admin routes
- validate Stripe webhook signatures
- never trust client-calculated totals

## 11. Suggested rollout flags
Use feature flags:
- `bookingApprovalFlow`
- `stripePayments`
- `achPayments`
- `contractorCheckWorkflow`
- `depositAuthorizationFlow`
- `digitalAgreementFlow`

## 12. Seed/default pricing and deposits
```json
[
  {
    "slug": "14k-dump-trailer-16",
    "dailyRateCents": 16000,
    "weekendRateCents": 36000,
    "weeklyRateCents": 105000,
    "defaultDepositCents": 75000
  },
  {
    "slug": "7k-dump-trailer-10",
    "dailyRateCents": 11000,
    "weekendRateCents": 25000,
    "weeklyRateCents": 75000,
    "defaultDepositCents": 50000
  },
  {
    "slug": "7k-dump-trailer-12",
    "dailyRateCents": 12000,
    "weekendRateCents": 27500,
    "weeklyRateCents": 80000,
    "defaultDepositCents": 50000
  },
  {
    "slug": "18-plus-2-car-hauler",
    "dailyRateCents": 10000,
    "weekendRateCents": 22500,
    "weeklyRateCents": 70000,
    "defaultDepositCents": 50000
  }
]
```
