# BFam Rentals Contract + E-Sign Integration Technical Spec

## Goal
Implement a contract-signing layer on top of the existing booking workflow.

Assume the current system already has:
- catalog pages
- product/trailer detail pages
- booking request submission
- admin review/approval
- no native payment checkout requirement yet

## Recommended Architecture
### Preferred approach
Use an internal signing flow rather than a third-party e-sign provider for MVP.

Why:
- faster integration into current site
- lower cost
- easier to bind to booking records and statuses
- enough for a single-signer rental agreement workflow

## Data Model

### bookings
Add fields if not present:
- `id`
- `booking_number`
- `customer_id` nullable
- `trailer_id`
- `status`
- `rental_start_at`
- `rental_end_at`
- `pickup_or_delivery`
- `delivery_address` nullable
- `base_rental_amount`
- `delivery_fee`
- `deposit_amount`
- `preferred_payment_method`
- `approved_payment_method`
- `admin_notes` nullable
- `approved_at` nullable
- `confirmed_at` nullable
- `cancelled_at` nullable
- `created_at`
- `updated_at`

### booking_documents
Stores executable contract artifacts.
- `id`
- `booking_id`
- `document_type` // RENTAL_AGREEMENT, DAMAGE_FEE_SCHEDULE, EXECUTED_PACKET
- `document_version`
- `title`
- `html_snapshot`
- `pdf_path` nullable
- `sha256_hash`
- `created_at`

### booking_signatures
Stores signature execution metadata.
- `id`
- `booking_id`
- `signer_name`
- `signer_email`
- `company_name` nullable
- `typed_signature`
- `signed_at`
- `ip_address` nullable
- `user_agent` nullable
- `agreement_version`
- `damage_schedule_version`
- `acknowledged_terms` JSON
- `signature_audit_json` JSON nullable
- `created_at`

### booking_action_tokens
Secure links for approval/signing/payment pages.
- `id`
- `booking_id`
- `token_hash`
- `action_type` // SIGN, PAY, VIEW
- `expires_at`
- `used_at` nullable
- `created_at`

### document_templates
Versioned source templates.
- `id`
- `document_type`
- `version`
- `title`
- `html_template`
- `is_active`
- `created_at`

## Template Strategy
Store the rental agreement and damage fee schedule as versioned HTML templates.

At time of approval:
1. render template with booking values
2. create immutable document snapshots
3. generate secure signing token
4. email the signing link

Do not render live templates directly at sign time without snapshotting.

## Required Routes / Pages
### Public-ish tokenized pages
- `GET /booking-actions/:token/sign`
- `POST /booking-actions/:token/sign`
- `GET /booking-actions/:token/payment`
- `GET /booking-actions/:token/complete`

### Admin pages
- `GET /admin/bookings/:id`
- `POST /admin/bookings/:id/approve`
- `POST /admin/bookings/:id/resend-signature`
- `POST /admin/bookings/:id/mark-payment-received`
- `POST /admin/bookings/:id/mark-check-cleared`
- `POST /admin/bookings/:id/mark-deposit-received`
- `POST /admin/bookings/:id/confirm`

## Signing Page Requirements
### Rendered content
The sign page must show:
- booking summary card
- rental agreement full text
- damage fee schedule full text
- required acknowledgments
- signature form

### Signature form fields
- full legal name
- company name optional
- email
- typed signature
- checkbox acknowledgments
- submit button

### Submit validations
Reject submission if:
- required acknowledgments not checked
- typed signature blank
- email does not match booking email unless admin override supported
- token expired or already used if one-time token

## PDF Generation
After successful signing:
1. generate a combined executed PDF packet
   - booking summary
   - rental agreement snapshot
   - damage fee schedule snapshot
   - signature details page
2. store file path on `booking_documents`
3. email PDF to customer
4. expose PDF to admin

Recommended implementation:
- render HTML to PDF server-side using existing stack tooling
- ensure page breaks are readable
- embed signature metadata on final page

## Status Transitions
### Approval
`PENDING_REVIEW` -> `APPROVED_AWAITING_SIGNATURE`

### Successful signature
If payment method is card or ACH:
`APPROVED_AWAITING_SIGNATURE` -> `SIGNED_AWAITING_PAYMENT`

If payment method is check:
`APPROVED_AWAITING_SIGNATURE` -> `SIGNED_AWAITING_CHECK_CLEARANCE`

### Payment received
Card/ACH:
`SIGNED_AWAITING_PAYMENT` -> `PAYMENT_RECEIVED_AWAITING_DEPOSIT` or `CONFIRMED`

### Check cleared
`SIGNED_AWAITING_CHECK_CLEARANCE` -> `CONFIRMED` only when required deposit condition is satisfied

### Booking changes after approval
If admin changes any binding term after packet generation but before signing, invalidate old token and regenerate documents.

If admin changes binding terms after signing, mark prior packet superseded and require re-sign.

## API Contract Sketch
### Approve booking
`POST /api/admin/bookings/:id/approve`

Request:
```json
{
  "trailerId": "tr_123",
  "rentalStartAt": "2026-04-20T09:00:00",
  "rentalEndAt": "2026-04-21T17:00:00",
  "baseRentalAmount": 16000,
  "deliveryFee": 0,
  "depositAmount": 75000,
  "approvedPaymentMethod": "card"
}
```

Effects:
- snapshot documents
- create signing token
- update booking status
- send approval email with signing link

### Submit signature
`POST /api/booking-actions/:token/sign`

Request:
```json
{
  "signerName": "Matt Bohachick",
  "companyName": "",
  "signerEmail": "name@example.com",
  "typedSignature": "Matt Bohachick",
  "acknowledgments": {
    "rentalAgreement": true,
    "damageFeeSchedule": true,
    "responsibilityForDamage": true,
    "paymentDepositRequirement": true
  }
}
```

Response:
```json
{
  "ok": true,
  "nextStatus": "SIGNED_AWAITING_PAYMENT",
  "nextUrl": "/booking-actions/abc123/payment"
}
```

## Security Requirements
- tokenized signing links must be long, random, and expire
- store token hashes, not raw tokens
- protect admin routes behind auth
- prevent signature replay
- log timestamp and IP if available
- immutable executed packet

## UX Requirements
- mobile-friendly sign page
- sticky booking summary on desktop is a plus
- clear success state after signing
- clear messaging that booking is not confirmed until payment/deposit conditions are met

## Suggested Email Events
- booking approved: sign now
- signature completed: next payment step
- payment received / check pending
- booking confirmed

## Edge Cases
- expired token
- customer opens old link after terms changed
- customer signs but payment fails
- admin manually confirms without payment by mistake
- same email used for multiple pending bookings

## Acceptance Requirements
- every confirmed booking must have an executed packet
- every executed packet must include both agreement and damage schedule text versions
- admin can re-send sign request without breaking history
- regenerated packets create new versions, not silent replacements
