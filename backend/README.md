# BFam Rental API

FastAPI service with all database access via Supabase (service role).

## Setup

1. Create a Supabase project and run `Specs/supabase-schema.sql` in the SQL editor (then optionally `Specs/supabase-seed.sql`). If you already ran an older schema, run `Specs/supabase-migration-towable-booking-docs.sql` too.
2. **Booking document storage (default: local disk):** with `BOOKING_DOCUMENTS_STORAGE=local` (default), files are saved under `BOOKING_DOCUMENTS_LOCAL_DIR` (default `data/booking-documents` relative to the process working directory — run uvicorn from `backend/`). This folder is gitignored. For production, set `BOOKING_DOCUMENTS_STORAGE=supabase`, create the private bucket **`booking-documents`** in Dashboard → Storage, and set **`API_PUBLIC_URL`** to your deployed API URL if needed for admin links.
3. Copy `.env.example` to `.env` and set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from Project Settings → API.

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
