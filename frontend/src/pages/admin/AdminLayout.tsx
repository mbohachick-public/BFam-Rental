import { Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAdminApiReady } from '../../hooks/useAdminApiReady'

export function AdminLayout() {
  const location = useLocation()
  const adminApiReady = useAdminApiReady()

  if (!adminApiReady) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
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
      </nav>
      <Outlet />
    </div>
  )
}
