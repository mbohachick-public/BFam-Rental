-- Trailer Match: separate delivery from recommendation + track delivery CTA.
-- Safe to re-run: uses IF EXISTS / IF NOT EXISTS patterns where applicable.
-- For databases created from the earlier trailer_match migration, normalizes cta_suggestion values.
-- -----------------------------------------------------------------------------

alter table public.trailer_match_requests
  drop column if exists delivery_preference;

-- Normalize legacy CTA values before tightening the check constraint
update public.trailer_match_requests
set cta_suggestion = 'ask_confirm'
where cta_suggestion = 'request_delivery';

alter table public.trailer_match_requests
  drop constraint if exists trailer_match_requests_cta_suggestion_check;

alter table public.trailer_match_requests
  add constraint trailer_match_requests_cta_suggestion_check
    check (cta_suggestion in ('book', 'ask_confirm'));

alter table public.trailer_match_requests
  add column if not exists delivery_cta_shown boolean not null default false;

alter table public.trailer_match_requests
  add column if not exists delivery_cta_reason text;

alter table public.trailer_match_requests
  add column if not exists delivery_quote_clicked boolean not null default false;

comment on column public.trailer_match_requests.delivery_cta_shown is
  'True when the result screen should emphasize the delivery-quote CTA (towing uncertainty, heavy load, etc.).';

comment on column public.trailer_match_requests.delivery_cta_reason is
  'Short internal note on why delivery CTA was emphasized (optional).';

comment on column public.trailer_match_requests.delivery_quote_clicked is
  'Customer tapped Request a delivery quote for this match id.';

notify pgrst, 'reload schema';
