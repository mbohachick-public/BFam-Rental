# BFam Rental API

FastAPI service with all database access via Supabase (service role).

## Setup

1. Create a Supabase project and run `Specs/supabase-schema.sql` in the SQL editor (then optionally `Specs/supabase-seed.sql`). If you already ran an older schema, run `Specs/supabase-migration-towable-booking-docs.sql`, `Specs/supabase-migration-booking-contact-fields.sql`, `Specs/supabase-migration-decline-reason.sql`, and `Specs/supabase-migration-item-active.sql` (catalog visibility) as needed.
2. **Booking document storage (default: Supabase Storage):** with `BOOKING_DOCUMENTS_STORAGE=supabase` (default), uploads go to the private bucket **`booking-documents`** (create it in Dashboard → Storage if needed). The API uses the service role key server-side. For local-only dev without Storage, set `BOOKING_DOCUMENTS_STORAGE=local` and files are saved under `BOOKING_DOCUMENTS_LOCAL_DIR` (default `data/booking-documents`; run uvicorn from `backend/`). Set **`API_PUBLIC_URL`** to your deployed API URL when the admin UI is not on the same host as the API.
3. **Item catalog images (default: Supabase Storage):** with `ITEM_IMAGES_STORAGE=supabase` (default), admin uploads go to the **public** bucket **`item-images`** (see `Specs/supabase-migration-item-images-bucket.sql`). The API stores public URLs in `item_images`. For local dev without Storage, set `ITEM_IMAGES_STORAGE=local` and files are saved under `ITEM_IMAGES_LOCAL_DIR` (default `data/item-images`); the API serves them at `/items/asset-images/{item_id}/{filename}` using **`API_PUBLIC_URL`** in stored links.
4. Copy `.env.example` to `.env` and set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from Project Settings → API.
5. **Emails:** To send **quote**, **booking confirmation**, and **decline** notices, set `SMTP_HOST`, `SMTP_FROM`, and usually `SMTP_USER` / `SMTP_PASSWORD` (TLS on port 587 by default). If SMTP is unset, those emails are skipped but the API still records bookings and declines.

## Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs for OpenAPI.

## Admin routes

Send header `X-Admin-Token: <ADMIN_STUB_TOKEN>` on `/admin/*` requests. Document download links also accept `?admin_token=` (same value) so you can open them in a new browser tab — **stub only**; replace with proper auth in production.

**Item photos:** `POST /admin/items/{item_id}/images` (multipart field `file`, JPEG/PNG/WebP, max 10 per item) uploads to Storage or local disk and appends a row in `item_images`. `DELETE /admin/items/{item_id}/images/{image_id}` removes the file (when it was uploaded by this app) and the row. Patching `image_urls` on `PATCH /admin/items/{item_id}` still replaces the full list and deletes prior bucket files for URLs this app recognizes.

**Catalog visibility:** `items.active` (default `true`). `GET /admin/items/{item_id}` returns any item; public `GET /items/{item_id}` and catalog list omit inactive items. `GET /admin/items/{item_id}/availability?from=&to=` matches public availability but works for inactive items (admin calendar).
