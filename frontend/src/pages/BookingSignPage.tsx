import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiGetPublic, apiPostPublic } from '../api/client'
import { LEGAL_BUSINESS_NAME } from '../branding'
import type { BookingSignPageOut, BookingSignResultOut } from '../types'

function money(s: string | null | undefined) {
  if (s == null || s === '') return '—'
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

export function BookingSignPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<BookingSignPageOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [signerName, setSignerName] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [typedSignature, setTypedSignature] = useState('')
  const [ackRental, setAckRental] = useState(false)
  const [ackDamage, setAckDamage] = useState(false)
  const [ackFinancial, setAckFinancial] = useState(false)
  const [ackPay, setAckPay] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!token) {
      setError('Missing signing link.')
      setLoading(false)
      return
    }
    let cancelled = false
    apiGetPublic<BookingSignPageOut>(`/booking-actions/${encodeURIComponent(token)}/sign`)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    if (!data) return
    const fn = (data.customer_first_name || '').trim()
    const ln = (data.customer_last_name || '').trim()
    if (fn || ln) {
      setSignerName([fn, ln].filter(Boolean).join(' '))
    }
    if ((data.company_name || '').trim()) {
      setCompanyName(data.company_name!.trim())
    }
  }, [data])

  const typedSignatureOk = Boolean(typedSignature.trim())
  const allAcknowledged = ackRental && ackDamage && ackFinancial && ackPay

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!token) return
    if (!allAcknowledged) {
      setError('Check all acknowledgment boxes above, then try again.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const body: Record<string, unknown> = {
        signer_name: signerName.trim(),
        typed_signature: typedSignature.trim(),
        acknowledgments: {
          rental_agreement: ackRental,
          damage_fee_schedule: ackDamage,
          financial_responsibility: ackFinancial,
          payment_deposit_gate: ackPay,
        },
      }
      const co = companyName.trim()
      if (co) body.company_name = co
      const out = await apiPostPublic<BookingSignResultOut>(
        `/booking-actions/${encodeURIComponent(token)}/sign`,
        body,
      )
      if (out.next_url) {
        navigate(out.next_url)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submit failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="container">
        <p className="muted">Loading agreement…</p>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="container page-booking-sign">
        <h1>Signing</h1>
        <p className="error-msg">{error ?? 'Unable to load this page.'}</p>
        <p className="muted small">
          If your link expired, contact {LEGAL_BUSINESS_NAME} for a new signing link.
        </p>
        <Link to="/catalog">Back to catalog</Link>
      </div>
    )
  }

  const emailOnFile = (data.customer_email || '').trim()

  return (
    <div className="container page-booking-sign">
      <p className="breadcrumb">
        <Link to="/catalog">Catalog</Link>
        <span aria-hidden> / </span>
        <span>Sign rental agreement</span>
      </p>
      <h1>Complete your rental agreement</h1>
      <p className="muted">
        Review your booking details, sign the rental agreement, and acknowledge the damage fee
        schedule to continue. Your booking is not confirmed until payment and deposit requirements are
        met.
      </p>

      <section className="card card-pad section-block">
        <h2>Booking summary</h2>
        <dl className="attr-list">
          <div>
            <dt>Trailer</dt>
            <dd>{data.item_title}</dd>
          </div>
          <div>
            <dt>Rental dates</dt>
            <dd>
              {data.start_date} → {data.end_date}
            </dd>
          </div>
          {data.delivery_address ? (
            <div>
              <dt>Address on file</dt>
              <dd>{data.delivery_address}</dd>
            </div>
          ) : null}
          <div>
            <dt>Email on file</dt>
            <dd>{emailOnFile || '—'}</dd>
          </div>
          <div>
            <dt>Rental total (with tax)</dt>
            <dd>{money(data.rental_total_with_tax)}</dd>
          </div>
          <div>
            <dt>Refundable deposit</dt>
            <dd>{money(data.deposit_amount)}</dd>
          </div>
          <div>
            <dt>Approved payment path</dt>
            <dd>{data.payment_path ?? '—'}</dd>
          </div>
          <div>
            <dt>Link expires</dt>
            <dd>{data.expires_at}</dd>
          </div>
        </dl>
        {!emailOnFile ? (
          <p className="error-msg small" style={{ marginTop: '0.75rem' }}>
            This booking has no email on file. Contact {LEGAL_BUSINESS_NAME} before you can sign —
            the API will not accept a signature without it.
          </p>
        ) : (
          <p className="muted small" style={{ marginTop: '0.75rem' }}>
            Your signature will be recorded using the email on file — you do not need to type it
            again.
          </p>
        )}
      </section>

      <section className="card card-pad section-block contract-html-block">
        <h2>Rental agreement</h2>
        <p className="muted small">
          You agree not to overload, misuse, or use the trailer in unsafe or prohibited ways. See full
          agreement for details.
        </p>
        <div className="contract-html" dangerouslySetInnerHTML={{ __html: data.agreement_html }} />
      </section>

      <section className="card card-pad section-block contract-html-block">
        <h2>Damage &amp; fee schedule</h2>
        <p className="muted small">
          Common examples (typical ranges; final charges depend on actual repair/replacement cost):
        </p>
        <ul className="muted small" style={{ marginTop: 0 }}>
          <li>Tire replacement ($150–$400)</li>
          <li>Coupler repair/replacement ($125–$450)</li>
          <li>Cleanup / excessive debris ($50–$300)</li>
          <li>Electrical repair ($50–$250)</li>
          <li>Late return (additional daily rental rate until returned)</li>
          <li>Administrative fee ($50–$100 per incident)</li>
        </ul>
        <details style={{ marginTop: '0.75rem' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 700 }}>
            View full damage &amp; fee schedule (important)
          </summary>
          <div style={{ maxHeight: 520, overflow: 'auto', marginTop: '0.75rem' }}>
            <div className="contract-html" dangerouslySetInnerHTML={{ __html: data.damage_html }} />
          </div>
        </details>
      </section>

      <section className="card card-pad section-block">
        <h2>Acknowledgments &amp; signature</h2>
        <p className="muted small" style={{ marginTop: '-0.25rem' }}>
          You&apos;re almost done. Review the agreement and check the boxes below to continue.
        </p>
        <form className="booking-grid" onSubmit={onSubmit}>
          <label className="field field-checkbox field-span">
            <input type="checkbox" checked={ackRental} onChange={(e) => setAckRental(e.target.checked)} />
            <span>
              I have reviewed and agree to the Rental Agreement, including pricing, deposit terms, and
              responsibilities for damage and loss.
            </span>
          </label>
          <label className="field field-checkbox field-span">
            <input type="checkbox" checked={ackDamage} onChange={(e) => setAckDamage(e.target.checked)} />
            <span>I have reviewed and acknowledge the Damage &amp; Fee Schedule Addendum.</span>
          </label>
          <label className="field field-checkbox field-span">
            <input
              type="checkbox"
              checked={ackFinancial}
              onChange={(e) => setAckFinancial(e.target.checked)}
            />
            <span>
              I understand I am financially responsible for any damage, loss, or misuse of the
              equipment during the rental period, including amounts exceeding the security deposit.
            </span>
          </label>
          <label className="field field-checkbox field-span">
            <input type="checkbox" checked={ackPay} onChange={(e) => setAckPay(e.target.checked)} />
            <span>
              I understand the trailer will not be released until payment and deposit requirements are
              satisfied.
            </span>
          </label>
          <label className="field">
            <span className="field-label">Full legal name</span>
            <input value={signerName} onChange={(e) => setSignerName(e.target.value)} required />
          </label>
          <label className="field">
            <span className="field-label">Company name (optional)</span>
            <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
          </label>
          <label className="field field-span">
            <span className="field-label">Type your full name as your electronic signature</span>
            <input value={typedSignature} onChange={(e) => setTypedSignature(e.target.value)} required />
          </label>
          <p className="muted small field-span" style={{ marginTop: '-0.25rem' }}>
            By signing electronically, I agree this constitutes a legally binding signature.
          </p>
          {!allAcknowledged ? (
            <p className="muted small field-span">
              Check all boxes above to enable <strong>Sign agreement</strong> (required by the
              rental contract).
            </p>
          ) : null}
          {error && <p className="error-msg field-span">{error}</p>}
          <div className="booking-actions field-span">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || !allAcknowledged || !typedSignatureOk || !emailOnFile}
            >
              {submitting ? 'Submitting…' : 'Sign agreement'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
