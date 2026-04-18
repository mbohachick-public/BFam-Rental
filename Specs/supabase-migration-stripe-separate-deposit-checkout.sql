-- =============================================================================
-- Separate Stripe Checkout for security deposit (rental + deposit = 2 sessions)
-- =============================================================================
-- Run after supabase-migration-stripe-checkout-phase1.sql and
-- supabase-migration-stripe-deposit-refund.sql (adds refund columns if needed).
--
-- Without this migration, the API fails when selecting stripe_deposit_checkout_url
-- (e.g. GET /booking-actions/{token}/complete, admin list, Stripe generate link flow).
-- =============================================================================

ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS stripe_deposit_checkout_session_id text,
  ADD COLUMN IF NOT EXISTS stripe_deposit_checkout_url text,
  ADD COLUMN IF NOT EXISTS stripe_deposit_checkout_created_at timestamptz,
  ADD COLUMN IF NOT EXISTS stripe_deposit_payment_intent_id text;

COMMENT ON COLUMN public.booking_requests.stripe_deposit_checkout_url IS
  'Stripe Checkout URL for the refundable security deposit only (separate PaymentIntent).';
COMMENT ON COLUMN public.booking_requests.stripe_deposit_payment_intent_id IS
  'PaymentIntent for the deposit Checkout; used for full deposit refunds.';

-- PostgREST caches table columns. Without a reload, PATCH/SELECT can fail with PGRST204
-- ("Could not find the 'stripe_deposit_checkout_*' column ... in the schema cache")
-- even after ALTER TABLE succeeds. Safe to run anytime.
NOTIFY pgrst, 'reload schema';
