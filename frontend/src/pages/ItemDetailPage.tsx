import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiGet, apiPost } from '../api/client'
import { useCustomerSession } from '../context/CustomerSessionContext'
import { MonthCalendar } from '../components/MonthCalendar'
import { StatusLegend } from '../components/StatusLegend'
import { firstOfMonth, lastOfMonth } from '../lib/calendar'
import type { BookingIntakeOut, BookingQuote, CustomerContactProfile, DayAvailability, ItemDetail } from '../types'

function money(s: string) {
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

/** Short, user-friendly copy for quote/intake failures tied to job site / routing. */
function prettifyLogisticsErrorMessage(raw: string): string {
  const d = raw.trim()
  if (!d) {
    return 'We couldn’t estimate logistics for this address. Try a fuller street address, city, state, and ZIP, or contact us.'
  }
  const lower = d.toLowerCase()

  if (
    lower.includes('outside the maximum service distance') ||
    lower.includes('outside our delivery zone') ||
    lower.includes('maximum service distance')
  ) {
    const m = d.match(/(\d+(?:\.\d+)?)\s*mi/i) ?? d.match(/\((\d+(?:\.\d+)?)\s*mile/i)
    const cap = m ? m[1] : null
    return cap
      ? `That location looks beyond our service area (${cap}-mile limit). Try a different address or contact us.`
      : 'That location looks beyond our service area. Try a different address or contact us.'
  }

  if (lower.includes('delivery is not enabled')) {
    return 'Delivery routing isn’t available right now. Contact the rental office or choose “I will pick up and return the trailer.”'
  }

  if (lower.includes('google maps api key')) {
    return 'Distance routing isn’t set up on our end yet. Contact us and we’ll help with your estimate.'
  }

  if (lower.includes('delivery origin is not configured') || lower.includes('admin → delivery')) {
    return 'Our depot address isn’t configured for routing yet. Contact us for a delivery estimate.'
  }

  if (
    lower.includes('route not found') ||
    lower.includes('address is required when') ||
    lower.includes('job site address is required')
  ) {
    return 'Enter a complete job site address (street, city, state, ZIP) so we can estimate delivery and pickup.'
  }

  if (lower.includes('this item does not offer delivery') || lower.includes('does not offer delivery or pickup')) {
    return 'This equipment isn’t offered with delivery or site pickup. Choose customer pickup instead.'
  }

  if (lower.includes('distance matrix')) {
    return 'We couldn’t look up driving distance for that address. Check spelling and include city and state.'
  }

  // Avoid dumping multi-line dev messages; use the first clear sentence
  const oneLine = d.replace(/\s+/g, ' ')
  const dot = oneLine.search(/\.(\s|$)/)
  const firstBit = dot > 0 ? oneLine.slice(0, dot + 1).trim() : oneLine
  return firstBit.length > 220 ? `${firstBit.slice(0, 217)}…` : firstBit
}

export function ItemDetailPage() {
  const navigate = useNavigate()
  const customer = useCustomerSession()
  const customerSignedIn = customer.mode === 'auth0' && customer.isAuthenticated
  const authBlocksSubmit = customer.mode === 'auth0' && !customer.isLoading && !customer.isAuthenticated
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
  const [phone, setPhone] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [notes, setNotes] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [customerAddress, setCustomerAddress] = useState('')
  const [deliverToSite, setDeliverToSite] = useState(false)
  const [pickupFromSite, setPickupFromSite] = useState(false)
  const [logisticsAddress, setLogisticsAddress] = useState('')
  const [quote, setQuote] = useState<BookingQuote | null>(null)
  const [quoteError, setQuoteError] = useState<string | null>(null)
  const [logisticsAddressError, setLogisticsAddressError] = useState<string | null>(null)
  const [quoting, setQuoting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  type IntakeSubmitPhase = 'idle' | 'saving' | 'email' | 'redirect'
  const [submitPhase, setSubmitPhase] = useState<IntakeSubmitPhase>('idle')
  const [activeImageIdx, setActiveImageIdx] = useState(0)

  const sortedImages = useMemo(
    () => (item ? [...item.images].sort((a, b) => a.sort_order - b.sort_order) : []),
    [item],
  )

  useEffect(() => {
    setActiveImageIdx(0)
    setCompanyName('')
    setDeliverToSite(false)
    setPickupFromSite(false)
    setLogisticsAddress('')
    setFirstName('')
    setLastName('')
    setCustomerAddress('')
    setLogisticsAddressError(null)
  }, [id])

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setLoading(true)
    setError(null)
    apiGet<ItemDetail>(`/items/${id}`)
      .then((data) => {
        if (!cancelled) {
          setItem(data)
        }
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

  useEffect(() => {
    if (!customerSignedIn || !id) return
    let cancelled = false
    apiGet<CustomerContactProfile>('/booking-requests/me/contact')
      .then((p) => {
        if (cancelled) return
        setEmail((prev) => (prev.trim() ? prev : p.customer_email))
        setPhone((prev) => (prev.trim() ? prev : p.customer_phone))
        setFirstName((prev) => (prev.trim() ? prev : p.customer_first_name))
        setLastName((prev) => (prev.trim() ? prev : p.customer_last_name))
        setCustomerAddress((prev) => (prev.trim() ? prev : p.customer_address))
      })
      .catch(() => {
        /* 404 = no prior bookings */
      })
    return () => {
      cancelled = true
    }
  }, [id, customerSignedIn])

  useEffect(() => {
    if (item && item.delivery_available === false) {
      setDeliverToSite(false)
      setPickupFromSite(false)
      setLogisticsAddress('')
      setQuote(null)
      setLogisticsAddressError(null)
    }
  }, [item])

  useEffect(() => {
    if (!id || !item || authBlocksSubmit) return

    const handle = window.setTimeout(() => {
      void (async () => {
        if (!startDate || !endDate) {
          setQuote(null)
          setLogisticsAddressError(null)
          return
        }
        const em = email.trim()
        if (!em) {
          setQuote(null)
          setLogisticsAddressError(null)
          return
        }
        const custAddr = customerAddress.trim()
        if (!custAddr) {
          setQuote(null)
          setLogisticsAddressError(null)
          return
        }
        if (item.delivery_available && (deliverToSite || pickupFromSite) && !logisticsAddress.trim()) {
          setQuote(null)
          setLogisticsAddressError(null)
          return
        }
        setQuoteError(null)
        setLogisticsAddressError(null)
        setQuoting(true)
        try {
          const q = await apiPost<BookingQuote>('/booking-requests/quote', {
            item_id: id,
            start_date: startDate,
            end_date: endDate,
            customer_email: em,
            customer_address: custAddr,
            ...(!item.delivery_available
              ? { delivery_requested: false, pickup_from_site_requested: false }
              : {
                  delivery_requested: deliverToSite,
                  pickup_from_site_requested: pickupFromSite,
                  ...((deliverToSite || pickupFromSite)
                    ? { job_site_address: logisticsAddress.trim() }
                    : {}),
                }),
          })
          setQuote(q)
        } catch (e) {
          setQuote(null)
          const msg = e instanceof Error ? e.message : 'Quote failed'
          const logisticsContext =
            item.delivery_available && (deliverToSite || pickupFromSite) && logisticsAddress.trim().length > 0
          if (logisticsContext) {
            setLogisticsAddressError(prettifyLogisticsErrorMessage(msg))
            setQuoteError(null)
          } else {
            setQuoteError(msg)
            setLogisticsAddressError(null)
          }
        } finally {
          setQuoting(false)
        }
      })()
    }, 450)

    return () => window.clearTimeout(handle)
  }, [
    id,
    item,
    authBlocksSubmit,
    startDate,
    endDate,
    email,
    deliverToSite,
    pickupFromSite,
    logisticsAddress,
    customerAddress,
  ])

  function shiftMonth(delta: number) {
    const d = new Date(calYear, calMonth - 1 + delta, 1)
    setCalYear(d.getFullYear())
    setCalMonth(d.getMonth() + 1)
  }

  async function submitRequest() {
    if (!id || !startDate || !endDate || !item) return
    if (!quote) {
      setQuoteError('Please wait for your estimate to finish updating.')
      setLogisticsAddressError(null)
      return
    }
    const em = email.trim()
    const ph = phone.trim()
    const fn = firstName.trim()
    const ln = lastName.trim()
    if (!em) {
      setQuoteError('Email is required.')
      setLogisticsAddressError(null)
      return
    }
    if (ph.length < 7) {
      setQuoteError('Please enter a valid phone number (at least 7 digits).')
      setLogisticsAddressError(null)
      return
    }
    if (!fn || !ln) {
      setQuoteError('First and last name are required.')
      setLogisticsAddressError(null)
      return
    }
    const custAddr = customerAddress.trim()
    if (!custAddr) {
      setQuoteError('Customer address is required.')
      setLogisticsAddressError(null)
      return
    }
    if (item.delivery_available && (deliverToSite || pickupFromSite) && !logisticsAddress.trim()) {
      setLogisticsAddressError('Enter a complete job site address (street, city, state, ZIP).')
      setQuoteError(null)
      return
    }
    setSubmitting(true)
    setSubmitPhase('saving')
    setQuoteError(null)
    setLogisticsAddressError(null)
    const phaseTimer = window.setTimeout(() => {
      setSubmitPhase((p) => (p === 'saving' ? 'email' : p))
    }, 500)
    let ok = false
    try {
      const out = await apiPost<BookingIntakeOut>('/booking-requests/intake', {
        item_id: id,
        start_date: startDate,
        end_date: endDate,
        customer_email: em,
        customer_phone: ph,
        customer_first_name: fn,
        customer_last_name: ln,
        customer_address: custAddr,
        notes: notes.trim() || undefined,
        company_name: companyName.trim() || undefined,
        delivery_requested: Boolean(item.delivery_available && deliverToSite),
        pickup_from_site_requested: Boolean(item.delivery_available && pickupFromSite),
        ...(item.delivery_available && (deliverToSite || pickupFromSite)
          ? { job_site_address: logisticsAddress.trim() }
          : {}),
      })
      ok = true
      window.clearTimeout(phaseTimer)
      setSubmitPhase('redirect')
      navigate(out.complete_path)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Submit failed'
      const logisticsContext =
        item.delivery_available && (deliverToSite || pickupFromSite) && logisticsAddress.trim().length > 0
      if (
        logisticsContext &&
        /address|delivery|pickup|mile|route|logistics|job site|outside|maps|distance/i.test(msg)
      ) {
        setLogisticsAddressError(prettifyLogisticsErrorMessage(msg))
        setQuoteError(null)
      } else {
        setQuoteError(msg)
        setLogisticsAddressError(null)
      }
    } finally {
      window.clearTimeout(phaseTimer)
      if (!ok) {
        setSubmitting(false)
        setSubmitPhase('idle')
      }
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

  const displayImageIdx =
    sortedImages.length === 0 ? 0 : Math.min(activeImageIdx, sortedImages.length - 1)

  const mainImage =
    sortedImages.length > 0 ? sortedImages[displayImageIdx]?.url : item.image_urls[0]

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
          {sortedImages.length > 1 && (
            <ul className="item-thumbs">
              {sortedImages.map((im, idx) => (
                <li key={im.id}>
                  <button
                    type="button"
                    className={`item-thumb-btn${idx === displayImageIdx ? ' item-thumb-btn-active' : ''}`}
                    onClick={() => setActiveImageIdx(idx)}
                    aria-pressed={idx === displayImageIdx}
                    aria-label={`View image ${idx + 1} of ${sortedImages.length}`}
                  >
                    <img src={im.url} alt="" loading="lazy" />
                  </button>
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
              <dd>{item.towable ? 'Yes — you will confirm towing on step 2' : 'No'}</dd>
            </div>
            <div>
              <dt>Delivery</dt>
              <dd>
                {item.delivery_available === false
                  ? 'Pickup only at our location'
                  : 'Pickup or delivery to your site — choose transport options when requesting'}
              </dd>
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
        <h2>Step 1 of 2 — Request booking</h2>
        <p className="muted">Reserve your trailer in under 60 seconds. No payment required yet.</p>
        {customer.mode === 'auth0' && !customer.isLoading && !customer.isAuthenticated && (
          <p className="booking-auth-hint">
            <span className="muted">Sign in to see pricing and submit a booking request.</span>{' '}
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => customer.login()}>
              Sign in
            </button>
          </p>
        )}
        <form
          className="booking-form"
          autoComplete="on"
          onSubmit={(e) => {
            e.preventDefault()
          }}
        >
          <div className="booking-grid">
            <label className="field">
              <span className="field-label">Start date</span>
              <input
                type="date"
                name="booking_start_date"
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
                name="booking_end_date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value)
                  setQuote(null)
                }}
              />
            </label>
            <label className="field field-span">
              <span className="field-label">Email (required)</span>
              <input
                type="email"
                name="customer_email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="section-booking email"
                required
              />
            </label>
            <label className="field field-span">
              <span className="field-label">Phone (required)</span>
              <input
                type="tel"
                name="customer_phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                autoComplete="section-booking tel"
                inputMode="tel"
                required
              />
            </label>
            <label className="field">
              <span className="field-label">First name (required)</span>
              <input
                type="text"
                name="customer_first_name"
                id="booking-given-name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                autoComplete="section-booking given-name"
                required
              />
            </label>
            <label className="field">
              <span className="field-label">Last name (required)</span>
              <input
                type="text"
                name="customer_last_name"
                id="booking-family-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                autoComplete="section-booking family-name"
                required
              />
            </label>
            <label className="field field-span">
              <span className="field-label">Customer address (required)</span>
              <textarea
                value={customerAddress}
                onChange={(e) => {
                  setCustomerAddress(e.target.value)
                  setQuote(null)
                }}
                rows={3}
                name="customer_address"
                autoComplete="street-address"
                placeholder="Street, city, state, ZIP"
                required
              />
              <span className="muted small">
                Used for billing, contract, and tax purposes.
              </span>
            </label>
            {item.delivery_available ? (
              <fieldset className="field field-span booking-transport-fieldset">
                <legend className="field-label">Transport options</legend>
                <label className="field field-checkbox field-span booking-transport-radio">
                  <input
                    type="radio"
                    name="transport_self"
                    checked={!deliverToSite && !pickupFromSite}
                    onChange={() => {
                      setDeliverToSite(false)
                      setPickupFromSite(false)
                      setQuote(null)
                      setLogisticsAddressError(null)
                    }}
                  />
                  <span>I will pick up and return the trailer</span>
                </label>
                <label className="field field-checkbox field-span">
                  <input
                    type="checkbox"
                    checked={deliverToSite}
                    onChange={(e) => {
                      setDeliverToSite(e.target.checked)
                      setQuote(null)
                      setLogisticsAddressError(null)
                    }}
                  />
                  <span>Deliver trailer to my site</span>
                </label>
                <label className="field field-checkbox field-span">
                  <input
                    type="checkbox"
                    checked={pickupFromSite}
                    onChange={(e) => {
                      setPickupFromSite(e.target.checked)
                      setQuote(null)
                      setLogisticsAddressError(null)
                    }}
                  />
                  <span>Pick up trailer from my site after rental</span>
                </label>
                <p className="muted small field-span">
                  Logistics availability and final pricing will be reviewed before approval.
                </p>
                {(deliverToSite || pickupFromSite) ? (
                  <label className="field field-span">
                    <span className="field-label">Job site address</span>
                    <input
                      type="text"
                      name="job_site_address"
                      id="booking-job-site-address"
                      value={logisticsAddress}
                      onChange={(e) => {
                        setLogisticsAddress(e.target.value)
                        setQuote(null)
                        setLogisticsAddressError(null)
                      }}
                      autoComplete="street-address"
                      placeholder="Street, city, state, ZIP"
                      aria-invalid={logisticsAddressError ? true : undefined}
                      aria-describedby={
                        logisticsAddressError
                          ? 'logistics-address-hint logistics-address-error'
                          : 'logistics-address-hint'
                      }
                    />
                    <span id="logistics-address-hint" className="muted small">
                      Used for delivery and/or pickup routing.
                    </span>
                    {logisticsAddressError ? (
                      <p id="logistics-address-error" className="logistics-address-error" role="alert">
                        {logisticsAddressError}
                      </p>
                    ) : null}
                  </label>
                ) : null}
              </fieldset>
            ) : null}
            <label className="field field-span">
              <span className="field-label">Notes (optional)</span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                name="booking_notes"
                placeholder="Example: Deliver 8–10am on start date; pickup after 3pm on return date (we’ll confirm)."
              />
              <span className="muted small">
                If you chose delivery or pickup from your site, note your requested delivery time and pickup
                time here — we’ll confirm when we approve your request.
              </span>
            </label>
            <label className="field field-span">
              <span className="field-label">Company / contractor name (optional)</span>
              <input
                type="text"
                name="customer_company"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                autoComplete="section-booking organization"
              />
            </label>
            <p className="muted small field-span tight-top">
              This is a request, not a confirmed reservation until we approve it.
            </p>
          </div>
          {quoteError ? <p className="error-msg booking-form-alert">{quoteError}</p> : null}
          <div className="quote card card-pad">
            <h3>Estimate</h3>
            {quoting ? <p className="muted small">Updating your estimate...</p> : null}
            {quote ? (
              <>
                <ul className="quote-lines">
                  <li>
                    <span>Days</span>
                    <span>{quote.num_days}</span>
                  </li>
                  <li>
                    <span>Rental (estimated)</span>
                    <span>{money(quote.discounted_subtotal)}</span>
                  </li>
                  {quote.delivery_fee != null && Number(quote.delivery_fee) > 0 ? (
                    <li>
                      <span>
                        Delivery (estimated)
                        {quote.delivery_distance_miles != null &&
                        quote.delivery_distance_miles !== '' ? (
                          <span className="muted">
                            {' '}
                            (~{Number(quote.delivery_distance_miles)} mi one-way)
                          </span>
                        ) : null}
                      </span>
                      <span>{money(quote.delivery_fee)}</span>
                    </li>
                  ) : null}
                  {quote.pickup_fee != null && Number(quote.pickup_fee) > 0 ? (
                    <li>
                      <span>
                        Pickup (estimated)
                        {quote.pickup_distance_miles != null &&
                        quote.pickup_distance_miles !== '' ? (
                          <span className="muted">
                            {' '}
                            (~{Number(quote.pickup_distance_miles)} mi one-way)
                          </span>
                        ) : null}
                      </span>
                      <span>{money(quote.pickup_fee)}</span>
                    </li>
                  ) : null}
                  <li>
                    <span>Subtotal (before tax)</span>
                    <span>
                      {money(
                        String(
                          Number(quote.discounted_subtotal) +
                            Number(quote.delivery_fee || 0) +
                            Number(quote.pickup_fee || 0),
                        ),
                      )}
                    </span>
                  </li>
                  <li>
                    <span>Sales tax ({Number(quote.sales_tax_rate_percent)}%)</span>
                    <span>{money(quote.sales_tax_amount)}</span>
                  </li>
                  <li>
                    <span>Total (estimated, with tax)</span>
                    <span>{money(quote.rental_total_with_tax)}</span>
                  </li>
                  <li>
                    <span>Deposit (hold)</span>
                    <span>{money(quote.deposit_amount)}</span>
                  </li>
                </ul>
                <p className="muted small quote-logistics-note">
                  Final logistics pricing confirmed after approval.
                </p>
              </>
            ) : !quoting && !authBlocksSubmit ? (
              <p className="muted small">Enter dates and your email to see pricing.</p>
            ) : !quoting && authBlocksSubmit ? (
              <p className="muted small">Sign in to see pricing for your dates.</p>
            ) : null}
          </div>
          <p className="muted small field-span booking-step1-cta-hint">
            Request your dates — we’ll review and confirm availability shortly.
          </p>
          {submitting ? (
            <div className="booking-submit-status field-span card card-pad" aria-live="polite">
              <p className="booking-submit-status-title">Requesting your booking…</p>
              <p className="muted small">This usually takes a few seconds.</p>
              <ul className="booking-submit-checklist">
                <li
                  className={
                    submitPhase === 'saving'
                      ? 'active'
                      : submitPhase === 'email' || submitPhase === 'redirect'
                        ? 'done'
                        : undefined
                  }
                >
                  Saving your request…
                </li>
                <li
                  className={
                    submitPhase === 'email'
                      ? 'active'
                      : submitPhase === 'redirect'
                        ? 'done'
                        : undefined
                  }
                >
                  Sending confirmation to your email…
                </li>
                <li className={submitPhase === 'redirect' ? 'active' : undefined}>
                  Opening the next step…
                </li>
              </ul>
            </div>
          ) : null}
          <div className="booking-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void submitRequest()}
              disabled={
                quoting ||
                submitting ||
                authBlocksSubmit ||
                !quote ||
                !email.trim() ||
                phone.trim().length < 7 ||
                !firstName.trim() ||
                !lastName.trim() ||
                !customerAddress.trim() ||
                (item.delivery_available &&
                  (deliverToSite || pickupFromSite) &&
                  !logisticsAddress.trim())
              }
            >
              {submitting ? 'Sending…' : 'Request booking'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
