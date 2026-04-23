-- =============================================================================
-- BFam Rental — Supabase schema (single script)
-- =============================================================================
-- Run in the Supabase SQL Editor on a new project, or when you intentionally
-- want to reset application tables (see PART 0).
--
-- PART 0 drops all BFam application tables and enum types, then recreates the
-- full current schema (Stripe, contract signing, delivery, booking workflow).
-- This is destructive to booking/catalog data in those tables.
--
-- After PART 1, create Storage buckets (PART 2). Optional demo seed / backfill
-- in PART 3–4. PART 5 is an optional data-only wipe that keeps catalog tables.
--
-- The FastAPI backend uses SUPABASE_SERVICE_ROLE_KEY (bypasses RLS). RLS is
-- enabled on all app tables; anon/authenticated have no policies.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- PART 0 — DROP (destructive; safe on empty DB)
-- -----------------------------------------------------------------------------

drop table if exists public.stripe_webhook_events cascade;
drop table if exists public.booking_events cascade;
drop table if exists public.booking_documents cascade;
drop table if exists public.booking_signatures cascade;
drop table if exists public.booking_action_tokens cascade;
drop table if exists public.booking_requests cascade;
drop table if exists public.item_day_status cascade;
drop table if exists public.item_images cascade;
drop table if exists public.items cascade;
drop table if exists public.delivery_settings cascade;

drop type if exists public.booking_request_status cascade;
drop type if exists public.day_status cascade;


-- -----------------------------------------------------------------------------
-- PART 1 — CREATE SCHEMA
-- -----------------------------------------------------------------------------

create extension if not exists "pgcrypto";

create type public.day_status as enum (
  'out_for_use',
  'booked',
  'open_for_booking',
  'readying_for_use',
  'pending_request'
);

create type public.booking_request_status as enum (
  'pending',
  'accepted',
  'rejected',
  'requested',
  'under_review',
  'approved_awaiting_signature',
  'approved_pending_payment',
  'approved_pending_check_clearance',
  'confirmed',
  'ready_for_pickup',
  'checked_out',
  'returned_pending_inspection',
  'completed',
  'completed_with_charges',
  'cancelled',
  'declined'
);

