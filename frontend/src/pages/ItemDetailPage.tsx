import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiGet, apiPost, apiPostFormData } from '../api/client'
import { MonthCalendar } from '../components/MonthCalendar'
import { StatusLegend } from '../components/StatusLegend'
import { firstOfMonth, lastOfMonth } from '../lib/calendar'
import type { BookingQuote, DayAvailability, ItemDetail } from '../types'

function money(s: string) {
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

export function ItemDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [item, setItem] = useState<ItemDetail | null>(null)
  const [days, setDays] = useState<DayAvailability[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const now = new Date()
  const [calYear, setCalYear] = useState(now.getFullYear())
  const [calMonth, setCalMonth] = useState(now.getMonth() + 1)

  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [email, setEmail] = useState('')
  const [notes, setNotes] = useState('')
  const [quote, setQuote] = useState<BookingQuote | null>(null)
  const [quoteError, setQuoteError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitOk, setSubmitOk] = useState<string | null>(null)
  const [driversLicenseFile, setDriversLicenseFile] = useState<File | null>(null)
  const [licensePlateFile, setLicensePlateFile] = useState<File | null>(null)

  useEffect(() => {
    setDriversLicenseFile(null)
    setLicensePlateFile(null)
  }, [id])

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setLoading(true)
    setError(null)
    apiGet<ItemDetail>(`/items/${id}`)
      .then((data) => {
        if (!cancelled) setItem(data)
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
  }, [id])

  const fromTo = useMemo(
    () => ({
      from: firstOfMonth(calYear, calMonth),
      to: lastOfMonth(calYear, calMonth),
    }),
    [calYear, calMonth],
  )

  const loadAvailability = useCallback(() => {
    if (!id) return
    const q = new URLSearchParams({ from: fromTo.from, to: fromTo.to }).toString()
    apiGet<DayAvailability[]>(`/items/${id}/availability?${q}`)
      .then(setDays)
      .catch(() => setDays([]))
  }, [id, fromTo.from, fromTo.to])

  useEffect(() => {
    loadAvailability()
  }, [loadAvailability])

  function shiftMonth(delta: number) {
    const d = new Date(calYear, calMonth - 1 + delta, 1)
    setCalYear(d.getFullYear())
    setCalMonth(d.getMonth() + 1)
  }

  async function getQuote() {
    if (!id || !startDate || !endDate) {
      setQuoteError('Choose a start and end date.')
      return
    }
    setQuoteError(null)
    setQuote(null)
    try {
      const q = await apiPost<BookingQuote>('/booking-requests/quote', {
        item_id: id,
        start_date: startDate,
        end_date: endDate,
      })
      setQuote(q)
    } catch (e) {
      setQuoteError(e instanceof Error ? e.message : 'Quote failed')
    }
  }

  async function submitRequest() {
    if (!id || !startDate || !endDate || !item) return
    if (!driversLicenseFile) {
      setQuoteError('Please upload a photo of your driver’s license.')
      return
    }
    if (item.towable && !licensePlateFile) {
      setQuoteError('This item is towable — please upload a photo of your vehicle’s license plate.')
      return
    }
    setSubmitting(true)
    setSubmitOk(null)
    setQuoteError(null)
    try {
      const fd = new FormData()
      fd.append('item_id', id)
      fd.append('start_date', startDate)
      fd.append('end_date', endDate)
      if (email.trim()) fd.append('customer_email', email.trim())
      if (notes.trim()) fd.append('notes', notes.trim())
      fd.append('drivers_license', driversLicenseFile)
      if (item.towable && licensePlateFile) {
        fd.append('license_plate', licensePlateFile)
      }
      await apiPostFormData('/booking-requests', fd)
      setSubmitOk('Request submitted. We will follow up when it is reviewed.')
      setQuote(null)
      setDriversLicenseFile(null)
      setLicensePlateFile(null)
    } catch (e) {
      setQuoteError(e instanceof Error ? e.message : 'Submit failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="container">
        <p className="muted">Loading…</p>
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="container">
        <p className="error-msg">{error ?? 'Not found'}</p>
        <Link to="/catalog">Back to catalog</Link>
      </div>
    )
  }

  const mainImage = item.images[0]?.url ?? item.image_urls[0]

  return (
    <div className="container page-item">
      <p className="breadcrumb">
        <Link to="/catalog">Catalog</Link>
        <span aria-hidden> / </span>
        <span>{item.title}</span>
      </p>

      <div className="item-hero">
        <div className="item-gallery card">
          {mainImage ? (
            <img src={mainImage} alt="" className="item-hero-img" />
          ) : (
            <div className="item-hero-placeholder" />
          )}
          {item.images.length > 1 && (
            <ul className="item-thumbs">
              {item.images.map((im) => (
                <li key={im.id}>
                  <img src={im.url} alt="" loading="lazy" />
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="item-summary card card-pad">
          <h1>{item.title}</h1>
          <p className="muted">{item.category}</p>
          <dl className="attr-list">
            <div>
              <dt>Cost per day</dt>
              <dd>{money(item.cost_per_day)}</dd>
            </div>
            <div>
              <dt>Minimum rental</dt>
              <dd>
                {item.minimum_day_rental} day{item.minimum_day_rental === 1 ? '' : 's'}
              </dd>
            </div>
            <div>
              <dt>Deposit</dt>
              <dd>{money(item.deposit_amount)}</dd>
            </div>
            <div>
              <dt>Towable</dt>
              <dd>{item.towable ? 'Yes — license plate photo required to book' : 'No'}</dd>
            </div>
          </dl>
        </div>
      </div>

      <section className="card card-pad section-block">
        <h2>Description</h2>
        <p>{item.description || '—'}</p>
        <h3>User requirements</h3>
        <p>{item.user_requirements || '—'}</p>
      </section>

      <section className="section-block">
        <h2>Availability</h2>
        <p className="muted">Each date has one status. Book only on days marked open.</p>
        <StatusLegend />
        <div className="cal-nav">
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => shiftMonth(-1)}>
            Previous
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => shiftMonth(1)}>
            Next
          </button>
        </div>
        <MonthCalendar year={calYear} month={calMonth} days={days} />
      </section>

      <section className="card card-pad section-block booking-block">
        <h2>Request a booking</h2>
        <p className="muted">
          Pick a range within the next 60 days. All days must be open for booking. Discount: 5% per
          rental day, up to 15%. Upload a clear photo of your driver’s license (JPEG, PNG, or WebP,
          max 10 MB).
          {item.towable ? ' Towable rentals also require a photo of your tow vehicle’s license plate.' : ''}
        </p>
        <div className="booking-grid">
          <label className="field">
            <span className="field-label">Start date</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value)
                setQuote(null)
              }}
            />
          </label>
          <label className="field">
            <span className="field-label">End date</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value)
                setQuote(null)
              }}
            />
          </label>
          <label className="field field-span">
            <span className="field-label">Email (optional)</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </label>
          <label className="field field-span">
            <span className="field-label">Notes (optional)</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
          </label>
          <label className="field field-span">
            <span className="field-label">Driver’s license photo (required)</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => setDriversLicenseFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {item.towable && (
            <label className="field field-span">
              <span className="field-label">License plate photo (required for towable)</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => setLicensePlateFile(e.target.files?.[0] ?? null)}
              />
            </label>
          )}
        </div>
        {quoteError && <p className="error-msg">{quoteError}</p>}
        {submitOk && <p className="success-msg">{submitOk}</p>}
        <div className="booking-actions">
          <button type="button" className="btn btn-secondary" onClick={getQuote}>
            Get quote
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={submitRequest}
            disabled={
              submitting ||
              !quote ||
              !driversLicenseFile ||
              (item.towable ? !licensePlateFile : false)
            }
          >
            {submitting ? 'Sending…' : 'Submit request'}
          </button>
        </div>
        {quote && (
          <div className="quote card card-pad">
            <h3>Quote</h3>
            <ul className="quote-lines">
              <li>
                <span>Days</span>
                <span>{quote.num_days}</span>
              </li>
              <li>
                <span>Base rental</span>
                <span>{money(quote.base_amount)}</span>
              </li>
              <li>
                <span>Duration discount</span>
                <span>{quote.discount_percent}%</span>
              </li>
              <li>
                <span>Rental after discount</span>
                <span>{money(quote.discounted_subtotal)}</span>
              </li>
              <li>
                <span>Deposit (hold)</span>
                <span>{money(quote.deposit_amount)}</span>
              </li>
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
