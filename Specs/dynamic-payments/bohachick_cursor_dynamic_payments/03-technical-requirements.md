# Technical Requirements

## TR-1 Environment variables
Add environment variables for Stripe:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `APP_BASE_URL`

Optional:
- `STRIPE_PUBLISHABLE_KEY` if needed later
- `STRIPE_API_VERSION` if pinned in implementation

## TR-2 Booking schema changes
Add fields to the booking model or persistence layer.

Minimum suggested fields:
- `stripe_session_id: string | null`
- `stripe_checkout_url: string | null`
- `stripe_payment_intent_id: string | null`
- `rental_payment_status: 'unpaid' | 'paid' | 'failed' | 'refunded'`
- `rental_paid_at: datetime | null`
- `stripe_checkout_created_at: datetime | null`

If not already present:
- `deposit_secured: boolean`
- `agreement_signed: boolean`

## TR-3 Stripe SDK integration
Use the official Stripe server SDK from backend code only.
Do not create Checkout Sessions from the client.

## TR-4 Admin-only session generation endpoint
Add an authenticated admin-only endpoint such as:

`POST /api/admin/bookings/:bookingId/stripe-checkout-session`

Behavior:
1. Load booking
2. Validate booking status is `approved_pending_payment`
3. Validate quote totals are present
4. Create a Stripe Checkout Session
5. Save session identifiers and URL to booking
6. Return session metadata and URL

## TR-5 Checkout session contents
Create Checkout Sessions with:
- `mode = 'payment'`
- `customer_email = booking.email` when available
- line item for booking rental amount
- success URL pointing to app success page
- cancel URL pointing back to item/booking page
- metadata including `booking_id`

Recommended metadata:
- `booking_id`
- `booking_status`
- `item_id`
- `days`
- `customer_email`

## TR-6 Amount source of truth
The session amount must come from the application’s computed booking quote, not from client-supplied values.
The backend must not trust any amount posted from the browser.

## TR-7 Webhook endpoint
Add a public Stripe webhook endpoint such as:

`POST /api/stripe/webhook`

The endpoint must:
- read raw request body
- verify Stripe signature with `STRIPE_WEBHOOK_SECRET`
- parse supported events
- respond quickly and safely

## TR-8 Supported webhook events
At minimum handle:
- `checkout.session.completed`

Recommended additional handling:
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `payment_intent.payment_failed`

## TR-9 Webhook booking update behavior
On successful payment:
- find booking by `metadata.booking_id`
- set `rental_payment_status = 'paid'`
- set `rental_paid_at`
- persist `stripe_payment_intent_id` if present

On failed/async failure:
- optionally mark `rental_payment_status = 'failed'`
- never mark paid

## TR-10 Idempotency
Webhook processing must be idempotent.
Use one or more of:
- event ID tracking table
- conditional updates
- idempotent booking status writes

## TR-11 Admin UI changes
In the booking admin UI:
- show rental payment state from persisted Stripe status
- show button to generate payment link if none exists
- show button to copy payment link if one exists
- optionally show button to regenerate link with confirmation if allowed

## TR-12 Regeneration rules
If regenerating sessions is allowed:
- old sessions must not overwrite completed payments
- regeneration should be blocked or confirmed if booking is already paid
- only one active intended checkout URL should be presented in admin UI

## TR-13 Success page
Add route such as:
- `/payment-success`
or
- `/bookings/:bookingId/payment-success`

This page should:
- show non-authoritative success messaging
- fetch booking state from backend if needed
- avoid trusting URL-only success
- remind user of next steps

## TR-14 Cancel path
Add return route for canceled checkout.
The app must not mark a booking paid on cancel redirect alone.

## TR-15 Logging
Add structured logging for:
- checkout session creation
- webhook receipt
- webhook verification failure
- booking update success/failure
- duplicate event handling

## TR-16 Security
- Stripe secret key must remain server-only
- webhook signature verification is required
- admin endpoints require admin auth
- booking payment amounts must be computed server-side

## TR-17 Backward compatibility
Existing manual admin controls should remain functional during rollout, but `Mark rental paid` should either:
- be restricted to manual recovery use, or
- clearly indicate when Stripe synced payment already

## TR-18 Suggested line item structure
Use a single line item for Phase 1:

Name example:
`7K Dump Trailer (12') rental — 2 days`

Amount:
- use app-computed rental total including tax if collected in-app

Alternative line-item decomposition can be deferred.

## TR-19 Example pseudocode

```ts
const session = await stripe.checkout.sessions.create({
  mode: "payment",
  customer_email: booking.email,
  line_items: [
    {
      price_data: {
        currency: "usd",
        product_data: {
          name: `${booking.item_name} rental — ${booking.days} days`,
        },
        unit_amount: Math.round(booking.rental_total_with_tax * 100),
      },
      quantity: 1,
    },
  ],
  success_url: `${APP_BASE_URL}/payment-success?booking_id=${booking.id}`,
  cancel_url: `${APP_BASE_URL}/items/${booking.item_id}`,
  metadata: {
    booking_id: booking.id,
    item_id: booking.item_id,
    days: String(booking.days),
    customer_email: booking.email ?? "",
  },
});
```

## TR-20 Example webhook pseudocode

```ts
if (event.type === "checkout.session.completed") {
  const session = event.data.object;
  const bookingId = session.metadata?.booking_id;
  if (!bookingId) return;

  await markBookingRentalPaid({
    bookingId,
    stripeSessionId: session.id,
    paymentIntentId: session.payment_intent ?? null,
    paidAt: new Date(),
  });
}
```
