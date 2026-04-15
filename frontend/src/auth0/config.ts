/** True when Vite env has domain + client id (enable Auth0Provider and customer session UI). */
export function auth0Configured(): boolean {
  const d = String(import.meta.env.VITE_AUTH0_DOMAIN ?? '').trim()
  const c = String(import.meta.env.VITE_AUTH0_CLIENT_ID ?? '').trim()
  return Boolean(d && c)
}
