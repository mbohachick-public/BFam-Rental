-- Run in Supabase SQL Editor on an existing database (additive migration).

alter table public.items
  add column if not exists towable boolean not null default false;

alter table public.booking_requests
  add column if not exists drivers_license_path text,
  add column if not exists license_plate_path text;

-- Create a private Storage bucket named `booking-documents` (Dashboard → Storage) unless you use BOOKING_DOCUMENTS_STORAGE=local only.
