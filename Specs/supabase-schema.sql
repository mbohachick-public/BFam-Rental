-- Run in Supabase SQL Editor (or via migration). Service role from Python bypasses RLS;
-- tighten RLS later if you expose PostgREST directly.

create extension if not exists "pgcrypto";

create type public.day_status as enum (
  'out_for_use',
  'booked',
  'open_for_booking',
  'readying_for_use'
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
  notes text,
  decline_reason text,
  base_amount numeric(10, 2),
  discount_percent numeric(5, 2),
  discounted_subtotal numeric(10, 2),
  deposit_amount numeric(10, 2),
  drivers_license_path text,
  license_plate_path text,
  created_at timestamptz not null default now(),
  check (end_date >= start_date)
);

create index booking_requests_item_id_idx on public.booking_requests (item_id);
create index booking_requests_status_idx on public.booking_requests (status);

-- Booking files: default app uses Supabase Storage bucket `booking-documents` (private; see backend README). Set BOOKING_DOCUMENTS_STORAGE=local to use disk only.
