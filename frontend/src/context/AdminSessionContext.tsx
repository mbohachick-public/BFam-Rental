import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { adminGet } from '../api/client'
import { useCustomerSession } from './CustomerSessionContext'

export type AdminSessionValue = {
  /** True after GET /admin/session succeeds for the current access token. */
  ready: boolean
  /** True while verifying admin access with the API. */
  pending: boolean
  /** True after GET /admin/session failed (e.g. not an admin account). */
  denied: boolean
}

const AdminSessionContext = createContext<AdminSessionValue | null>(null)

export function AdminSessionProvider({ children }: { children: ReactNode }) {
  const customer = useCustomerSession()
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'denied'>('idle')

  useEffect(() => {
    let base = false
    if (customer.mode === 'auth0') {
      base = !customer.isLoading && customer.isAuthenticated
    }

    if (!base) {
      setStatus('idle')
      return
    }

    let cancelled = false
    setStatus('loading')

    adminGet<{ admin: boolean }>('/admin/session')
      .then(() => {
        if (!cancelled) setStatus('ok')
      })
      .catch(() => {
        if (!cancelled) setStatus('denied')
      })

    return () => {
      cancelled = true
    }
  }, [customer])

  const value = useMemo<AdminSessionValue>(
    () => ({
      ready: status === 'ok',
      pending: status === 'loading',
      denied: status === 'denied',
    }),
    [status],
  )

  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>
}

export function useAdminSession(): AdminSessionValue {
  const ctx = useContext(AdminSessionContext)
  if (!ctx) throw new Error('useAdminSession must be used within AdminSessionProvider')
  return ctx
}
