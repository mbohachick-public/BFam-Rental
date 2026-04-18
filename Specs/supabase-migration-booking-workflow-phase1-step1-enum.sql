-- =============================================================================
-- Phase 1 — STEP 1 OF 2: Add new booking_request_status enum labels ONLY
-- =============================================================================
-- PostgreSQL requires new enum values to be COMMITTED before they can appear
-- in UPDATE/CAST/defaults in a later statement. Supabase runs each editor
-- execution as one transaction, so this file must run ALONE first.
--
-- Run this entire script once in Supabase SQL Editor → Run. Wait for success.
-- Then run: supabase-migration-booking-workflow-phase1-step2-schema.sql
-- =============================================================================

ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'requested';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'under_review';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'approved_pending_payment';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'approved_pending_check_clearance';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'confirmed';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'ready_for_pickup';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'checked_out';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'returned_pending_inspection';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'completed';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'completed_with_charges';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'cancelled';
ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'declined';
