-- Idempotent DDL for Supabase Postgres projects created before the two-step booking funnel.
-- Fixes: PGRST204 "Could not find the 'damage_waiver_daily_amount' column ... in the schema cache"
-- and related intake / verification fields.
--
-- Run in Supabase Dashboard → SQL → New query (as a role allowed to ALTER tables).
-- Safe to run more than once. Then wait a few seconds for PostgREST to refresh, or execute:
--   NOTIFY pgrst, 'reload schema';

-- -----------------------------------------------------------------------------
-- Enum value: booking moved to owner review after customer completes Step 2
-- -----------------------------------------------------------------------------
DO $migration$
BEGIN
  IF EXISTS (
      SELECT 1
      FROM pg_type t
      JOIN pg_namespace n ON n.oid = t.typnamespace
      WHERE n.nspname = 'public'
        AND t.typname = 'booking_request_status'
    )
    AND NOT EXISTS (
      SELECT 1
      FROM pg_enum e
      JOIN pg_type t ON e.enumtypid = t.oid
      JOIN pg_namespace n ON t.typnamespace = n.oid
      WHERE n.nspname = 'public'
        AND t.typname = 'booking_request_status'
        AND e.enumlabel = 'pending_approval'
    ) THEN
    ALTER TYPE public.booking_request_status ADD VALUE 'pending_approval';
  END IF;
END
$migration$;

-- -----------------------------------------------------------------------------
-- booking_requests: Step 2 + waiver snapshot columns (match Specs/supabase-setup.sql)
-- -----------------------------------------------------------------------------
ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS agreement_terms_acknowledged boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS vehicle_tow_capable_ack boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS damage_waiver_selected boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS damage_waiver_daily_amount numeric NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS damage_waiver_line_total numeric NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS rental_subtotal_snapshot numeric,
  ADD COLUMN IF NOT EXISTS stripe_saved_payment_method_id text,
  ADD COLUMN IF NOT EXISTS deposit_authorization_status text,
  ADD COLUMN IF NOT EXISTS verification_submitted_at timestamptz;

ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS request_approval_acknowledged boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS agreement_sign_intent_acknowledged boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.booking_requests.agreement_terms_acknowledged IS
  'Reserved; Step 2 does not imply signed terms. Prefer request_approval_acknowledged.';
COMMENT ON COLUMN public.booking_requests.request_approval_acknowledged IS
  'Step 2: customer confirmed request is subject to approval.';
COMMENT ON COLUMN public.booking_requests.agreement_sign_intent_acknowledged IS
  'Step 2 optional: intent to review/sign agreement if approved.';

UPDATE public.booking_requests
SET request_approval_acknowledged = true
WHERE verification_submitted_at IS NOT NULL
  AND request_approval_acknowledged IS NOT TRUE
  AND agreement_terms_acknowledged IS TRUE;

-- Help API gateway pick up new columns immediately (no-op if your pool ignores it).
NOTIFY pgrst, 'reload schema';
