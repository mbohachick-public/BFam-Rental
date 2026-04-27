import { Link, NavLink, Outlet } from 'react-router-dom'
import { auth0Configured } from '../../auth0/config'
import { useCustomerSession } from '../../context/CustomerSessionContext'
import { useAdminApiDenied, useAdminApiPending, useAdminApiReady } from '../../hooks/useAdminApiReady'

export function AdminLayout() {
  const customer = useCustomerSession()
  const adminApiReady = useAdminApiReady()
  const adminApiPending = useAdminApiPending()
  const adminDenied = useAdminApiDenied()

  if (customer.mode === 'disabled') {
    const auth0On = auth0Configured()
    return (
      <div className="container page-admin-gate">
        <div className="card card-pad admin-login-card">
          <h1>Admin</h1>
          {auth0On ? (
            <p className="muted">Sign in from the main site header, then open Admin again.</p>
          ) : (
            <p className="muted">
              Admin requires Auth0: set <code>VITE_AUTH0_DOMAIN</code>, <code>VITE_AUTH0_CLIENT_ID</code>, and{' '}
              <code>VITE_AUTH0_AUDIENCE</code> on the site, and <code>AUTH0_DOMAIN</code> /{' '}
              <code>AUTH0_AUDIENCE</code> on the API. Your access token is sent as{' '}
              <code>Authorization: Bearer</code> on all <code>/admin</code> requests.
            </p>
          )}
          <p>
            <Link to="/" className="nav-link">
              Back to site
            </Link>
          </p>
        </div>
      </div>
    )
  }

  if (customer.isLoading || adminApiPending) {
    return (
      <div className="container">
        <p className="muted">Checking admin access…</p>
      </div>
    )
  }

  if (!customer.isAuthenticated) {
    return (
      <div className="container page-admin-gate">
        <div className="card card-pad admin-login-card">
          <h1>Admin</h1>
          <p className="muted">Sign in to access the admin area.</p>
          <button type="button" className="btn btn-primary" onClick={() => customer.login()}>
            Sign in with Auth0
          </button>
          <p>
            <Link to="/" className="nav-link">
              Back to site
            </Link>
          </p>
        </div>
      </div>
    )
  }

  if (adminDenied) {
    return (
      <div className="container page-admin-gate">
        <div className="card card-pad admin-login-card">
          <h1>Admin access</h1>
          <p className="muted">This account is not authorized for admin (check API admin rules in the backend README).</p>
          <p>
            <Link to="/" className="nav-link">
              Back to site
            </Link>
          </p>
        </div>
      </div>
    )
  }

  if (!adminApiReady) {
    return (
      <div className="container">
        <p className="muted">Checking admin access…</p>
      </div>
    )
  }

  return (
    <div className="container admin-shell">
      <nav className="admin-subnav card card-pad" aria-label="Admin">
        <NavLink to="/admin/items" className="nav-link" end>
          Items
        </NavLink>
        <NavLink to="/admin/bookings" className="nav-link">
          Booking requests
        </NavLink>
        <NavLink to="/admin/delivery-settings" className="nav-link">
          Delivery
        </NavLink>
      </nav>
      <Outlet />
    </div>
  )
}
