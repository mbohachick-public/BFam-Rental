import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { adminDownloadBlob, adminGet } from '../../api/client'
import { useAdminApiReady } from '../../hooks/useAdminApiReady'
import type { BookingRequestOut } from '../../types'

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

function yesNo(v: boolean | null | undefined): string {
  if (v === true) return 'Yes'
  if (v === false) return 'No'
  return '—'
}

function text(v: string | null | undefined): string {
  const t = (v ?? '').trim()
  return t || '—'
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

export function AdminBookingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const adminApiReady = useAdminApiReady()
  const [row, setRow] = useState<BookingRequestOut | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!adminApiReady || !id) return
    adminGet<BookingRequestOut>(`/admin/booking-requests/${encodeURIComponent(id)}`)
      .then(setRow)
      .catch((e: Error) => {
        setRow(null)
        setError(e.message)
      })
  }, [adminApiReady, id])

  useEffect(() => {
    setError(null)
    load()
  }, [load])

  if (!id) {
    return (
      <div className="container">
        <p className="error-msg">Missing booking id.</p>
        <Link to="/admin/bookings">Back to booking requests</Link>
      </div>
    )
  }

  return (
    <div className="container page-admin-booking-detail">
      <p className="breadcrumb">
        <Link to="/admin/bookings">Booking requests</Link>
        <span aria-hidden> / </span>
        <span>Request detail</span>
      </p>
      <h1>Booking request</h1>
      {error && <p className="error-msg">{error}</p>}
      {!row && !error && <p className="muted">Loading…</p>}
      {row ? (
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
              <Link to={`/admin/items/${row.item_id}/edit`} className="nav-link">
                Open item in admin
              </Link>
              {' · '}
              <Link to={`/items/${row.item_id}`} className="nav-link" target="_blank" rel="noreferrer">
                View public item page
              </Link>
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
            <h2>Contact (as submitted)</h2>
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
            <h2>Delivery</h2>
            <dl className="attr-list">
              <DetailRow label="Delivery requested">{yesNo(row.delivery_requested)}</DetailRow>
              <DetailRow label="Delivery address">{text(row.delivery_address)}</DetailRow>
              <DetailRow label="Delivery fee (computed)">{money(row.delivery_fee)}</DetailRow>
              <DetailRow label="Delivery distance (miles)">
                {row.delivery_distance_miles != null && String(row.delivery_distance_miles).trim() !== ''
                  ? String(row.delivery_distance_miles)
                  : '—'}
              </DetailRow>
            </dl>
          </section>

          <section className="card card-pad section-block">
            <h2>Tow vehicle (if provided)</h2>
            <dl className="attr-list">
              <DetailRow label="Year">
                {row.tow_vehicle_year != null ? String(row.tow_vehicle_year) : '—'}
              </DetailRow>
              <DetailRow label="Make">{text(row.tow_vehicle_make)}</DetailRow>
              <DetailRow label="Model">{text(row.tow_vehicle_model)}</DetailRow>
              <DetailRow label="Tow rating (lbs)">
                {row.tow_vehicle_tow_rating_lbs != null
                  ? String(row.tow_vehicle_tow_rating_lbs)
                  : '—'}
              </DetailRow>
              <DetailRow label="Brake controller installed">{yesNo(row.has_brake_controller)}</DetailRow>
            </dl>
          </section>

          <section className="card card-pad section-block">
            <h2>Preferences & acknowledgments</h2>
            <dl className="attr-list">
              <DetailRow label="Payment method preference">
                {text(row.payment_method_preference)}
              </DetailRow>
              <DetailRow label="Repeat contractor">{yesNo(row.is_repeat_contractor)}</DetailRow>
              <DetailRow label="Understood request is not confirmed until approved">
                {yesNo(row.request_not_confirmed_ack)}
              </DetailRow>
            </dl>
          </section>

          <section className="card card-pad section-block">
            <h2>Pricing snapshot (at request time)</h2>
            <dl className="attr-list">
              <DetailRow label="Base / subtotal">{money(row.discounted_subtotal)}</DetailRow>
              <DetailRow label="Sales tax">{money(row.sales_tax_amount)}</DetailRow>
              <DetailRow label="Tax rate %">
                {row.sales_tax_rate_percent != null ? `${row.sales_tax_rate_percent}%` : '—'}
              </DetailRow>
              <DetailRow label="Total with tax">{money(row.rental_total_with_tax)}</DetailRow>
              <DetailRow label="Deposit">{money(row.deposit_amount)}</DetailRow>
              <DetailRow label="Tax source">{text(row.sales_tax_source)}</DetailRow>
            </dl>
          </section>

          <section className="card card-pad section-block">
            <h2>Uploaded documents</h2>
            <p className="admin-booking-docs small">
              {row.drivers_license_url ? (
                <button
                  type="button"
                  className="doc-link"
                  onClick={() => void openBookingDocument(row.drivers_license_url!, "driver's license")}
                >
                  Driver’s license
                </button>
              ) : (
                <span className="muted">No license on file</span>
              )}
              {row.license_plate_url ? (
                <>
                  {' · '}
                  <button
                    type="button"
                    className="doc-link"
                    onClick={() => void openBookingDocument(row.license_plate_url!, 'license plate photo')}
                  >
                    License plate
                  </button>
                </>
              ) : null}
              {row.insurance_card_url ? (
                <>
                  {' · '}
                  <button
                    type="button"
                    className="doc-link"
                    onClick={() => void openBookingDocument(row.insurance_card_url!, 'insurance card photo')}
                  >
                    Insurance card
                  </button>
                </>
              ) : null}
            </p>
          </section>

          <section className="card card-pad section-block muted-block">
            <h2>Workflow (after submission)</h2>
            <dl className="attr-list">
              <DetailRow label="Approved payment path">{text(row.payment_path)}</DetailRow>
              <DetailRow label="Decline reason">{text(row.decline_reason)}</DetailRow>
              <DetailRow label="Payment collection URL">
                {row.payment_collection_url ? (
                  <a href={row.payment_collection_url} target="_blank" rel="noreferrer">
                    open
                  </a>
                ) : (
                  '—'
                )}
              </DetailRow>
            </dl>
          </section>
        </>
      ) : null}
    </div>
  )
}
