-- Independent logistics: delivery to site + pickup from site (separate fees).
-- Run in Supabase SQL editor; then NOTIFY pgrst, 'reload schema'; if needed.

alter table public.booking_requests
  add column if not exists pickup_from_site_requested boolean not null default false;

alter table public.booking_requests
  add column if not exists pickup_fee numeric not null default 0;

alter table public.booking_requests
  add column if not exists pickup_distance_miles numeric;

comment on column public.booking_requests.delivery_address is
  'Job site address when customer requests delivery to site and/or pickup from site after rental.';

comment on column public.booking_requests.pickup_from_site_requested is
  'Customer requested owner pick up the trailer from the job site after the rental.';

comment on column public.booking_requests.pickup_fee is
  'Estimated one-way fee for pickup-from-site leg (taxed with rental subtotal).';

comment on column public.booking_requests.pickup_distance_miles is
  'Road distance for pickup leg (typically depot→job site miles, same as delivery).';
