import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiGetPublic } from '../api/client'
import { LEGAL_BUSINESS_NAME } from '../branding'
import type { BookingSignCompleteOut } from '../types'

const SIGN_TOKEN_KEY = (bookingId: string) => `bfam_sign_token:${bookingId}`

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

  useEffect(() => {
    if (!token || !data?.booking_id) return
    try {
      sessionStorage.setItem(SIGN_TOKEN_KEY(data.booking_id), token)
    } catch {
      /* ignore quota / private mode */
    }
  }, [token, data?.booking_id])

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
  const rentalDone = data.rental_balance_paid
  const depositDone = data.deposit_secured
  const bothStripeSteps = showRentalPay && showDepositPay
  const rentalIsNext = showRentalPay && (!bothStripeSteps || !rentalDone)
  const depositIsNext = showDepositPay && (!bothStripeSteps || rentalDone)

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

      {pendingCard && (showRentalPay || showDepositPay) ? (
        <section className="card card-pad section-block payment-steps-card" style={{ marginTop: '1rem' }}>
          <h2 className="h3">Pay online (card)</h2>
          <p className="muted small">
            Complete each step below in order. You will use separate Stripe checkouts for the rental
            total and the security deposit (hold).
          </p>

          {showRentalPay ? (
            <div
              className={`payment-step ${rentalIsNext ? 'payment-step-active' : 'payment-step-done'}`}
            >
              <h3 className="payment-step-title">
                <span className="payment-step-num">1</span>
                {rentalDone ? 'Rental total — paid' : 'Rental total (with tax)'}
              </h3>
              {!rentalDone ? (
                <>
                  <p className="muted small">
                    This checkout is only for the <strong>rental total (with tax)</strong>, not the
                    deposit.
                  </p>
                  <p>
                    <a className="btn btn-primary" href={rentalUrl}>
                      Pay rental total (Stripe)
                    </a>
                  </p>
                </>
              ) : (
                <p className="muted small">Recorded — continue to the deposit if required.</p>
              )}
            </div>
          ) : null}

          {showDepositPay ? (
            <div
              className={`payment-step ${depositIsNext && (rentalDone || !showRentalPay) ? 'payment-step-active' : ''} ${bothStripeSteps && !rentalDone ? 'payment-step-wait' : ''} ${depositDone ? 'payment-step-done' : ''}`}
            >
              <h3 className="payment-step-title">
                <span className="payment-step-num">{showRentalPay ? '2' : '1'}</span>
                {depositDone ? 'Security deposit — secured' : 'Security deposit (card hold)'}
              </h3>
              {bothStripeSteps && !rentalDone ? (
                <p className="muted small">
                  <strong>Next:</strong> complete step 1 first, then return to this page (bookmark it
                  or use the link from your Stripe receipt page).
                </p>
              ) : !depositDone ? (
                <>
                  <p className="muted small">
                    Separate checkout for the <strong>refundable security deposit</strong> (authorization
                    hold unless {LEGAL_BUSINESS_NAME} tells you otherwise).
                  </p>
                  <p>
                    <a className="btn btn-primary" href={depositUrl}>
                      Place deposit hold (Stripe)
                    </a>
                  </p>
                </>
              ) : (
                <p className="muted small">Deposit hold recorded.</p>
              )}
            </div>
          ) : null}
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
          <strong>Card payment:</strong> {LEGAL_BUSINESS_NAME} will email you separate Stripe links
          for the
          rental total and security deposit when they are ready. Check{' '}
          <Link to="/my-rentals">My rentals</Link> after signing in, or watch your inbox.
        </p>
      ) : null}
      {!pendingCard ? (
        <p className="muted">
          Next: complete payment and deposit requirements using the instructions from{' '}
          {LEGAL_BUSINESS_NAME}.
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
