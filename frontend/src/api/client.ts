/** Passed to Auth0 getAccessTokenSilently (e.g. cacheMode: 'off' after a 401). */
export type CustomerTokenOptions = { cacheMode?: 'on' | 'off' | 'cache-only' }

type CustomerTokenGetter = (opts?: CustomerTokenOptions) => Promise<string | null>

let customerAccessTokenGetter: CustomerTokenGetter | null = null

/** Called from Auth0 bridge; clears when Auth0 is off or on unmount. */
export function setCustomerAccessTokenGetter(fn: CustomerTokenGetter | null) {
  customerAccessTokenGetter = fn
}

async function withCustomerAuthHeaders(
  path: string,
  headers: Record<string, string>,
  tokenOpts?: CustomerTokenOptions,
): Promise<Record<string, string>> {
  const out = { ...headers }
  if (path.startsWith('/booking-requests') && customerAccessTokenGetter) {
    try {
      const t = await customerAccessTokenGetter(tokenOpts)
      if (t) out.Authorization = `Bearer ${t}`
    } catch {
      /* re-auth may be required */
    }
  }
  return out
}

/** Booking API calls: retry once with a fresh access token after auth errors (stale cache / expiry). */
async function fetchBookingRequestsWithAuthRetry(
  path: string,
  init: RequestInit,
): Promise<Response> {
  const baseHeaders: Record<string, string> =
    init.headers instanceof Headers
      ? Object.fromEntries(init.headers.entries())
      : { ...((init.headers as Record<string, string> | undefined) ?? {}) }

  const run = async (tokenOpts?: CustomerTokenOptions) => {
    const headers = await withCustomerAuthHeaders(path, baseHeaders, tokenOpts)
    return apiFetch(`${baseUrl()}${path}`, { ...init, headers })
  }

  let res = await run(undefined)
  if (
    res.status === 401 &&
    path.startsWith('/booking-requests') &&
    customerAccessTokenGetter
  ) {
    const msg = await parseError(res)
    if (/invalid|expired|sign in required/i.test(msg)) {
      res = await run({ cacheMode: 'off' })
    }
  }
  return res
}

const baseUrl = () => {
  const raw = import.meta.env.VITE_API_URL as string | undefined
  // Dev: omit VITE_API_URL (or set to "proxy") to use Vite proxy → same origin, no CORS.
  if (import.meta.env.DEV && (raw === undefined || raw === '' || raw === 'proxy')) {
    return '/api'
  }
  return (raw ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
}

function networkFailureMessage(): string {
  const url = baseUrl()
  return [
    `Cannot reach the API at ${url}.`,
    'Check: (1) Backend is running: `uvicorn app.main:app --reload --port 8000` from `backend/`.',
    '(2) `frontend/.env` has `VITE_API_URL` pointing at that server (then restart `npm run dev` — Vite reads env only at startup).',
    '(3) If you open the site as http://YOUR-LAN-IP:5173, add `http://YOUR-LAN-IP:5173` to `CORS_ORIGINS` in `backend/.env`.',
  ].join(' ')
}

/** Wraps fetch; turns browser "Failed to fetch" into an actionable message. */
async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch (e) {
    if (e instanceof TypeError) {
      throw new Error(networkFailureMessage())
    }
    throw e
  }
}

/** Headers for /admin/*: Auth0 Bearer from the registered token getter (required for admin routes). */
export async function adminAuthHeaders(
  initHeaders?: HeadersInit,
  tokenOpts?: CustomerTokenOptions,
): Promise<Record<string, string>> {
  const out: Record<string, string> =
    initHeaders instanceof Headers
      ? Object.fromEntries(initHeaders.entries())
      : { ...((initHeaders as Record<string, string> | undefined) ?? {}) }
  if (customerAccessTokenGetter) {
    try {
      const t = await customerAccessTokenGetter(tokenOpts)
      if (t) out.Authorization = `Bearer ${t}`
    } catch {
      /* ignore */
    }
  }
  return out
}

async function fetchAdminWithAuthRetry(path: string, init: RequestInit): Promise<Response> {
  const baseHeaders: Record<string, string> =
    init.headers instanceof Headers
      ? Object.fromEntries(init.headers.entries())
      : { ...((init.headers as Record<string, string> | undefined) ?? {}) }

  const run = async (tokenOpts?: CustomerTokenOptions) => {
    const headers = await adminAuthHeaders(baseHeaders, tokenOpts)
    return apiFetch(`${baseUrl()}${path}`, { ...init, headers })
  }

  let res = await run(undefined)
  if (res.status === 401 && customerAccessTokenGetter) {
    const msg = await parseError(res.clone())
    if (/invalid|expired|sign in required/i.test(msg)) {
      res = await run({ cacheMode: 'off' })
    }
  }
  return res
}

