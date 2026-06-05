-- Trailer Match Assistant — persisted recommendation attempts (run in Supabase SQL editor).
-- Trailer sizing is independent of delivery; delivery CTA is tracked post-recommendation only.
-- -----------------------------------------------------------------------------
create table if not exists public.trailer_match_requests (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  year int not null,
  make text not null,
  model text not null,
  trim_or_engine text,
  tow_package text not null
    check (tow_package in ('yes', 'no', 'unknown')),
  brake_controller text not null
    check (brake_controller in ('yes', 'no', 'unknown')),
  towing_experience text not null
    check (towing_experience in ('first_time', 'some', 'experienced')),
  load_type text not null
    check (
      load_type in (
        'mulch',
        'topsoil',
        'gravel',
        'brush',
        'construction',
        'household',
        'other'
      )
    ),
  estimated_amount text not null
    check (
      estimated_amount in ('y1', 'y2', 'y3', 'y4', 'y5plus', 'unsure')
    ),
  estimated_weight_min int,
  estimated_weight_max int,
  recommended_trailer_type text not null
    check (recommended_trailer_type in ('10_7k', '12_10k', '12_12k')),
  alternative_trailer_type text not null
    check (alternative_trailer_type in ('10_7k', '12_10k', '12_12k')),
  warnings jsonb not null default '[]'::jsonb,
  reasons jsonb not null default '[]'::jsonb,
  confidence text not null check (confidence in ('low', 'medium', 'high')),
  cta_suggestion text not null
    check (cta_suggestion in ('book', 'ask_confirm')),
  delivery_cta_shown boolean not null default false,
  delivery_cta_reason text,
  delivery_quote_clicked boolean not null default false,
  converted_to_booking boolean not null default false,
  booking_id uuid references public.booking_requests (id) on delete set null,
  session_id text,
  customer_auth0_sub text,
  recommended_catalog_item_id uuid references public.items (id) on delete set null
);

create index if not exists trailer_match_requests_created_at_idx
  on public.trailer_match_requests (created_at desc);

create index if not exists trailer_match_requests_converted_idx
  on public.trailer_match_requests (converted_to_booking);

comment on table public.trailer_match_requests is
  'Trailer Match Assistant submissions for market research; not a safety certification.';

comment on column public.trailer_match_requests.delivery_cta_shown is
  'True when the result screen should emphasize the delivery-quote CTA.';

comment on column public.trailer_match_requests.delivery_quote_clicked is
  'Customer requested a delivery quote from the match result screen.';

alter table public.trailer_match_requests enable row level security;

notify pgrst, 'reload schema';
