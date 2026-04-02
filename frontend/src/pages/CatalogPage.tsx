import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../api/client'
import type { ItemSummary } from '../types'

function money(s: string) {
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

function bumpInt(raw: string, delta: number): string {
  const n = parseInt(raw, 10)
  const base = Number.isFinite(n) ? n : 0
  return String(Math.max(0, base + delta))
}

export function CatalogPage() {
  const [items, setItems] = useState<ItemSummary[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [minCost, setMinCost] = useState('')
  const [maxCost, setMaxCost] = useState('')
  const [openFrom, setOpenFrom] = useState('')
  const [openTo, setOpenTo] = useState('')

  const dateFilterInvalid =
    (openFrom !== '' && openTo === '') || (openFrom === '' && openTo !== '')
  const dateRangeReversed =
    openFrom !== '' && openTo !== '' && openFrom > openTo

  const query = useMemo(() => {
    const p = new URLSearchParams()
    if (category.trim()) p.set('category', category.trim())
    if (minCost.trim() !== '') p.set('min_cost_per_day', minCost.trim())
    if (maxCost.trim() !== '') p.set('max_cost_per_day', maxCost.trim())
    if (openFrom && openTo && !dateRangeReversed) {
      p.set('open_from', openFrom)
      p.set('open_to', openTo)
    }
    const q = p.toString()
    return q ? `?${q}` : ''
  }, [category, minCost, maxCost, openFrom, openTo, dateRangeReversed])

  useEffect(() => {
    let cancelled = false
    apiGet<string[]>('/items/categories')
      .then((data) => {
        if (!cancelled) setCategories(data)
      })
      .catch(() => {
        if (!cancelled) setCategories([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (dateFilterInvalid || dateRangeReversed) {
      setItems([])
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    apiGet<ItemSummary[]>(`/items${query}`)
      .then((data) => {
        if (!cancelled) setItems(data)
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
  }, [query, dateFilterInvalid, dateRangeReversed])

  return (
    <div className="container page-catalog">
      <h1>Catalog</h1>
      <p className="muted">
        Filter by category, whole-dollar daily rate, and optional date range (every day in the range
        must be open for booking).
      </p>

      <form
        className="filters card card-pad"
        onSubmit={(e) => {
          e.preventDefault()
        }}
      >
        <div className="filters-grid filters-grid-wide">
          <label className="field">
            <span className="field-label">Category</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              aria-label="Category"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Min $ / day</span>
            <div className="number-stepper">
              <button
                type="button"
                className="btn btn-secondary btn-sm stepper-btn"
                aria-label="Decrease min price by 1"
                onClick={() => setMinCost((v) => bumpInt(v, -1))}
              >
                −
              </button>
              <input
                type="number"
                min={0}
                step={1}
                inputMode="numeric"
                value={minCost}
                onChange={(e) => setMinCost(e.target.value)}
                aria-label="Minimum dollars per day"
              />
              <button
                type="button"
                className="btn btn-secondary btn-sm stepper-btn"
                aria-label="Increase min price by 1"
                onClick={() => setMinCost((v) => bumpInt(v, 1))}
              >
                +
              </button>
            </div>
          </label>
          <label className="field">
            <span className="field-label">Max $ / day</span>
            <div className="number-stepper">
              <button
                type="button"
                className="btn btn-secondary btn-sm stepper-btn"
                aria-label="Decrease max price by 1"
                onClick={() => setMaxCost((v) => bumpInt(v, -1))}
              >
                −
              </button>
              <input
                type="number"
                min={0}
                step={1}
                inputMode="numeric"
                value={maxCost}
                onChange={(e) => setMaxCost(e.target.value)}
                aria-label="Maximum dollars per day"
              />
              <button
                type="button"
                className="btn btn-secondary btn-sm stepper-btn"
                onClick={() => setMaxCost((v) => bumpInt(v, 1))}
              >
                +
              </button>
            </div>
          </label>
          <label className="field">
            <span className="field-label">Open from</span>
            <input
              type="date"
              value={openFrom}
              onChange={(e) => setOpenFrom(e.target.value)}
              aria-label="Open for booking from date"
            />
          </label>
          <label className="field">
            <span className="field-label">Open through</span>
            <input
              type="date"
              value={openTo}
              onChange={(e) => setOpenTo(e.target.value)}
              aria-label="Open for booking through date"
            />
          </label>
        </div>
        {dateFilterInvalid && (
          <p className="error-msg" role="status">
            Select both start and end dates to filter by days open for booking, or clear both.
          </p>
        )}
        {dateRangeReversed && (
          <p className="error-msg" role="status">
            “Open from” must be on or before “Open through”.
          </p>
        )}
      </form>

      {loading && !dateFilterInvalid && !dateRangeReversed && (
        <p className="muted">Loading…</p>
      )}
      {error && <p className="error-msg">{error}</p>}

      {!loading &&
        !error &&
        !dateFilterInvalid &&
        !dateRangeReversed &&
        items.length === 0 && <p className="muted">No items match. Try clearing filters.</p>}

      <ul className="catalog-grid">
        {items.map((item) => (
          <li key={item.id}>
            <Link to={`/items/${item.id}`} className="catalog-card card">
              <div className="catalog-thumb">
                {item.image_urls[0] ? (
                  <img src={item.image_urls[0]} alt="" loading="lazy" />
                ) : (
                  <div className="catalog-thumb-placeholder" aria-hidden />
                )}
              </div>
              <div className="catalog-card-body">
                <h2 className="catalog-title">{item.title}</h2>
                <p className="catalog-meta muted">
                  {item.category}
                  {item.towable ? <span className="tag-towable">Towable</span> : null}
                </p>
                <p className="catalog-price">{money(item.cost_per_day)} / day</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
