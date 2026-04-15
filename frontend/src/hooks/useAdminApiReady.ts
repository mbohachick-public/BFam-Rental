import { useAuth } from '../context/AuthContext'
import { useCustomerSession } from '../context/CustomerSessionContext'

/** True when admin API calls can run: stub token and/or Auth0 “continue to admin” session. */
export function useAdminApiReady(): boolean {
  const { adminToken, adminAuth0Session } = useAuth()
  const customer = useCustomerSession()
  if (adminToken?.trim()) return true
  if (customer.mode === 'auth0' && customer.isAuthenticated && adminAuth0Session) return true
  return false
}
