-- Optional demo data. Run after supabase-schema.sql. Adjust UUIDs if they collide.

insert into public.items (
  id,
  title,
  description,
  category,
  cost_per_day,
  minimum_day_rental,
  deposit_amount,
  user_requirements,
  towable
) values (
  'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
  '12ft Utility Trailer',
  'Tandem axle, ramp gate, DOT lights. Ideal for local moves and equipment hauls.',
  'trailers',
  45.00,
  1,
  150.00,
  'Valid driver license; 2-inch ball; vehicle rated for trailer weight.',
  true
);

insert into public.item_images (item_id, url, sort_order) values
  ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'https://picsum.photos/seed/trailer1/800/600', 0),
  ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'https://picsum.photos/seed/trailer2/800/600', 1);

insert into public.items (
  id,
  title,
  description,
  category,
  cost_per_day,
  minimum_day_rental,
  deposit_amount,
  user_requirements,
  towable
) values (
  'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
  'Pressure Washer 3000 PSI',
  'Gas-powered cold water unit with hoses and wand.',
  'equipment',
  35.00,
  1,
  75.00,
  'Eye protection recommended; return clean and drained.',
  false
);

insert into public.item_images (item_id, url, sort_order) values
  ('b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'https://picsum.photos/seed/washer/800/600', 0);

-- Next 61 days open for booking on both items (inclusive window for the 60-day story).
insert into public.item_day_status (item_id, day, status)
select 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::uuid, d::date, 'open_for_booking'::public.day_status
from generate_series(current_date, current_date + 60, interval '1 day') as d;

insert into public.item_day_status (item_id, day, status)
select 'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22'::uuid, d::date, 'open_for_booking'::public.day_status
from generate_series(current_date, current_date + 60, interval '1 day') as d;
