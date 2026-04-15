/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_ADMIN_STUB_TOKEN?: string
  /** e.g. dev-abc.us.auth0.com — enable customer Auth0 when set with VITE_AUTH0_CLIENT_ID */
  readonly VITE_AUTH0_DOMAIN?: string
  readonly VITE_AUTH0_CLIENT_ID?: string
  /** Auth0 API identifier; must match backend AUTH0_AUDIENCE when enforcing JWT */
  readonly VITE_AUTH0_AUDIENCE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
