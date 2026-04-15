-- booking_requests: tax / total columns expected by the API (presign + quote flows).
-- Error without these: PGRST204 "Could not find the 'rental_total_with_tax' column ... in the schema cache"
-- Run in Supabase Dashboard → SQL Editor. Safe to re-run (IF NOT EXISTS).

alter table public.booking_requests
  add column if not exists sales_tax_rate_percent numeric(8, 4),
  add column if not exists sales_tax_amount numeric(10, 2),
  add column if not exists rental_total_with_tax numeric(10, 2),
  add column if not exists sales_tax_source text;

comment on column public.booking_requests.sales_tax_rate_percent is 'Combined sales tax % applied to rental subtotal at booking time';
comment on column public.booking_requests.sales_tax_amount is 'Tax dollars on rental subtotal only (not deposit)';
comment on column public.booking_requests.rental_total_with_tax is 'discounted_subtotal + sales_tax_amount';
comment on column public.booking_requests.sales_tax_source is 'How the rate was resolved (e.g. GET URL or fallback env)';
