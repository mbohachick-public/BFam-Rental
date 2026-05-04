import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiGet } from '../api/client'
import { useCustomerSession } from '../context/CustomerSessionContext'
import type { CustomerBookingSummary } from '../types'

function money(s: string | null | undefined) {
  if (s == null || s === '') return '—'
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

export function MyRentalsPage() {
  const navigate = useNavigate()
  const customer = useCustomerSession()
  const customerSignedIn = customer.mode === 'auth0' && customer.isAuthenticated
  const [rows, setRows] = useState<CustomerBookingSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!customerSignedIn) return
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
      setLoading(true)
      setError(null)
      apiGet<CustomerBookingSummary[]>('/booking-requests/mine')
        .then((data) => {
          if (!cancelled) setRows(data)
        })
        .catch((e: Error) => {
          if (!cancelled) setError(e.message)
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    })
    return () => {
      cancelled = true
    }
  }, [customerSignedIn])

  if (customer.mode !== 'auth0') {
    return (
      <div className="container">
        <h1>My rentals</h1>
        <p className="muted">Sign-in accounts are not enabled in this environment.</p>
        <Link to="/catalog">Back to catalog</Link>
      </div>
    )
  }

  if (!customer.isAuthenticated) {
    return (
      <div className="container">
        <h1>My rentals</h1>
        <p className="muted">Sign in to see your rental requests.</p>
        <button type="button" className="btn btn-secondary" onClick={() => customer.login()}>
          Sign in
        </button>
      </div>
    )
  }

  return (
    <div className="container page-my-rentals">
      <p className="breadcrumb">
        <Link to="/catalog">Catalog</Link>
        <span aria-hidden> / </span>
        <span>My rentals</span>
      </p>
      <h1>My rentals</h1>
      <p className="muted">
        Booking requests tied to your account (requested, approved, confirmed, declined, etc.). Select a
        row to view full details, documents, and your signed agreement when available.
      </p>
      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error-msg">{error}</p>}
      {!loading && !error && rows.length === 0 && (
        <p className="muted">You have not submitted any booking requests yet.</p>
      )}
      {!loading && !error && rows.length > 0 && (
        <ul className="admin-table-list card">
          {rows.map((r) => (
            <li
              key={r.id}
              className="admin-table-row my-rentals-row-li"
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/my-rentals/${encodeURIComponent(r.id)}`)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  navigate(`/my-rentals/${encodeURIComponent(r.id)}`)
                }
              }}
            >
              <div>
                <strong>{r.status}</strong>
                <span className="muted">
                  {' '}
                  · {r.start_date} → {r.end_date}
                </span>
              </div>
              <div>
                <span className="my-rentals-item-title">{r.item_title}</span>
                {!r.item_active ? (
                  <span className="muted">
                    {' '}
                    (not in catalog)
                  </span>
                ) : null}
              </div>
              <div className="muted small">
                Subtotal {money(r.discounted_subtotal)}
                {r.rental_total_with_tax != null && r.rental_total_with_tax !== '' ? (
                  <> · Total with tax {money(r.rental_total_with_tax)}</>
                ) : null}
                {r.deposit_amount != null && r.deposit_amount !== '' ? (
                  <> · Deposit {money(r.deposit_amount)}</>
                ) : null}
              </div>
              {r.payment_collection_url ? (
                <div className="small" style={{ marginTop: '0.35rem' }}>
                  <a
                    href={r.payment_collection_url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Payment / next steps
                  </a>
                </div>
              ) : null}
              {r.stripe_checkout_url ? (
                <div className="small" style={{ marginTop: '0.35rem' }}>
                  <a
                    href={r.stripe_checkout_url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Pay rental balance (secure card checkout)
                  </a>
                </div>
              ) : null}
              {r.stripe_deposit_checkout_url ? (
                <div className="small" style={{ marginTop: '0.35rem' }}>
                  <a
                    href={r.stripe_deposit_checkout_url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Pay security deposit (Stripe)
                  </a>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
