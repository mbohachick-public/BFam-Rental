-- Delivery pricing (admin-configurable) + booking line items.
-- Run in Supabase SQL Editor after backup.

CREATE TABLE IF NOT EXISTS public.delivery_settings (
  id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  enabled boolean NOT NULL DEFAULT false,
  origin_address text NOT NULL DEFAULT '',
  price_per_mile numeric NOT NULL DEFAULT 0,
  minimum_fee numeric NOT NULL DEFAULT 0,
  free_miles numeric NOT NULL DEFAULT 0,
  max_delivery_miles numeric,
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.delivery_settings IS 'Singleton (id=1): yard/origin + per-mile delivery pricing.';

INSERT INTO public.delivery_settings (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.booking_requests
  ADD COLUMN IF NOT EXISTS delivery_requested boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS delivery_fee numeric NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS delivery_distance_miles numeric;

COMMENT ON COLUMN public.booking_requests.delivery_requested IS 'Customer requested delivery to delivery_address.';
COMMENT ON COLUMN public.booking_requests.delivery_fee IS 'Computed delivery charge (taxed with rental subtotal).';
COMMENT ON COLUMN public.booking_requests.delivery_distance_miles IS 'Road distance origin→delivery from routing API.';
