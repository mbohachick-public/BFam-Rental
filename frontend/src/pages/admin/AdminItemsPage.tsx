import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminGet } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import type { ItemSummary } from '../../types'

function money(s: string) {
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

export function AdminItemsPage() {
  const { adminToken } = useAuth()
  const [items, setItems] = useState<ItemSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!adminToken) return
    adminGet<ItemSummary[]>('/admin/items', adminToken)
      .then(setItems)
      .catch((e: Error) => setError(e.message))
  }, [adminToken])

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
            </div>
          </li>
        ))}
      </ul>
      {items.length === 0 && !error && <p className="muted">No items yet.</p>}
    </div>
  )
}
