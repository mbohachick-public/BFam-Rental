# Functional Requirements

## FR-1 Booking request flow remains request-first
The customer-facing item/request flow must remain unchanged in principle:
- customer requests
- admin approves
- payment is requested after approval

## FR-2 Quote remains booking-specific
The application must continue to calculate and display quote values based on:
- selected trailer/item
- selected rental dates
- computed number of days
- subtotal
- sales tax
- rental total
- deposit amount

## FR-3 Approved bookings can generate Stripe checkout
When a booking is in `approved_pending_payment`, an admin must be able to generate a unique Stripe Checkout Session for that booking.

## FR-4 Checkout session must use booking-specific total
The Stripe Checkout Session must reflect the booking-specific rental total, including tax if tax is already calculated in-app and intended to be collected as part of the rental payment.

## FR-5 Deposit remains separate in Phase 1
The deposit shown in the quote must not be automatically collected through the same Stripe Checkout Session in Phase 1 unless explicitly configured later.
The existing manual `Mark deposit secured` flow remains active.

## FR-6 Booking must store Stripe references
Each booking must be able to store:
- Stripe checkout URL
- Stripe session ID
- rental payment status
- payment timestamp, if available

## FR-7 Payment success redirect
After a successful Stripe payment, the customer must be redirected back to the application to a payment success page.

## FR-8 Payment cancel redirect
If the customer cancels Stripe checkout, they must be returned to an appropriate booking or item page without altering payment state.

## FR-9 Webhook updates payment status
The application must expose a Stripe webhook endpoint that updates the booking when payment succeeds.

## FR-10 Idempotent webhook handling
Webhook processing must be idempotent so duplicate Stripe webhook deliveries do not corrupt or duplicate booking state changes.

## FR-11 Admin can see payment state
The admin booking view must clearly show:
- rental paid yes/no
- deposit secured yes/no
- agreement signed yes/no

## FR-12 Admin can generate/send payment link
The admin must be able to generate a payment link from the booking record and retrieve/copy it for delivery to the customer.

## FR-13 Existing confirmation gate remains
A booking must not be considered ready for final confirmation until:
- rental paid = yes
- deposit secured = yes
- agreement signed = yes

## FR-14 Repeat contractor field remains informational
The `Repeat contractor / account with us` field should remain informational in Phase 1 and must not bypass payment, deposit, or agreement requirements.

## FR-15 Payment preference field remains non-authoritative
The `Payment preference` field may remain visible and stored, but Stripe Checkout should become the actual rental payment method for card-based online payment in Phase 1.

## FR-16 Booking approval must not auto-create charge unless explicitly triggered
Approving a booking must not immediately charge the customer.
The charge flow begins only after creating the Checkout Session and sending the payment URL.

## FR-17 Booking-specific multi-day rentals supported
A 2-day, 3-day, or N-day booking must create the correct Stripe Checkout amount from the computed quote rather than using a static reusable link.

## FR-18 Auditability
The app must preserve enough information to reconstruct:
- quoted amount
- Stripe session created
- webhook received
- payment marked paid
for each booking.

## FR-19 Manual recovery path
If webhook sync fails, the admin must still be able to inspect Stripe session details and manually reconcile the booking payment state.

## FR-20 Test mode support
The implementation must work cleanly in Stripe sandbox/test mode before live rollout.
