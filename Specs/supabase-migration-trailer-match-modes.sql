-- Trailer Match Assistant — recommendation mode + fit breakdown (additive).
-- Existing rows keep NULLs on new columns; `recommended_trailer_type` may be NULL for contact_required.
-- -----------------------------------------------------------------------------

alter table public.trailer_match_requests
  add column if not exists mode text
    check (
      mode is null
      or mode in ('single_trailer', 'multi_load', 'contact_required', 'delivery_suggested')
    );

alter table public.trailer_match_requests
  add column if not exists trailer_for_load text
    check (
      trailer_for_load is null
      or trailer_for_load in ('10_7k', '12_10k', '12_12k')
    );

alter table public.trailer_match_requests
  add column if not exists estimated_trips integer
    check (estimated_trips is null or estimated_trips >= 1);

alter table public.trailer_match_requests
  add column if not exists job_fit text
    check (job_fit is null or job_fit in ('low', 'medium', 'high'));

alter table public.trailer_match_requests
  add column if not exists vehicle_fit text
    check (vehicle_fit is null or vehicle_fit in ('low', 'medium', 'high'));

alter table public.trailer_match_requests
  add column if not exists driver_fit text
    check (driver_fit is null or driver_fit in ('low', 'medium', 'high'));

alter table public.trailer_match_requests
  alter column recommended_trailer_type drop not null;

comment on column public.trailer_match_requests.mode is
  'Recommendation mode: single trailer, multi-load 10′ 7k plan, contact required, or delivery suggested.';

comment on column public.trailer_match_requests.trailer_for_load is
  'Material-sized trailer (single-trip fit) when it differs from the recommended tow plan.';

notify pgrst, 'reload schema';
