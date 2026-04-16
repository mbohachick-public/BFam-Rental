import { useAuth } from '../context/AuthContext'
import { useCustomerSession } from '../context/CustomerSessionContext'

/** True when admin API calls can run: Auth0 session + explicit “Continue to admin”. */
export function useAdminApiReady(): boolean {
  const { adminAuth0Session } = useAuth()
  const customer = useCustomerSession()
  if (customer.mode !== 'auth0') return false
  return customer.isAuthenticated && adminAuth0Session
}
