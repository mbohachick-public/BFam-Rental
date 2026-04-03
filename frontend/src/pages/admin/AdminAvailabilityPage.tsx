import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { adminGet, adminPut } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { firstOfMonth, iterDaysInMonth, lastOfMonth } from '../../lib/calendar'
import type { DayAvailability, DayStatus, ItemDetail } from '../../types'

const STATUSES: DayStatus[] = [
  'open_for_booking',
  'booked',
  'out_for_use',
  'readying_for_use',
]

function label(s: DayStatus): string {
  return s.replace(/_/g, ' ')
}

export function AdminAvailabilityPage() {
  const { id } = useParams<{ id: string }>()
  const { adminToken } = useAuth()
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [item, setItem] = useState<ItemDetail | null>(null)
  const [edits, setEdits] = useState<Record<string, DayStatus>>({})
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<string | null>(null)

  const from = useMemo(() => firstOfMonth(year, month), [year, month])
  const to = useMemo(() => lastOfMonth(year, month), [year, month])

  const loadItem = useCallback(() => {
    if (!id || !adminToken) return
    adminGet<ItemDetail>(`/admin/items/${id}`, adminToken)
      .then(setItem)
      .catch(() => setItem(null))
  }, [id, adminToken])

  const loadAvailability = useCallback(() => {
    if (!id || !adminToken) return
    const q = new URLSearchParams({ from, to }).toString()
    adminGet<DayAvailability[]>(`/admin/items/${id}/availability?${q}`, adminToken)
      .then((d) => {
        const next: Record<string, DayStatus> = {}
        for (const row of d) {
          if (row.status) next[row.day] = row.status
        }
        setEdits(next)
      })
      .catch(() => {
        setEdits({})
      })
  }, [id, from, to, adminToken])

  useEffect(() => {
    loadItem()
  }, [loadItem])

  useEffect(() => {
    loadAvailability()
  }, [loadAvailability])

  function statusForDay(dayIso: string): DayStatus {
    return edits[dayIso] ?? 'open_for_booking'
  }

  function setDay(dayIso: string, st: DayStatus) {
    setEdits((prev) => ({ ...prev, [dayIso]: st }))
    setSaved(null)
  }

  async function saveMonth() {
    if (!id || !adminToken) return
    setSaving(true)
    setError(null)
    setSaved(null)
    const days = iterDaysInMonth(year, month).map((d) => ({
      day: d,
      status: statusForDay(d),
    }))
    try {
      await adminPut(`/admin/items/${id}/availability`, adminToken, { days })
      setSaved('Saved.')
      loadAvailability()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  function shiftMonth(delta: number) {
    const d = new Date(year, month - 1 + delta, 1)
    setYear(d.getFullYear())
    setMonth(d.getMonth() + 1)
  }

  if (!id) return null

  const title = item?.title ?? 'Item'

  return (
    <div className="page-admin-availability">
      <p className="breadcrumb">
        <Link to="/admin/items">Items</Link>
        <span aria-hidden> / </span>
        <span>{title}</span>
        <span aria-hidden> / </span>
        <span>Calendar</span>
      </p>
      <h1>Availability — {title}</h1>
      {item && item.active === false && (
        <p className="admin-inactive-banner">
          This item is <strong>inactive</strong> (hidden from the public catalog).
        </p>
      )}
      <p className="muted">Set one status per date for this month, then save.</p>

      <div className="cal-nav">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => shiftMonth(-1)}>
          Previous month
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => shiftMonth(1)}>
          Next month
        </button>
      </div>

      {error && <p className="error-msg">{error}</p>}
      {saved && <p className="success-msg">{saved}</p>}

      <div className="card card-pad admin-avail-table-wrap">
        <table className="admin-avail-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {iterDaysInMonth(year, month).map((dayIso) => {
              const d = new Date(dayIso + 'T12:00:00')
              return (
                <tr key={dayIso}>
                  <td>{d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</td>
                  <td>
                    <select
                      value={statusForDay(dayIso)}
                      onChange={(e) => setDay(dayIso, e.target.value as DayStatus)}
                      aria-label={`Status for ${dayIso}`}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {label(s)}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <button type="button" className="btn btn-primary" onClick={saveMonth} disabled={saving}>
        {saving ? 'Saving…' : 'Save month'}
      </button>
    </div>
  )
}
