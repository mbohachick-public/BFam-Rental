-- Run in Supabase SQL Editor on an existing database (additive).

alter table public.booking_requests
  add column if not exists decline_reason text;
