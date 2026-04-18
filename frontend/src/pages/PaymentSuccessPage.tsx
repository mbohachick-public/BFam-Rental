import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiGetPublic } from '../api/client'
import type { BookingPaymentStatusPublic } from '../types'

export function PaymentSuccessPage() {
  const [params] = useSearchParams()
  const bookingId = params.get('booking_id')?.trim() ?? ''
  const [data, setData] = useState<BookingPaymentStatusPublic | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!bookingId) {
      setError('Missing booking reference.')
      return
    }
    let cancelled = false
    apiGetPublic<BookingPaymentStatusPublic>(
      `/booking-requests/${encodeURIComponent(bookingId)}/payment-status`,
    )
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
    return () => {
      cancelled = true
    }
  }, [bookingId])

  if (error) {
    return (
      <div className="container">
        <h1>Payment</h1>
        <p className="error-msg">{error}</p>
        <Link to="/catalog">Back to catalog</Link>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="container">
        <p className="muted">Loading…</p>
      </div>
    )
  }

  return (
    <div className="container page-payment-success">
      <h1>Thank you</h1>
      <p className="muted">
        Stripe reported your payment. This page is informational only — final confirmation still
        requires deposit and agreement steps from BFam Rentals.
      </p>
      <section className="card card-pad section-block">
        <h2>Booking</h2>
        <dl className="attr-list">
          <div>
            <dt>Equipment</dt>
            <dd>{data.item_title}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{data.status}</dd>
          </div>
          <div>
            <dt>Rental payment</dt>
            <dd>{data.rental_paid ? 'Received' : 'Not yet recorded'}</dd>
          </div>
        </dl>
      </section>
      <p className="muted small">
        If rental payment still shows as pending after a few minutes, contact BFam Rentals with
        your booking reference.
      </p>
      <p>
        <Link to="/catalog">Back to catalog</Link>
      </p>
    </div>
  )
}
