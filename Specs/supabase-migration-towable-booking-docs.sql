-- Run in Supabase SQL Editor on an existing database (additive migration).

alter table public.items
  add column if not exists towable boolean not null default false;

alter table public.booking_requests
  add column if not exists drivers_license_path text,
  add column if not exists license_plate_path text;

-- When BOOKING_DOCUMENTS_STORAGE=supabase: create a private bucket named `booking-documents`
-- (Dashboard → Storage). Not required while using local disk storage (default).
