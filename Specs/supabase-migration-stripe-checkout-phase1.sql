-- =============================================================================
-- Phase 1 — Stripe Checkout (rental only; deposit stays manual)
-- =============================================================================
-- Run in Supabase SQL Editor after backup. Idempotent where possible.
-- See Specs/dynamic-payments/bohachick_cursor_dynamic_payments/README.md
-- =============================================================================

ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS stripe_checkout_session_id text,
  ADD COLUMN IF NOT EXISTS stripe_checkout_url text,
  ADD COLUMN IF NOT EXISTS stripe_payment_intent_id text,
  ADD COLUMN IF NOT EXISTS rental_payment_status text NOT NULL DEFAULT 'unpaid'
    CHECK (rental_payment_status IN ('unpaid', 'paid', 'failed', 'refunded')),
  ADD COLUMN IF NOT EXISTS stripe_checkout_created_at timestamptz;

COMMENT ON COLUMN public.booking_requests.rental_payment_status IS 'Rental line: unpaid until Stripe webhook or admin mark.';
COMMENT ON COLUMN public.booking_requests.stripe_checkout_url IS 'Last generated Stripe Checkout URL (card path).';

CREATE TABLE IF NOT EXISTS public.stripe_webhook_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  stripe_event_id text NOT NULL UNIQUE,
  event_type text NOT NULL,
  booking_id uuid REFERENCES public.booking_requests (id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS stripe_webhook_events_booking_id_idx
  ON public.stripe_webhook_events (booking_id);

ALTER TABLE public.stripe_webhook_events ENABLE ROW LEVEL SECURITY;

-- Backfill: existing paid rentals
UPDATE public.booking_requests
SET rental_payment_status = 'paid'
WHERE rental_paid_at IS NOT NULL AND rental_payment_status = 'unpaid';
