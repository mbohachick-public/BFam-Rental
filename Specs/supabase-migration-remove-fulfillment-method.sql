-- =============================================================================
-- Remove booking_requests.fulfillment_method; tighten payment_method_preference
-- =============================================================================
-- Run in Supabase SQL Editor after backup. Safe to re-run (IF EXISTS / idempotent
-- constraint drop where possible).
--
-- 1) Customer preference no longer includes business_check (admin approve may still
--    use payment_path = business_check).
-- 2) Drops fulfillment_method (pickup/delivery); app assumes pickup-only.
-- =============================================================================

UPDATE public.booking_requests
SET payment_method_preference = 'ach'
WHERE payment_method_preference = 'business_check';

ALTER TABLE public.booking_requests DROP CONSTRAINT IF EXISTS booking_requests_payment_method_preference_check;

ALTER TABLE public.booking_requests
  ADD CONSTRAINT booking_requests_payment_method_preference_check
  CHECK (payment_method_preference IS NULL OR payment_method_preference IN ('card', 'ach'));

ALTER TABLE public.booking_requests DROP COLUMN IF EXISTS fulfillment_method;
