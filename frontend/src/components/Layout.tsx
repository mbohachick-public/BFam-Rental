import { Link, NavLink, Outlet } from 'react-router-dom'
import { LEGAL_BUSINESS_NAME, OFFER_TAGLINE, SERVICE_AREA_TAGLINE } from '../branding'
import { useAuth } from '../context/AuthContext'
import { useCustomerSession } from '../context/CustomerSessionContext'
import { useAdminApiReady } from '../hooks/useAdminApiReady'

export function Layout() {
  const { logout } = useAuth()
  const customer = useCustomerSession()
  const adminApiReady = useAdminApiReady()

  return (
    <div className="layout">
      <header className="site-header">
        <div className="container header-inner">
          <Link to="/" className="brand">
            <img src="/favicon_v2.png" alt="" width={48} height={48} className="brand-logo" />
            <span className="brand-text">
              <span className="brand-name brand-name-legal">{LEGAL_BUSINESS_NAME}</span>
            </span>
          </Link>
          <nav className="nav-main" aria-label="Main">
            <NavLink to="/" end className="nav-link">
              Home
            </NavLink>
            <NavLink to="/catalog" className="nav-link">
              Catalog
            </NavLink>
            {customer.mode === 'auth0' && !customer.isLoading && (
              <>
                {customer.isAuthenticated ? (
                  <>
                    <NavLink to="/my-rentals" className="nav-link">
                      My rentals
                    </NavLink>
                    <span className="nav-customer-email" title={customer.userEmail}>
                      {customer.userEmail ?? 'Signed in'}
                    </span>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => customer.logout()}
                    >
                      Sign out
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => customer.login()}
                  >
                    Sign in
                  </button>
                )}
              </>
            )}
            {adminApiReady ? (
              <>
                <NavLink to="/admin/items" className="nav-link">
                  Admin
                </NavLink>
                <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>
                  Admin out
                </button>
              </>
            ) : (
              <NavLink to="/admin/login" className="nav-link">
                Admin
              </NavLink>
            )}
          </nav>
        </div>
      </header>
      <main className="main-content">
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="container footer-inner">
          <p className="footer-brand-line footer-legal-name">{LEGAL_BUSINESS_NAME}</p>
          <p className="footer-offer">{OFFER_TAGLINE}</p>
          <p className="footer-service-area">{SERVICE_AREA_TAGLINE}</p>
        </div>
      </footer>
    </div>
  )
}
