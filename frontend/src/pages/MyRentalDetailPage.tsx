import { useEffect, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiGet, bookingDownloadBlob } from '../api/client'
import { useCustomerSession } from '../context/CustomerSessionContext'
import type { CustomerBookingDetail } from '../types'

async function openBookingAsset(url: string | null | undefined, label: string) {
  if (!url) return
  try {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      window.open(url, '_blank', 'noopener,noreferrer')
      return
    }
    const path = url.startsWith('/') ? url : `/${url}`
    const blob = await bookingDownloadBlob(path)
    const obj = URL.createObjectURL(blob)
    const w = window.open(obj, '_blank', 'noopener,noreferrer')
    if (!w) URL.revokeObjectURL(obj)
    else setTimeout(() => URL.revokeObjectURL(obj), 120_000)
  } catch (e) {
    window.alert(e instanceof Error ? e.message : `Could not open ${label}`)
  }
}

function money(s: string | null | undefined) {
  if (s == null || s === '') return '—'
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

function text(v: string | null | undefined): string {
  const t = (v ?? '').trim()
  return t || '—'
}

function yesNo(v: boolean | null | undefined): string {
  if (v === true) return 'Yes'
  if (v === false) return 'No'
  return '—'
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

export function MyRentalDetailPage() {
  const { id } = useParams<{ id: string }>()
  const customer = useCustomerSession()
  const customerSignedIn = customer.mode === 'auth0' && customer.isAuthenticated
  const [row, setRow] = useState<CustomerBookingDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!customerSignedIn || !id) return
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
      setLoading(true)
      setError(null)
      apiGet<CustomerBookingDetail>(`/booking-requests/mine/${encodeURIComponent(id)}`)
        .then((data) => {
          if (!cancelled) setRow(data)
        })
        .catch((e: Error) => {
          if (!cancelled) {
            setRow(null)
            setError(e.message)
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    })
    return () => {
      cancelled = true
    }
  }, [customerSignedIn, id])

  if (customer.mode !== 'auth0') {
    return (
      <div className="container">
        <h1>Rental details</h1>
        <p className="muted">Sign-in accounts are not enabled in this environment.</p>
        <Link to="/catalog">Back to catalog</Link>
      </div>
    )
  }

  if (!customer.isAuthenticated) {
    return (
      <div className="container">
        <h1>Rental details</h1>
        <p className="muted">Sign in to view this rental.</p>
        <button type="button" className="btn btn-secondary" onClick={() => customer.login()}>
          Sign in
        </button>
      </div>
    )
  }

  if (!id) {
    return (
      <div className="container">
        <p className="error-msg">Missing rental id.</p>
        <Link to="/my-rentals">Back to my rentals</Link>
      </div>
    )
  }

  return (
    <div className="container page-my-rental-detail">
      <p className="breadcrumb">
        <Link to="/catalog">Catalog</Link>
        <span aria-hidden> / </span>
        <Link to="/my-rentals">My rentals</Link>
        <span aria-hidden> / </span>
        <span>Details</span>
      </p>
      <h1>Rental details</h1>
      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error-msg">{error}</p>}
      {row && !loading && (
        <>
          <div className="card card-pad admin-booking-detail-meta">
            <p className="admin-booking-detail-status">
              <strong>{row.status}</strong>
              <span className="muted">
                {' '}
                · {row.start_date} → {row.end_date}
              </span>
            </p>
            <p className="muted small">
              Request id: <code>{row.id}</code>
            </p>
            <p>
              {row.item_active !== false ? (
                <Link to={`/items/${row.item_id}`} className="nav-link">
                  View item in catalog
                </Link>
              ) : (
                <span className="muted">This item is no longer in the catalog.</span>
              )}
            </p>
          </div>

          <section className="card card-pad section-block">
            <h2>Rental</h2>
            <dl className="attr-list">
              <DetailRow label="Item">{text(row.item_title)}</DetailRow>
              <DetailRow label="Start date">{row.start_date}</DetailRow>
              <DetailRow label="End date">{row.end_date}</DetailRow>
            </dl>
          </section>

          <section className="card card-pad section-block">
            <h2>Your contact information</h2>
            <dl className="attr-list">
              <DetailRow label="Email">{text(row.customer_email)}</DetailRow>
              <DetailRow label="Phone">{text(row.customer_phone)}</DetailRow>
              <DetailRow label="First name">{text(row.customer_first_name)}</DetailRow>
              <DetailRow label="Last name">{text(row.customer_last_name)}</DetailRow>
              <DetailRow label="Address">{text(row.customer_address)}</DetailRow>
              <DetailRow label="Company / contractor name">{text(row.company_name)}</DetailRow>
              <DetailRow label="Notes">{text(row.notes)}</DetailRow>
            </dl>
          </section>

          <section className="card card-pad section-block">
            <h2>Logistics</h2>
            <dl className="attr-list">
              <DetailRow label="Delivery requested">{yesNo(row.delivery_requested)}</DetailRow>
              <DetailRow label="Pickup from site (after rental)">{yesNo(row.pickup_from_site_requested)}</DetailRow>
              <DetailRow label="Job site / delivery address">{text(row.delivery_address)}</DetailRow>
              <DetailRow label="Delivery fee">{money(row.delivery_fee)}</DetailRow>
              <DetailRow label="Return pickup fee">{money(row.pickup_fee)}</DetailRow>
            </dl>
          </section>

          <section className="card card-pad section-block">
            <h2>Pricing</h2>
            <dl className="attr-list">
              <DetailRow label="Discounted subtotal">{money(row.discounted_subtotal)}</DetailRow>
              <DetailRow label="Rental total (with tax)">{money(row.rental_total_with_tax)}</DetailRow>
              <DetailRow label="Security deposit">{money(row.deposit_amount)}</DetailRow>
            </dl>
          </section>

          <section className="card card-pad section-block">
            <h2>Documents you submitted</h2>
            <p className="muted small">
              Uploaded IDs and photos open in a new tab. Some links expire after a short time when using cloud
              storage.
            </p>
            <ul className="my-rental-doc-actions">
              <li>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={!row.drivers_license_url}
                  onClick={() => openBookingAsset(row.drivers_license_url, "Driver's license")}
                >
                  Driver&apos;s license
                </button>
              </li>
              <li>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={!row.license_plate_url}
                  onClick={() => openBookingAsset(row.license_plate_url, 'License plate photo')}
                >
                  License plate photo
                </button>
              </li>
              <li>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={!row.insurance_card_url}
                  onClick={() => openBookingAsset(row.insurance_card_url, 'Insurance card')}
                >
                  Insurance card
                </button>
              </li>
            </ul>
          </section>

          <section className="card card-pad section-block">
            <h2>Signed agreement</h2>
            {row.has_executed_contract ? (
              <p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() =>
                    openBookingAsset(
                      `/booking-requests/mine/${encodeURIComponent(row.id)}/executed-contract`,
                      'Signed rental packet',
                    )
                  }
                >
                  Open signed rental packet (PDF)
                </button>
              </p>
            ) : (
              <p className="muted">No executed agreement is on file yet for this request.</p>
            )}
          </section>

          <section className="card card-pad section-block">
            <h2>Payment &amp; signing</h2>
            <dl className="attr-list">
              <DetailRow label="Agreement signed at">{text(row.agreement_signed_at)}</DetailRow>
              <DetailRow label="Rental paid at">{text(row.rental_paid_at)}</DetailRow>
              <DetailRow label="Deposit secured at">{text(row.deposit_secured_at)}</DetailRow>
            </dl>
            {row.stripe_checkout_url ? (
              <p className="small" style={{ marginTop: '0.75rem' }}>
                <a href={row.stripe_checkout_url} target="_blank" rel="noreferrer">
                  Pay rental balance (Stripe)
                </a>
              </p>
            ) : null}
            {row.stripe_deposit_checkout_url ? (
              <p className="small">
                <a href={row.stripe_deposit_checkout_url} target="_blank" rel="noreferrer">
                  Pay security deposit (Stripe)
                </a>
              </p>
            ) : null}
            {row.payment_collection_url ? (
              <p className="small">
                <a href={row.payment_collection_url} target="_blank" rel="noreferrer">
                  Payment / next steps (link from rental team)
                </a>
              </p>
            ) : null}
            {row.signing_url ? (
              <p className="small">
                <a href={row.signing_url} target="_blank" rel="noreferrer">
                  Open signing page
                </a>
              </p>
            ) : null}
          </section>
        </>
      )}
    </div>
  )
}
