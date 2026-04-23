import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Auth0Root } from './components/Auth0Root'
import { Layout } from './components/Layout'
import { AuthProvider } from './context/AuthContext'
import { CatalogPage } from './pages/CatalogPage'
import { HomePage } from './pages/HomePage'
import { ItemDetailPage } from './pages/ItemDetailPage'
import { MyRentalsPage } from './pages/MyRentalsPage'
import { AdminAvailabilityPage } from './pages/admin/AdminAvailabilityPage'
import { AdminBookingDetailPage } from './pages/admin/AdminBookingDetailPage'
import { AdminBookingsPage } from './pages/admin/AdminBookingsPage'
import { AdminDeliverySettingsPage } from './pages/admin/AdminDeliverySettingsPage'
import { AdminItemFormPage } from './pages/admin/AdminItemFormPage'
import { AdminItemsPage } from './pages/admin/AdminItemsPage'
import { AdminLayout } from './pages/admin/AdminLayout'
import { AdminLoginPage } from './pages/admin/AdminLoginPage'
import { BookingSignCompletePage } from './pages/BookingSignCompletePage'
import { BookingSignPage } from './pages/BookingSignPage'
import { PaymentSuccessPage } from './pages/PaymentSuccessPage'

export default function App() {
  return (
    <Auth0Root>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<HomePage />} />
              <Route path="catalog" element={<CatalogPage />} />
              <Route path="items/:id" element={<ItemDetailPage />} />
              <Route path="my-rentals" element={<MyRentalsPage />} />
              <Route path="booking-actions/:token/sign" element={<BookingSignPage />} />
              <Route path="booking-actions/:token/complete" element={<BookingSignCompletePage />} />
              <Route path="payment-success" element={<PaymentSuccessPage />} />
            </Route>
            <Route path="/admin/login" element={<AdminLoginPage />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="/admin/items" replace />} />
              <Route path="items" element={<AdminItemsPage />} />
              <Route path="items/new" element={<AdminItemFormPage />} />
              <Route path="items/:id/edit" element={<AdminItemFormPage />} />
              <Route path="items/:id/availability" element={<AdminAvailabilityPage />} />
              <Route path="bookings" element={<AdminBookingsPage />} />
              <Route path="bookings/:id" element={<AdminBookingDetailPage />} />
              <Route path="delivery-settings" element={<AdminDeliverySettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </Auth0Root>
  )
}
