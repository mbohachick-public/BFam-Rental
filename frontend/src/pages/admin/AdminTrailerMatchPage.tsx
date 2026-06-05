import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminGet } from '../../api/client'

type Row = {
  id: string
  created_at: string
  year: number
  make: string
  model: string
  trim_or_engine: string | null
  load_type: string
  estimated_amount: string
  mode: string | null
  recommended_trailer_type: string | null
  trailer_for_load: string | null
  estimated_trips: number | null
  job_fit: string | null
  vehicle_fit: string | null
  driver_fit: string | null
  confidence: string | null
  converted_to_booking: boolean
  delivery_cta_shown: boolean
  delivery_quote_clicked: boolean
  delivery_cta_reason: string | null
  warnings: string[]
}

function vehicleCell(r: Row) {
  const t = r.trim_or_engine ? ` ${r.trim_or_engine}` : ''
  return `${r.year} ${r.make} ${r.model}${t}`
}

function trailerLabel(t: string) {
  if (t === '10_7k') return "10′ 7k"
  if (t === '12_10k') return "12′ 10k"
  if (t === '12_12k') return "12′ 12k"
  return t
}

export function AdminTrailerMatchPage() {
  const [rows, setRows] = useState<Row[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    adminGet<Row[]>('/admin/trailer-match-requests')
      .then((data) => {
        if (!cancelled) {
          setRows(data)
          setError(null)
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="page-admin-items">
      <div className="page-head">
        <h1>Trailer Match requests</h1>
      </div>
      <p className="muted">Assistant runs for fleet planning. Delivery CTA = emphasize post-match delivery quote.</p>

      {loading ? <p className="muted">Loading…</p> : null}
      {error ? <p className="error-msg">{error}</p> : null}

      {!loading && !error ? (
        <ul className="admin-table-list card">
          {rows.length === 0 ? (
            <li className="admin-table-row">
              <span className="muted">No submissions yet.</span>
            </li>
          ) : (
            rows.map((r) => (
              <li key={r.id} className="admin-table-row">
                <div>
                  <strong>{new Date(r.created_at).toLocaleString()}</strong>
                  <span className="muted"> · {vehicleCell(r)}</span>
                </div>
                <div className="muted">
                  Mode: {r.mode ?? '—'} · Load: {r.load_type} · Amount: {r.estimated_amount} · Recommended:{' '}
                  {r.recommended_trailer_type ? trailerLabel(r.recommended_trailer_type) : '—'}
                  {r.trailer_for_load ? (
                    <>
                      {' '}
                      · Trailer for load: {trailerLabel(r.trailer_for_load)}
                    </>
                  ) : null}
                  {r.estimated_trips != null ? <> · Est. trips: {r.estimated_trips}</> : null}
                  {r.job_fit ? <> · Job fit: {r.job_fit}</> : null}
                  {r.vehicle_fit ? <> · Vehicle fit: {r.vehicle_fit}</> : null}
                  {r.driver_fit ? <> · Driver fit: {r.driver_fit}</> : null}
                  {r.confidence ? <> · Overall: {r.confidence}</> : null}
                  {' '}
                  · Booked: {r.converted_to_booking ? 'yes' : 'no'} · Delivery CTA emphasized:{' '}
                  {r.delivery_cta_shown ? 'yes' : 'no'} · Delivery quote clicked: {r.delivery_quote_clicked ? 'yes' : 'no'}
                </div>
                {r.delivery_cta_reason ? (
                  <p className="muted">
                    <span className="visually-hidden">Delivery CTA reason: </span>
                    {r.delivery_cta_reason}
                  </p>
                ) : null}
                {r.warnings.length > 0 ? <p className="muted">Warnings: {r.warnings.join(' · ')}</p> : null}
              </li>
            ))
          )}
        </ul>
      ) : null}

      <p>
        <Link to="/admin/bookings" className="nav-link">
          Booking requests
        </Link>
      </p>
    </div>
  )
}
