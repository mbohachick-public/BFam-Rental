import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { auth0Configured, e2eDevAuth0AccessToken } from '../../auth0/config'
import { useAuth } from '../../context/AuthContext'
import { useCustomerSession } from '../../context/CustomerSessionContext'

export function AdminLoginPage() {
  const { adminAuth0Session, setAdminAuth0Session } = useAuth()
  const customer = useCustomerSession()
  const location = useLocation()
  const navigate = useNavigate()
  const from = (location.state as { from?: string } | null)?.from ?? '/admin/items'

  const e2eToken = e2eDevAuth0AccessToken()
  const auth0On = auth0Configured() && customer.mode === 'auth0'
  const signedIn = customer.mode === 'auth0' && customer.isAuthenticated && !customer.isLoading

  if (adminAuth0Session && signedIn) {
    return <Navigate to={from} replace />
  }

  if (signedIn) {
    return (
      <div className="container page-admin-login">
        <div className="card card-pad admin-login-card">
          <h1>Admin</h1>
          {e2eToken ? (
            <p className="muted">
              E2E mode is using a fixed access token. Continue to open the admin area (the API must accept this
              JWT as an admin).
            </p>
          ) : (
            <p className="muted">
              You are signed in as <strong>{customer.userEmail ?? 'your account'}</strong>. Continue if this user
              is allowed as an admin in the API (Auth0 role / email / sub — see backend README).
            </p>
          )}
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setAdminAuth0Session(true)
              navigate(from, { replace: true })
            }}
          >
            Continue to admin
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="container page-admin-login">
      <div className="card card-pad admin-login-card">
        <h1>Admin sign-in</h1>
        {auth0On ? (
          <>
            <p className="muted">
              Sign in with your account (top of the site), then return here and choose <strong>Continue to admin</strong>.
            </p>
            {customer.isLoading ? (
              <p className="muted">Loading…</p>
            ) : (
              <button type="button" className="btn btn-primary" onClick={() => customer.login()}>
                Sign in with Auth0
              </button>
            )}
          </>
        ) : (
          <p className="muted">
            Admin requires Auth0: set <code>VITE_AUTH0_DOMAIN</code>, <code>VITE_AUTH0_CLIENT_ID</code>, and{' '}
            <code>VITE_AUTH0_AUDIENCE</code> on the site, and <code>AUTH0_DOMAIN</code> / <code>AUTH0_AUDIENCE</code>{' '}
            on the API. Your access token is sent as <code>Authorization: Bearer</code> on all <code>/admin</code>{' '}
            requests.
          </p>
        )}
      </div>
    </div>
  )
}
