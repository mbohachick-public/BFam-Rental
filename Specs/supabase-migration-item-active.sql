-- Items: catalog visibility. When active = false, the item is hidden from the public catalog
-- and item detail/booking for customers; admins still see it and can edit it.

alter table public.items
  add column if not exists active boolean not null default true;

comment on column public.items.active is
  'When false, item is hidden from public catalog and customer booking flows; admins still see it.';
