# BFam Rental API

FastAPI service with all database access via Supabase (service role).

## Setup

1. Create a Supabase project and run **`Specs/supabase-setup.sql`** in the SQL editor. **PART 0** drops and recreates all BFam application tables (destructive). **PART 1** is the full schema (booking workflow, Stripe columns, contract-signing tables, `delivery_settings`, RLS). **PART 2** lists Storage buckets; optional demo seed, day backfill, and booking-only wipe are commented in **PART 3–5**. **Availability:** new items get `item_day_status` rows for the next **61** calendar days (`today` through `today + 60`, inclusive) as `open_for_booking` when created via `POST /admin/items`. The API also **fills missing days** in that window on catalog date filters, public/admin availability reads, and quote/booking. For **existing** items that predate that behavior, uncomment **PART 4** once to backfill.
   - **Internal e-sign:** Included in `supabase-setup.sql`. Set **`FRONTEND_PUBLIC_URL`** to the customer-facing SPA origin (used in signing links in emails). Executed PDFs and snapshots are written under **`CONTRACT_PACKETS_DIR`** (default `data/contract-packets`; gitignored). **`reportlab`** is required (`pip install -e .`).
2. **Booking document storage (default: Supabase Storage):** with `BOOKING_DOCUMENTS_STORAGE=supabase` (default), uploads go to the private bucket **`booking-documents`** (create it in Dashboard → Storage if needed). The API uses the service role key server-side. For local-only dev without Storage, set `BOOKING_DOCUMENTS_STORAGE=local` and files are saved under `BOOKING_DOCUMENTS_LOCAL_DIR` (default `data/booking-documents`; run uvicorn from `backend/`). Set **`API_PUBLIC_URL`** to your deployed API URL when the admin UI is not on the same host as the API.
3. **Item catalog images (default: Supabase Storage):** with `ITEM_IMAGES_STORAGE=supabase` (default), admin uploads go to the **public** bucket **`item-images`** (see **PART 2** in `Specs/supabase-setup.sql`). The API stores public URLs in `item_images`. For local dev without Storage, set `ITEM_IMAGES_STORAGE=local` and files are saved under `ITEM_IMAGES_LOCAL_DIR` (default `data/item-images`); the API serves them at `/items/asset-images/{item_id}/{filename}` using **`API_PUBLIC_URL`** in stored links.
4. Copy `.env.example` to `.env` and set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from Project Settings → API.
5. **Emails:** To send the **quote** email (on `POST /booking-requests/quote`), **approval / signing**, **decline**, and related notices, set `SMTP_HOST`, `SMTP_FROM`, and usually `SMTP_USER` / `SMTP_PASSWORD` (TLS on port 587 by default). If SMTP is unset, those emails are skipped but the API still records bookings and declines. Submitting a booking does not send a second pricing email (the quote email is the customer’s pricing copy). **Staff workflow:** set **`ADMIN_NOTIFICATION_EMAIL`** (with SMTP) to receive **“booking needs approval”** when a customer finishes submitting documents, and **“booking ready to confirm”** when rental payment, deposit (if any), and signed agreement are all satisfied—each message links to `{FRONTEND_PUBLIC_URL}/admin/bookings/{id}`. Sends are deduplicated per booking via `booking_events`.
6. **Sales tax:** Quotes and booking inserts apply tax to the **rental subtotal** (`discounted_subtotal`), not the deposit. Configure **`SALES_TAX_RATE_URL`** (HTTPS GET, `{zip}` in the path or `postal_code` query appended) or **`SALES_TAX_FALLBACK_PERCENT`** for dev; see `backend/.env.example`.

## Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Keep the venv **activated** while `uvicorn` runs. If you start `uvicorn` from a shell that uses a different Python (for example a global install), you can get `ModuleNotFoundError` (e.g. for `stripe`) even though `pip install -e .` succeeded in `.venv`. Either activate `.venv` first or run `./.venv/bin/python -m uvicorn app.main:app --reload --port 8000`.

Open http://127.0.0.1:8000/docs for OpenAPI.

## Docker

From the **repository root** (build context is `backend/`):

```bash
docker build -f backend/Dockerfile -t bfam-rental-api backend
docker run --rm -p 8000:8000 -e PORT=8000 \
  -e SUPABASE_URL=… -e SUPABASE_SERVICE_ROLE_KEY=… \
  -e CORS_ORIGINS=http://localhost:5173 -e API_PUBLIC_URL=http://127.0.0.1:8000 \
  bfam-rental-api
```

Production on Render is defined in the root `render.yaml`; see `Specs/Deployment-Environments.md`.

## Admin routes

`/admin/*` requires **`AUTH0_DOMAIN`** and **`AUTH0_AUDIENCE`** on the API, plus **`Authorization: Bearer <access_token>`** where the token is valid for that API **and** the user is allowed as admin (see below). The SPA uses the same Auth0 access token it uses for quote/booking after the user chooses **Continue to admin**.

**Who counts as admin (Auth0):** After JWT verification, the API allows access if **any** of these match:

