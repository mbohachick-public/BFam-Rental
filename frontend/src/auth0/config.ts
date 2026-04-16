/**
 * Dev-only: Playwright / local automation injects a real access JWT without Universal Login.
 * Never set in production builds (ignored when `import.meta.env.PROD`).
 */
export function e2eDevAuth0AccessToken(): string | null {
  if (import.meta.env.PROD) return null
  const t = String(import.meta.env.VITE_E2E_AUTH0_ACCESS_TOKEN ?? '').trim()
  return t || null
}

/** True when Vite env has domain + client id (enable Auth0Provider and customer session UI). */
export function auth0Configured(): boolean {
  if (e2eDevAuth0AccessToken()) return true
  const d = String(import.meta.env.VITE_AUTH0_DOMAIN ?? '').trim()
  const c = String(import.meta.env.VITE_AUTH0_CLIENT_ID ?? '').trim()
  return Boolean(d && c)
}
