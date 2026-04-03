-- Run in Supabase SQL Editor on an existing database (additive).

alter table public.booking_requests
  add column if not exists customer_phone text,
  add column if not exists customer_first_name text,
  add column if not exists customer_last_name text,
  add column if not exists customer_address text;