- **`AUTH0_ADMIN_SUBS`**: comma-separated JWT **`sub`** values (e.g. `auth0|abc123`). Use this when your access token has **no** custom roles/email claims (typical until you add an Auth0 Action). Copy `sub` from [jwt.io](https://jwt.io) or Auth0 Dashboard → Users → **Details**.  
- Any of **`email`** or a namespaced claim whose key ends with **`/email`** matches **`AUTH0_ADMIN_EMAILS`** (comma-separated).  
- **`AUTH0_ADMIN_ROLES`** (comma-separated, default `admin`) appears in **`permissions`** (Auth0 RBAC), top-level **`roles`** (strings or objects with **`name`** / **`role_name`** / **`id`**), **any claim whose key ends with `/roles`**, or the optional **`AUTH0_ADMIN_ROLES_CLAIM`** (exact key; string or array).

You do **not** need **`AUTH0_ADMIN_ROLES_CLAIM`** if your Action already uses a namespaced key like `https://your.app/roles` — that pattern is picked up automatically.

Dashboard roles are **not** on the access token until you add an **Auth0 Action** (e.g. Post Login → add custom claims or enable RBAC “Add Permissions in the Access Token”). Example Action snippet to copy roles into a namespaced claim:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const namespace = 'https://your.app';
  if (event.authorization?.roles?.length) {
    api.accessToken.setCustomClaim(`${namespace}/roles`, event.authorization.roles);
  }
  if (event.user?.email) {
    api.accessToken.setCustomClaim('email', event.user.email);
  }
};
```

Set **`AUTH0_ADMIN_ROLES`** to the Auth0 role name(s) to allow (e.g. `admin`; matching is case-insensitive). Use **`AUTH0_ADMIN_ROLES_CLAIM`** only if your roles live under a non-standard key that does **not** end with `/roles`.

A valid token that fails these checks receives **403** `Not authorized as admin`.

**Item photos:** `POST /admin/items/{item_id}/images` (multipart field `file`, JPEG/PNG/WebP, max 10 per item) uploads to Storage or local disk and appends a row in `item_images`. `DELETE /admin/items/{item_id}/images/{image_id}` removes the file (when it was uploaded by this app) and the row. Patching `image_urls` on `PATCH /admin/items/{item_id}` still replaces the full list and deletes prior bucket files for URLs this app recognizes.

**Catalog visibility:** `items.active` (default `true`). `GET /admin/items/{item_id}` returns any item; public `GET /items/{item_id}` and catalog list omit inactive items. `GET /admin/items/{item_id}/availability?from=&to=` matches public availability but works for inactive items (admin calendar).

## Auth0 (optional customer JWT)

**Customers** use Auth0 for `POST /booking-requests/quote`, presign/complete or multipart booking create, and customer-account routes when **`AUTH0_DOMAIN`** + **`AUTH0_AUDIENCE`** are set. **Admins** use the same access token on `/admin/*` when role/email/sub rules match (see **Admin routes** above).

**Booking document uploads:** With **`BOOKING_DOCUMENTS_STORAGE=supabase`** (default), the SPA calls **`POST /booking-requests/presign`** (JSON, including `drivers_license_content_type` and optional `license_plate_content_type`), uploads files with **`PUT`** to the returned signed URLs (bytes go to Supabase, not through this API), then **`POST /booking-requests/{booking_id}/complete`** with the same `path` values from the presign response. With **`BOOKING_DOCUMENTS_STORAGE=local`**, use **`POST /booking-requests`** multipart only. **`DELETE /booking-requests/{id}/abandon`** removes a pending presign row and any partial uploads under that prefix. If **`PUT`** to Supabase fails with a browser CORS error, add your site origin to Storage CORS in the Supabase dashboard.

Use one **API** identifier for **`AUTH0_AUDIENCE`** (not the Auth0 Management API `.../api/v2/`) so the SPA and backend agree on audience.

1. In the Auth0 Dashboard, create a **Single Page Application** and an **API** with an identifier (audience), e.g. `https://api.yourdomain.com`.
2. Set **Allowed Callback URLs**, **Allowed Logout URLs**, and **Allowed Web Origins** to your SPA origins (e.g. `http://localhost:5173` and production `https://…`).
3. In `backend/.env`, set **`AUTH0_DOMAIN`** (hostname only, e.g. `dev-abc.us.auth0.com`) and **`AUTH0_AUDIENCE`** (the API identifier). When **both** are set, those two routes require `Authorization: Bearer <access_token>`. Leave either unset to allow anonymous quote/booking (typical local dev).
4. In `frontend/.env`, set **`VITE_AUTH0_DOMAIN`**, **`VITE_AUTH0_CLIENT_ID`**, and **`VITE_AUTH0_AUDIENCE`** (same audience as the API). Restart `npm run dev` after changes.
5. Keep **`CORS_ORIGINS`** including every origin where users open the Vite app (including LAN URLs if you test on a phone).

Tokens are validated with RS256 against `https://<AUTH0_DOMAIN>/.well-known/jwks.json` with issuer `https://<AUTH0_DOMAIN>/`.

**Production layout (same host vs split API):** see `Specs/Deployment-Environments.md`.
