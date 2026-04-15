import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

const STORAGE_KEY = 'bfam_admin_token'
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
  adminToken: string | null
  setAdminToken: (token: string | null) => void
  /** True after explicit “Continue to admin” while Auth0 session is used for /admin (no stub). */
  adminAuth0Session: boolean
  setAdminAuth0Session: (active: boolean) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [adminToken, setTokenState] = useState<string | null>(() => readStoredToken())
  const [adminAuth0Session, setAdminAuth0SessionState] = useState(() => readAdminAuth0Session())

  const setAdminToken = useCallback((token: string | null) => {
    setTokenState(token)
    try {
      if (token) localStorage.setItem(STORAGE_KEY, token)
      else localStorage.removeItem(STORAGE_KEY)
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
    setAdminToken(null)
    setAdminAuth0Session(false)
  }, [setAdminToken, setAdminAuth0Session])

  const value = useMemo(
    () => ({
      adminToken,
      setAdminToken,
      adminAuth0Session,
      setAdminAuth0Session,
      logout,
    }),
    [adminToken, setAdminToken, adminAuth0Session, setAdminAuth0Session, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
