-- =============================================================================
-- BFam Rental — Enable Row Level Security (fixes Supabase linter: public tables)
-- =============================================================================
-- Run once in Supabase SQL Editor (all environments: dev, staging, prod).
--
-- Why: PostgREST exposes public.* to the anon (and authenticated) JWT roles.
-- Without RLS, anyone with your project URL + anon key could read/write tables.
--
-- This app uses only the FastAPI backend with SUPABASE_SERVICE_ROLE_KEY. That key
-- uses the service_role role, which bypasses RLS in Supabase — your API keeps
-- working unchanged.
--
-- With RLS enabled and no policies for anon/authenticated, direct table access
-- via REST is denied. If you later add supabase-js + Auth and need SELECT on
-- items from the browser, add explicit policies (do not disable RLS).
-- =============================================================================

alter table public.items enable row level security;
alter table public.item_images enable row level security;
alter table public.item_day_status enable row level security;
alter table public.booking_requests enable row level security;
