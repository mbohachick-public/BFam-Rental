import { Auth0Provider, useAuth0 } from '@auth0/auth0-react'
import { useEffect, useLayoutEffect, useMemo, useRef, type ReactNode } from 'react'
import { setCustomerAccessTokenGetter, type CustomerTokenOptions } from '../api/client'
import { auth0Configured } from '../auth0/config'
import { CustomerSessionProvider, type CustomerSession } from '../context/CustomerSessionContext'

function ClearCustomerTokenGetter() {
  useEffect(() => {
    setCustomerAccessTokenGetter(null)
    return () => setCustomerAccessTokenGetter(null)
  }, [])
  return null
}

function Auth0AccessTokenBridge() {
  const { getAccessTokenSilently } = useAuth0()
  const getTokenRef = useRef(getAccessTokenSilently)
  getTokenRef.current = getAccessTokenSilently

  /* Register once; use ref so we always call the latest getAccessTokenSilently. */
  useLayoutEffect(() => {
    setCustomerAccessTokenGetter(async (opts?: CustomerTokenOptions) => {
      const audience = import.meta.env.VITE_AUTH0_AUDIENCE?.trim()
      const authorizationParams = audience ? { audience } : undefined
      const base = {
        authorizationParams,
        cacheMode: (opts?.cacheMode ?? 'on') as 'on' | 'off' | 'cache-only',
      }
      try {
        return await getTokenRef.current(base)
      } catch {
        if (opts?.cacheMode === 'off') return null
        try {
          return await getTokenRef.current({
            authorizationParams,
            cacheMode: 'off',
          })
        } catch {
          return null
        }
      }
    })
    return () => setCustomerAccessTokenGetter(null)
  }, [])
  return null
}

function Auth0SessionShell({ children }: { children: ReactNode }) {
  const auth0 = useAuth0()
  const value = useMemo<CustomerSession>(
    () => ({
      mode: 'auth0',
      isLoading: auth0.isLoading,
      isAuthenticated: auth0.isAuthenticated,
      login: () =>
        auth0.loginWithRedirect({
          authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE?.trim() || undefined,
            redirect_uri: window.location.origin,
          },
        }),
      logout: () =>
        auth0.logout({
          logoutParams: { returnTo: window.location.origin },
        }),
      userEmail: auth0.user?.email,
    }),
    [auth0],
  )
  return (
    <CustomerSessionProvider value={value}>
      <Auth0AccessTokenBridge />
      {children}
    </CustomerSessionProvider>
  )
}

export function Auth0Root({ children }: { children: ReactNode }) {
  if (!auth0Configured()) {
    return (
      <CustomerSessionProvider value={{ mode: 'disabled' }}>
        <ClearCustomerTokenGetter />
        {children}
      </CustomerSessionProvider>
    )
  }

  const domain = String(import.meta.env.VITE_AUTH0_DOMAIN).trim()
  const clientId = String(import.meta.env.VITE_AUTH0_CLIENT_ID).trim()
  const audience = import.meta.env.VITE_AUTH0_AUDIENCE?.trim()

  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: window.location.origin,
        audience: audience || undefined,
      }}
      cacheLocation="localstorage"
      useRefreshTokens
      useRefreshTokensFallback
    >
      <Auth0SessionShell>{children}</Auth0SessionShell>
    </Auth0Provider>
  )
}
