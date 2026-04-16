/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  /** Dev-only: real Auth0 access JWT for Playwright (never set in production). */
  readonly VITE_E2E_AUTH0_ACCESS_TOKEN?: string
  /** e.g. dev-abc.us.auth0.com — enable customer Auth0 when set with VITE_AUTH0_CLIENT_ID */
  readonly VITE_AUTH0_DOMAIN?: string
  readonly VITE_AUTH0_CLIENT_ID?: string
  /** Auth0 API identifier; must match backend AUTH0_AUDIENCE when enforcing JWT */
  readonly VITE_AUTH0_AUDIENCE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
