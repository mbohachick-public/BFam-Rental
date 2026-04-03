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

async function parseError(res: Response): Promise<string> {
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
  const res = await apiFetch(`${baseUrl()}${path}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

/** multipart/form-data (do not set Content-Type — browser sets boundary). */
export async function apiPostFormData<T>(path: string, formData: FormData): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'POST',
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

export async function adminGet<T>(path: string, token: string): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    headers: { 'X-Admin-Token': token },
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminPost<T>(path: string, token: string, body: unknown): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': token,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminPatch<T>(path: string, token: string, body: unknown): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': token,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminPut(path: string, token: string, body: unknown): Promise<void> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': token,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
}

export async function adminPostNoBody<T>(path: string, token: string): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'POST',
    headers: { 'X-Admin-Token': token },
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

/** multipart/form-data with admin token (do not set Content-Type). */
export async function adminPostFormData<T>(path: string, token: string, formData: FormData): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'POST',
    headers: { 'X-Admin-Token': token },
    body: formData,
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}

export async function adminDelete<T>(path: string, token: string): Promise<T> {
  const res = await apiFetch(`${baseUrl()}${path}`, {
    method: 'DELETE',
    headers: { 'X-Admin-Token': token },
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<T>
}
