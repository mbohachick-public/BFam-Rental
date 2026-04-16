import { useCallback, useEffect, useState } from 'react'
import { adminDownloadBlob, adminGet, adminPost, adminPostNoBody } from '../../api/client'
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

export function AdminBookingsPage() {
  const adminApiReady = useAdminApiReady()
  const [rows, setRows] = useState<BookingRequestOut[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [declineForId, setDeclineForId] = useState<string | null>(null)
  const [declineReason, setDeclineReason] = useState('')
  const [declineError, setDeclineError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!adminApiReady) return
    adminGet<BookingRequestOut[]>('/admin/booking-requests')
      .then(setRows)
      .catch((e: Error) => setError(e.message))
  }, [adminApiReady])

  useEffect(() => {
    load()
  }, [load])

  async function accept(id: string) {
    if (!adminApiReady) return
    setBusyId(id)
    setError(null)
    try {
      await adminPostNoBody<BookingRequestOut>(`/admin/booking-requests/${id}/accept`)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Accept failed')
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
        {rows.map((r) => (
          <li key={r.id} className="admin-table-row admin-booking-row">
            <div>
              <strong>{r.status}</strong>
              <span className="muted">
                {' '}
                · {r.start_date} → {r.end_date}
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
            {r.status === 'rejected' && r.decline_reason ? (
              <div className="small admin-decline-reason">
                <strong>Decline reason:</strong> {r.decline_reason}
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
            <div className="admin-row-actions">
              {r.status === 'pending' && (
                <>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={busyId === r.id}
                    onClick={() => accept(r.id)}
                  >
                    {busyId === r.id ? '…' : 'Accept'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={busyId === r.id}
                    onClick={() => openDecline(r.id)}
                  >
                    Decline
                  </button>
                </>
              )}
            </div>
          </li>
        ))}
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
