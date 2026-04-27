# Deployment: local/test vs production

## Locked production stack: Render

Production is defined as **two Render services** in the repo root [`render.yaml`](../render.yaml):

1. **`bfam-rental-api`** — `runtime: docker`, [`backend/Dockerfile`](../backend/Dockerfile), health check `GET /health`.
2. **`bfam-rental-web`** — `runtime: static`, Vite build from `frontend/`, publish `frontend/dist`.

### Static site: deep links (`/booking-actions/…`, `/admin/…`, etc.)

React Router paths are not real files on disk. If the CDN returns plain text **`Not Found`** for a URL like `https://www.example.com/booking-actions/TOKEN/sign`, the **SPA fallback** is not active.

1. **Render Dashboard (required):** open **`bfam-rental-web`** → **Redirects / Rewrites** → add **Rewrite** (not redirect): **Source** `/*` → **Destination** `/index.html`. [Render docs: static rewrites](https://render.com/docs/redirects-rewrites). Re-check this after attaching **custom domains** (`www` vs apex); Blueprint `routes` in [`render.yaml`](../render.yaml) should match, but the Dashboard rule is the reliable place to confirm.
2. **404 fallback:** the frontend build copies `index.html` to **`dist/404.html`** (`postbuild` in [`frontend/package.json`](../frontend/package.json)) so hosts that serve `404.html` for unknown paths still load the SPA.
3. **`CORS_ORIGINS`** on the API must include **every** origin customers use (e.g. both `https://bohachickrentals.com` and `https://www.bohachickrentals.com` if both serve the app).
4. **Approval email payment links** (`stripe_checkout_url` / `stripe_deposit_checkout_url`) require **`STRIPE_SECRET_KEY`** on the API, **`payment_path`** = card for that booking, and valid **`FRONTEND_PUBLIC_URL`** / **`APP_BASE_URL`** for Stripe return URLs. If links are missing only in production, check Render API env and logs for `stripe_checkout_at_email_skipped`.

This is **layout B** (split hosts): the SPA and API have different `https://…onrender.com` URLs unless you later put a custom domain and reverse proxy in front.

### Repeatable deploys

- **Infrastructure:** Connect the GitHub repo to Render and use **Blueprint** (Infrastructure as Code) with `render.yaml`. Pushes to the linked branch trigger **automatic deploys** for both services (per Render project settings).
- **CI:** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on pushes and PRs to `main`: backend `pytest`, frontend `npm ci` + `npm run build`.

### First-time order (avoid broken static build)

1. Create the Blueprint (or create the API service first from `render.yaml`).
2. Set **API** environment variables in the Render dashboard (see [Environment variables](#render-api-service) below). Deploy the API and copy its public URL (e.g. `https://bfam-rental-api.onrender.com`).
3. Set **`VITE_API_URL`** on the **static** service to that URL (no trailing slash). Set **`CORS_ORIGINS`** on the API to the static site’s public URL (and keep `http://localhost:5173` if you still want local dev against prod API — usually you use a separate Supabase project instead).
4. Set **`API_PUBLIC_URL`** on the API to the same public API base URL (for links in JSON and emails).
5. Redeploy the static site if needed so the Vite build picks up `VITE_*` values.

**Docker locally:** from the repo root, `docker build -f backend/Dockerfile backend` then run with `-e PORT=8000` and the same env vars as production (see `backend/.env.example`).

---

You can use **one Auth0 SPA application** for every environment. Add **each** SPA origin under **Allowed Callback URLs**, **Allowed Logout URLs**, and **Allowed Web Origins** (e.g. `http://localhost:5173` and your production `https://…`).

Use **separate Supabase projects** for non-prod vs prod (different `SUPABASE_URL` and **service role** keys). Never put the service role key in the frontend.

---

## API and SPA: same host vs different hosts

You do **not** have to decide before shipping; pick one layout and set env vars accordingly.

### A) Same host (reverse proxy)

**Example:** `https://www.example.com` serves the Vite-built SPA, and `/api/*` is proxied to uvicorn.

| Area | What to set |
|------|-------------|
| **Frontend** `VITE_API_URL` | `proxy` or leave unset in dev (Vite proxy in `vite.config`). In production build, configure the host so `/api` routes to the API (platform-specific: nginx, Cloudflare, Vercel rewrites, etc.). |
| **Backend** `CORS_ORIGINS` | Your SPA origin(s), e.g. `https://www.example.com` (same as users in the browser). |
| **Backend** `API_PUBLIC_URL` | Public base URL of the **API** as browsers see it, often `https://www.example.com` if links are same-origin. |

**Auth0:** Callback / logout / web origins = `https://www.example.com` (and localhost for dev).

---

### B) Different hosts (SPA and API on different URLs)

**Example:** SPA `https://app.example.com`, API `https://api.example.com`.

| Area | What to set |
|------|-------------|
| **Frontend** `VITE_API_URL` | Full API base with **no** trailing slash, e.g. `https://api.example.com`. The SPA calls this origin directly; the API must allow the SPA origin in CORS. |
| **Backend** `CORS_ORIGINS` | Include **every** SPA origin that will call the API, comma-separated, e.g. `https://app.example.com,http://localhost:5173`. |
| **Backend** `API_PUBLIC_URL` | `https://api.example.com` (or whatever generates correct links for admin file URLs and emails). |

**Auth0:** Callback / logout / web origins = SPA origins (`https://app.example.com`, localhost), **not** the API hostname (unless the SPA is served from there).

---

## Quick checklist (both layouts)

1. **Auth0:** Same client ID + audience in dev and prod; multiple callback origins listed.  
2. **Supabase:** Per-environment `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (server only).  
3. **CORS:** Backend `CORS_ORIGINS` matches how users open the SPA.  
4. **Storage / presign:** Supabase Storage CORS allows the SPA origin if browsers `PUT` directly to signed URLs.  
5. **Admin Auth0:** Set `AUTH0_DOMAIN` / `AUTH0_AUDIENCE` on the API and admin allowlist vars (`AUTH0_ADMIN_*`); the SPA sends the same Bearer token as customers after **Continue to admin**.

See `backend/.env.example` and `frontend/.env.example` for variable names.

---

## Render: environment variables

### Render API service

| Variable | Notes |
|----------|--------|
| `SUPABASE_URL` | Production Supabase project URL. |
| `SUPABASE_SERVICE_ROLE_KEY` | Server only; never in the frontend. |
| `CORS_ORIGINS` | Comma-separated SPA origins (your static site URL + localhost for dev if needed). |
| `API_PUBLIC_URL` | Public base URL of this API (e.g. `https://…onrender.com`). |
| `BOOKING_DOCUMENTS_STORAGE` | Default `supabase` in `render.yaml`. |
| `ITEM_IMAGES_STORAGE` | Default `supabase` in `render.yaml`. |

Optional (add in the dashboard when you use them): `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, admin allowlists, `SMTP_*`, sales tax URLs — same names as `backend/.env.example`.

### Render static site (build-time)

| Variable | Notes |
|----------|--------|
| `VITE_API_URL` | Full API origin, no trailing slash (required for split-host production). |
| `VITE_AUTH0_*` | Set for customer + admin UI (domain, client ID, audience). |

Supabase **Storage CORS** must allow your static site origin if browsers upload via signed URLs.
