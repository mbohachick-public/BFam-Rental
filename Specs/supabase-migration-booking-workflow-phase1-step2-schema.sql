-- =============================================================================
-- Phase 1 — STEP 2 OF 2: Data backfill + columns + booking_events
-- =============================================================================
-- Prerequisite: step1 enum migration has already run and committed successfully.
-- Run in Supabase SQL Editor after backup.
-- Source: Specs/payments-handoff/*.md
--
-- Legacy DBs that already ran an older version of this file (with fulfillment_method
-- and business_check in payment_method_preference): also run once
--   supabase-migration-remove-fulfillment-method.sql
-- =============================================================================

-- Move legacy "pending" rows to "requested" (requires step1 committed).
UPDATE public.booking_requests
SET status = 'requested'::public.booking_request_status
WHERE status = 'pending'::public.booking_request_status;

-- --- items: delivery flag for catalog badges ---
ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS delivery_available boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN public.items.delivery_available IS 'When true, catalog/detail may show delivery available.';

-- --- booking_requests: workflow & payment prep columns ---
ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS company_name text,
  ADD COLUMN IF NOT EXISTS delivery_address text,
  ADD COLUMN IF NOT EXISTS payment_method_preference text
    CHECK (payment_method_preference IS NULL OR payment_method_preference IN ('card', 'ach')),
  ADD COLUMN IF NOT EXISTS is_repeat_contractor boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS tow_vehicle_year int,
  ADD COLUMN IF NOT EXISTS tow_vehicle_make text,
  ADD COLUMN IF NOT EXISTS tow_vehicle_model text,
  ADD COLUMN IF NOT EXISTS tow_vehicle_tow_rating_lbs int,
  ADD COLUMN IF NOT EXISTS has_brake_controller boolean,
  ADD COLUMN IF NOT EXISTS request_not_confirmed_ack boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS payment_path text
    CHECK (payment_path IS NULL OR payment_path IN ('card', 'ach', 'business_check')),
  ADD COLUMN IF NOT EXISTS approved_at timestamptz,
  ADD COLUMN IF NOT EXISTS rental_paid_at timestamptz,
  ADD COLUMN IF NOT EXISTS deposit_secured_at timestamptz,
  ADD COLUMN IF NOT EXISTS agreement_signed_at timestamptz,
  ADD COLUMN IF NOT EXISTS payment_collection_url text,
  ADD COLUMN IF NOT EXISTS stripe_invoice_id text;

COMMENT ON COLUMN public.booking_requests.request_not_confirmed_ack IS 'Customer checked: request is not a confirmed reservation.';
COMMENT ON COLUMN public.booking_requests.payment_path IS 'Admin-selected path when approving (card / ach / business_check).';
COMMENT ON COLUMN public.booking_requests.rental_paid_at IS 'Set when rental balance is collected (manual or webhook).';
COMMENT ON COLUMN public.booking_requests.deposit_secured_at IS 'Set when refundable deposit is secured.';
COMMENT ON COLUMN public.booking_requests.agreement_signed_at IS 'Set when rental agreement is signed.';

-- --- booking_events: audit trail ---
CREATE TABLE IF NOT EXISTS public.booking_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.booking_requests (id) ON DELETE CASCADE,
  event_type text NOT NULL,
  actor_type text NOT NULL CHECK (actor_type IN ('customer', 'admin', 'system')),
  actor_id text,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS booking_events_booking_id_idx ON public.booking_events (booking_id);

ALTER TABLE public.booking_events ENABLE ROW LEVEL SECURITY;
