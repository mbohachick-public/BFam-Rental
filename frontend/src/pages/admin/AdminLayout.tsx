import { Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export function AdminLayout() {
  const { adminToken } = useAuth()
  const location = useLocation()

  if (!adminToken) {
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