create table public.items (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text not null default '',
  category text not null default 'general',
  cost_per_day numeric(10, 2) not null check (cost_per_day >= 0),
  minimum_day_rental int not null default 1 check (minimum_day_rental >= 1),
  deposit_amount numeric(10, 2) not null default 0 check (deposit_amount >= 0),
  user_requirements text not null default '',
  towable boolean not null default false,
  delivery_available boolean not null default true,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

comment on column public.items.delivery_available is
  'When true, catalog/detail may show delivery available.';
comment on column public.items.active is
  'When false, item is hidden from public catalog and customer booking flows; admins still see it.';

create table public.item_images (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.items (id) on delete cascade,
  url text not null,
  sort_order int not null default 0
);

create index item_images_item_id_idx on public.item_images (item_id);

create table public.item_day_status (
  item_id uuid not null references public.items (id) on delete cascade,
  day date not null,
  status public.day_status not null,
  primary key (item_id, day)
);

create index item_day_status_item_day_idx on public.item_day_status (item_id, day);

create table public.delivery_settings (
  id smallint primary key default 1 check (id = 1),
  enabled boolean not null default false,
  origin_address text not null default '',
  price_per_mile numeric not null default 0,
  minimum_fee numeric not null default 0,
  free_miles numeric not null default 0,
  max_delivery_miles numeric,
  updated_at timestamptz not null default now()
);

comment on table public.delivery_settings is
  'Singleton (id=1): yard/origin + per-mile delivery pricing.';

insert into public.delivery_settings (id) values (1)
on conflict (id) do nothing;

create table public.booking_requests (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.items (id) on delete cascade,
  start_date date not null,
  end_date date not null,
  status public.booking_request_status not null default 'requested',
  customer_email text,
  customer_phone text,
  customer_first_name text,
  customer_last_name text,
  customer_address text,
  customer_auth0_sub text,
  notes text,
  decline_reason text,
  base_amount numeric(10, 2),
  discount_percent numeric(5, 2),
  discounted_subtotal numeric(10, 2),
  deposit_amount numeric(10, 2),
  sales_tax_rate_percent numeric(8, 4),
  sales_tax_amount numeric(10, 2),
  rental_total_with_tax numeric(10, 2),
  sales_tax_source text,
  drivers_license_path text,
  license_plate_path text,
  created_at timestamptz not null default now(),
  company_name text,
  delivery_address text,
  payment_method_preference text,
  is_repeat_contractor boolean not null default false,
  tow_vehicle_year int,
  tow_vehicle_make text,
  tow_vehicle_model text,
  tow_vehicle_tow_rating_lbs int,
  has_brake_controller boolean,
  request_not_confirmed_ack boolean not null default false,
  payment_path text,
  approved_at timestamptz,
  rental_paid_at timestamptz,
  deposit_secured_at timestamptz,
  agreement_signed_at timestamptz,
  payment_collection_url text,
  stripe_invoice_id text,
  stripe_checkout_session_id text,
  stripe_checkout_url text,
  stripe_payment_intent_id text,
  rental_payment_status text not null default 'unpaid',
  stripe_checkout_created_at timestamptz,
  stripe_deposit_checkout_session_id text,
  stripe_deposit_checkout_url text,
  stripe_deposit_checkout_created_at timestamptz,
  stripe_deposit_payment_intent_id text,
  stripe_deposit_captured_cents int,
  deposit_refunded_at timestamptz,
  stripe_deposit_refund_id text,
  delivery_requested boolean not null default false,
  delivery_fee numeric not null default 0,
  delivery_distance_miles numeric,
  check (end_date >= start_date),
  constraint booking_requests_payment_method_preference_check
    check (payment_method_preference is null or payment_method_preference in ('card', 'ach')),
  constraint booking_requests_payment_path_check
    check (payment_path is null or payment_path in ('card', 'ach', 'business_check')),
  constraint booking_requests_rental_payment_status_check
    check (rental_payment_status in ('unpaid', 'paid', 'failed', 'refunded'))
);

create index booking_requests_item_id_idx on public.booking_requests (item_id);
create index booking_requests_status_idx on public.booking_requests (status);
create index booking_requests_customer_auth0_sub_idx on public.booking_requests (customer_auth0_sub);

comment on column public.booking_requests.customer_auth0_sub is
  'Auth0 JWT sub when booking was created with customer Auth0 enabled';
comment on column public.booking_requests.sales_tax_rate_percent is
  'Combined sales tax % applied to rental subtotal at booking time';
comment on column public.booking_requests.sales_tax_amount is
  'Tax dollars on rental subtotal only (not deposit)';
comment on column public.booking_requests.rental_total_with_tax is
  'discounted_subtotal + sales_tax_amount';
comment on column public.booking_requests.sales_tax_source is
  'How the rate was resolved (e.g. GET URL or fallback env)';
comment on column public.booking_requests.request_not_confirmed_ack is
  'Customer checked: request is not a confirmed reservation.';
comment on column public.booking_requests.payment_path is
  'Admin-selected path when approving (card / ach / business_check).';
comment on column public.booking_requests.rental_paid_at is
  'Set when rental balance is collected (manual or webhook).';
comment on column public.booking_requests.deposit_secured_at is
  'Set when refundable deposit is secured.';
comment on column public.booking_requests.agreement_signed_at is
  'Set when rental agreement is signed.';
comment on column public.booking_requests.rental_payment_status is
  'Rental line: unpaid until Stripe webhook or admin mark.';
comment on column public.booking_requests.stripe_checkout_url is
  'Last generated Stripe Checkout URL (card path).';
comment on column public.booking_requests.stripe_deposit_checkout_url is
  'Stripe Checkout URL for the refundable security deposit only (separate PaymentIntent).';
comment on column public.booking_requests.stripe_deposit_payment_intent_id is
  'PaymentIntent for the deposit Checkout; used for full deposit refunds.';
comment on column public.booking_requests.stripe_deposit_captured_cents is
  'Deposit portion of combined Stripe Checkout (cents); set by webhook when deposit_in_checkout.';
comment on column public.booking_requests.deposit_refunded_at is
  'When admin refunded the deposit via Stripe partial refund.';
comment on column public.booking_requests.stripe_deposit_refund_id is
  'Stripe Refund id (re_...) for the deposit partial refund.';
comment on column public.booking_requests.delivery_requested is
  'Customer requested delivery to delivery_address.';
comment on column public.booking_requests.delivery_fee is
  'Computed delivery charge (taxed with rental subtotal).';
comment on column public.booking_requests.delivery_distance_miles is
  'Road distance origin→delivery from routing API.';

create table public.booking_events (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references public.booking_requests (id) on delete cascade,
  event_type text not null,
  actor_type text not null check (actor_type in ('customer', 'admin', 'system')),
  actor_id text,
  metadata jsonb,
  created_at timestamptz not null default now()
);

create index booking_events_booking_id_idx on public.booking_events (booking_id);

create table public.booking_documents (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references public.booking_requests (id) on delete cascade,
  document_type text not null
    check (document_type in ('RENTAL_AGREEMENT', 'DAMAGE_FEE_SCHEDULE', 'EXECUTED_PACKET')),
  document_version text not null default '1',
  title text not null,
  html_snapshot text,
  pdf_path text,
  sha256_hash text not null,
  created_at timestamptz not null default now()
);

create index booking_documents_booking_id_idx on public.booking_documents (booking_id);

create table public.booking_signatures (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references public.booking_requests (id) on delete cascade,
  signer_name text not null,
  signer_email text not null,
  company_name text,
  typed_signature text not null,
  signed_at timestamptz not null default now(),
  ip_address text,
  user_agent text,
  agreement_version text not null default '1',
  damage_schedule_version text not null default '1',
  acknowledged_terms jsonb not null default '{}'::jsonb,
  signature_audit_json jsonb,
  created_at timestamptz not null default now()
);

create unique index booking_signatures_one_per_booking on public.booking_signatures (booking_id);

create table public.booking_action_tokens (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references public.booking_requests (id) on delete cascade,
  token_hash text not null,
  action_type text not null check (action_type in ('SIGN', 'PAY', 'VIEW')),
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);

create unique index booking_action_tokens_token_hash_uidx on public.booking_action_tokens (token_hash);
create index booking_action_tokens_booking_id_idx on public.booking_action_tokens (booking_id);

create table public.stripe_webhook_events (
  id uuid primary key default gen_random_uuid(),
  stripe_event_id text not null unique,
  event_type text not null,
  booking_id uuid references public.booking_requests (id) on delete set null,
  created_at timestamptz not null default now()
);

create index stripe_webhook_events_booking_id_idx on public.stripe_webhook_events (booking_id);

alter table public.items enable row level security;
alter table public.item_images enable row level security;
alter table public.item_day_status enable row level security;
alter table public.delivery_settings enable row level security;
alter table public.booking_requests enable row level security;
alter table public.booking_events enable row level security;
alter table public.booking_documents enable row level security;
alter table public.booking_signatures enable row level security;
alter table public.booking_action_tokens enable row level security;
alter table public.stripe_webhook_events enable row level security;

-- PostgREST schema cache (safe if PostgREST is not listening)
notify pgrst, 'reload schema';


-- -----------------------------------------------------------------------------
-- PART 2 — STORAGE (create in Dashboard)
-- -----------------------------------------------------------------------------
--
-- booking-documents — private bucket (BOOKING_DOCUMENTS_STORAGE=supabase).
-- item-images — public bucket (catalog URLs).


-- -----------------------------------------------------------------------------
-- PART 3 — OPTIONAL DEMO SEED
-- -----------------------------------------------------------------------------
/*
insert into public.items (
  id, title, description, category, cost_per_day, minimum_day_rental,
  deposit_amount, user_requirements, towable
) values (
  'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
  '12ft Utility Trailer',
  'Tandem axle, ramp gate, DOT lights. Ideal for local moves and equipment hauls.',
  'trailers', 45.00, 1, 150.00,
  'Valid driver license; 2-inch ball; vehicle rated for trailer weight.', true
);

insert into public.item_images (item_id, url, sort_order) values
  ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'https://picsum.photos/seed/trailer1/800/600', 0),
  ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'https://picsum.photos/seed/trailer2/800/600', 1);

insert into public.items (
  id, title, description, category, cost_per_day, minimum_day_rental,
  deposit_amount, user_requirements, towable
) values (
  'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
  'Pressure Washer 3000 PSI',
  'Gas-powered cold water unit with hoses and wand.',
  'equipment', 35.00, 1, 75.00,
  'Eye protection recommended; return clean and drained.', false
);

insert into public.item_images (item_id, url, sort_order) values
  ('b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'https://picsum.photos/seed/washer/800/600', 0);

insert into public.item_day_status (item_id, day, status)
select 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::uuid, d::date, 'open_for_booking'::public.day_status
from generate_series(current_date, current_date + 60, interval '1 day') as d;

insert into public.item_day_status (item_id, day, status)
select 'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22'::uuid, d::date, 'open_for_booking'::public.day_status
from generate_series(current_date, current_date + 60, interval '1 day') as d;
*/


-- -----------------------------------------------------------------------------
-- PART 4 — OPTIONAL BACKFILL item_day_status (existing items after seeding change)
-- -----------------------------------------------------------------------------
/*
insert into public.item_day_status (item_id, day, status)
select i.id, (current_date + g) as day, 'open_for_booking'::public.day_status
from public.items i
cross join generate_series(0, 60) as g(g)
on conflict (item_id, day) do nothing;
*/


-- -----------------------------------------------------------------------------
-- PART 5 — OPTIONAL: wipe bookings only (keep items / images / day status)
-- -----------------------------------------------------------------------------
/*
truncate table public.stripe_webhook_events;
delete from public.booking_requests;
*/
