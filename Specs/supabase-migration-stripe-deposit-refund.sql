-- =============================================================================
-- Stripe deposit partial refund (admin-triggered)
-- =============================================================================
-- Run after supabase-migration-stripe-checkout-phase1.sql. Idempotent.
-- =============================================================================

ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS stripe_deposit_captured_cents integer,
  ADD COLUMN IF NOT EXISTS deposit_refunded_at timestamptz,
  ADD COLUMN IF NOT EXISTS stripe_deposit_refund_id text;

COMMENT ON COLUMN public.booking_requests.stripe_deposit_captured_cents IS
  'Deposit portion of combined Stripe Checkout (cents); set by webhook when deposit_in_checkout.';
COMMENT ON COLUMN public.booking_requests.deposit_refunded_at IS
  'When admin refunded the deposit via Stripe partial refund.';
COMMENT ON COLUMN public.booking_requests.stripe_deposit_refund_id IS
  'Stripe Refund id (re_...) for the deposit partial refund.';
