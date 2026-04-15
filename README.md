# BFam-Rental

Website for the trailer rental business.

## Preview locally

1. **Supabase** — Run `Specs/supabase-setup.sql` in the SQL editor (see file header for parts; optional demo seed and backfill are commented there).
2. **API** — In `backend/`, copy `.env.example` to `.env`, set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, then:

   ```bash
   cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e . && uvicorn app.main:app --reload --port 8000
   ```

3. **Frontend** — In `frontend/`, optional `.env`: for local dev you can **omit** `VITE_API_URL` so the app uses the Vite `/api` proxy to port 8000 (avoids CORS). For production builds, set `VITE_API_URL` to your public API URL. Then:

   ```bash
   cd frontend && npm install && npm run dev
   ```

   Open the URL Vite prints (usually http://localhost:5173). Use **Admin** → sign in with the same value as `ADMIN_STUB_TOKEN` in the API `.env`.

### “Failed to fetch” or catalog errors in the browser

1. **API not running** — Uvicorn must be on port **8000** (or match your `VITE_API_URL` / Vite proxy target). Check [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

2. **Supabase URL invalid** — If the terminal shows `httpx.ConnectError` / `nodename nor servname provided`, `SUPABASE_URL` in `backend/.env` is wrong (placeholder, typo, or missing host). Use **Supabase → Project Settings → API → Project URL** (looks like `https://xxxxxxxx.supabase.co`). Restart uvicorn after fixing. The API now returns **503** with a clear JSON message instead of an opaque failure.

3. **CORS (only if you call the API directly)** — If `VITE_API_URL` is `http://127.0.0.1:8000`, the backend must list your page’s origin in `CORS_ORIGINS`. **Easier:** leave `VITE_API_URL` unset in dev so the app uses **`/api`** and Vite proxies to port 8000 (no cross-origin calls from the browser).

4. **Restart Vite** after changing `frontend/.env` (env is read at startup).

## Production (Render)

- **Hosting:** [Render](https://render.com) — API as a **Docker** web service, SPA as a **static** site. Definitions live in [`render.yaml`](render.yaml); full steps and env vars are in [Deployment: local/test vs production](Specs/Deployment-Environments.md).
- **CI:** GitHub Actions [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — backend tests and frontend production build on pushes and PRs to `main`.

## Documentation

- [Implementation plan](Specs/Implementation-Plan.md)
- [Style guide](Specs/Style-Guide.md) (colors, type, components — aligned with `assets/bfam-rental-logo.png`)
- [Deployment environments](Specs/Deployment-Environments.md) (Render, CORS, Auth0, Supabase)
