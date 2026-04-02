import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function Layout() {
  const { adminToken, logout } = useAuth()

  return (
    <div className="layout">
      <header className="site-header">
        <div className="container header-inner">
          <Link to="/" className="brand">
            <img src="/logo.png" alt="" width={44} height={44} className="brand-logo" />
            <span className="brand-text">
              <span className="brand-name">BFam</span>
              <span className="brand-tag">Rental</span>
            </span>
          </Link>
          <nav className="nav-main" aria-label="Main">
            <NavLink to="/" end className="nav-link">
              Home
            </NavLink>
            <NavLink to="/catalog" className="nav-link">
              Catalog
            </NavLink>
            {adminToken ? (
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
          <p>BFam Rental — equipment &amp; trailer rentals.</p>
        </div>
      </footer>
    </div>
  )
}
