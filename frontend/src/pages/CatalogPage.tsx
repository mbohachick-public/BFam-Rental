import { useEffect, useMemo, useRef, useState } from 'react'
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
  const [filtersOpen, setFiltersOpen] = useState(false)
  const filtersRef = useRef<HTMLDetailsElement | null>(null)
  const [category, setCategory] = useState('')
  const [rangeMin, setRangeMin] = useState(0)
  const [rangeMax, setRangeMax] = useState(PRICE_SLIDER_MAX)
  const [openFrom, setOpenFrom] = useState('')
  const [openTo, setOpenTo] = useState('')

  const dateFilterInvalid =
    (openFrom !== '' && openTo === '') || (openFrom === '' && openTo !== '')
  const dateRangeReversed =
    openFrom !== '' && openTo !== '' && openFrom > openTo

  const hasActiveFilters =
    category.trim() !== '' ||
    rangeMin > 0 ||
    rangeMax < PRICE_SLIDER_MAX ||
    openFrom !== '' ||
    openTo !== ''

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

  const listBlocked = dateFilterInvalid || dateRangeReversed

  useEffect(() => {
    if (listBlocked) return

    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
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
    })
    return () => {
      cancelled = true
    }
  }, [query, listBlocked])

  const displayItems = listBlocked ? [] : items
  const displayLoading = listBlocked ? false : loading
  const displayError = listBlocked ? null : error

  return (
    <div className="container page-catalog">
      <h1>Catalog</h1>
      <p className="muted">
        Filter by category, daily rate range (drag both handles), and optional date range (every day
        in the range must be open for booking).
      </p>

      <details
        ref={filtersRef}
        className="filters-collapsible card"
        onToggle={(e) => setFiltersOpen((e.currentTarget as HTMLDetailsElement).open)}
      >
        <summary className="filters-summary">
          <span className="filters-summary-title">Filters</span>
          {hasActiveFilters ? <span className="filters-summary-pill">Active</span> : null}
          <span className="filters-summary-hint muted small" aria-hidden>
            {filtersOpen ? 'Hide' : 'Show'}
          </span>
        </summary>
        <form
          className="filters filters-body"
          onSubmit={(e) => {
            e.preventDefault()
            if (filtersRef.current) filtersRef.current.open = false
            setFiltersOpen(false)
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
              <div className="dual-range" role="group" aria-labelledby="price-range-label">
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
                <span>{rangeMin > 0 ? `At least ${money(String(rangeMin))} / day` : 'No minimum'}</span>
                <span>{rangeMax < PRICE_SLIDER_MAX ? `Up to ${money(String(rangeMax))} / day` : 'No maximum'}</span>
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

          <div className="filters-actions">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!hasActiveFilters}
              onClick={() => {
                setCategory('')
                setRangeMin(0)
                setRangeMax(PRICE_SLIDER_MAX)
                setOpenFrom('')
                setOpenTo('')
              }}
            >
              Clear
            </button>
            <button type="submit" className="btn btn-primary">
              Done
            </button>
          </div>
        </form>
      </details>

      {displayLoading && <p className="muted">Loading…</p>}
      {displayError && <p className="error-msg">{displayError}</p>}

      {!displayLoading &&
        !displayError &&
        !listBlocked &&
        displayItems.length === 0 && <p className="muted">No items match. Try clearing filters.</p>}

      <ul className="catalog-grid">
        {displayItems.map((item) => (
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
                  {item.delivery_available === false ? (
                    <span className="tag-pickup-only">Pickup only</span>
                  ) : (
                    <span className="tag-delivery">Delivery OK</span>
                  )}
                </p>
                <p className="catalog-price">{money(item.cost_per_day)} / day</p>
                <p className="catalog-deposit muted small">Deposit {money(item.deposit_amount)}</p>
                <p className="catalog-cta" aria-hidden>
                  Request booking →
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
