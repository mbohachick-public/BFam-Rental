import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiGetPublic } from '../api/client'
import type { BookingSignCompleteOut } from '../types'

export function BookingSignCompletePage() {
  const { token } = useParams<{ token: string }>()
  const [data, setData] = useState<BookingSignCompleteOut | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setError('Missing link.')
      return
    }
    let cancelled = false
    apiGetPublic<BookingSignCompleteOut>(
      `/booking-actions/${encodeURIComponent(token)}/complete`,
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
  }, [token])

  if (error) {
    return (
      <div className="container">
        <h1>Next steps</h1>
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

  const rentalUrl = data.stripe_checkout_url?.trim() || ''
  const depositUrl = data.stripe_deposit_checkout_url?.trim() || ''
  const pendingCard =
    data.booking_status === 'approved_pending_payment' && data.payment_path === 'card'
  const showRentalPay =
    Boolean(rentalUrl) && !data.rental_balance_paid && pendingCard
  const showDepositPay = Boolean(depositUrl) && !data.deposit_secured && pendingCard

  const waitingForRentalLink = pendingCard && !data.rental_balance_paid && !rentalUrl

  return (
    <div className="container page-booking-sign">
      <h1>Agreement received</h1>
      <p className="success-msg">{data.message}</p>
      {data.booking_status ? (
        <p className="muted">
          Current status: <strong>{data.booking_status}</strong>
        </p>
      ) : null}
      {showRentalPay ? (
        <section className="card card-pad section-block" style={{ marginTop: '1rem' }}>
          <h2 className="h3">1) Pay rental balance</h2>
          <p className="muted">
            This secure checkout is only for the <strong>rental total (with tax)</strong> — not the
            security deposit.
          </p>
          <p>
            <a className="btn btn-primary" href={rentalUrl} target="_blank" rel="noreferrer">
              Open rental payment (Stripe)
            </a>
          </p>
        </section>
      ) : null}
      {showDepositPay ? (
        <section className="card card-pad section-block" style={{ marginTop: '1rem' }}>
          <h2 className="h3">2) Pay security deposit</h2>
          <p className="muted">
            Separate checkout for the <strong>refundable security deposit</strong>. Complete this
            after or before the rental payment unless BFam tells you otherwise.
          </p>
          <p>
            <a className="btn btn-primary" href={depositUrl} target="_blank" rel="noreferrer">
              Open deposit payment (Stripe)
            </a>
          </p>
        </section>
      ) : null}
      {(showRentalPay || showDepositPay) && (
        <p className="muted small" style={{ marginTop: '1rem' }}>
          Signed in with the same email as this booking? Open{' '}
          <Link to="/my-rentals">My rentals</Link> — the same links appear there after they are
          generated.
        </p>
      )}
      {waitingForRentalLink ? (
        <p className="muted" style={{ marginTop: '1rem' }}>
          <strong>Card payment:</strong> BFam Rentals will email you separate Stripe links for the
          rental total and security deposit when they are ready. Check{' '}
          <Link to="/my-rentals">My rentals</Link> after signing in, or watch your inbox.
        </p>
      ) : null}
      {!pendingCard ? (
        <p className="muted">
          Next: complete payment and deposit requirements using the instructions from BFam Rentals.
          Your rental is not confirmed until those steps are complete.
        </p>
      ) : null}
      {data.rental_balance_paid ? (
        <p className="muted small">
          Rental balance has been recorded as paid; complete the deposit checkout if you still owe
          the security deposit.
        </p>
      ) : null}
      {data.deposit_secured && !data.rental_balance_paid ? (
        <p className="muted small">Security deposit received; rental payment may still be due.</p>
      ) : null}
      <p style={{ marginTop: '1rem' }}>
        <Link to="/catalog">Back to catalog</Link>
      </p>
    </div>
  )
}
