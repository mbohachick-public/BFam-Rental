# Dynamic Stripe payments (Phase 1)

Product and technical specs live in **`bohachick_cursor_dynamic_payments/`** (from `assets/bohachick-cursor-dynamic-payments-bundle.zip`).

## What was implemented

- **SQL:** `Specs/supabase-migration-stripe-checkout-phase1.sql` — adds `stripe_checkout_*`, `rental_payment_status`, and `stripe_webhook_events` (idempotent webhook dedup). **`Specs/supabase-migration-stripe-deposit-refund.sql`** — `stripe_deposit_captured_cents`, `deposit_refunded_at`, `stripe_deposit_refund_id` for partial deposit refunds.
- **API:** `POST /admin/booking-requests/{id}/stripe-checkout-session` (admin JWT) creates Checkout (rental + optional deposit per `STRIPE_CHECKOUT_INCLUDE_DEPOSIT`). `POST /admin/booking-requests/{id}/refund-stripe-deposit` issues a **partial Stripe refund** for the captured deposit only. `POST /stripe/webhook` … `GET /booking-requests/{id}/payment-status` …
- **SPA:** Admin **Generate payment link**, **Refund deposit (Stripe)** when a combined-checkout deposit was captured; customer **`/payment-success?booking_id=`**.

## Env

See `backend/.env.example`: **`STRIPE_SECRET_KEY`**, **`STRIPE_WEBHOOK_SECRET`**, optional **`APP_BASE_URL`**, optional **`STRIPE_CHECKOUT_INCLUDE_DEPOSIT`**.

Run the Stripe SQL migrations in Supabase (both files above, in order) before using deposit refund in production.
