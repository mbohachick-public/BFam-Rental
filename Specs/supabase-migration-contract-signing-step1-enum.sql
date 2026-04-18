-- =============================================================================
-- Contract signing — STEP 1 OF 2: enum label only (commit before step 2)
-- =============================================================================

ALTER TYPE public.booking_request_status ADD VALUE IF NOT EXISTS 'approved_awaiting_signature';
