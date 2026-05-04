import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js'
import { loadStripe } from '@stripe/stripe-js'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  apiGet,
  apiPost,
  uploadBookingFileToSignedUrl,
} from '../api/client'
import { useCustomerSession } from '../context/CustomerSessionContext'
import type {
  BookingCompletionPresignOut,
  BookingCompletionSummaryOut,
  BookingRequestOut,
  BookingStripeSetupIntentOut,
} from '../types'

function money(s: string) {
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

/** Optional Stripe PM collection inside Elements. Parent calls confirmPm() before verification POST. */
export type StripePaymentHandle = {
  confirmPm: () => Promise<string | null>
}

const StripePaymentInner = forwardRef<
  StripePaymentHandle,
  { disabled: boolean; onStripeError?: (msg: string | null) => void }
>(function StripePaymentInner({ disabled, onStripeError }, ref) {
  const stripe = useStripe()
  const elements = useElements()

  useImperativeHandle(
    ref,
    () => ({
      async confirmPm() {
        if (!stripe || !elements) {
          onStripeError?.('Stripe is still loading.')
          return null
        }
        const { error, setupIntent } = await stripe.confirmSetup({
          elements,
          redirect: 'if_required',
          confirmParams: {
            return_url: window.location.href,
          },
        })
        if (error) {
          onStripeError?.(error.message ?? 'Card error')
          return null
        }
        const pm = setupIntent?.payment_method
        const id = typeof pm === 'string' ? pm : pm && typeof pm === 'object' && 'id' in pm ? String((pm as { id: string }).id) : null
        onStripeError?.(null)
        return id
      },
    }),
    [stripe, elements, onStripeError],
  )

  return (
    <div className={disabled ? 'muted' : ''}>
      <PaymentElement options={{ layout: 'tabs' }} />
    </div>
  )
})

StripePaymentInner.displayName = 'StripePaymentInner'

export function BookingCompletePage() {
  const { id: bookingId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const customer = useCustomerSession()
  const [summary, setSummary] = useState<BookingCompletionSummaryOut | null>(null)
  const [loadErr, setLoadErr] = useState<string | null>(null)
  const [stripeSetup, setStripeSetup] = useState<BookingStripeSetupIntentOut | null>(null)
  const [stripeErr, setStripeErr] = useState<string | null>(null)

  const [customerAddress, setCustomerAddress] = useState('')
  const [customerAddressEditing, setCustomerAddressEditing] = useState(false)
  const [jobSiteAddress, setJobSiteAddress] = useState('')
  const [sameAsCustomerJobSite, setSameAsCustomerJobSite] = useState(false)
  const [towAck, setTowAck] = useState(false)
  const [approvalAck, setApprovalAck] = useState(false)
  const [signIntentAck, setSignIntentAck] = useState(false)
  const [dlFile, setDlFile] = useState<File | null>(null)
  const [insFile, setInsFile] = useState<File | null>(null)
  const [submitErr, setSubmitErr] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  type SubmitPhase = 'idle' | 'upload' | 'payment' | 'submit'
  const [submitPhase, setSubmitPhase] = useState<SubmitPhase>('idle')
  const seededBookingIdRef = useRef<string | null>(null)
  const customerAddressSnapshotRef = useRef('')

  const stripePaymentRef = useRef<StripePaymentHandle | null>(null)

  const stripePk = stripeSetup?.publishable_key ?? ''
  const stripePromise = useMemo(() => (stripePk ? loadStripe(stripePk) : null), [stripePk])

  useEffect(() => {
    if (!bookingId) return
    let cancelled = false
    apiGet<BookingCompletionSummaryOut>(`/booking-requests/${encodeURIComponent(bookingId)}/completion-summary`)
      .then((s) => {
        if (!cancelled) {
          setSummary(s)
          setLoadErr(null)
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setSummary(null)
          setLoadErr(e.message)
        }
      })
    return () => {
      cancelled = true
    }
  }, [bookingId])

  useEffect(() => {
    if (!bookingId || !summary?.stripe_payment_collection_enabled || summary.status !== 'requested') {
      setStripeSetup(null)
      return
    }
    let cancelled = false
    apiPost<BookingStripeSetupIntentOut>(
      `/booking-requests/${encodeURIComponent(bookingId)}/stripe-setup-intent`,
      {},
    )
      .then((out) => {
        if (!cancelled) setStripeSetup(out)
      })
      .catch((e: Error) => {
        if (!cancelled) setStripeErr(e.message)
      })
    return () => {
      cancelled = true
    }
  }, [bookingId, summary?.stripe_payment_collection_enabled, summary?.status])

  useEffect(() => {
    seededBookingIdRef.current = null
  }, [bookingId])

  useEffect(() => {
    if (!summary || summary.status !== 'requested' || !bookingId) return
    if (seededBookingIdRef.current === bookingId) return
    seededBookingIdRef.current = bookingId
    const needsLogistics = summary.delivery_requested || summary.pickup_from_site_requested
    const cust =
      summary.customer_address?.trim() ??
      ''
    customerAddressSnapshotRef.current = cust
    setCustomerAddress(cust)
    setCustomerAddressEditing(false)
    const job =
      summary.job_site_address?.trim() ??
      summary.logistics_address?.trim() ??
      summary.delivery_address?.trim() ??
      ''
    setJobSiteAddress(job)
    setSameAsCustomerJobSite(
      Boolean(needsLogistics) && Boolean(job) && Boolean(cust) && job === cust,
    )
  }, [bookingId, summary])

  useEffect(() => {
    if (!summary || summary.status !== 'requested') return
    const needsLogistics = summary.delivery_requested || summary.pickup_from_site_requested
    if (!sameAsCustomerJobSite || !needsLogistics) return
    setJobSiteAddress(customerAddress)
  }, [sameAsCustomerJobSite, customerAddress, summary])

  const customerBlocked =
    customer.mode === 'auth0' && !customer.isLoading && !customer.isAuthenticated

  async function submitForApproval(stripeCollect: StripePaymentHandle | null) {
    if (!bookingId || !summary) return
    setSubmitErr(null)
    if (!dlFile) {
      setSubmitErr('Upload a valid driver\'s license for the renter — required to verify eligibility to rent.')
      return
    }
    if (!customerAddress.trim()) {
      setSubmitErr('Enter your customer address (billing / contract).')
      return
    }
    if (
      (summary.delivery_requested || summary.pickup_from_site_requested) &&
      !jobSiteAddress.trim()
    ) {
      setSubmitErr('Enter the job site address.')
      return
    }
    if (summary.towable && !towAck) {
      setSubmitErr('Confirm that your vehicle can safely tow this trailer.')
      return
    }
    if (!approvalAck) {
      setSubmitErr(
        'Please confirm that this request is subject to approval and is not yet confirmed.',
      )
      return
    }
    setSubmitting(true)
    setSubmitPhase('upload')
    setSubmitErr(null)
    let paymentMethodId: string | null = null
    try {
      const dlType = dlFile.type || 'application/octet-stream'
      const insType = insFile?.type
      const pre = await apiPost<BookingCompletionPresignOut>(
        `/booking-requests/${encodeURIComponent(bookingId)}/completion-uploads/presign`,
        {
          drivers_license_content_type: dlType,
          insurance_card_content_type: insType || undefined,
        },
      )
      await uploadBookingFileToSignedUrl(pre.drivers_license.signed_url, dlFile, dlType)
      if (insFile && pre.insurance_card) {
        await uploadBookingFileToSignedUrl(
          pre.insurance_card.signed_url,
          insFile,
          insType || 'application/octet-stream',
        )
      }
      if (summary.stripe_payment_collection_enabled) {
        setSubmitPhase('payment')
        if (!stripeCollect) {
          setSubmitErr('Payment form is not ready yet.')
          return
        }
        paymentMethodId = await stripeCollect.confirmPm()
        if (!paymentMethodId) return
      }
      setSubmitPhase('submit')
      await apiPost<BookingRequestOut>(`/booking-requests/${encodeURIComponent(bookingId)}/verification`, {
        drivers_license_path: pre.drivers_license.path,
        insurance_card_path: pre.insurance_card?.path ?? null,
        customer_address: customerAddress.trim(),
        job_site_address:
          summary.delivery_requested || summary.pickup_from_site_requested
            ? jobSiteAddress.trim()
            : undefined,
        vehicle_tow_capable_ack: summary.towable ? towAck : false,
        request_approval_acknowledged: approvalAck,
        agreement_sign_intent_acknowledged: signIntentAck,
        damage_waiver_selected: false,
        stripe_payment_method_id: paymentMethodId,
      })
      const next = await apiGet<BookingCompletionSummaryOut>(
        `/booking-requests/${encodeURIComponent(bookingId)}/completion-summary`,
      )
      setSummary(next)
    } catch (e) {
      setSubmitErr(e instanceof Error ? e.message : 'Submit failed')
    } finally {
      setSubmitting(false)
      setSubmitPhase('idle')
    }
  }

  if (!bookingId) {
    return (
      <div className="container">
        <p className="error-msg">Missing booking link.</p>
        <Link to="/catalog">Catalog</Link>
      </div>
    )
  }

  if (loadErr) {
    return (
      <div className="container">
        <p className="error-msg">{loadErr}</p>
        <Link to="/catalog">Back to catalog</Link>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="container">
        <p className="muted">Loading…</p>
      </div>
    )
  }

  if (summary.status === 'pending_approval') {
    return (
      <div className="container page-booking-complete">
        <div className="card card-pad booking-success-block booking-request-submitted">
          <h1>Request submitted</h1>
          <p className="success-msg booking-submitted-lead">
            We’ve received your request and are reviewing it now.
          </p>
          <div className="booking-submitted-status">
            <p className="booking-submitted-status-title">Your booking is not confirmed yet.</p>
            <p className="muted">
              We’ll review your request, including availability and delivery (if requested), and send you a
              confirmation shortly.
            </p>
            <p className="muted small booking-submitted-timeline">
              Most requests are reviewed within a few hours during business hours.
            </p>
          </div>
          <section className="booking-submitted-next" aria-labelledby="booking-submitted-next-heading">
            <h2 id="booking-submitted-next-heading" className="booking-submitted-next-title">
              What happens next:
            </h2>
            <ul className="booking-submitted-list">
              <li>We review your request and details</li>
              <li>You’ll receive an email once your booking is approved</li>
              <li>At that point, you’ll finalize your rental (agreement + payment)</li>
            </ul>
          </section>
          <p className="muted small booking-submitted-payment-note">No charges have been made to your card.</p>
          <div className="booking-actions booking-submitted-actions">
            <Link to="/catalog" className="btn btn-primary">
              Browse more equipment
            </Link>
            <Link to="/my-rentals" className="btn btn-secondary">
              View my requests
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const formDisabled = customerBlocked || submitting

  const needsLogistics = summary.delivery_requested || summary.pickup_from_site_requested

  return (
    <div className="container page-booking-complete">
      <p className="breadcrumb">
        <Link to="/catalog">Catalog</Link>
        <span aria-hidden> / </span>
        <span>Complete your request</span>
      </p>

      <header className="section-block">
        <h1>Step 2 of 2 — Complete Your Request</h1>
        <p className="muted">
          Complete your request so we can review and approve your booking.
        </p>
      </header>

      <div className="booking-warning-banner card card-pad" role="status">
        <strong>This is not a confirmed booking.</strong>
        <p className="small muted tight-top">
          We&apos;ll review your request, including logistics if requested, and confirm shortly.
        </p>
        <p className="small muted tight-top">
          Your dates are not reserved until your booking is approved.
        </p>
      </div>

      {customerBlocked ? (
        <p className="booking-auth-hint card card-pad">
          <span className="muted">Sign in to continue this booking.</span>{' '}
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => customer.login()}>
            Sign in
          </button>
        </p>
      ) : null}

      <section className="card card-pad section-block">
        <h2>Your request</h2>
        <ul className="quote-lines">
          <li>
            <span>Trailer</span>
            <span>{summary.item_title}</span>
          </li>
          <li>
            <span>Dates</span>
            <span>
              {summary.start_date} → {summary.end_date}
            </span>
          </li>
          <li>
            <span>Duration</span>
            <span>
              {summary.num_days} day{summary.num_days === 1 ? '' : 's'}
            </span>
          </li>
          <li>
            <span>Transport</span>
            <span>
              {!summary.delivery_requested && !summary.pickup_from_site_requested
                ? 'Customer pickup'
                : [
                    summary.delivery_requested ? 'Delivery' : null,
                    summary.pickup_from_site_requested ? 'Pickup from site' : null,
                  ]
                    .filter(Boolean)
                    .join(' + ')}
            </span>
          </li>
          <li>
            <span>Estimated rental (subtotal)</span>
            <span>{money(summary.discounted_subtotal)}</span>
          </li>
          {summary.delivery_fee != null && Number(summary.delivery_fee) > 0 ? (
            <li>
              <span>Delivery (estimated)</span>
              <span>{money(summary.delivery_fee)}</span>
            </li>
          ) : null}
          {summary.pickup_fee != null && Number(summary.pickup_fee) > 0 ? (
            <li>
              <span>Pickup (estimated)</span>
              <span>{money(summary.pickup_fee)}</span>
            </li>
          ) : null}
          <li>
            <span>Estimated total (with tax)</span>
            <span>{money(summary.rental_total_with_tax)}</span>
          </li>
          <li>
            <span>Estimated deposit</span>
            <span>{money(summary.deposit_amount)}</span>
          </li>
        </ul>
        <p className="muted small">
          Final pricing (including logistics, if any) will be confirmed after review.
        </p>
      </section>

      <section className="card card-pad section-block">
        <h2>Renter verification</h2>
        <p className="muted small">
          Upload a valid driver&apos;s license for the person responsible for this rental.
        </p>
        <p className="muted small">The renter must be present at pickup and is responsible for the trailer during the rental period.</p>
        <label className="field field-span">
          <span className="field-label">Driver&apos;s license</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            disabled={formDisabled}
            onChange={(e) => setDlFile(e.target.files?.[0] ?? null)}
          />
          {dlFile ? <span className="muted small">{dlFile.name}</span> : null}
        </label>
      </section>

      <section className="card card-pad section-block">
        <h2>Contact details</h2>
        {customerAddressEditing ? (
          <>
            <label className="field field-span">
              <span className="field-label">Customer address</span>
              <textarea
                value={customerAddress}
                onChange={(e) => setCustomerAddress(e.target.value)}
                rows={4}
                disabled={formDisabled}
                autoComplete="street-address"
                placeholder="Full address including ZIP"
              />
            </label>
            <span className="muted small field-span">
              Used for billing, contract, and tax purposes.
            </span>
            <div className="booking-inline-actions">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={formDisabled || !customerAddress.trim()}
                onClick={() => {
                  customerAddressSnapshotRef.current = customerAddress.trim()
                  setCustomerAddress(customerAddress.trim())
                  setCustomerAddressEditing(false)
                }}
              >
                Done
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={formDisabled}
                onClick={() => {
                  setCustomerAddress(customerAddressSnapshotRef.current)
                  setCustomerAddressEditing(false)
                }}
              >
                Cancel
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="booking-address-label">Customer address</p>
            <p className="booking-address-readonly">{customerAddress.trim() || '—'}</p>
            <p className="muted small booking-address-footnote">
              Used for billing, contract, and tax purposes.
            </p>
            <button
              type="button"
              className="btn btn-secondary btn-sm booking-address-edit"
              disabled={formDisabled}
              onClick={() => setCustomerAddressEditing(true)}
            >
              Edit
            </button>
          </>
        )}
        {needsLogistics ? (
          <>
            <label className="field field-span tight-top">
              <span className="field-label">Job site address</span>
              <textarea
                value={jobSiteAddress}
                onChange={(e) => {
                  setJobSiteAddress(e.target.value)
                  setSameAsCustomerJobSite(false)
                }}
                rows={4}
                disabled={formDisabled || sameAsCustomerJobSite}
                autoComplete="street-address"
                placeholder="Street, city, state, ZIP"
              />
            </label>
            <label className="field field-checkbox field-span">
              <input
                type="checkbox"
                checked={sameAsCustomerJobSite}
                onChange={(e) => {
                  const on = e.target.checked
                  setSameAsCustomerJobSite(on)
                  if (on) {
                    setJobSiteAddress(customerAddress)
                  }
                }}
                disabled={formDisabled}
              />
              <span>Same as customer address</span>
            </label>
            <p className="muted small field-span">
              Used for delivery and/or pickup routing. We&apos;ll confirm logistics when we review your request.
            </p>
          </>
        ) : null}
      </section>

      {summary.towable ? (
        <section className="card card-pad section-block">
          <h2>Vehicle Confirmation</h2>
          <label className="field field-checkbox field-span">
            <input
              type="checkbox"
              checked={towAck}
              onChange={(e) => setTowAck(e.target.checked)}
              disabled={formDisabled}
            />
            <span>My vehicle is capable of safely towing this trailer.</span>
          </label>
          <p className="muted small">Not sure? We can help confirm after submission.</p>
        </section>
      ) : null}

      <section className="card card-pad section-block">
        <h2>Insurance Information (Optional)</h2>
        <p className="muted small">
          Upload your insurance card if you&apos;d like us to keep it on file.
        </p>
        <label className="field field-span">
          <span className="field-label">Insurance card</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            disabled={formDisabled}
            onChange={(e) => setInsFile(e.target.files?.[0] ?? null)}
          />
          {insFile ? <span className="muted small">{insFile.name}</span> : null}
        </label>
      </section>

      <section className="card card-pad section-block">
        <h2>Deposit</h2>
        <p className="small">
          A refundable deposit of <strong>{money(summary.deposit_amount)}</strong> may be authorized on your card
          after your booking is approved.
        </p>
        <p className="muted small">Your card will not be charged until your booking is approved.</p>
      </section>

      <section className="card card-pad section-block">
        <h2>Rental Terms</h2>
        {summary.rental_terms_url ? (
          <p>
            <a
              href={summary.rental_terms_url}
              target="_blank"
              rel="noopener noreferrer"
              className="nav-link"
            >
              View rental terms
            </a>
          </p>
        ) : (
          <p className="muted small">
            General rental terms are provided after approval with your formal agreement package.
          </p>
        )}
        <label className="field field-checkbox field-span">
          <input
            type="checkbox"
            checked={approvalAck}
            onChange={(e) => setApprovalAck(e.target.checked)}
            disabled={formDisabled}
          />
          <span>I understand this request is subject to approval and is not yet confirmed.</span>
        </label>
        <label className="field field-checkbox field-span">
          <input
            type="checkbox"
            checked={signIntentAck}
            onChange={(e) => setSignIntentAck(e.target.checked)}
            disabled={formDisabled}
          />
          <span>I agree to review and sign the rental agreement if this request is approved.</span>
        </label>
      </section>

      {summary.stripe_payment_collection_enabled && stripeSetup && stripePromise ? (
        <section className="card card-pad section-block">
          <h2>Payment method</h2>
          <p className="muted small">
            Enter your card so we can secure your request if your booking is approved. Your card will not be
            charged until your booking is approved.
          </p>
          {stripeErr ? (
            <p className="error-msg">
              {import.meta.env.DEV ? stripeErr : 'We could not load the card form. Please try again or contact us.'}
            </p>
          ) : null}
          <Elements stripe={stripePromise} options={{ clientSecret: stripeSetup.client_secret }}>
            <StripePaymentInner
              ref={stripePaymentRef}
              disabled={formDisabled}
              onStripeError={setStripeErr}
            />
          </Elements>
        </section>
      ) : summary.stripe_payment_collection_enabled ? (
        <section className="card card-pad section-block">
          <h2>Payment method</h2>
          <p className="muted small">
            Enter your card so we can secure your request if your booking is approved. Your card will not be
            charged until your booking is approved.
          </p>
          {stripeErr ? (
            <p className="error-msg">
              {import.meta.env.DEV ? stripeErr : 'We could not load the card form. Please try again or contact us.'}
            </p>
          ) : null}
        </section>
      ) : (
        <section className="card card-pad section-block">
          <h2>Payment method</h2>
          <p className="muted small">
            Card collection is disabled in this environment. Your card will not be charged until your booking is
            approved. Approval and payment links will follow by email when the owner approves.
          </p>
        </section>
      )}

      {submitErr ? <p className="error-msg">{submitErr}</p> : null}

      {submitting ? (
        <div className="booking-submit-status card card-pad" aria-live="polite">
          <p className="booking-submit-status-title">Submitting your request...</p>
          <p className="muted small">This will only take a few seconds.</p>
          <ul className="booking-submit-checklist">
            <li
              className={
                submitPhase === 'upload'
                  ? 'active'
                  : submitPhase === 'payment' || submitPhase === 'submit'
                    ? 'done'
                    : undefined
              }
            >
              Uploading documents...
            </li>
            {summary.stripe_payment_collection_enabled ? (
              <li className={submitPhase === 'payment' ? 'active' : submitPhase === 'submit' ? 'done' : undefined}>
                Securing payment method...
              </li>
            ) : null}
            <li className={submitPhase === 'submit' ? 'active' : undefined}>Submitting request...</li>
          </ul>
        </div>
      ) : null}

      <div className="booking-actions">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={submitting || customerBlocked}
          onClick={() => navigate(-1)}
        >
          Back
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={
            customerBlocked ||
            submitting ||
            (summary.stripe_payment_collection_enabled &&
              !(stripeSetup && stripePromise))
          }
          onClick={() => void submitForApproval(summary.stripe_payment_collection_enabled ? stripePaymentRef.current : null)}
        >
          {submitting ? 'Submitting...' : 'Submit for Approval'}
        </button>
      </div>
      <p className="muted small">
        We&apos;ll review your request and confirm shortly.
        <br />
        You&apos;ll receive an email once your booking is approved.
      </p>
    </div>
  )
}