function resolveApiUrl(pathOrUrl: string): string {
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) {
    return pathOrUrl
  }
  const base = baseUrl()
  const p = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return `${base}${p}`
}

/** GET a binary (e.g. booking document) with admin auth; opens safely without putting tokens in the URL. */
export async function adminDownloadBlob(url: string): Promise<Blob> {
  const headers = await adminAuthHeaders()
  const res = await apiFetch(resolveApiUrl(url), { method: 'GET', headers })
  if (!res.ok) throw new Error(await parseError(res))
  return res.blob()
}

export async function parseError(res: Response): Promise<string> {
  try {
    const j: unknown = await res.json()
    if (j && typeof j === 'object' && 'detail' in j) {
      const d = (j as { detail: unknown }).detail
      if (typeof d === 'string') return d
      if (Array.isArray(d)) return JSON.stringify(d)
    }
  } catch {
    /* ignore */
  }
  return res.statusText || 'Request failed'
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = path.startsWith('/booking-requests')
    ? await fetchBookingRequestsWithAuthRetry(path, { method: 'GET' })
    : await apiFetch(`${baseUrl()}${path}`, {
        headers: await withCustomerAuthHeaders(path, {}),
      })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

/** GET without customer/admin auth (e.g. tokenized signing links). */
export async function apiGetPublic<T>(path: string): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, { method: 'GET' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

/** POST JSON without customer/admin auth. */
export async function apiPostPublic<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const useBookingAuth = path.startsWith('/booking-requests')
  const res = useBookingAuth
    ? await fetchBookingRequestsWithAuthRetry(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
    : await apiFetch(`${baseUrl()}${path}`, {
        method: 'POST',
        headers: await withCustomerAuthHeaders(path, { 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
      })
  if (!res.ok) throw new Error(await parseError(res))
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

/** multipart/form-data (do not set Content-Type — browser sets boundary). */
/** PUT file bytes to a Supabase signed upload URL (not the API origin). */
export async function uploadBookingFileToSignedUrl(
  signedUrl: string,
  file: File,
  contentType: string,
): Promise<void> {
  const ct = contentType.trim() || 'application/octet-stream'
  const res = await fetch(signedUrl, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': ct },
  })
  if (!res.ok) {
    const t = await res.text().catch(() => res.statusText)
    throw new Error(t || `Upload failed (${res.status})`)
  }
}

export async function apiDelete(path: string): Promise<void> {
  const useBookingAuth = path.startsWith('/booking-requests')
  const res = useBookingAuth
    ? await fetchBookingRequestsWithAuthRetry(path, { method: 'DELETE' })
    : await apiFetch(`${baseUrl()}${path}`, {
        method: 'DELETE',
        headers: await withCustomerAuthHeaders(path, {}),
      })
  if (!res.ok) throw new Error(await parseError(res))
}

export async function apiPostFormData<T>(path: string, formData: FormData): Promise<T> {
  const res = path.startsWith('/booking-requests')
    ? await fetchBookingRequestsWithAuthRetry(path, {
        method: 'POST',
        body: formData,
      })
    : await apiFetch(`${baseUrl()}${path}`, {
        method: 'POST',
        headers: await withCustomerAuthHeaders(path, {}),
        body: formData,
      })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function apiPut(path: string, body: unknown): Promise<void> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminGet<T>(path: string): Promise<T> {
  const res = await fetchAdminWithAuthRetry(path, { method: 'GET' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchAdminWithAuthRetry(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchAdminWithAuthRetry(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminPut(path: string, body: unknown): Promise<void> {
  const res = await fetchAdminWithAuthRetry(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
}

export async function adminPostNoBody<T>(path: string): Promise<T> {
  const res = await fetchAdminWithAuthRetry(path, { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

/** multipart/form-data with admin auth (do not set Content-Type). */
export async function adminPostFormData<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetchAdminWithAuthRetry(path, { method: 'POST', body: formData })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminDelete<T>(path: string): Promise<T> {
  const res = await fetchAdminWithAuthRetry(path, { method: 'DELETE' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}
