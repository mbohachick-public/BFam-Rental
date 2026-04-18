-- =============================================================================
-- Contract signing — STEP 2 OF 2: tables (run after step 1 committed)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.booking_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.booking_requests (id) ON DELETE CASCADE,
  document_type text NOT NULL
    CHECK (document_type IN ('RENTAL_AGREEMENT', 'DAMAGE_FEE_SCHEDULE', 'EXECUTED_PACKET')),
  document_version text NOT NULL DEFAULT '1',
  title text NOT NULL,
  html_snapshot text,
  pdf_path text,
  sha256_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS booking_documents_booking_id_idx ON public.booking_documents (booking_id);

CREATE TABLE IF NOT EXISTS public.booking_signatures (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.booking_requests (id) ON DELETE CASCADE,
  signer_name text NOT NULL,
  signer_email text NOT NULL,
  company_name text,
  typed_signature text NOT NULL,
  signed_at timestamptz NOT NULL DEFAULT now(),
  ip_address text,
  user_agent text,
  agreement_version text NOT NULL DEFAULT '1',
  damage_schedule_version text NOT NULL DEFAULT '1',
  acknowledged_terms jsonb NOT NULL DEFAULT '{}'::jsonb,
  signature_audit_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS booking_signatures_one_per_booking
  ON public.booking_signatures (booking_id);

CREATE TABLE IF NOT EXISTS public.booking_action_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.booking_requests (id) ON DELETE CASCADE,
  token_hash text NOT NULL,
  action_type text NOT NULL CHECK (action_type IN ('SIGN', 'PAY', 'VIEW')),
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS booking_action_tokens_token_hash_uidx
  ON public.booking_action_tokens (token_hash);

CREATE INDEX IF NOT EXISTS booking_action_tokens_booking_id_idx ON public.booking_action_tokens (booking_id);

ALTER TABLE public.booking_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.booking_signatures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.booking_action_tokens ENABLE ROW LEVEL SECURITY;
