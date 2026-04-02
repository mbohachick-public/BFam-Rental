import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

const STORAGE_KEY = 'bfam_admin_token'

type AuthContextValue = {
  adminToken: string | null
  setAdminToken: (token: string | null) => void
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

  const setAdminToken = useCallback((token: string | null) => {
    setTokenState(token)
    try {
      if (token) localStorage.setItem(STORAGE_KEY, token)
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }, [])

  const logout = useCallback(() => {
    setAdminToken(null)
  }, [setAdminToken])

  const value = useMemo(
    () => ({ adminToken, setAdminToken, logout }),
    [adminToken, setAdminToken, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
