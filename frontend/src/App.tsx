import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AuthProvider } from './context/AuthContext'
import { CatalogPage } from './pages/CatalogPage'
import { HomePage } from './pages/HomePage'
import { ItemDetailPage } from './pages/ItemDetailPage'
import { AdminAvailabilityPage } from './pages/admin/AdminAvailabilityPage'
import { AdminBookingsPage } from './pages/admin/AdminBookingsPage'
import { AdminItemFormPage } from './pages/admin/AdminItemFormPage'
import { AdminItemsPage } from './pages/admin/AdminItemsPage'
import { AdminLayout } from './pages/admin/AdminLayout'
import { AdminLoginPage } from './pages/admin/AdminLoginPage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="catalog" element={<CatalogPage />} />
            <Route path="items/:id" element={<ItemDetailPage />} />
          </Route>
          <Route path="/admin/login" element={<AdminLoginPage />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<Navigate to="/admin/items" replace />} />
            <Route path="items" element={<AdminItemsPage />} />
            <Route path="items/new" element={<AdminItemFormPage />} />
            <Route path="items/:id/edit" element={<AdminItemFormPage />} />
            <Route path="items/:id/availability" element={<AdminAvailabilityPage />} />
            <Route path="bookings" element={<AdminBookingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
