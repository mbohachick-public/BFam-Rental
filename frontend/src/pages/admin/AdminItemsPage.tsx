import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminDeleteVoid, adminGet, adminPatch, adminPost } from '../../api/client'
import { useAdminApiReady } from '../../hooks/useAdminApiReady'
import type { E2eCleanupResult, ItemSummary } from '../../types'

function money(s: string) {
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

export function AdminItemsPage() {
  const adminApiReady = useAdminApiReady()
  const [items, setItems] = useState<ItemSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [cleanupMsg, setCleanupMsg] = useState<string | null>(null)
  const [cleanupBusy, setCleanupBusy] = useState(false)
  const [rowBusyId, setRowBusyId] = useState<string | null>(null)

  const loadItems = useCallback(() => {
    if (!adminApiReady) return
    adminGet<ItemSummary[]>('/admin/items')
      .then(setItems)
      .catch((e: Error) => setError(e.message))
  }, [adminApiReady])

  useEffect(() => {
    loadItems()
  }, [loadItems])

  async function toggleVisibility(it: ItemSummary) {
    if (!adminApiReady) return
    const hide = it.active !== false
    const msg = hide
      ? `Hide "${it.title}" from the public catalog? Customers will no longer see it.`
      : `Show "${it.title}" in the public catalog again?`
    if (!window.confirm(msg)) return
    setRowBusyId(it.id)
    setError(null)
    try {
      await adminPatch<ItemSummary>(`/admin/items/${it.id}`, { active: !hide })
      loadItems()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Update failed')
    } finally {
      setRowBusyId(null)
    }
  }

  async function deleteItem(it: ItemSummary) {
    if (!adminApiReady) return
    const ok = window.confirm(
      `Permanently delete "${it.title}"? This removes the item, its calendar, images, ` +
        'and all related booking records. This cannot be undone.',
    )
    if (!ok) return
    setRowBusyId(it.id)
    setError(null)
    try {
      await adminDeleteVoid(`/admin/items/${it.id}`)
      loadItems()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setRowBusyId(null)
    }
  }

  async function runE2eCleanup() {
    if (!adminApiReady) return
    const ok = window.confirm(
      'Delete all catalog items in categories e2e-test and e2e-admin, ' +
        'including related bookings, calendar rows, and storage files? This cannot be undone.',
    )
    if (!ok) return
    setCleanupBusy(true)
    setCleanupMsg(null)
    setError(null)
    try {
      const res = await adminPost<E2eCleanupResult>('/admin/maintenance/cleanup-e2e-test-data', {
        confirm: true,
      })
      setCleanupMsg(
        `Removed ${res.items_deleted} item(s); cleaned files for ${res.bookings_processed_for_file_cleanup} booking(s).`,
      )
      loadItems()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Cleanup failed')
    } finally {
      setCleanupBusy(false)
    }
  }

  return (
    <div className="page-admin-items">
      <div className="page-head">
        <h1>Items</h1>
        <Link to="/admin/items/new" className="btn btn-primary">
          Add item
        </Link>
      </div>
      {error && <p className="error-msg">{error}</p>}
      <ul className="admin-table-list card">
        {items.map((it) => (
          <li
            key={it.id}
            className={`admin-table-row${it.active === false ? ' admin-table-row-inactive' : ''}`}
          >
            <div>
              <strong>{it.title}</strong>
              <span className="muted"> · {it.category}</span>
              {it.active === false && (
                <span className="admin-badge-inactive" title="Hidden from public catalog">
                  Inactive
                </span>
              )}
            </div>
            <div className="muted">{money(it.cost_per_day)} / day</div>
            <div className="admin-row-actions">
              <Link to={`/admin/items/${it.id}/edit`} className="btn btn-secondary btn-sm">
                Edit
              </Link>
              <Link to={`/admin/items/${it.id}/availability`} className="btn btn-secondary btn-sm">
                Calendar
              </Link>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={!adminApiReady || rowBusyId === it.id}
                onClick={() => void toggleVisibility(it)}
              >
                {rowBusyId === it.id ? 'Saving…' : it.active === false ? 'Show' : 'Hide'}
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm admin-btn-danger"
                disabled={!adminApiReady || rowBusyId === it.id}
                onClick={() => void deleteItem(it)}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
      {items.length === 0 && !error && <p className="muted">No items yet.</p>}

      <section className="card admin-e2e-cleanup" style={{ marginTop: '1.5rem' }}>
        <h2 className="h3" style={{ marginTop: 0 }}>
          Test data cleanup
        </h2>
        <p className="muted" style={{ marginBottom: '0.75rem' }}>
          Removes items whose category is <code>e2e-test</code> or <code>e2e-admin</code> (Playwright /
          API test data), related booking rows, and uploaded files.
        </p>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={!adminApiReady || cleanupBusy}
          onClick={() => void runE2eCleanup()}
        >
          {cleanupBusy ? 'Cleaning…' : 'Remove E2E test data'}
        </button>
        {cleanupMsg && <p className="success-msg" style={{ marginTop: '0.75rem' }}>{cleanupMsg}</p>}
      </section>
    </div>
  )
}
