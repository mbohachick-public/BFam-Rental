import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminDownloadBlob, adminGet, adminPost } from '../../api/client'
import { useAdminApiReady } from '../../hooks/useAdminApiReady'
import type {
  BookingRequestOut,
  ResendSignatureOut,
  StripeCheckoutSessionOut,
  StripeCheckoutSyncOut,
} from '../../types'

async function openBookingDocument(url: string, label: string) {
  try {
    const blob = await adminDownloadBlob(url)
    const obj = URL.createObjectURL(blob)
    const w = window.open(obj, '_blank', 'noopener,noreferrer')
    if (!w) URL.revokeObjectURL(obj)
    else setTimeout(() => URL.revokeObjectURL(obj), 120_000)
  } catch (e) {
    window.alert(e instanceof Error ? e.message : `Could not open ${label}`)
  }
}

function money(s: string | null | undefined) {
  if (s == null) return '—'
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

function isRequestedLike(status: string) {
  return status === 'requested' || status === 'pending' || status === 'under_review'
}

function isPreConfirmApproved(status: string) {
  return status === 'approved_pending_payment' || status === 'approved_pending_check_clearance'
}

function isAwaitingSignature(status: string) {
  return status === 'approved_awaiting_signature'
}

function stripeCheckoutEligible(r: BookingRequestOut) {
  return (
    r.status === 'approved_pending_payment' &&
    r.payment_path === 'card' &&
    r.rental_total_with_tax != null &&
    Number(r.rental_total_with_tax) > 0
  )
}

function stripeDepositRefundEligible(r: BookingRequestOut) {
  if (r.deposit_refunded_at || !r.deposit_secured_at) return false
  const depPi = (r.stripe_deposit_payment_intent_id || '').trim()
  if (depPi) return true
  const cents = r.stripe_deposit_captured_cents
  return (
    typeof cents === 'number' &&
    cents > 0 &&
    Boolean(r.stripe_payment_intent_id)
  )
}

function truncateId(s: string | null | undefined, max = 14) {
  if (!s) return null
  return s.length > max ? `${s.slice(0, max)}…` : s
}

export function AdminBookingsPage() {
  const adminApiReady = useAdminApiReady()
  const [rows, setRows] = useState<BookingRequestOut[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [declineForId, setDeclineForId] = useState<string | null>(null)
  const [declineReason, setDeclineReason] = useState('')
  const [declineError, setDeclineError] = useState<string | null>(null)
  /** Latest signing URLs from approve/resend (list GET does not echo the token). */
  const [signingUrlById, setSigningUrlById] = useState<Record<string, string>>({})

  const load = useCallback(() => {
    if (!adminApiReady) return
    adminGet<BookingRequestOut[]>('/admin/booking-requests')
      .then(setRows)
      .catch((e: Error) => setError(e.message))
  }, [adminApiReady])

  useEffect(() => {
    load()
  }, [load])

  async function approve(r: BookingRequestOut) {
    if (!adminApiReady) return
    const id = r.id
    setBusyId(id)
    setError(null)
    try {
      const out = await adminPost<BookingRequestOut>(`/admin/booking-requests/${id}/approve`, {})
      if (out.signing_url) {
        setSigningUrlById((prev) => ({ ...prev, [id]: out.signing_url! }))
      }
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Approve failed')
    } finally {
      setBusyId(null)
    }
  }

  async function markAction(id: string, action: string) {
    if (!adminApiReady) return
    setBusyId(id)
    setError(null)
    try {
      await adminPost<BookingRequestOut>(`/admin/booking-requests/${id}/${action}`, {})
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`)
    } finally {
      setBusyId(null)
    }
  }

  async function resendSignature(id: string) {
    if (!adminApiReady) return
    setBusyId(id)
    setError(null)
    try {
      const out = await adminPost<ResendSignatureOut>(
        `/admin/booking-requests/${id}/resend-signature`,
        {},
      )
      setSigningUrlById((prev) => ({ ...prev, [id]: out.signing_url }))
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Resend failed')
    } finally {
      setBusyId(null)
    }
  }

  async function copySigningLink(url: string) {
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      window.prompt('Copy signing link:', url)
    }
  }

  async function copyText(url: string, label: string) {
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      window.prompt(`Copy ${label}:`, url)
    }
  }

  async function syncStripeCheckout(id: string) {
    if (!adminApiReady) return
    setBusyId(id)
    setError(null)
    try {
      const out = await adminPost<StripeCheckoutSyncOut>(
        `/admin/booking-requests/${id}/sync-stripe-checkout`,
        {},
      )
      window.alert(
        `Stripe sync finished:\n${out.actions.join('\n')}\n\nIf you still see unpaid here, ensure webhooks reach this API (e.g. stripe listen --forward-to localhost:8000/stripe/webhook).`,
      )
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Stripe sync failed')
    } finally {
      setBusyId(null)
    }
  }

  async function generateStripeCheckout(id: string) {
    if (!adminApiReady) return
    setBusyId(id)
    setError(null)
    try {
      const out = await adminPost<StripeCheckoutSessionOut>(
        `/admin/booking-requests/${id}/stripe-checkout-session`,
        {},
      )
      const es = out.stripe_checkout_email_status
      if (es === 'sent') {
        window.alert('Stripe links were saved and a payment email was sent to the customer.')
      } else if (es === 'skipped_payment_links_in_approval_email') {
        // Awaiting signature: email copy assumes signed agreement; use Resend signing email for links, or customer pays after signing.
      } else if (es && es !== 'sent') {
        const hint =
          es === 'skipped_no_smtp'
            ? 'Configure SMTP on the API (SMTP_HOST, SMTP_FROM, etc. in backend .env). Until then, use Copy rental link / Copy deposit link and send them to the customer manually.'
            : es === 'skipped_no_customer_email'
              ? 'This booking has no customer email on file; add one or send the Stripe links manually.'
              : es === 'skipped_no_payment_links'
                ? 'No checkout URLs were produced for this run (e.g. already paid); nothing was emailed.'
                : es.startsWith('failed_smtp')
                  ? `SMTP send failed: ${es.slice('failed_smtp:'.length)}`
                  : `Checkout email not sent (${es}).`
        setError(`Stripe links were saved, but the customer email was not sent. ${hint}`)
      }
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Stripe checkout failed')
    } finally {
      setBusyId(null)
    }
  }

  async function refundStripeDeposit(id: string) {
    if (!adminApiReady) return
    const row = rows.find((x) => x.id === id)
    const separate =
      typeof row?.stripe_deposit_payment_intent_id === 'string' &&
      row.stripe_deposit_payment_intent_id.trim().length > 0
    const isHold =
      separate &&
      row.deposit_secured_at &&
      !row.stripe_deposit_captured_cents
    const msg = separate
      ? isHold
        ? 'Release the card hold for the security deposit? This cancels the authorization in Stripe; no charge was taken on the deposit yet. The rental charge is a separate payment and is not affected.'
        : 'Refund the full security deposit charge on Stripe? The rental payment is a separate charge and is not affected.'
      : 'Issue a partial Stripe refund for the security deposit line on the combined rental payment? The rest of the rental charge stays captured.'
    if (!window.confirm(msg)) {
      return
    }
    setBusyId(id)
    setError(null)
    try {
      await adminPost<BookingRequestOut>(`/admin/booking-requests/${id}/refund-stripe-deposit`, {})
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Deposit refund failed')
    } finally {
      setBusyId(null)
    }
  }

  async function confirm(id: string) {
    if (!adminApiReady) return
    setBusyId(id)
    setError(null)
    try {
      await adminPost<BookingRequestOut>(`/admin/booking-requests/${id}/confirm`, {})
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Confirm failed')
    } finally {
      setBusyId(null)
    }
  }

  function openDecline(id: string) {
    setDeclineForId(id)
    setDeclineReason('')
    setDeclineError(null)
  }

  function closeDecline() {
    setDeclineForId(null)
    setDeclineReason('')
    setDeclineError(null)
  }

  async function confirmDecline() {
    if (!adminApiReady || !declineForId) return
    const reason = declineReason.trim()
    if (!reason) {
      setDeclineError('Please enter a reason for declining.')
      return
    }
    setDeclineError(null)
    setBusyId(declineForId)
    setError(null)
    try {
      const out = await adminPost<BookingRequestOut>(`/admin/booking-requests/${declineForId}/decline`, {
        reason,
      })
      closeDecline()
      load()
      if (out.decline_email_sent === false) {
        setError(
          'Decline saved, but the customer email was not sent (check SMTP or customer email on file).',
        )
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Decline failed')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="page-admin-bookings">
      <h1>Booking requests</h1>
      {error && <p className="error-msg">{error}</p>}
      <ul className="admin-table-list card">
        {rows.map((r) => {
          const canDecline =
            isRequestedLike(r.status) || isAwaitingSignature(r.status) || isPreConfirmApproved(r.status)
          const canApprove = isRequestedLike(r.status)
          const canMark = isPreConfirmApproved(r.status)
          const signUrl = signingUrlById[r.id] ?? r.signing_url ?? null
          const depositAmountNum = r.deposit_amount != null ? Number(r.deposit_amount) : 0
          const needsDeposit = Number.isFinite(depositAmountNum) && depositAmountNum > 0
          const rentalPaidOk =
            Boolean(r.rental_paid_at) || String(r.rental_payment_status || '').toLowerCase() === 'paid'
          const depositSecuredOk =
            !needsDeposit ||
            Boolean(r.deposit_secured_at) ||
            Boolean((r.stripe_deposit_payment_intent_id || '').trim())
          const readyToConfirm =
            canMark && rentalPaidOk && depositSecuredOk && Boolean(r.agreement_signed_at)
          return (
            <li key={r.id} className="admin-table-row admin-booking-row">
              <div>
                <strong>{r.status}</strong>
                <span className="muted">
                  {' '}
                  · {r.start_date} → {r.end_date}
                </span>
                <span className="admin-booking-detail-link">
                  {' '}
                  ·{' '}
                  <Link to={`/admin/bookings/${r.id}`} className="nav-link">
                    View full request
                  </Link>
                </span>
              </div>
              <div className="muted small">
                {[r.customer_first_name, r.customer_last_name].filter(Boolean).join(' ') || '—'}
                {r.customer_phone ? ` · ${r.customer_phone}` : ''}
                {r.customer_email ? ` · ${r.customer_email}` : ' · No email'}
              </div>
              {r.customer_address ? (
                <div className="muted small">{r.customer_address}</div>
              ) : null}
              {r.notes ? <div className="muted small">{r.notes}</div> : null}
              <div className="muted small">
                Customer payment preference:{' '}
                <strong>{r.payment_method_preference ?? '—'}</strong>
                {r.payment_path ? (
                  <>
                    {' '}
                    · Approved payment path: <strong>{r.payment_path}</strong>
                  </>
                ) : null}
              </div>
              {(r.status === 'rejected' || r.status === 'declined') && r.decline_reason ? (
                <div className="small admin-decline-reason">
                  <strong>Decline reason:</strong> {r.decline_reason}
                </div>
              ) : null}
              {isAwaitingSignature(r.status) ? (
                <div className="muted small admin-awaiting-signature">
                  Waiting for customer to sign the rental agreement. They were emailed a link; you can
                  resend or copy the link here after approve or resend.
                </div>
              ) : null}
              {r.payment_collection_url ? (
                <div className="muted small">
                  Payment link:{' '}
                  <a href={r.payment_collection_url} target="_blank" rel="noreferrer">
                    open
                  </a>
                </div>
              ) : null}
              <div className="muted">
                {r.sales_tax_amount != null && r.rental_total_with_tax != null ? (
                  <>
                    Subtotal {money(r.discounted_subtotal)} · Tax {money(r.sales_tax_amount)}
                    {r.sales_tax_rate_percent != null
                      ? ` (${Number(r.sales_tax_rate_percent)}%)`
                      : ''}{' '}
                    · Total {money(r.rental_total_with_tax)} · Deposit {money(r.deposit_amount)}
                  </>
                ) : (
                  <>
                    Rental {money(r.discounted_subtotal)} · Deposit {money(r.deposit_amount)}
                  </>
                )}
              </div>
              {canMark ? (
                <div className="muted small">
                  Rental paid: {r.rental_paid_at ? 'yes' : 'no'}
                  {r.rental_payment_status ? ` (${r.rental_payment_status})` : ''} · Deposit secured:{' '}
                  {r.deposit_secured_at ? 'yes' : 'no'} · Agreement signed:{' '}
                  {r.agreement_signed_at ? 'yes' : 'no'}
                </div>
              ) : null}
              {stripeCheckoutEligible(r) ? (
                <div className="muted small">
                  Stripe rental checkout:{' '}
                  {r.stripe_checkout_session_id
                    ? `session ${truncateId(r.stripe_checkout_session_id)}`
                    : 'not generated'}
                  {r.stripe_checkout_created_at ? ` · ${r.stripe_checkout_created_at}` : ''}
                </div>
              ) : null}
              {stripeCheckoutEligible(r) && r.stripe_checkout_url ? (
                <div className="muted small">
                  Rental total (pay link):{' '}
                  <a href={r.stripe_checkout_url} target="_blank" rel="noreferrer">
                    open
                  </a>
                </div>
              ) : null}
              {stripeCheckoutEligible(r) &&
              r.deposit_amount != null &&
              Number(r.deposit_amount) > 0 ? (
                <div className="muted small">
                  Stripe deposit checkout:{' '}
                  {r.stripe_deposit_checkout_session_id
                    ? `session ${truncateId(r.stripe_deposit_checkout_session_id)}`
                    : 'not generated'}
                  {r.stripe_deposit_checkout_created_at ? ` · ${r.stripe_deposit_checkout_created_at}` : ''}
                </div>
              ) : null}
              {stripeCheckoutEligible(r) && r.stripe_deposit_checkout_url ? (
                <div className="muted small">
                  Security deposit (pay link):{' '}
                  <a href={r.stripe_deposit_checkout_url} target="_blank" rel="noreferrer">
                    open
                  </a>
                </div>
              ) : null}
              {r.deposit_secured_at && r.stripe_deposit_payment_intent_id && !r.stripe_deposit_captured_cents ? (
                <div className="muted small">
                  {r.deposit_refunded_at
                    ? `Security deposit (hold) voided ${r.deposit_refunded_at}${r.stripe_deposit_refund_id ? ` · ${truncateId(r.stripe_deposit_refund_id, 18)}` : ''}`
                    : 'Security deposit: card hold (not captured) — use “Refund deposit (Stripe)” to void the hold in Stripe when appropriate.'}
                </div>
              ) : null}
              {typeof r.stripe_deposit_captured_cents === 'number' && r.stripe_deposit_captured_cents > 0 ? (
                <div className="muted small">
                  Stripe deposit captured: {(r.stripe_deposit_captured_cents / 100).toLocaleString(undefined, {
                    style: 'currency',
                    currency: 'USD',
                  })}
                  {r.deposit_refunded_at
                    ? ` · Refunded ${r.deposit_refunded_at}${r.stripe_deposit_refund_id ? ` (${truncateId(r.stripe_deposit_refund_id, 18)})` : ''}`
                    : ''}
                </div>
              ) : null}
              <div className="admin-booking-docs small">
                {r.drivers_license_url ? (
                  <button
                    type="button"
                    className="doc-link"
                    onClick={() =>
                      void openBookingDocument(r.drivers_license_url!, "driver's license")
                    }
                  >
                    Driver’s license
                  </button>
                ) : (
                  <span className="muted">No license on file</span>
                )}
                {r.license_plate_url ? (
                  <>
                    {' · '}
                    <button
                      type="button"
                      className="doc-link"
                      onClick={() =>
                        void openBookingDocument(r.license_plate_url!, 'license plate photo')
                      }
                    >
                      License plate
                    </button>
                  </>
                ) : null}
              </div>
              <div className="admin-row-actions admin-booking-actions">
                {isAwaitingSignature(r.status) ? (
                  <>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busyId === r.id}
                      onClick={() => void resendSignature(r.id)}
                    >
                      Resend signing email
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={!signUrl}
                      title={signUrl ? undefined : 'Approve or resend to generate a signing link'}
                      onClick={() => signUrl && void copySigningLink(signUrl)}
                    >
                      Copy signing link
                    </button>
                  </>
                ) : null}
                {canApprove ? (
                  <>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={busyId === r.id}
                      onClick={() => approve(r)}
                    >
                      {busyId === r.id ? '…' : 'Approve'}
                    </button>
                  </>
                ) : null}
                {canMark ? (
                  <>
                    {stripeCheckoutEligible(r) ? (
                      <>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          disabled={busyId === r.id || (Boolean(r.rental_paid_at) && Boolean(r.deposit_secured_at))}
                          title={
                            r.rental_paid_at && r.deposit_secured_at
                              ? 'Rental paid and deposit secured'
                              : 'Creates or recreates Stripe Checkout sessions. After the customer has signed (awaiting payment), this emails them the payment links if SMTP is configured. While still awaiting signature, use Resend signing email for links in the approval message.'
                          }
                          onClick={() => void generateStripeCheckout(r.id)}
                        >
                          {r.stripe_checkout_url || r.stripe_deposit_checkout_url
                            ? 'Regenerate Stripe links'
                            : 'Generate payment links'}
                        </button>
                        {r.stripe_checkout_url ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={!r.stripe_checkout_url}
                            onClick={() =>
                              r.stripe_checkout_url && void copyText(r.stripe_checkout_url, 'Rental Stripe link')
                            }
                          >
                            Copy rental link
                          </button>
                        ) : null}
                        {r.stripe_deposit_checkout_url ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={!r.stripe_deposit_checkout_url}
                            onClick={() =>
                              r.stripe_deposit_checkout_url &&
                              void copyText(r.stripe_deposit_checkout_url, 'Deposit Stripe link')
                            }
                          >
                            Copy deposit link
                          </button>
                        ) : null}
                        {r.stripe_checkout_session_id || r.stripe_deposit_checkout_session_id ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={busyId === r.id}
                            title="Fetches Checkout sessions from Stripe and updates rental paid / deposit secured if Stripe shows paid (use when webhooks did not update this screen)."
                            onClick={() => void syncStripeCheckout(r.id)}
                          >
                            Sync payment from Stripe
                          </button>
                        ) : null}
                      </>
                    ) : null}
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busyId === r.id || Boolean(r.rental_paid_at)}
                      title="Manual reconciliation if Stripe webhook did not run"
                      onClick={() => markAction(r.id, 'mark-rental-paid')}
                    >
                      Mark rental paid
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={
                        busyId === r.id ||
                        Boolean(r.deposit_secured_at) ||
                        Boolean((r.stripe_deposit_payment_intent_id || '').trim())
                      }
                      title={
                        (r.stripe_deposit_payment_intent_id || '').trim() && !r.deposit_secured_at
                          ? 'Deposit PaymentIntent exists on the booking; refresh the list if the status looks stale.'
                          : undefined
                      }
                      onClick={() => markAction(r.id, 'mark-deposit-secured')}
                    >
                      Mark deposit secured
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busyId === r.id || Boolean(r.agreement_signed_at)}
                      onClick={() => markAction(r.id, 'mark-agreement-signed')}
                    >
                      Mark agreement signed
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={busyId === r.id || !readyToConfirm}
                      title={
                        readyToConfirm
                          ? 'Books calendar dates'
                          : 'Requires rental paid, deposit secured (if deposit > 0), and agreement signed. If Stripe already shows paid, use Sync payment from Stripe first.'
                      }
                      onClick={() => confirm(r.id)}
                    >
                      Confirm booking
                    </button>
                  </>
                ) : null}
                {stripeDepositRefundEligible(r) ? (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={busyId === r.id}
                    title={
                      (r.stripe_deposit_payment_intent_id || '').trim()
                        ? r.deposit_secured_at && !r.stripe_deposit_captured_cents
                          ? 'Void the separate deposit authorization hold in Stripe (no charge was taken yet), or refund if the deposit was captured'
                          : 'Full refund on the separate deposit charge'
                        : 'Partial refund on the rental PaymentIntent for the deposit amount (legacy combined checkout)'
                    }
                    onClick={() => void refundStripeDeposit(r.id)}
                  >
                    Refund deposit (Stripe)
                  </button>
                ) : null}
                {canDecline ? (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={busyId === r.id}
                    onClick={() => openDecline(r.id)}
                  >
                    Decline
                  </button>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>
      {rows.length === 0 && !error && <p className="muted">No requests yet.</p>}

      {declineForId && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={(e) => e.target === e.currentTarget && closeDecline()}
        >
          <div className="modal-dialog" role="dialog" aria-labelledby="decline-title">
            <h2 id="decline-title">Decline rental request</h2>
            <p className="muted small">
              The customer will receive an email with the item, requested dates, and this reason.
              Requested dates will be set to <strong>Open for booking</strong>.
            </p>
            <label className="field">
              <span className="field-label">Reason (required)</span>
              <textarea
                value={declineReason}
                onChange={(e) => setDeclineReason(e.target.value)}
                placeholder="e.g. Equipment is already reserved for maintenance that week."
                rows={5}
              />
            </label>
            {declineError && <p className="error-msg small">{declineError}</p>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary btn-sm" onClick={closeDecline}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={busyId === declineForId}
                onClick={() => void confirmDecline()}
              >
                {busyId === declineForId ? 'Sending…' : 'Decline & notify'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
