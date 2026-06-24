-- Step 2 booking access token (hashed) + Stripe SetupIntent binding.
-- Run in Supabase SQL editor. Safe to re-run.

ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS step2_token_hash text;

ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS step2_token_expires_at timestamptz;

ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS stripe_setup_intent_id text;

COMMENT ON COLUMN public.booking_requests.step2_token_hash IS
  'SHA-256 hex of the Step 2 completion secret emailed to the customer.';

COMMENT ON COLUMN public.booking_requests.stripe_setup_intent_id IS
  'Latest Stripe SetupIntent created for this booking during Step 2 card collection.';

NOTIFY pgrst, 'reload schema';
