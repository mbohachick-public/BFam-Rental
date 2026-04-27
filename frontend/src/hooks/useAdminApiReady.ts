import { useAdminSession } from '../context/AdminSessionContext'

/** True when the access token is accepted as admin by GET /admin/session. */
export function useAdminApiReady(): boolean {
  return useAdminSession().ready
}

/** True while verifying admin access with the API. */
export function useAdminApiPending(): boolean {
  return useAdminSession().pending
}

/** True when the current user is signed in but not accepted as admin by the API. */
export function useAdminApiDenied(): boolean {
  return useAdminSession().denied
}
