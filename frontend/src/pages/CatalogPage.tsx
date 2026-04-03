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

/** Upper bound for the price slider; above this we do not send `max_cost_per_day` (no ceiling). */
const PRICE_SLIDER_MAX = 500

export function CatalogPage() {
  const [items, setItems] = useState<ItemSummary[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [rangeMin, setRangeMin] = useState(0)
  const [rangeMax, setRangeMax] = useState(PRICE_SLIDER_MAX)
  const [openFrom, setOpenFrom] = useState('')
  const [openTo, setOpenTo] = useState('')

  const dateFilterInvalid =
    (openFrom !== '' && openTo === '') || (openFrom === '' && openTo !== '')
  const dateRangeReversed =
    openFrom !== '' && openTo !== '' && openFrom > openTo

  const query = useMemo(() => {
    const p = new URLSearchParams()
    if (category.trim()) p.set('category', category.trim())
    if (rangeMin > 0) p.set('min_cost_per_day', String(rangeMin))
    if (rangeMax < PRICE_SLIDER_MAX) p.set('max_cost_per_day', String(rangeMax))
    if (openFrom && openTo && !dateRangeReversed) {
      p.set('open_from', openFrom)
      p.set('open_to', openTo)
    }
    const q = p.toString()
    return q ? `?${q}` : ''
  }, [category, rangeMin, rangeMax, openFrom, openTo, dateRangeReversed])

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
        Filter by category, daily rate range (drag both handles), and optional date range (every day
        in the range must be open for booking).
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
          <div className="field field-price-range">
            <span className="field-label" id="price-range-label">
              $ / day (left = minimum, right = maximum)
            </span>
            <div
              className="dual-range"
              role="group"
              aria-labelledby="price-range-label"
            >
              <div className="dual-range-track" aria-hidden />
              <div
                className="dual-range-fill"
                style={{
                  left: `${(rangeMin / PRICE_SLIDER_MAX) * 100}%`,
                  width: `${((rangeMax - rangeMin) / PRICE_SLIDER_MAX) * 100}%`,
                }}
                aria-hidden
              />
              <input
                type="range"
                className="dual-range-input dual-range-input-min"
                min={0}
                max={PRICE_SLIDER_MAX}
                step={1}
                value={rangeMin}
                aria-label="Minimum dollars per day"
                onChange={(e) => {
                  const v = Number(e.target.value)
                  setRangeMin(Math.min(v, rangeMax))
                }}
              />
              <input
                type="range"
                className="dual-range-input dual-range-input-max"
                min={0}
                max={PRICE_SLIDER_MAX}
                step={1}
                value={rangeMax}
                aria-label="Maximum dollars per day"
                onChange={(e) => {
                  const v = Number(e.target.value)
                  setRangeMax(Math.max(v, rangeMin))
                }}
              />
            </div>
            <div className="dual-range-ticks" aria-hidden>
              <span>$0</span>
              <span>${PRICE_SLIDER_MAX}+</span>
            </div>
            <div className="dual-range-values muted small">
              <span>
                {rangeMin > 0
                  ? `At least ${money(String(rangeMin))} / day`
                  : 'No minimum'}
              </span>
              <span>
                {rangeMax < PRICE_SLIDER_MAX
                  ? `Up to ${money(String(rangeMax))} / day`
                  : 'No maximum'}
              </span>
            </div>
          </div>
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
