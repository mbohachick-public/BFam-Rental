-- =============================================================================
-- BFam Rental — Supabase setup (single file)
-- =============================================================================
-- Run in the Supabase SQL Editor.
--
-- New empty project: run PART 1 only (or PART 1 + PART 2 — PART 2 is idempotent).
--   Then create Storage buckets per PART 3. Optionally uncomment PART 4 (demo seed)
--   and/or PART 5 (day-status backfill).
--
-- Legacy database (older schema, tables already exist): do NOT re-run PART 1.
--   Run PART 2 only, then optionally PART 5 (uncomment) if items lack day rows.
--
-- Row Level Security (RLS) is enabled on all app tables (see end of PART 1). The Python
-- API uses the service role key, which bypasses RLS. anon/authenticated have no policies,
-- so direct browser/PostgREST access to tables is denied unless you add policies later.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- PART 1 — CORE SCHEMA (new database)
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
  'rejected'
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
  active boolean not null default true,
  created_at timestamptz not null default now()
);

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

create table public.booking_requests (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.items (id) on delete cascade,
  start_date date not null,
  end_date date not null,
  status public.booking_request_status not null default 'pending',
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
  check (end_date >= start_date)
);

create index booking_requests_item_id_idx on public.booking_requests (item_id);
create index booking_requests_status_idx on public.booking_requests (status);
create index booking_requests_customer_auth0_sub_idx on public.booking_requests (customer_auth0_sub);

comment on column public.booking_requests.customer_auth0_sub is 'Auth0 JWT sub when booking was created with customer Auth0 enabled';
comment on column public.booking_requests.sales_tax_rate_percent is 'Combined sales tax % applied to rental subtotal at booking time';
comment on column public.booking_requests.sales_tax_amount is 'Tax dollars on rental subtotal only (not deposit)';
comment on column public.booking_requests.rental_total_with_tax is 'discounted_subtotal + sales_tax_amount';
comment on column public.booking_requests.sales_tax_source is 'How the rate was resolved (e.g. GET URL or fallback env)';
comment on column public.items.active is
  'When false, item is hidden from public catalog and customer booking flows; admins still see it.';

-- PostgREST exposes public tables to anon/authenticated. With RLS on and no policies,
-- those roles cannot read or write rows. Service role (API) bypasses RLS.
alter table public.items enable row level security;
alter table public.item_images enable row level security;
alter table public.item_day_status enable row level security;
alter table public.booking_requests enable row level security;

-- Booking files: default app uses Supabase Storage bucket `booking-documents` (private; see backend README).
-- Set BOOKING_DOCUMENTS_STORAGE=local to use disk only.


-- -----------------------------------------------------------------------------
-- PART 2 — LEGACY IDEMPOTENT MIGRATIONS
-- -----------------------------------------------------------------------------
-- Safe no-ops when columns/indexes already exist (e.g. after PART 1). Use when
-- upgrading an older database that was missing these columns.

alter table public.items
  add column if not exists towable boolean not null default false,
  add column if not exists active boolean not null default true;

alter table public.booking_requests
  add column if not exists drivers_license_path text,
  add column if not exists license_plate_path text,
  add column if not exists customer_phone text,
  add column if not exists customer_first_name text,
  add column if not exists customer_last_name text,
  add column if not exists customer_address text,
  add column if not exists customer_auth0_sub text,
  add column if not exists decline_reason text,
  add column if not exists sales_tax_rate_percent numeric(8, 4),
  add column if not exists sales_tax_amount numeric(10, 2),
  add column if not exists rental_total_with_tax numeric(10, 2),
  add column if not exists sales_tax_source text;

create index if not exists booking_requests_customer_auth0_sub_idx
  on public.booking_requests (customer_auth0_sub);

-- Idempotent: safe on DBs created before RLS was added to PART 1.
alter table public.items enable row level security;
alter table public.item_images enable row level security;
alter table public.item_day_status enable row level security;
alter table public.booking_requests enable row level security;


-- -----------------------------------------------------------------------------
-- PART 3 — STORAGE (manual steps in Dashboard)
-- -----------------------------------------------------------------------------
--
-- booking-documents
--   Dashboard → Storage → New bucket → name: booking-documents → Private.
--   Used when BOOKING_DOCUMENTS_STORAGE=supabase (default).
--
-- item-images
--   Dashboard → Storage → New bucket → name: item-images → Public (catalog URLs).
--   Used when ITEM_IMAGES_STORAGE=supabase (default). API uploads with service role;
--   anon upload policy not required unless you add direct browser uploads later.


-- -----------------------------------------------------------------------------
-- PART 4 — OPTIONAL DEMO SEED
-- -----------------------------------------------------------------------------
-- Uncomment to load sample items (adjust UUIDs if they collide).

/*
insert into public.items (
  id,
  title,
  description,
  category,
  cost_per_day,
  minimum_day_rental,
  deposit_amount,
  user_requirements,
  towable
) values (
  'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
  '12ft Utility Trailer',
  'Tandem axle, ramp gate, DOT lights. Ideal for local moves and equipment hauls.',
  'trailers',
  45.00,
  1,
  150.00,
  'Valid driver license; 2-inch ball; vehicle rated for trailer weight.',
  true
);

insert into public.item_images (item_id, url, sort_order) values
  ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'https://picsum.photos/seed/trailer1/800/600', 0),
  ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'https://picsum.photos/seed/trailer2/800/600', 1);

insert into public.items (
  id,
  title,
  description,
  category,
  cost_per_day,
  minimum_day_rental,
  deposit_amount,
  user_requirements,
  towable
) values (
  'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
  'Pressure Washer 3000 PSI',
  'Gas-powered cold water unit with hoses and wand.',
  'equipment',
  35.00,
  1,
  75.00,
  'Eye protection recommended; return clean and drained.',
  false
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
-- PART 5 — OPTIONAL BACKFILL item_day_status
-- -----------------------------------------------------------------------------
-- One-time for existing items: open_for_booking for [today, today + 60] where missing.
-- Safe to re-run (ON CONFLICT DO NOTHING). Uncomment to run.

/*
insert into public.item_day_status (item_id, day, status)
select
  i.id,
  (current_date + g) as day,
  'open_for_booking'::public.day_status
from public.items i
cross join generate_series(0, 60) as g(g)
on conflict (item_id, day) do nothing;
*/


-- -----------------------------------------------------------------------------
-- PART 6 — MAINTENANCE: DELETE ALL ITEMS (DANGER)
-- -----------------------------------------------------------------------------
-- Uncomment only to wipe the catalog. CASCADE removes booking_requests, item_images,
-- item_day_status. Does NOT delete Storage objects; use:
--   cd backend && python3 scripts/delete_all_items.py --yes

/*
delete from public.items;
*/
