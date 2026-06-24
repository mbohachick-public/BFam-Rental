import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiGetPaymentStatus } from '../api/client'
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
  const bookingIdOk = Boolean(bookingId)
  const [data, setData] = useState<BookingPaymentStatusPublic | null>(null)
  const [error, setError] = useState<string | null>(null)

  const signToken = useMemo(() => {
    if (!bookingIdOk) return null
    try {
      return sessionStorage.getItem(SIGN_TOKEN_KEY(bookingId))
    } catch {
      return null
    }
  }, [bookingId, bookingIdOk])

  useEffect(() => {
    if (!bookingIdOk) return
    let cancelled = false
    apiGetPaymentStatus<BookingPaymentStatusPublic>(bookingId, signToken)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
    return () => {
      cancelled = true
    }
  }, [bookingId, bookingIdOk])

  if (!bookingIdOk) {
    return (
      <div className="container">
        <h1>Payment</h1>
        <p className="error-msg">Missing booking reference.</p>
        <Link to="/catalog">Back to catalog</Link>
      </div>
    )
  }

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
  const requiresDeposit = Boolean(data.requires_deposit)
  const depositStatus = requiresDeposit
    ? data.deposit_secured
      ? 'Hold secured'
      : 'Not yet recorded'
    : 'Not required'

  return (
    <div className="container page-payment-success">
      <h1>You're confirmed</h1>
      <p>Your rental is confirmed and your payment/deposit status is complete.</p>

      <section className="card card-pad section-block" style={{ marginTop: '1rem' }}>
        <p style={{ margin: 0, fontWeight: 700 }}>
          We’ve sent your pickup or delivery instructions to your email address on file.
        </p>
      </section>

      <section className="card card-pad section-block" style={{ marginTop: '1rem' }}>
        <h2 className="h3" style={{ marginTop: 0 }}>
          Please check your email before heading out. It includes:
        </h2>
        <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
          <li>Pickup time and location, or delivery details</li>
          <li>What to bring</li>
          <li>Trailer return instructions</li>
          <li>Contact info if anything looks wrong</li>
        </ul>
      </section>

      <p className="muted small" style={{ marginTop: '0.75rem' }}>
        Payment status may take a moment to update while Stripe webhooks finish processing.
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
          <div>
            <dt>Security deposit</dt>
            <dd>{depositStatus}</dd>
          </div>
          <div>
            <dt>Next step</dt>
            <dd>Check your email for pickup/delivery instructions</dd>
          </div>
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
        Didn’t receive the email? Check your spam folder or contact {LEGAL_BUSINESS_NAME}.
      </p>
      <p style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <Link to="/my-rentals" className="btn btn-primary">
          Open My Rentals
        </Link>
        <Link to="/catalog" className="btn">
          Back to Catalog
        </Link>
      </p>
    </div>
  )
}
