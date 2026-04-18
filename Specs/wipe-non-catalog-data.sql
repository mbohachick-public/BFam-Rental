-- =============================================================================
-- Wipe operational data; keep catalog (items, item_images, item_day_status)
-- =============================================================================
-- Run in the Supabase SQL Editor on a project you have backed up.
--
-- Removes:
--   - public.stripe_webhook_events (Stripe idempotency / audit rows)
--   - public.booking_requests and, via ON DELETE CASCADE:
--       booking_events, booking_documents, booking_signatures, booking_action_tokens
--
-- Preserves:
--   - public.items, public.item_images, public.item_day_status
--
-- Does NOT delete objects in Storage (booking-documents, etc.). For file cleanup
-- plus the same DB wipe, use:
--   cd backend && python3 scripts/wipe_non_catalog_data.py --yes
-- =============================================================================

begin;

truncate table public.stripe_webhook_events;

delete from public.booking_requests;

commit;
