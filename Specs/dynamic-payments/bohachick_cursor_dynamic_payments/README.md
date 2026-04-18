# Cursor Handoff: Dynamic Stripe Checkout for Bohachick Rentals

This bundle is tailored to the current flow shown in the provided screenshots:

- Item detail page with availability calendar and request form
- Quote block rendered inline after "Get quote"
- Admin booking requests list with statuses:
  - `requested`
  - `approved_pending_payment`
- Existing manual admin controls:
  - Approve / Decline
  - Mark rental paid
  - Mark deposit secured
  - Mark agreement signed

## Goal

Integrate Stripe into the existing booking workflow without redesigning the UX.

The implementation should:

- Preserve the current request-first flow
- Replace static/manual payment-link handling for variable bookings
- Support multi-day bookings
- Support booking-specific totals
- Generate a Stripe Checkout Session per approved booking
- Sync payment status back into the app via webhook
- Keep deposit handling manual in Phase 1

## Files in this bundle

1. `01-implementation-plan.md`
2. `02-functional-requirements.md`
3. `03-technical-requirements.md`
4. `04-test-plan.md`

## Implementation summary

### Current flow
1. Customer opens trailer detail page
2. Customer selects dates and enters details
3. Customer clicks `Get quote`
4. App shows quote:
   - Days
   - Rental subtotal
   - Sales tax
   - Rental total with tax
   - Deposit
5. Customer clicks `Submit request`
6. Admin reviews booking request
7. Admin clicks `Approve`
8. Booking moves to `approved_pending_payment`

### New flow
After admin approval:
1. App generates a unique Stripe Checkout Session for that booking
2. Checkout URL is stored on the booking
3. Admin can copy/send the payment link
4. Customer pays via Stripe-hosted checkout
5. Stripe webhook marks rental payment as paid
6. Admin sees updated payment state in booking admin

### Phase 1 boundary
Phase 1 includes:
- Rental payment via Stripe Checkout Session
- Webhook-driven payment sync
- Manual deposit handling remains in place

Phase 1 excludes:
- Stripe-held deposit auth/capture
- Automatic deposit release
- Full customer portal
- ACH-specific branching
- Refactors to the quote UI beyond minimal integration hooks

## Notes for Cursor

Cursor should implement the smallest diff that:
- preserves existing layout
- uses the current quote + request flow
- uses the current admin booking list
- minimizes schema and UI churn
- adds strong observability/logging around Stripe session creation and webhook handling
