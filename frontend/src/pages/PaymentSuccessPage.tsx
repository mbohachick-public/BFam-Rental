import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiGetPublic } from '../api/client'
import { LEGAL_BUSINESS_NAME } from '../branding'
import type { BookingPaymentStatusPublic } from '../types'

const SIGN_TOKEN_KEY = (bookingId: string) => `bfam_sign_token:${bookingId}`

/** Customer-facing copy; internal statuses stay unchanged in the API. */
function customerFacingBookingStatus(status: string): string {
  switch (status) {
    case 'approved_pending_payment':
    case 'approved_pending_check_clearance':
      return 'Waiting for final confirmation'
    case 'approved_awaiting_signature':
      return 'Waiting for your signature'
    case 'confirmed':
      return 'Confirmed'
    case 'ready_for_pickup':
      return 'Ready for pickup'
    case 'checked_out':
      return 'Checked out'
    case 'returned_pending_inspection':
      return 'Returned — inspection pending'
    case 'completed':
      return 'Completed'
    case 'completed_with_charges':
      return 'Completed (with charges)'
    case 'declined':
    case 'rejected':
      return 'Not approved'
    case 'cancelled':
      return 'Cancelled'
    case 'pending':
    case 'requested':
    case 'under_review':
      return 'In review'
    default:
      return status
        .split('_')
        .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : w))
        .join(' ')
  }
}

export function PaymentSuccessPage() {
  const [params] = useSearchParams()
  const bookingId = params.get('booking_id')?.trim() ?? ''
  const [data, setData] = useState<BookingPaymentStatusPublic | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [signToken, setSignToken] = useState<string | null>(null)

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

  useEffect(() => {
    if (!bookingId) return
    try {
      setSignToken(sessionStorage.getItem(SIGN_TOKEN_KEY(bookingId)))
    } catch {
      setSignToken(null)
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

  const fullyDone =
    data.rental_paid && (!data.requires_deposit || data.deposit_secured)
  const continuePaymentHref =
    signToken && !fullyDone
      ? `/booking-actions/${encodeURIComponent(signToken)}/complete`
      : null

  return (
    <div className="container page-payment-success">
      <h1>Thank you</h1>
      <p className="muted">
        Stripe sent you back here after checkout. Payment status below may take a moment to update
        while webhooks process.
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
            <dd>{customerFacingBookingStatus(data.status)}</dd>
          </div>
          <div>
            <dt>Rental payment</dt>
            <dd>{data.rental_paid ? 'Received' : 'Not yet recorded'}</dd>
          </div>
          {data.requires_deposit ? (
            <div>
              <dt>Security deposit</dt>
              <dd>{data.deposit_secured ? 'Hold secured' : 'Not yet recorded'}</dd>
            </div>
          ) : null}
        </dl>
      </section>
      {continuePaymentHref ? (
        <section className="card card-pad section-block" style={{ marginTop: '1rem' }}>
          <h2 className="h3">More steps?</h2>
          <p className="muted small">
            If you still owe the rental total or the deposit hold, open your payment checklist to
            continue.
          </p>
          <p>
            <Link className="btn btn-primary" to={continuePaymentHref}>
              Continue payment steps
            </Link>
          </p>
        </section>
      ) : null}
      <p className="muted small">
        If something still looks wrong after a few minutes, contact {LEGAL_BUSINESS_NAME} with your
        booking reference.
      </p>
      <p>
        <Link to="/catalog">Back to catalog</Link>
      </p>
    </div>
  )
}
