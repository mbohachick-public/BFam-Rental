# BFam Rental — Implementation Plan

This document aligns user stories in `BFam Rental Stories.txt` with architecture, wireframes, and delivery phases.

## Locked stack decisions

| Concern | Choice |
|--------|--------|
| Database | **Supabase** (managed Postgres; optional Storage for item images) |
| Frontend | **Vite + React** with **TypeScript** |
| Backend | **Python** (**FastAPI**); **all reads and writes to the database go through Python** — the React app never holds Supabase DB credentials or calls PostgREST for data |
| Authentication | **Auth0** in production; **stubbed** for now (mock roles / placeholder UI) |

## Python stack (recommended)

Use this as the default backend toolchain unless you explicitly need an ORM-first migration workflow (see alternative below).

| Piece | Choice | Why |
|--------|--------|-----|
| HTTP API | **[FastAPI](https://fastapi.tiangolo.com/)** | First-class OpenAPI docs, Pydantic v2 models, async-friendly, natural fit for a JSON API consumed by Vite + React. |
| Project & env | **[uv](https://docs.astral.sh/uv/)** | Fast installs, one tool for `venv`, dependency lock (`uv lock`), and running the app (`uv run`). Replaces juggling pip/poetry for most teams. |
| Supabase access | **[supabase-py](https://github.com/supabase/supabase-py)** (service role key **server-side only**) | Official client for Postgres and Storage; matches “everything goes through Python” without wiring SQLAlchemy to Supabase separately. Use `.table().select()` / `.insert()` etc., or RPC if you add SQL functions in Supabase later. |
| Config & validation | **Pydantic settings** (`pydantic-settings`) | Typed env (Supabase URL, keys, CORS origins); ships in the FastAPI ecosystem. |
| HTTP client (outbound) | **httpx** | Handy for Auth0 token introspection or webhooks later; commonly paired with FastAPI. |
| Tests | **pytest** + **httpx** `ASGITransport` | Call the FastAPI app in-process without a live server. |

**Runtime:** Python **3.12** (or current **3.13** if all deps support it — lock the minor version in `pyproject.toml` for the team).

### Alternative: SQLAlchemy + Alembic

Choose this if you want **schema migrations as Python/SQL files in the repo** and a classic ORM layer instead of the Supabase client API.

- **SQLAlchemy 2.0** (async with **asyncpg**) + **Alembic** for migrations, using Supabase’s **Postgres connection string** (not the anon key in the browser — still server-only).
- Slightly more setup; stronger when queries grow complex or you may move off Supabase hosting later while keeping the same SQL model.

For BFam Rental’s scope, **FastAPI + uv + supabase-py** is the better default: less glue, faster to ship, Storage stays straightforward.

## Architecture

```mermaid
flowchart LR
  subgraph client [Browser]
    V[Vite + React + TS]
  end
  subgraph server [Python services]
    API[HTTP API e.g. FastAPI]
    API --> DB[(Supabase Postgres)]
    API --> ST[Supabase Storage optional]
  end
  V -->|JSON / REST| API
```

- The React client calls only the Python API for catalog, filters, item detail, calendar data, booking requests, and admin operations.
- Python uses a Supabase **service role** or connection string to access Postgres (and Storage if used). Enforce booking rules, discount logic, and date validation on the server.

## User stories → capabilities

**Customer**

- List items available to rent; filter by item attributes.
- Item detail shows: Cost Per Day, Minimum Day Rental, Category, images (array), Description, Title, Deposit Amount, User Requirements.
- Per-item calendar: one status per date — *Out for Use*, *Booked*, *Open for Booking*, *Readying for Use*.
- Request a booking only for dates that are *Open for Booking*, within the next **60 days** from the request date.
- Show rental pricing with duration discount: **5% per day**, **maximum 15%**.
- **Email** (required) and **phone** (required) on booking requests; **quote** is emailed to that address when **SMTP** is configured on the API.

**Admin**

- Add rental items and their attributes.
- Mark items **active** or **inactive**: inactive items are omitted from the public catalog, item detail, and customer quote/booking APIs; admins still see them in the admin item list (visually highlighted) and can load them via `GET /admin/items/{id}` and `GET /admin/items/{id}/availability` for edit and calendar (public `GET /items/...` returns 404 for inactive items).
- Accept or **decline** proposed bookings (decline captures a reason, emails the customer with item and dates, sets requested days back to *Open for Booking*).
- Update each item’s per-date status.

**Data model (items)**

- `items.active` (boolean, default `true`): when `false`, the item is hidden from customers; run `Specs/supabase-migration-item-active.sql` on existing databases.

## UI wireframes (summary)

- **Catalog**: responsive grid; attribute-driven filters; optional search later.
- **Item detail**: gallery, full attribute block, calendar with legend, date selection for booking, quote line showing discount cap, submit booking request.
- **Admin**: item list and create/edit forms; booking request queue with accept and decline (reason + customer email); per-item (or item-scoped) calendar editor for status by date.
- **Auth stub**: Sign-in / account placeholders without real Auth0 until enabled.

Mobile: single-column layouts, collapsible filters, calendar suited to small screens (e.g. scrollable month or week views).

## Suggested API surface (Python)

Define concrete routes during implementation; initial shape:

- `GET /items` — list with query params: `category` (exact), `min_cost_per_day`, `max_cost_per_day`, optional `open_from` + `open_to` (item must be `open_for_booking` on every day in range, inclusive).
- `GET /items/categories` — distinct category values for filter UI.
- `GET /items/{id}` — detail including image URLs and pricing fields.
- `GET /items/{id}/availability?from=&to=` — calendar slice (status per day).
- `POST /booking-requests` — `multipart/form-data`: `item_id`, `start_date`, `end_date`, required `customer_email`, `customer_phone`, `customer_first_name`, `customer_last_name`, `customer_address`, optional `notes`, required file `drivers_license`; if the item is **towable**, required file `license_plate`. Files go to Supabase Storage **`booking-documents`** by default (`BOOKING_DOCUMENTS_STORAGE=supabase`); use `BOOKING_DOCUMENTS_STORAGE=local` and `BOOKING_DOCUMENTS_LOCAL_DIR` for disk-only dev. Sends booking confirmation email when SMTP is configured.
- `GET /admin/booking-requests/{id}/files/drivers-license` | `license-plate` — admin-only; serves local file or redirects to a signed Storage URL.
- `POST /booking-requests/quote` — JSON: `item_id`, `start_date`, `end_date`, required `customer_email`; returns quote plus `email_sent` when SMTP delivers the quote email.
- Items include **`towable`** (boolean); admin sets it via item create/update.
- Admin (stub-guarded): `POST/PATCH /admin/items`, `POST /admin/booking-requests/{id}/accept`, `POST /admin/booking-requests/{id}/decline` (JSON `reason`), `PUT /admin/items/{id}/availability` (or per-day PATCH).

## Data model (high level)

Tables or equivalent concepts (names illustrative):

- **items** — scalar attributes (title, description, category, cost_per_day, minimum_day_rental, deposit_amount, user_requirements, …).
- **item_images** — ordered images per item (or JSON array if kept simple early).
- **item_day_status** — `item_id`, `date`, `status` enum (four values).
- **booking_requests** — item, date range, status (pending/accepted/rejected), optional **decline_reason**, pricing snapshot, **customer_email**, **customer_phone**, **customer_first_name**, **customer_last_name**, **customer_address**, document storage paths, notes.

## Delivery phases

1. **Monorepo layout** — `frontend/` (Vite+React+TS), `backend/` (Python), shared env documentation; Supabase project and schema migration path.
2. **Stub auth** — React context for “customer” vs “admin”; no Auth0 yet.
3. **Read APIs** — items list, filters, item by id, availability range.
4. **Customer UI** — catalog, detail, calendar display.
5. **Booking** — POST booking request with server-side validation and discount calculation.
6. **Admin UI + APIs** — CRUD items, edit day status, accept bookings.
7. **Polish** — responsive QA, errors, empty states; then real Auth0 and securing admin routes.

## Related files

- User stories and tech spec bullets: `Specs/BFam Rental Stories.txt`
