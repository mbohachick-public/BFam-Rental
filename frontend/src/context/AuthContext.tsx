import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

/** Legacy stub token storage — removed; clear so old values are not mistaken for secrets. */
const LEGACY_ADMIN_TOKEN_KEY = 'bfam_admin_token'

/** Session flag: user chose “Continue to admin” after Auth0 sign-in (see Admin login). */
const ADMIN_AUTH0_SESSION_KEY = 'bfam_admin_auth0_session'

function readAdminAuth0Session(): boolean {
  try {
    return sessionStorage.getItem(ADMIN_AUTH0_SESSION_KEY) === '1'
  } catch {
    return false
  }
}

type AuthContextValue = {
  /** True after explicit “Continue to admin” while the SPA uses Auth0 Bearer for /admin. */
  adminAuth0Session: boolean
  setAdminAuth0Session: (active: boolean) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [adminAuth0Session, setAdminAuth0SessionState] = useState(() => readAdminAuth0Session())

  useEffect(() => {
    try {
      localStorage.removeItem(LEGACY_ADMIN_TOKEN_KEY)
    } catch {
      /* ignore */
    }
  }, [])

  const setAdminAuth0Session = useCallback((active: boolean) => {
    setAdminAuth0SessionState(active)
    try {
      if (active) sessionStorage.setItem(ADMIN_AUTH0_SESSION_KEY, '1')
      else sessionStorage.removeItem(ADMIN_AUTH0_SESSION_KEY)
    } catch {
      /* ignore */
    }
  }, [])

  const logout = useCallback(() => {
    setAdminAuth0Session(false)
  }, [setAdminAuth0Session])

  const value = useMemo(
    () => ({
      adminAuth0Session,
      setAdminAuth0Session,
      logout,
    }),
    [adminAuth0Session, setAdminAuth0Session, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
